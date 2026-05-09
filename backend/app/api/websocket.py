"""WebSocket 进度推送端点。

路径：``/ws/progress``
查询参数：``job_id``（可选；不带则订阅所有 job）

客户端可发送 ``{"type": "ping"}`` 心跳，服务器回 ``pong``。
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from loguru import logger

from ..services.progress import get_progress_broker


router = APIRouter(tags=["websocket"])


@router.websocket("/ws/progress")
async def websocket_progress(websocket: WebSocket, job_id: str | None = Query(default=None)):
    """订阅 job 进度。"""
    broker = get_progress_broker()
    await websocket.accept()

    parsed_id: UUID | None = None
    if job_id:
        try:
            parsed_id = UUID(job_id)
        except ValueError:
            await websocket.close(code=1003, reason="invalid job_id")
            return

    await broker.subscribe(websocket, parsed_id)
    logger.info(f"WS 已订阅 job_id={parsed_id}")

    try:
        while True:
            msg = await websocket.receive_text()
            if msg == "ping" or '"ping"' in msg:
                await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        logger.info(f"WS 断开 job_id={parsed_id}")
    except Exception as exc:
        logger.warning(f"WS 异常断开：{exc}")
    finally:
        await broker.unsubscribe(websocket)
