"""LLM 客户端 — OpenAI 兼容协议，支持 DeepSeek / OpenAI / 通义千问 / 自定义。

为什么自己写而不依赖 axon_quant？
  - ``axon_quant.llm.LLMBackend`` 是 PyO3 绑定，必须有 Rust 工具链 + 编译环境
  - 实际上绝大多数 LLM 协议都是 OpenAI 兼容的（POST /v1/chat/completions）
  - 我们已有 httpx 依赖，10 行代码就能直连
  - 这样不依赖 axon_quant 也能用真 LLM

提供能力：
  - ``LLMClient(config).chat(messages, **opts)`` → 同步返回
  - ``LLMClient(config).achat(...)`` → 异步流式
  - ``test_connection()`` → 健康检查
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from ..logging_config import get_logger
from .runtime_config import LLMConfig, get_runtime_config

logger = get_logger("core.llm")


# ============================================================
# 预置 provider 模板
# ============================================================
PROVIDER_PRESETS: Dict[str, Dict[str, str]] = {
    "deepseek": {
        "label": "DeepSeek（深度求索）",
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
    },
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
    },
    "qwen": {
        "label": "通义千问（DashScope）",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-turbo",
    },
    "zhipu": {
        "label": "智谱 AI（GLM）",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-flash",
    },
    "moonshot": {
        "label": "月之暗面（Kimi）",
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-8k",
    },
    "ollama": {
        "label": "Ollama（本地）",
        "base_url": "http://127.0.0.1:11434/v1",
        "default_model": "llama3.1:8b",
    },
    "custom": {
        "label": "自定义（OpenAI 兼容）",
        "base_url": "",
        "default_model": "",
    },
}


@dataclass
class ChatMessage:
    role: str   # system / user / assistant
    content: str


@dataclass
class ChatResponse:
    content: str
    model: str
    usage: Dict[str, int]
    elapsed_ms: int
    raw: Dict[str, Any]


class LLMError(RuntimeError):
    """LLM 调用错误（网络 / 鉴权 / 上限 等）。"""


# ============================================================
# 客户端
# ============================================================
class LLMClient:
    """OpenAI 兼容 LLM 客户端。"""

    def __init__(self, config: Optional[LLMConfig] = None) -> None:
        self.config = config or get_runtime_config().get_llm()

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

    def _endpoint(self) -> str:
        base = (self.config.base_url or "").rstrip("/")
        if not base:
            raise LLMError("base_url 未配置")
        # 兼容已含 /chat/completions 的情况
        if base.endswith("/chat/completions"):
            return base
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/chat/completions"

    # ---- 同步 ----
    def chat(
        self,
        messages: List[ChatMessage],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
    ) -> ChatResponse:
        if not self.config.enabled:
            raise LLMError("LLM 未启用（请到设置页启用并填入 API key）")
        if not self.config.api_key:
            raise LLMError("API key 未配置")

        payload = {
            "model": model or self.config.model,
            "messages": [m.__dict__ for m in messages],
            "temperature": temperature if temperature is not None else self.config.temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
            "stream": False,
        }
        t0 = time.time()
        try:
            with httpx.Client(timeout=self.config.timeout_sec) as client:
                resp = client.post(self._endpoint(), json=payload, headers=self._headers())
        except httpx.TimeoutException as exc:
            raise LLMError(f"LLM 请求超时 ({self.config.timeout_sec}s): {exc}") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM 网络错误: {exc}") from exc

        elapsed = int((time.time() - t0) * 1000)
        if resp.status_code != 200:
            raise LLMError(f"LLM HTTP {resp.status_code}: {resp.text[:300]}")
        try:
            data = resp.json()
        except json.JSONDecodeError as exc:
            raise LLMError(f"LLM 响应不是 JSON: {exc}") from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"LLM 响应字段异常: {data}") from exc

        return ChatResponse(
            content=content,
            model=data.get("model", self.config.model),
            usage=data.get("usage", {}),
            elapsed_ms=elapsed,
            raw=data,
        )

    # ---- 异步 ----
    async def achat(self, messages: List[ChatMessage], **opts) -> ChatResponse:
        return await asyncio.to_thread(self.chat, messages, **opts)

    async def astream(self, messages: List[ChatMessage], **opts) -> AsyncIterator[str]:
        """SSE 流式（OpenAI 兼容协议 /v1/chat/completions?stream=true）。"""
        if not self.config.enabled or not self.config.api_key:
            raise LLMError("LLM 未启用或 API key 缺失")
        payload = {
            "model": opts.get("model") or self.config.model,
            "messages": [m.__dict__ for m in messages],
            "temperature": opts.get("temperature", self.config.temperature),
            "max_tokens": opts.get("max_tokens") or self.config.max_tokens,
            "stream": True,
        }
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout_sec) as client:
                async with client.stream("POST", self._endpoint(), json=payload, headers=self._headers()) as resp:
                    if resp.status_code != 200:
                        body = await resp.aread()
                        raise LLMError(f"LLM HTTP {resp.status_code}: {body[:300].decode('utf-8', 'ignore')}")
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        chunk = line[5:].strip()
                        if chunk == "[DONE]":
                            break
                        try:
                            obj = json.loads(chunk)
                            delta = obj["choices"][0]["delta"].get("content", "")
                            if delta:
                                yield delta
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
        except httpx.TimeoutException as exc:
            raise LLMError(f"LLM 流式超时: {exc}") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM 流式网络错误: {exc}") from exc

    # ---- 健康检查 ----
    def test_connection(self) -> Dict[str, Any]:
        """快速 ping：发送 1 个最小请求验证鉴权 + 网络。"""
        if not self.config.api_key:
            return {"ok": False, "error": "API key 未配置"}
        if not self.config.base_url:
            return {"ok": False, "error": "base_url 未配置"}
        t0 = time.time()
        try:
            with httpx.Client(timeout=min(self.config.timeout_sec, 15)) as client:
                resp = client.post(
                    self._endpoint(),
                    json={
                        "model": self.config.model,
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 8,
                    },
                    headers=self._headers(),
                )
            elapsed = int((time.time() - t0) * 1000)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    return {
                        "ok": True,
                        "model": data.get("model", self.config.model),
                        "elapsed_ms": elapsed,
                        "usage": data.get("usage", {}),
                    }
                except json.JSONDecodeError:
                    return {"ok": True, "elapsed_ms": elapsed, "note": "non-JSON response"}
            return {
                "ok": False,
                "status": resp.status_code,
                "error": resp.text[:300],
                "elapsed_ms": elapsed,
            }
        except httpx.TimeoutException:
            return {"ok": False, "error": f"请求超时 ({self.config.timeout_sec}s)"}
        except httpx.HTTPError as exc:
            return {"ok": False, "error": f"网络错误: {exc}"}
        except Exception as exc:  # pragma: no cover
            return {"ok": False, "error": str(exc)}


# ============================================================
# 工厂
# ============================================================
def make_llm_client(config: Optional[LLMConfig] = None) -> LLMClient:
    return LLMClient(config or get_runtime_config().get_llm())


def is_llm_configured() -> bool:
    cfg = get_runtime_config().get_llm()
    return cfg.enabled and bool(cfg.api_key) and bool(cfg.base_url)
