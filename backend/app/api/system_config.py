"""系统配置 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.security import get_current_user
from ..db.session import get_db
from ..schemas.schemas import SystemConfigOut, SystemConfigUpdateIn
from ..services.system_config import get_system_config_dict, update_system_config


router = APIRouter(prefix="/system-config", tags=["system-config"])


@router.get("", response_model=SystemConfigOut, summary="读取系统配置")
async def get_system_config(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """返回系统配置（用于系统配置页面）。"""
    data = await get_system_config_dict(db)
    return SystemConfigOut(**data)


@router.put("", response_model=SystemConfigOut, summary="更新系统配置")
async def put_system_config(
    body: SystemConfigUpdateIn,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """按字段增量更新系统配置。"""
    payload = body.model_dump(exclude_none=True)
    data = await update_system_config(db, payload)
    return SystemConfigOut(**data)
