# QuantOffice 插件化改造方案 — 兼容 QuantCell 双模式运行

> **v0.1.0 架构更新**：原方案采用 Godot 4.3+ 导出的 WebAssembly 像素场景 + `react-godot-bridge` 双向通信。
> 现已**完全切换为纯前端技术栈**（React 18 + TypeScript + Vite + bun + 纯 CSS 像素风），
> 不再依赖 Godot / WASM / WebGL / JavaScriptBridge 等运行时，构建/部署/分发大幅简化。
> 本文档中如仍出现 Godot / WASM 描述，仅作历史参考；实际项目结构请见 README 与 [QuantOffice_Project_Plan.md](./QuantOffice_Project_Plan.md)。

## 一、参考项目架构分析

### 1.1 QuantCell 插件系统核心架构

QuantCell 采用前后端分离的插件架构，支持完整生命周期管理（安装/启用/禁用/卸载）、热加载与重启加载、ZIP/Git/手动三种安装方式。

**后端插件系统**（`backend/plugins/`）：

| 组件 | 文件 | 职责 |
|------|------|------|
| `PluginBase` | `plugin_base.py` | 插件基类，定义生命周期接口（register/start/stop/on_enable/on_disable） |
| `PluginManager` | `plugin_manager.py` | 插件全生命周期管理（扫描/加载/卸载/安装/启用/禁用） |
| `PluginLoader` | `plugin_loader.py` | 热加载器（HotPluginLoader）与重启加载器（RestartPluginLoader） |
| `PluginInstaller` | `plugin_installer.py` | ZIP 上传安装与 Git 克隆安装 |
| `PluginStore` | `plugin_store.py` | 插件元数据持久化（数据库） |
| `EventBus` | `event_bus.py` | 插件间及插件与系统的事件通信 |

**前端插件系统**（`frontend/src/plugins/`）：

| 组件 | 文件 | 职责 |
|------|------|------|
| `PluginContext` | `PluginContext.tsx` | React Context，提供 `usePlugins()` Hook |
| `PluginRegistry` | `PluginRegistry.ts` | 全局单例，管理菜单项和路由注册 |
| `PluginLoader` | `PluginLoader.ts` | 动态加载插件 JS/CSS 资源 |
| `pluginApi` | `api/plugin.ts` | 前端调用后端插件 API 的客户端 |

**关键约定**：
- 后端插件必须包含 `register_plugin()` 入口函数，返回 `PluginBase` 实例
- 路由统一前缀：`APIRouter(prefix="/api/plugins/{plugin-name}")`
- 前端通过 `pluginRegistry.registerMenu()` 和 `registerRoute()` 注册 UI
- 资源加载路径：`/api/plugins/{name}/assets/index.{js,css}`
- SSE 事件流实时同步插件状态变更

### 1.2 WalletMonitor 双模式设计剖析

WalletMonitor 是 QuantCell 生态中第一个完整实现"既可独立运行，又可作为插件加载"的参考项目，其双模式架构设计非常精妙：

```
WalletMonitor/
├── run.py                    # 独立运行入口（直接 uvicorn 启动）
├── run_cli.py                # CLI 命令行工具
├── wallet_monitor/
│   ├── app.py                # 独立模式：完整 FastAPI 应用工厂
│   ├── plugin.py             # 插件模式：PluginBase 子类外壳
│   ├── config.py             # 配置管理（两种模式共享）
│   ├── api/                  # 业务 API 路由（两种模式复用）
│   │   ├── wallets.py
│   │   ├── transactions.py
│   │   ├── alerts.py
│   │   └── whales.py
│   ├── blockchain/           # 区块链交互（两种模式复用）
│   ├── data/                 # 数据存储（两种模式复用）
│   ├── alert/                # 告警引擎（两种模式复用）
│   └── logging_config.py     # 日志配置（两种模式复用）
└── frontend/
    └── src/plugins/wallet-monitor/   # 前端插件
        ├── index.tsx
        ├── manifest.json
        └── components/
```

**双模式核心设计原则**：

1. **业务逻辑与框架完全解耦**：`api/`、`blockchain/`、`data/`、`alert/` 等核心业务模块不依赖任何插件框架代码，可被两种模式复用。

2. **独立模式提供完整上下文**：`app.py` 负责创建完整的 FastAPI 应用，包含 CORS、中间件、数据库初始化、根路由、健康检查等。路由前缀为 `/api`。

3. **插件模式仅提供"适配外壳"**：`plugin.py` 只负责：
   - 继承 `PluginBase`，实现生命周期回调
   - 创建 `APIRouter(prefix="/api/plugins/wallet-monitor")`
   - 将业务路由 `include_router()` 到插件路由下
   - 通过 `register_plugin()` 返回实例

