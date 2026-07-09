"""Redis 缓存封装 — 优雅降级到内存。"""
from __future__ import annotations

import json
import time
from collections import OrderedDict
from typing import Any, Optional

from ..config import settings
from ..logging_config import get_logger

logger = get_logger("data.redis")

try:  # pragma: no cover - 可选依赖
    import redis.asyncio as aioredis

    _REDIS_OK = True
except Exception:  # pragma: no cover
    _REDIS_OK = False


class InMemoryCache:
    """LRU + TTL 内存缓存（Redis 不可用时回退）。"""

    def __init__(self, capacity: int = 1024) -> None:
        self._data: "OrderedDict[str, tuple[float, str]]" = OrderedDict()
        self._capacity = capacity

    def set(self, key: str, value: Any, ttl: int = 60) -> None:
        self._data[key] = (time.time() + ttl, json.dumps(value, default=str))
        self._data.move_to_end(key)
        while len(self._data) > self._capacity:
            self._data.popitem(last=False)

    def get(self, key: str) -> Optional[Any]:
        item = self._data.get(key)
        if not item:
            return None
        exp, raw = item
        if exp < time.time():
            self._data.pop(key, None)
            return None
        self._data.move_to_end(key)
        try:
            return json.loads(raw)
        except Exception:
            return None

    def delete(self, key: str) -> None:
        self._data.pop(key, None)

    def clear(self) -> None:
        self._data.clear()


class RedisCache:
    """Redis 包装。失败时自动回退到内存。"""

    def __init__(self) -> None:
        self._mem = InMemoryCache()
        self._client: Any = None
        self._connect()

    def _connect(self) -> None:
        if not (settings.redis_enabled and _REDIS_OK):
            logger.info("Redis 不可用，使用内存缓存")
            return
        try:  # pragma: no cover
            self._client = aioredis.from_url(settings.redis_url, decode_responses=True)
            logger.info("Redis 已连接: %s", settings.redis_url)
        except Exception as exc:  # pragma: no cover
            logger.warning("Redis 连接失败，使用内存缓存: %s", exc)
            self._client = None

    async def set(self, key: str, value: Any, ttl: int = 60) -> None:
        if self._client is not None:  # pragma: no cover
            try:
                await self._client.set(key, json.dumps(value, default=str), ex=ttl)
                return
            except Exception as exc:
                logger.warning("Redis set 失败，回退内存: %s", exc)
        self._mem.set(key, value, ttl)

    async def get(self, key: str) -> Optional[Any]:
        if self._client is not None:  # pragma: no cover
            try:
                raw = await self._client.get(key)
                if raw is None:
                    return None
                return json.loads(raw)
            except Exception as exc:
                logger.warning("Redis get 失败，回退内存: %s", exc)
        return self._mem.get(key)

    async def delete(self, key: str) -> None:
        if self._client is not None:  # pragma: no cover
            try:
                await self._client.delete(key)
                return
            except Exception:
                pass
        self._mem.delete(key)

    async def clear(self) -> None:
        if self._client is not None:  # pragma: no cover
            try:
                await self._client.flushdb()
                return
            except Exception:
                pass
        self._mem.clear()


_cache: Optional[RedisCache] = None


def get_cache() -> RedisCache:
    global _cache
    if _cache is None:
        _cache = RedisCache()
    return _cache
