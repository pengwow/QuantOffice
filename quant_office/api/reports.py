"""报告生成 API。"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from ..core.agent_scheduler import get_agent_scheduler

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/")
async def generate(body: Dict[str, Any]) -> Dict[str, Any]:
    res = await get_agent_scheduler().get("report").handle("generate_report", body)
    return res.get("result", {})


@router.get("/")
async def list_reports() -> Dict[str, Any]:
    res = await get_agent_scheduler().get("report").handle("list_reports")
    return res.get("result", {})
