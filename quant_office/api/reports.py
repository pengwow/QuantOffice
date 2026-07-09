"""报告 API（与前端 Report 形状对齐）。"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ..data.database import get_session_factory
from ..data.models import Report, Strategy, Trade
from ..services.api_schemas import report_to_response

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("")
async def list_reports() -> list[dict]:
    factory = get_session_factory()
    async with factory() as session:
        rows = (await session.scalars(select(Report).order_by(Report.created_at.desc()))).all()
    return [report_to_response(r) for r in rows]


@router.get("/{report_id}")
async def get_report(report_id: str) -> dict:
    factory = get_session_factory()
    async with factory() as session:
        r = await session.get(Report, report_id)
    if r is None:
        raise HTTPException(404, f"Report not found: {report_id}")
    return report_to_response(r)


@router.post("", status_code=201)
async def generate_report(body: dict) -> dict:
    """生成指定区间的报告（演示用：根据 trade 聚合）。"""
    now = datetime.utcnow()
    end = now
    start = now - timedelta(days=int(body.get("days", 30)))

    factory = get_session_factory()
    async with factory() as session:
        # 聚合数据
        strategies = (await session.scalars(select(Strategy))).all()
        trades = (
            await session.scalars(
                select(Trade).where(Trade.created_at >= start, Trade.created_at <= end)
            )
        ).all()

        total_pnl = sum(float(t.pnl or 0) for t in trades)
        win = sum(1 for t in trades if t.pnl > 0)
        win_rate = win / max(len(trades), 1)
        per_strat = []
        for s in strategies:
            sub = [t for t in trades if t.strategy_id == s.id]
            per_strat.append({
                "title": s.name,
                "body": f"区间内成交 {len(sub)} 笔，PnL {sum(float(t.pnl or 0) for t in sub):+.2f} USDT",
            })

        sections = [
            {"title": "收益概览", "body": f"区间 {start:%Y-%m-%d} ~ {end:%Y-%m-%d} 累计 PnL {total_pnl:+.2f} USDT，胜率 {win_rate:.1%}。"},
            {"title": "策略贡献", "body": "\n".join(f"- {x['title']}: {x['body']}" for x in per_strat)},
            {"title": "下月展望", "body": "继续维持 BTC 动量主策略，降低 DOGE 仓位，启动 BNB 配对实验。"},
        ]
        r = Report(
            id=f"rep-{uuid.uuid4().hex[:8]}",
            title=body.get("title", f"{start:%Y-%m-%d} ~ {end:%Y-%m-%d} 量化交易报告"),
            period_start=start,
            period_end=end,
            summary=f"区间内成交 {len(trades)} 笔，PnL {total_pnl:+.2f} USDT，胜率 {win_rate:.1%}。",
            sections=json.dumps(sections, ensure_ascii=False),
            created_at=now,
        )
        session.add(r)
        await session.commit()
        await session.refresh(r)
        return report_to_response(r)
