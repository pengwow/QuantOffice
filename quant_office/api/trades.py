"""成交 API（与前端 Trade 形状对齐）。"""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from ..data.database import get_session_factory
from ..data.models import Strategy, Trade
from ..services.api_schemas import trade_to_response

router = APIRouter(prefix="/trades", tags=["trades"])


SYMBOL_PRICE = {
    "BTCUSDT": 67000.0, "ETHUSDT": 3500.0, "SOLUSDT": 150.0,
    "DOGEUSDT": 0.18,   "BNBUSDT": 600.0,
}


@router.get("")
async def list_trades(limit: int = Query(200, ge=1, le=1000), symbol: str | None = None) -> list[dict]:
    factory = get_session_factory()
    async with factory() as session:
        stmt = select(Trade).order_by(Trade.created_at.desc()).limit(limit)
        if symbol:
            stmt = (
                select(Trade).where(Trade.symbol == symbol.upper())
                .order_by(Trade.created_at.desc()).limit(limit)
            )
        rows = (await session.scalars(stmt)).all()
    return [trade_to_response(r) for r in rows]


@router.get("/{trade_id}")
async def get_trade(trade_id: str) -> dict:
    factory = get_session_factory()
    async with factory() as session:
        t = await session.get(Trade, trade_id)
    if t is None:
        raise HTTPException(404, f"Trade not found: {trade_id}")
    return trade_to_response(t)


@router.post("", status_code=201)
async def submit_trade(body: dict) -> dict:
    """提交一笔模拟成交（演示用：随机 pnl + 状态）。"""
    symbol = (body.get("symbol") or "BTCUSDT").upper()
    side = body.get("side", "buy")
    qty = float(body.get("qty") or body.get("quantity") or 0)
    price = float(body.get("price") or SYMBOL_PRICE.get(symbol, 100.0))
    strategy_id = body.get("strategy_id") or "strat-momentum-btc"

    if side not in ("buy", "sell"):
        raise HTTPException(422, "side must be buy or sell")
    if qty <= 0:
        raise HTTPException(422, "qty must be > 0")

    factory = get_session_factory()
    async with factory() as session:
        s = await session.get(Strategy, strategy_id)
        if s is None:
            raise HTTPException(404, f"Strategy not found: {strategy_id}")
        random.seed(uuid.uuid4().int % 100000)
        pnl = round(random.gauss(50, 80), 2)
        status = random.choices(["filled", "filled", "filled", "submitted"], k=1)[0]
        t = Trade(
            id=f"trade-{uuid.uuid4().hex[:10]}",
            strategy_id=strategy_id,
            order_id=f"order-{uuid.uuid4().hex[:10]}",
            symbol=symbol,
            side=side,
            qty=qty,
            price=price,
            pnl=pnl,
            status=status,
            created_at=datetime.utcnow(),
        )
        session.add(t)
        await session.commit()
        await session.refresh(t)
        return trade_to_response(t)
