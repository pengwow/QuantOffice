"""API 响应转换层 — 将 ORM 实体映射为前端期望的 JSON 形状。

为什么需要这层？
  - 前端 [frontend/src/types/index.ts](file:///workspace/frontend/src/types/index.ts) 期望的字段
    （如 Agent 的 emoji/color/position/metrics、Trade 的 pnl/strategy_id 等）
    并非 ORM 直接存储的字段，需要根据 role 映射、计算、合成。
  - 同时为前端/插件模式提供统一的响应序列化。
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

# ============================================================
# Agent 元数据（与前端 lib/agentMeta.ts 完全一致）
# ============================================================
AGENT_META: dict[str, dict[str, Any]] = {
    "chief":     {"name": "首席交易员",   "emoji": "🎩", "color": "#00b894", "position": {"x": 640, "y": 360}},
    "data":      {"name": "数据分析师",   "emoji": "📊", "color": "#74b9ff", "position": {"x": 240, "y": 360}},
    "strategy":  {"name": "策略研究员",   "emoji": "📈", "color": "#e17055", "position": {"x": 360, "y": 520}},
    "risk":      {"name": "风控官",       "emoji": "🛡️", "color": "#ff7675", "position": {"x": 920, "y": 520}},
    "execution": {"name": "执行交易员",   "emoji": "⚡", "color": "#a29bfe", "position": {"x": 1040, "y": 360}},
    "report":    {"name": "报告专员",     "emoji": "📝", "color": "#fdcb6e", "position": {"x": 640, "y": 600}},
}

AGENT_ROLES = ["chief", "data", "strategy", "risk", "execution", "report"]

# 后端 role 枚举（PascalCase）→ 前端 role 枚举（lowercase）
BACKEND_TO_FRONT_ROLE: dict[str, str] = {
    "ChiefTrader":   "chief",
    "DataAgent":     "data",
    "StrategyAgent": "strategy",
    "RiskAgent":     "risk",
    "ExecutionAgent":"execution",
    "ReportAgent":   "report",
}

# 后端 AgentStatus 枚举 → 前端 status 枚举
BACKEND_TO_FRONT_STATUS: dict[str, str] = {
    "idle":    "idle",
    "working": "busy",
    "alert":   "warning",
    "error":   "error",
    "stopped": "idle",
}


# ============================================================
# Agent
# ============================================================
def agent_to_response(agent_summary: dict[str, Any], live_metrics: dict[str, Any] | None = None) -> dict[str, Any]:
    """把 scheduler.summary() 的输出转换为前端期望的 Agent 形状。"""
    role = agent_summary.get("role", "")
    front_role = BACKEND_TO_FRONT_ROLE.get(role, role.lower())
    meta = AGENT_META.get(front_role, {})
    status = BACKEND_TO_FRONT_STATUS.get(agent_summary.get("status", "idle"), "idle")

    return {
        "id": agent_summary.get("id", front_role),
        "role": front_role,
        "name": meta.get("name", agent_summary.get("name", role)),
        "emoji": meta.get("emoji", "🤖"),
        "color": meta.get("color", "#b2bec3"),
        "position": meta.get("position", {"x": 640, "y": 360}),
        "status": status,
        "metrics": live_metrics or {},
        "current_task": agent_summary.get("current_task"),
        "updated_at": _iso(agent_summary.get("ts")),
    }


# ============================================================
# Strategy
# ============================================================
def strategy_to_response(s) -> dict[str, Any]:
    """ORM Strategy → 前端 Strategy。"""
    try:
        params = json.loads(s.params or "{}")
    except (TypeError, json.JSONDecodeError):
        params = {}
    return {
        "id": s.id,
        "name": s.name,
        "symbol": s.symbol,
        "status": s.status,
        "params": params,
        "pnl": float(s.pnl or 0.0),
        "sharpe": float(s.sharpe or 0.0),
        "drawdown": float(s.drawdown or 0.0),
        "created_at": _iso(s.created_at),
        "updated_at": _iso(s.updated_at),
    }


# ============================================================
# Backtest
# ============================================================
def backtest_to_response(b) -> dict[str, Any]:
    try:
        curve = json.loads(b.equity_curve or "[]")
    except (TypeError, json.JSONDecodeError):
        curve = []
    return {
        "id": b.id,
        "strategy_id": b.strategy_id,
        "period": {
            "start": b.period_start.strftime("%Y-%m-%d") if b.period_start else "",
            "end":   b.period_end.strftime("%Y-%m-%d") if b.period_end else "",
        },
        "total_return": float(b.total_return or 0.0),
        "annual_return": float(b.annual_return or 0.0),
        "sharpe": float(b.sharpe or 0.0),
        "max_drawdown": float(b.max_drawdown or 0.0),
        "win_rate": float(b.win_rate or 0.0),
        "trades": int(b.trades or 0),
        "equity_curve": curve,
        "created_at": _iso(b.created_at),
    }


# ============================================================
# Trade
# ============================================================
def trade_to_response(t) -> dict[str, Any]:
    return {
        "id": t.id,
        "strategy_id": t.strategy_id,
        "order_id": t.order_id,
        "symbol": t.symbol,
        "side": t.side,
        "qty": float(t.qty or 0.0),
        "price": float(t.price or 0.0),
        "pnl": float(t.pnl or 0.0),
        "status": t.status,
        "created_at": _iso(t.created_at),
    }


# ============================================================
# Risk Alert
# ============================================================
def alert_to_response(a) -> dict[str, Any]:
    return {
        "id": a.id,
        "level": a.level,
        "rule": a.rule,
        "message": a.message,
        "symbol": a.symbol or None,
        "metric": a.metric or None,
        "value": float(a.value or 0.0) if a.value is not None else None,
        "threshold": float(a.threshold or 0.0) if a.threshold is not None else None,
        "acknowledged": bool(a.acknowledged),
        "created_at": _iso(a.created_at),
    }


# ============================================================
# Report
# ============================================================
def report_to_response(r) -> dict[str, Any]:
    try:
        sections = json.loads(r.sections or "[]")
    except (TypeError, json.JSONDecodeError):
        sections = []
    return {
        "id": r.id,
        "title": r.title,
        "period": {
            "start": r.period_start.strftime("%Y-%m-%d") if r.period_start else "",
            "end":   r.period_end.strftime("%Y-%m-%d") if r.period_end else "",
        },
        "summary": r.summary or "",
        "sections": sections,
        "created_at": _iso(r.created_at),
    }


# ============================================================
# helpers
# ============================================================
def _iso(value: Any) -> str:
    if value is None:
        return datetime.utcnow().isoformat()
    if isinstance(value, datetime):
        return value.replace(microsecond=0).isoformat()
    if isinstance(value, (int, float)):
        return datetime.utcfromtimestamp(value).replace(microsecond=0).isoformat()
    return str(value)
