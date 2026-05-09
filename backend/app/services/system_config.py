"""系统配置服务。

负责系统配置单例的初始化、读取与更新：
- Azure Foundry 链接
- 模型候选与默认模型
- 模型参数
- 分阶段提示词模板
"""

from __future__ import annotations

from typing import Any, Dict
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..models.models import SystemConfig

SYSTEM_CONFIG_KEY = "default"

DEFAULT_STAGE_PROMPTS: Dict[str, Dict[str, str]] = {
    "slide_analysis": {
        "system_prompt": "你是一名资深的 PPT 视觉设计分析师与 prompt 工程师。\n用户会提供一张 PPT slide 的截图，请你从以下维度做分析：\n1. 整体风格（如：商务简洁、科技未来、手绘扁平、杂志排版等）\n2. 配色方案（主色 / 辅色 / 强调色，使用 hex）\n3. 字体观感（衬线 / 无衬线 / 手写体；中英文倾向）\n4. 布局结构（左右分栏 / 顶部标题 + 内容、卡片网格等）\n5. 配图与图标风格（写实 / 矢量 / 插画；是否有图标、数据图表、人物等）\n6. slide 主题（用一句话总结这页讲什么）\n\n最终请严格输出一个 JSON 对象，**不要输出任何额外文字或 markdown 围栏**，结构如下：\n{\n  \"title\": \"<不超过 30 字的页面标题>\",\n  \"summary\": \"<不超过 80 字的中文摘要>\",\n  \"prompt\": \"<一段中文的 prompt 模板，描述此 slide 的视觉风格、配色、布局、配图，可被其他生成式工具直接复用，长度 150-400 字>\",\n  \"tags\": [\"<3-8 个中文短标签，覆盖风格、行业、主题、用途>\"],\n  \"style\": {\n    \"overall_style\": \"<整体风格简述>\",\n    \"color_palette\": {\n      \"primary\": \"#RRGGBB\",\n      \"secondary\": \"#RRGGBB\",\n      \"accent\": \"#RRGGBB\",\n      \"background\": \"#RRGGBB\"\n    },\n    \"typography\": \"<字体观感>\",\n    \"layout\": \"<布局结构>\",\n    \"imagery\": \"<配图风格>\"\n  }\n}\n若无法判断某字段，请使用合理的默认值，但保持 JSON 结构完整。",
        "user_prompt": "请分析这张 PPT slide 截图。",
    },
    "prompt_refine": {
        "system_prompt": "你是一名提示词优化助手，请在不改变原意的前提下提升提示词可执行性。",
        "user_prompt": "请优化以下提示词：{{prompt}}",
    },
    "tag_generation": {
        "system_prompt": "你是一名内容标签助手，请输出简洁、可检索的中文标签。",
        "user_prompt": "请基于以下内容生成 3-8 个标签：{{content}}",
    },
}

DEFAULT_MODEL_SETTINGS: Dict[str, Any] = {
    "temperature": 0.3,
    "max_tokens": 1200,
    "top_p": 1.0,
}


def _sanitize_candidates(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()]


async def get_or_create_system_config(session: AsyncSession) -> SystemConfig:
    """读取系统配置单例，不存在则创建默认配置。"""
    stmt = select(SystemConfig).where(SystemConfig.config_key == SYSTEM_CONFIG_KEY)
    config = (await session.execute(stmt)).scalar_one_or_none()
    if config is not None:
        return config

    settings = get_settings()
    config = SystemConfig(
        id=uuid4(),
        config_key=SYSTEM_CONFIG_KEY,
        azure_foundry_url="",
        default_model_deployment=settings.azure_openai_vision_deployment,
        model_candidates=[
            settings.azure_openai_vision_deployment,
            "gpt-4.1",
            "gpt-4.1-mini",
        ],
        model_settings=DEFAULT_MODEL_SETTINGS,
        stage_prompts=DEFAULT_STAGE_PROMPTS,
    )
    session.add(config)
    await session.commit()
    await session.refresh(config)
    return config


async def get_system_config_dict(session: AsyncSession) -> dict[str, Any]:
    """返回前端可直接消费的系统配置字典。"""
    config = await get_or_create_system_config(session)

    # 兜底，避免历史脏数据导致字段缺失
    stage_prompts = config.stage_prompts if isinstance(config.stage_prompts, dict) else {}
    model_settings = config.model_settings if isinstance(config.model_settings, dict) else {}

    merged_stage_prompts = {**DEFAULT_STAGE_PROMPTS, **stage_prompts}
    merged_model_settings = {**DEFAULT_MODEL_SETTINGS, **model_settings}

    return {
        "azure_foundry_url": config.azure_foundry_url or "",
        "default_model_deployment": config.default_model_deployment,
        "model_candidates": _sanitize_candidates(config.model_candidates),
        "model_settings": merged_model_settings,
        "stage_prompts": merged_stage_prompts,
        "updated_at": config.updated_at,
    }


async def update_system_config(session: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    """更新系统配置并返回最新值。"""
    config = await get_or_create_system_config(session)

    if payload.get("azure_foundry_url") is not None:
        config.azure_foundry_url = str(payload["azure_foundry_url"]).strip()

    if payload.get("default_model_deployment") is not None:
        config.default_model_deployment = str(payload["default_model_deployment"]).strip()

    if payload.get("model_candidates") is not None:
        config.model_candidates = _sanitize_candidates(payload["model_candidates"])

    if payload.get("model_settings") is not None and isinstance(payload["model_settings"], dict):
        current = config.model_settings if isinstance(config.model_settings, dict) else {}
        config.model_settings = {**current, **payload["model_settings"]}

    if payload.get("stage_prompts") is not None and isinstance(payload["stage_prompts"], dict):
        current_prompts = config.stage_prompts if isinstance(config.stage_prompts, dict) else {}
        merged: dict[str, Any] = {**current_prompts}
        for stage, stage_cfg in payload["stage_prompts"].items():
            stage_key = str(stage).strip()
            if not stage_key:
                continue
            previous = merged.get(stage_key, {})
            if not isinstance(previous, dict):
                previous = {}
            if isinstance(stage_cfg, dict):
                merged[stage_key] = {**previous, **stage_cfg}
        config.stage_prompts = merged

    await session.commit()
    await session.refresh(config)
    return await get_system_config_dict(session)
