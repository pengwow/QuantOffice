"""回测任务 API。"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from ..core.agent_scheduler import get_agent_scheduler

router = APIRouter(prefix="/backtests", tags=["backtests"])


@router.post("/")
async def run_backtest(body: Dict[str, Any]) -> Dict[str, Any]:
    agent = get_agent_scheduler().get("strategy")
    res = await agent.handle("run_backtest", body)
    return res.get("result", {})
