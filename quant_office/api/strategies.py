"""策略管理 API（与前端 Strategy 形状对齐）。"""
from __future__ import annotations

import json
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ..data.database import get_session_factory
from ..data.models import Strategy
from ..services.api_schemas import strategy_to_response

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("")
async def list_strategies() -> list[dict]:
    factory = get_session_factory()
    async with factory() as session:
        rows = (await session.scalars(select(Strategy).order_by(Strategy.created_at.desc()))).all()
    return [strategy_to_response(r) for r in rows]


@router.post("", status_code=201)
async def create_strategy(body: dict) -> dict:
    if not body.get("name"):
        raise HTTPException(422, "name is required")
    sid = body.get("id") or f"strat-{uuid.uuid4().hex[:8]}"
    factory = get_session_factory()
    async with factory() as session:
        # 唯一性检查
        if await session.get(Strategy, sid):
            raise HTTPException(409, f"Strategy exists: {sid}")
        s = Strategy(
            id=sid,
            name=body["name"],
            description=body.get("description", ""),
            symbol=body.get("symbol", "BTCUSDT"),
            params=json.dumps(body.get("params", {})),
            status=body.get("status", "draft"),
            pnl=0.0,
            sharpe=0.0,
            drawdown=0.0,
        )
        session.add(s)
        await session.commit()
        await session.refresh(s)
        return strategy_to_response(s)


@router.get("/{strategy_id}")
async def get_strategy(strategy_id: str) -> dict:
    factory = get_session_factory()
    async with factory() as session:
        s = await session.get(Strategy, strategy_id)
    if s is None:
        raise HTTPException(404, f"Strategy not found: {strategy_id}")
    return strategy_to_response(s)


@router.put("/{strategy_id}")
async def update_strategy(strategy_id: str, body: dict) -> dict:
    factory = get_session_factory()
    async with factory() as session:
        s = await session.get(Strategy, strategy_id)
        if s is None:
            raise HTTPException(404, f"Strategy not found: {strategy_id}")
        if "name" in body:
            s.name = body["name"]
        if "description" in body:
            s.description = body["description"]
        if "symbol" in body:
            s.symbol = body["symbol"]
        if "params" in body:
            s.params = json.dumps(body["params"])
        if "status" in body:
            if body["status"] not in ("draft", "live", "paused", "stopped"):
                raise HTTPException(422, f"Invalid status: {body['status']}")
            s.status = body["status"]
        s.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(s)
        return strategy_to_response(s)


@router.delete("/{strategy_id}", status_code=204)
async def delete_strategy(strategy_id: str):
    factory = get_session_factory()
    async with factory() as session:
        s = await session.get(Strategy, strategy_id)
        if s is None:
            raise HTTPException(404, f"Strategy not found: {strategy_id}")
        await session.delete(s)
        await session.commit()
        return None
