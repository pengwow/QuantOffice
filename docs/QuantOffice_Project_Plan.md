# QuantOffice — 像素风格量化交易指挥中枢

## 项目计划书

---

## 一、创意名称 + 创意介绍

**创意名称：QuantOffice（量化交易指挥中枢）**

**想解决什么问题：**
当前量化交易平台的操作界面普遍枯燥、数据堆砌严重，交易员需要在多个终端之间切换，难以直观感知策略执行状态与风险敞口。QuantOffice 将枯燥的量化交易流程转化为可视化的像素风格"虚拟办公室"，让交易员像指挥一支专业团队一样管理量化策略，大幅降低认知负荷与操作门槛。

**为什么会想到做这个：**
灵感来源于腾讯 Marvis（马维斯）的像素风格多 Agent 办公室设计。马维斯通过"1+5 Agent 协作架构"将系统级 AI 操作具象化为一个虚拟办公场景，每个 Agent 都有独立的工位和可视化状态。我们认为这种"拟物化 + 游戏化"的设计理念与量化交易场景高度契合——量化交易本身就是多角色协同（数据、策略、风控、执行、报告）的复杂系统，用像素办公室的形式呈现，既能让专业交易员获得沉浸式掌控感，也能让新手快速理解量化交易的全流程。

**大概是什么产品：**
QuantOffice 是一款基于 Godot 引擎开发的 2D 像素风格量化交易可视化系统。前端以 React 组件形式嵌入 Godot 导出的 WebAssembly 像素办公室场景，后端采用 FastAPI + Python 架构，底层量化执行引擎集成 axon_quant。用户通过浏览器即可访问一个活生生的"量化交易办公室"：首席交易员（主 Agent）坐镇中央，数据分析师、策略研究员、风控官、执行交易员、报告专员各司其职，实时显示行情数据、策略状态、风险指标与交易执行进度。

---

## 二、目标用户及痛点

**面向哪些用户：**
- 个人量化交易者（有编程基础，希望降低策略监控成本）
- 小型量化私募团队（3-10人，需要轻量级协同与可视化工具）
- 量化交易教育培训机构（需要直观的教学演示系统）
- 对量化交易感兴趣的开发者与技术爱好者

**在什么场景下使用：**
- 日常策略监控：开盘期间实时观察多个策略的运行状态与健康度
- 策略回测审查：查看历史回测的绩效报告与可视化分析
- 风险事件响应：当风险指标触发阈值时，通过像素办公室的"警报动画"第一时间感知
- 团队协同复盘：多人同时在线查看办公室状态，讨论策略调整
- 量化交易教学：向学生/客户演示量化交易的完整工作流

**当前痛点：**
- **信息过载**：传统量化终端（如 Jupyter Notebook、终端脚本）以文本和表格为主，策略一多就眼花缭乱
- **缺乏状态感知**：策略运行是"黑盒"，只能看日志判断是否正常运行，无法直观感知
- **切换成本高**：数据获取、策略编写、回测、风控、下单分散在不同工具中
- **学习曲线陡峭**：新人难以理解量化交易的全链路流程，缺乏"一张图讲清楚"的载体
- **情绪隔离**：纯数据界面缺乏"在场感"，长时间监控容易产生疲劳

---

## 三、价值与意义

**效率提升角度：**
QuantOffice 通过"空间隐喻"将抽象的量化交易流程映射为具象的办公室场景，将策略监控效率提升 40% 以上。交易员无需在多个窗口间切换，一个浏览器标签页即可掌握全局：左侧导航栏切换功能模块，中间办公室实时显示各 Agent 工作状态（忙碌/空闲/报警），右侧面板展示核心指标。据我们估算，这种"一目了然的指挥室"设计可将策略异常发现时间从平均 5 分钟缩短至 30 秒以内。

**社会价值角度：**
量化交易长期以来被外界误解为"神秘的赚钱机器"，QuantOffice 的像素办公室设计将量化交易的完整工作流透明化、游戏化，大幅降低公众理解门槛。对于教育场景，学生可以通过"观察办公室里的角色在做什么"来学习量化交易的各个环节；对于个人投资者，它提供了一个低门槛的入口来了解"我的钱是怎么被管理的"。这种可视化透明性有助于提升整个行业的信任度与普及率。

---

## 四、技术架构详解

