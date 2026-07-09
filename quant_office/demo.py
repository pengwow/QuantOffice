"""演示数据 — 启动时自动播种。

启动 QuantOffice 后，如果数据库为空（首次运行 / 清空数据后），
自动注入完整的演示数据，确保前端 8 个页面均有内容可看。

包含：
  - 5 个策略（3 个 live、1 个 paused、1 个 draft）
  - 4 个回测（含等权权益曲线）
  - 30 笔成交（5 标的 / 6 策略，多空混合）
  - 3 个风控告警（1 critical / 1 warning / 1 info）
  - 1 个示例报告
"""
from __future__ import annotations

import json
import math
import random
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select

from .data.database import get_session_factory
from .data.models import Backtest, Report, RiskAlert, Strategy, Trade
from .logging_config import get_logger

logger = get_logger("demo")

# 固定随机种子 → 每次启动生成的数据完全一致（便于演示对比）
random.seed(20260709)

# ============================================================
# 元数据
# ============================================================
STRATEGY_META = [
    {
        "id": "strat-momentum-btc",
        "name": "BTC 动量突破",
        "description": "突破 20 日均线 + 动量确认，主要做多 BTC",
        "symbol": "BTCUSDT",
        "params": {"fast_ma": 5, "slow_ma": 20, "rsi_period": 14, "stop_loss": 0.02, "take_profit": 0.05},
        "status": "live",
        "pnl": 12480.50,
        "sharpe": 1.85,
        "drawdown": 0.082,
    },
    {
        "id": "strat-meanrev-eth",
        "name": "ETH 均值回归",
        "description": "RSI 超买超卖反转策略，ETH 1h 级别",
        "symbol": "ETHUSDT",
        "params": {"rsi_oversold": 30, "rsi_overbought": 70, "lookback": 20},
        "status": "live",
        "pnl": 6230.80,
        "sharpe": 1.42,
        "drawdown": 0.054,
    },
    {
        "id": "strat-grid-sol",
        "name": "SOL 网格套利",
        "description": "价格在网格内反复高抛低吸",
        "symbol": "SOLUSDT",
        "params": {"upper": 180, "lower": 120, "grids": 20, "qty_per_grid": 0.5},
        "status": "live",
        "pnl": 1840.20,
        "sharpe": 0.95,
        "drawdown": 0.031,
    },
    {
        "id": "strat-trend-doge",
        "name": "DOGE 趋势跟踪",
        "description": "海龟交易法则，ATR 动态止损",
        "symbol": "DOGEUSDT",
        "params": {"entry_period": 20, "exit_period": 10, "atr_multiplier": 2.0},
        "status": "paused",
        "pnl": -120.30,
        "sharpe": 0.42,
        "drawdown": 0.156,
    },
    {
        "id": "strat-pairs-bnb",
        "name": "BNB/USDT 配对",
        "description": "协整配对交易（实验性）",
        "symbol": "BNBUSDT",
        "params": {"zscore_entry": 2.0, "zscore_exit": 0.5, "lookback": 60},
        "status": "draft",
        "pnl": 0.0,
        "sharpe": 0.0,
        "drawdown": 0.0,
    },
]

SYMBOL_PRICE = {
    "BTCUSDT": 67000.0,
    "ETHUSDT": 3500.0,
    "SOLUSDT": 150.0,
    "DOGEUSDT": 0.18,
    "BNBUSDT": 600.0,
}


# ============================================================
# 生成器
# ============================================================
def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def _gen_equity_curve(period_start: datetime, period_end: datetime, total_return: float, daily_vol: float = 0.012) -> list[dict]:
    """生成与 total_return 一致的伪权益曲线（用于图表）。"""
    days = max((period_end - period_start).days, 7)
    n = min(days, 90)  # 最多 90 个点
    daily = total_return / n
    equity = 100_000.0
    pts: list[dict] = []
    drift = total_return / n
    for i in range(n + 1):
        t = period_start + timedelta(days=int(days * i / n))
        shock = random.gauss(0, daily_vol)
        equity = 100_000.0 * (1 + drift * i + shock * math.sqrt(i + 1))
        pts.append({"date": t.strftime("%Y-%m-%d"), "equity": round(equity, 2)})
    pts[-1]["equity"] = round(100_000.0 * (1 + total_return), 2)
    return pts


