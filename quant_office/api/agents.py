"""Agent 状态与控制 API。"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from ..core.agent_scheduler import get_agent_scheduler

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/")
async def list_agents() -> Dict[str, Any]:
    """列出所有 Agent 当前状态。"""
    return {"agents": get_agent_scheduler().summary()}


@router.get("/{agent_id}")
async def get_agent(agent_id: str) -> Dict[str, Any]:
    scheduler = get_agent_scheduler()
    try:
        agent = scheduler.get(agent_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "id": agent.agent_id,
        "name": agent.name,
        "role": agent.role.value,
        "status": agent.status.value,
        "workstation": agent.workstation,
        "metrics": agent.metrics,
    }


@router.post("/{agent_id}/command")
async def send_command(agent_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    scheduler = get_agent_scheduler()
    try:
        agent = scheduler.get(agent_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    command = body.get("command") or body.get("action")
    if not command:
        raise HTTPException(status_code=400, detail="缺少 command 字段")
    payload = body.get("payload", {})
    return await agent.handle(command, payload)


@router.get("/{agent_id}/logs")
async def get_agent_logs(agent_id: str, limit: int = 50) -> Dict[str, Any]:
    scheduler = get_agent_scheduler()
    try:
        agent = scheduler.get(agent_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"logs": agent.recent_logs(limit=limit)}
