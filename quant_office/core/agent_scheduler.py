"""Agent 调度器 — 独立模式与插件模式共享。

调度 6 个 Agent 的运行时生命周期：
- 启动 / 停止全部
- 心跳上报（→ WebSocket 推送 agent_status）
- 注册业务 handler（→ EventBus 监听）
"""
from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable, Dict, List, Optional

from ..agents import AGENT_REGISTRY
from ..agents.base import AgentStatus, BaseAgent
from ..logging_config import get_logger
from .event_publisher import EventPublisher, get_event_publisher
from .websocket_manager import WebSocketManager, get_websocket_manager

logger = get_logger("core.scheduler")


class AgentScheduler:
    """管理 1+5 Agent 生命周期 + 周期心跳。"""

    HEARTBEAT_INTERVAL = 2.0  # 秒

    def __init__(
        self,
        ws_manager: WebSocketManager | None = None,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        self.ws_manager = ws_manager or get_websocket_manager()
        self.event_publisher = event_publisher or get_event_publisher()
        self._agents: Dict[str, BaseAgent] = {}
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False

    # ---- 生命周期 ----

    async def start_all(self) -> None:
        if self._running:
            return
        self._running = True
        self._agents = {name: factory() for name, factory in AGENT_REGISTRY.items()}
        for name, agent in self._agents.items():
            try:
                await agent.start()
                agent.status = AgentStatus.IDLE
                logger.info("Agent 已启动: %s", name)
            except Exception as exc:  # pragma: no cover
                logger.exception("Agent 启动失败 %s: %s", name, exc)
                agent.status = AgentStatus.ERROR
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("AgentScheduler 已启动，共 %d 个 Agent", len(self._agents))

    async def stop_all(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except (asyncio.CancelledError, Exception):
                pass
            self._heartbeat_task = None
        for name, agent in self._agents.items():
            try:
                await agent.stop()
            except Exception as exc:  # pragma: no cover
                logger.exception("Agent 停止失败 %s: %s", name, exc)
        self._agents.clear()
        logger.info("AgentScheduler 已停止")

    # ---- 访问 ----

    def get(self, name: str) -> BaseAgent:
        if name not in self._agents:
            raise KeyError(f"Agent 不存在: {name}")
        return self._agents[name]

    def all_agents(self) -> List[BaseAgent]:
        return list(self._agents.values())

    def summary(self) -> List[Dict[str, object]]:
        return [
            {
                "id": a.agent_id,
                "name": a.name,
                "role": a.role,
                "status": a.status.value,
                "workstation": a.workstation,
            }
            for a in self._agents.values()
        ]

    # ---- 心跳 ----

    async def _heartbeat_loop(self) -> None:
        while self._running:
            try:
                snapshot = []
                for agent in self._agents.values():
                    metrics = await agent.tick()
                    snapshot.append(
                        {
                            "id": agent.agent_id,
                            "name": agent.name,
                            "role": agent.role,
                            "status": agent.status.value,
                            "workstation": agent.workstation,
                            "metrics": metrics,
                            "ts": time.time(),
                        }
                    )
                await self.event_publisher.publish("agent_status", {"agents": snapshot})
            except Exception as exc:  # pragma: no cover
                logger.exception("心跳异常: %s", exc)
            await asyncio.sleep(self.HEARTBEAT_INTERVAL)


_scheduler: AgentScheduler | None = None


def get_agent_scheduler() -> AgentScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AgentScheduler()
    return _scheduler


def reset_agent_scheduler() -> None:  # pragma: no cover - 测试用
    global _scheduler
    _scheduler = None


# 类型别名，供调用方使用
ScheduleTask = Callable[[], Awaitable[None]]
