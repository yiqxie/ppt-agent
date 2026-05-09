"""上传与 Job 相关的 REST API。"""

from __future__ import annotations

import asyncio
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.security import get_current_user
from ..db.session import AsyncSessionLocal, get_db
from ..models.models import (
    JOB_STATUS_PENDING,
    UploadJob,
)
from ..schemas.schemas import UploadJobListOut, UploadJobOut, UploadResponse
from ..services.orchestrator import delete_job_with_blobs, process_upload_job
from ..services.storage import get_storage_service
from ..core.config import get_settings


router = APIRouter(prefix="/jobs", tags=["jobs"])


# 控制同时进行的 PPT 任务数，避免 LibreOffice 过度并发
_concurrency_sem: Optional[asyncio.Semaphore] = None


def _get_concurrency_sem() -> asyncio.Semaphore:
    """惰性创建全局并发信号量（在事件循环内创建）。"""
    global _concurrency_sem
    if _concurrency_sem is None:
        _concurrency_sem = asyncio.Semaphore(get_settings().max_concurrent_slide_jobs)
    return _concurrency_sem


@router.post("/upload", response_model=UploadResponse, summary="上传一个或多个 PPT 文件")
async def upload_ppt_files(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(..., description="一个或多个 .ppt/.pptx 文件"),
    auto_start: bool = Query(default=True, description="是否上传完立即开始处理"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """接收上传的 PPT 文件，写 Job 记录，并可选地立即排队处理。"""
    if not files:
        raise HTTPException(status_code=400, detail="未提供任何文件")

    settings = get_settings()
    storage = get_storage_service()
    created: List[UploadJob] = []

    user_id = user.get("oid") or user.get("sub")

    for upload in files:
        suffix = (upload.filename or "").lower()
        if not (suffix.endswith(".ppt") or suffix.endswith(".pptx")):
            raise HTTPException(
                status_code=400, detail=f"不支持的文件类型：{upload.filename}"
            )
        data = await upload.read()
        if not data:
            raise HTTPException(status_code=400, detail=f"文件为空：{upload.filename}")

        job_id = uuid4()
        blob_name = f"{job_id}/{upload.filename}"
        # 1) 上传原 PPT 到 Storage
        await storage.upload_bytes(
            settings.azure_container_uploads,
            blob_name,
            data,
            content_type=(
                "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                if suffix.endswith(".pptx")
                else "application/vnd.ms-powerpoint"
            ),
        )

        # 2) 创建 Job 记录
        job = UploadJob(
            id=job_id,
            original_filename=upload.filename or "untitled.pptx",
            file_size=len(data),
            blob_path=blob_name,
            status=JOB_STATUS_PENDING,
            created_by=user_id,
        )
        db.add(job)
        created.append(job)

        # 3) 安排后台处理
        if auto_start:
            ppt_bytes = data  # 在闭包中固定引用

            async def _runner(jid: UUID = job_id, content: bytes = ppt_bytes, name: str = upload.filename or ""):
                sem = _get_concurrency_sem()
                async with sem:
                    await process_upload_job(jid, content, name, AsyncSessionLocal)

            background_tasks.add_task(_runner)

    await db.commit()
    for j in created:
        await db.refresh(j)

    return UploadResponse(jobs=[UploadJobOut.model_validate(j) for j in created])


@router.post("/{job_id}/start", response_model=UploadJobOut, summary="手动触发处理")
async def start_job(
    job_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """重新触发一个 pending/failed 的 job。"""
    settings = get_settings()
    storage = get_storage_service()
    job = await db.get(UploadJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job 不存在")
    if job.status == "running":
        return UploadJobOut.model_validate(job)

    # 重新拉原始 PPT
    data = await storage.download_bytes(settings.azure_container_uploads, job.blob_path)

    job.status = JOB_STATUS_PENDING
    job.processed_slides = 0
    job.error_message = None
    await db.commit()
    await db.refresh(job)

    async def _runner():
        sem = _get_concurrency_sem()
        async with sem:
            await process_upload_job(job_id, data, job.original_filename, AsyncSessionLocal)

    background_tasks.add_task(_runner)
    return UploadJobOut.model_validate(job)


@router.get("", response_model=UploadJobListOut, summary="查询 Job 列表")
async def list_jobs(
    status: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    stmt = select(UploadJob).order_by(UploadJob.created_at.desc())
    count_stmt = select(func.count(UploadJob.id))
    if status:
        stmt = stmt.where(UploadJob.status == status)
        count_stmt = count_stmt.where(UploadJob.status == status)
    total = (await db.execute(count_stmt)).scalar_one()
    rows = (await db.execute(stmt.offset(skip).limit(limit))).scalars().all()
    return UploadJobListOut(
        items=[UploadJobOut.model_validate(r) for r in rows], total=total
    )


@router.get("/{job_id}", response_model=UploadJobOut, summary="查询 Job 详情")
async def get_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    job = await db.get(UploadJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job 不存在")
    return UploadJobOut.model_validate(job)


@router.delete("/{job_id}", summary="删除 Job 及其所有 slide 与 blob")
async def delete_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ok = await delete_job_with_blobs(db, job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="job 不存在")
    return {"deleted": True, "job_id": str(job_id)}