4. **配置与数据隔离**：插件模式使用插件数据目录存放数据库，避免污染源码目录：
   ```python
   plugin_data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
   ```

5. **独立开发调试支持**：QuantCell 提供 `plugin_dev.py`，支持 `--reload` 热重载，无需启动完整系统。

---

## 二、QuantOffice 双模式改造方案

### 2.1 改造目标

将 QuantOffice 从"单一系统"重构为"双模式运行"架构：

- **独立运行模式**：`python run.py` 直接启动完整服务，适合个人交易者快速部署
- **插件运行模式**：将插件目录放入 QuantCell 的 `backend/plugins/`，由 QuantCell 统一管理，适合团队协作与生态集成

两种模式共享 100% 的业务逻辑代码，仅入口文件和路由前缀不同。

### 2.2 改造后目录结构

```
QuantOffice/
├── run.py                              # 独立运行入口
├── pyproject.toml                      # 依赖配置
├── manifest.json                       # 插件清单（插件模式必需）
├── quant_office/
│   ├── __init__.py
│   ├── app.py                          # 独立模式：完整 FastAPI 应用工厂
│   ├── plugin.py                       # 插件模式：PluginBase 子类外壳
│   ├── config.py                       # 配置管理（共享）
│   ├── logging_config.py               # 日志配置（共享）
│   │
│   ├── core/                           # 核心业务逻辑（共享）
│   │   ├── __init__.py
│   │   ├── engine_adapter.py           # axon_quant 引擎适配器（Rust核心+Python前端）
│   │   ├── agent_scheduler.py          # Agent 任务调度（Celery封装）
│   │   ├── websocket_manager.py        # WebSocket 连接管理
│   │   └── event_publisher.py          # 事件发布（兼容EventBus）
│   │
│   ├── agents/                         # Agent 业务逻辑（共享）
│   │   ├── __init__.py
│   │   ├── chief_agent.py              # ChiefTrader 逻辑
│   │   ├── data_agent.py               # DataAgent 逻辑
│   │   ├── strategy_agent.py           # StrategyAgent 逻辑
│   │   ├── risk_agent.py               # RiskAgent 逻辑
│   │   ├── execution_agent.py          # ExecutionAgent 逻辑
│   │   └── report_agent.py             # ReportAgent 逻辑
│   │
│   ├── api/                            # API 路由（共享）
│   │   ├── __init__.py
│   │   ├── agents.py                   # Agent 状态/控制接口
│   │   ├── strategies.py               # 策略 CRUD 接口
│   │   ├── backtests.py                # 回测任务接口
│   │   ├── trades.py                   # 交易记录接口
│   │   ├── risk.py                     # 风控指标接口
│   │   ├── reports.py                  # 报告生成接口
│   │   └── dashboard.py                # 仪表盘数据接口
│   │
│   ├── data/                           # 数据层（共享）
│   │   ├── __init__.py
│   │   ├── database.py                 # SQLAlchemy 数据库连接
│   │   ├── models.py                   # ORM 模型定义
│   │   ├── redis_cache.py              # Redis 缓存封装
│   │   ├── arrow_store.py              # Arrow RecordBatch 零拷贝存储
│   │   └── parquet_client.py           # Parquet 列式时序数据
│   │
│   ├── services/                       # 服务层（共享）
│   │   ├── __init__.py
│   │   ├── agent_service.py            # Agent  orchestration
│   │   ├── strategy_service.py         # 策略生命周期管理
│   │   ├── backtest_service.py         # 回测执行服务
│   │   ├── market_data_service.py      # 行情数据服务
│   │   └── notification_service.py     # 通知/告警服务
│   │
│   └── godot/                          # Godot 场景导出资源
│       ├── quant_office.wasm
│       ├── quant_office.pck
│       └── quant_office.js
│
├── frontend/                           # 前端（独立模式完整前端）
│   ├── index.html
│   ├── src/
│   │   ├── main.tsx                    # 独立模式入口
│   │   ├── App.tsx
│   │   ├── api/                        # API 客户端
│   │   ├── components/                 # React 组件
│   │   ├── plugins/
│   │   │   └── quant-office/           # 插件模式前端入口
│   │   │       ├── index.tsx           # 插件注册（菜单+路由）
│   │   │       ├── manifest.json       # 前端插件清单
│   │   │       ├── components/         # 插件专用组件
│   │   │       └── assets/             # 静态资源（Godot WASM等）
│   │   └── ...
│   └── package.json
│
├── godot_project/                      # Godot 源工程
│   ├── project.godot
│   ├── scenes/
│   │   ├── office.tscn                 # 主办公室场景
│   │   ├── characters/                 # 角色动画
│   │   └── ui/                         # 场景内 UI
│   ├── scripts/
│   │   ├── office_manager.gd           # 办公室状态管理
│   │   ├── character_controller.gd     # 角色动画控制
│   │   └── react_bridge.gd             # React ↔ Godot 通信
│   └── assets/
│       ├── sprites/                    # 像素素材
│       └── fonts/
│
├── tests/                              # 测试用例
└── docker/
    ├── Dockerfile
    └── docker-compose.yml
```

