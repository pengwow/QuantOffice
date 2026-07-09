"""Agent 基类 — 1+5 Agent 抽象。"""
from __future__ import annotations

import abc
import asyncio
import time
from collections import deque
from enum import Enum
from typing import Any, Deque, Dict, List, Optional

from ..logging_config import get_logger


class AgentStatus(str, Enum):
    """Agent 可视化状态，对应前端 Agent 卡片状态色。"""

    IDLE = "idle"          # 绿
    WORKING = "working"    # 黄
    ALERT = "alert"        # 红
    ERROR = "error"        # 红闪烁
    STOPPED = "stopped"


class AgentRole(str, Enum):
    CHIEF = "ChiefTrader"
    DATA = "DataAgent"
    STRATEGY = "StrategyAgent"
    RISK = "RiskAgent"
    EXECUTION = "ExecutionAgent"
    REPORT = "ReportAgent"


class BaseAgent(abc.ABC):
    """所有 Agent 的基类。

    每个 Agent 负责：
    1. 维护自身状态（``status``）
    2. 接收并执行命令（``handle``）
    3. 周期心跳（``tick``）
    4. 记录最近日志（``logs``）
    """

    agent_id: str = "agent"
    name: str = "Agent"
    role: AgentRole = AgentRole.CHIEF
    workstation: str = "中央"

    def __init__(self) -> None:
        self.status: AgentStatus = AgentStatus.STOPPED
        self._logs: Deque[Dict[str, Any]] = deque(maxlen=200)
        self._lock = asyncio.Lock()
        self._started_at: Optional[float] = None
        self._commands_processed: int = 0
        self._last_metrics: Dict[str, Any] = {}
        self._logger = get_logger(f"agent.{self.agent_id}")

    # ---- 生命周期 ----

    async def start(self) -> None:
        async with self._lock:
            self._started_at = time.time()
            self._log("info", f"{self.name} 已启动")
        await self.on_start()

    async def stop(self) -> None:
        await self.on_stop()
        self.status = AgentStatus.STOPPED
        self._log("info", f"{self.name} 已停止")

    async def on_start(self) -> None:  # noqa: B027
        """子类可选覆盖。"""
        return None

    async def on_stop(self) -> None:  # noqa: B027
        """子类可选覆盖。"""
        return None

    # ---- 业务入口 ----

    async def handle(self, command: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """接收并执行命令。"""
        payload = payload or {}
        self._commands_processed += 1
        prev = self.status
        self.status = AgentStatus.WORKING
        self._log("info", f"收到命令: {command} payload={payload}")
        try:
            result = await self.process(command, payload)
            self._log("info", f"命令完成: {command}")
            return {"ok": True, "result": result, "agent": self.agent_id}
        except Exception as exc:  # pragma: no cover
            self.status = AgentStatus.ERROR
            self._log("error", f"命令异常: {exc}")
            return {"ok": False, "error": str(exc), "agent": self.agent_id}
        finally:
            # 成功后回到 idle，失败保持 error
            if self.status == AgentStatus.WORKING:
                self.status = prev if prev in (AgentStatus.IDLE, AgentStatus.WORKING) else AgentStatus.IDLE

    @abc.abstractmethod
    async def process(self, command: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """业务逻辑入口（子类必须实现）。"""

    # ---- 心跳 ----

    async def tick(self) -> Dict[str, Any]:
        """周期心跳 — 返回指标用于前端展示。"""
        try:
            metrics = await self.collect_metrics()
        except Exception as exc:  # pragma: no cover
            metrics = {"error": str(exc)}
        self._last_metrics = metrics
        return metrics

    async def collect_metrics(self) -> Dict[str, Any]:
        return {
            "uptime_sec": (time.time() - self._started_at) if self._started_at else 0.0,
            "commands": self._commands_processed,
            "status": self.status.value,
        }

    # ---- 日志 ----

    def _log(self, level: str, message: str) -> None:
        entry = {"ts": time.time(), "level": level, "message": message, "agent": self.agent_id}
        self._logs.append(entry)
        getattr(self._logger, level, self._logger.info)(message)

    def recent_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        return list(self._logs)[-limit:]

    @property
    def metrics(self) -> Dict[str, Any]:
        return self._last_metrics
