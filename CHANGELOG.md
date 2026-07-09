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

### 兼容性
- Python 3.10+
- FastAPI 0.110+
- 当未安装 `axon_quant` 时自动回退到内存实现，业务零修改
