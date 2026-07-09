"""风控 API（与前端 RiskAlert 形状对齐）。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ..data.database import get_session_factory
from ..data.models import RiskAlert
from ..services.api_schemas import alert_to_response

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
