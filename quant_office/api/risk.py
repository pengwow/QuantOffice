"""风控相关 API。"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from ..core.agent_scheduler import get_agent_scheduler

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/metrics")
async def get_metrics() -> Dict[str, Any]:
    res = await get_agent_scheduler().get("risk").handle("get_risk_metrics")
    return res.get("result", {})


@router.post("/check")
async def check(body: Dict[str, Any]) -> Dict[str, Any]:
    res = await get_agent_scheduler().get("risk").handle("check_risk", body)
    return res.get("result", {})


@router.get("/alerts")
async def alerts(limit: int = 20) -> Dict[str, Any]:
    agent = get_agent_scheduler().get("risk")
    return {"alerts": agent.recent_alerts(limit=limit)}


@router.post("/circuit/reset")
async def reset_circuit() -> Dict[str, Any]:
    res = await get_agent_scheduler().get("risk").handle("reset_circuit")
    return res.get("result", {})
