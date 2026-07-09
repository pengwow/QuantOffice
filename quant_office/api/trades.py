"""成交 API（与前端 Trade 形状对齐）。

真实流程：调 ``engine_adapter.submit_order``（axon 模式用 L1MatchingEngine 真撮合，
fallback 模式内存成交），结果写入 ``qo_trades`` 表。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from ..core.engine_adapter import (
    OrderRequest,
    Portfolio,
    get_engine_adapter,
)
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
    """提交一笔成交（真实调 engine_adapter.submit_order）。"""
    symbol = (body.get("symbol") or "BTCUSDT").upper()
    side = body.get("side", "buy")
    qty = float(body.get("qty") or body.get("quantity") or 0)
    price = body.get("price")
    if price is None:
        price = SYMBOL_PRICE.get(symbol, 100.0)
    price = float(price)
    order_type = body.get("order_type") or ("limit" if price else "market")
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

        # ---- 真实下单（先风控再撮合） ----
        engine = get_engine_adapter()
        portfolio = Portfolio(
            cash=100_000.0,
            positions={s.symbol: 1.0} if s.symbol else {},
        )
        req = OrderRequest(
            symbol=symbol,
            side=side,
            quantity=qty,
            order_type=order_type,
            price=price,
        )
        result = await engine.submit_order(req, portfolio)
        fill_price = float(result.filled_price or price)
        # 简化：买单 cost = qty*price，pnl = 0；卖单释放现金
        pnl = 0.0
        if result.status == "rejected":
            raise HTTPException(400, f"order rejected: {result.reason}")

        t = Trade(
            id=f"trade-{uuid.uuid4().hex[:10]}",
            strategy_id=strategy_id,
            order_id=result.order_id or f"order-{uuid.uuid4().hex[:10]}",
            symbol=symbol,
            side=side,
            qty=qty,
            price=fill_price,
            pnl=pnl,
            status=result.status,
            created_at=datetime.utcnow(),
        )
        session.add(t)
        await session.commit()
        await session.refresh(t)
        return trade_to_response(t)
