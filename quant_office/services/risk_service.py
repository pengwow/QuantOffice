"""风控服务 — 包装 RiskAgent 业务 + 真实数据库读写。

职责：
- ``record_alert`` 写 RiskAlert 库
- ``run_full_risk_scan`` 扫所有 active 策略，触发则写告警
- ``get_active_risk_cfg`` 从 RuntimeConfigStore 读最新阈值（热更新）
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from ..core.runtime_config import RiskConfig, get_runtime_config
from ..data.database import get_session_factory
from ..data.models import RiskAlert, Strategy
from ..logging_config import get_logger

logger = get_logger("services.risk")


# ============================================================
# 工具
# ============================================================


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def get_active_risk_cfg() -> RiskConfig:
    """从 RuntimeConfigStore 读最新风险阈值（UI 改完立即生效）。"""
    return get_runtime_config().get_risk()


# ============================================================
# 写库
# ============================================================


async def record_alert(
    level: str,
    rule: str,
    message: str,
    *,
    symbol: str = "",
    metric: str = "",
    value: float = 0.0,
    threshold: float = 0.0,
) -> Dict[str, Any]:
    """写一条 RiskAlert 入库，返回序列化结果。"""
    alert_id = f"alert-{uuid.uuid4().hex[:10]}"
    factory = get_session_factory()
    async with factory() as session:
        row = RiskAlert(
            id=alert_id,
            level=level,
            rule=rule,
            message=message,
            symbol=symbol,
            metric=metric,
            value=float(value),
            threshold=float(threshold),
            acknowledged=0,
            created_at=datetime.utcnow(),
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return {
            "id": row.id,
            "level": row.level,
            "rule": row.rule,
            "message": row.message,
            "symbol": row.symbol or None,
            "metric": row.metric or None,
            "value": float(row.value or 0.0),
            "threshold": float(row.threshold or 0.0),
            "acknowledged": bool(row.acknowledged),
            "created_at": row.created_at.isoformat() if row.created_at else _now_iso(),
        }


# ============================================================
# 扫描
# ============================================================


def _evaluate_strategy(strategy: Strategy, cfg: RiskConfig) -> List[Dict[str, Any]]:
    """根据 strategy 当前指标与阈值，决定是否触发告警。"""
    alerts: List[Dict[str, Any]] = []
    drawdown = float(strategy.drawdown or 0.0)
    pnl = float(strategy.pnl or 0.0)
    sharpe = float(strategy.sharpe or 0.0)

    # 1) drawdown 越线
    if drawdown >= cfg.max_drawdown:
        alerts.append({
            "level": "critical",
            "rule": "max_drawdown_breach",
            "message": (
                f"策略 {strategy.name}({strategy.symbol}) 回撤 {drawdown:.2%} "
                f"超过阈值 {cfg.max_drawdown:.2%}"
            ),
            "symbol": strategy.symbol,
            "metric": "drawdown",
            "value": drawdown,
            "threshold": cfg.max_drawdown,
        })
    elif drawdown >= cfg.warning_drawdown:
        alerts.append({
            "level": "warning",
            "rule": "warning_drawdown_breach",
            "message": (
                f"策略 {strategy.name}({strategy.symbol}) 回撤 {drawdown:.2%} "
                f"逼近阈值 {cfg.warning_drawdown:.2%}"
            ),
            "symbol": strategy.symbol,
            "metric": "drawdown",
            "value": drawdown,
            "threshold": cfg.warning_drawdown,
        })

    # 2) sharpe 长期为负
    if sharpe < -1.0:
        alerts.append({
            "level": "warning",
            "rule": "low_sharpe",
            "message": (
                f"策略 {strategy.name}({strategy.symbol}) Sharpe={sharpe:.2f} 长期低于 -1"
            ),
            "symbol": strategy.symbol,
            "metric": "sharpe",
            "value": sharpe,
            "threshold": -1.0,
        })

    # 3) 单策略累计亏损超过 max_position_ratio（用 pnl 相对初始 100k 估算）
    if pnl < -50_000.0 * cfg.max_position_ratio:
        alerts.append({
            "level": "critical",
            "rule": "portfolio_loss_breach",
            "message": (
                f"策略 {strategy.name} 累计亏损 {pnl:.0f} 超出允许范围"
            ),
            "symbol": strategy.symbol,
            "metric": "pnl",
            "value": pnl,
            "threshold": -50_000.0 * cfg.max_position_ratio,
        })

    return alerts


async def run_full_risk_scan(*, write: bool = True) -> List[Dict[str, Any]]:
    """扫所有 live/paused 策略，触发则写 RiskAlert，返回所有本次告警。

    - ``write=False`` 用于 dry-run（前端预览）。
    - 每次扫描都从 RuntimeConfigStore 重读阈值 → UI 改完立即生效。
    """
    cfg = get_active_risk_cfg()
    factory = get_session_factory()
    triggered: List[Dict[str, Any]] = []
    async with factory() as session:
        rows = (
            await session.scalars(
                select(Strategy).where(Strategy.status.in_(("live", "paused")))
            )
        ).all()
        strategies = list(rows)

    for s in strategies:
        try:
            candidates = _evaluate_strategy(s, cfg)
        except Exception as exc:  # pragma: no cover
            logger.exception("策略 %s 风控评估失败: %s", s.id, exc)
            continue
        for c in candidates:
            if not write:
                triggered.append({**c, "id": None, "acknowledged": False, "created_at": _now_iso()})
                continue
            try:
                rec = await record_alert(**c)
                triggered.append(rec)
                logger.info("触发风控告警: %s [%s] %s", c["rule"], c["level"], c["message"])
            except Exception as exc:  # pragma: no cover
                logger.exception("写风控告警失败: %s", exc)
    return triggered


# ============================================================
# RiskAgent.process 包装 — 旧接口兼容
# ============================================================


async def check_risk_order(order: Dict[str, Any], portfolio: Optional[Any] = None) -> Dict[str, Any]:
    """被 RiskAgent.process('check_risk', ...) 调用：跑预交易风控并写库。"""
    from ..core.engine_adapter import OrderRequest, Portfolio, get_engine_adapter

    engine = get_engine_adapter()
    portfolio = portfolio or Portfolio(cash=100_000.0, positions={})
    req = OrderRequest(
        symbol=str(order.get("symbol", "BTCUSDT")),
        side=str(order.get("side", "buy")),
        quantity=float(order.get("quantity", 0.0)),
        order_type=str(order.get("order_type", "market")),
        price=order.get("price"),
    )
    out = engine.pre_trade_check(req, portfolio)
    if not out.passed:
        # 写一条告警
        await record_alert(
            level="critical" if out.severity == "critical" else "warning",
            rule=out.failed_check or "pre_trade_reject",
            message=out.message or "预交易风控拒绝",
            symbol=req.symbol,
            metric="pre_trade",
            value=req.quantity * (req.price or 0.0),
            threshold=portfolio.portfolio_value * engine.settings.risk_max_position_ratio,
        )
    return out.to_dict()
