"""数据库 ORM 模型定义。

数据模型说明：
- ``UploadJob``：用户上传的一个 PPT 文件对应一条 Job 记录，跟踪整体处理进度。
- ``Slide``：PPT 中的每一页 slide，保存截图路径、prompt 路径、tag、自动生成的描述等。

所有路径都是 Azure Storage 中的 blob 名（容器+路径），不存放完整 URL。
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.session import Base


# 任务状态枚举（使用字符串便于扩展）
JOB_STATUS_PENDING = "pending"
JOB_STATUS_RUNNING = "running"
JOB_STATUS_COMPLETED = "completed"
JOB_STATUS_FAILED = "failed"


class UploadJob(Base):
    """一次 PPT 上传与处理任务。"""

    __tablename__ = "upload_jobs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # 原始文件信息
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    blob_path: Mapped[str] = mapped_column(String(1024), nullable=False, comment="原始 PPT 在 Storage 中的路径")

    # 处理进度
    status: Mapped[str] = mapped_column(String(32), default=JOB_STATUS_PENDING, index=True)
    total_slides: Mapped[int] = mapped_column(Integer, default=0)
    processed_slides: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 创建者（来自 Entra ID 的 oid 或 sub）
    created_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # 关联的 slide 列表
    slides: Mapped[List["Slide"]] = relationship(
        "Slide", back_populates="job", cascade="all, delete-orphan"
    )


class Slide(Base):
    """PPT 中的单个 slide。"""

    __tablename__ = "slides"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    job_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("upload_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # slide 在 PPT 中的索引（从 1 开始）
    slide_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # Storage Blob 路径
    screenshot_blob: Mapped[str] = mapped_column(String(1024), nullable=False)
    prompt_blob: Mapped[str] = mapped_column(String(1024), nullable=False)

    # AI 提取出的 prompt 模板（同时存数据库与 blob 文件，方便检索）
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # AI 总结的简要描述与标题（用于卡片展示）
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 标签数组（PostgreSQL JSONB 存储 List[str]）
    tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    # 配色、字体等结构化样式信息（dict）
    style_meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    job: Mapped[UploadJob] = relationship("UploadJob", back_populates="slides")
