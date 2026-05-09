"""SQLAlchemy 异步引擎与会话工厂。

提供：
- ``engine``: 全局异步引擎
- ``AsyncSessionLocal``: 会话工厂
- ``Base``: ORM 基类
- ``get_db``: FastAPI 依赖注入函数
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from ..core.config import get_settings


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


_settings = get_settings()

# echo=False 以避免日志噪音；pool_pre_ping 处理空闲连接
engine = create_async_engine(
    _settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：获取一个异步数据库会话。"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