### 2.3 核心代码设计

#### 2.3.1 独立运行入口 `run.py`

```python
#!/usr/bin/env python3
"""QuantOffice 独立运行入口"""
import argparse
import uvicorn

def main():
    parser = argparse.ArgumentParser(description="QuantOffice 量化交易指挥中枢")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=8000, help="监听端口")
    parser.add_argument("--reload", action="store_true", help="开发模式热重载")
    args = parser.parse_args()

    print(f"🎯 QuantOffice 启动中... http://{args.host}:{args.port}")
    print(f"📊 API 文档: http://localhost:{args.port}/docs")
    print(f"🏢 像素办公室: http://localhost:{args.port}/")
    print()

    uvicorn.run(
        "quant_office.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )

if __name__ == "__main__":
    main()
```

#### 2.3.2 独立模式应用工厂 `quant_office/app.py`

```python
"""独立运行模式：完整的 FastAPI 应用工厂"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .logging_config import setup_logging
from .data.database import init_database
from .core.websocket_manager import WebSocketManager
from .api import agents, strategies, backtests, trades, risk, reports, dashboard

setup_logging(level=settings.log_level)


def create_app() -> FastAPI:
    app = FastAPI(
        title="QuantOffice",
        description="像素风格量化交易指挥中枢",
        version="1.0.0",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 初始化数据库
    init_database()

    # WebSocket 管理器
    ws_manager = WebSocketManager()
    app.state.ws_manager = ws_manager

    # API 路由（独立模式前缀为 /api）
    prefix = "/api"
    app.include_router(agents.router, prefix=prefix)
    app.include_router(strategies.router, prefix=prefix)
    app.include_router(backtests.router, prefix=prefix)
    app.include_router(trades.router, prefix=prefix)
    app.include_router(risk.router, prefix=prefix)
    app.include_router(reports.router, prefix=prefix)
    app.include_router(dashboard.router, prefix=prefix)

    # WebSocket 端点（独立模式）
    app.add_api_websocket_route("/ws", ws_manager.handle_ws)

    # 静态资源（Godot WASM + 前端构建产物）
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.exists(static_dir):
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    # 根路由
    @app.get("/api/")
    async def root():
        return {
            "name": "QuantOffice",
            "version": "1.0.0",
            "mode": "standalone",
            "agents": ["chief", "data", "strategy", "risk", "execution", "report"],
            "docs": "/docs",
        }

    @app.get("/api/health")
    async def health():
        from datetime import datetime, timezone
        return {
            "status": "ok",
            "version": "1.0.0",
            "mode": "standalone",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    return app


app = create_app()
```

#### 2.3.3 插件模式外壳 `quant_office/plugin.py`

