"""交易所客户端 — 简洁包装 Binance / OKX REST API。

设计：
  - 仅用 httpx（不引入 ccxt）— 减少依赖，控制依赖图
  - 同时支持 testnet / 主网
  - 未配置 API key 时仅可访问公共行情，私有接口 401
  - 与 ``AxonQuantAdapter`` 解耦：业务通过 ``get_exchange_client()`` 拿单例

支持接口：
  - ``get_ticker(symbol)``        当前价 / 24h 变化
  - ``get_klines(symbol, interval, limit)``  K 线
  - ``get_account()``             账户余额（需 API key）
  - ``submit_order(...)``         提交订单（需 API key）
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx

from ..logging_config import get_logger
from .runtime_config import ExchangeConfig, get_runtime_config

logger = get_logger("core.exchange")


# ============================================================
# 预设 venue
# ============================================================
VENUE_PRESETS: Dict[str, Dict[str, Any]] = {
    "binance": {
        "label": "Binance（币安）",
        "base_url": "https://api.binance.com",
        "testnet_base_url": "https://testnet.binance.vision",
    },
    "okx": {
        "label": "OKX",
        "base_url": "https://www.okx.com",
    },
    "bybit": {
        "label": "Bybit",
        "base_url": "https://api.bybit.com",
    },
}


class ExchangeError(RuntimeError):
    pass


class ExchangeClient:
    def __init__(self, config: Optional[ExchangeConfig] = None) -> None:
        self.config = config or get_runtime_config().get_exchange()

    # ---- 基础 URL ----
    def base_url(self) -> str:
        preset = VENUE_PRESETS.get(self.config.venue, VENUE_PRESETS["binance"])
        if self.config.venue == "binance" and self.config.testnet:
            return preset["testnet_base_url"]
        return preset["base_url"]

    def _has_creds(self) -> bool:
        return bool(self.config.api_key) and bool(self.config.api_secret)

    # ---- 签名（Binance 风格 HMAC-SHA256）----
    @staticmethod
    def _sign(secret: str, query: str) -> str:
        return hmac.new(secret.encode("utf-8"), query.encode("utf-8"), hashlib.sha256).hexdigest()

    # ---- 公共行情 ----
    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        symbol = symbol.upper()
        url = f"{self.base_url()}/api/v3/ticker/24hr"
        try:
            with httpx.Client(timeout=self.config.timeout_sec) as client:
                resp = client.get(url, params={"symbol": symbol})
            if resp.status_code != 200:
                raise ExchangeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            data = resp.json()
            return {
                "symbol": data.get("symbol", symbol),
                "last_price": float(data.get("lastPrice", 0) or 0),
                "bid": float(data.get("bidPrice", 0) or 0),
                "ask": float(data.get("askPrice", 0) or 0),
                "high_24h": float(data.get("highPrice", 0) or 0),
                "low_24h": float(data.get("lowPrice", 0) or 0),
                "volume_24h": float(data.get("volume", 0) or 0),
                "change_pct": float(data.get("priceChangePercent", 0) or 0),
            }
        except httpx.HTTPError as exc:
            raise ExchangeError(f"行情网络错误: {exc}") from exc

    def get_klines(
        self, symbol: str, interval: str = "1h", limit: int = 100
    ) -> List[Dict[str, Any]]:
        symbol = symbol.upper()
        url = f"{self.base_url()}/api/v3/klines"
        try:
            with httpx.Client(timeout=self.config.timeout_sec) as client:
                resp = client.get(url, params={"symbol": symbol, "interval": interval, "limit": limit})
            if resp.status_code != 200:
                raise ExchangeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            raw = resp.json()
            out: List[Dict[str, Any]] = []
            for row in raw:
                # Binance 格式：[openTime, open, high, low, close, volume, ...]
                out.append({
                    "ts": int(row[0]),
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[5]),
                })
            return out
        except httpx.HTTPError as exc:
            raise ExchangeError(f"K线网络错误: {exc}") from exc

    # ---- 私有接口（需签名）----
    def get_account(self) -> Dict[str, Any]:
        if not self._has_creds():
            raise ExchangeError("未配置 API key / secret")
        params = {"timestamp": int(time.time() * 1000), "recvWindow": 5000}
        qs = urlencode(params)
        params["signature"] = self._sign(self.config.api_secret, qs)
        url = f"{self.base_url()}/api/v3/account"
        try:
            with httpx.Client(timeout=self.config.timeout_sec) as client:
                resp = client.get(
                    url,
                    params=params,
                    headers={"X-MBX-APIKEY": self.config.api_key},
                )
            if resp.status_code != 200:
                raise ExchangeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
            return resp.json()
        except httpx.HTTPError as exc:
            raise ExchangeError(f"账户网络错误: {exc}") from exc

    def submit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "MARKET",
        price: Optional[float] = None,
    ) -> Dict[str, Any]:
        if not self._has_creds():
            raise ExchangeError("未配置 API key / secret")
        params: Dict[str, Any] = {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "type": order_type.upper(),
            "quantity": quantity,
            "timestamp": int(time.time() * 1000),
            "recvWindow": 5000,
        }
        if order_type.upper() == "LIMIT":
            if price is None:
                raise ExchangeError("LIMIT 单必须指定 price")
            params["price"] = price
            params["timeInForce"] = "GTC"
        qs = urlencode(params)
        params["signature"] = self._sign(self.config.api_secret, qs)
        url = f"{self.base_url()}/api/v3/order"
        try:
            with httpx.Client(timeout=self.config.timeout_sec) as client:
                resp = client.post(
                    url,
                    params=params,
                    headers={"X-MBX-APIKEY": self.config.api_key},
                )
            if resp.status_code not in (200, 201):
                raise ExchangeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
            return resp.json()
        except httpx.HTTPError as exc:
            raise ExchangeError(f"下单网络错误: {exc}") from exc

    # ---- 健康检查 ----
    def test_connection(self) -> Dict[str, Any]:
        try:
            # 公共 ping
            with httpx.Client(timeout=min(self.config.timeout_sec, 8)) as client:
                resp = client.get(f"{self.base_url()}/api/v3/ping")
            if resp.status_code != 200:
                return {"ok": False, "error": f"ping HTTP {resp.status_code}"}
            # 公共 ticker
            ticker = self.get_ticker("BTCUSDT")
            return {
                "ok": True,
                "venue": self.config.venue,
                "testnet": self.config.testnet,
                "base_url": self.base_url(),
                "btc_price": ticker["last_price"],
                "has_creds": self._has_creds(),
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc), "base_url": self.base_url()}


# ============================================================
# 单例
# ============================================================
_client: Optional[ExchangeClient] = None


def get_exchange_client() -> ExchangeClient:
    global _client
    if _client is None:
        _client = ExchangeClient()
    return _client
