# QuantOffice

> 像素风格量化交易指挥中枢 — AI-Native Pixel-style Quantitative Trading Command Center

QuantOffice 基于 FastAPI 后端 + **纯前端像素风 SPA**（React + TypeScript + Vite + bun）+ axon_quant 量化引擎，
将枯燥的量化交易流程转化为一个可视化的"虚拟办公室"，由 1 名首席交易员 + 5 名专业 Agent 协同完成数据、策略、风控、执行、报告全链路工作。

## 核心特性

- **🏢 像素办公室**：1+5 Agent 拟物化协作场景（**纯 CSS + 硬阴影 + 4px 像素栅格**，零 WASM / 零 Godot）
- **🤖 AI-Native**：基于 axon_quant 的 Agent Swarm（`SwarmOrchestrator` + `ReActAgent`）
- **⚡ 纳秒级风控**：12ns 预交易检查 + AtomicBool 熔断
- **📈 完整闭环**：数据 → 策略 → 风控 → 执行 → 报告
- **🔌 双模式运行**：独立部署 (`python run.py`) 或 QuantCell 插件加载
- **🔁 零拷贝数据流**：Arrow `RecordBatch` 在所有 Agent 间透传
- **📦 极轻前端**：bun 包管理 + Vite 构建，首屏 gzip < 100KB（不含 echarts）

## 架构总览

```
┌────────────── Browser ──────────────┐
│  React UI Shell + CSS Pixel Office  │
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
uv sync --group dev                # 安装后端 + 开发依赖
uv run python run.py --reload      # 启动后端 :8000

# 2) 前端（React 18 + Vite + bun）
curl -fsSL https://bun.sh/install | bash
cd frontend && bun install         # 安装前端依赖
bun run dev                        # 启动 Vite :5173（自动代理 :8000）

# 打开浏览器
open http://localhost:5173
```

#### 可选扩展包

```bash
# 后端：axon_quant 真实引擎（取代内存 fallback）
uv sync --extra axon

# 后端：RL 训练栈（torch / gymnasium / stable-baselines3）
uv sync --extra rl

# 前端：生产构建（输出 frontend/dist/）
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
│       ├── styles/                # 像素风 CSS（pixel.css / global.css）
│       ├── components/
│       │   ├── Layout/            # Sidebar / TopBar / RightPanel
│       │   └── PixelOffice/       # OfficeScene / Workstation / AgentCharacter
│       ├── pages/                 # 8 个页面
│       ├── api/                   # REST + WebSocket 客户端
│       ├── stores/                # Zustand (agentStore / uiStore)
│       ├── lib/                   # agentMeta 等
│       ├── types/                 # 全局 TS 类型
│       └── plugins/quant-office/  # QuantCell 插件入口
├── tests/                         # 后端测试
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