```python
"""QuantCell 插件模式入口：PluginBase 子类外壳

设计原则：
1. 业务逻辑 100% 复用 quant_office 内部模块
2. 本文件仅提供插件生命周期适配和路由前缀转换
3. 数据存储使用插件数据目录，避免污染源码
"""
import os
from fastapi import APIRouter
from plugins.plugin_base import PluginBase

from .config import settings
from .logging_config import setup_logging
from .data.database import init_database
from .core.websocket_manager import WebSocketManager
from .core.event_publisher import EventPublisher
from .api import agents, strategies, backtests, trades, risk, reports, dashboard

setup_logging(level=settings.log_level)


class QuantOfficePlugin(PluginBase):
    def __init__(self):
        super().__init__("quant_office", "1.0.0")
        self.load_type = "hot"  # 支持热加载
        self.description = "像素风格量化交易指挥中枢，支持多Agent协作、策略回测、风险监控与可视化交易执行"
        self.author = "QuantOffice Team"
        self.frontend_entry = "/index.js"  # 前端资源入口

        # 插件数据目录隔离
        plugin_data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data"
        )
        os.makedirs(plugin_data_dir, exist_ok=True)

        # 初始化数据库（使用插件数据目录）
        init_database(db_dir=plugin_data_dir)

        # WebSocket 与事件发布器
        self.ws_manager = WebSocketManager()
        self.event_publisher = EventPublisher()

        # 创建插件路由
        self.router = APIRouter(prefix="/api/plugins/quant-office")
        self._setup_routes()
        self._setup_websocket()
        self._setup_events()

    def _setup_routes(self):
        """注册业务 API 路由到插件命名空间"""
        self.router.include_router(agents.router)
        self.router.include_router(strategies.router)
        self.router.include_router(backtests.router)
        self.router.include_router(trades.router)
        self.router.include_router(risk.router)
        self.router.include_router(reports.router)
        self.router.include_router(dashboard.router)

    def _setup_websocket(self):
        """注册 WebSocket 到插件路由"""
        self.router.add_api_websocket_route("/ws", self.ws_manager.handle_ws)

    def _setup_events(self):
        """注册 EventBus 事件监听，实现插件间通信"""
        # 监听其他插件的数据事件，转发到本插件的 WebSocket 客户端
        self.event_publisher.subscribe("market_data", self._on_market_data)
        self.event_publisher.subscribe("trade_signal", self._on_trade_signal)

    async def _on_market_data(self, data):
        await self.ws_manager.broadcast({"type": "market_data", "payload": data})

    async def _on_trade_signal(self, data):
        await self.ws_manager.broadcast({"type": "trade_signal", "payload": data})

    @self.router.get("/health")
    async def health():
        return {
            "status": "ok",
            "plugin": self.name,
            "version": self.version,
            "mode": "plugin",
            "agents": ["chief", "data", "strategy", "risk", "execution", "report"],
        }

    def register(self, plugin_manager):
        super().register(plugin_manager)
        self.logger.info(f"{self.name} 插件注册成功，版本: {self.version}")

    def start(self):
        super().start()
        # 启动 Agent 调度器
        from .core.agent_scheduler import AgentScheduler
        self.scheduler = AgentScheduler()
        self.scheduler.start_all()
        self.logger.info(f"{self.name} 启动成功，所有 Agent 已就绪")

    def stop(self):
        super().stop()
        if hasattr(self, "scheduler"):
            self.scheduler.stop_all()
        self.logger.info(f"{self.name} 停止成功")

    def on_enable(self):
        self.logger.info(f"{self.name} 已启用")

    def on_disable(self):
        self.logger.info(f"{self.name} 已禁用")

    def get_config_schema(self):
        """返回插件配置 JSON Schema，前端自动生成配置表单"""
        return {
            "type": "object",
            "properties": {
                "axon_quant_config": {
                    "type": "string",
                    "title": "axon_quant 引擎配置文件路径",
                    "default": "./config/quant.yaml",
                },
                "default_exchange": {
                    "type": "string",
                    "title": "默认交易所",
                    "enum": ["binance", "okx", "bybit"],
                    "default": "binance",
                },
                "risk_max_drawdown": {
                    "type": "number",
                    "title": "最大回撤阈值 (%)",
                    "default": 5.0,
                    "minimum": 0.1,
                    "maximum": 50.0,
                },
                "pixel_fps": {
                    "type": "integer",
                    "title": "像素办公室渲染帧率",
                    "default": 30,
                    "minimum": 15,
                    "maximum": 60,
                },
            },
        }


def register_plugin():
    """QuantCell 插件系统入口函数约定"""
    return QuantOfficePlugin()
```

#### 2.3.4 前端插件入口 `frontend/src/plugins/quant-office/index.tsx`

```typescript
/**
 * QuantOffice 前端插件入口
 * 
 * 设计原则：
 * 1. 插件模式通过 PluginRegistry 注册菜单和路由
 * 2. 独立模式通过 main.tsx 直接渲染
 * 3. 业务组件 100% 复用，仅入口逻辑不同
 */
import { pluginRegistry } from '@/plugins';
import { PixelOfficePage } from './components/PixelOfficePage';
import { AgentDashboardPage } from './components/AgentDashboardPage';
import { StrategyManagerPage } from './components/StrategyManagerPage';
import { RiskMonitorPage } from './components/RiskMonitorPage';
import { BacktestLabPage } from './components/BacktestLabPage';

// 插件 API 前缀适配：独立模式用 /api，插件模式用 /api/plugins/quant-office
const API_PREFIX = import.meta.env.VITE_PLUGIN_MODE === 'quantcell'
  ? '/api/plugins/quant-office'
  : '/api';

export { API_PREFIX };

// 注册菜单项
pluginRegistry.registerMenu({
  key: 'quant-office',
  label: 'QuantOffice',
  icon: '🏢',
  pluginName: 'quant-office',
  children: [
    { key: 'pixel-office', label: '像素办公室', icon: '🖥️' },
    { key: 'agent-dashboard', label: 'Agent 面板', icon: '🤖' },
    { key: 'strategy-manager', label: '策略管理', icon: '📈' },
    { key: 'risk-monitor', label: '风控监控', icon: '🛡️' },
    { key: 'backtest-lab', label: '回测实验室', icon: '🔬' },
  ],
});

// 注册路由
pluginRegistry.registerRoute({
  path: '/plugins/quant-office',
  element: <PixelOfficePage />,
  pluginName: 'quant-office',
});

pluginRegistry.registerRoute({
  path: '/plugins/quant-office/agents',
  element: <AgentDashboardPage />,
  pluginName: 'quant-office',
});

pluginRegistry.registerRoute({
  path: '/plugins/quant-office/strategies',
  element: <StrategyManagerPage />,
  pluginName: 'quant-office',
});

pluginRegistry.registerRoute({
  path: '/plugins/quant-office/risk',
  element: <RiskMonitorPage />,
  pluginName: 'quant-office',
});

pluginRegistry.registerRoute({
  path: '/plugins/quant-office/backtest',
  element: <BacktestLabPage />,
  pluginName: 'quant-office',
});

// Godot WASM 资源注册（插件模式下由 PluginLoader 动态加载）
pluginRegistry.registerAsset({
  pluginName: 'quant-office',
  js: '/api/plugins/quant-office/assets/godot/quant_office.js',
  wasm: '/api/plugins/quant-office/assets/godot/quant_office.wasm',
  pck: '/api/plugins/quant-office/assets/godot/quant_office.pck',
});
```