### 4.1 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                     用户层 (Browser)                          │
│  ┌──────────────┐  ┌──────────────────────┐  ┌───────────┐ │
│  │ React UI Shell│  │  Godot Pixel Office  │  │  Dashboard │ │
│  │  (导航/面板)  │  │  (WASM + WebGL 2.0)  │  │ (ECharts)  │ │
│  └──────────────┘  └──────────────────────┘  └───────────┘ │
│         ↑                    ↑                      ↑       │
│         └────────────────────┴──────────────────────┘       │
│                        react-godot-bridge                    │
│                     (双向事件通信中间层)                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ WebSocket / HTTP
┌─────────────────────────────────────────────────────────────┐
│                   服务层 (FastAPI + Python)                   │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │
│  │  REST API   │ │  WebSocket  │ │  Agent调度  │            │
│  │   (CRUD)    │ │  (实时推送)  │ │  (Celery)   │            │
│  └─────────────┘ └─────────────┘ └─────────────┘            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 引擎层 (axon_quant + Python)                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │
│  │  数据获取    │ │  策略回测    │ │  实盘执行    │            │
│  │ (DataAgent) │ │(StrategyAgent)│ │(ExecutionAgent)│          │
│  └─────────────┘ └─────────────┘ └─────────────┘            │
│  ┌─────────────┐ ┌─────────────┐                            │
│  │  风险管理    │ │  报告生成    │                            │
│  │ (RiskAgent) │ │(ReportAgent) │                            │
│  └─────────────┘ └─────────────┘                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   数据层 (Data Storage)                       │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │
│  │  PostgreSQL │ │    Redis    │ │  ClickHouse │            │
│  │ (业务数据)   │ │  (缓存/消息) │ │ (时序数据)   │            │
│  └─────────────┘ └─────────────┘ └─────────────┘            │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 前端层：React + Godot WebAssembly

**技术选型理由：**
- **Godot 4.3+**：开源免费，2D 像素渲染能力优秀，原生支持 WebAssembly 导出，文件体积小（相比 Unity WebGL 轻量 50% 以上）
- **react-godot-4 + react-godot-bridge**：成熟的 React-Godot 桥接方案，支持双向事件通信。React 可以发送指令给 Godot（如"切换到策略 A 的工位"），Godot 可以发送事件给 React（如"RiskAgent 触发警报"）
- **ECharts / TradingVue.js**：右侧面板的 K 线图、绩效曲线等专业图表

**Godot 场景设计：**
- **等距像素办公室场景**：参考马维斯的布局，6 个工位呈 U 型排列
  - 中央：ChiefTrader（主 Agent，统筹全局，面对多屏幕）
  - 左侧：DataAgent（数据分析师，面对数据流瀑布屏）
  - 左前：StrategyAgent（策略研究员，面对代码与回测图表）
  - 右前：RiskAgent（风控官，面对红灯/绿灯风险面板）
  - 右侧：ExecutionAgent（执行交易员，面对订单簿与成交瀑布）
  - 后区：ReportAgent（报告专员，面对打印机和报表堆）
  - 休闲区：咖啡机、跑步机（马维斯同款，增加生活气息）
- **动态元素**：角色有 idle / working / alert 三种动画状态；显示器屏幕内容随数据实时变化；天花板悬挂 PnL 数字飘带

### 4.3 后端层：FastAPI + Python

**核心模块：**
- **REST API**：用户认证、策略 CRUD、历史数据查询、回测任务提交
- **WebSocket Manager**：基于 `fastapi.WebSocket` 实现 Connection Pool，支持多客户端实时订阅
  - 订阅频道：`market_data`、`agent_status`、`trade_execution`、`risk_alert`
- **Agent 调度器**：使用 Celery + Redis 实现异步任务队列
  - 每个 Agent 对应一个 Celery Worker Pool
  - 任务状态通过 WebSocket 实时推送到前端
- **数据模型**（SQLAlchemy + PostgreSQL）：
  - `users`、`strategies`、`backtests`、`trades`、`risk_events`、`agent_logs`

### 4.4 引擎层：axon_quant 集成（v0.3.0）

**axon_quant 定位：**
axon_quant 是 pengwow 开发的 AI-Native 量化交易框架，采用 Rust 核心（21 个 crate，9 层架构）+ Python 前端设计。QuantOffice 通过 Python SDK 调用其真实 API：

- **DataAgent → `axon_quant.data`**：`DataLoader` + `FeaturePipeline` + Arrow `RecordBatch` 零拷贝数据流
- **StrategyAgent → `axon_quant.rl` + `axon_quant.backtest`**：`TradingEnv`（Gymnasium 环境）+ `BacktestEngine`（L1/L2/L3 撮合）
- **RiskAgent → `axon_quant.risk`**：`RiskEngine` 提供 12ns 级预交易检查 + `CircuitBreaker` 熔断
- **ExecutionAgent → `axon_quant.oms` + `axon_quant.exchange`**：`OrderManagementSystem` + `BinanceAdapter`/`OkxAdapter`
- **ReportAgent → `axon_quant.compliance` + `axon_quant.explain`**：`ComplianceEngine` + `KernelSHAP` 可解释性
- **ChiefTrader → `axon_quant.llm`**：`SwarmOrchestrator` + `ReActAgent` 统筹 Agent 协作

**核心性能指标：**

| 指标 | 数值 |
|---|---|
| 回测吞吐 | > 1M events/sec |
| 撮合延迟 | < 1μs (P99) |
| 风控检查 | 12ns（AtomicBool 熔断 + HashMap 仓位） |
| 订单提交 | 1.2μs |
| RL 训练 | > 10K steps/sec（8 env VecEnv） |

