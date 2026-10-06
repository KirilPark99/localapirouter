import os
import json
import time
import uuid
import struct
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

import httpx
from app.core.errors import normalize_upstream_error, RouterException, ErrorCategory
from app.modules.base import BaseModuleAdapter, ModuleExecutionContext, collect_chat_completion
from app.schemas.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatMessage,
    UsageInfo,
)
from app.adapters.base import DiscoveredModelData

logger = logging.getLogger("app.modules.kimi_web")

BASE_URL = "https://www.kimi.ai"
CHAT_URL = f"{BASE_URL}/apiv2/kimi.gateway.chat.v1.ChatService/Chat"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
)
MAX_FRAME_LEN = 8 * 1024 * 1024


def frame_connect_message(json_obj: Dict[str, Any]) -> bytes:
    payload = json.dumps(json_obj).encode("utf-8")
    length = len(payload)
    return struct.pack(">BI", 0, length) + payload


def decode_connect_frame(buf: bytes, offset: int = 0) -> Tuple[int, Optional[int], Optional[Dict[str, Any]]]:
    if len(buf) < offset + 5:
        return 0, None, None
    flags, length = struct.unpack_from(">BI", buf, offset)
    if length > MAX_FRAME_LEN:
        return -1, None, None
    if len(buf) < offset + 5 + length:
        return 0, None, None
    payload = buf[offset + 5 : offset + 5 + length]
    msg = None
    if length > 0:
        try:
            msg = json.loads(payload.decode("utf-8"))
        except Exception:
            pass
    return 5 + length, flags, msg


def extract_delta(msg: Optional[Dict[str, Any]]) -> Optional[Tuple[str, str]]:
    """
    Extracts delta text and kind ('text' or 'think') from a Kimi Connect message.
    """
    if not msg:
        return None
    op = str(msg.get("op") or "")
    mask = str(msg.get("mask") or "")
    block = msg.get("block") or {}

    if op == "append":
        if mask == "block.text.content":
            text = str((block.get("text") or {}).get("content") or "")
            return ("text", text) if text else None
        if mask == "block.think.content":
            text = str((block.get("think") or {}).get("content") or "")
            return ("think", text) if text else None
        return None

    if op == "set":
        if mask == "block.text":
            text = str((block.get("text") or {}).get("content") or "")
            return ("text", text) if text else None
        if mask == "block.think":
            text = str((block.get("think") or {}).get("content") or "")
            return ("think", text) if text else None

    return None


def fold_messages(messages: List[ChatMessage]) -> Tuple[str, str]:
    system_parts = []
    convo_parts = []

    for m in messages:
        text = m.content if isinstance(m.content, str) else json.dumps(m.content)
        if not text:
            continue
        role = (m.role or "").lower()
        if role in ("system", "developer"):
            system_parts.append(text)
        elif role == "user":
            convo_parts.append(f"User: {text}" if convo_parts else text)
        elif role == "assistant":
            convo_parts.append(f"Assistant: {text}")

    prompt = "\n\n".join(convo_parts).strip()
    system_prompt = "\n\n".join(system_parts).strip()
    return prompt, system_prompt


