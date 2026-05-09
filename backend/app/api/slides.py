"""Slide 检索 / 编辑 / 批量删除 API。"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..core.security import get_current_user
from ..db.session import get_db
from ..models.models import Slide
from ..schemas.schemas import (
    SlideBatchDeleteIn,
    SlideListOut,
    SlideOut,
    SlideUpdateIn,
)
from ..services.orchestrator import delete_slides_with_blobs
from ..services.storage import get_storage_service


router = APIRouter(prefix="/slides", tags=["slides"])


async def _to_slide_out(slide: Slide) -> SlideOut:
    """把 ORM Slide 组装成包含 SAS URL 的响应模型。"""
    settings = get_settings()
    storage = get_storage_service()
    screenshot_url = await storage.generate_read_sas_url(
        settings.azure_container_screenshots, slide.screenshot_blob
    )
    prompt_url = await storage.generate_read_sas_url(
        settings.azure_container_prompts, slide.prompt_blob
    )
    return SlideOut(
        id=slide.id,
        job_id=slide.job_id,
        slide_index=slide.slide_index,
        screenshot_url=screenshot_url,
        prompt_url=prompt_url,
        prompt_text=slide.prompt_text,
        title=slide.title,
        summary=slide.summary,
        tags=list(slide.tags or []),
        style_meta=dict(slide.style_meta or {}),
        created_at=slide.created_at,
        updated_at=slide.updated_at,
    )


@router.get("", response_model=SlideListOut, summary="查询 slide（支持关键字、tag、job 过滤）")
async def list_slides(
    job_id: Optional[UUID] = Query(default=None),
    keyword: Optional[str] = Query(default=None, description="标题/摘要/prompt 模糊匹配"),
    tag: Optional[str] = Query(default=None, description="按 tag 精确过滤"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=24, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    stmt = select(Slide).order_by(Slide.created_at.desc())
    count_stmt = select(func.count(Slide.id))

    if job_id:
        stmt = stmt.where(Slide.job_id == job_id)
        count_stmt = count_stmt.where(Slide.job_id == job_id)

    if keyword:
        like = f"%{keyword}%"
        cond = or_(
            Slide.title.ilike(like),
            Slide.summary.ilike(like),
            Slide.prompt_text.ilike(like),
        )
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    if tag:
        # JSON 数组包含元素 —— 用 PostgreSQL JSONB ? 操作符
        # SQLAlchemy 通过 cast 实现
        cond = Slide.tags.cast(JSONB).contains([tag])
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    total = (await db.execute(count_stmt)).scalar_one()
    rows = (await db.execute(stmt.offset(skip).limit(limit))).scalars().all()
    items = [await _to_slide_out(r) for r in rows]
    return SlideListOut(items=items, total=total)


@router.get("/{slide_id}", response_model=SlideOut, summary="查询单个 slide 详情")
async def get_slide(
    slide_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    slide = await db.get(Slide, slide_id)
    if slide is None:
        raise HTTPException(status_code=404, detail="slide 不存在")
    return await _to_slide_out(slide)


@router.put("/{slide_id}", response_model=SlideOut, summary="更新 slide 的 prompt / tag / 标题等")
async def update_slide(
    slide_id: UUID,
    payload: SlideUpdateIn,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    slide = await db.get(Slide, slide_id)
    if slide is None:
        raise HTTPException(status_code=404, detail="slide 不存在")

    if payload.prompt_text is not None:
        slide.prompt_text = payload.prompt_text
    if payload.title is not None:
        slide.title = payload.title
    if payload.summary is not None:
        slide.summary = payload.summary
    if payload.tags is not None:
        slide.tags = payload.tags

    await db.commit()
    await db.refresh(slide)
    return await _to_slide_out(slide)


@router.post("/batch-delete", summary="批量删除 slide（含 blob 与 DB 记录）")
async def batch_delete(
    payload: SlideBatchDeleteIn,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    deleted = await delete_slides_with_blobs(db, payload.slide_ids)
    return {"deleted": deleted}


@router.get("/tags/all", summary="返回所有出现过的 tag（供前端过滤下拉）")
async def list_all_tags(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """聚合所有 slide.tags 出现的标签。

    使用 PostgreSQL 的 jsonb_array_elements_text 展开，再 distinct 去重。
    """
    from sqlalchemy import text

    sql = text(
        """
        SELECT DISTINCT jsonb_array_elements_text(tags::jsonb) AS tag
        FROM slides
        WHERE jsonb_typeof(tags::jsonb) = 'array'
        ORDER BY tag
        """
    )
    rows = (await db.execute(sql)).all()
    return {"tags": [r[0] for r in rows]}
