"""行情数据服务 — 缓存行情快照。"""
from __future__ import annotations

from typing import Any, Dict

from ..core.agent_scheduler import get_agent_scheduler
from ..core.engine_adapter import get_engine_adapter
from ..data.redis_cache import get_cache


class MarketDataService:
    """对内提供行情查询，对外缓存。"""

    CACHE_TTL = 5  # 秒

    async def get_price(self, symbol: str) -> Dict[str, Any]:
        cache = get_cache()
        key = f"price:{symbol}"
        cached = await cache.get(key)
        if cached is not None:
            return cached
        price = get_engine_adapter().current_price(symbol)
        snapshot = {"symbol": symbol, "price": price}
        await cache.set(key, snapshot, ttl=self.CACHE_TTL)
        return snapshot

    async def load_series(self, symbol: str, timeframe: str, limit: int = 200) -> Dict[str, Any]:
        agent = get_agent_scheduler().get("data")
        res = await agent.handle("load_data", {"symbol": symbol, "timeframe": timeframe, "limit": limit})
        return res.get("result", {})
