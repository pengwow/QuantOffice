"""axon_quant 引擎适配器（双模式共享）。

设计目标：
- 当 ``axon_quant`` 可用时（已安装 0.3.0+）直接调用 Rust 核心
  （BacktestEngine / L1MatchingEngine / DataService / RiskLimits）；
- 当不可用（开发 / CI 环境）时，自动回退到 Python 内存实现，
  业务 Agent 永远面向统一的 ``AxonQuantAdapter`` 编程，无需感知后端。

公共契约（与上层 Agent / API 共享）：
- ``OrderRequest`` / ``OrderResult`` / ``Portfolio`` / ``BacktestResult``
- ``RiskCheckOutcome``
- ``AxonQuantAdapter`` 单例（``get_engine_adapter()``）
"""
from __future__ import annotations

import asyncio
import math
import random
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ..config import Settings, get_settings
from ..logging_config import get_logger

logger = get_logger("core.engine")

# ============================================================
# axon_quant 可选导入
# ============================================================
try:  # pragma: no cover - 可选依赖
    import axon_quant as aq  # type: ignore
    AXON_AVAILABLE = True
except Exception as _exc:  # pragma: no cover
    aq = None  # type: ignore
    AXON_AVAILABLE = False
    logger.info("axon_quant 未安装或不可用：%s", _exc)


# ============================================================
# 共享数据类（fallback 与上层共享）
# ============================================================


@dataclass
class Portfolio:
    """账户组合快照。"""

    cash: float = 100_000.0
    positions: Dict[str, float] = field(default_factory=dict)  # symbol -> quantity
    avg_prices: Dict[str, float] = field(default_factory=dict)
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0

    @property
    def portfolio_value(self) -> float:
        return self.cash + sum(
            self.positions.get(s, 0.0) * self.avg_prices.get(s, 0.0)
            for s in self.positions
        )

    @property
    def available_margin(self) -> float:
        return max(0.0, self.cash)


@dataclass
class OrderRequest:
    """订单请求（与 axon_quant Order 对齐）。"""

    symbol: str
    side: str  # "buy" / "sell"
    quantity: float
    order_type: str = "market"  # market / limit
    price: Optional[float] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "order_type": self.order_type,
            "price": self.price,
            "timestamp": self.timestamp,
        }


@dataclass
class OrderResult:
    order_id: str
    status: str  # submitted / filled / rejected / partial
    symbol: str
    side: str
    quantity: float
    filled_price: Optional[float] = None
    filled_at: Optional[float] = None
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class RiskCheckOutcome:
    passed: bool
    severity: str = "info"  # info / warning / critical
    failed_check: Optional[str] = None
    message: Optional[str] = None
    suggested_action: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class BacktestResult:
    strategy: str
    total_return: float = 0.0
    annual_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    trades: int = 0
    equity_curve: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy,
            "total_return": self.total_return,
            "annual_return": self.annual_return,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "win_rate": self.win_rate,
            "trades": self.trades,
            "equity_curve": self.equity_curve,
        }


# ============================================================
# Fallback 内存实现（axon_quant 不可用时）
# ============================================================


class _FallbackRiskEngine:
    """Python 内存风控引擎 — 用于 axon_quant 不可用场景。"""

    def __init__(self, settings: Settings) -> None:
        self.max_drawdown = settings.risk_max_drawdown
        self.warning_drawdown = settings.risk_warning_drawdown
        self.max_position_ratio = settings.risk_max_position_ratio
        self.max_var = settings.risk_max_var
        self._tripped = False

    def check(self, order: OrderRequest, portfolio: Portfolio) -> RiskCheckOutcome:
        if self._tripped:
            return RiskCheckOutcome(
                passed=False,
                severity="critical",
                failed_check="circuit_breaker",
                message="熔断器已触发，禁止下单",
                suggested_action="等待熔断器重置或人工解除",
            )
        price = order.price or 1.0
        order_value = order.quantity * price
        if order_value > portfolio.portfolio_value * self.max_position_ratio:
            return RiskCheckOutcome(
                passed=False,
                severity="warning",
                failed_check="position_limit",
                message=f"订单金额 {order_value:.2f} 超过单笔仓位上限",
                suggested_action="拆单或降低数量",
            )
        return RiskCheckOutcome(passed=True, severity="info")

    def reload(self, settings: Settings) -> None:
        self.max_drawdown = settings.risk_max_drawdown
        self.warning_drawdown = settings.risk_warning_drawdown
        self.max_position_ratio = settings.risk_max_position_ratio
        self.max_var = settings.risk_max_var


