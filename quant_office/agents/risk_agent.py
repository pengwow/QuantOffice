"""RiskAgent — 12ns 预交易风控 + 实时组合风险监控。

阈值（VaR 上限、告警历史长度）从 ``RuntimeConfigStore.risk`` 热读取；
UI 改完立即生效，无需重启 Agent。
"""
from __future__ import annotations

import math
import time
from typing import Any, Dict, List

from .base import AgentRole, BaseAgent


def _active_risk_cfg() -> Any:
    """每次调用重读最新阈值，保证 UI 热更新（lazy import 避开循环）。"""
    from ..core.runtime_config import get_runtime_config
    return get_runtime_config().get_risk()


class RiskAgent(BaseAgent):
    agent_id = "risk"
    name = "风控官 RiskAgent"
    role = AgentRole.RISK
    workstation = "右前红绿灯面板"

    def __init__(self) -> None:
        super().__init__()
        self._circuit_tripped = False
        self._alerts: List[Dict[str, Any]] = []
        self._portfolio_snapshot: Dict[str, Any] = {
            "cash": 100_000.0,
            "positions": {},
            "pnl": 0.0,
        }

    async def process(self, command: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if command == "check_risk":
            return await self._check_risk(payload)
        if command == "get_risk_metrics":
            return self._metrics()
        if command == "reset_circuit":
            self._circuit_tripped = False
            return {"circuit_tripped": False}
        if command == "update_portfolio":
            self._portfolio_snapshot = payload
            return {"ok": True}
        raise ValueError(f"RiskAgent 不支持命令: {command}")

    # ---- 业务方法 ----

    async def _check_risk(self, order: Dict[str, Any]) -> Dict[str, Any]:
        from ..core.engine_adapter import OrderRequest, get_engine_adapter

        engine = get_engine_adapter()
        portfolio = self._build_portfolio()
        req = OrderRequest(
            symbol=order.get("symbol", "BTCUSDT"),
            side=order.get("side", "buy"),
            quantity=float(order.get("quantity", 0.0)),
            order_type=order.get("order_type", "market"),
            price=order.get("price"),
        )
        result = engine.pre_trade_check(req, portfolio)
        out = result.to_dict()
        if not result.passed:
            cfg = _active_risk_cfg()
            alert = {
                "level": "CRITICAL" if result.severity == "critical" else "WARNING",
                "type": result.failed_check,
                "message": result.message,
                "ts": time.time(),
            }
            self._alerts.append(alert)
            # 滚动丢弃：保留最近 N 条（N 从配置读）
            if len(self._alerts) > cfg.alert_history_size:
                self._alerts = self._alerts[-cfg.alert_history_size:]
            # 触发熔断
            if result.severity == "critical":
                self._circuit_tripped = True
        return out

    def _metrics(self) -> Dict[str, Any]:
        cfg = _active_risk_cfg()
        positions = self._portfolio_snapshot.get("positions", {})
        total = self._portfolio_snapshot.get("cash", 0.0)
        for symbol, qty in positions.items():
            total += qty * self._mark_price(symbol)
        # VaR 95%：占组合价值比例从 RiskConfig 读（默认 0.02）
        var_95 = max(0.0, total * cfg.var_pct_limit)
        return {
            "portfolio_value": total,
            "positions": positions,
            "var_95": var_95,
            "var_pct_limit": cfg.var_pct_limit,
            "circuit_tripped": self._circuit_tripped,
            "alerts_count": len(self._alerts),
            "ts": time.time(),
        }

    def recent_alerts(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._alerts[-limit:]

    # ---- 心跳 ----

    async def collect_metrics(self) -> Dict[str, Any]:
        base = await super().collect_metrics()
        m = self._metrics()
        base.update(m)
        return base

    # ---- 工具 ----

    def _build_portfolio(self) -> Any:
        from ..core.engine_adapter import Portfolio
        positions = self._portfolio_snapshot.get("positions", {})
        return Portfolio(
            cash=self._portfolio_snapshot.get("cash", 100_000.0),
            positions={k: float(v) for k, v in positions.items()},
        )

    @staticmethod
    def _mark_price(symbol: str) -> float:
        from ..core.engine_adapter import get_engine_adapter
        return get_engine_adapter().current_price(symbol)
