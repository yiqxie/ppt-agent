"""Azure Blob Storage 服务封装。

支持两种鉴权：
1. ``connection_string``：本地开发更方便。
2. ``DefaultAzureCredential``：生产环境推荐，使用 Managed Identity。

封装了上传 bytes / 下载 / 生成带 SAS 的访问 URL / 删除等操作。
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob import (
    BlobSasPermissions,
    UserDelegationKey,
    generate_blob_sas,
)
from azure.storage.blob.aio import BlobServiceClient
from loguru import logger

from ..core.config import Settings, get_settings


class StorageService:
    """Azure Blob Storage 异步封装。"""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self._service_client: Optional[BlobServiceClient] = None
        self._credential: Optional[DefaultAzureCredential] = None
        # User Delegation Key 缓存，1 小时刷新
        self._udk: Optional[UserDelegationKey] = None
        self._udk_expiry: Optional[datetime] = None
        self._lock = asyncio.Lock()

    # ----------- 客户端构建 -----------
    async def _get_client(self) -> BlobServiceClient:
        """惰性创建并缓存 BlobServiceClient。"""
        if self._service_client is not None:
            return self._service_client

        async with self._lock:
            if self._service_client is not None:
                return self._service_client

            if self.settings.azure_storage_connection_string:
                # 本地：使用连接字符串
                self._service_client = BlobServiceClient.from_connection_string(
                    self.settings.azure_storage_connection_string
                )
                logger.info("Storage 客户端使用 connection string 初始化")
            else:
                # 生产：使用 Managed Identity
                self._credential = DefaultAzureCredential()
                account_url = (
                    f"https://{self.settings.azure_storage_account}.blob.core.windows.net"
                )
                self._service_client = BlobServiceClient(
                    account_url=account_url, credential=self._credential
                )
                logger.info("Storage 客户端使用 DefaultAzureCredential 初始化")

            # 确保容器存在
            for container_name in (
                self.settings.azure_container_screenshots,
                self.settings.azure_container_prompts,
                self.settings.azure_container_uploads,
            ):
                container_client = self._service_client.get_container_client(container_name)
                try:
                    await container_client.create_container()
                    logger.info(f"已创建容器 {container_name}")
                except Exception:  # 已存在则忽略
                    pass

        return self._service_client

    async def close(self) -> None:
        """关闭客户端连接。"""
        if self._service_client is not None:
            await self._service_client.close()
            self._service_client = None
        if self._credential is not None:
            await self._credential.close()
            self._credential = None

    # ----------- 上传 / 下载 / 删除 -----------
    async def upload_bytes(
        self,
        container: str,
        blob_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """上传 bytes，返回 blob 名称（不带 URL 前缀）。"""
        from azure.storage.blob import ContentSettings

        client = await self._get_client()
        blob_client = client.get_blob_client(container=container, blob=blob_name)
        await blob_client.upload_blob(
            data,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )
        return blob_name

    async def download_bytes(self, container: str, blob_name: str) -> bytes:
        """下载 blob 并返回 bytes。"""
        client = await self._get_client()
        blob_client = client.get_blob_client(container=container, blob=blob_name)
        stream = await blob_client.download_blob()
        return await stream.readall()

    async def delete_blob(self, container: str, blob_name: str) -> None:
        """删除单个 blob，忽略 404。"""
        client = await self._get_client()
        blob_client = client.get_blob_client(container=container, blob=blob_name)
        try:
            await blob_client.delete_blob()
        except Exception as exc:  # pragma: no cover
            logger.warning(f"删除 blob 失败 {container}/{blob_name}: {exc}")

    # ----------- SAS URL 生成 -----------
    async def _get_user_delegation_key(self) -> UserDelegationKey:
        """获取 / 复用 User Delegation Key（用于 MI 模式生成 SAS）。"""
        now = datetime.now(timezone.utc)
        if self._udk is not None and self._udk_expiry is not None and self._udk_expiry > now + timedelta(minutes=10):
            return self._udk

        client = await self._get_client()
        start = now - timedelta(minutes=5)
        expiry = now + timedelta(hours=1)
        self._udk = await client.get_user_delegation_key(key_start_time=start, key_expiry_time=expiry)
        self._udk_expiry = expiry
        return self._udk

    async def generate_read_sas_url(self, container: str, blob_name: str, ttl_minutes: int = 60) -> str:
        """为 blob 生成只读 SAS URL（前端临时访问用）。"""
        client = await self._get_client()
        expiry = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)

        if self.settings.azure_storage_connection_string:
            # 解析 account name & key
            parts = dict(
                kv.split("=", 1)
                for kv in self.settings.azure_storage_connection_string.split(";")
                if "=" in kv
            )
            account_name = parts.get("AccountName", self.settings.azure_storage_account)
            account_key = parts.get("AccountKey")
            sas = generate_blob_sas(
                account_name=account_name,
                container_name=container,
                blob_name=blob_name,
                account_key=account_key,
                permission=BlobSasPermissions(read=True),
                expiry=expiry,
            )
        else:
            udk = await self._get_user_delegation_key()
            sas = generate_blob_sas(
                account_name=self.settings.azure_storage_account,
                container_name=container,
                blob_name=blob_name,
                user_delegation_key=udk,
                permission=BlobSasPermissions(read=True),
                expiry=expiry,
            )

        base_url = client.url.rstrip("/")
        return f"{base_url}/{container}/{blob_name}?{sas}"


# 全局单例
_storage_service: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    """返回全局 StorageService 实例。"""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
