"""WebSocket 进度广播管理。

按 ``job_id`` 维护订阅者；后台 worker 处理 slide 时把 ``ProgressMessage``
推送到所有订阅了该 job 的客户端。
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Dict, Set
from uuid import UUID

from fastapi import WebSocket
from loguru import logger


class ProgressBroker:
    """WebSocket 订阅 / 广播管理。"""

    def __init__(self) -> None:
        # job_id -> set of websockets
        self._subs: Dict[UUID, Set[WebSocket]] = defaultdict(set)
        # 全局监听者（订阅所有 job）
        self._all_subs: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self, ws: WebSocket, job_id: UUID | None = None) -> None:
        """订阅指定 job 的进度（job_id=None 表示订阅所有）。"""
        async with self._lock:
            if job_id is None:
                self._all_subs.add(ws)
            else:
                self._subs[job_id].add(ws)

    async def unsubscribe(self, ws: WebSocket) -> None:
        """取消该 ws 的所有订阅。"""
        async with self._lock:
            self._all_subs.discard(ws)
            for subs in self._subs.values():
                subs.discard(ws)

    async def publish(self, job_id: UUID, payload: dict) -> None:
        """向订阅了该 job_id 的客户端广播 payload。"""
        targets: list[WebSocket] = []
        async with self._lock:
            targets.extend(self._subs.get(job_id, set()))
            targets.extend(self._all_subs)

        if not targets:
            return

        text = _json_dumps(payload)
        # 并发发送，单个失败不影响其他
        results = await asyncio.gather(
            *(_safe_send(ws, text) for ws in targets), return_exceptions=True
        )
        for ws, result in zip(targets, results):
            if isinstance(result, Exception):
                logger.debug(f"WS 推送失败，移除订阅：{result}")
                await self.unsubscribe(ws)


async def _safe_send(ws: WebSocket, text: str) -> None:
    """带超时的安全发送。"""
    await asyncio.wait_for(ws.send_text(text), timeout=5)


def _json_dumps(payload: dict) -> str:
    """带 UUID/datetime 序列化的 json.dumps。"""
    import json
    from datetime import datetime
    from uuid import UUID as _UUID

    def default(obj):
        if isinstance(obj, _UUID):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"不可序列化对象：{type(obj)}")

    return json.dumps(payload, default=default, ensure_ascii=False)


# 全局单例
_broker: ProgressBroker | None = None


def get_progress_broker() -> ProgressBroker:
    global _broker
    if _broker is None:
        _broker = ProgressBroker()
    return _broker
