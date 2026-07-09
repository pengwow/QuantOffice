"""通知 / 告警服务 — 聚合风控事件推送。"""
from __future__ import annotations

from typing import Any, Dict

from ..core.agent_scheduler import get_agent_scheduler
from ..core.event_publisher import get_event_publisher


class NotificationService:
    def __init__(self) -> None:
        self._publisher = get_event_publisher()
        # 监听风控事件，自动广播
        self._publisher.subscribe("risk_alert", self._on_risk)

    async def _on_risk(self, payload: Dict[str, Any]) -> None:
        await self._publisher.publish("notification", {"channel": "risk", "data": payload})

    def recent_alerts(self, limit: int = 20) -> list:
        agent = get_agent_scheduler().get("risk")
        return agent.recent_alerts(limit=limit)