**集成方式（真实 API）：**
```python
# FastAPI 中调用 axon_quant 真实 API
from axon_quant.llm import LLMBackend, ReActAgent, SwarmOrchestrator
from axon_quant.risk import RiskEngine, RiskCheckRequest
from axon_quant.backtest import BacktestEngine
from axon_quant.rl import TradingEnv
from axon_quant.data import DataLoader

# ChiefTrader: SwarmOrchestrator 统筹
llm = LLMBackend.new(api_key=..., model="deepseek-chat")
orchestrator = SwarmOrchestrator()

# StrategyAgent: TradingEnv + BacktestEngine
env = TradingEnv.new(config=env_config, data_loader=data_loader)
backtest = BacktestEngine.new(env=env, matching_level="L1")
result = backtest.run(strategy=my_strategy)

# RiskAgent: 12ns 预交易检查
risk_engine = RiskEngine.new(pre_trade_check=True)
result = risk_engine.check(RiskCheckRequest(symbol="BTCUSDT", ...))

# ExecutionAgent: OMS + 交易所适配器
oms = OrderManagementSystem.new()
exchange = BinanceAdapter(exchange_config)
```

### 4.5 数据层

- **PostgreSQL**：关系型业务数据（用户、策略配置、交易记录）
- **Redis**：实时缓存（最新行情、Agent 状态）、Celery 消息队列、WebSocket session 存储
- **Arrow / Parquet**：时序数据（Tick 级行情、策略信号、账户净值曲线）。通过 `axon_quant.data` 的 Arrow `RecordBatch` 实现零拷贝数据流，所有 Agent 共享同一内存格式，无需序列化开销

---

## 五、像素办公室 Agent 角色设计（1 主 + 5 副）

| Agent 名称 | 角色定位 | 工位特征 | 核心职责 | 可视化状态 |
|---|---|---|---|---|
| **ChiefTrader** | 首席交易员 | 中央指挥台，多屏幕环绕 | 接收用户指令、分配任务、汇总结果、全局监控 | 绿色=正常 / 黄色=忙碌 / 红色=异常 |
| **DataAgent** | 数据分析师 | 左侧工位，数据瀑布屏 | 行情获取、数据清洗、特征计算、存储管理 | 屏幕显示数据流动画 |
| **StrategyAgent** | 策略研究员 | 左前工位，代码编辑器+回测图表 | 策略开发、参数调优、回测执行、信号生成 | 屏幕显示 K 线与信号点 |
| **RiskAgent** | 风控官 | 右前工位，红绿灯面板 | 仓位监控、止损止盈、VaR 计算、风险预警 | 绿灯=安全 / 红灯=报警 |
| **ExecutionAgent** | 执行交易员 | 右侧工位，订单簿瀑布 | 订单拆分、滑点控制、成交确认、对账 | 屏幕显示订单流 |
| **ReportAgent** | 报告专员 | 后区工位，打印机+报表堆 | 绩效归因、报告生成、图表导出、邮件推送 | 打印机出纸动画 |

---

## 六、开发里程碑

| 阶段 | 时间 | 交付物 |
|---|---|---|
| **Phase 1: 原型验证** | Week 1-2 | Godot 像素办公室基础场景（静态布局+角色占位） |
| **Phase 2: 前端集成** | Week 3-4 | React 壳层搭建、Godot WASM 嵌入、双向通信打通 |
| **Phase 3: 后端核心** | Week 5-6 | FastAPI 基础 API、WebSocket 实时通道、PostgreSQL 模型 |
| **Phase 4: 引擎对接** | Week 7-8 | axon_quant SDK 封装、Agent 任务调度、回测流程跑通 |
| **Phase 5: 可视化联动** | Week 9-10 | Agent 状态 ↔ 像素角色动画联动、风险报警可视化 |
| **Phase 6: 优化上线** | Week 11-12 | 性能优化、压力测试、Docker 部署、文档完善 |

---

## 七、与腾讯 Marvis 的差异与致敬

**致敬点：**
- 像素风格等距办公室场景设计
- 1 主 + 5 副 Agent 的多智能体协作架构
- 左侧导航 + 中间办公室 + 右侧面板的经典三区布局
- 咖啡机、跑步机等休闲元素增添人文气息
- Token 消耗统计 → 转化为"今日策略信号数/今日交易量/今日盈亏"

**差异化创新：**
- **领域聚焦**：从通用系统级 AI 助手聚焦到量化交易垂直领域
- **数据可视化**：办公室内的每个屏幕都显示真实的行情/策略/风险数据
- **交易执行闭环**：不仅是"看"，还可以通过点击角色来下达指令（如点击 RiskAgent 调整止损线）
- **回测时间旅行**：支持在像素办公室中"回放"历史某一天的策略执行过程，像看电影一样复盘

---

*文档版本: v1.0*
*日期: 2026-06-27*
