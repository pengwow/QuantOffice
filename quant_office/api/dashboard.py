"""仪表盘综合数据 API — 一次性获取 Agent 状态 / 风控 / 当日成交。"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from ..core.agent_scheduler import get_agent_scheduler
from ..core.engine_adapter import get_engine_adapter

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/")
async def overview() -> Dict[str, Any]:
    scheduler = get_agent_scheduler()
    agents = scheduler.summary()

    # 风险指标
    risk = await scheduler.get("risk").handle("get_risk_metrics")
    risk_data = risk.get("result", {})

    # 今日成交
    exec_res = await scheduler.get("execution").handle("list_orders")
    orders = exec_res.get("result", {}).get("orders", [])
    fills = [o for o in orders if o.get("status") == "filled"]

    # 引擎模式
    engine = get_engine_adapter()

    return {
        "agents": agents,
        "risk": risk_data,
        "trades": {
            "total": len(orders),
            "filled": len(fills),
            "rejected": sum(1 for o in orders if o.get("status") == "rejected"),
        },
        "engine": {
            "using_axon_quant": engine.using_axon,
        },
        "office": {
            "fps": 30,
            "layout": "U-shape",
        },
    }
