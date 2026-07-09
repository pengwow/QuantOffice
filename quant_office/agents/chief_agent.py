"""ChiefTrader — 统筹 1+5 Agent 的主 Agent。

基于 ``axon_quant.llm.SwarmOrchestrator`` + ``ReActAgent``；
fallback 模式下提供内存版的指令分发。
"""
from __future__ import annotations

from typing import Any, Dict, List

from .base import AgentRole, AgentStatus, BaseAgent


class ChiefTraderAgent(BaseAgent):
    agent_id = "chief"
    name = "首席交易员 ChiefTrader"
    role = AgentRole.CHIEF
    workstation = "中央指挥台"

    _TOOL_AGENT_MAP: Dict[str, str] = {
        "query_market": "data",
        "load_data": "data",
        "list_strategies": "strategy",
        "run_backtest": "strategy",
        "place_order": "execution",
        "list_orders": "execution",
        "check_risk": "risk",
        "get_risk_metrics": "risk",
        "generate_report": "report",
    }

    async def process(self, command: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        from ..core.event_publisher import get_event_publisher

        publisher = get_event_publisher()
        target_agent = self._TOOL_AGENT_MAP.get(command, "data")

        # 在 fallback 模式下，ChiefTrader 仅做任务分发与汇总
        await publisher.publish(
            "chief_dispatch",
            {
                "command": command,
                "target": target_agent,
                "payload": payload,
            },
        )

        thought = self._build_thought(command, payload)
        actions: List[Dict[str, Any]] = [
            {
                "tool": command,
                "agent": target_agent,
                "dispatched": True,
            }
        ]
        return {
            "thought": thought,
            "actions": actions,
            "summary": f"已将命令 `{command}` 分发给 {target_agent}",
        }

    @staticmethod
    def _build_thought(command: str, payload: Dict[str, Any]) -> str:
        mapping_explain = {
            "query_market": "市场数据查询 → DataAgent",
            "load_data": "数据加载请求 → DataAgent",
            "list_strategies": "策略列表查询 → StrategyAgent",
            "run_backtest": "回测任务提交 → StrategyAgent",
            "place_order": "下单请求 → ExecutionAgent（先经 RiskAgent 风控）",
            "list_orders": "订单查询 → ExecutionAgent",
            "check_risk": "风控检查 → RiskAgent",
            "get_risk_metrics": "风险指标查询 → RiskAgent",
            "generate_report": "报告生成 → ReportAgent",
        }
        return mapping_explain.get(command, f"通用调度: {command} payload={payload}")

    async def collect_metrics(self) -> Dict[str, Any]:
        base = await super().collect_metrics()
        base.update(
            {
                "dispatched_commands": self._commands_processed,
                "managed_agents": 5,
            }
        )
        return base
