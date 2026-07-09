"""回测服务 — 异步任务执行。"""
from __future__ import annotations

import asyncio
from typing import Any, Dict

from ..core.agent_scheduler import get_agent_scheduler
from ..core.event_publisher import get_event_publisher


class BacktestService:
    async def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        scheduler = get_agent_scheduler()
        # 1. 加载数据
        symbol = params.get("symbol", "BTCUSDT")
        timeframe = params.get("timeframe", "1h")
        await scheduler.get("data").handle("load_data", {"symbol": symbol, "timeframe": timeframe, "limit": params.get("limit", 300)})
        # 2. 执行回测
        result = await scheduler.get("strategy").handle("run_backtest", params)
        # 3. 推送 backtest_complete 事件
        await get_event_publisher().publish(
            "backtest_complete", {"params": params, "result": result.get("result", {})}
        )
        return result.get("result", {})
