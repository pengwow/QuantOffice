"""API 路由集合 — 独立模式与插件模式 100% 复用。"""
from . import agents, backtests, chat, dashboard, reports, risk, settings, strategies, trades

__all__ = [
    "agents",
    "backtests",
    "chat",
    "dashboard",
    "reports",
    "risk",
    "settings",
    "strategies",
    "trades",
]
