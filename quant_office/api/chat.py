"""Chat API — 与 LLM 直接对话的端点。

端点：
  POST  /chat          -> {reply, model, usage, elapsed_ms, llm_used}
  POST  /chat/stream   -> SSE 流式 (text/event-stream)
  GET   /chat/status   -> {configured, enabled, provider, model, base_url}

设计：与 Settings/LLM 配置联动；LLM 未启用时给出 200 + 提示信息（不抛 5xx），
这样前端可以无感降级。
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Dict, List, Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..core.llm_client import ChatMessage, is_llm_configured, make_llm_client
from ..core.runtime_config import get_runtime_config
from ..logging_config import get_logger

logger = get_logger("api.chat")
router = APIRouter(prefix="/chat", tags=["chat"])


class ChatTurn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatTurn] = Field(default_factory=list)
    prompt: Optional[str] = None
    system: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=8192)


def _build_messages(body: ChatRequest) -> List[ChatMessage]:
    out: List[ChatMessage] = []
    if body.system:
        out.append(ChatMessage(role="system", content=body.system))
    if body.messages:
        for m in body.messages:
            out.append(ChatMessage(role=m.role, content=m.content))
    elif body.prompt:
        out.append(ChatMessage(role="user", content=body.prompt))
    return out


@router.get("/status", response_model=Dict[str, Any])
async def chat_status() -> Dict[str, Any]:
    cfg = get_runtime_config().get_llm()
    return {
        "configured": is_llm_configured(),
        "enabled": cfg.enabled,
        "provider": cfg.provider,
        "model": cfg.model,
        "base_url": cfg.base_url,
    }


@router.post("", response_model=Dict[str, Any])
async def chat(body: ChatRequest) -> Dict[str, Any]:
    """非流式对话。LLM 未启用时返回 200 + 友好提示。"""
    if not is_llm_configured():
        return {
            "ok": False,
            "llm_used": False,
            "reply": (
                "LLM 未启用。请到「系统设置 → LLM」页开启开关，"
                "并填入 API key 后再试。"
            ),
            "hint": "open_settings",
        }
    msgs = _build_messages(body)
    if not msgs:
        return {"ok": False, "error": "messages 或 prompt 至少传一个"}
    try:
        client = make_llm_client()
        resp = await client.achat(
            msgs,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
        )
        return {
            "ok": True,
            "llm_used": True,
            "reply": resp.content,
            "model": resp.model,
            "usage": resp.usage,
            "elapsed_ms": resp.elapsed_ms,
        }
    except Exception as exc:
        logger.exception("Chat 失败: %s", exc)
        return {"ok": False, "error": str(exc)}


@router.post("/stream")
async def chat_stream(body: ChatRequest) -> StreamingResponse:
    """SSE 流式对话。"""
    if not is_llm_configured():
        async def _fallback() -> AsyncIterator[bytes]:
            payload = {
                "type": "error",
                "message": "LLM 未启用，请到「系统设置 → LLM」页配置。",
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")
            yield b"data: [DONE]\n\n"

        return StreamingResponse(
            _fallback(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    msgs = _build_messages(body)
    if not msgs:
        async def _empty() -> AsyncIterator[bytes]:
            payload = {"type": "error", "message": "messages 或 prompt 至少传一个"}
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")
            yield b"data: [DONE]\n\n"

        return StreamingResponse(
            _empty(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    async def _gen() -> AsyncIterator[bytes]:
        try:
            client = make_llm_client()
            async for chunk in client.astream(
                msgs,
                temperature=body.temperature,
                max_tokens=body.max_tokens,
            ):
                payload = {"type": "delta", "text": chunk}
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")
                await asyncio.sleep(0)  # 让出事件循环
            yield b"data: [DONE]\n\n"
        except Exception as exc:
            logger.exception("Chat 流式失败: %s", exc)
            payload = {"type": "error", "message": str(exc)}
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")
            yield b"data: [DONE]\n\n"

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
