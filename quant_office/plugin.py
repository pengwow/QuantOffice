"""QuantCell 插件模式入口。

设计原则：
1. ``core/``、``agents/``、``api/``、``data/``、``services/`` 业务代码 100% 复用；
2. 本文件仅提供：
   - 插件生命周期（``register / start / stop / on_enable / on_disable``）
   - 路由前缀适配（``/api/plugins/quant-office``）
   - EventBus 桥接（订阅其他插件事件）
   - 插件数据目录隔离
3. 兼容两种宿主：
   - 真实 QuantCell ``plugins.plugin_base.PluginBase``
   - 本地 ``_StubPluginBase``（用于无宿主调试）
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter

from . import __version__
from .api import agents, backtests, chat, dashboard, reports, risk, strategies, trades
from .api import settings as settings_api
from .config import settings
from .core.agent_scheduler import get_agent_scheduler
from .core.engine_adapter import get_engine_adapter
from .core.event_publisher import get_event_publisher
from .core.websocket_manager import get_websocket_manager
from .data.database import init_database
from .logging_config import get_logger, setup_logging

# ---- 宿主 PluginBase 适配 ----

try:  # pragma: no cover - 依赖外部宿主
    from plugins.plugin_base import PluginBase  # type: ignore
except Exception:  # 提供最小 stub，保证无宿主时也可调试

    class PluginBase:  # type: ignore[no-redef]
        """QuantCell ``PluginBase`` 的最小兼容实现。"""

        def __init__(self, name: str, version: str = "0.0.0") -> None:
            self.name = name
            self.version = version
            self.load_type = "cold"
            self.description = ""
            self.author = ""
            self.frontend_entry: Optional[str] = None
            self.logger = get_logger(f"plugin.{name}")

        # 生命周期钩子 — 子类按需覆盖
        def register(self, plugin_manager: Any) -> None:  # noqa: D401
            return None

        def start(self) -> None:
            return None

        def stop(self) -> None:
            return None

        def on_enable(self) -> None:
            return None

        def on_disable(self) -> None:
            return None

        def get_config_schema(self) -> Dict[str, Any]:
            return {"type": "object", "properties": {}}


setup_logging(level=settings.log_level)


class QuantOfficePlugin(PluginBase):
    """QuantOffice 插件 — QuantCell 集成入口。"""

    PLUGIN_PREFIX = "/api/plugins/quant-office"

    def __init__(self) -> None:
        super().__init__("quant-office", __version__)
        self.load_type = "hot"
        self.description = (
            "QuantOffice — 量化交易指挥中枢：1+5 Agent 协作、策略回测、风控监控与可视化交易执行"
        )
        self.author = "QuantOffice Team"
        self.frontend_entry = "/index.js"

        # 插件数据目录隔离
        self._plugin_data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
        )
        os.makedirs(self._plugin_data_dir, exist_ok=True)

        # 初始化数据库 + 业务组件
        settings.mode = "plugin"
        settings.data_dir = self._plugin_data_dir
        init_database()

        self.ws_manager = get_websocket_manager()
        self.event_publisher = get_event_publisher()
        self.engine = get_engine_adapter()

        # 路由（带插件前缀）
        self.router = APIRouter(prefix=self.PLUGIN_PREFIX)
        self._setup_routes()
        self._setup_websocket()
        self._setup_event_bridge()

    # ---- 路由 ----

    def _setup_routes(self) -> None:
        self.router.include_router(agents.router)
        self.router.include_router(strategies.router)
        self.router.include_router(backtests.router)
        self.router.include_router(trades.router)
        self.router.include_router(risk.router)
        self.router.include_router(reports.router)
        self.router.include_router(dashboard.router)
        self.router.include_router(settings_api.router)
        self.router.include_router(chat.router)

        @self.router.get("/health")
        async def _health() -> Dict[str, Any]:
            return {
                "status": "ok",
                "plugin": self.name,
                "version": self.version,
                "mode": "plugin",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        @self.router.get("/")
        async def _root() -> Dict[str, Any]:
            return {
                "name": "QuantOffice",
                "version": self.version,
                "mode": "plugin",
                "agents": ["chief", "data", "strategy", "risk", "execution", "report"],
                "websocket": f"{self.PLUGIN_PREFIX}/ws",
            }

        @self.router.post("/demo/reset", status_code=200)
        async def _demo_reset() -> Dict[str, Any]:
            from .demo import reset_and_seed
            return {"ok": True, "seeded": await reset_and_seed()}

        @self.router.post("/demo/seed", status_code=200)
        async def _demo_seed() -> Dict[str, Any]:
            from .demo import seed_if_empty
            return {"ok": True, "seeded": await seed_if_empty()}

    def _setup_websocket(self) -> None:
        self.router.add_api_websocket_route("/ws", self.ws_manager.handle_ws)

    # ---- 事件桥接 ----

    def _setup_event_bridge(self) -> None:
        # 订阅其他插件可能发布的行情/信号事件，转发到本插件 WS
        self.event_publisher.subscribe("market_data", self._on_external_market)
        self.event_publisher.subscribe("trade_signal", self._on_external_signal)

    async def _on_external_market(self, payload: Dict[str, Any]) -> None:
        await self.ws_manager.publish("market_data", payload)

    async def _on_external_signal(self, payload: Dict[str, Any]) -> None:
        await self.ws_manager.publish("trade_signal", payload)

    # ---- 生命周期 ----

    def register(self, plugin_manager: Any) -> None:
        super().register(plugin_manager)
        self.logger.info("QuantOffice 插件已注册 (版本 %s)", self.version)

    def start(self) -> None:
        super().start()
        # 启动 Agent 调度
        self._scheduler = get_agent_scheduler()
        try:
            import asyncio

            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            if loop.is_running():
                loop.create_task(self._scheduler.start_all())
                loop.create_task(self._seed_demo())
            else:
                loop.run_until_complete(self._scheduler.start_all())
                loop.run_until_complete(self._seed_demo())
        except Exception as exc:  # pragma: no cover
            self.logger.exception("AgentScheduler 启动失败: %s", exc)
        self.logger.info("QuantOffice 插件已启动")

    async def _seed_demo(self) -> None:
        try:
            from .demo import seed_if_empty
            counts = await seed_if_empty()
            if any(counts.values()):
                self.logger.info("插件演示数据已注入：%s", counts)
        except Exception as exc:  # pragma: no cover
            self.logger.exception("插件演示数据播种失败: %s", exc)

    def stop(self) -> None:
        super().stop()
        if hasattr(self, "_scheduler"):
            try:
                import asyncio

                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                if loop.is_running():
                    loop.create_task(self._scheduler.stop_all())
                else:
                    loop.run_until_complete(self._scheduler.stop_all())
            except Exception as exc:  # pragma: no cover
                self.logger.exception("AgentScheduler 停止失败: %s", exc)
        self.logger.info("QuantOffice 插件已停止")

    def on_enable(self) -> None:
        super().on_enable()
        self.logger.info("QuantOffice 插件已启用")

    def on_disable(self) -> None:
        super().on_disable()
        self.logger.info("QuantOffice 插件已禁用")

    # ---- 配置 ----

    def get_config_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "axon_quant_config": {
                    "type": "string",
                    "title": "axon_quant 引擎配置文件路径",
                    "default": "./config/quant.yaml",
                },
                "default_exchange": {
                    "type": "string",
                    "title": "默认交易所",
                    "enum": ["binance", "okx", "bybit"],
                    "default": "binance",
                },
                "risk_max_drawdown": {
                    "type": "number",
                    "title": "最大回撤阈值 (%)",
                    "default": 5.0,
                    "minimum": 0.1,
                    "maximum": 50.0,
                },
                "render_fps": {
                    "type": "integer",
                    "title": "前端渲染帧率",
                    "default": 30,
                    "minimum": 15,
                    "maximum": 60,
                },
            },
        }


def register_plugin() -> QuantOfficePlugin:
    """QuantCell 插件系统约定入口。"""
    return QuantOfficePlugin()
