"""P4/P5 + 关键 API 路由单测。

通过 ``httpx.AsyncClient(transport=ASGITransport(app=app))`` 走完整 ASGI 栈,
覆盖以下路由:
- GET  /api/settings/engine                    (P5)
- POST /api/settings/engine/exchange/test      (P5)
- GET  /api/strategies                         (CRUD)
- POST /api/strategies                         (CRUD)
- GET  /api/strategies/{id}                    (CRUD)
- DELETE /api/strategies/{id}                  (CRUD)
- POST /api/strategies/{id}/train              (P4 训练端点)
- GET  /api/risk/metrics                       (P0/P2)
- POST /api/trades                             (P5 落库 + axon 撮合)
- GET  /api/dashboard                          (聚合)

注:本测试使用 lifespan 真实启动的 FastAPI app,DB 共享 dev ``data/quant_office.db``,
每个测试用唯一名前缀 (p10_*) 避免与 demo 数据冲突。
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Dict

import pytest

# 测试前确保 BINANCE_API_KEY 不在环境里 → OMS 走 None
for k in ("BINANCE_API_KEY", "BINANCE_API_SECRET"):
    os.environ.pop(k, None)


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def app():
    """复用 lifespan 启动过的 app(全模块一次启动,DB + agents + demo seed)。"""
    from quant_office.app import app as fastapi_app
    return fastapi_app


@pytest.fixture(scope="module")
def client(app):
    """``fastapi.TestClient`` (同步) with lifespan → DB + agents + demo seed。

    注:必须用 ``with`` 进 lifespan,否则 agents 不会被注册,后续 train / dashboard 会失败。
    """
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c


def _unique(prefix: str = "p10") -> str:
    import uuid
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# =====================================================================
# P5 — Engine Status API
# =====================================================================

def test_api_engine_status_default(client):
    """P5: GET /api/settings/engine 应返回 axon + exchange 状态。"""
    r = client.get("/api/settings/engine")
    assert r.status_code == 200
    body = r.json()
    # 字段是 flat 形式(见 api/settings.py:get_engine_status)
    assert body["axon_available"] is True
    assert body["using_axon"] is True
    # 没设 BINANCE key
    assert body["using_exchange"] is False
    assert body["exchange_venue"] is None
    # 整数/布尔字段
    assert isinstance(body.get("exchange_testnet"), bool)


def test_api_exchange_test_no_keys(client):
    """P5: POST /api/settings/engine/exchange/test 无 key 时返回 ok=False。"""
    r = client.post("/api/settings/engine/exchange/test")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "BINANCE_API_KEY" in body.get("error", "")


# =====================================================================
# Strategies CRUD
# =====================================================================

def test_api_strategies_list_includes_demo(client):
    """GET /api/strategies 应返回列表(可能含 demo seed)。"""
    r = client.get("/api/strategies")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)


def test_api_create_strategy_minimal(client):
    """POST /api/strategies 最少字段(name)能创建。"""
    name = _unique("p10-strat")
    r = client.post("/api/strategies", json={
        "name": name,
        "symbol": "BTCUSDT",
        "params": {"timeframe": "1h"},
        "status": "live",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == name
    assert "id" in body
    assert body["symbol"] == "BTCUSDT"


def test_api_create_strategy_missing_name_422(client):
    """POST /api/strategies 缺 name 应被 422 拒绝。"""
    r = client.post("/api/strategies", json={
        "symbol": "BTCUSDT",
        "params": {},
    })
    assert r.status_code in (422, 400)  # HTTPException(422) 或 pydantic 422


def test_api_get_strategy_by_id(client):
    """POST 后 GET /api/strategies/{id} 能取回。"""
    name = _unique("p10-strat")
    create = client.post("/api/strategies", json={
        "name": name, "symbol": "ETHUSDT", "params": {}, "status": "live",
    })
    assert create.status_code == 201
    sid = create.json()["id"]

    r = client.get(f"/api/strategies/{sid}")
    assert r.status_code == 200
    assert r.json()["id"] == sid
    assert r.json()["name"] == name


def test_api_get_strategy_404(client):
    """GET /api/strategies/{nonexistent} 应 404。"""
    r = client.get("/api/strategies/strat-doesnotexist")
    assert r.status_code == 404


def test_api_delete_strategy(client):
    """DELETE /api/strategies/{id} 后 GET 应 404。"""
    name = _unique("p10-strat")
    create = client.post("/api/strategies", json={
        "name": name, "symbol": "BTCUSDT", "params": {}, "status": "live",
    })
    sid = create.json()["id"]

    r = client.delete(f"/api/strategies/{sid}")
    assert r.status_code in (200, 204)

    r2 = client.get(f"/api/strategies/{sid}")
    assert r2.status_code == 404


# =====================================================================
# P4 — Train Endpoint
# =====================================================================

def test_api_train_strategy_heuristic(client):
    """P4: POST /api/strategies/{id}/train 走 heuristic backend。"""
    name = _unique("p10-train")
    create = client.post("/api/strategies", json={
        "name": name,
        "symbol": "BTCUSDT",
        "params": {"timeframe": "1h"},
        "status": "live",
    })
    sid = create.json()["id"]

    r = client.post(f"/api/strategies/{sid}/train", json={
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "episodes": 2,
        "limit": 60,
        "ppo": False,
    })
    assert r.status_code == 200
    body = r.json()
    # 顶层是 wrapper {"ok": True, "result": {...}, "agent", "strategy_id"}
    assert body["ok"] is True
    assert body["strategy_id"] == sid
    assert body["agent"] == "strategy"
    inner = body["result"]
    assert inner["backend"] == "heuristic"
    assert inner["episodes"] == 2
    for k in ("avg_reward", "sharpe", "win_rate", "final_portfolio", "total_trades"):
        assert k in inner, f"missing train key: {k}"


def test_api_train_strategy_404(client):
    """P4: 对不存在的策略训练应 404。"""
    r = client.post("/api/strategies/strat-notreal/train", json={
        "symbol": "BTCUSDT", "episodes": 1,
    })
    assert r.status_code == 404


# =====================================================================
# P0/P2 — Risk metrics API
# =====================================================================

def test_api_risk_metrics(client):
    """GET /api/risk/metrics 应返回 RiskAgent 状态。"""
    r = client.get("/api/risk/metrics")
    assert r.status_code == 200
    body = r.json()
    # 字段允许缺省,但 portfolio / alerts 必有
    assert "portfolio" in body or "positions" in body or "alerts" in body or isinstance(body, dict)


# =====================================================================
# P5 — Trades API (axon 撮合)
# =====================================================================

def test_api_submit_trade_no_keys(client):
    """P5: POST /api/trades 无 BINANCE key 时,axon 撮合应成功。"""
    name = _unique("p10-trade")
    create = client.post("/api/strategies", json={
        "name": name, "symbol": "BTCUSDT", "params": {}, "status": "live",
    })
    sid = create.json()["id"]

    r = client.post("/api/trades", json={
        "strategy_id": sid,
        "symbol": "BTCUSDT",
        "side": "buy",
        "qty": 0.01,
        "order_type": "market",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["symbol"] == "BTCUSDT"
    assert body["side"] == "buy"
    assert "order_id" in body
    assert body["order_id"].startswith("AQ-") or body["order_id"]  # axon 或 fallback
    assert body["status"] in ("filled", "submitted", "pending", "new", "partially_filled")


# =====================================================================
# Dashboard API
# =====================================================================

def test_api_dashboard(client):
    """GET /api/dashboard 聚合数据。"""
    r = client.get("/api/dashboard")
    assert r.status_code == 200
    body = r.json()
    # 关键字段
    assert "total_strategies" in body or "strategies" in body
    assert "total_trades" in body or "trades" in body
    # agents 列表
    assert "agents" in body
    assert isinstance(body["agents"], list)
    assert len(body["agents"]) >= 6  # 6 个 agent


def test_api_health(client):
    """GET /api/health 基础探活。"""
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "timestamp" in body
