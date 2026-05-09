"""核心业务编排：处理一个上传的 PPT 文件。

流程：
1. 把原始 PPT 上传到 Storage（uploads 容器）
2. 把 PPT 渲染为每页 PNG
3. 对每页：上传截图 -> 调用 AI 分析 -> 上传 prompt JSON -> 写数据库
4. 期间通过 ProgressBroker 广播进度
"""

from __future__ import annotations

import asyncio
import json
import uuid
from io import BytesIO
from typing import Optional
from uuid import UUID

from loguru import logger
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..core.config import get_settings
from ..models.models import (
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    JOB_STATUS_RUNNING,
    Slide,
    UploadJob,
)
from .ai import get_ai_service
from .ppt_renderer import convert_ppt_to_images
from .progress import get_progress_broker
from .storage import get_storage_service


def _slide_dir(job_id: UUID) -> str:
    """约定：同一个 job 下的所有 slide 都放在同一目录下。"""
    return f"job_{job_id}"


def _compress_screenshot(image_bytes: bytes) -> tuple[bytes, str, str]:
    """截图压缩：优先转为 JPEG 并限制最大边长，失败时回退原 PNG。"""
    try:
        with Image.open(BytesIO(image_bytes)) as img:
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            elif img.mode == "L":
                img = img.convert("RGB")

            resampling = getattr(Image, "Resampling", Image)
            img.thumbnail((1600, 1600), resampling.LANCZOS)

            out = BytesIO()
            img.save(out, format="JPEG", quality=82, optimize=True, progressive=True)
            return out.getvalue(), "jpg", "image/jpeg"
    except Exception as exc:  # pragma: no cover
        logger.warning(f"截图压缩失败，回退原图：{exc}")
        return image_bytes, "png", "image/png"


