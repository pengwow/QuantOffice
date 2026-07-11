"""QuantOffice 端到端联调脚本 (P7)。

链路:
  1. /api/health                 — 探活
  2. /api/settings/engine        — EngineAdapter 状态
  3. POST /api/agents/data/command{load_data}   — DataAgent 三层降级拉 bars
  4. POST /api/strategies         — 建新策略
  5. POST /api/strategies/{id}/train  — StrategyAgent RL 真接 axon_quant.TradingEnv
  6. GET  /api/risk/metrics       — 风控现状
  7. POST /api/risk/check-dry-run — 风控扫描(预演)
  8. POST /api/trades             — ExecutionAgent 真接 BinanceAdapter (无 key 走 fallback)
  9. GET  /api/dashboard          — 总览聚合
 10. 落 JSON 报告到 reports/e2e_<ts>.json

用法:
  python scripts/e2e_smoke.py [--base http://127.0.0.1:8765]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORT_DIR = REPO_ROOT / "reports"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _step(client: httpx.Client, base: str, name: str, method: str, path: str,
          body: Any = None, expect_status: int = 200) -> Dict[str, Any]:
    """单步调用,带计时 + 错误捕获。"""
    t0 = time.perf_counter()
    record: Dict[str, Any] = {
        "step": name,
        "method": method,
        "path": path,
        "ts": _now(),
    }
    try:
        if method == "GET":
            r = client.get(f"{base}{path}", timeout=30.0)
        elif method == "POST":
            r = client.post(f"{base}{path}", json=body or {}, timeout=60.0)
        else:
            raise ValueError(f"unsupported method: {method}")
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        record["status"] = r.status_code
        record["elapsed_ms"] = elapsed_ms
        try:
            record["body"] = r.json()
        except Exception:
            record["body"] = r.text[:2000]
        if r.status_code != expect_status:
            record["error"] = f"expected {expect_status}, got {r.status_code}"
    except Exception as exc:
        record["status"] = "exception"
        record["error"] = f"{type(exc).__name__}: {exc}"
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8765")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--limit", type=int, default=120)
    parser.add_argument("--episodes", type=int, default=4)
    args = parser.parse_args()

    base = args.base.rstrip("/")
    report: Dict[str, Any] = {
        "ts_start": _now(),
        "base": base,
        "params": vars(args),
        "steps": [],
        "summary": {},
    }

    with httpx.Client() as client:
        # 1. health
        report["steps"].append(_step(client, base, "health", "GET", "/api/health"))

        # 2. engine status
        report["steps"].append(_step(client, base, "engine_status", "GET", "/api/settings/engine"))

        # 3. DataAgent load_data
        report["steps"].append(_step(
            client, base, "data_load", "POST", "/api/agents/data/command",
            body={"command": "load_data", "payload": {
                "symbol": args.symbol, "timeframe": args.timeframe, "limit": args.limit,
            }},
        ))

        # 4. create strategy
        strat_name = f"e2e-strat-{int(time.time())}"
        report["steps"].append(_step(
            client, base, "create_strategy", "POST", "/api/strategies",
            body={
                "name": strat_name,
                "description": "P7 E2E smoke strategy",
                "symbol": args.symbol,
                "params": {"timeframe": args.timeframe, "episodes": args.episodes},
                "status": "live",
            },
            expect_status=201,
        ))
        # 取回 strategy_id
        strategy_id: str | None = None
        for s in reversed(report["steps"]):
            if s["step"] == "create_strategy" and isinstance(s.get("body"), dict):
                strategy_id = s["body"].get("id")
                break

        # 5. RL train
        if strategy_id:
            report["steps"].append(_step(
                client, base, "rl_train", "POST", f"/api/strategies/{strategy_id}/train",
                body={
                    "symbol": args.symbol,
                    "timeframe": args.timeframe,
                    "episodes": args.episodes,
                    "limit": args.limit,
                    "ppo": False,
                },
            ))

        # 6. risk metrics
        report["steps"].append(_step(client, base, "risk_metrics", "GET", "/api/risk/metrics"))

        # 7. risk dry-run
        report["steps"].append(_step(client, base, "risk_dry_run", "POST", "/api/risk/check-dry-run"))

        # 8. submit order (BinanceAdapter 需要 BINANCE_API_KEY,沙箱内会 fallback 到本地撮合)
        if strategy_id:
            report["steps"].append(_step(
                client, base, "submit_trade", "POST", "/api/trades",
                body={
                    "strategy_id": strategy_id,
                    "symbol": args.symbol,
                    "side": "buy",
                    "qty": 0.01,
                    "order_type": "market",
                },
                expect_status=201,
            ))

        # 9. dashboard
        report["steps"].append(_step(client, base, "dashboard", "GET", "/api/dashboard"))

    # ---- 总结 ----
    ok = sum(1 for s in report["steps"] if "error" not in s)
    fail = sum(1 for s in report["steps"] if "error" in s)
    total_ms = sum(s.get("elapsed_ms", 0) for s in report["steps"])
    # 抽取核心数据
    summary: Dict[str, Any] = {
        "total_steps": len(report["steps"]),
        "ok": ok,
        "failed": fail,
        "total_elapsed_ms": total_ms,
    }
    for s in report["steps"]:
        if s["step"] == "engine_status" and isinstance(s.get("body"), dict):
            summary["engine"] = s["body"]
        if s["step"] == "data_load" and isinstance(s.get("body"), dict):
            inner = s["body"].get("result", s["body"])
            summary["data"] = {
                "source": inner.get("source"),
                "bars": inner.get("bars"),
                "symbol": inner.get("symbol"),
                "timeframe": inner.get("timeframe"),
            }
        if s["step"] == "rl_train" and isinstance(s.get("body"), dict):
            inner = s["body"].get("result", s["body"])
            summary["rl_train"] = {
                "backend": inner.get("backend"),
                "episodes": inner.get("episodes"),
                "avg_reward": inner.get("avg_reward"),
                "avg_return": inner.get("avg_return"),
                "sharpe": inner.get("sharpe"),
                "win_rate": inner.get("win_rate"),
            }
        if s["step"] == "submit_trade" and isinstance(s.get("body"), dict):
            summary["trade"] = {
                "status": s["body"].get("status"),
                "symbol": s["body"].get("symbol"),
                "side": s["body"].get("side"),
                "qty": s["body"].get("qty"),
                "price": s["body"].get("price"),
            }
        if s["step"] == "dashboard" and isinstance(s.get("body"), dict):
            db = s["body"]
            summary["dashboard"] = {
                "total_strategies": db.get("total_strategies"),
                "active_strategies": db.get("active_strategies"),
                "total_trades": db.get("total_trades"),
                "win_rate": db.get("win_rate"),
                "total_pnl": db.get("total_pnl"),
                "total_alerts": db.get("total_alerts"),
                "axon_engine": next(
                    (a.get("role") for a in db.get("agents", []) if a.get("status") == "running"),
                    None,
                ),
            }
    report["summary"] = summary
    report["ts_end"] = _now()

    # 落盘
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = REPORT_DIR / f"e2e_{ts}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2))

    # 控制台摘要
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\n[OK] report → {out}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