#### 2.3.5 插件清单 `manifest.json`

```json
{
  "name": "quant-office",
  "version": "1.0.0",
  "description": "像素风格量化交易指挥中枢，支持多Agent协作、策略回测、风险监控与可视化交易执行",
  "author": "QuantOffice Team",
  "main": "plugin.py",
  "load_type": "hot",
  "min_system_version": "2.0.0",
  "permissions": [
    "database.read",
    "database.write",
    "websocket.broadcast",
    "event.publish",
    "event.subscribe"
  ],
  "config_schema": {
    "type": "object",
    "properties": {
      "axon_quant_config": {
        "type": "string",
        "title": "axon_quant 引擎配置文件路径",
        "default": "./config/quant.yaml"
      },
      "default_exchange": {
        "type": "string",
        "title": "默认交易所",
        "enum": ["binance", "okx", "bybit"],
        "default": "binance"
      },
      "risk_max_drawdown": {
        "type": "number",
        "title": "最大回撤阈值 (%)",
        "default": 5.0,
        "minimum": 0.1,
        "maximum": 50.0
      },
      "pixel_fps": {
        "type": "integer",
        "title": "像素办公室渲染帧率",
        "default": 30,
        "minimum": 15,
        "maximum": 60
      }
    }
  },
  "frontend_entry": "/index.js",
  "dependencies": []
}
```

#### 2.3.6 业务路由共享示例 `quant_office/api/agents.py`

```python
"""Agent 状态与控制 API — 独立模式和插件模式 100% 复用"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Dict, Any

from ..services.agent_service import AgentService

router = APIRouter(prefix="/agents", tags=["agents"])
agent_service = AgentService()


@router.get("/")
async def list_agents() -> List[Dict[str, Any]]:
    """获取所有 Agent 状态"""
    return await agent_service.list_agents()


@router.get("/{agent_id}")
async def get_agent(agent_id: str) -> Dict[str, Any]:
    """获取指定 Agent 详情"""
    return await agent_service.get_agent(agent_id)


@router.post("/{agent_id}/command")
async def send_command(agent_id: str, command: Dict[str, Any]):
    """向 Agent 发送指令"""
    return await agent_service.send_command(agent_id, command)


@router.get("/{agent_id}/logs")
async def get_agent_logs(agent_id: str, limit: int = 100):
    """获取 Agent 运行日志"""
    return await agent_service.get_logs(agent_id, limit)
```

### 2.4 双模式运行时差异对比

| 维度 | 独立运行模式 | QuantCell 插件模式 |
|------|-------------|-------------------|
| **启动方式** | `python run.py --port 8000` | 放入 `backend/plugins/quant-office/`，QuantCell 自动扫描加载 |
| **入口文件** | `quant_office/app.py` | `quant_office/plugin.py` |
| **API 前缀** | `/api/agents` | `/api/plugins/quant-office/agents` |
| **WebSocket** | `/ws` | `/api/plugins/quant-office/ws` |
| **前端路由** | `/` (自有域名) | `/plugins/quant-office` (嵌入 QuantCell) |
| **前端 API** | `/api/*` | `/api/plugins/quant-office/*` |
| **数据目录** | `./data/` | `backend/plugins/quant-office/data/` |
| **CORS** | 需自行配置 | 继承 QuantCell 全局 CORS |
| **认证** | 需自行实现 | 继承 QuantCell JWT 认证 |
| **日志** | 独立日志文件 | 通过 PluginBase.logger 写入 QuantCell 日志系统 |
| **事件通信** | 内部 WebSocket | EventBus + WebSocket 双通道 |
| **部署方式** | Docker / 直接运行 | ZIP 上传 / Git 克隆 / 手动放置 |

