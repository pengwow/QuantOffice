"""StrategyAgent — 策略开发 / 回测 / RL 训练。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

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
        if command == "analyze_strategy":
            return await self._analyze_strategy(payload)
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

    async def _analyze_strategy(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """用 LLM 分析策略 / 回测结果（可解释性 + 改进建议）。"""
        bt = payload.get("backtest") or self._last_backtest
        if not bt:
            return {"error": "缺少回测结果，无法分析"}

        # 截取核心指标
        metrics = {
            "strategy": bt.get("strategy"),
            "symbol": bt.get("symbol"),
            "timeframe": bt.get("timeframe"),
            "total_return": bt.get("total_return"),
            "sharpe": bt.get("sharpe"),
            "max_drawdown": bt.get("max_drawdown"),
            "win_rate": bt.get("win_rate"),
            "trades": bt.get("trades"),
        }

        # 若 LLM 未配置，返回规则化建议
        try:
            from ..core.llm_client import ChatMessage, is_llm_configured, make_llm_client
        except Exception:
            is_llm_configured = lambda: False  # type: ignore
            make_llm_client = None  # type: ignore

        if not is_llm_configured() or make_llm_client is None:
            return {
                "metrics": metrics,
                "llm_used": False,
                "summary": self._rule_based_summary(metrics),
                "suggestions": self._rule_based_suggestions(metrics),
            }

        try:
            client = make_llm_client()
            sys_prompt = (
                "你是一名量化策略研究员。请用 2-3 句中文点评下面的回测结果，"
                "指出主要优点与潜在风险，并给出 1-2 条可执行的改进建议。"
                "保持简洁专业，避免空话。"
            )
            user_prompt = f"回测指标:\n{metrics}"
            resp = await client.achat(
                [
                    ChatMessage(role="system", content=sys_prompt),
                    ChatMessage(role="user", content=user_prompt),
                ],
                max_tokens=400,
            )
            text = resp.content.strip()
            return {
                "metrics": metrics,
                "llm_used": True,
                "model": resp.model,
                "elapsed_ms": resp.elapsed_ms,
                "analysis": text,
            }
        except Exception as exc:
            from ..logging_config import get_logger
            get_logger("agents.strategy").warning("LLM 分析失败，降级为规则化: %s", exc)
            return {
                "metrics": metrics,
                "llm_used": False,
                "llm_error": str(exc),
                "summary": self._rule_based_summary(metrics),
                "suggestions": self._rule_based_suggestions(metrics),
            }

    @staticmethod
    def _rule_based_summary(metrics: Dict[str, Any]) -> str:
        sharpe = metrics.get("sharpe") or 0
        mdd = metrics.get("max_drawdown") or 0
        wr = metrics.get("win_rate") or 0
        if sharpe >= 1.5 and mdd <= 0.1:
            return "策略风险调整收益良好，回撤可控，具备实盘潜力。"
        if sharpe >= 0.8:
            return "策略整体正收益，但夏普一般，建议结合仓位管理进一步优化。"
        if sharpe < 0:
            return "策略目前为负收益或回撤较大，需要重新审视信号逻辑或风控参数。"
        return f"胜率 {wr*100:.1f}%，最大回撤 {mdd*100:.1f}%，可继续观察。"

    @staticmethod
    def _rule_based_suggestions(metrics: Dict[str, Any]) -> List[str]:
        out: List[str] = []
        mdd = metrics.get("max_drawdown") or 0
        if mdd > 0.15:
            out.append("回撤偏高，建议加仓风控：单笔止损 2%、最大持仓 30%")
        sharpe = metrics.get("sharpe") or 0
        if sharpe < 1.0:
            out.append("夏普偏低，可考虑加入趋势过滤或波动率倒数加权")
        wr = metrics.get("win_rate") or 0
        if 0 < wr < 0.45:
            out.append("胜率较低，可放宽入场条件或减少交易频率")
        if not out:
            out.append("当前指标健康，可进行样本外测试 / 走实盘小仓位")
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

