# QuantOffice

> 像素风格量化交易指挥中枢 — AI-Native Pixel-style Quantitative Trading Command Center

QuantOffice 基于 FastAPI 后端 + Godot 像素场景前端 + axon_quant 量化引擎，将枯燥的量化交易流程转化为一个可视化的"虚拟办公室"，由 1 名首席交易员 + 5 名专业 Agent 协同完成数据、策略、风控、执行、报告全链路工作。

## 核心特性

- **🏢 像素办公室**：1+5 Agent 拟物化协作场景（Godot 4.3+ WASM）
- **🤖 AI-Native**：基于 axon_quant 的 Agent Swarm（`SwarmOrchestrator` + `ReActAgent`）
- **⚡ 纳秒级风控**：12ns 预交易检查 + AtomicBool 熔断
- **📈 完整闭环**：数据 → 策略 → 风控 → 执行 → 报告
- **🔌 双模式运行**：独立部署 (`python run.py`) 或 QuantCell 插件加载
- **🔁 零拷贝数据流**：Arrow `RecordBatch` 在所有 Agent 间透传

## 架构总览

```
┌────────────── Browser ──────────────┐
│  React Shell + Godot WASM Office    │
└───────────────┬─────────────────────┘
                │ WebSocket / HTTP
┌───────────────▼─────────────────────┐
│  FastAPI Service Layer              │
│  ├─ REST API                        │
│  ├─ WebSocket Manager               │
│  └─ Agent Scheduler (asyncio)       │
└───────────────┬─────────────────────┘
                │ Python SDK
┌───────────────▼─────────────────────┐
│  axon_quant Engine (Rust + PyO3)    │
│  ├─ axon-data    axon-risk          │
│  ├─ axon-backtest  axon-oms         │
│  ├─ axon-rl      axon-llm           │
│  └─ axon-exchange  axon-explain     │
└─────────────────────────────────────┘
```

## 快速开始

### 依赖管理工具

QuantOffice 使用 [uv](https://github.com/astral-sh/uv) 进行依赖管理（同样兼容 pip）：

| 工具 | 锁定文件 | 安装速度 | 推荐场景 |
|------|---------|---------|---------|
| **uv** | `uv.lock` | 极快（Rust 实现） | 开发 / CI / Docker |
| pip | `requirements.txt` | 慢 | 兼容旧环境 |

### 独立运行模式

#### 方式一：使用 uv（推荐）

```bash
# 安装 uv（如未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# uv 会自动读取 .python-version（3.14）并下载对应解释器
uv python install 3.14

# 同步依赖（含开发依赖）
uv sync

# 启动后端
uv run python run.py --host 0.0.0.0 --port 8000 --reload

# 访问 API 文档
open http://localhost:8000/docs
```

#### 方式二：使用 pip

```bash
# Python 3.14+ 必需
python3.14 -m venv .venv
source .venv/bin/activate

# 安装运行时依赖
pip install -r requirements.txt

# 安装开发依赖
pip install -r requirements-dev.txt

# 或直接安装为可编辑模式
pip install -e "."

# 启动后端
python run.py --host 0.0.0.0 --port 8000 --reload
```

#### 可选扩展包

```bash
# 安装 axon_quant 真实引擎（取代内存 fallback）
uv sync --extra axon

# 安装 RL 训练栈（torch / gymnasium / stable-baselines3）
uv sync --extra rl

# 一次性安装全部可选扩展
uv sync --extra axon --extra rl
```

#### 常用 Make 命令

```bash
make help          # 查看所有命令
make install       # 安装 uv
make sync          # uv sync --no-dev
make sync-dev      # uv sync（默认包含 dev 组）
make dev           # 启动开发服务器（热重载）
make test          # 运行测试
make test-cov      # 测试 + 覆盖率
make lint          # ruff check
make fmt           # ruff format
make lock-export   # 同步 pyproject.toml -> requirements.txt
```

### 插件运行模式 (QuantCell)

```bash
# 复制插件到 QuantCell
cp -r quant_office /path/to/quantcell/backend/plugins/quant-office
cp manifest.json /path/to/quantcell/backend/plugins/quant-office/

# 重启 QuantCell
python service_manager.py restart backend
```

## 项目结构

```
QuantOffice/
├── run.py                         # 独立模式入口
├── pyproject.toml                 # 项目元数据 + 依赖声明
├── uv.lock                        # uv 锁定文件（依赖解析结果）
├── requirements.txt               # pip 运行时依赖（uv export 生成）
├── requirements-dev.txt           # pip 开发依赖（uv export 生成）
├── Makefile                       # 常用命令
├── .python-version                # uv Python 版本锁定（3.14）
├── manifest.json                  # QuantCell 插件清单
├── quant_office/                  # 核心代码
│   ├── app.py                     # 独立模式 FastAPI 应用
│   ├── plugin.py                  # 插件模式 PluginBase
│   ├── config.py                  # 配置
│   ├── logging_config.py
│   ├── core/                      # 核心基础设施
│   │   ├── engine_adapter.py      # axon_quant 适配器
│   │   ├── websocket_manager.py
│   │   ├── event_publisher.py
│   │   └── agent_scheduler.py
│   ├── agents/                    # 6 个 Agent 业务逻辑
│   │   ├── chief_agent.py
│   │   ├── data_agent.py
│   │   ├── strategy_agent.py
│   │   ├── risk_agent.py
│   │   ├── execution_agent.py
│   │   └── report_agent.py
│   ├── api/                       # FastAPI 路由
│   │   ├── agents.py
│   │   ├── strategies.py
│   │   ├── backtests.py
│   │   ├── trades.py
│   │   ├── risk.py
│   │   ├── reports.py
│   │   └── dashboard.py
│   ├── data/                      # 数据层
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── redis_cache.py
│   │   └── arrow_store.py
│   └── services/                  # 业务服务
│       ├── agent_service.py
│       ├── strategy_service.py
│       ├── backtest_service.py
│       ├── market_data_service.py
│       └── notification_service.py
├── frontend/                      # React + 插件前端
├── godot_project/                 # Godot 像素办公室源工程
├── tests/                         # 测试
└── docker/                        # 容器化部署
```

## 双模式差异

| 维度 | 独立模式 | QuantCell 插件模式 |
|------|---------|-------------------|
| 启动 | `python run.py` | 复制到 `backend/plugins/` |
| 入口 | `quant_office/app.py` | `quant_office/plugin.py` |
| API 前缀 | `/api/*` | `/api/plugins/quant-office/*` |
| WebSocket | `/ws` | `/api/plugins/quant-office/ws` |
| 数据目录 | `./data/` | `backend/plugins/quant-office/data/` |

业务代码（`core/`、`agents/`、`api/`、`data/`、`services/`）**100% 复用**，仅入口与路由前缀不同。

## 开发与测试

```bash
# 单元测试
pytest -v

# 代码风格
ruff check .

# 完整集成
pip install -e ".[dev,axon,rl]"
python run.py --reload
```

## 参考

- [axon_quant](https://github.com/pengwow/axon_quant) — AI-Native 量化交易框架（Rust 核心）
- [QuantCell](https://github.com/) — 插件化部署平台

## 许可证

MIT © 2026 QuantOffice Team
