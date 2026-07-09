# 变更日志

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
- Godot 像素办公室场景源工程（`godot_project/`）
- 前端插件入口（`frontend/src/plugins/quant-office/`）
- Docker 镜像（`docker/Dockerfile` + `docker-compose.yml`）
- 单元测试 + 集成测试（17 个用例全部通过）
- 端到端冒烟测试（健康检查、Agent 列表、回测、下单、风控、Dashboard）

### 依赖管理（uv）
- 使用 [uv](https://github.com/astral-sh/uv) 作为推荐依赖管理工具
- `pyproject.toml` 添加 `[tool.uv]` 与 `[dependency-groups]` 配置
- 生成 `uv.lock`（51 个包已锁定）
- `.python-version` 锁定 Python 3.12
- 自动生成 `requirements.txt` / `requirements-dev.txt`（pip 兼容）
- `Makefile` 提供 `make help/sync/dev/test/lint/fmt` 等命令
- `Dockerfile` 改用 uv 多阶段构建，依赖层缓存更高效
- `quant_office/cli.py` 提供 `quant-office` 命令行入口

### 兼容性
- Python 3.10+（开发与生产使用 3.12）
- FastAPI 0.110+
- uv 0.11+（推荐）/ pip 23+（兼容）
- 当未安装 `axon_quant` 时自动回退到内存实现，业务零修改
