"""交易执行 API。"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from ..core.agent_scheduler import get_agent_scheduler

router = APIRouter(prefix="/trades", tags=["trades"])


@router.get("/")
async def list_trades() -> Dict[str, Any]:
    res = await get_agent_scheduler().get("execution").handle("list_orders")
    return res.get("result", {})


@router.post("/")
async def place_order(body: Dict[str, Any]) -> Dict[str, Any]:
    res = await get_agent_scheduler().get("execution").handle("place_order", body)
    return res.get("result", {})


@router.post("/{order_id}/cancel")
async def cancel_order(order_id: str) -> Dict[str, Any]:
    res = await get_agent_scheduler().get("execution").handle("cancel_order", {"order_id": order_id})
    return res.get("result", {})
