"""QuantOffice 多 Agent 协作框架 — 1 主 + 5 副 Agent。

业务逻辑被独立模式与插件模式 100% 共享。
"""
from __future__ import annotations

from typing import Callable, Dict

from .base import AgentRole, AgentStatus, BaseAgent
from .chief_agent import ChiefTraderAgent
from .data_agent import DataAgent
from .execution_agent import ExecutionAgent
from .report_agent import ReportAgent
from .risk_agent import RiskAgent
from .strategy_agent import StrategyAgent


def _build_chief() -> BaseAgent:
    return ChiefTraderAgent()


def _build_data() -> BaseAgent:
    return DataAgent()


def _build_strategy() -> BaseAgent:
    return StrategyAgent()


def _build_risk() -> BaseAgent:
    return RiskAgent()


def _build_execution() -> BaseAgent:
    return ExecutionAgent()


def _build_report() -> BaseAgent:
    return ReportAgent()


AGENT_REGISTRY: Dict[str, Callable[[], BaseAgent]] = {
    "chief": _build_chief,
    "data": _build_data,
    "strategy": _build_strategy,
    "risk": _build_risk,
    "execution": _build_execution,
    "report": _build_report,
}


__all__ = [
    "AGENT_REGISTRY",
    "AgentRole",
    "AgentStatus",
    "BaseAgent",
    "ChiefTraderAgent",
    "DataAgent",
    "StrategyAgent",
    "RiskAgent",
    "ExecutionAgent",
    "ReportAgent",
]
