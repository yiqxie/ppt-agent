"""FastAPI 应用入口。"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from .api import jobs, slides, system_config, websocket
from .core.config import get_settings
from .core.logging import setup_logging
from .db.session import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动 / 关闭钩子。"""
    settings = get_settings()
    setup_logging(debug=settings.debug)
    logger.info(f"启动 {settings.app_name} ({settings.environment})")

    # 自动建表（生产建议改用 Alembic 迁移；MVP 阶段够用）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        yield
    finally:
        logger.info("关闭中…")
        await engine.dispose()


def create_app() -> FastAPI:
    """工厂函数。"""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        lifespan=lifespan,
        docs_url=f"{settings.api_prefix}/docs",
        openapi_url=f"{settings.api_prefix}/openapi.json",
    )

    # CORS（前端独立部署时需要）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 健康检查
    @app.get("/healthz", tags=["meta"], summary="健康检查")
    async def healthz():
        return {"status": "ok"}

    @app.get(f"{settings.api_prefix}/config", tags=["meta"], summary="返回前端可见的配置（非敏感）")
    async def public_config():
        return {
            "app_name": settings.app_name,
            "auth_enabled": settings.auth_enabled,
            "tenant_id": settings.aad_tenant_id if settings.auth_enabled else None,
            "api_audience": settings.aad_api_audience if settings.auth_enabled else None,
            "api_scope": settings.aad_required_scope if settings.auth_enabled else None,
        }

    # 业务路由
    app.include_router(jobs.router, prefix=settings.api_prefix)
    app.include_router(slides.router, prefix=settings.api_prefix)
    app.include_router(system_config.router, prefix=settings.api_prefix)
    app.include_router(websocket.router)  # ws 不带 /api 前缀

    # 可选：托管前端 dist（生产容器内）
    static_dir = os.environ.get("SERVE_STATIC_DIR")
    if static_dir and Path(static_dir).is_dir():
        index_file = Path(static_dir) / "index.html"
        # 静态资源：JS/CSS/图片
        app.mount("/assets", StaticFiles(directory=Path(static_dir) / "assets"), name="assets")

        @app.get("/", include_in_schema=False)
        async def _root():
            return FileResponse(index_file)

        # SPA fallback：未命中 API 的路径都返回 index.html，由前端路由处理
        @app.get("/{full_path:path}", include_in_schema=False)
        async def _spa_fallback(full_path: str):
            # 已经被业务路由处理的不会进到这里；为安全起见再判断一次
            if full_path.startswith("api/") or full_path.startswith("ws/"):
                from fastapi import HTTPException

                raise HTTPException(status_code=404)
            candidate = Path(static_dir) / full_path
            if candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(index_file)

    return app


app = create_app()
