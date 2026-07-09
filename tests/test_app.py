"""FastAPI 应用 — 独立模式启动 / 健康检查 / API 端到端。"""
from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch, tmp_path):
    # 使用临时数据目录
    monkeypatch.setenv("QUANT_OFFICE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("QUANT_OFFICE_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'data' / 'qo.db'}")
    # 重新 import，避免历史单例
    import importlib
    import quant_office.config
    import quant_office.data.database as database
    importlib.reload(quant_office.config)
    importlib.reload(database)
    import quant_office.app as app_module
    importlib.reload(app_module)
    from quant_office.core import (
        agent_scheduler,
        engine_adapter,
        event_publisher,
        websocket_manager,
    )
    for mod in (agent_scheduler, engine_adapter, event_publisher, websocket_manager):
        importlib.reload(mod)
    importlib.reload(app_module)

    with TestClient(app_module.app) as c:
        yield c


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["mode"] == "standalone"


def test_info(client):
    r = client.get("/api/info")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "QuantOffice"
    assert "chief" in body["agents"]


def test_agents_list(client):
    r = client.get("/api/agents")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) == 6
    ids = {a["id"] for a in body}
    assert ids == {"chief", "data", "strategy", "risk", "execution", "report"}
    # 验证字段完整（与前端 Agent 形状一致）
    first = body[0]
    for k in ("id", "role", "name", "emoji", "color", "position", "status"):
        assert k in first, f"missing field: {k}"


def test_full_workflow(client):
    # 1. 加载数据
    r = client.post(
        "/api/agents/data/command",
        json={"command": "load_data", "payload": {"symbol": "BTCUSDT", "timeframe": "1h", "limit": 200}},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True

    # 2. 跑回测（新 API：需 strategy_id，演示数据中已有 strat-momentum-btc）
    r = client.post(
        "/api/backtests",
        json={"strategy_id": "strat-momentum-btc", "start": "2025-01-01", "end": "2025-12-31"},
    )
    assert r.status_code == 201
    body = r.json()
    assert "total_return" in body
    assert "equity_curve" in body
    assert isinstance(body["equity_curve"], list)

    # 3. 下单（POST 创建资源返回 201）
    r = client.post(
        "/api/trades",
        json={"strategy_id": "strat-momentum-btc", "symbol": "BTCUSDT", "side": "buy", "qty": 0.01},
    )
    assert r.status_code == 201
    assert r.json()["status"] in ("filled", "submitted", "rejected")

    # 4. 风控指标
    r = client.get("/api/risk/metrics")
    assert r.status_code == 200

    # 5. 风控告警列表
    r = client.get("/api/risk/alerts")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    # 6. Dashboard
    r = client.get("/api/dashboard")
    assert r.status_code == 200
    body = r.json()
    assert "agents" in body
    assert "recent_alerts" in body
    assert "equity_curve" in body
    assert "total_pnl" in body

    # 7. 策略列表（含 demo 数据）
    r = client.get("/api/strategies")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) >= 1

    # 8. 回测列表
    r = client.get("/api/backtests")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_demo_seed_and_reset(client):
    """启动时自动播种演示数据，且 /api/demo/reset 可重新注入。"""
    r = client.get("/api/strategies")
    assert r.status_code == 200
    assert len(r.json()) >= 5  # 5 个 demo 策略

    r = client.get("/api/backtests")
    assert r.status_code == 200
    assert len(r.json()) >= 4  # 4 个 demo 回测

    r = client.get("/api/trades")
    assert r.status_code == 200
    assert len(r.json()) >= 30  # 30 笔 demo 成交

    r = client.get("/api/risk/alerts")
    assert r.status_code == 200
    assert len(r.json()) >= 3  # 3 个 demo 告警

    r = client.get("/api/reports")
    assert r.status_code == 200
    assert len(r.json()) >= 1  # 1 个 demo 报告

    # 测试 reset 端点
    r = client.post("/api/demo/reset")
    assert r.status_code == 200
    seeded = r.json()["seeded"]
    assert seeded["strategy"] == 5
    assert seeded["backtest"] == 4
    assert seeded["trade"] == 30


def test_plugin_mode_registers():
    """验证插件模式能正常实例化并返回路由。"""
    from fastapi import FastAPI
    from starlette.testclient import TestClient

    from quant_office.plugin import QuantOfficePlugin

    plugin = QuantOfficePlugin()
    assert plugin.name == "quant-office"
    assert plugin.version == "0.1.0"
    assert plugin.router.prefix == "/api/plugins/quant-office"
    # 通过挂载到临时 FastAPI 应用，触发路由展开
    app = FastAPI()
    app.include_router(plugin.router)
    client = TestClient(app)
    r = client.get("/api/plugins/quant-office/health")
    assert r.status_code == 200
    assert r.json()["plugin"] == "quant-office"
    assert r.json()["mode"] == "plugin"
    r = client.get("/api/plugins/quant-office/")
    assert r.status_code == 200
    assert "agents" in r.json()
