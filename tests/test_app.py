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
    r = client.get("/api/agents/")
    assert r.status_code == 200
    body = r.json()
    assert len(body["agents"]) == 6
    names = {a["id"] for a in body["agents"]}
    assert names == {"chief", "data", "strategy", "risk", "execution", "report"}


def test_full_workflow(client):
    # 1. 加载数据
    r = client.post(
        "/api/agents/data/command",
        json={"command": "load_data", "payload": {"symbol": "BTCUSDT", "timeframe": "1h", "limit": 200}},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True

    # 2. 跑回测
    r = client.post(
        "/api/backtests/",
        json={"strategy": "momentum", "symbol": "BTCUSDT", "timeframe": "1h"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "total_return" in body

    # 3. 下单
    r = client.post(
        "/api/trades/",
        json={"symbol": "BTCUSDT", "side": "buy", "quantity": 0.01, "order_type": "market"},
    )
    assert r.status_code == 200
    assert r.json()["status"] in ("filled", "submitted", "rejected")

    # 4. 风控指标
    r = client.get("/api/risk/metrics")
    assert r.status_code == 200

    # 5. Dashboard
    r = client.get("/api/dashboard/")
    assert r.status_code == 200
    body = r.json()
    assert "agents" in body
    assert "risk" in body
    assert "trades" in body


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
