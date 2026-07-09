"""配置管理 — 独立模式与插件模式共享。

通过环境变量 ``QUANT_OFFICE_*`` 覆盖默认值。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _project_root() -> Path:
    """推断项目根目录。

    优先级：
    1. ``QUANT_OFFICE_ROOT`` 环境变量
    2. 当前工作目录
    3. ``quant_office`` 包的父目录
    """
    env_root = os.environ.get("QUANT_OFFICE_ROOT")
    if env_root:
        return Path(env_root).resolve()
    return Path.cwd().resolve()


class Settings(BaseSettings):
    """QuantOffice 全局配置（双模式共享）。"""

    model_config = SettingsConfigDict(
        env_prefix="QUANT_OFFICE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- 基础 ----
    app_name: str = "QuantOffice"
    version: str = "0.1.0"
    mode: Literal["standalone", "plugin"] = "standalone"
    log_level: str = "INFO"
    debug: bool = False

    # ---- 服务 ----
    host: str = "0.0.0.0"
    port: int = 8000

    # ---- 路径 ----
    project_root: Path = Field(default_factory=_project_root)
    data_dir: Path | None = None  # 留空时自动使用 ``<root>/data``
    static_dir: Path | None = None  # 留空时使用 ``<root>/quant_office/static``

    # ---- axon_quant 引擎 ----
    axon_enabled: bool = False  # 未安装 axon_quant 时保持 False
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_base_url: str = "https://api.deepseek.com"

    # ---- 交易所 ----
    default_exchange: Literal["binance", "okx", "bybit"] = "binance"
    exchange_testnet: bool = True
    binance_api_key: str = ""
    binance_api_secret: str = ""

    # ---- 风控 ----
    risk_max_drawdown: float = 0.05
    risk_warning_drawdown: float = 0.03
    risk_max_position_ratio: float = 1.0
    risk_max_var: float = 0.02
    circuit_breaker_threshold: int = 5
    circuit_breaker_reset_sec: int = 60

    # ---- 像素办公室 ----
    pixel_fps: int = 30
    frontend_static_dir: str = "./frontend/dist"

    # ---- 数据库 ----
    database_url: str = "sqlite+aiosqlite:///./data/quant_office.db"

    # ---- Redis (可选) ----
    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = False

    # ---- CORS ----
    cors_allow_origins: str = "*"

    @property
    def resolved_data_dir(self) -> Path:
        return self.data_dir or self.project_root / "data"

    @property
    def resolved_static_dir(self) -> Path:
        return self.static_dir or Path(__file__).resolve().parent / "static"


settings = Settings()


def get_settings() -> Settings:
    """FastAPI 依赖注入使用的工厂方法。"""
    return settings
