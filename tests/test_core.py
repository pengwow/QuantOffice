"""独立模式 + 插件模式共享业务代码的单元测试。"""
from __future__ import annotations

import asyncio

import pytest

from quant_office.agents import AGENT_REGISTRY
from quant_office.core.agent_scheduler import (
    AgentScheduler,
    get_agent_scheduler,
    reset_agent_scheduler,
)
from quant_office.core.engine_adapter import (
    AxonQuantAdapter,
    OrderRequest,
    Portfolio,
    get_engine_adapter,
    reset_engine_adapter,
)
from quant_office.core.event_publisher import (
    EventPublisher,
    get_event_publisher,
    reset_event_publisher,
)
from quant_office.core.websocket_manager import (
    WebSocketManager,
    get_websocket_manager,
    reset_websocket_manager,
)
from quant_office.config import get_settings


@pytest.fixture(autouse=True)
def _reset_singletons():
    """每个测试前后重置全局单例，避免相互污染。"""
    reset_engine_adapter()
    reset_websocket_manager()
    reset_event_publisher()
    reset_agent_scheduler()
    yield
    reset_engine_adapter()
    reset_websocket_manager()
    reset_event_publisher()
    reset_agent_scheduler()


def test_settings_basic():
    s = get_settings()
    assert s.app_name == "QuantOffice"
    assert s.mode in ("standalone", "plugin")


def test_engine_adapter_pre_trade_check():
    engine = get_engine_adapter()
    portfolio = Portfolio(cash=100_000.0, positions={})
    order = OrderRequest(symbol="BTCUSDT", side="buy", quantity=0.01, price=30_000.0)
    res = engine.pre_trade_check(order, portfolio)
    assert res.passed is True


def test_engine_adapter_position_limit():
    engine = get_engine_adapter()
    portfolio = Portfolio(cash=100_000.0, positions={})
    # 超过单笔仓位上限（默认 100%）
    order = OrderRequest(symbol="BTCUSDT", side="buy", quantity=10, price=30_000.0)
    res = engine.pre_trade_check(order, portfolio)
    assert res.passed is False
    assert res.failed_check == "position_limit"


def test_engine_adapter_backtest_runs():
    engine = get_engine_adapter()
    bars = [
        {"open": 100, "high": 101, "low": 99, "close": 100 + i * 0.1, "volume": 1, "sma5": 100, "sma20": 99}
        for i in range(120)
    ]
    result = engine.run_backtest("momentum", bars)
    assert result.strategy == "momentum"
    assert len(result.equity_curve) > 0
    assert isinstance(result.total_return, float)


@pytest.mark.asyncio
async def test_websocket_manager_publish_subscribe():
    ws = WebSocketManager()
    received: list = []

    class _FakeWS:
        def __init__(self):
            self.accepted = False
            self.sent: list[str] = []

        async def accept(self):
            self.accepted = True

        async def send_text(self, data: str):
            self.sent.append(data)

        async def receive_text(self):
            return ""

    client = _FakeWS()
    await ws.connect(client)
    # 手动订阅
    ws._subscriptions[client].add("market_data")  # noqa: SLF001
    await ws.publish("market_data", {"price": 12345})
    await ws.disconnect(client)
    assert client.accepted is True
    assert any("market_data" in m for m in client.sent)


@pytest.mark.asyncio
async def test_event_publisher_dispatch():
    pub: EventPublisher = get_event_publisher()
    received: list = []

    async def handler(payload):
        received.append(payload)

    pub.subscribe("ping", handler)
    await pub.publish("ping", {"v": 1})
    assert received == [{"v": 1}]


@pytest.mark.asyncio
async def test_agent_scheduler_lifecycle():
    scheduler: AgentScheduler = get_agent_scheduler()
    assert len(scheduler.all_agents()) == 0
    await scheduler.start_all()
    assert len(scheduler.all_agents()) == 6
    for agent in scheduler.all_agents():
        assert agent.agent_id in AGENT_REGISTRY
    await scheduler.stop_all()
    assert len(scheduler.all_agents()) == 0


@pytest.mark.asyncio
async def test_data_agent_load_and_query():
    scheduler = get_agent_scheduler()
    await scheduler.start_all()
    data = scheduler.get("data")
    res = await data.handle("load_data", {"symbol": "BTCUSDT", "timeframe": "1h", "limit": 100})
    assert res["ok"] is True
    assert res["result"]["bars"] == 100
    price = await data.handle("query_market", {"symbol": "BTCUSDT"})
    assert "price" in price["result"]


@pytest.mark.asyncio
async def test_strategy_agent_run_backtest():
    scheduler = get_agent_scheduler()
    await scheduler.start_all()
    strategy = scheduler.get("strategy")
    # 先加载数据
    await scheduler.get("data").handle("load_data", {"symbol": "BTCUSDT", "timeframe": "1h", "limit": 200})
    res = await strategy.handle("run_backtest", {"strategy": "momentum", "symbol": "BTCUSDT", "timeframe": "1h"})
    assert res["ok"] is True
    assert "total_return" in res["result"]


@pytest.mark.asyncio
async def test_execution_agent_place_and_fill():
    scheduler = get_agent_scheduler()
    await scheduler.start_all()
    exec_agent = scheduler.get("execution")
    res = await exec_agent.handle(
        "place_order",
        {"symbol": "BTCUSDT", "side": "buy", "quantity": 0.01, "order_type": "market"},
    )
    result = res["result"]
    assert result["symbol"] == "BTCUSDT"
    assert result["status"] in ("filled", "submitted")
    if result["status"] == "filled":
        assert result["filled_price"] is not None


@pytest.mark.asyncio
async def test_risk_agent_check_and_alert():
    scheduler = get_agent_scheduler()
    await scheduler.start_all()
    risk = scheduler.get("risk")
    # 正常单
    res = await risk.handle(
        "check_risk",
        {"symbol": "BTCUSDT", "side": "buy", "quantity": 0.01, "price": 30_000.0},
    )
    assert res["result"]["passed"] is True
    # 超限单
    res = await risk.handle(
        "check_risk",
        {"symbol": "BTCUSDT", "side": "buy", "quantity": 100, "price": 30_000.0},
    )
    assert res["result"]["passed"] is False
    alerts = risk.recent_alerts()
    assert len(alerts) >= 1


@pytest.mark.asyncio
async def test_report_agent_generate():
    scheduler = get_agent_scheduler()
    await scheduler.start_all()
    # 先生成一笔成交
    await scheduler.get("execution").handle(
        "place_order",
        {"symbol": "BTCUSDT", "side": "buy", "quantity": 0.01, "order_type": "market"},
    )
    res = await scheduler.get("report").handle("generate_report", {"type": "daily"})
    result = res["result"]
    assert result["type"] == "daily"
    assert "metrics" in result
    assert result["metrics"]["fills"] >= 1
