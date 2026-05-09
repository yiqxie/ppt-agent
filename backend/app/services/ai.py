"""Azure OpenAI 多模态分析服务。

向 GPT-4o（或 gpt-4.5-preview）发送 slide 截图，
让模型从风格、配色、布局、配图等角度提取一段可复用的 prompt 模板，
并自动产出标题、摘要、tag 列表、结构化样式元数据。
"""

from __future__ import annotations

import base64
import json
from typing import Optional

from loguru import logger
from openai import AsyncAzureOpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ..core.config import Settings, get_settings
from ..db.session import AsyncSessionLocal
from .system_config import DEFAULT_STAGE_PROMPTS, get_system_config_dict


class AIAnalysisError(RuntimeError):
    """AI 分析失败异常。"""


def _extract_json_object(content: str) -> str:
    """从模型输出中提取 JSON 对象字符串。"""
    text = (content or "").strip()
    if not text:
        return "{}"

    # 优先处理 markdown code fence。
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            candidate = part.strip()
            if candidate.lower().startswith("json"):
                candidate = candidate[4:].strip()
            if candidate.startswith("{") and candidate.endswith("}"):
                return candidate

    if text.startswith("{") and text.endswith("}"):
        return text

    # 回退：提取首个完整 JSON 对象。
    start = text.find("{")
    if start < 0:
        return text
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return text


def _pick_first_str(data: dict, keys: list[str]) -> str:
    for key in keys:
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _pick_first_list(data: dict, keys: list[str]) -> list[str]:
    for key in keys:
        val = data.get(key)
        if isinstance(val, list):
            out = [str(v).strip() for v in val if str(v).strip()]
            if out:
                return out
    return []


def _normalize_style(style_raw: dict) -> dict:
    color_raw = style_raw.get("color_palette") or style_raw.get("colors") or {}
    if not isinstance(color_raw, dict):
        color_raw = {}

    style = {
        "overall_style": str(
            style_raw.get("overall_style")
            or style_raw.get("overall")
            or style_raw.get("style")
            or ""
        ).strip(),
        "typography": str(
            style_raw.get("typography") or style_raw.get("font_style") or ""
        ).strip(),
        "layout": str(style_raw.get("layout") or "").strip(),
        "imagery": str(
            style_raw.get("imagery")
            or style_raw.get("image_style")
            or style_raw.get("visual_style")
            or ""
        ).strip(),
        "color_palette": {
            "primary": str(color_raw.get("primary") or color_raw.get("main") or "").strip(),
            "secondary": str(color_raw.get("secondary") or "").strip(),
            "accent": str(color_raw.get("accent") or color_raw.get("highlight") or "").strip(),
            "background": str(color_raw.get("background") or color_raw.get("bg") or "").strip(),
        },
    }
    return style


def _normalize_analysis_payload(data: dict) -> dict:
    title = _pick_first_str(data, ["title", "page_title", "topic", "theme"])
    summary = _pick_first_str(data, ["summary", "overview", "description", "desc"])
    prompt = _pick_first_str(
        data,
        [
            "prompt",
            "prompt_template",
            "template",
            "style_prompt",
            "visual_prompt",
            "instructions",
            "analysis",
        ],
    )
    tags = _pick_first_list(data, ["tags", "keywords", "design_keywords"])

    style_raw = data.get("style")
    if not isinstance(style_raw, dict):
        style_raw = data.get("style_meta") if isinstance(data.get("style_meta"), dict) else {}

    style = _normalize_style(style_raw)

    # 若模型未给 prompt 字段，尽量从摘要/风格中补一个可读文本，避免页面出现空白。
    if not prompt:
        prompt = summary or style.get("overall_style", "")

    if not title:
        title = "未命名 slide"

    return {
        "title": title[:200],
        "summary": summary[:500],
        "prompt": prompt,
        "tags": tags[:12],
        "style": style,
    }


