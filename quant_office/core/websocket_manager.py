"""WebSocket 管理器 — 实时推送 Agent 状态、行情、风控事件。

支持：
- 频道订阅（``market_data``、``agent_status``、``trade_execution``、``risk_alert``）
- 多客户端广播
- 异步发布/订阅
"""
from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any, Dict, Iterable, Set

from fastapi import WebSocket, WebSocketDisconnect

from ..logging_config import get_logger

logger = get_logger("core.ws")


class WebSocketManager:
    """轻量级 WebSocket 管理器。"""

    def __init__(self) -> None:
        self._connections: Set[WebSocket] = set()
        self._subscriptions: Dict[WebSocket, Set[str]] = defaultdict(set)
        self._lock = asyncio.Lock()

    # ---- 连接管理 ----

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.add(ws)
            self._subscriptions[ws] = set()
        logger.info("WS 连接建立，当前连接数: %d", len(self._connections))

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(ws)
            self._subscriptions.pop(ws, None)
        logger.info("WS 连接断开，当前连接数: %d", len(self._connections))

    async def handle_ws(self, ws: WebSocket) -> None:
        """FastAPI WebSocket 端点入口。"""
        await self.connect(ws)
        try:
            while True:
                msg = await ws.receive_text()
                await self._on_client_message(ws, msg)
        except WebSocketDisconnect:
            pass
        except Exception as exc:  # pragma: no cover
            logger.exception("WS 处理异常: %s", exc)
        finally:
            await self.disconnect(ws)

    # ---- 订阅 ----

    async def _on_client_message(self, ws: WebSocket, raw: str) -> None:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            await ws.send_text(json.dumps({"type": "error", "message": "invalid json"}))
            return
        msg_type = data.get("type")
        if msg_type == "subscribe":
            channels = data.get("channels", [])
            if isinstance(channels, str):
                channels = [channels]
            async with self._lock:
                self._subscriptions[ws].update(channels)
            await ws.send_text(
                json.dumps({"type": "subscribed", "channels": list(channels)})
            )
        elif msg_type == "unsubscribe":
            channels: Iterable[str] = data.get("channels", [])
            async with self._lock:
                for ch in channels:
                    self._subscriptions[ws].discard(ch)
            await ws.send_text(
                json.dumps({"type": "unsubscribed", "channels": list(channels)})
            )
        elif msg_type == "ping":
            await ws.send_text(json.dumps({"type": "pong", "ts": data.get("ts")}))

    # ---- 广播 ----

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """向所有连接广播。"""
        if not self._connections:
            return
        payload = json.dumps(message, default=str)
        dead: list[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)

    async def publish(self, channel: str, payload: Dict[str, Any]) -> None:
        """向订阅了 ``channel`` 的连接发送。"""
        if not self._connections:
            return
        message = {"type": channel, "payload": payload}
        data = json.dumps(message, default=str)
        dead: list[WebSocket] = []
        for ws, channels in list(self._subscriptions.items()):
            if channel in channels or "*" in channels:
                try:
                    await ws.send_text(data)
                except Exception:
                    dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)

    # ---- 状态 ----

    @property
    def connection_count(self) -> int:
        return len(self._connections)


_manager: WebSocketManager | None = None


def get_websocket_manager() -> WebSocketManager:
    global _manager
    if _manager is None:
        _manager = WebSocketManager()
    return _manager


def reset_websocket_manager() -> None:  # pragma: no cover - 测试用
    global _manager
    _manager = None
