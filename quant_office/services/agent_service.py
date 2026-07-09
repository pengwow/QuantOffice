"""Agent 编排服务。"""
from __future__ import annotations

from typing import Any, Dict, List

from ..core.agent_scheduler import get_agent_scheduler


class AgentService:
    """Agent 业务编排门面。"""

    def list_agents(self) -> List[Dict[str, Any]]:
        return get_agent_scheduler().summary()

    def dispatch(self, agent_id: str, command: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        agent = get_agent_scheduler().get(agent_id)
        return agent.handle_sync(command, payload) if hasattr(agent, "handle_sync") else {}

    def snapshot(self) -> Dict[str, Any]:
        return {"agents": self.list_agents()}