### 2.5 Godot 场景的双模式适配

Godot 导出的 WebAssembly 场景需要适配两种模式的前端环境：

```gdscript
# react_bridge.gd — React ↔ Godot 通信桥接
extends Node

class_name ReactBridge

# 信号定义
signal on_react_event(event_type, payload)
signal on_config_loaded(config)

# API 前缀：根据运行模式动态确定
var api_prefix: String = "/api"
var ws_url: String = "ws://localhost:8000/ws"

func _ready():
    # 从 JavaScript 环境读取运行模式
    if OS.has_feature("JavaScript"):
        var mode = JavaScriptBridge.eval("window.QUANT_OFFICE_MODE || 'standalone'")
        if mode == "quantcell":
            api_prefix = "/api/plugins/quant-office"
            ws_url = "ws://" + JavaScriptBridge.eval("window.location.host") + "/api/plugins/quant-office/ws"
        _connect_websocket()
        _setup_postmessage_bridge()

func _connect_websocket():
    # WebSocket 连接逻辑...
    pass

func _setup_postmessage_bridge():
    # 监听 React 的 postMessage 事件
    JavaScriptBridge.eval("""
        window.addEventListener('message', function(e) {
            if (e.data && e.data.source === 'quant-office-react') {
                window.godotBridge.handleReactEvent(e.data.type, e.data.payload);
            }
        });
    """)

# Godot → React 发送事件
func emit_to_react(event_type: String, payload: Dictionary):
    if OS.has_feature("JavaScript"):
        JavaScriptBridge.eval("window.parent.postMessage({source: 'quant-office-godot', type: '%s', payload: %s}, '*')" % [event_type, JSON.stringify(payload)])

# React → Godot 接收事件（由 JS 回调触发）
func handle_react_event(event_type: String, payload: Dictionary):
    on_react_event.emit(event_type, payload)
```

---

## 三、开发工作流程

### 3.1 独立开发阶段（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/your-org/quantoffice.git
cd quantoffice

# 2. 安装后端依赖
uv sync

# 3. 启动独立后端（热重载）
python run.py --port 8000 --reload

# 4. 安装前端依赖
cd frontend
bun install

# 5. 启动前端开发服务器
bun run dev

# 6. 打开浏览器访问 http://localhost:5173
```

### 3.2 插件集成测试阶段

```bash
# 1. 将插件目录复制到 QuantCell 的插件目录
cp -r quantoffice/quant_office /path/to/quantcell/backend/plugins/quant-office
cp quantoffice/manifest.json /path/to/quantcell/backend/plugins/quant-office/

# 2. 将前端插件复制到 QuantCell 前端插件目录
cp -r quantoffice/frontend/src/plugins/quant-office /path/to/quantcell/frontend/src/plugins/

# 3. 重启 QuantCell 后端
python service_manager.py restart backend

# 4. 重新构建 QuantCell 前端（生产模式）
cd /path/to/quantcell/frontend
bun run build

# 5. 访问 QuantCell → 设置 → 插件管理 → 启用 quant-office
```

### 3.3 使用 QuantCell 独立开发服务器调试

```bash
cd /path/to/quantcell/backend

# 启动插件独立开发服务器（自动热重载）
python -m plugins.plugin_dev run \
    --plugin-dir plugins/quant-office \
    --port 9000 \
    --reload

# 调试端点：
#   GET  http://localhost:9000/dev/health
#   POST http://localhost:9000/dev/reload
```

### 3.4 打包发布

```bash
# 打包后端插件
python /path/to/quantcell/plugin_packer.py quantoffice/quant_office

# 打包前端插件
python /path/to/quantcell/plugin_packer.py quantoffice/frontend/src/plugins/quant-office

