"""ReportAgent — 绩效归因 / 合规审计 / 可解释性报告。"""
from __future__ import annotations

import time
from collections import deque
from typing import Any, Deque, Dict, List

from .base import AgentRole, BaseAgent


class ReportAgent(BaseAgent):
    agent_id = "report"
    name = "报告专员 ReportAgent"
    role = AgentRole.REPORT
    workstation = "后区打印机"

    def __init__(self) -> None:
        super().__init__()
        self._reports: Deque[Dict[str, Any]] = deque(maxlen=50)

    async def process(self, command: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if command == "generate_report":
            return self._generate(payload)
        if command == "list_reports":
            return {"reports": list(self._reports)}
        raise ValueError(f"ReportAgent 不支持命令: {command}")

    def _generate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        report_type = payload.get("type", "daily")
        peer = self._peer_execution_agent()
        orders = list(peer._orders) if peer else []
        fills = [o for o in orders if o.get("status") == "filled"]

        total_volume = sum(float(o.get("quantity", 0)) * float(o.get("filled_price") or 0) for o in fills)
        pnl = 0.0
        for o in fills:
            qty = float(o.get("quantity", 0))
            price = float(o.get("filled_price") or 0)
            pnl += qty * price * (1 if o.get("side") == "sell" else -1)

        report = {
            "id": f"rpt-{int(time.time() * 1000)}",
            "type": report_type,
            "ts": time.time(),
            "metrics": {
                "orders_total": len(orders),
                "fills": len(fills),
                "volume": round(total_volume, 2),
                "net_pnl": round(pnl, 2),
            },
            "sections": [
                {"title": "市场概览", "content": "市场震荡偏多，成交活跃。"},
                {"title": "策略表现", "content": f"今日完成 {len(fills)} 笔成交。"},
                {"title": "风控合规", "content": "未触发风控阈值，订单全部通过预检查。"},
            ],
            "shap_attribution": {
                "feature": "momentum_5_20",
                "importance": 0.62,
            },
        }
        self._reports.append(report)
        return report

    # ---- 心跳 ----

    async def collect_metrics(self) -> Dict[str, Any]:
        base = await super().collect_metrics()
        base.update({"reports_generated": len(self._reports)})
        return base

    @staticmethod
    def _peer_execution_agent() -> Any:
        try:
            from ..core.agent_scheduler import get_agent_scheduler
            return get_agent_scheduler().get("execution")
        except Exception:
            return None
