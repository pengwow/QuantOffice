"""ChiefTrader — 统筹 1+5 Agent 的主 Agent。

基于 ``axon_quant.llm.SwarmOrchestrator`` + ``ReActAgent``；
fallback 模式下提供内存版的指令分发 + 可选 LLM 润色回复。
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

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

    _THOUGHT_TEMPLATES: Dict[str, str] = {
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

    async def process(self, command: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        from ..core.event_publisher import get_event_publisher
        from ..core.runtime_config import get_runtime_config

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

        thought = self._THOUGHT_TEMPLATES.get(command, f"通用调度: {command} payload={payload}")
        actions: List[Dict[str, Any]] = [
            {
                "tool": command,
                "agent": target_agent,
                "dispatched": True,
            }
        ]

        # 可选：用 LLM 润色回复（如果用户在 payload 中提供了 context 字段）
        result: Dict[str, Any] = {
            "thought": thought,
            "actions": actions,
            "summary": f"已将命令 `{command}` 分发给 {target_agent}",
        }

        llm_remark = await self._maybe_llm_commentary(command, payload, result)
        if llm_remark:
            result["llm_commentary"] = llm_remark

        return result

    async def _maybe_llm_commentary(
        self, command: str, payload: Dict[str, Any], result: Dict[str, Any]
    ) -> Optional[str]:
        """若启用 LLM 且 payload 中显式 ask_llm=true，则用 LLM 给一段简短点评。"""
        if not payload.get("ask_llm"):
            return None
        try:
            from ..core.llm_client import ChatMessage, is_llm_configured
            from ..core.llm_client import make_llm_client
        except Exception:
            return None
        if not is_llm_configured():
            return None
        try:
            client = make_llm_client()
            prompt = (
                f"你是一个量化交易指挥中枢的首席交易员。"
                f"用户命令：{command}\n上下文：{payload}\n"
                f"系统结果：{result}\n请用 1-2 句中文点评执行情况。"
            )
            resp = await client.achat([ChatMessage(role="user", content=prompt)], max_tokens=200)
            return resp.content.strip()
        except Exception as exc:  # pragma: no cover
            from ..logging_config import get_logger
            get_logger("agents.chief").warning("LLM 润色失败: %s", exc)
            return None

    @staticmethod
    def _build_thought(command: str, payload: Dict[str, Any]) -> str:
        return ChiefTraderAgent._THOUGHT_TEMPLATES.get(
            command, f"通用调度: {command} payload={payload}"
        )

    async def collect_metrics(self) -> Dict[str, Any]:
        base = await super().collect_metrics()
        base.update(
            {
                "dispatched_commands": self._commands_processed,
                "managed_agents": 5,
            }
        )
        return base
