"""ExecutionAgent — OMS + 交易所适配器封装（fallback 走内存 OMS）。"""
from __future__ import annotations

import time
from typing import Any, Dict, List

from .base import AgentRole, BaseAgent


class ExecutionAgent(BaseAgent):
    agent_id = "execution"
    name = "执行交易员 ExecutionAgent"
    role = AgentRole.EXECUTION
    workstation = "右侧订单簿屏"

    def __init__(self) -> None:
        super().__init__()
        self._orders: List[Dict[str, Any]] = []

    async def process(self, command: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if command == "place_order":
            return await self._place_order(payload)
        if command == "list_orders":
            return {"orders": self._orders[-50:]}
        if command == "cancel_order":
            return self._cancel_order(payload.get("order_id"))
        raise ValueError(f"ExecutionAgent 不支持命令: {command}")

    async def _place_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        from ..core.engine_adapter import OrderRequest, Portfolio, get_engine_adapter
        from ..core.event_publisher import get_event_publisher

        # 1. 风控
        risk_agent = self._peer_risk_agent()
        if risk_agent is not None:
            check = await risk_agent.handle("check_risk", order)
            result = check.get("result", {})
            if not result.get("passed", True):
                self._log("warning", f"风控拒绝: {result.get('message')}")
                return {"status": "rejected", "reason": result.get("message"), "agent": "risk"}

        # 2. 下单（axon / fallback OMS 都会返回 filled 或 submitted）
        req = OrderRequest(
            symbol=order.get("symbol", "BTCUSDT"),
            side=order.get("side", "buy"),
            quantity=float(order.get("quantity", 0.0)),
            order_type=order.get("order_type", "market"),
            price=order.get("price"),
        )
        result = await get_engine_adapter().submit_order(req, self._build_portfolio(risk_agent))

        # 3. 如果已成交（axon + fallback OMS 都返回 filled），把仓位应用到 RiskAgent
        if result.status == "filled" and risk_agent is not None and result.filled_price is not None:
            risk_agent.apply_fill(req.symbol, req.side, req.quantity, result.filled_price)

        record = result.to_dict()
        record["ts"] = time.time()
        self._orders.append(record)
        if len(self._orders) > 200:
            self._orders = self._orders[-200:]

        # 4. 推送 trade_execution 事件
        await get_event_publisher().publish(
            "trade_execution",
            {"order": record, "agent": self.agent_id},
        )
        return record

    def _cancel_order(self, order_id: str) -> Dict[str, Any]:
        for o in self._orders:
            if o.get("order_id") == order_id and o.get("status") in ("submitted",):
                o["status"] = "cancelled"
                return o
        return {"error": f"订单 {order_id} 不可取消或不存在"}

    # ---- 心跳 ----

    async def collect_metrics(self) -> Dict[str, Any]:
        base = await super().collect_metrics()
        fills = [o for o in self._orders if o.get("status") == "filled"]
        base.update(
            {
                "orders_total": len(self._orders),
                "orders_filled": len(fills),
                "orders_rejected": sum(1 for o in self._orders if o.get("status") == "rejected"),
            }
        )
        return base

    # ---- 工具 ----

    @staticmethod
    def _peer_risk_agent() -> Any:
        try:
            from ..core.agent_scheduler import get_agent_scheduler
            return get_agent_scheduler().get("risk")
        except Exception:
            return None

    def _build_portfolio(self, risk_agent: Any) -> Any:
        from ..core.engine_adapter import Portfolio
        if risk_agent is None:
            return Portfolio()
        # 走公开 API，不再直读 risk_agent._portfolio_snapshot
        snap = risk_agent.get_portfolio_snapshot()
        return Portfolio(
            cash=snap.get("cash", 100_000.0),
            positions={k: float(v) for k, v in snap.get("positions", {}).items()},
        )
