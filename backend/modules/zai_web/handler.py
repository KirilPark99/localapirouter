import os
import json
import time
import uuid
import hmac
import hashlib
import base64
import re
import logging
from datetime import datetime, timezone
from urllib.parse import urlencode
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

import httpx
from app.modules.base import BaseModuleAdapter, ModuleExecutionContext
from app.schemas.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatMessage,
    UsageInfo,
)
from app.adapters.base import DiscoveredModelData

logger = logging.getLogger("app.modules.zai_web")

ZAI_BASE_URL = "https://chat.z.ai"
ZAI_NEW_CHAT_URL = f"{ZAI_BASE_URL}/api/v1/chats/new"
ZAI_CHAT_URL = f"{ZAI_BASE_URL}/api/v2/chat/completions"
ZAI_DEFAULT_MODEL = "glm-5.3"
ZAI_DEFAULT_FE_VERSION = "prod-fe-1.1.98"
ZAI_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
)

SIGNATURE_KEY = b"key-@@@@)))()((9))-xxxx&&&%%%%%"
CLIENT_PROTOCOL_VERSION = "0.0.1"

_cached_fe_version = {"version": ZAI_DEFAULT_FE_VERSION, "expires_at": 0.0}


async def get_zai_fe_version(client: httpx.AsyncClient) -> str:
    now = time.time()
    if _cached_fe_version["expires_at"] > now:
        return _cached_fe_version["version"]
    try:
        resp = await client.get(
            f"{ZAI_BASE_URL}/",
            headers={"User-Agent": ZAI_USER_AGENT, "Accept": "text/html"},
            timeout=5.0,
        )
        if resp.status_code == 200:
            m = re.search(r'/frontend/(prod-fe-[^/]+)/', resp.text)
            if m:
                _cached_fe_version["version"] = m.group(1)
                _cached_fe_version["expires_at"] = now + 900.0  # Cache for 15 min
    except Exception as e:
        logger.debug("Failed to detect live Z.ai frontend version: %s", e)
    return _cached_fe_version["version"]


def extract_zai_user_id(token: str) -> str:
    parts = token.split(".")
    if len(parts) < 2:
        return ""
    payload_b64 = parts[1]
    # Add padding if needed
    rem = len(payload_b64) % 4
    if rem > 0:
        payload_b64 += "=" * (4 - rem)
    try:
        decoded = json.loads(base64.urlsafe_b64decode(payload_b64.encode("utf-8")).decode("utf-8"))
        return str(decoded.get("id") or "")
    except Exception:
        return ""


