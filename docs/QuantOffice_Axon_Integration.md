# QuantOffice + axon_quant 深度集成设计方案

## 一、axon_quant 架构深度解析

### 1.1 项目概述

[axon_quant](https://github.com/pengwow/axon_quant) 是 pengwow 开发的 **AI-Native Quantitative Trading Framework**，采用 Rust 核心 + Python 前端的架构设计。最新版本 v0.3.0，安装方式：

```bash
pip install axon_quant==0.3.0
# 或带可选依赖
pip install axon_quant[onnx,rl]
```

### 1.2 九层架构（21个 Crate）

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 9: 应用入口                                           │
│ ├─ axon-cli       CLI 工具                                  │
│ └─ axon-python    PyO3 统一入口 (axon_quant 包)             │
├─────────────────────────────────────────────────────────────┤
│ Layer 8: AI 智能体                                          │
│ ├─ axon-llm       ReAct Agent + Tool Calling + Agent Swarm  │
│ └─ axon-explain   SHAP / 反事实 / 决策报告                  │
├─────────────────────────────────────────────────────────────┤
│ Layer 7: 模型服务                                           │
│ ├─ axon-inference ONNX / Candle / tch 推理引擎              │
│ └─ axon-ensemble  模型集成（投票 / Stacking / 动态加权）    │
├─────────────────────────────────────────────────────────────┤
│ Layer 6: 训练管线                                           │
│ ├─ axon-rl        Gymnasium 环境 + VecEnv + 奖励函数        │
│ ├─ axon-hpo       Optuna 超参优化（NSGA-II 多目标）        │
│ ├─ axon-distributed Ray Actor 分布式训练                    │
│ └─ axon-walk-forward 滚动前向验证（Purged + Embargo）       │
├─────────────────────────────────────────────────────────────┤
│ Layer 5: 实验治理                                           │
│ ├─ axon-tracker   MLflow / WandB / Local / Memory 追踪      │
│ └─ axon-registry  模型注册表（SemVer + 生命周期 + 回滚）    │
├─────────────────────────────────────────────────────────────┤
│ Layer 4: 生产执行                                           │
│ ├─ axon-exchange  Binance / OKX 适配器（REST + WebSocket）  │
│ ├─ axon-risk      风控引擎（仓位 / 回撤 / VaR / 熔断）      │
│ ├─ axon-oms       订单管理系统                              │
│ └─ axon-monitor   监控告警 + 健康检查                       │
├─────────────────────────────────────────────────────────────┤
│ Layer 3: 回测引擎                                           │
│ ├─ axon-backtest  L1/L2/L3 撮合 + Almgren-Chriss 冲击模型  │
│ └─ axon-compliance 合规审计 + 日报/月报/年报                │
├─────────────────────────────────────────────────────────────┤
│ Layer 2: 数据服务                                           │
│ └─ axon-data      Arrow 列式存储 + CSV/Parquet + 特征管道   │
├─────────────────────────────────────────────────────────────┤
│ Layer 1: 核心类型                                           │
│ └─ axon-core      时间戳/价格/数量/订单/事件/队列/组合/SIMD │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 关键性能指标

| 指标 | 数值 |
|---|---|
| 回测吞吐 | > 1M events/sec |
| 撮合延迟 | < 1μs (P99) |
| 风控检查 | 12ns (AtomicBool 熔断 + HashMap 仓位) |
| 订单提交 | 1.2μs |
| RL 训练 | > 10K steps/sec (8 env VecEnv) |
| 测试用例 | 1200+ Rust + 24 Python |

### 1.4 Python API 顶层模块

| Python 模块 | Crate | 核心功能 | 主要类型 |
|---|---|---|---|
| `axon_quant.rl` | axon-rl | Gymnasium 交易环境 | `TradingEnv`, `ActionSpace`, `RewardFn` |
| `axon_quant.llm` | axon-llm | LLM Agent + ReAct | `LLMBackend`, `ReActAgent`, `ToolDefinition` |
| `axon_quant.backtest` | axon-backtest | 事件驱动回测 | `BacktestEngine`, `MatchingEngine` |
| `axon_quant.exchange` | axon-exchange | 交易所适配器 | `BinanceAdapter`, `OkxAdapter` |
| `axon_quant.risk` | axon-risk | 风控引擎 | 预交易检查 / 熔断 / VaR |
| `axon_quant.oms` | axon-oms | 订单管理 | 订单状态机 / Portfolio |
| `axon_quant.inference` | axon-inference | 模型推理 | `InferenceEngine`, `OnnxBackend` |
| `axon_quant.hpo` | axon-hpo | 超参优化 | `HPOConfig`, `StudyConfig` |
| `axon_quant.tracker` | axon-tracker | 实验追踪 | `ExperimentTracker` |
| `axon_quant.registry` | axon-registry | 模型注册 | `ModelRegistry`, `ModelVersion` |
| `axon_quant.explain` | axon-explain | 可解释性 | `KernelSHAP`, `CounterfactualGenerator` |
| `axon_quant.ensemble` | axon-ensemble | 模型集成 | `DynamicWeightedEnsemble` |

### 1.5 Agent Swarm 架构（与 QuantOffice 天然对应）

axon_quant 内置 **Agent Swarm** 多智能体协作框架，采用 Actor 模型：

- **MarketAgent**：市场分析与信号生成
- **RiskAgent**：预交易风控评估与合规检查
- **ExecutionAgent**：订单执行（TWAP/VWAP 策略）
- **AuditAgent**：决策日志与合规报告
- **SwarmOrchestrator**：Agent 生命周期管理、消息路由、自动扩缩容

这与 QuantOffice 的 1+5 Agent 设计**高度重合**，为深度集成提供了天然基础。

---

## 二、QuantOffice Agent 架构与 axon_quant 对齐方案

### 2.1 映射关系

| QuantOffice Agent | axon_quant 对应模块 | 集成方式 | 职责对齐 |
|---|---|---|---|
| **ChiefTrader** (主 Agent) | `axon-llm.SwarmOrchestrator` + `ReActAgent` | 封装为调度器 | 统筹调度、自然语言指令解析、任务分发 |
| **DataAgent** | `axon-data` + `axon-core` | 直接调用 | 行情数据获取、Arrow 列式存储、特征工程 |
| **StrategyAgent** | `axon-rl.TradingEnv` + `axon-backtest.BacktestEngine` | 封装为策略工厂 | 策略开发、回测执行、RL 训练、信号生成 |
| **RiskAgent** | `axon-risk` 风控引擎 | 直接调用 | 仓位监控、VaR 计算、熔断、预交易检查 |
| **ExecutionAgent** | `axon-oms` + `axon-exchange` | 封装为执行器 | 订单管理、TWAP/VWAP、Binance/OKX 下单 |
| **ReportAgent** | `axon-compliance` + `axon-explain` | 封装为报告生成器 | 合规审计、SHAP 可解释性、决策报告 |

### 2.2 核心集成代码示例

#### ChiefTrader — 基于 SwarmOrchestrator 的调度中枢

```python
"""ChiefTrader Agent — 基于 axon_quant.llm 的 SwarmOrchestrator 封装"""
import asyncio
from typing import Dict, Any, List
from axon_quant import (
    ReActAgent, LLMBackend, ToolDefinition, Message,
    SwarmOrchestrator, AgentRole
)
from axon_quant.risk import RiskCheckRequest
from axon_quant.oms import OrderRequest

class ChiefTraderAgent:
    """首席交易员 — 统筹全局的主 Agent
    
    基于 axon_quant 的 SwarmOrchestrator 实现，通过 ReAct 推理循环
    理解用户自然语言指令，拆解任务并分发给各副 Agent。
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # 初始化 LLM 后端（支持 OpenAI / DeepSeek / 本地模型）
        self.llm = LLMBackend.new(
            api_key=config["llm_api_key"],
            model=config.get("llm_model", "deepseek-chat"),
            base_url=config.get("llm_base_url", "https://api.deepseek.com"),
        )
        
        # 初始化 ReAct Agent（带 SafetyMode 风控）
        self.react_agent = ReActAgent(
            llm=self.llm,
            safety_mode=True,  # 启用风控安全检查
            max_iterations=10,
        )
        
        # 注册内置交易工具
        self._register_tools()
        
        # 初始化 SwarmOrchestrator
        self.orchestrator = SwarmOrchestrator()
        self._setup_swarm()
    
    def _register_tools(self):
        """注册 ReAct Agent 可调用的交易工具"""
        tools = [
            ToolDefinition(
                name="query_portfolio",
                description="查询当前投资组合状态",
                parameters={"type": "object", "properties": {}},
            ),
            ToolDefinition(
                name="analyze_market",
                description="分析指定交易对的市场数据",
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "timeframe": {"type": "string", "default": "1h"},
                    },
                    "required": ["symbol"],
                },
            ),
            ToolDefinition(
                name="place_order",
                description="提交交易订单（需通过 RiskAgent 预检查）",
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "side": {"type": "string", "enum": ["buy", "sell"]},
                        "quantity": {"type": "number"},
                        "order_type": {"type": "string", "default": "market"},
                    },
                    "required": ["symbol", "side", "quantity"],
                },
            ),
            ToolDefinition(
                name="run_backtest",
                description="对指定策略执行回测",
                parameters={
                    "type": "object",
                    "properties": {
                        "strategy_name": {"type": "string"},
                        "start_date": {"type": "string"},
                        "end_date": {"type": "string"},
                    },
                    "required": ["strategy_name"],
                },
            ),
        ]
        self.react_agent.register_tools(tools)
    
    def _setup_swarm(self):
        """配置 Agent Swarm 各角色"""
        # MarketAgent — 市场分析与信号生成
        self.orchestrator.register_agent(
            AgentRole.MarketAgent,
            self._create_market_agent(),
        )
        # RiskAgent — 预交易风控
        self.orchestrator.register_agent(
            AgentRole.RiskAgent,
            self._create_risk_agent(),
        )
        # ExecutionAgent — 订单执行
        self.orchestrator.register_agent(
            AgentRole.ExecutionAgent,
            self._create_execution_agent(),
        )
        # AuditAgent — 决策审计
        self.orchestrator.register_agent(
            AgentRole.AuditAgent,
            self._create_audit_agent(),
        )
    
    async def process_command(self, command: str) -> Dict[str, Any]:
        """处理用户自然语言指令
        
        示例指令：
        - "分析 BTCUSDT 当前技术面并给出交易建议"
        - "对动量策略执行 2024 年回测"
        - "查询当前持仓和风险敞口"
        """
        messages = [
            Message(role="system", content="你是一位专业的量化交易指挥官。"),
            Message(role="user", content=command),
        ]
        
        # ReAct 推理循环
        response = await self.react_agent.run(messages)
        
        # 如果有工具调用，分发给对应 Agent
        if response.tool_calls:
            results = await self._dispatch_tool_calls(response.tool_calls)
            return {
                "thought": response.thought,
                "actions": results,
                "summary": await self._generate_summary(results),
            }
        
        return {"response": response.content}
    
    async def _dispatch_tool_calls(self, tool_calls: List[Any]) -> List[Dict]:
        """将工具调用分发给对应 Agent 执行"""
        results = []
        for call in tool_calls:
            agent_role = self._map_tool_to_agent(call.name)
            agent = self.orchestrator.get_agent(agent_role)
            result = await agent.execute(call.arguments)
            results.append({
                "tool": call.name,
                "agent": agent_role.value,
                "result": result,
            })
        return results
    
    def _map_tool_to_agent(self, tool_name: str) -> AgentRole:
        """将工具名称映射到 Agent 角色"""
        mapping = {
            "query_portfolio": AgentRole.MarketAgent,
            "analyze_market": AgentRole.MarketAgent,
            "place_order": AgentRole.ExecutionAgent,
            "check_risk": AgentRole.RiskAgent,
            "run_backtest": AgentRole.MarketAgent,
        }
        return mapping.get(tool_name, AgentRole.AuditAgent)
```

#### StrategyAgent — 基于 TradingEnv + BacktestEngine 的策略研发

```python
"""StrategyAgent — 基于 axon_quant.rl 和 axon_quant.backtest 的策略研发"""
from typing import Dict, Any, Optional
import numpy as np
from axon_quant import (
    TradingEnv, EnvConfig,
    DefaultObservationSpace, FeatureConfig, FeatureSource, NormalizerType,
    DiscreteActionSpace, ContinuousActionSpace, TradingDirection,
    PnLReward, SharpeReward, MultiObjectiveReward,
    BacktestEngine, MatchingEngine,
)
from axon_quant.hpo import HPOConfig, StudyConfig
from axon_quant.tracker import ExperimentTracker, MemoryTracker

class StrategyAgent:
    """策略研究员 — 负责策略开发、回测、优化与信号生成
    
    基于 axon_quant 的 TradingEnv（RL 环境）和 BacktestEngine（回测引擎）
    实现传统策略 + RL 策略的统一研发管线。
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tracker = MemoryTracker.new()  # 或使用 MLflowTracker
        self.active_strategies: Dict[str, Any] = {}
    
    def create_env(self, strategy_config: Dict[str, Any]) -> TradingEnv:
        """创建 TradingEnv 交易环境"""
        env_config = EnvConfig(
            initial_capital=strategy_config.get("initial_capital", 100_000.0),
            transaction_cost=strategy_config.get("transaction_cost", 0.001),
            slippage=strategy_config.get("slippage", 0.0005),
            max_position_ratio=strategy_config.get("max_position_ratio", 1.0),
            max_steps=strategy_config.get("max_steps", 1000),
            symbol=strategy_config.get("symbol", "BTCUSDT"),
            return_window=252,
        )
        
        # 观测空间（特征工程）
        obs_space = DefaultObservationSpace.new(
            window_size=strategy_config.get("window_size", 20),
            features=[
                FeatureConfig(
                    name="close",
                    source=FeatureSource.PriceField("close"),
                    normalizer=NormalizerType.ZScore,
                    clip_range=(-5.0, 5.0),
                ),
                FeatureConfig(
                    name="volume",
                    source=FeatureSource.VolumeField("volume"),
                    normalizer=NormalizerType.ZScore,
                ),
                FeatureConfig(
                    name="rsi",
                    source=FeatureSource.RSI(14),
                    normalizer=NormalizerType.MinMax,
                ),
                FeatureConfig(
                    name="sma_diff",
                    source=FeatureSource.SMA crossover(10, 30),
                    normalizer=NormalizerType.ZScore,
                ),
            ],
        )
        
        # 动作空间
        action_type = strategy_config.get("action_type", "discrete")
        if action_type == "discrete":
            action_space = DiscreteActionSpace.new(
                n_quantity_bins=strategy_config.get("n_bins", 5),
                direction=TradingDirection.Both,
            )
        else:
            action_space = ContinuousActionSpace.new(
                action_dim=1,
                low=-1.0,
                high=1.0,
            )
        
        # 奖励函数（多目标）
        reward_fn = MultiObjectiveReward([
            PnLReward(relative=True, scale=1.0),
            SharpeReward(risk_free_rate=0.02, window=20),
        ])
        
        # 加载市场数据（Arrow RecordBatch）
        market_data = self._load_market_data(
            symbol=env_config.symbol,
            timeframe=strategy_config.get("timeframe", "1h"),
            start=strategy_config.get("start_date", "2024-01-01"),
            end=strategy_config.get("end_date", "2024-12-31"),
        )
        
        return TradingEnv.new(
            config=env_config,
            action_space=action_space,
            observation_space=obs_space,
            reward_fn=reward_fn,
            market_data=market_data,
        )
    
    async def run_backtest(self, strategy_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行策略回测
        
        使用 axon_quant.backtest.BacktestEngine 进行事件驱动回测，
        支持 L1/L2/L3 撮合级别和 Almgren-Chriss 市场冲击模型。
        """
        # 创建环境
        env = self.create_env(params)
        
        # 初始化回测引擎
        backtest_engine = BacktestEngine.new(
            env=env,
            matching_level=params.get("matching_level", "L1"),  # L1/L2/L3
            impact_model=params.get("impact_model", "almgren_chriss"),
            latency_model=params.get("latency_model", "probabilistic"),
        )
        
        # 运行回测
        with self.tracker.start_run(run_name=f"backtest_{strategy_name}"):
            self.tracker.log_param("strategy", strategy_name)
            self.tracker.log_params(list(params.items()))
            
            result = backtest_engine.run(
                strategy=self._get_strategy(strategy_name),
                initial_capital=params.get("initial_capital", 100_000.0),
            )
            
            # 记录指标
            self.tracker.log_metric("total_return", result.total_return)
            self.tracker.log_metric("sharpe_ratio", result.sharpe_ratio)
            self.tracker.log_metric("max_drawdown", result.max_drawdown)
            self.tracker.log_metric("win_rate", result.win_rate)
            
        return {
            "strategy": strategy_name,
            "total_return": result.total_return,
            "sharpe_ratio": result.sharpe_ratio,
            "max_drawdown": result.max_drawdown,
            "win_rate": result.win_rate,
            "trades": result.trades,
            "equity_curve": result.equity_curve,
        }
    
    async def optimize_hyperparameters(
        self,
        strategy_name: str,
        search_space: Dict[str, Any],
        n_trials: int = 50,
    ) -> Dict[str, Any]:
        """超参数优化 — 基于 axon_quant.hpo (Optuna + NSGA-II)"""
        from axon_quant.hpo import HPOConfig, StudyConfig
        
        hpo_config = HPOConfig(
            study=StudyConfig(
                study_name=f"hpo_{strategy_name}",
                direction="Maximize",
            ),
            search_space=search_space,
            n_trials=n_trials,
            n_jobs=4,
            early_stopping=True,
        )
        
        # 运行 HPO
        best_params = await self._run_hpo(hpo_config, strategy_name)
        return best_params
```

#### RiskAgent — 基于 axon-risk 的风控官

```python
"""RiskAgent — 基于 axon_quant.risk 的风控引擎封装"""
from typing import Dict, Any, Optional
from decimal import Decimal
from axon_quant.risk import (
    RiskEngine, RiskCheckRequest, RiskCheckResult,
    PositionLimit, DrawdownLimit, VaRLimit,
    CircuitBreaker,
)
from axon_quant.oms import Portfolio

class RiskAgent:
    """风控官 — 负责仓位监控、止损止盈、VaR 计算与风险预警
    
    基于 axon_quant.risk 风控引擎，提供 12ns 级预交易检查、
    实时熔断和仓位限制管理。
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # 初始化风控引擎
        self.risk_engine = RiskEngine.new(
            pre_trade_check=True,  # 启用预交易检查
            circuit_breaker_enabled=True,
        )
        
        # 配置风险限额
        self._setup_limits(config)
        
        # 熔断器
        self.circuit_breaker = CircuitBreaker.new(
            threshold=config.get("circuit_breaker_threshold", 5),
            reset_seconds=config.get("circuit_breaker_reset_sec", 60),
        )
    
    def _setup_limits(self, config: Dict[str, Any]):
        """配置风险限额规则"""
        limits = [
            # 仓位限制
            PositionLimit(
                max_position_ratio=config.get("max_position_ratio", 1.0),
                max_position_value=config.get("max_position_value", 1_000_000.0),
            ),
            # 回撤限制
            DrawdownLimit(
                max_drawdown=config.get("max_drawdown", 0.05),  # 5%
                warning_drawdown=config.get("warning_drawdown", 0.03),  # 3%
            ),
            # VaR 限制
            VaRLimit(
                confidence=config.get("var_confidence", 0.95),
                max_var=config.get("max_var", 0.02),
                window=config.get("var_window", 252),
            ),
        ]
        
        for limit in limits:
            self.risk_engine.add_limit(limit)
    
    async def pre_trade_check(self, order: Dict[str, Any], portfolio: Portfolio) -> RiskCheckResult:
        """预交易风控检查 — 12ns 级响应
        
        在订单提交前执行，检查：
        1. 仓位限制是否超限
        2. 回撤是否触及阈值
        3. VaR 是否超标
        4. 熔断器是否触发
        """
        request = RiskCheckRequest(
            symbol=order["symbol"],
            side=order["side"],
            quantity=Decimal(str(order["quantity"])),
            price=Decimal(str(order.get("price", 0))),
            portfolio=portfolio,
            timestamp=order["timestamp"],
        )
        
        # 执行风控检查
        result = self.risk_engine.check(request)
        
        # 如果风险超限，触发警报
        if not result.passed:
            await self._trigger_alert(result)
        
        return result
    
    async def monitor_portfolio(self, portfolio: Portfolio) -> Dict[str, Any]:
        """实时监控投资组合风险指标"""
        metrics = {
            "total_value": portfolio.portfolio_value,
            "available_margin": portfolio.available_margin,
            "unrealized_pnl": portfolio.unrealized_pnl,
            "realized_pnl": portfolio.realized_pnl,
            "positions": {},
            "risk_indicators": {},
        }
        
        # 计算各仓位风险
        for symbol, position in portfolio.positions.items():
            position_risk = self.risk_engine.calculate_position_risk(position)
            metrics["positions"][symbol] = {
                "quantity": position.quantity,
                "avg_price": position.avg_price,
                "unrealized_pnl": position.unrealized_pnl,
                "var_95": position_risk.var_95,
                "margin_ratio": position_risk.margin_ratio,
            }
        
        # 组合级风险指标
        portfolio_risk = self.risk_engine.calculate_portfolio_risk(portfolio)
        metrics["risk_indicators"] = {
            "portfolio_var_95": portfolio_risk.var_95,
            "expected_shortfall": portfolio_risk.expected_shortfall,
            "beta": portfolio_risk.beta,
            "correlation_matrix": portfolio_risk.correlation_matrix,
        }
        
        return metrics
    
    async def _trigger_alert(self, result: RiskCheckResult):
        """触发风险警报"""
        alert = {
            "level": "CRITICAL" if result.severity == "high" else "WARNING",
            "type": result.failed_check,
            "message": result.message,
            "timestamp": result.timestamp,
            "suggested_action": result.suggested_action,
        }
        # 通过 WebSocket 推送到前端像素办公室
        await self._emit_risk_alert(alert)
```

#### ExecutionAgent — 基于 axon-oms + axon-exchange 的执行交易员

```python
"""ExecutionAgent — 基于 axon_quant.oms 和 axon_quant.exchange 的订单执行"""
from typing import Dict, Any, List, Optional
from decimal import Decimal
from axon_quant.oms import (
    OrderManagementSystem, Order, OrderId, OrderType, Side, TimeInForce,
    OrderStatus, Portfolio,
)
from axon_quant.exchange import (
    BinanceAdapter, OkxAdapter, ExchangeConfig, ExchangeId,
    RateLimitConfig, ReconnectConfig,
)

class ExecutionAgent:
    """执行交易员 — 负责订单拆分、滑点控制、成交确认与对账
    
    基于 axon_quant.oms 订单管理系统和 axon_quant.exchange 交易所适配器，
    支持 Binance / OKX 的 REST + WebSocket 对接，内置 TWAP/VWAP 执行策略。
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # 初始化 OMS
        self.oms = OrderManagementSystem.new()
        
        # 初始化交易所适配器
        self.exchange = self._create_exchange_adapter(config)
        
        # 执行策略配置
        self.execution_strategy = config.get("execution_strategy", "market")
    
    def _create_exchange_adapter(self, config: Dict[str, Any]):
        """创建交易所适配器"""
        exchange_id = config.get("exchange", "binance")
        
        exchange_config = ExchangeConfig(
            exchange_id=ExchangeId.Binance if exchange_id == "binance" else ExchangeId.Okx,
            api_key=config["api_key"],
            api_secret=config["api_secret"],
            testnet=config.get("testnet", True),
            rate_limit=RateLimitConfig(
                requests_per_second=10,
                orders_per_minute=60,
            ),
            reconnect=ReconnectConfig(
                max_retries=10,
                initial_backoff_ms=500,
                circuit_breaker_threshold=5,
            ),
        )
        
        if exchange_id == "binance":
            return BinanceAdapter(exchange_config)
        else:
            return OkxAdapter(exchange_config)
    
    async def execute_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "market",
        price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """执行订单"""
        # 创建订单
        order = Order(
            client_order_id=OrderId.new(),
            symbol=symbol,
            side=Side.Buy if side == "buy" else Side.Sell,
            order_type=OrderType.Market if order_type == "market" else OrderType.Limit,
            price=Decimal(str(price)) if price else None,
            quantity=Decimal(str(quantity)),
            time_in_force=TimeInForce.Gtc,
            exchange=ExchangeId.Binance,
        )
        
        # 通过 OMS 提交订单
        order_id = await self.oms.submit_order(order)
        
        # 发送到交易所
        exchange_order_id = await self.exchange.send_order(order)
        
        # 更新订单状态
        await self.oms.update_order_status(
            order_id=order_id,
            exchange_order_id=exchange_order_id,
            status=OrderStatus.Submitted,
        )
        
        return {
            "order_id": str(order_id),
            "exchange_order_id": str(exchange_order_id),
            "status": "submitted",
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
        }
    
    async def execute_twap(
        self,
        symbol: str,
        side: str,
        total_quantity: float,
        n_slices: int = 10,
        interval_seconds: int = 60,
    ) -> List[Dict[str, Any]]:
        """TWAP 时间加权平均价格执行策略"""
        slice_quantity = total_quantity / n_slices
        results = []
        
        for i in range(n_slices):
            result = await self.execute_order(
                symbol=symbol,
                side=side,
                quantity=slice_quantity,
                order_type="market",
            )
            results.append(result)
            
            # 等待下一个时间片
            if i < n_slices - 1:
                await asyncio.sleep(interval_seconds)
        
        return results
    
    async def get_portfolio(self) -> Portfolio:
        """获取当前 Portfolio 状态"""
        return await self.exchange.get_account_info()
```

#### DataAgent — 基于 axon-data 的数据分析师

```python
"""DataAgent — 基于 axon_quant.data 的数据服务封装"""
from typing import Dict, Any, List, Optional
import pyarrow as pa
from axon_quant.data import (
    DataLoader, FeaturePipeline,
    RecordBatch, BarAggregator,
)

class DataAgent:
    """数据分析师 — 负责行情数据获取、清洗、特征工程与存储管理
    
    基于 axon_quant.data 的 Arrow 列式存储和 FeaturePipeline，
    提供高性能数据处理和特征工程能力。
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.data_loader = DataLoader.new()
        self.feature_pipeline = FeaturePipeline.new()
        
        # 数据源配置
        self.data_sources = config.get("data_sources", ["binance", "csv"])
        self.storage_format = config.get("storage_format", "parquet")
    
    async def load_market_data(
        self,
        symbol: str,
        timeframe: str = "1h",
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> pa.RecordBatch:
        """加载市场数据 — 返回 Arrow RecordBatch
        
        支持数据源：Binance API / CSV / Parquet / Mock 数据
        """
        # 优先从本地 Parquet 加载
        local_path = f"./data/{symbol}_{timeframe}.parquet"
        
        try:
            data = self.data_loader.load_parquet(local_path)
        except FileNotFoundError:
            # 从交易所 API 获取
            data = await self._fetch_from_exchange(symbol, timeframe, start, end)
            # 缓存到本地 Parquet
            self.data_loader.save_parquet(data, local_path)
        
        return data
    
    async def compute_features(
        self,
        data: pa.RecordBatch,
        features: List[str],
    ) -> pa.RecordBatch:
        """计算技术指标特征
        
        支持的特征：rsi, sma, ema, macd, bollinger, atr, obv, etc.
        """
        pipeline = self.feature_pipeline
        
        for feature_name in features:
            match feature_name:
                case "rsi":
                    pipeline.add_rsi(period=14)
                case "sma":
                    pipeline.add_sma(period=20)
                case "ema":
                    pipeline.add_ema(period=12)
                case "macd":
                    pipeline.add_macd(fast=12, slow=26, signal=9)
                case "bollinger":
                    pipeline.add_bollinger(period=20, std_dev=2.0)
                case "atr":
                    pipeline.add_atr(period=14)
        
        return pipeline.transform(data)
    
    async def aggregate_bars(
        self,
        data: pa.RecordBatch,
        target_timeframe: str,
    ) -> pa.RecordBatch:
        """K 线聚合 — 如 1min -> 1h"""
        aggregator = BarAggregator.new(target=target_timeframe)
        return aggregator.aggregate(data)
```

#### ReportAgent — 基于 axon-compliance + axon-explain 的报告专员

```python
"""ReportAgent — 基于 axon_quant.compliance 和 axon_quant.explain 的报告生成"""
from typing import Dict, Any, List
from axon_quant.compliance import ComplianceEngine, ReportType
from axon_quant.explain import (
    KernelSHAP, CounterfactualGenerator, ReportGenerator,
)

class ReportAgent:
    """报告专员 — 负责绩效归因、合规审计、可解释性报告生成
    
    基于 axon_quant.compliance 合规审计引擎和 axon_quant.explain
    可解释性引擎，自动生成日报 / 月报 / 年报，包含 SHAP 特征归因
    和反事实分析。
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.compliance_engine = ComplianceEngine.new()
        self.shap_explainer = KernelSHAP.new()
        self.counterfactual = CounterfactualGenerator.new()
        self.report_generator = ReportGenerator.new()
    
    async def generate_daily_report(
        self,
        portfolio: Dict[str, Any],
        trades: List[Dict[str, Any]],
        date: str,
    ) -> Dict[str, Any]:
        """生成日报"""
        # 合规检查
        compliance_result = self.compliance_engine.check_daily(trades)
        
        # 绩效指标
        metrics = self._calculate_metrics(portfolio, trades)
        
        # SHAP 特征归因（如果有模型预测）
        shap_values = self.shap_explainer.explain(trades)
        
        report = {
            "date": date,
            "type": "daily",
            "compliance": compliance_result,
            "metrics": metrics,
            "shap_attribution": shap_values,
            "trades_summary": self._summarize_trades(trades),
        }
        
        return report
    
    async def generate_explainability_report(
        self,
        trade: Dict[str, Any],
        model_prediction: Dict[str, Any],
    ) -> Dict[str, Any]:
        """生成单条交易的可解释性报告"""
        # SHAP 特征归因
        shap_values = self.shap_explainer.explain_single(trade, model_prediction)
        
        # 反事实分析
        counterfactual = self.counterfactual.generate(
            trade=trade,
            model_prediction=model_prediction,
            question="如果当时不买入，收益会如何变化？",
        )
        
        # 结构化决策报告
        decision_report = self.report_generator.generate(
            trade=trade,
            shap_values=shap_values,
            counterfactual=counterfactual,
        )
        
        return {
            "trade_id": trade["id"],
            "shap_values": shap_values,
            "counterfactual": counterfactual,
            "decision_report": decision_report,
        }
```

---

## 三、QuantOffice 与 axon_quant 数据流集成

```
┌─────────────────────────────────────────────────────────────────────┐
│                        用户层 (QuantOffice UI)                       │
│  ┌──────────────┐  ┌──────────────────────┐  ┌──────────────────┐  │
│  │ React UI Shell│  │ Pure-CSS Pixel       │  │ ECharts Dashboard│  │
│  │  (导航/面板)  │  │ Office (CSS+SVG)     │  │ (绩效可视化)      │  │
│  └──────────────┘  └──────────────────────┘  └──────────────────┘  │
│         ↑                    ↑                      ↑               │
│         └────────────────────┴──────────────────────┘               │
│                       TanStack Query + Zustand                       │
│                  (HTTP REST + WebSocket Bus)                         │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼ WebSocket / HTTP
┌─────────────────────────────────────────────────────────────────────┐
│                   服务层 (QuantOffice FastAPI)                       │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                   │
│  │  REST API   │ │  WebSocket  │ │ Agent调度   │                   │
│  │   (CRUD)    │ │  (实时推送)  │ │  (asyncio)  │                   │
│  └─────────────┘ └─────────────┘ └─────────────┘                   │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼ Python SDK 调用
┌─────────────────────────────────────────────────────────────────────┐
│                   引擎层 (axon_quant PyO3绑定)                       │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐  │
│  │  axon-data  │ │ axon-backtest│ │   axon-rl   │ │  axon-risk  │  │
│  │ Arrow/Parquet│ │  回测引擎    │ │ RL训练环境   │ │  风控引擎    │  │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐  │
│  │ axon-exchange│ │  axon-oms   │ │ axon-llm    │ │ axon-explain│  │
│  │ Binance/OKX │ │  订单管理    │ │ LLM Agent   │ │ SHAP/反事实 │  │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                  │
│  │  axon-hpo   │ │ axon-tracker│ │ axon-registry│                  │
│  │ 超参优化     │ │ 实验追踪     │ │ 模型注册     │                  │
│  └─────────────┘ └─────────────┘ └─────────────┘                  │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              axon-core (Rust核心 — 纳秒级性能)                │   │
│  │  Timestamp / Price / Quantity / Order / Event / Portfolio   │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 四、关键技术集成点

### 4.1 Arrow RecordBatch 零拷贝数据流

axon_quant 所有模块共享同一套 Arrow `RecordBatch`，零拷贝透传。QuantOffice 的 DataAgent 直接操作 Arrow 数据，无需格式转换：

```python
# DataAgent 加载数据
record_batch = await data_agent.load_market_data("BTCUSDT", "1h")

# StrategyAgent 直接使用同一 RecordBatch
env = strategy_agent.create_env({"symbol": "BTCUSDT"})
# TradingEnv 内部直接消费 Arrow 数据，零拷贝

# ReportAgent 基于同一数据生成报告
report = await report_agent.generate_daily_report(
    portfolio=portfolio,
    trades=trades,
)
```

### 4.2 事件驱动架构对齐

axon_quant 使用 `crossbeam-channel` bounded 100K 事件队列（零锁设计）。QuantOffice 的 WebSocket 管理器与该事件队列对接：

```python
# QuantOffice WebSocket Manager 订阅 axon_quant 事件
from axon_quant.core import EventBus

class QuantOfficeEventBridge:
    def __init__(self, ws_manager):
        self.ws_manager = ws_manager
        self.event_bus = EventBus.new()
        
    async def subscribe(self):
        # 订阅交易事件
        self.event_bus.subscribe("order_filled", self._on_order_filled)
        self.event_bus.subscribe("risk_alert", self._on_risk_alert)
        self.event_bus.subscribe("backtest_complete", self._on_backtest_complete)
        
    async def _on_order_filled(self, event):
        # 转发到前端像素办公室
        await self.ws_manager.broadcast({
            "type": "order_filled",
            "agent": "ExecutionAgent",
            "data": event,
        })
        
    async def _on_risk_alert(self, event):
        # RiskAgent 红灯警报 → 前端闪烁
        await self.ws_manager.broadcast({
            "type": "risk_alert",
            "agent": "RiskAgent",
            "severity": event.severity,
        })
```

### 4.3 RL 训练管线集成

QuantOffice 的 StrategyAgent 提供可视化 RL 训练监控：

```python
# 前端发起 RL 训练任务
POST /api/strategies/{id}/train
{
    "algorithm": "PPO",
    "timesteps": 50000,
    "n_envs": 8,
    "reward": "sharpe"
}

# StrategyAgent 调用 axon_quant.rl
from axon_quant.rl import TradingEnv, VecEnv
from stable_baselines3 import PPO

# 创建向量化环境
vec_env = VecEnv.new(n_envs=8, env_factory=lambda: trading_env)

# 训练并实时推送进度
model = PPO("MlpPolicy", vec_env)
for step in range(50000):
    model.learn(1000)
    
    # 每 1000 步推送进度到前端
    metrics = {
        "step": step,
        "mean_reward": model.logger.get("rollout/ep_rew_mean"),
        "sharpe": evaluate_sharpe(model, vec_env),
    }
    await ws_manager.broadcast({
        "type": "training_progress",
        "agent": "StrategyAgent",
        "data": metrics,
    })
```

---

## 五、性能优化策略

| 维度 | axon_quant 能力 | QuantOffice 集成优化 |
|---|---|---|
| **回测速度** | > 1M events/sec | 前端显示回测进度条，大回测任务后台异步执行 |
| **撮合延迟** | < 1μs (P99) | 实盘模式下 ExecutionAgent 状态实时同步到像素办公室 |
| **风控检查** | 12ns | RiskAgent 绿灯/黄灯/红灯状态毫秒级刷新 |
| **数据加载** | 1M tick < 15ms | DataAgent 预加载常用数据到内存，前端秒开 |
| **RL 训练** | > 10K steps/sec | 训练过程可视化（TensorBoard 嵌入 + Godot 进度动画） |
| **模型推理** | ONNX batch < 1ms | InferenceEngine 热更新时前端自动切换模型版本指示器 |

---

## 六、部署依赖

```toml
# pyproject.toml
[project]
name = "quant-office"
version = "1.0.0"
dependencies = [
    # 核心框架
    "axon_quant==0.3.0",
    
    # FastAPI 后端
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
    "websockets>=12.0",
    "celery>=5.3",
    "redis>=5.0",
    
    # 数据库
    "sqlalchemy>=2.0",
    "asyncpg>=0.29",
    "alembic>=1.13",
    
    # RL 训练（可选）
    "stable-baselines3>=2.3",
    "gymnasium>=0.29",
    "torch>=2.2",
    
    # 可视化
    "pyarrow>=15.0",
    "matplotlib>=3.8",
    "plotly>=5.19",
]

[project.optional-dependencies]
onnx = ["onnxruntime>=1.17"]
mlflow = ["mlflow>=2.11"]
wandb = ["wandb>=0.16"]
ray = ["ray[default]>=2.9"]
```

---

*文档版本: v2.0（基于 axon_quant 0.3.0）*
*日期: 2026-07-09*
