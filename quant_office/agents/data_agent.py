"""DataAgent — 基于 ``axon_quant.data`` 的数据分析师（fallback 用合成数据）。"""
from __future__ import annotations

import math
import random
import time
from typing import Any, Dict, List, Optional

from ..logging_config import get_logger
from .base import AgentRole, BaseAgent

logger = get_logger("agents.data")


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
        # 三层降级：exchange (Binance/OKX 实时 K 线) → axon (本地 ticks 合成) → 纯合成
        bars = self._load_exchange_bars(symbol, timeframe, limit)
        source = "exchange"
        if bars is None:
            bars = self._load_axon_bars(symbol, timeframe, limit)
            source = "axon"
        if bars is None:
            bars = self._synth_bars(symbol, timeframe, limit)
            source = "synthetic"
        # 简单特征
        closes = [b["close"] for b in bars]
        self._enrich(bars, closes)
        self._cache[f"{symbol}_{timeframe}"] = bars
        self._last_loaded = time.time()
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "bars": len(bars),
            "source": source,
            "first": bars[0],
            "last": bars[-1],
        }

    # ---- 真实交易所 ----

    # timeframe -> Binance interval 映射
    _TIMEFRAME_INTERVAL_MAP: Dict[str, str] = {
        "1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m", "30m": "30m",
        "1h": "1h", "2h": "2h", "4h": "4h", "6h": "6h", "8h": "8h", "12h": "12h",
        "1d": "1d", "3d": "3d", "1w": "1w", "1M": "1M",
    }

    @classmethod
    def _timeframe_to_interval(cls, timeframe: str) -> Optional[str]:
        return cls._TIMEFRAME_INTERVAL_MAP.get(timeframe.lower())

    def _load_exchange_bars(
        self, symbol: str, timeframe: str, limit: int
    ) -> Optional[List[Dict[str, Any]]]:
        """通过 ``ExchangeClient.get_klines`` 拉交易所真实 K 线（无 key 也可走公共行情）。

        失败/未联网/不支持的 timeframe 时返回 None 触发 axon fallback。
        """
        interval = self._timeframe_to_interval(timeframe)
        if interval is None:
            return None
        try:
            from ..core.exchange_client import ExchangeError, get_exchange_client
        except Exception:
            return None
        try:
            client = get_exchange_client()
            raw = client.get_klines(symbol, interval=interval, limit=min(limit, 1000))
        except ExchangeError as exc:
            logger.warning("exchange 拉取失败，fallback axon: %s", exc)
            return None
        except Exception as exc:  # pragma: no cover
            logger.warning("exchange 拉取异常，fallback axon: %s", exc)
            return None
        if not raw:
            return None
        # Binance kline 行已转 dict；按时间升序
        return sorted(raw, key=lambda r: int(r.get("ts", 0)))

    # ---- axon 真接 ----

    def _load_axon_bars(self, symbol: str, timeframe: str, limit: int) -> Optional[List[Dict[str, Any]]]:
        """通过 ``axon_quant.data.DataService + MockSource.with_tick_series`` 拉真 ticks，
        再在 Python 侧按 timeframe 聚合成 OHLCV bars。失败时返回 None 触发 fallback。"""
        try:
            import axon_quant as aq  # type: ignore
        except Exception:
            return None
        try:
            from datetime import datetime, timezone

            tf_sec = self._timeframe_seconds(timeframe)
            # 每个 bar 采样 ticks：根据 limit 反算，保证能产足 bars
            # 上限 total_ticks=200_000；最少 60 ticks/bar 以保证有 OHLCV 变化
            ticks_per_bar = max(60, min(tf_sec, 200_000 // max(1, limit)))
            total_ticks = min(limit * ticks_per_bar, 200_000)
            # MockSource 步长：bar_sec / ticks_per_bar；最少 1ns
            nanos_per_step = max(1, int(tf_sec * 1_000_000_000 / max(1, ticks_per_bar)))

            base_price = 30_000.0 if "BTC" in symbol else 100.0

            def price_fn(i: int) -> float:
                # 漂移 + 周期 + 噪声，模拟真实走势
                drift = math.sin(i / 200.0) * 0.002
                cycle = math.sin(i * 0.013) * 0.008
                noise = ((i * 1103515245 + 12345) % 1000) / 1000.0 - 0.5
                return base_price * (1.0 + drift + cycle + noise * 0.004)

            ds = aq.DataService()
            src = aq.MockSource.with_tick_series(
                f"{symbol.lower()}_ticks", total_ticks, nanos_per_step, price_fn
            )
            ds.register_source(src)
            start = datetime.now(timezone.utc)
            end = datetime.now(timezone.utc)
            req = aq.DataRequest(symbol, start, end, aq.Frequency.Tick)
            dataset = ds.load(req)
            ticks = list(dataset.ticks())
            if not ticks:
                return None
            return self._aggregate_ticks(ticks, tf_sec, ticks_per_bar, limit)
        except Exception as exc:  # pragma: no cover
            logger.warning("axon 拉取失败，fallback 合成: %s", exc)
            return None

    @staticmethod
    def _aggregate_ticks(
        ticks: List[Any], tf_sec: int, ticks_per_bar: int, limit: int
    ) -> List[Dict[str, Any]]:
        """ticks → OHLCV bars（按 tick 序号等距分桶）。"""
        bars: List[Dict[str, Any]] = []
        cur: Optional[Dict[str, Any]] = None
        for i, t in enumerate(ticks):
            bar_idx = i // ticks_per_bar
            if bar_idx >= limit:
                break
            price = float(t.price)
            qty = float(t.qty)
            if cur is None or cur["_bar_idx"] != bar_idx:
                if cur is not None:
                    bars.append(cur)
                cur = {
                    "_bar_idx": bar_idx,
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": qty,
                }
            else:
                cur["high"] = max(cur["high"], price)
                cur["low"] = min(cur["low"], price)
                cur["close"] = price
                cur["volume"] += qty
        if cur is not None:
            bars.append(cur)

        now = int(time.time())
        out: List[Dict[str, Any]] = []
        for i, b in enumerate(bars):
            ts = now - (len(bars) - i) * tf_sec
            out.append(
                {
                    "ts": ts,
                    "open": b["open"],
                    "high": b["high"],
                    "low": b["low"],
                    "close": b["close"],
                    "volume": b["volume"],
                }
            )
        return out

    # ---- fallback 合成 ----

    def _synth_bars(self, symbol: str, timeframe: str, limit: int) -> List[Dict[str, Any]]:
        """未装 axon 时合成 SMA/EMA 友好的随机游走数据。"""
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
        return bars

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