def build_zai_signature(prompt: str, request_id: str, timestamp: int, user_id: str) -> str:
    timestamp_str = str(timestamp)
    entries = sorted([
        ("requestId", request_id),
        ("timestamp", timestamp_str),
        ("user_id", user_id),
    ], key=lambda x: x[0])

    sorted_payload = ",".join(f"{k},{v}" for k, v in entries)
    # Strip user prompt before signing to match chat.z.ai client logic
    clean_prompt = prompt.strip()
    encoded_prompt = base64.b64encode(clean_prompt.encode("utf-8")).decode("utf-8")
    bucket = str(timestamp // (5 * 60 * 1000)).encode("utf-8")
    derived_key = hmac.new(SIGNATURE_KEY, bucket, hashlib.sha256).hexdigest().encode("utf-8")
    to_sign = f"{sorted_payload}|{encoded_prompt}|{timestamp_str}".encode("utf-8")
    return hmac.new(derived_key, to_sign, hashlib.sha256).hexdigest()


def build_completion_url(request_id: str, timestamp: int, token: str, user_id: str) -> str:
    now_utc = datetime.now(timezone.utc)
    params = {
        "timestamp": str(timestamp),
        "requestId": request_id,
        "user_id": user_id,
        "version": CLIENT_PROTOCOL_VERSION,
        "platform": "web",
        "token": token,
        "user_agent": ZAI_USER_AGENT,
        "language": "en-US",
        "languages": "en-US,en",
        "timezone": "UTC",
        "cookie_enabled": "true",
        "screen_width": "1280",
        "screen_height": "800",
        "screen_resolution": "1280x800",
        "viewport_height": "800",
        "viewport_width": "1280",
        "viewport_size": "1280x800",
        "color_depth": "24",
        "pixel_ratio": "1",
        "current_url": f"{ZAI_BASE_URL}/",
        "pathname": "/",
        "search": "",
        "hash": "",
        "host": "chat.z.ai",
        "hostname": "chat.z.ai",
        "protocol": "https:",
        "referrer": "",
        "title": "Z.ai - Advanced AI Chatbot & Agent powered by GLM-5.3-Flash",
        "timezone_offset": "0",
        "local_time": now_utc.isoformat(),
        "utc_time": now_utc.strftime("%a, %d %b %Y %H:%M:%S GMT"),
        "is_mobile": "false",
        "is_touch": "false",
        "max_touch_points": "0",
        "browser_name": "Chrome",
        "os_name": "Mac OS",
        "signature_timestamp": str(timestamp),
    }
    return f"{ZAI_CHAT_URL}?{urlencode(params)}"


def extract_zai_frame_error(data: Any) -> Optional[str]:
    """
    Extract human-readable error from Z.ai SSE payload if present.
    Z.ai returns HTTP 200 with an error object inside data / data.data for
    failures such as FRONTEND_CAPTCHA_REQUIRED, invalid token, or expired session.
    """
    if not isinstance(data, dict):
        return None
    raw_err = data.get("error")
    if not raw_err and isinstance(data.get("data"), dict):
        raw_err = data["data"].get("error")
        if not raw_err and isinstance(data["data"].get("data"), dict):
            raw_err = data["data"]["data"].get("error")

    if not raw_err:
        return None

    if isinstance(raw_err, str):
        return raw_err
    if isinstance(raw_err, dict):
        code = str(raw_err.get("code") or raw_err.get("error_code") or "")
        detail = str(raw_err.get("detail") or raw_err.get("message") or raw_err.get("content") or "")
        if code == "FRONTEND_CAPTCHA_REQUIRED":
            return (
                "FRONTEND_CAPTCHA_REQUIRED: Z.ai requires CAPTCHA verification proof. "
                "Please obtain 'captcha_verify_param' from chat.z.ai DevTools Network inspection "
                "(/api/v2/chat/completions payload) and add it to your Provider Credentials, or refresh your session token."
            )
        if code and detail:
            return f"{code}: {detail}"
        return code or detail or str(raw_err)
    return str(raw_err)


def parse_zai_sse_line(line: str) -> Optional[Tuple[str, str, bool]]:
    """
    Parses a single Z.ai SSE payload.
    Returns: (content_type: 'text' | 'thinking', delta: str, done: bool)
    Raises: RuntimeError if the frame carries an upstream error.
    """
    if not line.startswith("data:"):
        return None
    raw = line[5:].strip()
    if not raw or raw == "[DONE]":
        return ("text", "", True)

    try:
        data = json.loads(raw)
    except Exception:
        return None

    # Error check across root and nested data envelopes
    err_msg = extract_zai_frame_error(data)
    if err_msg:
        raise RuntimeError(f"Z.ai upstream error: {err_msg}")

    # Standard choices format
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        delta = choices[0].get("delta", {})
        finish = choices[0].get("finish_reason")
        content = delta.get("content") or ""
        reasoning = delta.get("reasoning_content") or ""
        if reasoning:
            return ("thinking", reasoning, finish is not None)
        return ("text", content, finish is not None)

    # Internal envelope format
    inner = data.get("data") if isinstance(data.get("data"), dict) else data
    phase = str(inner.get("phase") or "")
    delta_content = str(inner.get("delta_content") or inner.get("edit_content") or inner.get("content") or "")
    done = inner.get("done") is True or phase in ("done", "finish")

    if delta_content:
        return ("thinking" if phase == "thinking" else "text", delta_content, done)

    return ("text", "", done)


class ZaiWebAdapter(BaseModuleAdapter):
    """
    Adapter for Z.ai consumer chat (chat.z.ai).
    """

    def _get_token(self, ctx: ModuleExecutionContext) -> str:
        token = (
            ctx.credentials.get("token")
            or ctx.credentials.get("accessToken")
            or ctx.credentials.get("api_key")
            or ""
        )
        return str(token).strip()

    def _build_headers(self, token: str, signature: Optional[str] = None, fe_version: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Accept-Language": "en-US",
            "User-Agent": ZAI_USER_AGENT,
            "Origin": ZAI_BASE_URL,
            "Referer": f"{ZAI_BASE_URL}/",
            "Authorization": f"Bearer {token}",
            "X-FE-Version": fe_version or ZAI_DEFAULT_FE_VERSION,
        }
        if signature:
            headers["X-Signature"] = signature
        return headers

    async def validate_credentials(
        self,
        ctx: ModuleExecutionContext,
    ) -> Tuple[bool, str, int]:
        token = self._get_token(ctx)
        if not token:
            return False, "Missing Z.ai token", 0

        user_id = extract_zai_user_id(token)
        if not user_id:
            return False, "Invalid JWT token: could not extract user ID", 0

        models = await self.list_models(ctx)
        return True, f"Z.ai token valid for user {user_id}", len(models)

    async def list_models(
        self,
        ctx: ModuleExecutionContext,
    ) -> List[DiscoveredModelData]:
        token = self._get_token(ctx)
        if token:
            try:
                async with self.create_http_client(ctx) as client:
                    resp = await client.get(
                        f"{ZAI_BASE_URL}/api/models",
                        headers={"Authorization": f"Bearer {token}", "User-Agent": ZAI_USER_AGENT},
                        timeout=5.0,
                    )
                    if resp.status_code == 200:
                        payload = resp.json()
                        discovered: List[DiscoveredModelData] = []
                        for m in payload.get("data", []):
                            meta = m.get("info", {}).get("meta", {})
                            # Filter out legacy/hidden models marked hidden: True
                            if meta.get("hidden") is True:
                                continue
                            m_id = str(m.get("id") or "")
                            if not m_id:
                                continue
                            m_name = str(m.get("name") or m_id)
                            # Expose user-friendly slug for GLM-5.3-Flash
                            if m_id == "x-preview-l":
                                m_id = "glm-5.3-flash"
                            caps = meta.get("capabilities", {})
                            discovered.append(
                                DiscoveredModelData(
                                    provider_model_id=m_id,
                                    display_name=f"{m_name} (Z.ai)",
                                    capabilities={
                                        "chat": True,
                                        "streaming": True,
                                        "vision": bool(caps.get("vision", False)),
                                        "tools": bool(caps.get("mcp", False) or caps.get("returnFc", False)),
                                        "reasoning": bool(caps.get("think", False) or caps.get("reasoning_effort", False)),
                                    },
                                    context_length=1048576,
                                    max_output_tokens=16384,
                                )
                            )
                        if discovered:
                            return discovered
            except Exception as e:
                logger.debug("Failed to query live models from chat.z.ai: %s", e)

        # Fallback to the 3 active visible models on chat.z.ai
        return [
            DiscoveredModelData(
                provider_model_id="glm-5.3",
                display_name="GLM-5.3 (Z.ai)",
                capabilities={"chat": True, "streaming": True, "vision": False, "tools": True, "reasoning": True},
                context_length=1048576,
                max_output_tokens=16384,
            ),
            DiscoveredModelData(
                provider_model_id="glm-5.3-flash",
                display_name="GLM-5.3-Flash (Z.ai)",
                capabilities={"chat": True, "streaming": True, "vision": True, "tools": True, "reasoning": True},
                context_length=1048576,
                max_output_tokens=16384,
            ),
            DiscoveredModelData(
                provider_model_id="glm-5.2",
                display_name="GLM-5.2 (Z.ai)",
                capabilities={"chat": True, "streaming": True, "vision": False, "tools": True, "reasoning": True},
                context_length=1048576,
                max_output_tokens=16384,
            ),
        ]

    async def _create_chat(
        self,
        client: httpx.AsyncClient,
        token: str,
        prompt: str,
        model: str,
        fe_version: str,
    ) -> Tuple[str, str]:
        user_message_id = str(uuid.uuid4())
        effort_supported = model.lower() in ("glm-5.3", "glm-5.2", "x-preview-l", "glm-5.3-flash")
        payload = {
            "chat": {
                "id": "",
                "title": "New Chat",
                "models": [model],
                "params": {},
                "history": {
                    "messages": {
                        user_message_id: {
                            "id": user_message_id,
                            "parentId": None,
                            "childrenIds": [],
                            "role": "user",
                            "content": prompt,
                            "timestamp": int(time.time()),
                            "models": [model],
                        }
                    },
                    "currentId": user_message_id,
                },
                "tags": [],
                "flags": [],
                "features": [{"server": "tool_selector_h", "status": "hidden", "type": "tool_selector"}],
                "mcp_servers": [],
                "enable_thinking": True,
                "reasoning_effort": "high" if effort_supported else None,
                "auto_web_search": False,
                "message_version": 1,
                "extra": {
                    "vlm_tools_enable": False,
                    "vlm_web_search_enable": False,
                    "vlm_website_mode": False,
                },
                "timestamp": int(time.time() * 1000),
                "type": "default",
            }
        }
        headers = self._build_headers(token, fe_version=fe_version)
        headers["Accept"] = "application/json"
        resp = await client.post(ZAI_NEW_CHAT_URL, headers=headers, json=payload, timeout=15.0)
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to create Z.ai chat session: HTTP {resp.status_code}")
        data = resp.json()
        chat_id = data.get("id") or ""
        return chat_id, user_message_id

    async def chat_completions(
        self,
        request: ChatCompletionRequest,
        ctx: ModuleExecutionContext,
    ) -> ChatCompletionResponse:
        full_content = ""
        full_reasoning = ""
        model_name = request.model or ctx.model_id or ZAI_DEFAULT_MODEL

        async for chunk_str in self.stream_chat(request, ctx):
            if not chunk_str.startswith("data: "):
                continue
            data_part = chunk_str[6:].strip()
            if data_part == "[DONE]":
                break
            try:
                chunk = json.loads(data_part)
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content", "")
                reasoning = delta.get("reasoning_content", "")
                if content:
                    full_content += content
                if reasoning:
                    full_reasoning += reasoning
            except Exception:
                pass

        if not full_content and not full_reasoning:
            raise RuntimeError("Z.ai chat completed with empty response")

        msg = ChatMessage(role="assistant", content=full_content)
        if full_reasoning:
            msg.reasoning_content = full_reasoning

        return ChatCompletionResponse(
            id=f"chatcmpl-zai-{uuid.uuid4().hex[:12]}",
            object="chat.completion",
            created=int(time.time()),
            model=model_name,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=msg,
                    finish_reason="stop",
                )
            ],
            usage=UsageInfo(
                prompt_tokens=len(str(request.messages)) // 4,
                completion_tokens=(len(full_content) + len(full_reasoning)) // 4,
                total_tokens=(len(str(request.messages)) + len(full_content) + len(full_reasoning)) // 4,
            ),
        )

    async def stream_chat(
        self,
        request: ChatCompletionRequest,
        ctx: ModuleExecutionContext,
    ) -> AsyncGenerator[str, None]:
        token = self._get_token(ctx)
        if not token:
            raise RuntimeError("Missing Z.ai token")
        user_id = extract_zai_user_id(token)
        if not user_id:
            raise RuntimeError("Invalid Z.ai JWT: user_id missing")

        model_name = request.model or ctx.model_id or ZAI_DEFAULT_MODEL
        clean_model = model_name
        if clean_model.startswith("zai_web/"):
            clean_model = clean_model[8:]
        elif clean_model.startswith("zai-web/"):
            clean_model = clean_model[8:]

        # Map user alias to upstream model ID
        if clean_model.lower() in ("glm-5.3-flash", "glm-5.3_flash"):
            upstream_model = "x-preview-l"
        else:
            upstream_model = clean_model

        # Get latest user prompt
        user_prompt = ""
        for m in reversed(request.messages):
            if m.role == "user":
                user_prompt = m.content if isinstance(m.content, str) else json.dumps(m.content)
                break

        # Check captcha_verify_param in credentials or extra_body
        captcha_verify = (
            ctx.credentials.get("captcha_verify_param")
            or getattr(request, "captcha_verify_param", "")
            or ""
        )
        if not captcha_verify and hasattr(request, "model_extra") and request.model_extra:
            captcha_verify = request.model_extra.get("captcha_verify_param", "")

        effort_supported = upstream_model.lower() in ("glm-5.3", "glm-5.2", "x-preview-l")

        async with self.create_http_client(ctx) as client:
            fe_version = await get_zai_fe_version(client)
            chat_id, user_msg_id = await self._create_chat(
                client, token, user_prompt, upstream_model, fe_version
            )

            timestamp = int(time.time() * 1000)
            req_id = str(uuid.uuid4())
            signature = build_zai_signature(user_prompt, req_id, timestamp, user_id)
            comp_url = build_completion_url(req_id, timestamp, token, user_id)

            headers = self._build_headers(token, signature, fe_version)
            messages_payload = [
                {"role": m.role, "content": m.content if isinstance(m.content, str) else json.dumps(m.content)}
                for m in request.messages
            ]

            features_payload = {
                "image_generation": False,
                "web_search": False,
                "auto_web_search": False,
                "preview_mode": True,
                "flags": [],
                "vlm_tools_enable": False,
                "vlm_web_search_enable": False,
                "vlm_website_mode": False,
                "enable_thinking": True,
            }
            if effort_supported:
                features_payload["reasoning_effort"] = "high"

            body_payload = {
                "stream": True,
                "model": upstream_model,
                "messages": messages_payload,
                "signature_prompt": user_prompt.strip(),
                "params": {},
                "extra": {
                    "vlm_tools_enable": False,
                    "vlm_web_search_enable": False,
                    "vlm_website_mode": False,
                },
                "features": features_payload,
                "variables": {},
                "chat_id": chat_id,
                "id": str(uuid.uuid4()),
                "current_user_message_id": user_msg_id,
                "current_user_message_parent_id": None,
                "background_tasks": {"title_generation": True, "tags_generation": True},
                "captcha_verify_param": captcha_verify or "",
            }

            resp_id = f"chatcmpl-zai-{uuid.uuid4().hex[:12]}"
            created_ts = int(time.time())
            role_emitted = False

            async with client.stream("POST", comp_url, headers=headers, json=body_payload, timeout=ctx.timeout or 120.0) as resp:
                if resp.status_code != 200:
                    err_text = await resp.aread()
                    raise RuntimeError(f"Z.ai chat failed (HTTP {resp.status_code}): {err_text.decode('utf-8', errors='ignore')[:300]}")

                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        parsed = parse_zai_sse_line(line)
                    except Exception as e:
                        if role_emitted:
                            chunk = {
                                "id": resp_id,
                                "object": "chat.completion.chunk",
                                "created": created_ts,
                                "model": model_name,
                                "choices": [{"index": 0, "delta": {"content": f"\n\n[Z.ai upstream error: {e}]"}, "finish_reason": "stop"}],
                            }
                            yield f"data: {json.dumps(chunk)}\n\n"
                            yield "data: [DONE]\n\n"
                            return
                        raise

                    if not parsed:
                        continue
                    kind, text, done = parsed

                    if done:
                        yield "data: [DONE]\n\n"
                        return

                    if text:
                        if not role_emitted:
                            role_emitted = True
                            role_chunk = {
                                "id": resp_id,
                                "object": "chat.completion.chunk",
                                "created": created_ts,
                                "model": model_name,
                                "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}],
                            }
                            yield f"data: {json.dumps(role_chunk)}\n\n"

                        delta_dict = {"reasoning_content": text} if kind == "thinking" else {"content": text}
                        chunk = {
                            "id": resp_id,
                            "object": "chat.completion.chunk",
                            "created": created_ts,
                            "model": model_name,
                            "choices": [{"index": 0, "delta": delta_dict, "finish_reason": None}],
                        }
                        yield f"data: {json.dumps(chunk)}\n\n"

                yield "data: [DONE]\n\n"
