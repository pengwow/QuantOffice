"""StrategyAgent — 策略开发 / 回测 / RL 训练。"""
from __future__ import annotations

from typing import Any, Dict, List

from .base import AgentRole, BaseAgent


# 简单预置策略
PRESET_STRATEGIES: Dict[str, str] = {
    "momentum": "5/20 SMA 动量策略",
    "mean_reversion": "均值回归策略",
    "buy_and_hold": "买入持有基准",
}


class StrategyAgent(BaseAgent):
    agent_id = "strategy"
    name = "策略研究员 StrategyAgent"
    role = AgentRole.STRATEGY
    workstation = "左前回测台"

    def __init__(self) -> None:
        super().__init__()
        self._strategies: Dict[str, Dict[str, Any]] = {
            name: {"name": name, "description": desc, "active": False}
            for name, desc in PRESET_STRATEGIES.items()
        }
        self._last_backtest: Dict[str, Any] = {}

    async def process(self, command: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if command == "list_strategies":
            return {"strategies": list(self._strategies.values())}
        if command == "create_strategy":
            return self._create_strategy(payload)
        if command == "activate_strategy":
            return self._activate_strategy(payload.get("name"))
        if command == "run_backtest":
            return await self._run_backtest(payload)
        raise ValueError(f"StrategyAgent 不支持命令: {command}")

    # ---- 业务方法 ----

    def _create_strategy(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        name = payload.get("name", "custom")
        spec = {
            "name": name,
            "description": payload.get("description", "用户自定义策略"),
            "params": payload.get("params", {}),
            "active": False,
        }
        self._strategies[name] = spec
        return spec

    def _activate_strategy(self, name: str) -> Dict[str, Any]:
        if name not in self._strategies:
            return {"error": f"策略 {name} 不存在"}
        for n, s in self._strategies.items():
            s["active"] = n == name
        return self._strategies[name]

    async def _run_backtest(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        from ..core.engine_adapter import get_engine_adapter

        strategy_name = payload.get("strategy", "momentum")
        symbol = payload.get("symbol", "BTCUSDT")
        timeframe = payload.get("timeframe", "1h")

        # 复用 DataAgent 缓存
        cache_key = f"{symbol}_{timeframe}"
        data_agent = self._peer_data_agent()
        bars = data_agent._cache.get(cache_key) if data_agent else None
        if not bars:
            # 触发数据加载
            if data_agent:
                await data_agent.handle("load_data", {"symbol": symbol, "timeframe": timeframe, "limit": 300})
                bars = data_agent._cache.get(cache_key)

        if not bars:
            return {"error": f"无 {symbol} 数据"}

        result = get_engine_adapter().run_backtest(strategy_name, bars)
        out = result.to_dict()
        out["symbol"] = symbol
        out["timeframe"] = timeframe
        self._last_backtest = out
        return out

    @staticmethod
    def _peer_data_agent() -> Any:
        """在已启动的调度器中查找 DataAgent 实例。"""
        try:
            from ..core.agent_scheduler import get_agent_scheduler
            return get_agent_scheduler().get("data")
        except Exception:
            return None

    # ---- 心跳 ----

    async def collect_metrics(self) -> Dict[str, Any]:
        base = await super().collect_metrics()
        base.update(
            {
                "strategies": len(self._strategies),
                "active": sum(1 for s in self._strategies.values() if s["active"]),
                "last_backtest_strategy": self._last_backtest.get("strategy"),
            }
        )
        return base