def _gen_strategies() -> list[Strategy]:
    now = datetime.utcnow()
    rows: list[Strategy] = []
    for meta in STRATEGY_META:
        created = now - timedelta(days=random.randint(30, 180))
        rows.append(Strategy(
            id=meta["id"],
            name=meta["name"],
            description=meta["description"],
            symbol=meta["symbol"],
            params=json.dumps(meta["params"]),
            status=meta["status"],
            pnl=meta["pnl"],
            sharpe=meta["sharpe"],
            drawdown=meta["drawdown"],
            created_at=created,
            updated_at=now - timedelta(hours=random.randint(0, 48)),
        ))
    return rows


def _gen_backtests(strategies: list[Strategy]) -> list[Backtest]:
    rows: list[Backtest] = []
    now = datetime.utcnow()
    # 4 个回测：3 个 live 策略 + 1 个 paused
    for strat in strategies[:4]:
        period_end = now - timedelta(days=random.randint(1, 30))
        period_start = period_end - timedelta(days=random.choice([90, 180, 365]))
        total_return = round(random.uniform(0.12, 0.85), 4) if strat.status != "paused" else round(random.uniform(-0.15, 0.05), 4)
        annual = round(total_return * (365 / max((period_end - period_start).days, 1)), 4)
        sharpe = round(random.uniform(0.8, 2.2), 2)
        max_dd = round(random.uniform(0.05, 0.25), 4)
        win = round(random.uniform(0.42, 0.68), 4)
        n_trades = random.randint(45, 280)
        rows.append(Backtest(
            id=f"bt-{uuid.uuid4().hex[:8]}",
            strategy_id=strat.id,
            period_start=period_start,
            period_end=period_end,
            total_return=total_return,
            annual_return=annual,
            sharpe=sharpe,
            max_drawdown=max_dd,
            win_rate=win,
            trades=n_trades,
            equity_curve=json.dumps(_gen_equity_curve(period_start, period_end, total_return)),
            created_at=now - timedelta(days=random.randint(0, 7)),
        ))
    return rows


def _gen_trades(strategies: list[Strategy]) -> list[Trade]:
    rows: list[Trade] = []
    now = datetime.utcnow()
    active = [s for s in strategies if s.status in ("live", "paused")]
    for i in range(30):
        strat = random.choice(active)
        sym = strat.symbol
        side = random.choice(["buy", "sell"])
        # 价格在基准价附近 ±10%
        base = SYMBOL_PRICE.get(sym, 100.0)
        price = round(base * (1 + random.uniform(-0.08, 0.08)), 4)
        # 数量
        if "BTC" in sym:
            qty = round(random.uniform(0.005, 0.05), 4)
        elif "ETH" in sym:
            qty = round(random.uniform(0.05, 0.5), 4)
        elif "SOL" in sym:
            qty = round(random.uniform(0.5, 5.0), 2)
        elif "DOGE" in sym:
            qty = round(random.uniform(100, 2000), 0)
        else:
            qty = round(random.uniform(0.5, 5.0), 2)
        # PnL: 大多数正收益，少量亏损
        pnl = round(random.gauss(50, 80), 2)
        # 状态
        status = random.choices(["filled", "filled", "filled", "submitted", "rejected", "cancelled"], k=1)[0]
        ts = now - timedelta(minutes=random.randint(1, 60 * 24 * 7))
        rows.append(Trade(
            id=f"trade-{uuid.uuid4().hex[:10]}",
            strategy_id=strat.id,
            order_id=f"order-{uuid.uuid4().hex[:10]}",
            symbol=sym,
            side=side,
            qty=qty,
            price=price,
            pnl=pnl,
            status=status,
            created_at=ts,
        ))
    rows.sort(key=lambda t: t.created_at, reverse=True)
    return rows


def _gen_alerts() -> list[RiskAlert]:
    now = datetime.utcnow()
    return [
        RiskAlert(
            id=f"alert-{uuid.uuid4().hex[:8]}",
            level="critical",
            rule="position_limit",
            message="BTCUSDT 多头持仓占比超过 35% 上限",
            symbol="BTCUSDT",
            metric="position_pct",
            value=37.2,
            threshold=35.0,
            acknowledged=0,
            created_at=now - timedelta(minutes=12),
        ),
        RiskAlert(
            id=f"alert-{uuid.uuid4().hex[:8]}",
            level="warning",
            rule="drawdown",
            message="DOGE 策略近 7 日回撤达 12.5%，逼近 15% 红线",
            symbol="DOGEUSDT",
            metric="drawdown_7d",
            value=12.5,
            threshold=15.0,
            acknowledged=0,
            created_at=now - timedelta(hours=2),
        ),
        RiskAlert(
            id=f"alert-{uuid.uuid4().hex[:8]}",
            level="info",
            rule="daily_pnl",
            message="今日组合 PnL 已达 +8.2%，表现优异",
            symbol="",
            metric="daily_pnl_pct",
            value=8.2,
            threshold=0.0,
            acknowledged=1,
            created_at=now - timedelta(hours=6),
        ),
    ]