async def process_upload_job(
    job_id: UUID,
    ppt_bytes: bytes,
    original_filename: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """后台任务：处理一个 PPT 上传。

    任何异常都会被捕获并写入 job.error_message，且通过 WebSocket 推送 error 消息。
    """
    settings = get_settings()
    storage = get_storage_service()
    ai = get_ai_service()
    broker = get_progress_broker()

    try:
        # === 1) 标记 running 并广播 ===
        async with session_factory() as session:
            job = await session.get(UploadJob, job_id)
            if job is None:
                logger.error(f"Job {job_id} 不存在，跳过处理")
                return
            job.status = JOB_STATUS_RUNNING
            await session.commit()
            await broker.publish(
                job_id,
                {"type": "job_update", "job_id": str(job_id), "status": JOB_STATUS_RUNNING},
            )

        # === 2) 渲染图片 ===
        logger.info(f"[{job_id}] 开始渲染 PPT -> 图片")
        slide_images = await convert_ppt_to_images(ppt_bytes, original_filename)
        total = len(slide_images)
        logger.info(f"[{job_id}] 渲染完成，共 {total} 页")

        async with session_factory() as session:
            job = await session.get(UploadJob, job_id)
            if job is not None:
                job.total_slides = total
                await session.commit()
                await broker.publish(
                    job_id,
                    {
                        "type": "job_update",
                        "job_id": str(job_id),
                        "status": JOB_STATUS_RUNNING,
                        "total_slides": total,
                        "processed_slides": 0,
                    },
                )

        if total == 0:
            raise RuntimeError("PPT 解析后没有任何 slide")

        # === 3) 并发处理每一页（限制并发） ===
        sem = asyncio.Semaphore(settings.max_concurrent_slide_pages)
        processed_counter = {"value": 0}
        counter_lock = asyncio.Lock()

        async def _process_one(idx: int, image_bytes: bytes) -> None:
            async with sem:
                slide_index = idx + 1
                slug = f"{_slide_dir(job_id)}/slide_{slide_index:03d}"
                compressed_bytes, screenshot_ext, screenshot_mime = await asyncio.to_thread(
                    _compress_screenshot, image_bytes
                )
                screenshot_blob = f"{slug}.{screenshot_ext}"
                prompt_blob = f"{slug}.json"

                # 3.1) 上传截图
                await storage.upload_bytes(
                    settings.azure_container_screenshots,
                    screenshot_blob,
                    compressed_bytes,
                    content_type=screenshot_mime,
                )

                # 3.2) 调用 AI 分析
                analysis = await ai.analyze_slide(compressed_bytes, image_mime=screenshot_mime)

                # 3.3) 上传 prompt JSON
                prompt_payload = {
                    "title": analysis["title"],
                    "summary": analysis["summary"],
                    "prompt": analysis["prompt"],
                    "tags": analysis["tags"],
                    "style": analysis["style"],
                    "slide_index": slide_index,
                    "screenshot_blob": screenshot_blob,
                }
                await storage.upload_bytes(
                    settings.azure_container_prompts,
                    prompt_blob,
                    json.dumps(prompt_payload, ensure_ascii=False, indent=2).encode("utf-8"),
                    content_type="application/json",
                )

                # 3.4) 写数据库（每页独立 session，避免长事务）
                async with session_factory() as session:
                    slide = Slide(
                        id=uuid.uuid4(),
                        job_id=job_id,
                        slide_index=slide_index,
                        screenshot_blob=screenshot_blob,
                        prompt_blob=prompt_blob,
                        prompt_text=analysis["prompt"],
                        title=analysis["title"],
                        summary=analysis["summary"],
                        tags=analysis["tags"],
                        style_meta=analysis["style"],
                    )
                    session.add(slide)
                    # 同步更新 job.processed_slides
                    job = await session.get(UploadJob, job_id)
                    if job is not None:
                        async with counter_lock:
                            processed_counter["value"] += 1
                            job.processed_slides = processed_counter["value"]
                    await session.commit()
                    if job is not None:
                        await session.refresh(slide)

                # 3.5) 广播进度
                screenshot_url = await storage.generate_read_sas_url(
                    settings.azure_container_screenshots, screenshot_blob
                )
                prompt_url = await storage.generate_read_sas_url(
                    settings.azure_container_prompts, prompt_blob
                )
                await broker.publish(
                    job_id,
                    {
                        "type": "slide_completed",
                        "job_id": str(job_id),
                        "processed_slides": processed_counter["value"],
                        "total_slides": total,
                        "slide": {
                            "id": str(slide.id),
                            "job_id": str(job_id),
                            "slide_index": slide_index,
                            "screenshot_url": screenshot_url,
                            "prompt_url": prompt_url,
                            "prompt_text": analysis["prompt"],
                            "title": analysis["title"],
                            "summary": analysis["summary"],
                            "tags": analysis["tags"],
                            "style_meta": analysis["style"],
                            "created_at": slide.created_at.isoformat(),
                            "updated_at": slide.updated_at.isoformat(),
                        },
                    },
                )

        await asyncio.gather(*[_process_one(i, img) for i, img in enumerate(slide_images)])

        # === 4) 完成 ===
        async with session_factory() as session:
            job = await session.get(UploadJob, job_id)
            if job is not None:
                job.status = JOB_STATUS_COMPLETED
                await session.commit()
        await broker.publish(
            job_id,
            {
                "type": "done",
                "job_id": str(job_id),
                "status": JOB_STATUS_COMPLETED,
                "total_slides": total,
                "processed_slides": total,
            },
        )
        logger.success(f"[{job_id}] 处理完成")

    except Exception as exc:
        logger.exception(f"[{job_id}] 处理失败")
        try:
            async with session_factory() as session:
                job = await session.get(UploadJob, job_id)
                if job is not None:
                    job.status = JOB_STATUS_FAILED
                    job.error_message = str(exc)[:2000]
                    await session.commit()
        except Exception:  # pragma: no cover
            logger.exception("更新 job 失败状态时再次出错")
        await broker.publish(
            job_id,
            {
                "type": "error",
                "job_id": str(job_id),
                "status": JOB_STATUS_FAILED,
                "error_message": str(exc)[:2000],
            },
        )


async def delete_slides_with_blobs(
    session: AsyncSession, slide_ids: list[UUID]
) -> int:
    """批量删除 slide：先删除 blob，再删数据库记录。

    返回实际删除的条数。
    """
    settings = get_settings()
    storage = get_storage_service()

    result = await session.execute(select(Slide).where(Slide.id.in_(slide_ids)))
    slides = result.scalars().all()
    if not slides:
        return 0

    # 并发删除 blob
    tasks = []
    for s in slides:
        tasks.append(storage.delete_blob(settings.azure_container_screenshots, s.screenshot_blob))
        tasks.append(storage.delete_blob(settings.azure_container_prompts, s.prompt_blob))
    await asyncio.gather(*tasks, return_exceptions=True)

    for s in slides:
        await session.delete(s)
    await session.commit()
    return len(slides)


async def delete_job_with_blobs(session: AsyncSession, job_id: UUID) -> bool:
    """删除整个 job：包含其所有 slide 的 blob 与数据库记录、原始 ppt 文件。"""
    settings = get_settings()
    storage = get_storage_service()

    job = await session.get(UploadJob, job_id)
    if job is None:
        return False

    # 加载 slides 关系
    result = await session.execute(select(Slide).where(Slide.job_id == job_id))
    slides = result.scalars().all()

    tasks = []
    for s in slides:
        tasks.append(storage.delete_blob(settings.azure_container_screenshots, s.screenshot_blob))
        tasks.append(storage.delete_blob(settings.azure_container_prompts, s.prompt_blob))
    if job.blob_path:
        tasks.append(storage.delete_blob(settings.azure_container_uploads, job.blob_path))
    await asyncio.gather(*tasks, return_exceptions=True)

    await session.delete(job)
    await session.commit()
    return True