class KimiWebAdapter(BaseModuleAdapter):
    """
    Adapter for Kimi Web Chat (www.kimi.ai).
    Uses Connect-RPC 5-byte unary stream framing.
    """

    def _get_token(self, ctx: ModuleExecutionContext) -> str:
        token = (
            ctx.credentials.get("access_token")
            or ctx.credentials.get("accessToken")
            or ctx.credentials.get("api_key")
            or ctx.credentials.get("token")
            or ""
        )
        return str(token).strip()

    def _build_headers(self, token: str) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/connect+json",
            "Accept": "*/*",
            "User-Agent": USER_AGENT,
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/",
            "connect-protocol-version": "1",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def validate_credentials(
        self,
        ctx: ModuleExecutionContext,
    ) -> Tuple[bool, str, int]:
        token = self._get_token(ctx)
        if not token:
            return False, "Missing Kimi access_token", 0

        # Validate by testing chat service with a 1-token prompt
        try:
            req_body = {
                "chat_id": "",
                "scenario": "SCENARIO_K2D5",
                "tools": [],
                "message": {
                    "id": "",
                    "parent_id": "",
                    "children_message_ids": [],
                    "role": "user",
                    "blocks": [{"id": "", "message_id": "", "text": {"content": "hi"}}],
                    "scenario": "SCENARIO_K2D5",
                    "labels": [],
                    "references": [],
                    "is_goal": False,
                },
                "options": {
                    "thinking": False,
                    "enable_plugin": False,
                    "reasoning_effort": "REASONING_EFFORT_NONE",
                },
                "project_id": "",
            }
            framed = frame_connect_message(req_body)
            headers = self._build_headers(token)

            async with self.create_http_client(ctx) as client:
                async with client.stream("POST", CHAT_URL, headers=headers, content=framed, timeout=15.0) as resp:
                    if resp.status_code in (401, 403):
                        return False, f"Authentication failed: HTTP {resp.status_code}", 0
                    if resp.status_code == 200:
                        models = await self.list_models(ctx)
                        return True, "Kimi access_token is valid and active", len(models)
                    err_text = await resp.aread()
                    return False, f"Kimi returned HTTP {resp.status_code}: {err_text.decode('utf-8', errors='ignore')[:200]}", 0
        except Exception as e:
            return False, f"Connection error: {str(e)}", 0

    async def list_models(
        self,
        ctx: ModuleExecutionContext,
    ) -> List[DiscoveredModelData]:
        return [
            DiscoveredModelData(
                provider_model_id="kimi-k2.8",
                display_name="Kimi K2.8 (Web)",
                capabilities={"chat": True, "streaming": True, "vision": True, "tools": False, "reasoning": True},
                context_length=1048576,
                max_output_tokens=16384,
            ),
            DiscoveredModelData(
                provider_model_id="kimi-k2.8-thinking",
                display_name="Kimi K2.8 (Deep Thinking)",
                capabilities={"chat": True, "streaming": True, "vision": True, "tools": False, "reasoning": True},
                context_length=1048576,
                max_output_tokens=16384,
                reasoning_effort="low",
            ),
            DiscoveredModelData(
                provider_model_id="k2d8",
                display_name="Kimi K2.8 (Web Alias)",
                capabilities={"chat": True, "streaming": True, "vision": True, "tools": False, "reasoning": True},
                context_length=1048576,
                max_output_tokens=16384,
            ),
            DiscoveredModelData(
                provider_model_id="k2.8",
                display_name="Kimi K2.8 (Short)",
                capabilities={"chat": True, "streaming": True, "vision": True, "tools": False, "reasoning": True},
                context_length=1048576,
                max_output_tokens=16384,
            ),
            DiscoveredModelData(
                provider_model_id="kimi-k3",
                display_name="Kimi K3 (Web)",
                capabilities={"chat": True, "streaming": True, "vision": False, "tools": False, "reasoning": True},
                context_length=1048576,
                max_output_tokens=16384,
            ),
            DiscoveredModelData(
                provider_model_id="kimi-k3-thinking",
                display_name="Kimi K3 (Deep Thinking)",
                capabilities={"chat": True, "streaming": True, "vision": False, "tools": False, "reasoning": True},
                context_length=1048576,
                max_output_tokens=16384,
                reasoning_effort="low",
            ),
            DiscoveredModelData(
                provider_model_id="k3",
                display_name="Kimi K3 (Web Alias)",
                capabilities={"chat": True, "streaming": True, "vision": False, "tools": False, "reasoning": True},
                context_length=1048576,
                max_output_tokens=16384,
            ),
            DiscoveredModelData(
                provider_model_id="kimi-k2.6",
                display_name="Kimi K2.6 (Web)",
                capabilities={"chat": True, "streaming": True, "vision": False, "tools": False, "reasoning": True},
                context_length=1048576,
                max_output_tokens=16384,
            ),
            DiscoveredModelData(
                provider_model_id="k2d6",
                display_name="Kimi K2.6 (Web Alias)",
                capabilities={"chat": True, "streaming": True, "vision": False, "tools": False, "reasoning": True},
                context_length=1048576,
                max_output_tokens=16384,
            ),
            DiscoveredModelData(
                provider_model_id="k2.6",
                display_name="Kimi K2.6 (Short)",
                capabilities={"chat": True, "streaming": True, "vision": False, "tools": False, "reasoning": True},
                context_length=1048576,
                max_output_tokens=16384,
            ),
        ]

    async def chat_completions(
        self,
        request: ChatCompletionRequest,
        ctx: ModuleExecutionContext,
    ) -> ChatCompletionResponse:
        model = request.model or ctx.model_id or "kimi-k2.8"
        return await collect_chat_completion(self.stream_chat(request, ctx), model, require_complete=True)

    async def stream_chat(
        self,
        request: ChatCompletionRequest,
        ctx: ModuleExecutionContext,
    ) -> AsyncGenerator[str, None]:
        token = self._get_token(ctx)
        if not token:
            raise RuntimeError("Missing Kimi access_token")

        model_name = request.model or ctx.model_id or "kimi-k2.8"
        clean_model = model_name
        if clean_model.startswith("kimi_web/"):
            clean_model = clean_model[9:]
        elif clean_model.startswith("kimi-web/"):
            clean_model = clean_model[9:]

        reasoning_effort = "REASONING_EFFORT_NONE"
        req_effort = getattr(request, "reasoning_effort", None)
        if "-thinking" in clean_model:
            reasoning_effort = "REASONING_EFFORT_LOW"
        elif req_effort:
            norm_effort = f"REASONING_EFFORT_{str(req_effort).upper()}"
            if norm_effort in ("REASONING_EFFORT_LOW", "REASONING_EFFORT_HIGH", "REASONING_EFFORT_MAX", "REASONING_EFFORT_NONE"):
                reasoning_effort = norm_effort
            else:
                reasoning_effort = "REASONING_EFFORT_LOW"

        prompt, system_prompt = fold_messages(request.messages)
        if not prompt:
            raise ValueError("Kimi Web requires a non-empty user message")

        options = {
            "thinking": True,
            "enable_plugin": False,
            "reasoning_effort": reasoning_effort,
        }
        if system_prompt:
            options["system_prompt"] = system_prompt

        req_body = {
            "chat_id": "",
            "scenario": "SCENARIO_K2D5",
            "tools": [],
            "message": {
                "id": "",
                "parent_id": "",
                "children_message_ids": [],
                "role": "user",
                "blocks": [{"id": "", "message_id": "", "text": {"content": prompt}}],
                "scenario": "SCENARIO_K2D5",
                "labels": [],
                "references": [],
                "is_goal": False,
            },
            "options": options,
            "project_id": "",
        }
        framed = frame_connect_message(req_body)
        headers = self._build_headers(token)

        req_id = f"chatcmpl-kimi-{uuid.uuid4().hex[:12]}"
        created_ts = int(time.time())

        async with self.create_http_client(ctx) as client:
            async with client.stream("POST", CHAT_URL, headers=headers, content=framed, timeout=ctx.timeout or 120.0) as resp:
                if resp.status_code != 200:
                    err_text = await resp.aread()
                    raise normalize_upstream_error(status_code=resp.status_code, response_body=(await resp.aread()).decode("utf-8", errors="replace"))

                buffer = bytearray()
                role_emitted = False

                async for chunk_bytes in resp.aiter_bytes():
                    buffer.extend(chunk_bytes)

                    offset = 0
                    while offset < len(buffer):
                        consumed, flags, msg = decode_connect_frame(buffer, offset)
                        if consumed == -1:
                            raise RuntimeError("Kimi Connect frame exceeded max size")
                        if consumed == 0:
                            break
                        offset += consumed

                        if flags is not None and (flags & 0x02) != 0:
                            # End stream frame
                            if msg and msg.get("error"):
                                err = msg["error"]
                                code = err.get("code", "unknown")
                                m_text = err.get("message", "upstream error")
                                raise normalize_upstream_error(status_code=502, response_body=f"Kimi Connect EndStream error: {code}: {m_text}")
                            terminal = {"id": req_id, "object": "chat.completion.chunk", "created": created_ts,
                                        "model": model_name, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
                            if msg and msg.get("usage"):
                                terminal["usage"] = msg["usage"]
                            yield f"data: {json.dumps(terminal)}\n\n"
                            yield "data: [DONE]\n\n"
                            return

                        delta = extract_delta(msg)
                        if delta:
                            kind, text = delta
                            if not role_emitted:
                                role_emitted = True
                                role_chunk = {
                                    "id": req_id,
                                    "object": "chat.completion.chunk",
                                    "created": created_ts,
                                    "model": model_name,
                                    "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}],
                                }
                                yield f"data: {json.dumps(role_chunk)}\n\n"

                            delta_dict = {"reasoning_content": text} if kind == "think" else {"content": text}
                            chunk_data = {
                                "id": req_id,
                                "object": "chat.completion.chunk",
                                "created": created_ts,
                                "model": model_name,
                                "choices": [{"index": 0, "delta": delta_dict, "finish_reason": None}],
                            }
                            yield f"data: {json.dumps(chunk_data)}\n\n"

                    if offset > 0:
                        buffer = buffer[offset:]

                raise normalize_upstream_error(status_code=502, response_body="Kimi Connect stream ended without EndStream or with incomplete frame")
