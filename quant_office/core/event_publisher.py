"""事件发布器 — 兼容 QuantCell EventBus 的统一事件层。

- 独立模式：内部异步事件循环 + WebSocket 广播
- 插件模式：把事件转发到 QuantCell 宿主 EventBus
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, Awaitable, Callable, Dict, List, Set

from .websocket_manager import WebSocketManager, get_websocket_manager

EventHandler = Callable[[Dict[str, Any]], Awaitable[None]]


class EventPublisher:
    """进程内异步事件发布器。"""

    def __init__(self, ws_manager: WebSocketManager | None = None) -> None:
        self._handlers: Dict[str, List[EventHandler]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self.ws_manager = ws_manager or get_websocket_manager()

    # ---- 订阅 ----

    def subscribe(self, event: str, handler: EventHandler) -> None:
        self._handlers[event].append(handler)

    def unsubscribe(self, event: str, handler: EventHandler) -> None:
        if event in self._handlers and handler in self._handlers[event]:
            self._handlers[event].remove(handler)

    # ---- 发布 ----

    async def publish(self, event: str, payload: Dict[str, Any]) -> None:
        # WebSocket 广播
        await self.ws_manager.publish(event, payload)
        # 内部 handler 调用
        handlers: List[EventHandler] = list(self._handlers.get(event, []))
        for handler in handlers:
            try:
                await handler(payload)
            except Exception as exc:  # pragma: no cover
                from ..logging_config import get_logger
                get_logger("core.event").exception("Handler 异常 [%s]: %s", event, exc)

    # ---- 主题列表 ----

    @property
    def topics(self) -> Set[str]:
        return set(self._handlers.keys())


_publisher: EventPublisher | None = None


def get_event_publisher() -> EventPublisher:
    global _publisher
    if _publisher is None:
        _publisher = EventPublisher()
    return _publisher


def reset_event_publisher() -> None:  # pragma: no cover - 测试用
    global _publisher
    _publisher = None
