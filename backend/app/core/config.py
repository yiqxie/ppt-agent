"""应用全局配置模块。

通过 pydantic-settings 从环境变量与 .env 文件读取配置；
所有需要在多处共享的常量都集中在这里，便于本地开发与云端部署一致管理。
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置对象。

    字段名称遵循"环境变量大写下划线"约定，例如 ``app_name`` 对应 ``APP_NAME``。
    """

    # -------- 基础应用信息 --------
    app_name: str = Field(default="PPT Slide Agent", description="应用名称")
    environment: str = Field(default="development", description="运行环境标识")
    api_prefix: str = Field(default="/api", description="API 统一前缀")
    debug: bool = Field(default=False, description="是否开启调试模式")

    # -------- CORS 允许的前端来源 --------
    cors_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:3000"],
        description="允许跨域的前端地址列表",
    )

    # -------- PostgreSQL 连接 --------
    # 形如：postgresql+asyncpg://user:password@host:5432/dbname
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/ppt_agent",
        description="异步 SQLAlchemy 连接字符串",
    )

    # -------- Azure Storage Blob --------
    azure_storage_account: str = Field(default="", description="Storage 账户名称")
    # 容器名约定：screenshots 存截图，prompts 存 prompt JSON，uploads 存原始 PPT
    azure_container_screenshots: str = Field(default="screenshots", description="截图容器名")
    azure_container_prompts: str = Field(default="prompts", description="Prompt 容器名")
    azure_container_uploads: str = Field(default="uploads", description="原始 PPT 容器名")
    # 可选：使用 connection string 本地开发；生产环境建议使用 Managed Identity
    azure_storage_connection_string: Optional[str] = Field(
        default=None, description="Storage 连接字符串（仅本地）"
    )

    # -------- Azure OpenAI --------
    azure_openai_endpoint: str = Field(default="", description="Azure OpenAI Endpoint")
    azure_openai_api_key: Optional[str] = Field(default=None, description="API Key（本地用）")
    azure_openai_api_version: str = Field(default="2024-10-21", description="API 版本")
    # 视觉模型部署名（默认用 gpt-4o；如已部署 gpt-4.5-preview 可在环境覆盖）
    azure_openai_vision_deployment: str = Field(
        default="gpt-4o", description="视觉/对话模型部署名称"
    )

    # -------- Microsoft Entra ID（Azure AD）认证 --------
    aad_tenant_id: str = Field(default="", description="租户 ID")
    aad_api_audience: str = Field(default="", description="后端 API Application ID URI 或 client_id")
    aad_required_scope: str = Field(default="access_as_user", description="必备权限 scope")
    # 是否启用认证；本地调试可关闭
    auth_enabled: bool = Field(default=False, description="是否启用 JWT 认证")

    # -------- 任务并发控制 --------
    max_concurrent_slide_jobs: int = Field(
        default=2, description="同一时刻并发处理的 PPT 文件数量"
    )
    max_concurrent_slide_pages: int = Field(
        default=4, description="同一 PPT 内并发分析的 slide 页数量"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """返回全局唯一的配置实例（带缓存）。"""
    return Settings()
