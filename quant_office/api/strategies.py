"""策略管理 API（基于 StrategyAgent）。"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from ..core.agent_scheduler import get_agent_scheduler

router = APIRouter(prefix="/strategies", tags=["strategies"])


def _agent():
    return get_agent_scheduler().get("strategy")


@router.get("/")
async def list_strategies() -> Dict[str, Any]:
    res = await _agent().handle("list_strategies")
    return res.get("result", {})


@router.post("/")
async def create_strategy(body: Dict[str, Any]) -> Dict[str, Any]:
    res = await _agent().handle("create_strategy", body)
    return res.get("result", {})


@router.post("/{name}/activate")
async def activate_strategy(name: str) -> Dict[str, Any]:
    res = await _agent().handle("activate_strategy", {"name": name})
    result = res.get("result", {})
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
