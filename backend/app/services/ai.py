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


# 系统提示词：定义输出 JSON Schema，便于稳定解析
_SYSTEM_PROMPT = """你是一名资深的 PPT 视觉设计分析师与 prompt 工程师。
用户会提供一张 PPT slide 的截图，请你从以下维度做分析：
1. 整体风格（如：商务简洁、科技未来、手绘扁平、杂志排版等）
2. 配色方案（主色 / 辅色 / 强调色，使用 hex）
3. 字体观感（衬线 / 无衬线 / 手写体；中英文倾向）
4. 布局结构（左右分栏 / 顶部标题 + 内容、卡片网格等）
5. 配图与图标风格（写实 / 矢量 / 插画；是否有图标、数据图表、人物等）
6. slide 主题（用一句话总结这页讲什么）

最终请严格输出一个 JSON 对象，**不要输出任何额外文字或 markdown 围栏**，结构如下：
{
  "title": "<不超过 30 字的页面标题>",
  "summary": "<不超过 80 字的中文摘要>",
  "prompt": "<一段中文的 prompt 模板，描述此 slide 的视觉风格、配色、布局、配图，可被其他生成式工具直接复用，长度 150-400 字>",
  "tags": ["<3-8 个中文短标签，覆盖风格、行业、主题、用途>"],
  "style": {
    "overall_style": "<整体风格简述>",
    "color_palette": {
      "primary": "#RRGGBB",
      "secondary": "#RRGGBB",
      "accent": "#RRGGBB",
      "background": "#RRGGBB"
    },
    "typography": "<字体观感>",
    "layout": "<布局结构>",
    "imagery": "<配图风格>"
  }
}
若无法判断某字段，请使用合理的默认值，但保持 JSON 结构完整。"""


class AIAnalysisError(RuntimeError):
    """AI 分析失败异常。"""


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

        try:
            resp = await client.chat.completions.create(
                model=self.settings.azure_openai_vision_deployment,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "请分析这张 PPT slide 截图。"},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    },
                ],
                temperature=0.3,
                max_tokens=1200,
                response_format={"type": "json_object"},
            )
        except Exception as exc:  # pragma: no cover
            logger.exception("Azure OpenAI 调用失败")
            raise AIAnalysisError(f"Azure OpenAI 调用失败：{exc}") from exc

        content = resp.choices[0].message.content or "{}"
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.error(f"AI 输出非合法 JSON：{content[:200]}")
            raise AIAnalysisError("AI 输出非合法 JSON") from exc

        # 字段兜底，避免后续 KeyError
        return {
            "title": str(data.get("title", "")).strip()[:200] or "未命名 slide",
            "summary": str(data.get("summary", "")).strip()[:500],
            "prompt": str(data.get("prompt", "")).strip(),
            "tags": [str(t).strip() for t in data.get("tags", []) if str(t).strip()][:12],
            "style": data.get("style") if isinstance(data.get("style"), dict) else {},
        }

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