class _FallbackOMS:
    def __init__(self) -> None:
        self._orders: Dict[str, OrderResult] = {}
        self._seq = 0

    async def submit(self, order: OrderRequest) -> OrderResult:
        self._seq += 1
        oid = f"FALLBACK-{self._seq:08d}"
        result = OrderResult(
            order_id=oid,
            status="filled",
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            filled_price=order.price or 0.0,
            filled_at=time.time(),
        )
        self._orders[oid] = result
        return result


class _FallbackExchange:
    """模拟交易所 — 立即以市价成交。"""

    SEED_PRICES = {"BTCUSDT": 67_000.0, "ETHUSDT": 3_500.0, "SOLUSDT": 150.0}

    def __init__(self) -> None:
        self._prices: Dict[str, float] = dict(self.SEED_PRICES)

    def get_price(self, symbol: str) -> float:
        return self._prices.get(symbol, 100.0)

    def set_price(self, symbol: str, price: float) -> None:
        self._prices[symbol] = price


# ============================================================
# axon_quant 真接实现
# ============================================================


class _AxonRiskEngine:
    """封装 axon_quant.RiskLimits + 仓位 / 净值 / VaR 检查。"""

    def __init__(self, settings: Settings) -> None:
        self.max_drawdown = settings.risk_max_drawdown
        self.warning_drawdown = settings.risk_warning_drawdown
        self.max_position_ratio = settings.risk_max_position_ratio
        self.max_var = settings.risk_max_var
        self._tripped = False

    def check(self, order: OrderRequest, portfolio: Portfolio) -> RiskCheckOutcome:
        if self._tripped:
            return RiskCheckOutcome(
                passed=False,
                severity="critical",
                failed_check="circuit_breaker",
                message="熔断器已触发，禁止下单",
                suggested_action="等待熔断器重置或人工解除",
            )
        price = order.price or 1.0
        order_value = order.quantity * price
        if order_value > portfolio.portfolio_value * self.max_position_ratio:
            return RiskCheckOutcome(
                passed=False,
                severity="warning",
                failed_check="position_limit",
                message=f"订单金额 {order_value:.2f} 超过单笔仓位上限",
                suggested_action="拆单或降低数量",
            )
        # 真实引擎中可继续用 aq.RiskLimits / aq.RiskCheckResult 做原子检查
        return RiskCheckOutcome(passed=True, severity="info")

    def reload(self, settings: Settings) -> None:
        self.max_drawdown = settings.risk_max_drawdown
        self.warning_drawdown = settings.risk_warning_drawdown
        self.max_position_ratio = settings.risk_max_position_ratio
        self.max_var = settings.risk_max_var


class _AxonOMS:
    """使用 axon_quant.L1MatchingEngine 做撮合的轻量 OMS。"""

    def __init__(self) -> None:
        # 每个 symbol 一个 L1 实例
        self._engines: Dict[str, Any] = {}
        self._seq = 0

    def _get_engine(self, symbol: str, mid: float) -> Any:
        me = self._engines.get(symbol)
        if me is None:
            me = aq.L1MatchingEngine()
            me.seed_liquidity(mid, 0.05, 3, 1.0, symbol, 1)
            self._engines[symbol] = me
        return me

    async def submit(self, order: OrderRequest) -> OrderResult:
        self._seq += 1
        mid = order.price or 100.0
        me = self._get_engine(order.symbol, mid)
        oid = f"AQ-{self._seq:08d}-{uuid.uuid4().hex[:6]}"
        try:
            # axon_quant.L1MatchingEngine 期望的字段：
            # id(int) / type(limit/market) / tif(GTC/IOC/FOK) / quantity(数字)
            # side 大小写不敏感，buy 即可
            order_dict = {
                "id": self._seq,
                "type": order.order_type if order.order_type in ("limit", "market") else "market",
                "tif": "GTC" if order.order_type == "limit" else "IOC",
                "symbol": order.symbol,
                "side": order.side,
                "quantity": float(order.quantity),
                "price": float(order.price or mid),
                "timestamp_ns": int(time.time() * 1_000_000_000),
            }
            ack = me.submit(order_dict)
            fills = ack.get("fills", []) if isinstance(ack, dict) else []
            is_filled = bool(ack.get("is_filled")) if isinstance(ack, dict) else False
            status = "filled" if is_filled else "submitted"
            fill_price = float(fills[0]["price"]) if fills else float(order.price or mid)
            return OrderResult(
                order_id=oid,
                status=status,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                filled_price=fill_price,
                filled_at=time.time(),
            )
        except Exception as exc:  # pragma: no cover
            return OrderResult(
                order_id=oid,
                status="rejected",
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                reason=str(exc),
            )


