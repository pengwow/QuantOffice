"""运行时配置存储 — 覆盖 .env / 环境变量，支持热更新。

为什么需要这层？
  - ``config.Settings`` 只能在启动时从 .env 读取，无法热更新
  - 用户在 UI 填了 API key 后，必须立即生效（无需重启服务）
  - 加密存储敏感字段（api_key）— 仅写日志时打码

存储位置：``<data_dir>/runtime_config.json``
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from ..config import settings
from ..logging_config import get_logger

logger = get_logger("config.runtime")


# ============================================================
# LLM 配置模型
# ============================================================
class LLMConfig(BaseModel):
    """LLM 提供商配置（OpenAI 兼容接口）。"""

    enabled: bool = False
    provider: str = "deepseek"  # openai / deepseek / qwen / custom
    api_key: str = ""
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-chat"
    temperature: float = 0.3
    max_tokens: int = 1024
    timeout_sec: int = 30


class ExchangeConfig(BaseModel):
    """交易所配置（Binance / OKX / Bybit）。"""

    enabled: bool = False
    venue: str = "binance"  # binance / okx / bybit
    api_key: str = ""
    api_secret: str = ""
    testnet: bool = True
    timeout_sec: int = 10


class RiskConfig(BaseModel):
    """风控阈值（运行时覆盖 settings 默认值）。"""

    max_drawdown: float = 0.05
    warning_drawdown: float = 0.03
    max_position_ratio: float = 1.0
    circuit_breaker_threshold: int = 5


class RuntimeConfig(BaseModel):
    """运行时总配置（持久化到 JSON）。"""

    llm: LLMConfig = Field(default_factory=LLMConfig)
    exchange: ExchangeConfig = Field(default_factory=ExchangeConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    updated_at: str = ""

    def is_sensitive(self, key: str) -> bool:
        return key in ("api_key", "api_secret")


# ============================================================
# 存储 + 缓存
# ============================================================
class RuntimeConfigStore:
    """线程安全的运行时配置存储。

    - 启动时从 JSON 加载（无文件则用默认值）
    - 修改时落盘 + 内存更新
    - 提供 ``snapshot()`` / ``update_llm()`` 等 API
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or (settings.resolved_data_dir / "runtime_config.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._cfg: RuntimeConfig = self._load()

    # ----- IO -----
    def _load(self) -> RuntimeConfig:
        if not self.path.exists():
            logger.info("runtime_config.json 不存在，使用默认配置")
            return RuntimeConfig(updated_at="")
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            cfg = RuntimeConfig(**data)
            logger.info("runtime_config.json 已加载（LLM enabled=%s）", cfg.llm.enabled)
            return cfg
        except Exception as exc:  # pragma: no cover
            logger.exception("runtime_config.json 加载失败，使用默认: %s", exc)
            return RuntimeConfig(updated_at="")

    def _save(self) -> None:
        try:
            self.path.write_text(
                self._cfg.model_dump_json(indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            # chmod 600 — 仅当前用户可读（保护 api_key）
            try:
                os.chmod(self.path, 0o600)
            except Exception:  # pragma: no cover
                pass
        except Exception as exc:  # pragma: no cover
            logger.exception("runtime_config.json 保存失败: %s", exc)

    # ----- 公共 API -----
    def snapshot(self, *, mask_secrets: bool = True) -> Dict[str, Any]:
        """返回当前配置（默认隐藏 secret 字段）。"""
        with self._lock:
            data = self._cfg.model_dump()
            data["updated_at"] = data.get("updated_at", "")
            if mask_secrets:
                if data.get("llm", {}).get("api_key"):
                    data["llm"]["api_key"] = self._mask(data["llm"]["api_key"])
                if data.get("exchange", {}).get("api_key"):
                    data["exchange"]["api_key"] = self._mask(data["exchange"]["api_key"])
                if data.get("exchange", {}).get("api_secret"):
                    data["exchange"]["api_secret"] = self._mask(data["exchange"]["api_secret"])
            return data

    def get_llm(self) -> LLMConfig:
        with self._lock:
            return self._cfg.llm.model_copy()

    def get_exchange(self) -> ExchangeConfig:
        with self._lock:
            return self._cfg.exchange.model_copy()

    def get_risk(self) -> RiskConfig:
        with self._lock:
            return self._cfg.risk.model_copy()

    def update_llm(self, body: Dict[str, Any]) -> LLMConfig:
        """更新 LLM 配置（部分字段）。"""
        from datetime import datetime
        with self._lock:
            data = self._cfg.llm.model_dump()
            for k, v in body.items():
                if k in LLMConfig.model_fields:
                    data[k] = v
            # api_key 是空字符串 / 占位符时不变更
            if body.get("api_key") in ("", "***", None, "placeholder") and "api_key" in body:
                data.pop("api_key", None)
            self._cfg.llm = LLMConfig(**data)
            self._cfg.updated_at = datetime.utcnow().isoformat()
            self._save()
            return self._cfg.llm.model_copy()

    def update_exchange(self, body: Dict[str, Any]) -> ExchangeConfig:
        from datetime import datetime
        with self._lock:
            data = self._cfg.exchange.model_dump()
            for k, v in body.items():
                if k in ExchangeConfig.model_fields:
                    data[k] = v
            if body.get("api_key") in ("", "***", None, "placeholder"):
                data.pop("api_key", None)
            if body.get("api_secret") in ("", "***", None, "placeholder"):
                data.pop("api_secret", None)
            self._cfg.exchange = ExchangeConfig(**data)
            self._cfg.updated_at = datetime.utcnow().isoformat()
            self._save()
            return self._cfg.exchange.model_copy()

    def update_risk(self, body: Dict[str, Any]) -> RiskConfig:
        from datetime import datetime
        with self._lock:
            data = self._cfg.risk.model_dump()
            for k, v in body.items():
                if k in RiskConfig.model_fields:
                    data[k] = v
            self._cfg.risk = RiskConfig(**data)
            self._cfg.updated_at = datetime.utcnow().isoformat()
            self._save()
            return self._cfg.risk.model_copy()

    @staticmethod
    def _mask(secret: str) -> str:
        """``sk-1234567890abcdef`` -> ``sk-1********cdef``（前 4 后 4 明文）"""
        if not secret or len(secret) <= 8:
            return "***"
        return f"{secret[:4]}{'*' * (len(secret) - 8)}{secret[-4:]}"

    def real_llm_key(self) -> str:
        """未脱敏的真实 API key（仅服务端内部使用，绝不返回给前端）。"""
        with self._lock:
            return self._cfg.llm.api_key

    def real_exchange_key(self) -> tuple[str, str]:
        with self._lock:
            return self._cfg.exchange.api_key, self._cfg.exchange.api_secret


# ============================================================
# 全局单例
# ============================================================
_store: Optional[RuntimeConfigStore] = None
_store_lock = threading.Lock()


def get_runtime_config() -> RuntimeConfigStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = RuntimeConfigStore()
        return _store
