"""DataAgent — 基于 ``axon_quant.data`` 的数据分析师（fallback 用合成数据）。"""
from __future__ import annotations

import math
import random
import time
from typing import Any, Dict, List, Optional

from .base import AgentRole, BaseAgent


class DataAgent(BaseAgent):
    agent_id = "data"
    name = "数据分析师 DataAgent"
    role = AgentRole.DATA
    workstation = "左侧数据瀑布屏"

    def __init__(self) -> None:
        super().__init__()
        self._cache: Dict[str, List[Dict[str, Any]]] = {}
        self._last_loaded: Optional[float] = None

    async def process(self, command: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if command == "load_data":
            return await self._load_data(
                symbol=payload.get("symbol", "BTCUSDT"),
                timeframe=payload.get("timeframe", "1h"),
                limit=int(payload.get("limit", 200)),
            )
        if command == "query_market":
            return self._query_market(payload.get("symbol", "BTCUSDT"))
        if command == "compute_features":
            return self._compute_features(
                symbol=payload.get("symbol", "BTCUSDT"),
                features=payload.get("features", ["sma", "rsi"]),
            )
        raise ValueError(f"DataAgent 不支持命令: {command}")

    # ---- 业务方法 ----

    async def _load_data(self, symbol: str, timeframe: str, limit: int) -> Dict[str, Any]:
        # Fallback：合成 SMA/EMA 友好的随机游走数据
        random.seed(hash(symbol) & 0xFFFF)
        base_price = 30_000.0 if "BTC" in symbol else 100.0
        now = int(time.time())
        step_sec = self._timeframe_seconds(timeframe)
        bars: List[Dict[str, Any]] = []
        price = base_price
        closes: List[float] = []
        for i in range(limit):
            ts = now - (limit - i) * step_sec
            drift = math.sin(i / 12.0) * 0.002
            shock = random.gauss(0, 0.012)
            ret = drift + shock
            o = price
            c = max(0.01, price * (1 + ret))
            h = max(o, c) * (1 + abs(random.gauss(0, 0.004)))
            l = min(o, c) * (1 - abs(random.gauss(0, 0.004)))
            v = abs(random.gauss(1000, 200))
            closes.append(c)
            bars.append(
                {
                    "ts": ts,
                    "open": o,
                    "high": h,
                    "low": l,
                    "close": c,
                    "volume": v,
                }
            )
            price = c
        # 简单特征
        self._enrich(bars, closes)
        self._cache[f"{symbol}_{timeframe}"] = bars
        self._last_loaded = time.time()
        return {"symbol": symbol, "timeframe": timeframe, "bars": len(bars), "first": bars[0], "last": bars[-1]}

    def _query_market(self, symbol: str) -> Dict[str, Any]:
        from ..core.engine_adapter import get_engine_adapter
        price = get_engine_adapter().current_price(symbol)
        return {"symbol": symbol, "price": price, "ts": time.time()}

    def _compute_features(self, symbol: str, features: List[str]) -> Dict[str, Any]:
        key = next((k for k in self._cache if k.startswith(symbol + "_")), None)
        if not key:
            return {"error": f"无 {symbol} 缓存数据，请先调用 load_data"}
        bars = self._cache[key]
        closes = [b["close"] for b in bars]
        out: Dict[str, Any] = {"symbol": symbol, "features": {}}
        if "sma" in features:
            out["features"]["sma5"] = closes[-1] - sum(closes[-5:]) / 5
            out["features"]["sma20"] = closes[-1] - sum(closes[-20:]) / 20
        if "rsi" in features:
            gains = [max(0, closes[i] - closes[i - 1]) for i in range(-14, 0)]
            losses = [max(0, closes[i - 1] - closes[i]) for i in range(-14, 0)]
            avg_g = sum(gains) / 14 if gains else 0
            avg_l = sum(losses) / 14 if losses else 1e-9
            rs = avg_g / max(avg_l, 1e-9)
            out["features"]["rsi"] = 100 - 100 / (1 + rs)
        return out

    # ---- 心跳 ----

    async def collect_metrics(self) -> Dict[str, Any]:
        base = await super().collect_metrics()
        base.update(
            {
                "cached_series": len(self._cache),
                "last_loaded_ts": self._last_loaded,
            }
        )
        return base

    # ---- 工具 ----

    @staticmethod
    def _timeframe_seconds(tf: str) -> int:
        tf = tf.lower()
        if tf.endswith("m"):
            return int(tf[:-1]) * 60
        if tf.endswith("h"):
            return int(tf[:-1]) * 3600
        if tf.endswith("d"):
            return int(tf[:-1]) * 86_400
        return 3600

    @staticmethod
    def _enrich(bars: List[Dict[str, Any]], closes: List[float]) -> None:
        for i, b in enumerate(bars):
            if i >= 5:
                b["sma5"] = sum(closes[i - 5 : i]) / 5
            if i >= 20:
                b["sma20"] = sum(closes[i - 20 : i]) / 20