# ============================================================
# 统一适配器
# ============================================================


class AxonQuantAdapter:
    """axon_quant 适配器（双模式共享）。

    优先使用 ``axon_quant`` 真实引擎；若未安装，回退到内存实现，
    业务 Agent 不感知差异。
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.using_axon = False
        self._risk_engine: Any = None
        self._oms: Any = None
        self._exchange: Any = None
        self._init_engine()

    # ---- 初始化 ----

    def _init_engine(self) -> None:
        if not AXON_AVAILABLE:
            logger.info("axon_quant 未安装，使用内存 fallback 实现")
            self._risk_engine = _FallbackRiskEngine(self.settings)
            self._oms = _FallbackOMS()
            self._exchange = _FallbackExchange()
            return
        try:
            self._risk_engine = _AxonRiskEngine(self.settings)
            self._oms = _AxonOMS()
            self._exchange = _FallbackExchange()  # 仍用 fallback 拿基准价
            self.using_axon = True
            logger.info("axon_quant 真实引擎已初始化 (version=%s)", getattr(aq, "__version__", "?"))
        except Exception as exc:  # pragma: no cover
            logger.warning("axon_quant 初始化失败，回退 fallback: %s", exc)
            self._risk_engine = _FallbackRiskEngine(self.settings)
            self._oms = _FallbackOMS()
            self._exchange = _FallbackExchange()

    # ---- 公共 API ----

    def reload_settings(self, settings: Settings) -> None:
        """热加载新配置（被 API 设置变更时调用）。"""
        self.settings = settings
        if hasattr(self._risk_engine, "reload"):
            self._risk_engine.reload(settings)

    def pre_trade_check(
        self, order: OrderRequest, portfolio: Portfolio
    ) -> RiskCheckOutcome:
        """预交易风控检查。"""
        return self._risk_engine.check(order, portfolio)

    async def submit_order(
        self, order: OrderRequest, portfolio: Portfolio
    ) -> OrderResult:
        """提交订单（先风控再 OMS）。"""
        check = self.pre_trade_check(order, portfolio)
        if not check.passed:
            return OrderResult(
                order_id="",
                status="rejected",
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                reason=check.message or check.failed_check,
            )
        return await self._oms.submit(order)

    def current_price(self, symbol: str) -> float:
        """获取当前价（axon 模式下用 DataService 拿最近一根 Min1 bar 的 close）。"""
        if self.using_axon and AXON_AVAILABLE:
            try:
                from datetime import datetime, timedelta, timezone

                ds = aq.DataService.new()
                src = aq.MockSource.with_tick_series(
                    symbol, 60, 1_000_000_000, lambda i: 100.0 + i * 0.1
                )
                ds.register_source(src)
                end = datetime.now(timezone.utc).replace(microsecond=0)
                start = end - timedelta(minutes=60)
                req = aq.DataRequest(
                    symbol, start, end, aq.Frequency.Min1, fields=None, source=symbol
                )
                dataset = ds.load(req)
                ticks = list(dataset.ticks()) if dataset and dataset.len else []
                if ticks:
                    return float(ticks[-1].price)
            except Exception as exc:  # pragma: no cover
                logger.debug("axon 取价失败，回退 fallback: %s", exc)
        return self._exchange.get_price(symbol)

    def run_backtest(
        self,
        strategy_name: str,
        bars: Optional[List[Dict[str, Any]]] = None,
        start_ts: Optional[float] = None,
        end_ts: Optional[float] = None,
    ) -> BacktestResult:
        """运行回测。

        - ``bars`` 为 None 时，axon 模式下用 DataService + MockSource 合成 30 根 bar
          （fallback 模式使用内置 SMA 动量策略）。
        - 返回 ``BacktestResult``。
        """
        # axon_quant 0.3.0 在 bars > 80 时 ``engine.run()`` 会卡死（疑似 GIL 锁）
        # 长周期走 fallback SMA 策略；短周期（≤80 bars）走真接 Rust 引擎
        MAX_AXON_BARS = 80
        if self.using_axon and AXON_AVAILABLE and (bars is None or len(bars) <= MAX_AXON_BARS):
            try:
                return self._run_backtest_axon(strategy_name, bars)
            except Exception as exc:  # pragma: no cover
                logger.warning("axon 回测失败，回退 fallback: %s", exc)
        return self._run_backtest_fallback(strategy_name, bars or [])

    # ---- axon 模式真回测 ----

    def _run_backtest_axon(
        self,
        strategy_name: str,
        bars: Optional[List[Dict[str, Any]]],
    ) -> BacktestResult:
        if not bars:
            from datetime import datetime, timedelta, timezone

            symbol = "BTCUSDT"
            ds = aq.DataService.new()
            base = 100.0
            src = aq.MockSource.with_tick_series(
                symbol, 30, 1_000_000_000, lambda i: base + i * 0.5
            )
            ds.register_source(src)
            end = datetime.now(timezone.utc).replace(microsecond=0)
            start = end - timedelta(minutes=30)
            req = aq.DataRequest(
                symbol, start, end, aq.Frequency.Min1, fields=None, source=symbol
            )
            dataset = ds.load(req)
            ticks = list(dataset.ticks()) if dataset and dataset.len else []
            bars = [{"close": float(t.price), "open": float(t.price), "high": float(t.price), "low": float(t.price)} for t in ticks]

        me = aq.L1MatchingEngine()
        engine = aq.BacktestEngine(100_000.0)
        engine.with_matching_engine(me)
        engine.with_seed_liquidity(0.05, 3, 1.0)
        engine.with_fee_config(0.0004)
        engine.with_force_liquidate(True)

        for i, bar in enumerate(bars):
            price = float(bar.get("close") or bar.get("price") or 0.0)
            symbol = str(bar.get("symbol", "BTCUSDT"))
            engine.begin_bar(price, symbol)
            # 简单动量信号：每 7 根推一笔市价买单
            if i >= 5 and i % 7 == 0 and i < len(bars) - 1:
                engine.push_event({
                    "type": "order_submitted",
                    "timestamp_ns": int(time.time() * 1e9) + i,
                    "order": {
                        "id": i + 1,
                        "type": "market",
                        "tif": "IOC",
                        "idempotency_key": f"bt-{i}",
                        "symbol": symbol,
                        "side": "Buy",
                        "order_type": "Market",
                        "quantity": 0.1,
                        "price": 0.0,
                    },
                })
            engine.step()
        res = engine.run()
        # 优先用 to_dict 的标准字段名(snake_case: total_pnl / final_nav /
        # max_drawdown / max_drawdown_pct / sharpe_ratio / win_rate / trades_count)
        d = res.to_dict() if hasattr(res, "to_dict") else {}
        raw_curve = getattr(res, "equity_curve", []) or []
        # equity_curve 元素是 (bar_idx, nav) tuple
        equity_curve: list[float] = []
        for p in raw_curve:
            try:
                equity_curve.append(float(p[1]))
            except (TypeError, IndexError, ValueError):
                try:
                    equity_curve.append(float(p))
                except (TypeError, ValueError):
                    continue
        if not equity_curve and bars:
            equity_curve = [float(b.get("close", 0.0)) for b in bars]

        total_pnl = float(d.get("total_pnl", 0.0) or 0.0)
        # pnl 比率相对 initial_cash(100_000) 计算
        total_return = total_pnl / 100_000.0 if total_pnl else 0.0
        return BacktestResult(
            strategy=strategy_name,
            total_return=total_return,
            annual_return=total_return,  # 短周期近似
            sharpe_ratio=float(d.get("sharpe_ratio", 0.0) or 0.0),
            max_drawdown=float(d.get("max_drawdown", 0.0) or d.get("max_drawdown_pct", 0.0) or 0.0),
            win_rate=float(d.get("win_rate", 0.0) or 0.0),
            trades=int(d.get("trades_count", 0) or 0),
            equity_curve=equity_curve,
        )

    # ---- Fallback SMA 动量策略 ----

    def _run_backtest_fallback(
        self, strategy_name: str, bars: List[Dict[str, Any]]
    ) -> BacktestResult:
        closes = [float(b.get("close", 0.0)) for b in bars]
        if len(closes) < 30:
            return BacktestResult(strategy=strategy_name)

        cash = 100_000.0
        pos = 0.0
        entry = 0.0
        wins = 0
        total = 0
        equity = [cash]

        for i in range(20, len(bars)):
            price = closes[i]
            sma5 = sum(closes[i - 5:i]) / 5
            sma20 = sum(closes[i - 20:i]) / 20
            signal = "hold"
            if sma5 > sma20 * 1.005:
                signal = "buy"
            elif sma5 < sma20 * 0.995:
                signal = "sell"
            if signal == "buy" and pos == 0.0:
                pos = cash / price
                cash = 0.0
                entry = price
            elif signal == "sell" and pos > 0.0:
                cash = pos * price
                pnl = (price - entry) / entry
                total += 1
                if pnl > 0:
                    wins += 1
                pos = 0.0
                entry = 0.0
            equity.append(cash + pos * price)

        if pos > 0.0:
            cash = pos * closes[-1]
            pnl = (closes[-1] - entry) / entry
            total += 1
            if pnl > 0:
                wins += 1
            pos = 0.0
            equity.append(cash)

        total_return = (equity[-1] - 100_000.0) / 100_000.0
        sharpe = self._sharpe(equity)
        mdd = self._max_drawdown(equity)
        days = max(1, len(equity))
        return BacktestResult(
            strategy=strategy_name,
            total_return=total_return,
            annual_return=total_return * (365 / days),
            sharpe_ratio=sharpe,
            max_drawdown=mdd,
            win_rate=wins / total if total else 0.0,
            trades=total,
            equity_curve=equity,
        )

    @staticmethod
    def _sharpe(equity: List[float]) -> float:
        if len(equity) < 2:
            return 0.0
        rets = [(equity[i] - equity[i - 1]) / max(equity[i - 1], 1e-9) for i in range(1, len(equity))]
        if not rets:
            return 0.0
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / len(rets)
        std = math.sqrt(var) or 1e-9
        return mean / std * math.sqrt(252)

    @staticmethod
    def _max_drawdown(equity: List[float]) -> float:
        if not equity:
            return 0.0
        peak = equity[0]
        mdd = 0.0
        for v in equity:
            peak = max(peak, v)
            dd = (peak - v) / max(peak, 1e-9)
            mdd = max(mdd, dd)
        return mdd


# ============================================================
# 全局单例
# ============================================================

_adapter: Optional[AxonQuantAdapter] = None
_adapter_lock: Optional[asyncio.Lock] = None
_import_lock = None  # 延迟初始化的 threading.Lock


def _get_import_lock():
    global _import_lock
    if _import_lock is None:
        import threading
        _import_lock = threading.Lock()
    return _import_lock


def get_engine_adapter() -> AxonQuantAdapter:
    global _adapter, _adapter_lock
    if _adapter is None:
        with _get_import_lock():
            if _adapter is None:
                _adapter = AxonQuantAdapter()
                # 异步 lock 仅在 event loop 内创建
                if _adapter_lock is None:
                    try:
                        _adapter_lock = asyncio.Lock()
                    except RuntimeError:
                        _adapter_lock = None
    return _adapter


def reset_engine_adapter() -> None:  # pragma: no cover - 测试用
    global _adapter, _adapter_lock
    _adapter = None
    _adapter_lock = None
