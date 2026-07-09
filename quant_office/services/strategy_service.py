"""策略服务（生命周期管理）。"""
from __future__ import annotations

from typing import Any, Dict, List

from ..core.agent_scheduler import get_agent_scheduler


class StrategyService:
    def list(self) -> List[Dict[str, Any]]:
        agent = get_agent_scheduler().get("strategy")
        return agent._strategies  # noqa: SLF001

    def activate(self, name: str) -> Dict[str, Any]:
        agent = get_agent_scheduler().get("strategy")
        return agent._activate_strategy(name)  # noqa: SLF001
