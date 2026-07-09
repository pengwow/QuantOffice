"""ORM 模型定义。

数据库表与 SQLAlchemy 2.0 异步 ORM。所有表统一加 ``qo_`` 前缀避免与其它业务表冲突。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# ============================================================
# 策略
# ============================================================
class Strategy(Base):
    __tablename__ = "qo_strategies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    symbol: Mapped[str] = mapped_column(String(32), default="BTCUSDT")
    params: Mapped[str] = mapped_column(Text, default="{}")   # JSON
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft/live/paused/stopped
    pnl: Mapped[float] = mapped_column(Float, default=0.0)
    sharpe: Mapped[float] = mapped_column(Float, default=0.0)
    drawdown: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============================================================
# 回测
# ============================================================
class Backtest(Base):
    __tablename__ = "qo_backtests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    strategy_id: Mapped[str] = mapped_column(String(64), index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime)
    period_end: Mapped[datetime] = mapped_column(DateTime)
    total_return: Mapped[float] = mapped_column(Float, default=0.0)
    annual_return: Mapped[float] = mapped_column(Float, default=0.0)
    sharpe: Mapped[float] = mapped_column(Float, default=0.0)
    max_drawdown: Mapped[float] = mapped_column(Float, default=0.0)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    trades: Mapped[int] = mapped_column(Integer, default=0)
    equity_curve: Mapped[str] = mapped_column(Text, default="[]")  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ============================================================
# 成交
# ============================================================
class Trade(Base):
    __tablename__ = "qo_trades"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    strategy_id: Mapped[str] = mapped_column(String(64), index=True)
    order_id: Mapped[str] = mapped_column(String(64), index=True)
    symbol: Mapped[str] = mapped_column(String(32))
    side: Mapped[str] = mapped_column(String(8))    # buy / sell
    qty: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    pnl: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(16), default="filled")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


# ============================================================
# 风控告警
# ============================================================
class RiskAlert(Base):
    __tablename__ = "qo_risk_alerts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    level: Mapped[str] = mapped_column(String(16), index=True)   # info / warning / critical
    rule: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text)
    symbol: Mapped[str] = mapped_column(String(32), default="")
    metric: Mapped[str] = mapped_column(String(64), default="")
    value: Mapped[float] = mapped_column(Float, default=0.0)
    threshold: Mapped[float] = mapped_column(Float, default=0.0)
    acknowledged: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


# ============================================================
# 报告
# ============================================================
class Report(Base):
    __tablename__ = "qo_reports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(256))
    period_start: Mapped[datetime] = mapped_column(DateTime)
    period_end: Mapped[datetime] = mapped_column(DateTime)
    summary: Mapped[str] = mapped_column(Text, default="")
    sections: Mapped[str] = mapped_column(Text, default="[]")  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ============================================================
# Agent 日志（保留原有）
# ============================================================
class AgentLog(Base):
    __tablename__ = "qo_agent_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent: Mapped[str] = mapped_column(String(32), index=True)
    level: Mapped[str] = mapped_column(String(16))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