# 生成产物：
#   quant-office-1.0.0-backend.zip
#   quant-office-1.0.0-frontend.zip
```

---

## 四、与 WalletMonitor 的差异与优化

| 维度 | WalletMonitor | QuantOffice（本方案） |
|------|--------------|---------------------|
| **业务复杂度** | 单领域（钱包监控） | 多 Agent 协作（数据/策略/风控/执行/报告） |
| **前端形态** | 传统 React + Ant Design | Godot WebAssembly 像素场景 + React UI Shell |
| **实时通信** | 轮询为主 | WebSocket + SSE + EventBus 三通道 |
| **可视化** | ECharts 图表 | 像素办公室 + ECharts 混合 |
| **引擎集成** | 无外部引擎 | axon_quant 量化交易引擎 |
| **多模式 API 适配** | 手动前缀切换 | 环境变量自动适配（VITE_PLUGIN_MODE） |
| **Godot 资源加载** | 不涉及 | PluginLoader 动态加载 WASM/PCK |
| **事件总线** | 未使用 | 深度集成 EventBus 实现跨插件通信 |

---

## 五、axon_quant 深度集成设计

### 5.1 引擎适配器 `engine_adapter.py`

```python
"""axon_quant 引擎适配器 — 封装真实 axon_quant 0.3.0 API"""
from typing import Dict, Any, Optional
import axon_quant
from axon_quant.llm import LLMBackend, ReActAgent, SwarmOrchestrator, AgentRole
from axon_quant.risk import RiskEngine
from axon_quant.oms import OrderManagementSystem
from axon_quant.exchange import BinanceAdapter, OkxAdapter
from axon_quant.backtest import BacktestEngine
from axon_quant.rl import TradingEnv
from axon_quant.data import DataLoader


