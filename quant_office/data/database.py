"""SQLAlchemy 数据库连接（异步，SQLite 默认）。"""
from __future__ import annotations

import os
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..config import settings
from ..logging_config import get_logger

logger = get_logger("data.database")

_engine = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def _resolve_url() -> str:
    url = settings.database_url
    if url.startswith("sqlite+aiosqlite:///"):
        path = url.replace("sqlite+aiosqlite:///", "")
        if not os.path.isabs(path):
            path = os.path.join(str(settings.resolved_data_dir), os.path.basename(path))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        url = f"sqlite+aiosqlite:///{path}"
    return url


def init_database() -> None:
    global _engine, _session_factory
    if _engine is not None:
        return
    url = _resolve_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    _engine = create_async_engine(url, echo=False, future=True, connect_args=connect_args)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)

    # 导入并建表（延迟避免循环依赖）
    try:
        from . import models  # noqa: F401

        async def _create() -> None:
            from .models import Base

            async with _engine.begin() as conn:  # type: ignore[union-attr]
                await conn.run_sync(Base.metadata.create_all)

        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        if loop.is_running():
            loop.create_task(_create())
        else:
            loop.run_until_complete(_create())
        logger.info("数据库已初始化: %s", url)
    except Exception as exc:  # pragma: no cover
        logger.exception("数据库表创建失败（功能仍将运行）: %s", exc)


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        init_database()
    assert _session_factory is not None
    return _session_factory


async def get_session() -> AsyncSession:
    factory = get_session_factory()
    async with factory() as session:
        yield session
