"""axon_quant 引擎适配器（双模式共享）。

设计目标：
- 当 ``axon_quant`` 可用时直接调用真实 Rust 核心；
- 当不可用（开发 / CI 环境）时，自动回退到 Python 内存实现，保证业务可运行；
- 业务 Agent 永远面向统一的 ``AxonQuantAdapter`` 编程，无需感知后端。
"""
from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional

from ..config import Settings, get_settings
from ..logging_config import get_logger

logger = get_logger("core.engine")

# 尝试导入 axon_quant，失败时使用 fallback 实现
try:  # pragma: no cover - 可选依赖
    import axon_quant  # type: ignore
    from axon_quant.llm import LLMBackend, ReActAgent, SwarmOrchestrator, AgentRole  # type: ignore
    from axon_quant.risk import RiskEngine, RiskCheckRequest, RiskCheckResult  # type: ignore
    from axon_quant.oms import OrderManagementSystem, Order, OrderId, OrderType, Side  # type: ignore
    from axon_quant.exchange import BinanceAdapter, ExchangeConfig  # type: ignore
    from axon_quant.backtest import BacktestEngine  # type: ignore
    from axon_quant.rl import TradingEnv  # type: ignore
    from axon_quant.data import DataLoader  # type: ignore

    AXON_AVAILABLE = True
except Exception:  # pragma: no cover - 可选依赖
    AXON_AVAILABLE = False


# ===== 数据类（fallback 与上层共享） =====


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
    """订单请求（与 axon_quant.oms.OrderRequest 对齐）。"""

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
    status: str  # submitted / filled / rejected
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
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    trades: int = 0
    equity_curve: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy,
            "total_return": self.total_return,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "win_rate": self.win_rate,
            "trades": self.trades,
            "equity_curve": self.equity_curve,
        }


# ===== Fallback 内存实现 =====


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

        # 仓位限制
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


class _FallbackOMS:
    def __init__(self) -> None:
        self._orders: Dict[str, OrderResult] = {}
        self._seq = 0

    async def submit(self, order: OrderRequest) -> OrderResult:
        self._seq += 1
        oid = f"FALLBACK-{self._seq:08d}"
        result = OrderResult(
            order_id=oid,
            status="submitted",
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
        )
        self._orders[oid] = result
        return result


class _FallbackExchange:
    """模拟交易所 — 立即以市价成交。"""

    def __init__(self) -> None:
        self._prices: Dict[str, float] = {"BTCUSDT": 30_000.0, "ETHUSDT": 2_000.0}

    def get_price(self, symbol: str) -> float:
        return self._prices.get(symbol, 100.0)

    def set_price(self, symbol: str, price: float) -> None:
        self._prices[symbol] = price


# ===== 统一适配器 =====


