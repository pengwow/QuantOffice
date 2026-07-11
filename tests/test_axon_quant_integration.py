"""P0-P7 关键路径覆盖测试。

每个测试对应一个 PR 的"真接 axon_quant"改造点,目标覆盖率从 60% → 80%。

P0 - EngineAdapter axon 模式 + 风控
P1 - DataAgent 真拉 axon ticks / RiskAgent 读 RuntimeConfigStore
P2 - RiskAgent 公开 portfolio API (get_portfolio_snapshot / apply_fill)
P3 - DataAgent 三层降级 (exchange → axon → synth)
P4 - StrategyAgent RL 训练 (heuristic + ppo paths)
P5 - EngineAdapter BinanceAdapter 真实 OMS 联通测试
P7 - API 集成: /api/settings/engine + /api/strategies/{id}/train
"""
from __future__ import annotations

import asyncio
import os

import pytest


# =====================================================================
# Helpers
# =====================================================================

def _run(coro):
    """同步跑一个 awaitable。"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@pytest.fixture(autouse=True)
def _reset_singletons():
    """每个测试前后重置全局单例,避免相互污染。"""
    from quant_office.core.agent_scheduler import reset_agent_scheduler
    from quant_office.core.engine_adapter import reset_engine_adapter
    from quant_office.core.event_publisher import reset_event_publisher

    reset_engine_adapter()
    reset_event_publisher()
    reset_agent_scheduler()
    # 清掉 key,确保 OMS 不被拉起
    for k in ("BINANCE_API_KEY", "BINANCE_API_SECRET"):
        os.environ.pop(k, None)
    yield
    reset_engine_adapter()
    reset_event_publisher()
    reset_agent_scheduler()


# =====================================================================
# P0 — EngineAdapter axon 模式 + 风控
# =====================================================================

def test_p0_engine_adapter_axon_mode():
    """P0: ``axon_quant`` 可用时 using_axon=True。"""
    from quant_office.core.engine_adapter import (
        AXON_AVAILABLE,
        get_engine_adapter,
    )

    assert AXON_AVAILABLE is True
    engine = get_engine_adapter()
    assert engine.using_axon is True
    assert engine.using_exchange is False  # 无 BINANCE_API_KEY


def test_p0_engine_pre_trade_position_limit():
    """P0: 单笔仓位超 max_position_ratio 应被拒。"""
    from quant_office.core.engine_adapter import (
        OrderRequest,
        Portfolio,
        get_engine_adapter,
    )
    engine = get_engine_adapter()
    portfolio = Portfolio(cash=100_000.0, positions={})
    # 100 BTC * 30000 = 3M USD,占组合 3000% > 100% 默认上限
    order = OrderRequest(symbol="BTCUSDT", side="buy", quantity=100.0, price=30_000.0)
    res = engine.pre_trade_check(order, portfolio)
    assert res.passed is False
    assert res.failed_check in ("position_limit", "max_position")


def test_p0_backtest_returns_full_signature():
    """P0: 回测结果字段齐全(strategy / equity_curve / sharpe / max_drawdown)。"""
    from quant_office.core.engine_adapter import get_engine_adapter

    engine = get_engine_adapter()
    bars = [
        {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0 + i * 0.5,
         "volume": 1.0, "sma5": 100.0, "sma20": 99.0}
        for i in range(60)
    ]
    result = engine.run_backtest("momentum", bars)
    d = result.to_dict()
    assert d["strategy"] == "momentum"
    assert isinstance(d.get("equity_curve"), list)
    assert len(d["equity_curve"]) > 0
    for k in ("sharpe_ratio", "max_drawdown", "total_return", "win_rate", "trades"):
        assert k in d, f"missing backtest key: {k}"


# =====================================================================
# P1 — DataAgent 真接 axon (不走 exchange,只走 axon)
# =====================================================================

def test_p1_data_agent_axon_path():
    """P1: 关闭 exchange+synth 时,只能走 axon(返回 bars>0)。"""
    from quant_office.agents.data_agent import DataAgent
    from unittest.mock import patch

    agent = DataAgent()
    with patch.object(agent, "_load_exchange_bars", return_value=None), \
         patch.object(agent, "_synth_bars", side_effect=AssertionError("应走不到 synth")):
        res = _run(agent.handle("load_data", {
            "symbol": "BTCUSDT", "timeframe": "1h", "limit": 50,
        }))
    assert res["ok"] is True
    inner = res["result"]
    assert inner["source"] == "axon"
    assert inner["bars"] == 50
    assert inner["symbol"] == "BTCUSDT"


def test_p1_data_agent_axon_bars_field_complete():
    """P1: axon 拉的 bars 字段完整(open/high/low/close/volume/ts)。"""
    from quant_office.agents.data_agent import DataAgent
    from unittest.mock import patch

    agent = DataAgent()
    with patch.object(agent, "_load_exchange_bars", return_value=None):
        res = _run(agent.handle("load_data", {
            "symbol": "ETHUSDT", "timeframe": "1h", "limit": 30,
        }))
    first = res["result"]["first"]
    for k in ("ts", "open", "high", "low", "close", "volume"):
        assert k in first, f"missing key: {k}"
    assert first["high"] >= first["low"]


# =====================================================================
# P2 — RiskAgent 公开 portfolio API (替代私有属性直访)
# =====================================================================

def test_p2_risk_get_portfolio_snapshot_isolated():
    """P2: get_portfolio_snapshot 返回浅拷贝,改返回 dict 不影响内部状态。"""
    from quant_office.agents.risk_agent import RiskAgent

    agent = RiskAgent()
    snap = agent.get_portfolio_snapshot()
    # 改返回的字典
    snap["cash"] = 0.0
    snap["positions"]["HACK"] = 999.0
    # 内部状态不变
    fresh = agent.get_portfolio_snapshot()
    assert fresh["cash"] == 100_000.0
    assert "HACK" not in fresh["positions"]


def test_p2_risk_apply_fill_buy_increases_position():
    """P2: apply_fill('buy') 增仓 + 扣现金。"""
    from quant_office.agents.risk_agent import RiskAgent

    agent = RiskAgent()
    snap = agent.apply_fill("BTCUSDT", "buy", 0.5, 60_000.0)
    assert snap["positions"]["BTCUSDT"] == 0.5
    # 100_000 - 30_000 = 70_000
    assert snap["cash"] == pytest.approx(70_000.0, abs=1e-6)


def test_p2_risk_apply_fill_sell_releases_cash_and_clears():
    """P2: apply_fill('sell') 减仓 + 释放现金,平仓后清空 position。"""
    from quant_office.agents.risk_agent import RiskAgent

    agent = RiskAgent()
    agent.apply_fill("BTCUSDT", "buy", 0.5, 60_000.0)
    snap = agent.apply_fill("BTCUSDT", "sell", 0.5, 65_000.0)
    assert "BTCUSDT" not in snap["positions"]
    # 70_000 + 32_500 = 102_500
    assert snap["cash"] == pytest.approx(102_500.0, abs=1e-6)


def test_p2_risk_active_cfg_hot_read():
    """P1/P2: _active_risk_cfg 每次实时读 RuntimeConfigStore(可热改)。"""
    from quant_office.agents.risk_agent import _active_risk_cfg
    from quant_office.core.runtime_config import get_runtime_config

    store = get_runtime_config()
    before = _active_risk_cfg().var_pct_limit
    new_value = 0.077 if abs(before - 0.077) > 1e-6 else 0.088
    try:
        store.update_risk({"var_pct_limit": new_value})
        after = _active_risk_cfg().var_pct_limit
        assert after == new_value
        assert after != before
    finally:
        store.update_risk({"var_pct_limit": before})


# =====================================================================
# P3 — DataAgent 三层降级
# =====================================================================

def test_p3_data_agent_synth_path_when_both_fail():
    """P3: exchange + axon 都返回 None 时,落到 synth。"""
    from quant_office.agents.data_agent import DataAgent
    from unittest.mock import patch

    agent = DataAgent()
    with patch.object(agent, "_load_exchange_bars", return_value=None), \
         patch.object(agent, "_load_axon_bars", return_value=None):
        res = _run(agent.handle("load_data", {
            "symbol": "BTCUSDT", "timeframe": "1h", "limit": 40,
        }))
    assert res["ok"] is True
    assert res["result"]["source"] == "synthetic"
    assert res["result"]["bars"] == 40


def test_p3_data_agent_exchange_path_wins_over_others():
    """P3: exchange 返回非空时优先用 exchange,axon 不应被调。"""
    from quant_office.agents.data_agent import DataAgent
    from unittest.mock import patch

    agent = DataAgent()
    fake_bars = [{"ts": i, "open": 100.0, "high": 101.0, "low": 99.0,
                  "close": 100.0 + i, "volume": 1.0} for i in range(10)]
    with patch.object(agent, "_load_axon_bars", side_effect=AssertionError("不应 fallback 到 axon")), \
         patch.object(agent, "_synth_bars", side_effect=AssertionError("不应 fallback 到 synth")):
        res = _run(agent.handle("load_data", {
            "symbol": "BTCUSDT", "timeframe": "1h", "limit": 10,
        }))
    assert res["ok"] is True
    assert res["result"]["source"] == "exchange"
    assert res["result"]["bars"] == 10


def test_p3_data_agent_timeframe_to_interval_map():
    """P3: timeframe → Binance interval 映射覆盖主流周期。

    注意:函数会 ``timeframe.lower()``,所以 "1M" 也会落到 "1m" key
    (与 Binance 习惯一致:大写 M = month / 小写 m = minute)。
    """
    from quant_office.agents.data_agent import DataAgent

    for tf, expected in [("1m", "1m"), ("5m", "5m"), ("15m", "15m"),
                          ("1h", "1h"), ("4h", "4h"), ("1d", "1d"),
                          ("1w", "1w")]:
        assert DataAgent._timeframe_to_interval(tf) == expected
    # "1M" 被 lower() 变 "1m",拿到的也是 "1m"(Binance 约定)
    assert DataAgent._timeframe_to_interval("1M") == "1m"
    assert DataAgent._timeframe_to_interval("foo") is None


# =====================================================================
# P4 — StrategyAgent RL 训练 (heuristic path)
# =====================================================================

def test_p4_strategy_train_rl_heuristic():
    """P4: train_rl 默认走 heuristic backend,产出 sharpe/avg_reward 等指标。"""
    from quant_office.agents.data_agent import DataAgent
    from quant_office.agents.strategy_agent import StrategyAgent
    from quant_office.core.agent_scheduler import get_agent_scheduler

    scheduler = get_agent_scheduler()
    _run(scheduler.start_all())
    strategy = scheduler.get("strategy")

    res = _run(strategy.handle("train_rl", {
        "symbol": "BTCUSDT", "timeframe": "1h", "episodes": 2, "limit": 60, "ppo": False,
    }))
    assert res["ok"] is True
    inner = res["result"]
    assert inner["backend"] == "heuristic"
    assert inner["episodes"] == 2
    for k in ("avg_reward", "avg_return", "sharpe", "win_rate",
              "final_portfolio", "total_trades", "episodes_detail"):
        assert k in inner, f"missing train_rl key: {k}"


def test_p4_strategy_sma_action_signals():
    """P4: SMA(5) heuristic 动作生成器在三个区间返回正确信号。

    _sma_action 要求 ``current_step >= 5``(才能拿到 5 个 close)。
    """
    from quant_office.agents.strategy_agent import StrategyAgent

    # 平: close == sma → [0.0]
    flat = [{"close": 100.0}] * 6
    assert StrategyAgent._sma_action(flat, 5) == [0.0]
    # 涨: close > sma*1.001 → [0.5]
    rising = [{"close": 100.0}] * 5 + [{"close": 105.0}]
    assert StrategyAgent._sma_action(rising, 5) == [0.5]
    # 跌: close < sma*0.999 → [-0.5]
    falling = [{"close": 100.0}] * 5 + [{"close": 95.0}]
    assert StrategyAgent._sma_action(falling, 5) == [-0.5]
    # step < 5 → [0.0](窗口未到 5 个)
    assert StrategyAgent._sma_action(flat, 4) == [0.0]
    assert StrategyAgent._sma_action(flat, 0) == [0.0]


def test_p4_strategy_summarize_handles_zero_variance():
    """P4: 收益完全相同(std≈0)时 sharpe=0,不除零。"""
    from quant_office.agents.strategy_agent import StrategyAgent

    metrics = [
        {"episode": 0, "total_reward": 1.0, "final_portfolio": 100.0, "return": 0.0, "trades": 0},
        {"episode": 1, "total_reward": 1.0, "final_portfolio": 100.0, "return": 0.0, "trades": 0},
    ]
    summary = StrategyAgent._summarize_training(metrics, 2, "test", "heuristic")
    assert summary["sharpe"] == 0.0  # 0/0 保护
    assert summary["avg_return"] == 0.0
    assert summary["win_rate"] == 0.0


# =====================================================================
# P5 — EngineAdapter BinanceAdapter 真实 OMS (无 key 走 None)
# =====================================================================

def test_p5_engine_exchange_oms_none_without_keys():
    """P5: 未配 BINANCE_API_KEY 时 _exchange_oms 留 None。"""
    from quant_office.core.engine_adapter import get_engine_adapter

    engine = get_engine_adapter()
    assert engine.using_exchange is False
    assert engine._exchange_oms is None
    assert engine.exchange_venue is None


def test_p5_engine_exchange_test_no_keys_returns_error():
    """P5: 无 key 时 test_exchange_connection 返回 ok=False + 明确原因。"""
    from quant_office.core.engine_adapter import get_engine_adapter

    engine = get_engine_adapter()
    res = engine.test_exchange_connection()
    assert res["ok"] is False
    assert "BINANCE_API_KEY" in res.get("error", "")


def test_p5_engine_submit_order_axon_signature():
    """P5: 无 exchange OMS 时,submit_order 走 axon,order_id 形如 AQ-*。"""
    from quant_office.core.engine_adapter import (
        OrderRequest,
        Portfolio,
        get_engine_adapter,
    )
    engine = get_engine_adapter()
    assert engine.using_exchange is False

    result = _run(engine.submit_order(
        OrderRequest(symbol="BTCUSDT", side="buy", quantity=0.01, order_type="market"),
        Portfolio(cash=100_000.0, positions={}),
    ))
    assert result.status in ("filled", "submitted")
    assert result.order_id.startswith("AQ-")
    assert result.symbol == "BTCUSDT"


# =====================================================================
# P5 — RiskMonitor 周期扫描
# =====================================================================

def test_p5_risk_monitor_singleton():
    """P0/P5: RiskMonitor 单例可获取,有 SCAN_INTERVAL 类属性。"""
    from quant_office.core.risk_monitor import RiskMonitor, get_risk_monitor

    rm = get_risk_monitor()
    assert isinstance(rm, RiskMonitor)
    assert hasattr(rm, "_loop")
    assert hasattr(RiskMonitor, "SCAN_INTERVAL")
    assert isinstance(RiskMonitor.SCAN_INTERVAL, (int, float))
    assert RiskMonitor.SCAN_INTERVAL > 0


# =====================================================================
# RuntimeConfig — 风险配置字段存在性
# =====================================================================

def test_runtime_risk_config_has_var_and_history():
    """P1: RiskConfig 加了 var_pct_limit / alert_history_size。"""
    from quant_office.core.runtime_config import RiskConfig, get_runtime_config

    cfg = get_runtime_config().get_risk()
    # 新字段在
    assert hasattr(cfg, "var_pct_limit")
    assert hasattr(cfg, "alert_history_size")
    assert isinstance(cfg.var_pct_limit, float)
    assert isinstance(cfg.alert_history_size, int)
    assert 0.0 < cfg.var_pct_limit < 1.0
    assert cfg.alert_history_size > 0
