# 变更日志

## [0.2.2] - 2026-07-09

### 修复
- **浏览器端 API 全面 404 / 307**
  - `quant_office/app.py` FastAPI 加 `redirect_slashes=False`，避免前端无斜杠路径 307
- **后端响应字段与前端 `types/index.ts` 完全对不上**
  - 新增 [services/api_schemas.py](file:///workspace/quant_office/services/api_schemas.py) 统一转换层
  - Agent：后端 PascalCase role（`ChiefTrader`）→ 前端 lowercase（`chief`），补 `emoji / color / position / metrics / updated_at`
  - Strategy / Backtest / Trade / RiskAlert / Report 全部按前端字段名 + 嵌套结构输出
  - Dashboard：返回 `DashboardSummary` 形状（`agents / recent_alerts / equity_curve / total_pnl / sharpe / drawdown`）
- **缺失端点补齐**
  - `POST /api/agents/{role}/start|stop`（前端 start/stop 按钮）
  - `POST /api/strategies` + `PUT/DELETE /api/strategies/{id}`（策略 CRUD）
  - `POST /api/risk/alerts/{id}/ack`（告警确认）
  - `GET /api/risk/metrics`（风控聚合）
  - `GET /api/reports/{id}`（报告详情）

### 新增（演示模式）
- [quant_office/demo.py](file:///workspace/quant_office/demo.py) — 启动自动播种：
  - 5 个策略（3 live / 1 paused / 1 draft）
  - 4 个回测（含 90 点权益曲线）
  - 30 笔成交（5 标的，多空混合）
  - 3 个风控告警（1 critical / 1 warning / 1 info）
  - 1 个完整报告（含 4 个章节）
- `POST /api/demo/reset` 端点（清空 + 重新注入）
- `POST /api/demo/seed` 端点（空库注入）
- 插件模式（`quant_office/plugin.py`）也接入 `_seed_demo()` hook

### 改进
- [quant_office/data/database.py](file:///workspace/quant_office/data/database.py)：拆分 `init_database()` 与 `create_all_tables()`，
  解决 FastAPI lifespan 中 `loop.is_running()` 导致表创建在后台异步执行的竞态
- [quant_office/data/models.py](file:///workspace/quant_office/data/models.py)：扩展 ORM 字段
  （Strategy 加 `pnl / sharpe / drawdown / params`；Backtest 加完整指标；Trade 加 `pnl / order_id`；RiskAlert 加 `acknowledged` 等）

### 测试
- 新增 `test_demo_seed_and_reset`：验证 5 策略 / 4 回测 / 30 成交 / 3 告警 / 1 报告 / reset 端点
- 更新 `test_agents_list`：校验前端 Agent 形状（id/role/name/emoji/color/position/status 字段齐全）
- 更新 `test_full_workflow`：用新的 backtest / trade API 形状
- **结果：18/18 全部通过（1.13s）**

### 端到端验证
- 后端启动后自动播种：策略=5 回测=4 成交=30 告警=3 报告=1
- 11 个端点全部返回 200/201（含 5 个写入端点：start/trade/strategy/ack/reset）
- 前端 `bun run typecheck` 通过；`bun run build` 706 modules 5.06s

## [0.2.1] - 2026-07-09

### 修复
- **后端启动 `ValueError: the greenlet library is required`**
  - SQLAlchemy 2.0+ 异步模式将 `greenlet` 列为软依赖（`Required-by: sqlalchemy` 但不保证自动安装）
  - 显式声明 `greenlet>=3.0` 到 [pyproject.toml](file:///workspace/pyproject.toml) 顶层 `dependencies`
  - 重新生成 `uv.lock`（greenlet 3.5.3 已锁定为顶层包）与 5 份 `requirements*.txt`
  - 影响用户：克隆后 `uv sync` 即自动装上 greenlet，无需手动 `pip install greenlet`

## [0.2.0] - 2026-07-09

### ⚠️ 重大变更
- **前端完全重写：移除 Godot，切换为纯前端技术栈**
  - 删除 `godot_project/` 整个目录（`.gd` / `.tscn` / `project.godot` 全部废弃）
  - 废弃 Godot WASM 场景 + `react-godot-bridge` 双向通信
  - 改为 **React 18 + TypeScript + Vite + bun + 纯 CSS 硬阴影风格**
  - 角色由 CSS 伪元素 + 调色板变量动态生成（无外部素材）
  - 场景由 CSS 棋盘格地板 + 静态装饰（盆栽/机柜/大屏）拼出

### 新增（前端）
- `frontend/package.json` — 声明 bun 包管理（`packageManager: bun@1.1.34`）
- `frontend/bunfig.toml` — npmmirror 国内镜像
- `frontend/tsconfig.json` — 严格 TS 配置 + `@/*` 路径别名
- `frontend/vite.config.ts` — Vite + React + FastAPI 代理
- `frontend/index.html` — 入口 HTML（含 Press Start 2P 字体）
- `frontend/src/styles/` — 设计令牌（pixel.css / global.css / reset.css）
- `frontend/src/components/PixelOffice/` — OfficeScene / Workstation / AgentCharacter
- `frontend/src/components/Layout/` — Sidebar / TopBar / RightPanel
- `frontend/src/pages/` — 8 个页面（PixelOffice / Dashboard / Agents / Strategies / Backtests / Trades / Risk / Reports）
- `frontend/src/api/` — REST 客户端 + WebSocket Bus（含自动重连）
- `frontend/src/stores/` — Zustand (agentStore / uiStore)
- `frontend/src/types/index.ts` — 与后端 FastAPI 响应字段对齐的 TS 类型
- `frontend/src/plugins/quant-office/` — QuantCell 插件入口（动态 import）

### 新增（项目根）
- `Makefile` — 新增 `fe-install / fe-dev / fe-build / fe-typecheck / fe-preview / dev-all` 命令
- `.gitignore` — 新增 `frontend/.vite / bun.lockb / node_modules` 排除

### 依赖（前端）
- runtime: `react / react-dom / react-router-dom / @tanstack/react-query / zustand / echarts / echarts-for-react / clsx`
- dev: `@types/node / @types/react / @vitejs/plugin-react / typescript / vite`
- bun install: 82 packages, 4.14s（npmmirror）
- bun build: 706 modules → 22.86 kB CSS + 1.29 MB JS（gzip ≈ 421 KB），4.5s

### 文档
- `README.md` — 核心特性 / 架构图 / 工具链表 / 全栈快速开始 / 项目结构 全面更新
- `docs/QuantOffice_Project_Plan.md` — 移除 Godot 描述，改为纯前端
- `docs/QuantOffice_Plugin_Architecture.md` — 顶部加 v0.1.0 架构变更说明
- `docs/QuantOffice_Axon_Integration.md` — 架构图改为 Pure-CSS Office

### 兼容性
- 前端构建产物可作为 QuantCell 插件集成（路由前缀 `/api/plugins/quant-office`）
- 浏览器侧最低要求：Chrome 90+ / Edge 90+ / Safari 14+（无 WASM 依赖）
- 不再需要 Godot 编辑器 / WebGL 2.0 / JavaScriptBridge

## [0.1.0] - 2026-07-09

### 新增
- 完整 FastAPI 后端骨架（独立模式 + 插件模式双模式运行）
- 1+5 Agent 协作框架（Chief / Data / Strategy / Risk / Execution / Report）
- `core/engine_adapter.py` — axon_quant 引擎统一适配器（含内存 fallback）
- `core/websocket_manager.py` — WebSocket 频道订阅 / 广播
- `core/event_publisher.py` — 进程内事件总线（兼容 QuantCell EventBus）
- `core/agent_scheduler.py` — Agent 生命周期管理 + 周期心跳
- API 路由集：agents / strategies / backtests / trades / risk / reports / dashboard
- `plugin.py` — QuantCell 插件外壳（路由前缀 `/api/plugins/quant-office`）
- `manifest.json` — 插件清单（permissions + config_schema）
- 数据层：SQLAlchemy 异步 ORM + Redis 缓存 + Arrow/Parquet 时序存储
- ~~Godot 虚拟办公室场景源工程（`godot_project/`）~~ → 0.2.0 移除
- 前端插件入口（`frontend/src/plugins/quant-office/`）
- Docker 镜像（`docker/Dockerfile` + `docker-compose.yml`）
- 单元测试 + 集成测试（17 个用例全部通过）
- 端到端冒烟测试（健康检查、Agent 列表、回测、下单、风控、Dashboard）

### 依赖管理（uv）
- 使用 [uv](https://github.com/astral-sh/uv) 作为推荐依赖管理工具
- `pyproject.toml` 添加 `[tool.uv]` 与 `[dependency-groups]` 配置
- **Python 版本要求提升至 3.14+**（`.python-version` 锁定 + `requires-python = ">=3.14"`）
- 生成 `uv.lock`（77 个包已锁定，含 axon_quant / torch / stable-baselines3 等可选扩展）
- 重新启用 `axon` / `rl` 可选 extras（axon_quant 0.3.0 仅支持 Python 3.14+）
- `.python-version` 锁定 Python 3.14
- 自动生成 `requirements.txt` / `requirements-dev.txt` / `requirements-all.txt`
- `Makefile` 提供 `make help/sync/dev/test/lint/fmt` 等命令
- `Dockerfile` 改用 `python:3.14-slim` + uv 多阶段构建
- `quant_office/cli.py` 提供 `quant-office` 命令行入口

### 兼容性
- **Python 3.14+**（强制要求，因 axon_quant 引擎依赖）
- FastAPI 0.110+
- uv 0.11+（推荐）/ pip 23+（兼容）
- 当未安装 `axon_quant` 时自动回退到内存实现，业务零修改

### 修复
- **中国大陆网络环境 `uv sync` 失败 (`tls handshake eof`)**
  - 新增 `uv.toml`，默认指向清华 / 阿里云 / 中科大 PyPI 镜像（主源 + 备用）
  - `pyproject.toml` build backend 由 `setuptools>=68, wheel` 切换为 `hatchling`，
    消除 `build-system.requires` 阶段的网络拉取（零 build 依赖）
  - `[tool.uv]` 仅保留 `default-groups = ["dev"]`，避免与 `uv.toml` 重复告警
  - 重新生成 `uv.lock` 与 5 份 `requirements*.txt`
  - README 增加"PyPI 镜像"章节，说明 `UV_INDEX_URL` 环境变量覆盖方式
