"""回测 API（与前端 BacktestResult 形状对齐）。

真实流程：通过 ``engine_adapter`` 调 axon_quant.BacktestEngine + L1MatchingEngine
执行回测，结果入库。
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ..core.engine_adapter import get_engine_adapter
from ..data.database import get_session_factory
from ..data.models import Backtest, Strategy
from ..services.api_schemas import backtest_to_response

router = APIRouter(prefix="/backtests", tags=["backtests"])


def _curve_to_dict(curve: list, start: datetime, end: datetime) -> list[dict]:
    """把 equity_curve(float list) 转换为前端期望的 [{date, equity}, ...]。"""
    if not curve:
        return []
    n = len(curve)
    days = max((end - start).days, 1)
    out: list[dict] = []
    for i, equity in enumerate(curve):
        t = start + timedelta(seconds=int(days * 86400 * i / max(n - 1, 1)))
        out.append({
            "date": t.strftime("%Y-%m-%d"),
            "equity": round(float(equity), 2),
        })
    return out


@router.get("")
async def list_backtests() -> list[dict]:
    factory = get_session_factory()
    async with factory() as session:
        rows = (await session.scalars(select(Backtest).order_by(Backtest.created_at.desc()))).all()
    return [backtest_to_response(r) for r in rows]


@router.get("/{backtest_id}")
async def get_backtest(backtest_id: str) -> dict:
    factory = get_session_factory()
    async with factory() as session:
        b = await session.get(Backtest, backtest_id)
    if b is None:
        raise HTTPException(404, f"Backtest not found: {backtest_id}")
    return backtest_to_response(b)


@router.post("", status_code=201)
async def run_backtest(body: dict) -> dict:
    """启动一次回测。

    请求体：
      {
        "strategy_id": "strat-xxx",   // 必填
        "start": "2025-01-01",         // 可选，默认 1 年前
        "end":   "2025-12-31",         // 可选，默认今天
      }

    真实实现：调 ``engine_adapter.run_backtest(strategy_name)``，
    axon 模式用 axon_quant.BacktestEngine + L1MatchingEngine 真跑，
    fallback 模式用 SMA 动量策略合成演示数据。
    """
    strategy_id = body.get("strategy_id")
    if not strategy_id:
        raise HTTPException(422, "strategy_id is required")

    factory = get_session_factory()
    async with factory() as session:
        s = await session.get(Strategy, strategy_id)
        if s is None:
            raise HTTPException(404, f"Strategy not found: {strategy_id}")

        try:
            end_dt = datetime.fromisoformat(body["end"]) if body.get("end") else datetime.utcnow()
        except ValueError:
            raise HTTPException(422, f"Invalid end date: {body.get('end')}")
        try:
            start_dt = datetime.fromisoformat(body["start"]) if body.get("start") else end_dt - timedelta(days=180)
        except ValueError:
            raise HTTPException(422, f"Invalid start date: {body.get('start')}")
        if start_dt >= end_dt:
            raise HTTPException(422, "start must be before end")

        # ---- 真实回测 ----
        engine = get_engine_adapter()
        result = engine.run_backtest(strategy_name=s.name or strategy_id)

        bt = Backtest(
            id=f"bt-{uuid.uuid4().hex[:8]}",
            strategy_id=strategy_id,
            period_start=start_dt,
            period_end=end_dt,
            total_return=float(result.total_return or 0.0),
            annual_return=float(result.annual_return or 0.0),
            sharpe=float(result.sharpe_ratio or 0.0),
            max_drawdown=float(result.max_drawdown or 0.0),
            win_rate=float(result.win_rate or 0.0),
            trades=int(result.trades or 0),
            equity_curve=json.dumps(_curve_to_dict(result.equity_curve, start_dt, end_dt)),
            created_at=datetime.utcnow(),
        )
        session.add(bt)
        await session.commit()
        await session.refresh(bt)
        return backtest_to_response(bt)
