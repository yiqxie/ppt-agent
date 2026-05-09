"""Pydantic Schemas：API 输入输出模型。"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# Job
# ============================================================


class UploadJobOut(BaseModel):
    """返回给前端的 Job 信息。"""

    id: UUID
    original_filename: str
    file_size: int
    status: str
    total_slides: int
    processed_slides: int
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UploadJobListOut(BaseModel):
    """Job 分页列表。"""

    items: List[UploadJobOut]
    total: int


# ============================================================
# Slide
# ============================================================


class SlideOut(BaseModel):
    """返回给前端的 slide 信息（不含图片二进制）。"""

    id: UUID
    job_id: UUID
    slide_index: int
    screenshot_url: str = Field(description="带 SAS 的截图访问 URL")
    prompt_url: str = Field(description="带 SAS 的 prompt 文件访问 URL")
    prompt_text: str
    title: Optional[str] = None
    summary: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    style_meta: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class SlideListOut(BaseModel):
    """Slide 分页列表。"""

    items: List[SlideOut]
    total: int


class SlideUpdateIn(BaseModel):
    """前端编辑 slide 时的入参。"""

    prompt_text: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    tags: Optional[List[str]] = None


class SlideBatchDeleteIn(BaseModel):
    """批量删除入参。"""

    slide_ids: List[UUID] = Field(min_length=1, description="要删除的 slide ID 列表")


# ============================================================
# 上传响应
# ============================================================


class UploadResponse(BaseModel):
    """上传接口响应。"""

    jobs: List[UploadJobOut]


# ============================================================
# WebSocket 进度消息
# ============================================================


class ProgressMessage(BaseModel):
    """通过 WebSocket 推送给前端的进度消息。"""

    type: str = Field(description="job_update | slide_completed | error | done")
    job_id: UUID
    status: Optional[str] = None
    total_slides: Optional[int] = None
    processed_slides: Optional[int] = None
    slide: Optional[SlideOut] = None
    error_message: Optional[str] = None


# ============================================================
# 系统配置
# ============================================================


class StagePromptConfig(BaseModel):
    """单个阶段的提示词配置。"""

    system_prompt: str = Field(default="")
    user_prompt: str = Field(default="")


class SystemConfigOut(BaseModel):
    """系统配置出参。"""

    azure_foundry_url: str
    default_model_deployment: str
    model_candidates: List[str] = Field(default_factory=list)
    model_settings: Dict[str, Any] = Field(default_factory=dict)
    stage_prompts: Dict[str, StagePromptConfig] = Field(default_factory=dict)
    updated_at: datetime


class SystemConfigUpdateIn(BaseModel):
    """系统配置更新入参（均为可选，按字段增量更新）。"""

    azure_foundry_url: Optional[str] = None
    default_model_deployment: Optional[str] = None
    model_candidates: Optional[List[str]] = None
    model_settings: Optional[Dict[str, Any]] = None
    stage_prompts: Optional[Dict[str, StagePromptConfig]] = None
