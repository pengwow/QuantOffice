"""风控 API（与前端 RiskAlert 形状对齐）。

- ``GET  /api/risk/alerts``            列出告警
- ``GET  /api/risk/metrics``           聚合风控指标
- ``POST /api/risk/alerts/{id}/ack``   确认一条告警
- ``POST /api/risk/check``             立即触发一次全量扫描（手动）
- ``GET  /api/risk/config``            当前生效的阈值
- ``POST /api/risk/check-order``       单订单预风控（前端 dry-run 用）
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ..core.runtime_config import get_runtime_config
from ..data.database import get_session_factory
from ..data.models import RiskAlert
from ..services.api_schemas import alert_to_response
from ..services.risk_service import (
    check_risk_order,
    get_active_risk_cfg,
    run_full_risk_scan,
)

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/alerts")
async def list_alerts() -> list[dict]:
    factory = get_session_factory()
    async with factory() as session:
        rows = (await session.scalars(select(RiskAlert).order_by(RiskAlert.created_at.desc()))).all()
    return [alert_to_response(r) for r in rows]


@router.get("/metrics")
async def risk_metrics() -> dict:
    """聚合风控指标。"""
    factory = get_session_factory()
    async with factory() as session:
        rows = (await session.scalars(select(RiskAlert))).all()
    counts = {"info": 0, "warning": 0, "critical": 0}
    for r in rows:
        counts[r.level] = counts.get(r.level, 0) + 1
    return {
        "total_alerts": len(rows),
        "by_level": counts,
        "unacknowledged": sum(1 for r in rows if not r.acknowledged),
        "ts": "now",
    }


@router.post("/alerts/{alert_id}/ack", status_code=200)
async def ack_alert(alert_id: str) -> dict:
    factory = get_session_factory()
    async with factory() as session:
        a = await session.get(RiskAlert, alert_id)
        if a is None:
            raise HTTPException(404, f"Alert not found: {alert_id}")
        a.acknowledged = 1
        await session.commit()
        await session.refresh(a)
        return alert_to_response(a)


# ============================================================
# 周期 / 手动检查
# ============================================================


@router.post("/check", status_code=200)
async def trigger_check() -> dict:
    """手动触发一次全量风控扫描（写库 + 推送 event）。"""
    triggered = await run_full_risk_scan(write=True)
    return {
        "ok": True,
        "scanned": len(triggered),
        "alerts": triggered,
    }


@router.post("/check-dry-run", status_code=200)
async def trigger_check_dry_run() -> dict:
    """Dry-run：不写库，只返回会触发的告警（前端预览）。"""
    triggered = await run_full_risk_scan(write=False)
    return {
        "ok": True,
        "scanned": len(triggered),
        "alerts": triggered,
    }


@router.get("/config")
async def get_risk_config() -> dict:
    """当前生效的风险阈值（从 RuntimeConfigStore 实时读）。"""
    return get_active_risk_cfg().model_dump()


@router.post("/check-order", status_code=200)
async def check_order(body: Dict[str, Any]) -> dict:
    """单订单预风控（与 RiskAgent.check_risk 行为一致）。"""
    if not body:
        raise HTTPException(422, "body is required")
    result = await check_risk_order(body)
    return {"ok": True, "result": result}
