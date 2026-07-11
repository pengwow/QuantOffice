"""风控监控器 — 周期扫描所有 active 策略并触发告警。

由 ``AgentScheduler.start_all`` 拉起，由 ``AgentScheduler.stop_all`` 停止。
- 每 ``SCAN_INTERVAL`` 秒调一次 ``services.risk_service.run_full_risk_scan``
- 实时从 ``RuntimeConfigStore`` 读风险阈值 → 用户改完立即生效
- 通过 ``EventPublisher`` 推送 ``risk_alert_new`` 事件，WebSocket 广播
"""
from __future__ import annotations

import asyncio
from typing import Optional

from ..logging_config import get_logger
from .event_publisher import EventPublisher, get_event_publisher

logger = get_logger("core.risk_monitor")


class RiskMonitor:
    """周期风控扫描器。"""

    SCAN_INTERVAL = 5.0  # 秒

    def __init__(self, event_publisher: Optional[EventPublisher] = None) -> None:
        self.event_publisher = event_publisher or get_event_publisher()
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="risk-monitor")
        logger.info("RiskMonitor 已启动（间隔 %.1fs）", self.SCAN_INTERVAL)

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        logger.info("RiskMonitor 已停止")

    async def _loop(self) -> None:
        # lazy import 避开 services <-> core 循环
        from ..services.risk_service import run_full_risk_scan

        while self._running:
            try:
                alerts = await run_full_risk_scan(write=True)
                for a in alerts:
                    await self.event_publisher.publish("risk_alert_new", a)
            except asyncio.CancelledError:
                break
            except Exception as exc:  # pragma: no cover
                logger.exception("RiskMonitor 扫描异常: %s", exc)
            try:
                await asyncio.sleep(self.SCAN_INTERVAL)
            except asyncio.CancelledError:
                break


# ============================================================
# 全局单例
# ============================================================

_monitor: Optional[RiskMonitor] = None


def get_risk_monitor() -> RiskMonitor:
    global _monitor
    if _monitor is None:
        _monitor = RiskMonitor()
    return _monitor


def reset_risk_monitor() -> None:  # pragma: no cover - 测试用
    global _monitor
    _monitor = None