def _gen_report() -> list[Report]:
    now = datetime.utcnow()
    end = now
    start = now - timedelta(days=30)
    return [
        Report(
            id=f"rep-{uuid.uuid4().hex[:8]}",
            title="近 30 日量化交易报告",
            period_start=start,
            period_end=end,
            summary=(
                "近 30 日组合实现 +18.4% 收益，年化约 +220%，最大回撤控制在 8.2% 以内。"
                "BTC 动量突破策略表现最佳（贡献 +12,480.50），ETH 均值回归次之（+6,230.80），"
                "DOGE 趋势跟踪处于回撤期已暂停。整体夏普 1.65，胜率 58.3%。"
            ),
            sections=json.dumps([
                {
                    "title": "收益概览",
                    "body": "近 30 日累计收益 +18.42%，年化 +221%。最大回撤 8.20% 出现在 7 月 3 日 DOGEUSDT 单日下跌 12% 时段，已及时止损。",
                },
                {
                    "title": "策略贡献度",
                    "body": "BTC 动量: +12,480.50 (71.2%) | ETH 均值回归: +6,230.80 (35.5%) | SOL 网格: +1,840.20 (10.5%) | DOGE 趋势: -120.30 (-0.7%) | 费用: -2,041.20",
                },
                {
                    "title": "风险事件",
                    "body": "本月共触发 12 次风控告警，其中 1 次 critical（BTCUSDT 持仓超限）已手动平仓处理，3 次 warning 自动调仓，8 次 info。",
                },
                {
                    "title": "下月展望",
                    "body": "建议：1) 恢复 DOGE 趋势策略但降低仓位至 5%；2) 启动 BNB 配对策略实验性运行；3) BTC 动量策略加仓至 1.5x。",
                },
            ]),
            created_at=now - timedelta(hours=3),
        ),
    ]


# ============================================================
# 主入口
# ============================================================
async def seed_if_empty() -> dict[str, int]:
    """如果数据库为空则注入演示数据，返回各类插入条数。"""
    factory = get_session_factory()
    counts = {"strategy": 0, "backtest": 0, "trade": 0, "risk_alert": 0, "report": 0}
    async with factory() as session:
        # 检测是否已有数据
        existing = await session.scalar(select(Strategy).limit(1))
        if existing is not None:
            logger.info("数据库已有数据，跳过演示播种")
            return counts

        # ----- 1) 策略 -----
        strategies = _gen_strategies()
        session.add_all(strategies)
        await session.flush()
        counts["strategy"] = len(strategies)

        # ----- 2) 回测 -----
        backtests = _gen_backtests(strategies)
        session.add_all(backtests)
        await session.flush()
        counts["backtest"] = len(backtests)

        # ----- 3) 成交 -----
        trades = _gen_trades(strategies)
        session.add_all(trades)
        await session.flush()
        counts["trade"] = len(trades)

        # ----- 4) 告警 -----
        alerts = _gen_alerts()
        session.add_all(alerts)
        await session.flush()
        counts["risk_alert"] = len(alerts)

        # ----- 5) 报告 -----
        reports = _gen_report()
        session.add_all(reports)
        await session.flush()
        counts["report"] = len(reports)

        await session.commit()

    logger.info(
        "演示数据已播种：策略=%d 回测=%d 成交=%d 告警=%d 报告=%d",
        counts["strategy"], counts["backtest"], counts["trade"], counts["risk_alert"], counts["report"],
    )
    return counts


async def reset_and_seed() -> dict[str, int]:
    """清空并重新注入演示数据（供 /api/demo/reset 调用）。"""
    from .data.models import Backtest, Report, RiskAlert, Strategy, Trade
    factory = get_session_factory()
    async with factory() as session:
        for model in (Backtest, Report, RiskAlert, Trade, Strategy):
            await session.execute(model.__table__.delete())
        await session.commit()
    return await seed_if_empty()