class AxonQuantAdapter:
    """axon_quant 统一适配器
    
    为 QuantOffice 的 6 个 Agent 提供真实 axon_quant API 的封装入口，
    实现 Agent 业务逻辑与底层引擎的解耦。
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # 初始化 LLM 后端（ChiefTrader 用）
        self.llm = LLMBackend.new(
            api_key=config["llm_api_key"],
            model=config.get("llm_model", "deepseek-chat"),
        )
        
        # 初始化 SwarmOrchestrator（Agent 生命周期管理）
        self.orchestrator = SwarmOrchestrator()
        
        # 初始化风控引擎
        self.risk_engine = RiskEngine.new(
            pre_trade_check=True,
            circuit_breaker_enabled=True,
        )
        
        # 初始化 OMS
        self.oms = OrderManagementSystem.new()
        
        # 初始化交易所适配器
        exchange_id = config.get("exchange", "binance")
        if exchange_id == "binance":
            self.exchange = BinanceAdapter(config["exchange_config"])
        else:
            self.exchange = OkxAdapter(config["exchange_config"])
        
        # 初始化数据加载器
        self.data_loader = DataLoader.new()
        
        # 实验追踪器（可选 MLflow）
        from axon_quant.tracker import MemoryTracker
        self.tracker = MemoryTracker.new()
    
    def create_trading_env(self, strategy_config: Dict[str, Any]) -> TradingEnv:
        """为 StrategyAgent 创建 TradingEnv"""
        return TradingEnv.new(
            config=strategy_config,
            data_loader=self.data_loader,
        )
    
    def create_backtest_engine(self, env: TradingEnv, params: Dict[str, Any]) -> BacktestEngine:
        """为 StrategyAgent 创建 BacktestEngine"""
        return BacktestEngine.new(
            env=env,
            matching_level=params.get("matching_level", "L1"),
            impact_model=params.get("impact_model", "almgren_chriss"),
        )
    
    def pre_trade_risk_check(self, order: Dict[str, Any], portfolio) -> bool:
        """RiskAgent 预交易风控检查 — 12ns 级响应"""
        from axon_quant.risk import RiskCheckRequest
        request = RiskCheckRequest(
            symbol=order["symbol"],
            side=order["side"],
            quantity=order["quantity"],
            price=order.get("price", 0),
            portfolio=portfolio,
        )
        result = self.risk_engine.check(request)
        return result.passed
    
    async def submit_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """ExecutionAgent 提交订单"""
        from axon_quant.oms import Order, OrderId, OrderType, Side, TimeInForce
        o = Order(
            client_order_id=OrderId.new(),
            symbol=order["symbol"],
            side=Side.Buy if order["side"] == "buy" else Side.Sell,
            order_type=OrderType.Market if order["type"] == "market" else OrderType.Limit,
            quantity=order["quantity"],
            price=order.get("price"),
            time_in_force=TimeInForce.Gtc,
        )
        order_id = await self.oms.submit_order(o)
        exchange_id = await self.exchange.send_order(o)
        return {"order_id": str(order_id), "exchange_order_id": str(exchange_id)}


# 全局单例（双模式共享）
_engine_adapter: Optional[AxonQuantAdapter] = None

def get_engine_adapter(config: Optional[Dict[str, Any]] = None) -> AxonQuantAdapter:
    global _engine_adapter
    if _engine_adapter is None:
        if config is None:
            raise RuntimeError("AxonQuantAdapter 未初始化")
        _engine_adapter = AxonQuantAdapter(config)
    return _engine_adapter
```

### 5.2 axon_quant Agent Swarm 与 QuantOffice Agent 映射

axon_quant 内置 **Agent Swarm**（`axon-llm` crate）与 QuantOffice 的 1+5 Agent 设计天然对齐：

| QuantOffice Agent | axon_quant Swarm 角色 | 底层 Crate | 核心 API |
|---|---|---|---|
| ChiefTrader | SwarmOrchestrator + ReActAgent | `axon-llm` | `LLMBackend`, `ReActAgent`, `SwarmOrchestrator` |
| DataAgent | 数据管道 | `axon-data` | `DataLoader`, `FeaturePipeline`, `RecordBatch` |
| StrategyAgent | RL 环境 + 回测引擎 | `axon-rl`, `axon-backtest` | `TradingEnv`, `BacktestEngine`, `VecEnv` |
| RiskAgent | 风控引擎 | `axon-risk` | `RiskEngine`, `CircuitBreaker`, `VaRLimit` |
| ExecutionAgent | OMS + 交易所适配器 | `axon-oms`, `axon-exchange` | `OrderManagementSystem`, `BinanceAdapter` |
| ReportAgent | 合规 + 可解释性 | `axon-compliance`, `axon-explain` | `ComplianceEngine`, `KernelSHAP` |

### 5.3 Arrow RecordBatch 零拷贝数据流

QuantOffice 双模式共享 axon_quant 的 Arrow `RecordBatch` 数据格式，无需格式转换：

```python
# DataAgent → Arrow RecordBatch
record_batch = await data_agent.load_market_data("BTCUSDT", "1h")

# StrategyAgent 直接消费同一 RecordBatch（零拷贝）
env = engine_adapter.create_trading_env({"symbol": "BTCUSDT"})

# ReportAgent 基于同一数据生成报告
report = await report_agent.generate_daily_report(portfolio, trades)
```

### 5.4 事件驱动桥接

axon_quant 的 `crossbeam-channel` 事件队列（100K bounded，零锁设计）与 QuantOffice WebSocket 对接：

```python
from axon_quant.core import EventBus

class QuantOfficeEventBridge:
    def __init__(self, ws_manager):
        self.ws_manager = ws_manager
        self.event_bus = EventBus.new()
    
    async def subscribe(self):
        self.event_bus.subscribe("order_filled", self._on_order_filled)
        self.event_bus.subscribe("risk_alert", self._on_risk_alert)
        self.event_bus.subscribe("backtest_complete", self._on_backtest_complete)
    
    async def _on_risk_alert(self, event):
        await self.ws_manager.broadcast({
            "type": "risk_alert",
            "agent": "RiskAgent",
            "severity": event.severity,
        })
```

---

## 六、技术风险与应对

| 风险 | 影响 | 应对方案 |
|------|------|----------|
| Godot WASM 文件体积大（>10MB） | 插件安装包过大 | 1. 启用 Brotli/Gzip 压缩<br>2. 按需加载场景资源<br>3. CDN 托管静态资源 |
| axon_quant Rust 编译依赖复杂 | 部署环境缺少 Rust 工具链 | 1. 使用 `pip install axon_quant==0.3.0` 预编译 wheel<br>2. Docker 镜像预装编译环境<br>3. 提供 ARM64/x86_64 双架构包 |
| WebSocket 与 QuantCell 冲突 | 端口/路径冲突 | 1. 使用 QuantCell 统一 WebSocket 管理器<br>2. 插件 WebSocket 挂载到子路径 |
| axon_quant 与 QuantCell 数据模型冲突 | ORM 表名冲突 | 1. 插件表名加前缀 `qo_`<br>2. 使用独立数据库文件 |
| Godot 与 React 版本兼容性 | 渲染异常 | 1. 锁定 Godot 4.3+ LTS 版本<br>2. 使用 react-godot-bridge 官方适配版 |
| 热加载导致 Godot WASM 状态丢失 | 用户体验中断 | 1. Godot 场景状态持久化到 localStorage<br>2. 热重载时恢复场景状态 |

---

## 六、总结

本方案参考 WalletMonitor 的双模式设计精髓，将 QuantOffice 重构为**"业务逻辑 100% 复用、仅入口和路由前缀适配"**的插件化架构：

1. **独立模式**（`app.py` + `run.py`）：面向个人交易者，一键启动完整服务
2. **插件模式**（`plugin.py` + `manifest.json`）：面向 QuantCell 生态用户，无缝集成到现有平台

两种模式共享 `core/`、`agents/`、`api/`、`data/`、`services/` 等全部业务代码，仅需维护一套代码库即可同时服务两种场景。Godot 像素办公室通过 `JavaScriptBridge` 动态检测运行模式，自动适配 API 前缀和 WebSocket 地址，确保前端体验一致。

---

*文档版本: v1.0*
*日期: 2026-07-09*