class AxonQuantAdapter:
    """axon_quant 适配器（双模式共享）。

    优先使用 ``axon_quant`` 真实引擎；若未安装或初始化失败，回退到内存实现，
    业务 Agent 不感知差异。
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.using_axon = False
        self._llm: Any = None
        self._orchestrator: Any = None
        self._risk_engine: Any = None
        self._oms: Any = None
        self._exchange: Any = None
        self._data_loader: Any = None
        self._init_engine()

    # ---- 初始化 ----

    def _init_engine(self) -> None:
        if not self.settings.axon_enabled or not AXON_AVAILABLE:
            logger.info("axon_quant 不可用，使用内存 fallback 实现")
            self._risk_engine = _FallbackRiskEngine(self.settings)
            self._oms = _FallbackOMS()
            self._exchange = _FallbackExchange()
            return

        try:  # pragma: no cover - 需要真实 axon_quant 环境
            self._llm = LLMBackend.new(
                api_key=self.settings.llm_api_key,
                model=self.settings.llm_model,
                base_url=self.settings.llm_base_url,
            )
            self._orchestrator = SwarmOrchestrator()
            self._risk_engine = RiskEngine.new(
                pre_trade_check=True, circuit_breaker_enabled=True
            )
            self._oms = OrderManagementSystem.new()
            exchange_cfg = ExchangeConfig(
                api_key=self.settings.binance_api_key,
                api_secret=self.settings.binance_api_secret,
                testnet=self.settings.exchange_testnet,
            )
            self._exchange = BinanceAdapter(exchange_cfg)
            self._data_loader = DataLoader.new()
            self.using_axon = True
            logger.info("axon_quant 真实引擎已初始化")
        except Exception as exc:  # pragma: no cover
            logger.warning("axon_quant 初始化失败，回退 fallback: %s", exc)
            self._risk_engine = _FallbackRiskEngine(self.settings)
            self._oms = _FallbackOMS()
            self._exchange = _FallbackExchange()

    # ---- 公共 API ----

    def pre_trade_check(
        self, order: OrderRequest, portfolio: Portfolio
    ) -> RiskCheckOutcome:
        """预交易风控检查（同步 12ns 级别 / fallback μs 级）。"""
        if self.using_axon:  # pragma: no cover
            req = RiskCheckRequest(
                symbol=order.symbol,
                side=order.side,
                quantity=Decimal(str(order.quantity)),
                price=Decimal(str(order.price or 0)),
                portfolio=portfolio,
                timestamp=order.timestamp,
            )
            res = self._risk_engine.check(req)
            return RiskCheckOutcome(
                passed=res.passed,
                severity=getattr(res, "severity", "info"),
                failed_check=getattr(res, "failed_check", None),
                message=getattr(res, "message", None),
            )
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

        if self.using_axon:  # pragma: no cover
            o = Order(
                client_order_id=OrderId.new(),
                symbol=order.symbol,
                side=Side.Buy if order.side == "buy" else Side.Sell,
                order_type=OrderType.Market if order.order_type == "market" else OrderType.Limit,
                quantity=Decimal(str(order.quantity)),
                price=Decimal(str(order.price)) if order.price else None,
            )
            oid = await self._oms.submit_order(o)
            return OrderResult(
                order_id=str(oid),
                status="submitted",
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
            )

        return await self._oms.submit(order)

    def current_price(self, symbol: str) -> float:
        if isinstance(self._exchange, _FallbackExchange):
            return self._exchange.get_price(symbol)
        # 真实环境通过 exchange ticker 获取
        try:  # pragma: no cover
            return float(self._exchange.get_ticker(symbol).last_price)
        except Exception:
            return 0.0

    def run_backtest(
        self,
        strategy_name: str,
        bars: List[Dict[str, Any]],
        strategy: Optional[Callable[[Dict[str, Any]], str]] = None,
    ) -> BacktestResult:
        """简化版回测（fallback）。

        真实环境直接调用 ``axon_quant.backtest.BacktestEngine``；
        fallback 走简单 SMA 策略演示完整接口。
        """
        if self.using_axon:  # pragma: no cover
            engine = BacktestEngine.new(
                matching_level="L1", impact_model="almgren_chriss"
            )
            res = engine.run(strategy_name=strategy_name, bars=bars)
            return BacktestResult(
                strategy=strategy_name,
                total_return=res.total_return,
                sharpe_ratio=res.sharpe_ratio,
                max_drawdown=res.max_drawdown,
                win_rate=res.win_rate,
                trades=len(res.trades or []),
            )

        # ---- Fallback: 简单动量策略 ----
        closes = [float(b["close"]) for b in bars]
        if len(closes) < 30:
            return BacktestResult(strategy=strategy_name)

        strategy = strategy or self._default_momentum
        cash = 100_000.0
        pos = 0.0
        entry = 0.0
        wins = 0
        total = 0
        equity = [cash]

        for i in range(20, len(bars)):
            price = closes[i]
            signal = strategy(bars[i])
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

        # 强制平仓
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
        win_rate = wins / total if total else 0.0
        return BacktestResult(
            strategy=strategy_name,
            total_return=total_return,
            sharpe_ratio=sharpe,
            max_drawdown=mdd,
            win_rate=win_rate,
            trades=total,
            equity_curve=equity,
        )

    @staticmethod
    def _default_momentum(bar: Dict[str, Any]) -> str:
        sma5 = bar.get("sma5", 0.0)
        sma20 = bar.get("sma20", 0.0)
        if sma5 == 0 or sma20 == 0:
            return "hold"
        return "buy" if sma5 > sma20 * 1.005 else "sell" if sma5 < sma20 * 0.995 else "hold"

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


# ===== 全局单例 =====

_adapter: Optional[AxonQuantAdapter] = None


def get_engine_adapter() -> AxonQuantAdapter:
    global _adapter
    if _adapter is None:
        _adapter = AxonQuantAdapter()
    return _adapter


def reset_engine_adapter() -> None:  # pragma: no cover - 测试用
    global _adapter
    _adapter = None
