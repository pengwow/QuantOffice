"""总览仪表盘 API — 返回 DashboardSummary 形状。"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from fastapi import APIRouter
from sqlalchemy import select

from ..core.agent_scheduler import get_agent_scheduler
from ..data.database import get_session_factory
from ..data.models import Backtest, Report, RiskAlert, Strategy, Trade
from ..services.api_schemas import (
    AGENT_META,
    AGENT_ROLES,
    agent_to_response,
    alert_to_response,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
async def dashboard() -> dict:
    """聚合 Dashboard 所需的所有数据。

    一次查询所有表，再在内存里聚合，避免 N+1。
    """
    scheduler = get_agent_scheduler()
    factory = get_session_factory()
    async with factory() as session:
        trades    = (await session.scalars(select(Trade).order_by(Trade.created_at.desc()))).all()
        backtests = (await session.scalars(select(Backtest).order_by(Backtest.created_at.desc()))).all()
        alerts    = (await session.scalars(select(RiskAlert).order_by(RiskAlert.created_at.desc()).limit(5))).all()
        reports   = (await session.scalars(select(Report).order_by(Report.created_at.desc()).limit(1))).all()
        strategies = (await session.scalars(select(Strategy))).all()

    # ===== Agent 列表 =====
    agent_summaries = {a["id"]: a for a in scheduler.summary()}
    agents_out = []
    for role in AGENT_ROLES:
        meta = AGENT_META[role]
        s = agent_summaries.get(role) or {"id": role, "name": meta["name"], "role": role, "status": "stopped"}
        agents_out.append(agent_to_response(s))

    # ===== 指标 =====
    total_pnl = sum(float(t.pnl or 0) for t in trades)
    cutoff = datetime.utcnow() - timedelta(hours=24)
    daily_pnl = sum(
        float(t.pnl or 0) for t in trades
        if t.created_at and t.created_at >= cutoff
    )
    win = sum(1 for t in trades if t.pnl > 0)
    win_rate = win / max(len(trades), 1)

    active_alerts = [a for a in alerts if not a.acknowledged]
    last_bt = backtests[0] if backtests else None

    # ===== 权益曲线 =====
    equity_curve: list[dict] = []
    if last_bt and last_bt.equity_curve:
        try:
            equity_curve = json.loads(last_bt.equity_curve)
        except (TypeError, json.JSONDecodeError):
            equity_curve = []

    return {
        "total_pnl": round(total_pnl, 2),
        "daily_pnl": round(daily_pnl, 2),
        "total_strategies": len(strategies),
        "active_strategies": sum(1 for s in strategies if s.status == "live"),
        "total_trades": len(trades),
        "win_rate": round(win_rate, 4),
        "sharpe": float(last_bt.sharpe) if last_bt else 0.0,
        "drawdown": float(last_bt.max_drawdown) if last_bt else 0.0,
        "agents": agents_out,
        "recent_alerts": [alert_to_response(a) for a in active_alerts[:5]],
        "equity_curve": equity_curve,
        "total_backtests": len(backtests),
        "total_alerts": len(alerts),
        "total_reports": len(reports),
    }
