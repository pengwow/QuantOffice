"""Settings API — LLM / Exchange / Risk 运行时配置。

端点（standalone 模式在 ``/api/settings`` 前缀下；插件模式在 ``/api/plugins/quant-office/settings``）：
  GET   /settings/llm-presets                       -> 预置 provider 模板
  GET   /settings/exchange-presets                  -> 预置 venue 模板
  GET   /settings/llm                               -> 当前 LLM 配置（api_key 脱敏）
  PUT   /settings/llm                               -> 更新 LLM 配置
  POST  /settings/llm/test                          -> 联通测试
  GET   /settings/exchange                          -> 当前 Exchange 配置
  PUT   /settings/exchange                          -> 更新 Exchange 配置
  POST  /settings/exchange/test                     -> 联通测试
  GET   /settings/risk                              -> 当前 Risk 配置
  PUT   /settings/risk                              -> 更新 Risk 配置
  GET   /settings/snapshot                          -> 全部配置快照（脱敏）
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..core.exchange_client import VENUE_PRESETS, ExchangeClient
from ..core.llm_client import LLMClient, PROVIDER_PRESETS
from ..core.runtime_config import (
    ExchangeConfig,
    LLMConfig,
    RiskConfig,
    get_runtime_config,
)
from ..logging_config import get_logger

logger = get_logger("api.settings")
router = APIRouter(prefix="/settings", tags=["settings"])


# ============================================================
# Presets
# ============================================================
@router.get("/llm-presets", response_model=List[Dict[str, str]])
async def list_llm_presets() -> List[Dict[str, str]]:
    """返回所有预置 LLM provider 模板（用于前端下拉）。"""
    out: List[Dict[str, str]] = []
    for key, info in PROVIDER_PRESETS.items():
        out.append({
            "key": key,
            "label": info.get("label", key),
            "base_url": info.get("base_url", ""),
            "default_model": info.get("default_model", ""),
        })
    return out


@router.get("/exchange-presets", response_model=List[Dict[str, str]])
async def list_exchange_presets() -> List[Dict[str, str]]:
    """返回所有预置交易所模板。"""
    out: List[Dict[str, str]] = []
    for key, info in VENUE_PRESETS.items():
        out.append({
            "key": key,
            "label": info.get("label", key),
            "base_url": info.get("base_url", ""),
            "testnet_base_url": info.get("testnet_base_url", ""),
        })
    return out


# ============================================================
# LLM
# ============================================================
@router.get("/llm", response_model=Dict[str, Any])
async def get_llm() -> Dict[str, Any]:
    """当前 LLM 配置（api_key 自动脱敏）。"""
    store = get_runtime_config()
    cfg = store.get_llm()
    snap = cfg.model_dump()
    if snap.get("api_key"):
        snap["api_key"] = store._mask(snap["api_key"])
    # 脱敏仍保留 4 字符前后缀，便于 UI 提示
    snap["api_key_set"] = bool(cfg.api_key)
    return snap


class LLMUpdateBody(BaseModel):
    enabled: bool | None = None
    provider: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=32768)
    timeout_sec: int | None = Field(default=None, ge=1, le=300)


@router.put("/llm", response_model=Dict[str, Any])
async def update_llm(body: LLMUpdateBody) -> Dict[str, Any]:
    store = get_runtime_config()
    payload = body.model_dump(exclude_unset=True)

    # 切换 provider 时自动填默认 base_url/model（除非显式提供）
    if "provider" in payload and payload["provider"] in PROVIDER_PRESETS:
        preset = PROVIDER_PRESETS[payload["provider"]]
        if "base_url" not in payload or not payload.get("base_url"):
            payload["base_url"] = preset.get("base_url", "")
        if "model" not in payload or not payload.get("model"):
            payload["model"] = preset.get("default_model", "")

    # api_key 保留原值（不允许覆盖为 "" / "***"）
    if payload.get("api_key") in ("", "***", None):
        payload.pop("api_key", None)

    cfg = store.update_llm(payload)
    snap = cfg.model_dump()
    if snap.get("api_key"):
        snap["api_key"] = store._mask(snap["api_key"])
    snap["api_key_set"] = bool(cfg.api_key)
    logger.info("LLM 配置已更新: enabled=%s provider=%s", cfg.enabled, cfg.provider)
    return snap


@router.post("/llm/test", response_model=Dict[str, Any])
async def test_llm() -> Dict[str, Any]:
    """实时联通测试：用当前已保存的配置发送 1 个最小请求。"""
    cfg = get_runtime_config().get_llm()
    if not cfg.enabled:
        return {"ok": False, "error": "LLM 未启用（请先启用开关再保存）"}
    if not cfg.api_key:
        return {"ok": False, "error": "API key 未配置"}
    try:
        client = LLMClient(cfg)
        result = client.test_connection()
        logger.info("LLM 联通测试: %s", result)
        return result
    except Exception as exc:  # pragma: no cover
        logger.exception("LLM 测试失败: %s", exc)
        return {"ok": False, "error": str(exc)}


# ============================================================
# Exchange
# ============================================================
@router.get("/exchange", response_model=Dict[str, Any])
async def get_exchange() -> Dict[str, Any]:
    store = get_runtime_config()
    cfg = store.get_exchange()
    snap = cfg.model_dump()
    if snap.get("api_key"):
        snap["api_key"] = store._mask(snap["api_key"])
    if snap.get("api_secret"):
        snap["api_secret"] = store._mask(snap["api_secret"])
    snap["api_key_set"] = bool(cfg.api_key)
    snap["api_secret_set"] = bool(cfg.api_secret)
    return snap


class ExchangeUpdateBody(BaseModel):
    enabled: bool | None = None
    venue: str | None = None
    api_key: str | None = None
    api_secret: str | None = None
    testnet: bool | None = None
    timeout_sec: int | None = Field(default=None, ge=1, le=60)


@router.put("/exchange", response_model=Dict[str, Any])
async def update_exchange(body: ExchangeUpdateBody) -> Dict[str, Any]:
    store = get_runtime_config()
    payload = body.model_dump(exclude_unset=True)

    if payload.get("api_key") in ("", "***", None):
        payload.pop("api_key", None)
    if payload.get("api_secret") in ("", "***", None):
        payload.pop("api_secret", None)

    cfg = store.update_exchange(payload)
    snap = cfg.model_dump()
    if snap.get("api_key"):
        snap["api_key"] = store._mask(snap["api_key"])
    if snap.get("api_secret"):
        snap["api_secret"] = store._mask(snap["api_secret"])
    snap["api_key_set"] = bool(cfg.api_key)
    snap["api_secret_set"] = bool(cfg.api_secret)
    logger.info("Exchange 配置已更新: venue=%s testnet=%s", cfg.venue, cfg.testnet)
    return snap


@router.post("/exchange/test", response_model=Dict[str, Any])
async def test_exchange() -> Dict[str, Any]:
    """实时联通测试：ping 交易所并拉一次 BTC ticker。"""
    cfg = get_runtime_config().get_exchange()
    try:
        client = ExchangeClient(cfg)
        result = client.test_connection()
        logger.info("Exchange 联通测试: %s", result)
        return result
    except Exception as exc:
        logger.exception("Exchange 测试失败: %s", exc)
        return {"ok": False, "error": str(exc)}


# ============================================================
# Risk
# ============================================================
@router.get("/risk", response_model=Dict[str, Any])
async def get_risk() -> Dict[str, Any]:
    cfg = get_runtime_config().get_risk()
    return cfg.model_dump()


class RiskUpdateBody(BaseModel):
    max_drawdown: float | None = Field(default=None, ge=0.0, le=1.0)
    warning_drawdown: float | None = Field(default=None, ge=0.0, le=1.0)
    max_position_ratio: float | None = Field(default=None, ge=0.0, le=10.0)
    circuit_breaker_threshold: int | None = Field(default=None, ge=1, le=1000)


@router.put("/risk", response_model=Dict[str, Any])
async def update_risk(body: RiskUpdateBody) -> Dict[str, Any]:
    store = get_runtime_config()
    payload = body.model_dump(exclude_unset=True)
    cfg = store.update_risk(payload)
    logger.info("Risk 配置已更新: %s", payload)
    return cfg.model_dump()


# ============================================================
# Snapshot
# ============================================================
@router.get("/snapshot", response_model=Dict[str, Any])
async def snapshot() -> Dict[str, Any]:
    """返回完整运行时配置（敏感字段脱敏）。"""
    return get_runtime_config().snapshot(mask_secrets=True)
