"""SQLAlchemy 数据库连接（异步，SQLite 默认）。"""
from __future__ import annotations

import asyncio
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


async def _create_all_tables_async() -> None:
    """异步建表（由 lifespan 显式 await 调用）。"""
    from .models import Base

    if _engine is None:
        return
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def init_database() -> None:
    """同步初始化：建 engine + factory，并建表（兼容无 running loop 的情况）。

    - 若在 FastAPI lifespan 中调用：先 setup 同步部分，再在 lifespan 里 await ``create_all_tables_async()``
    - 若在测试/脚本中调用：直接同步 run_until_complete 建表
    """
    global _engine, _session_factory
    if _engine is not None:
        return
    url = _resolve_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    _engine = create_async_engine(url, echo=False, future=True, connect_args=connect_args)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)

    # 触发模型注册（延迟避免循环依赖）
    try:
        from . import models  # noqa: F401

        # 若当前无运行中的 event loop，同步建表（脚本/测试场景）
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 已有 loop 在跑，交给 lifespan / 调用方显式 await
                logger.info("数据库已 setup: %s（建表交给 await 上下文）", url)
                return
            loop.run_until_complete(_create_all_tables_async())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_create_all_tables_async())
        logger.info("数据库已初始化: %s", url)
    except Exception as exc:  # pragma: no cover
        logger.exception("数据库表创建失败（功能仍将运行）: %s", exc)


async def create_all_tables() -> None:
    """由 lifespan / 测试 fixture 显式 await，确保表存在。"""
    await _create_all_tables_async()


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        init_database()
    assert _session_factory is not None
    return _session_factory


async def get_session() -> AsyncSession:
    factory = get_session_factory()
    async with factory() as session:
        yield session