class AIAnalysisService:
    """封装 Azure OpenAI 多模态分析。"""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self._client: Optional[AsyncAzureOpenAI] = None

    def _get_client(self) -> AsyncAzureOpenAI:
        """惰性构建 Azure OpenAI 客户端。"""
        if self._client is not None:
            return self._client
        if not self.settings.azure_openai_endpoint:
            raise AIAnalysisError("未配置 azure_openai_endpoint")
        # 优先使用 API Key；生产环境也可以扩展为 AAD token
        if not self.settings.azure_openai_api_key:
            raise AIAnalysisError("未配置 azure_openai_api_key")
        self._client = AsyncAzureOpenAI(
            azure_endpoint=self.settings.azure_openai_endpoint,
            api_key=self.settings.azure_openai_api_key,
            api_version=self.settings.azure_openai_api_version,
        )
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def analyze_slide(self, image_bytes: bytes, image_mime: str = "image/png") -> dict:
        """分析单张 slide 截图，返回结构化结果。

        参数：
            image_bytes: 截图原始字节
            image_mime: 截图 MIME 类型（默认 png）

        返回：
            {
                "title": str,
                "summary": str,
                "prompt": str,
                "tags": List[str],
                "style": dict,
            }
        """
        client = self._get_client()
        b64 = base64.b64encode(image_bytes).decode("ascii")
        data_url = f"data:{image_mime};base64,{b64}"

        # 每次调用前读取系统配置，让页面上的模型/提示词调整即时生效。
        async with AsyncSessionLocal() as session:
            runtime_cfg = await get_system_config_dict(session)

        slide_prompt_cfg = runtime_cfg.get("stage_prompts", {}).get(
            "slide_analysis", DEFAULT_STAGE_PROMPTS["slide_analysis"]
        )
        system_prompt = str(
            slide_prompt_cfg.get("system_prompt")
            or DEFAULT_STAGE_PROMPTS["slide_analysis"]["system_prompt"]
        )
        user_prompt = str(
            slide_prompt_cfg.get("user_prompt")
            or DEFAULT_STAGE_PROMPTS["slide_analysis"]["user_prompt"]
        )

        model_settings = runtime_cfg.get("model_settings", {})
        temperature = float(model_settings.get("temperature", 0.3))
        max_tokens = int(
            model_settings.get(
                "max_completion_tokens", model_settings.get("max_tokens", 1200)
            )
        )
        model_name = str(
            runtime_cfg.get("default_model_deployment")
            or self.settings.azure_openai_vision_deployment
        )

        try:
            resp = await client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    },
                ],
                temperature=temperature,
                max_completion_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
        except Exception as exc:  # pragma: no cover
            logger.exception("Azure OpenAI 调用失败")
            raise AIAnalysisError(f"Azure OpenAI 调用失败：{exc}") from exc

        content = resp.choices[0].message.content or "{}"
        normalized_content = _extract_json_object(content)
        try:
            data = json.loads(normalized_content)
        except json.JSONDecodeError as exc:
            logger.error(f"AI 输出非合法 JSON，原始内容片段：{content[:400]}")
            raise AIAnalysisError("AI 输出非合法 JSON") from exc

        if not isinstance(data, dict):
            raise AIAnalysisError("AI 输出 JSON 不是对象")

        normalized = _normalize_analysis_payload(data)
        if not normalized["summary"] and not normalized["prompt"]:
            logger.warning(
                f"AI 输出字段不完整，keys={list(data.keys())[:20]} model={model_name}"
            )
        return normalized

    async def close(self) -> None:
        """关闭客户端。"""
        if self._client is not None:
            await self._client.close()
            self._client = None


# 全局单例
_ai_service: Optional[AIAnalysisService] = None


def get_ai_service() -> AIAnalysisService:
    """返回全局 AIAnalysisService 实例。"""
    global _ai_service
    if _ai_service is None:
        _ai_service = AIAnalysisService()
    return _ai_service
