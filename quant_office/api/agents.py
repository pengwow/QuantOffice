"""Agent API。

端点：
  GET    /api/agents             -> Agent[]
  GET    /api/agents/{role}      -> Agent
  POST   /api/agents/{role}/start  -> Agent
  POST   /api/agents/{role}/stop   -> Agent
  POST   /api/agents/{role}/command -> {ok, result, agent}
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..core.agent_scheduler import get_agent_scheduler
from ..services.api_schemas import AGENT_META, AGENT_ROLES, agent_to_response

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("")
async def list_agents() -> list[dict]:
    """返回 6 个 Agent 的实时状态（按前端 Agent[] 形状）。"""
    scheduler = get_agent_scheduler()
    out: list[dict] = []
    summaries = {a["id"]: a for a in scheduler.summary()}
    for role in AGENT_ROLES:
        meta = AGENT_META[role]
        # 若 scheduler 没有这个 Agent（插件模式下可能未启动），仍返回 fallback
        s = summaries.get(role)
        if s is None:
            s = {"id": role, "name": meta["name"], "role": role, "status": "stopped"}
        out.append(agent_to_response(s))
    return out


@router.get("/{role}")
async def get_agent(role: str) -> dict:
    if role not in AGENT_META:
        raise HTTPException(404, f"Unknown agent role: {role}")
    scheduler = get_agent_scheduler()
    for s in scheduler.summary():
        if s["id"] == role:
            return agent_to_response(s)
    # fallback
    return agent_to_response({"id": role, "name": AGENT_META[role]["name"], "role": role, "status": "stopped"})


@router.post("/{role}/start", status_code=200)
async def start_agent(role: str) -> dict:
    if role not in AGENT_META:
        raise HTTPException(404, f"Unknown agent role: {role}")
    scheduler = get_agent_scheduler()
    try:
        agent = scheduler.get(role)
    except KeyError:
        raise HTTPException(404, f"Agent not started: {role}")
    res = await agent.handle("start", {})
    return {
        "ok": res.get("ok", False),
        "role": role,
        "result": res.get("result"),
    }


@router.post("/{role}/stop", status_code=200)
async def stop_agent(role: str) -> dict:
    if role not in AGENT_META:
        raise HTTPException(404, f"Unknown agent role: {role}")
    scheduler = get_agent_scheduler()
    try:
        agent = scheduler.get(role)
    except KeyError:
        raise HTTPException(404, f"Agent not started: {role}")
    res = await agent.handle("stop", {})
    return {
        "ok": res.get("ok", False),
        "role": role,
        "result": res.get("result"),
    }


@router.post("/{role}/command", status_code=200)
async def send_command(role: str, body: dict) -> dict:
    """通用命令入口：{command: str, payload: dict}"""
    if role not in AGENT_META:
        raise HTTPException(404, f"Unknown agent role: {role}")
    scheduler = get_agent_scheduler()
    try:
        agent = scheduler.get(role)
    except KeyError:
        raise HTTPException(404, f"Agent not started: {role}")
    cmd = body.get("command", "")
    payload = body.get("payload", {})
    res = await agent.handle(cmd, payload)
    return res
