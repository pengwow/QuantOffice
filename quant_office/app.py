"""独立运行模式 — 完整 FastAPI 应用工厂。

两种模式共享 100% 业务代码（``core/``、``agents/``、``api/``、``data/``、``services/``），
本文件仅负责：
- CORS / 中间件
- 数据库初始化
- 路由前缀（``/api``）
- WebSocket 端点（``/ws``）
- 静态资源（Godot WASM + 前端构建产物）
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api import agents, backtests, chat, dashboard, reports, risk, strategies, trades
from .api import settings as settings_api
from .config import settings
from .core.agent_scheduler import get_agent_scheduler
from .core.engine_adapter import get_engine_adapter
from .core.websocket_manager import get_websocket_manager
from .data.database import init_database
from .logging_config import get_logger, setup_logging

setup_logging(level=settings.log_level)
logger = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """启动 / 关闭钩子。"""
    settings.resolved_data_dir.mkdir(parents=True, exist_ok=True)
    init_database()
    # 显式建表（确保在有 running loop 的 lifespan 场景下也完成）
    from .data.database import create_all_tables
    await create_all_tables()
    scheduler = get_agent_scheduler()
    await scheduler.start_all()
    # 首次启动自动播种演示数据（数据库为空时）
    try:
        from .demo import seed_if_empty
        counts = await seed_if_empty()
        if any(counts.values()):
            logger.info("演示数据已注入：%s", counts)
    except Exception as exc:  # pragma: no cover
        logger.exception("演示数据播种失败: %s", exc)
    logger.info("QuantOffice 启动完成，模式=standalone 版本=%s", __version__)
    try:
        yield
    finally:
        await scheduler.stop_all()
        logger.info("QuantOffice 已关闭")


def create_app() -> FastAPI:
    settings.mode = "standalone"
    # 关闭 trailing-slash 307 重定向（前端不带斜杠，必须直接 200）
    app = FastAPI(
        title="QuantOffice",
        description="QuantOffice — 量化交易指挥中枢：1+5 Agent 协作、策略回测、风控监控与可视化交易执行",
        version=__version__,
        lifespan=lifespan,
        redirect_slashes=False,
    )

    # ---- CORS ----
    origins = [o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()] or ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---- 全局对象挂载 ----
    app.state.settings = settings
    app.state.ws_manager = get_websocket_manager()
    app.state.engine = get_engine_adapter()

    # ---- API 路由 ----
    api_prefix = "/api"
    app.include_router(agents.router, prefix=api_prefix)
    app.include_router(strategies.router, prefix=api_prefix)
    app.include_router(backtests.router, prefix=api_prefix)
    app.include_router(trades.router, prefix=api_prefix)
    app.include_router(risk.router, prefix=api_prefix)
    app.include_router(reports.router, prefix=api_prefix)
    app.include_router(dashboard.router, prefix=api_prefix)
    app.include_router(settings_api.router, prefix=api_prefix)
    app.include_router(chat.router, prefix=api_prefix)

    # ---- WebSocket ----
    @app.websocket("/ws")
    async def ws_endpoint(ws):  # noqa: ANN001
        await app.state.ws_manager.handle_ws(ws)

    # ---- 系统路由 ----
    @app.get("/api/")
    async def root() -> dict:
        return {
            "name": "QuantOffice",
            "version": __version__,
            "mode": "standalone",
            "agents": ["chief", "data", "strategy", "risk", "execution", "report"],
            "docs": "/docs",
            "websocket": "/ws",
        }

    @app.get("/api/health")
    async def health() -> dict:
        return {
            "status": "ok",
            "version": __version__,
            "mode": "standalone",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @app.get("/api/info")
    async def info() -> dict:
        engine = app.state.engine
        return {
            "name": "QuantOffice",
            "version": __version__,
            "mode": "standalone",
            "axon_quant_enabled": engine.using_axon,
            "agents": ["chief", "data", "strategy", "risk", "execution", "report"],
            "config": {
                "render_fps": settings.render_fps,
                "default_exchange": settings.default_exchange,
                "risk_max_drawdown": settings.risk_max_drawdown,
            },
        }

    # ---- 演示数据管理 ----
    @app.post("/api/demo/reset", status_code=200)
    async def demo_reset() -> dict:
        """清空并重新注入演示数据（用于演示重置）。"""
        from .demo import reset_and_seed
        counts = await reset_and_seed()
        return {"ok": True, "seeded": counts}

    @app.post("/api/demo/seed", status_code=200)
    async def demo_seed() -> dict:
        """仅在空库时注入（启动时已自动调用）。"""
        from .demo import seed_if_empty
        counts = await seed_if_empty()
        return {"ok": True, "seeded": counts}

    # ---- 静态资源（前端 Vite 构建产物） ----
    static_dir = settings.resolved_static_dir
    if static_dir.exists():
        # 挂载 /assets 子目录（Vite 构建产物）
        assets_dir = static_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
        # 根路径直接提供 index.html
        @app.get("/")
        async def index() -> FileResponse:
            return FileResponse(static_dir / "index.html")

        # SPA 兜底：所有非 /api /assets /ws 路径都返回 index.html
        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str) -> FileResponse:
            # 安全检查：路径里不能有 .. （防止越权）
            if ".." in full_path or full_path.startswith("api") or full_path.startswith("ws"):
                raise HTTPException(404, "Not Found")
            target = static_dir / full_path
            if target.is_file():
                return FileResponse(target)
            return FileResponse(static_dir / "index.html")
    else:
        @app.get("/")
        async def index() -> JSONResponse:
            return JSONResponse(
                {
                    "name": "QuantOffice",
                    "version": __version__,
                    "ui_hint": "前端尚未构建（quant_office/static/ 不存在），请访问 /docs 查看 API",
                }
            )

    return app


app = create_app()
