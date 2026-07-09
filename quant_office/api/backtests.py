"""回测 API（与前端 BacktestResult 形状对齐）。"""
from __future__ import annotations

import json
import math
import random
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ..data.database import get_session_factory
from ..data.models import Backtest, Strategy
from ..services.api_schemas import backtest_to_response

router = APIRouter(prefix="/backtests", tags=["backtests"])


def _gen_equity_curve(start: datetime, end: datetime, total_return: float) -> list[dict]:
    random.seed(total_return * 1000)
    days = max((end - start).days, 7)
    n = min(days, 90)
    drift = total_return / n
    pts: list[dict] = []
    for i in range(n + 1):
        t = start + timedelta(days=int(days * i / n))
        shock = random.gauss(0, 0.012)
        equity = 100_000.0 * (1 + drift * i + shock * math.sqrt(i + 1) * 0.4)
        pts.append({"date": t.strftime("%Y-%m-%d"), "equity": round(equity, 2)})
    pts[-1]["equity"] = round(100_000.0 * (1 + total_return), 2)
    return pts


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
    """
    strategy_id = body.get("strategy_id")
    if not strategy_id:
        raise HTTPException(422, "strategy_id is required")

    factory = get_session_factory()
    async with factory() as session:
        s = await session.get(Strategy, strategy_id)
        if s is None:
            raise HTTPException(404, f"Strategy not found: {strategy_id}")

        # 解析回测区间
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

        # 合成回测结果（演示用，真实环境接 axon_quant）
        random.seed(uuid.uuid4().int % 100000)
        total_return = round(random.uniform(0.05, 0.85), 4)
        days = max((end_dt - start_dt).days, 1)
        annual = round(total_return * (365 / days), 4)
        sharpe = round(random.uniform(0.8, 2.2), 2)
        max_dd = round(random.uniform(0.05, 0.25), 4)
        win = round(random.uniform(0.42, 0.68), 4)
        n_trades = random.randint(45, 280)

        bt = Backtest(
            id=f"bt-{uuid.uuid4().hex[:8]}",
            strategy_id=strategy_id,
            period_start=start_dt,
            period_end=end_dt,
            total_return=total_return,
            annual_return=annual,
            sharpe=sharpe,
            max_drawdown=max_dd,
            win_rate=win,
            trades=n_trades,
            equity_curve=json.dumps(_gen_equity_curve(start_dt, end_dt, total_return)),
            created_at=datetime.utcnow(),
        )
        session.add(bt)
        await session.commit()
        await session.refresh(bt)
        return backtest_to_response(bt)
