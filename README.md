# QuantOffice

> 量化交易指挥中枢 — AI-Native Quantitative Trading Command Center

QuantOffice 基于 FastAPI 后端 + **前端 SPA**（React + TypeScript + Vite + bun）+ axon_quant 量化引擎，
将枯燥的量化交易流程转化为一个可视化的"虚拟办公室"，由 1 名首席交易员 + 5 名专业 Agent 协同完成数据、策略、风控、执行、报告全链路工作。

## 核心特性

- **🏢 Agent 办公室**：1+5 Agent 拟物化协作场景（纯 CSS + 硬阴影 + 4px 栅格，零 WASM / 零 Godot）
- **🤖 AI-Native**：基于 axon_quant 的 Agent Swarm（`SwarmOrchestrator` + `ReActAgent`）
- **⚡ 纳秒级风控**：12ns 预交易检查 + AtomicBool 熔断
- **📈 完整闭环**：数据 → 策略 → 风控 → 执行 → 报告
- **🔌 双模式运行**：独立部署 (`python run.py`) 或 QuantCell 插件加载
- **🔁 零拷贝数据流**：Arrow `RecordBatch` 在所有 Agent 间透传
- **📦 极轻前端**：bun 包管理 + Vite 构建，首屏 gzip < 100KB（不含 echarts）
- **🦀 真接 axon_quant 引擎**：K 线 / 撮合 / 风控 / RL 训练 / 真实下单全部直连 Rust 内核（[改造演化](#axon_quant-真接改造-p0-p7)）

## axon_quant 真接改造 (P0-P7)

QuantOffice 已完成从"内存 fallback"到"真接 `axon_quant 0.3.0` Rust 内核"的端到端改造,所有关键路径均直连 Rust + PyO3 引擎:

| 阶段 | 主题 | 关键改动 | 真实接入点 |
|------|------|---------|-----------|
| **P0** | 引擎 + 风控 | `AxonQuantAdapter` / `RiskMonitor` 周期扫描 | `axon_quant.core.BacktestEngine` + `RiskLimits` |
| **P1** | Data + Risk | DataAgent 真拉 ticks / RiskAgent 读 RuntimeConfigStore | `aq.DataService` + `aq.MockSource.with_tick_series` |
| **P2** | 解耦 + 清理 | Agent 私有属性 → `get_portfolio_snapshot` 公开 API | 移除 fallback "立即成交" 死代码 |
| **P3** | K 线三层降级 | exchange (Binance/OKX) → axon → 纯合成 | `ExchangeClient.get_klines` 公共行情 |
| **P4** | RL 训练 | StrategyAgent 真接 `TradingEnv`,heuristic / PPO 双 backend | `aq.rl.TradingEnv` (action=list[float]) |
| **P5** | 真下单 | ExecutionAgent 真接 `BinanceAdapter`,order_id `AQ-*` 引擎签发 | `aq.BinanceAdapter` + `aq.binance_testnet_config` |
| **P6** | 前端联调 | bun 1.2+ cache 走 `[\~]/` escape,build 跑通 | Vite 5.4.21 / bun 1.2.14 |
| **P7** | E2E 联调 | 9 步全链路探针 + JSON 报告 | `scripts/e2e_smoke.py` + `reports/e2e_*.json` |

**首次跑通示例** ([reports/e2e_20260711T095549Z.json](reports/e2e_20260711T095549Z.json)):

```
9/9 步 ✅ 共 4.9s
├─ engine:      axon_quant 0.3.0 loaded, exchange OMS 未配置
├─ data:        source=exchange (Binance 公共 K 线) 120 bars
├─ rl_train:    backend=heuristic, 4 episodes, 92 笔模拟成交
├─ risk:        dry-run 命中 4 条 (3 critical + 1 warning)
├─ trade:       0.01 BTC @ 67000.05 filled (order_id AQ-00000001-...)
└─ dashboard:   6 策略 / 31 笔 / 61.29% 胜率 / $867 pnl
```

## 架构总览

```
┌────────────── Browser ──────────────┐
│  React UI Shell + Agent Dashboard  │
└───────────────┬─────────────────────┘
                │ WebSocket / HTTP (Vite proxy)
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

### PyPI 镜像（中国大陆网络环境）

项目内置 `uv.toml`，自动启用清华 / 阿里云 / 中科大 PyPI 镜像，**无需任何手动配置**。
如果遇到 `tls handshake eof` / `Failed to fetch https://pypi.org/simple/...` 等网络错误，说明当前网络无法直连 PyPI 官方源，镜像会自动接管。

```bash
# 默认情况：uv.toml 自动生效，直接 uv sync 即可
uv sync
```

如需在 CI / 容器中临时切换回官方源，覆盖环境变量即可：

```bash
# 临时切回官方源
export UV_INDEX_URL=https://pypi.org/simple
uv sync

# 临时切换到指定镜像
export UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
uv sync
```

> 优先级：`UV_INDEX_URL` 环境变量 > `uv.toml` > `pyproject.toml [tool.uv]` > CLI `--index-url`

### 工具链总览

| 工具 | 用途 | 安装 | 备注 |
|------|------|------|------|
| **uv**   | Python 依赖 + 解释器 | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | 锁定 `uv.lock` |
| **bun**  | 前端依赖 + 脚本 | `curl -fsSL https://bun.sh/install \| bash` | 锁定 `bun.lockb` |
| **vite** | 前端构建（bun 调用） | bun 自带 | dev 5173 / build dist |

### 全栈快速开始

```bash
# 1) 后端（Python 3.14+ / FastAPI）
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.14
uv sync --extra axon --extra rl --group dev   # 装后端 + axon_quant 引擎 + RL 栈
uv run python run.py --reload                 # 启动后端 :8765

# 2) 前端（React 18 + Vite + bun）
curl -fsSL https://bun.sh/install | bash
cd frontend && bun install                     # 安装前端依赖
bun run dev                                    # 启动 Vite :5173（自动代理 :8765）

# 3) 一键 E2E 验证（另起一个终端，需先起后端）
uv run python scripts/e2e_smoke.py --base http://127.0.0.1:8765
# → 控制台打印 summary + 落 reports/e2e_<UTC ts>.json

# 打开浏览器
open http://localhost:5173
```

> **P0-P7 改造后必备**:`uv sync --extra axon` 会装上 `axon_quant==0.3.0`,没有它所有"真接"路径都会落回内存 fallback。
> 想启用 PPO RL backend 还需要 `--extra rl`(装 `stable-baselines3` + `torch`)。

#### 可选扩展包

```bash
# 后端:axon_quant 真实引擎(取代内存 fallback)
uv sync --extra axon

# 后端:RL 训练栈(torch / gymnasium / stable-baselines3)
uv sync --extra rl

# 前端:生产构建(输出 frontend/dist/)
cd frontend && bun run build
```

#### 常用 Make 命令

```bash
make help         # 查看所有命令
make install      # 安装 uv
make sync         # uv sync --no-dev
make sync-dev     # uv sync --group dev
make dev          # 启动后端（热重载）
make test         # 后端 pytest
make lint         # ruff check
make fmt          # ruff format
make lock-export  # 同步 pyproject.toml -> requirements.txt

make fe-install    # bun install
make fe-dev        # bun run dev（Vite :5173）
make fe-build      # bun run build（输出 dist/）
make fe-typecheck  # tsc --noEmit
make fe-preview    # bun run preview
```

### 独立运行模式（旧文档兼容）

#### 方式一：使用 uv（推荐）

```bash
# 安装 uv（如未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# uv 会自动读取 .python-version（3.14）并下载对应解释器
uv python install 3.14

# 同步依赖（含开发依赖）
uv sync

# 启动后端
uv run python run.py --host 0.0.0.0 --port 8765 --reload

# 访问 API 文档
open http://localhost:8765/docs
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
python run.py --host 0.0.0.0 --port 8765 --reload
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
# 构建前端静态资源
cd frontend && bun run build

# 复制后端插件到 QuantCell
cp -r quant_office /path/to/quantcell/backend/plugins/quant-office
cp manifest.json /path/to/quantcell/backend/plugins/quant-office/

# 复制前端插件入口（作为 QuantCell 前端 plugin）
cp -r frontend/src/plugins/quant-office /path/to/quantcell/frontend/src/plugins/

# 重启 QuantCell
python service_manager.py restart backend
```

> **说明**：作为插件运行时，前端通过 `lazy import` 加载 [frontend/src/plugins/quant-office/index.tsx](frontend/src/plugins/quant-office/index.tsx)，
> 路由前缀自动变为 `/api/plugins/quant-office/`，由 `VITE_PLUGIN_MODE=quantcell` 环境变量切换。

## 项目结构

```
QuantOffice/
├── run.py                         # 独立模式入口
├── pyproject.toml                 # 项目元数据 + 依赖声明
├── uv.lock                        # uv 锁定文件（依赖解析结果）
├── uv.toml                        # PyPI 镜像配置（国内加速）
├── requirements.txt               # pip 运行时依赖（uv export 生成）
├── requirements-dev.txt           # pip 开发依赖（uv export 生成）
├── requirements-axon.txt          # axon 引擎依赖
├── requirements-rl.txt            # RL 训练依赖
├── requirements-all.txt           # 全部可选扩展
├── Makefile                       # 常用命令（含 fe-* 前端命令）
├── .python-version                # uv Python 版本锁定（3.14）
├── manifest.json                  # QuantCell 插件清单
├── quant_office/                  # 后端核心代码
│   ├── app.py                     # 独立模式 FastAPI 应用
│   ├── plugin.py                  # 插件模式 PluginBase
│   ├── config.py
│   ├── logging_config.py
│   ├── core/                      # 核心基础设施
│   │   ├── engine_adapter.py
│   │   ├── websocket_manager.py
│   │   ├── event_publisher.py
│   │   └── agent_scheduler.py
│   ├── agents/                    # 6 个 Agent
│   ├── api/                       # FastAPI 路由
│   ├── data/                      # 数据层
│   └── services/                  # 业务服务
├── frontend/                      # 前端 SPA（Vite + bun）
│   ├── package.json
│   ├── bunfig.toml                # bun 配置（npmmirror 镜像）
│   ├── tsconfig.json
│   ├── vite.config.ts             # Vite + React + 代理
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx                # 路由 + 布局
│       ├── styles/                # CSS 设计令牌（tokens / global / reset）
│       ├── components/
│       │   ├── Layout/            # TopNav / TopBar / RightPanel
│       │   └── AgentAvatar/       # AgentCharacter 头像组件
│       ├── pages/                 # 9 个页面
│       ├── api/                   # REST + WebSocket 客户端
│       ├── stores/                # Zustand (agentStore / uiStore)
│       ├── lib/                   # agentMeta 等
│       ├── types/                 # 全局 TS 类型
│       └── plugins/quant-office/  # QuantCell 插件入口
├── tests/                         # 后端测试
├── scripts/                       # 运维 / E2E 脚本
│   └── e2e_smoke.py               # P7 全链路探针(9 步)
├── reports/                       # E2E / 回测运行报告(JSON)
│   └── e2e_*.json                 # 每次跑 e2e_smoke 的原始记录
├── docker/                        # 容器化部署
└── docs/                          # 项目文档
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

## E2E 联调测试

`scripts/e2e_smoke.py` 是 P7 引入的全链路探针,9 步走完 "K 线 → 策略 → RL 训练 → 风控 → 真下单 → 仪表盘" 的完整闭环。

```bash
# 1. 起后端（任一终端）
uv run python run.py --port 8765

# 2. 跑 E2E（另起终端）
uv run python scripts/e2e_smoke.py --base http://127.0.0.1:8765

# 可调参数
uv run python scripts/e2e_smoke.py \
    --base http://127.0.0.1:8765 \
    --symbol BTCUSDT --timeframe 1h --limit 120 --episodes 4
```

**链路覆盖**:

| # | 端点 | 验证点 |
|---|------|--------|
| 1 | `GET /api/health` | 探活 + 启动时间 |
| 2 | `GET /api/settings/engine` | `axon_quant` 加载状态 / `using_exchange` 标志 |
| 3 | `POST /api/agents/data/command{load_data}` | DataAgent 三层降级(exchange→axon→synth),确认 `source` 字段 |
| 4 | `POST /api/strategies` | 建新策略,回 `201` + `id` |
| 5 | `POST /api/strategies/{id}/train` | StrategyAgent 真接 `aq.rl.TradingEnv`,回 `backend` + `sharpe` + `final_portfolio` |
| 6 | `GET /api/risk/metrics` | 全量告警聚合 |
| 7 | `POST /api/risk/check-dry-run` | 风控预演(不写库),命中规则明细 |
| 8 | `POST /api/trades` | ExecutionAgent 走三层 OMS(exchange→axon→fallback),`order_id` 形如 `AQ-*` |
| 9 | `GET /api/dashboard` | 聚合策略 / 成交 / 告警 / 权益曲线 |

**报告样例**:
- `reports/e2e_<UTC ts>.json` — 完整 9 步 raw 响应(每步含 `status` / `elapsed_ms` / `body`)
- 控制台末尾打印 `summary` 字段:`{ok, failed, engine, data, rl_train, risk, trade, dashboard}`

**判定标准**: `summary.failed == 0` 即视为全链路通过。任意一步 `error` 会写进对应 step 的 `error` 字段,但脚本不会中断,便于一次性看完所有问题。

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

- [axon_quant](https://github.com/pengwow/axon_quant) — AI-Native 量化交易框架（Rust + PyO3,当前 `0.3.0`）
- [QuantCell](https://github.com/) — 插件化部署平台
- [scripts/e2e_smoke.py](scripts/e2e_smoke.py) — P7 全链路 E2E 探针
- [reports/](reports/) — E2E 运行报告归档

## 许可证

MIT © 2026 QuantOffice Team
