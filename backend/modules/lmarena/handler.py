import os
import json
import time
import uuid
import re
import logging
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

logger = logging.getLogger("app.modules.lmarena")

LMARENA_BASE_URL = "https://arena.ai"
LMARENA_STREAM_URL = f"{LMARENA_BASE_URL}/nextjs-api/stream/create-evaluation"
LMARENA_AUTH_COOKIE = "arena-auth-prod-v1"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
)

MODELS_FILE = os.path.join(os.path.dirname(__file__), "models_dump.json")
ARENA_MODEL_MAP: Dict[str, Dict[str, Any]] = {}

if os.path.exists(MODELS_FILE):
    try:
        with open(MODELS_FILE, "r", encoding="utf-8") as f:
            ARENA_MODEL_MAP = json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load models_dump.json: {e}")

# Fallback models if dump is missing
if not ARENA_MODEL_MAP:
    ARENA_MODEL_MAP = {
        "claude-sonnet-5": {"arenaId": "019f19f2-41f1-7c6d-9891-48d02fd9952c", "name": "Claude Sonnet 5 (Arena)", "vision": True, "reasoning": True, "rank": 1},
        "gpt-5.5-instant": {"arenaId": "019e71ea-1e1d-740f-9c2d-dab5869ff108", "name": "GPT-5.5 Instant (Arena)", "vision": True, "reasoning": False, "rank": 40},
        "gpt-5.4-mini-high": {"arenaId": "019cfcdd-5426-777e-8314-04619cb92cc4", "name": "GPT-5.4 Mini (Arena)", "vision": True, "reasoning": True, "rank": 83},
        "gemini-3.6-flash": {"arenaId": "019f90b1-c0ac-71ce-b295-487f261bf0f4", "name": "Gemini 3.6 Flash (Arena)", "vision": True, "reasoning": False, "rank": 22},
        "gemini-3.1-pro-preview": {"arenaId": "019c7820-5480-78b6-9fef-04c0d7004054", "name": "Gemini 3.1 Pro Preview (Arena)", "vision": True, "reasoning": False, "rank": 18},
        "deepseek-v4-flash-max": {"arenaId": "01a088f2-2e70-71e2-9d8a-bab3d370df44", "name": "DeepSeek V4 Flash Max (Arena)", "vision": False, "reasoning": True, "rank": 50},
        "deepseek-v4-pro-thinking": {"arenaId": "019dc1c1-c62d-7b70-85a1-e0565e29fce1", "name": "DeepSeek V4 Pro Thinking (Arena)", "vision": False, "reasoning": True, "rank": 55},
        "qwen3.7-plus": {"arenaId": "019e86fe-167d-77bd-94a8-df7aee4f4551", "name": "Qwen3.7 Plus (Arena)", "vision": True, "reasoning": False, "rank": 68},
        "glm-5": {"arenaId": "019c45d7-96f0-7d39-8143-9d57941b5523", "name": "GLM 5 (Arena)", "vision": False, "reasoning": False, "rank": 63},
        "minimax-m3": {"arenaId": "019e809d-f62d-7192-bb7f-1657e066b5f2", "name": "MiniMax M3 (Arena)", "vision": True, "reasoning": True, "rank": 95},
    }

_LIVE_MODELS_CACHE: Dict[str, Dict[str, Any]] = {}
_LAST_FETCH_TIME: float = 0.0


def parse_initial_models(html: str) -> List[Dict[str, Any]]:
    for escapedMarker in [r"\"initialModels\":[", "\"initialModels\":["]:
        idx = html.find(escapedMarker)
        if idx != -1:
            array_start = idx + len(escapedMarker) - 1
            for end_marker in [r"],\"initialModelAId\"", "],\"initialModelAId\"", r"],\"initial", "],\"initial"]:
                end_idx = html.find(end_marker, array_start)
                if end_idx != -1:
                    raw = html[array_start:end_idx + 1].replace(r"\"", "\"")
                    try:
                        return json.loads(raw)
                    except Exception:
                        pass
    return []


async def fetch_live_arena_models(cookie: str = "") -> Dict[str, Dict[str, Any]]:
    global _LIVE_MODELS_CACHE, _LAST_FETCH_TIME
    now = time.time()
    if _LIVE_MODELS_CACHE and (now - _LAST_FETCH_TIME) < 3600:
        return _LIVE_MODELS_CACHE

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    if cookie:
        headers["Cookie"] = cookie

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"{LMARENA_BASE_URL}/direct", headers=headers)
            if resp.status_code == 200:
                raw_models = parse_initial_models(resp.text)
                new_cache: Dict[str, Dict[str, Any]] = {}
                for m in raw_models:
                    if m.get("userSelectable") is not True:
                        continue
                    mid = m.get("id", "")
                    if not re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", mid, re.I):
                        continue
                    caps = m.get("capabilities", {})
                    inp = caps.get("inputCapabilities", {})
                    out = caps.get("outputCapabilities", {})
                    if not inp.get("text") or not out.get("text"):
                        continue
                    pname = (m.get("publicName") or m.get("name") or m.get("displayName") or "").strip()
                    if not pname or pname in new_cache:
                        continue
                    dname = (m.get("displayName") or m.get("name") or pname).strip()
                    org = (m.get("organization") or m.get("provider") or "").strip()
                    has_vision = bool(inp.get("image"))
                    has_reasoning = any(k in pname.lower() for k in ["thinking", "reasoning", "pro-thinking", "thought", "o1", "o3", "r1"])
                    rank = m.get("rank") if m.get("rank") is not None else 999
                    new_cache[pname] = {
                        "arenaId": mid,
                        "name": f"{dname} (Arena)" if "(Arena)" not in dname else dname,
                        "organization": org,
                        "vision": has_vision,
                        "reasoning": has_reasoning,
                        "rank": rank,
                    }
                if new_cache:
                    _LIVE_MODELS_CACHE = new_cache
                    _LAST_FETCH_TIME = now
                    ARENA_MODEL_MAP.update(new_cache)
                    return _LIVE_MODELS_CACHE
    except Exception as e:
        logger.warning(f"Failed to fetch live Arena models: {e}")

    return _LIVE_MODELS_CACHE or ARENA_MODEL_MAP


def generate_uuidv7() -> str:
    """
    Generates an RFC 9562-compliant UUIDv7 string.
    LMSYS Arena requires valid UUIDv7 timestamps and versioning for:
    - id (battle evaluation ID)
    - userMessageId
    - modelAMessageId
    """
    ts_ms = int(time.time() * 1000)
    rand_bytes = os.urandom(10)
    b_ts = ts_ms.to_bytes(6, byteorder="big")
    byte6 = 0x70 | (rand_bytes[0] & 0x0F)
    byte7 = rand_bytes[1]
    byte8 = 0x80 | (rand_bytes[2] & 0x3F)
    raw = b_ts + bytes([byte6, byte7, byte8]) + rand_bytes[3:10]
    return str(uuid.UUID(bytes=raw))


def reconstruct_arena_cookie(raw_cookie: str) -> str:
    """
    Reconstructs LMArena's single arena-auth-prod-v1 auth cookie from Supabase SSR chunks.
    """
    if not raw_cookie or not raw_cookie.strip():
        return raw_cookie

    pairs = []
    for part in raw_cookie.split(";"):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        pairs.append((k.strip(), v.strip()))

    for k, v in pairs:
        if k == LMARENA_AUTH_COOKIE and v:
            return raw_cookie

    chunk_prefix = f"{LMARENA_AUTH_COOKIE}."
    chunks: Dict[int, str] = {}
    for k, v in pairs:
        if k.startswith(chunk_prefix):
            idx_str = k[len(chunk_prefix):]
            if idx_str.isdigit():
                chunks[int(idx_str)] = v

    if not chunks:
        return raw_cookie

    joined_parts = []
    idx = 0
    while idx in chunks:
        joined_parts.append(chunks[idx])
        idx += 1

    joined = "".join(joined_parts)
    if not joined:
        return raw_cookie

    preserved = [f"{k}={v}" for k, v in pairs if k != LMARENA_AUTH_COOKIE and not k.startswith(chunk_prefix)]
    return f"{LMARENA_AUTH_COOKIE}={joined}; " + "; ".join(preserved) if preserved else f"{LMARENA_AUTH_COOKIE}={joined}"


def resolve_arena_model_id(model_name: str) -> str:
    clean = model_name
    if clean.startswith("lmarena/"):
        clean = clean[8:]
    elif clean.startswith("lma/"):
        clean = clean[4:]
    elif clean.startswith("arena/"):
        clean = clean[6:]

    # Direct UUID match
    if re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", clean, re.I):
        return clean

    pool = {**ARENA_MODEL_MAP, **_LIVE_MODELS_CACHE}
    if clean in pool:
        return pool[clean]["arenaId"]

    # Case-insensitive lookup
    clean_lower = clean.lower()
    for k, v in pool.items():
        if k.lower() == clean_lower or str(v.get("name", "")).lower() == clean_lower:
            return v["arenaId"]

    # Fallback to default
    if "claude-sonnet-5" in pool:
        return pool["claude-sonnet-5"]["arenaId"]
    return "019f19f2-41f1-7c6d-9891-48d02fd9952c"


def format_arena_prompt(messages: List[ChatMessage]) -> str:
    rendered = []
    for m in messages:
        text = m.content if isinstance(m.content, str) else json.dumps(m.content)
        if not text:
            continue
        role = (m.role or "user").capitalize()
        rendered.append(f"{role}: {text}")

    if len(rendered) == 1 and messages[0].role == "user":
        content = messages[0].content
        return content if isinstance(content, str) else json.dumps(content)

    return "\n\n".join(rendered)


def parse_arena_sse_line(line: str) -> Optional[Tuple[str, str]]:
    """
    Parses an AI-SDK / Arena SSE payload line.
    Returns: (type: 'text' | 'thinking' | 'done' | 'error' | 'heartbeat', content: str)
    """
    trimmed = line.strip()
    if trimmed.startswith("data: "):
        trimmed = trimmed[6:].strip()
    if not trimmed:
        return None

    # Handle legacy ae: / be: errors
    legacy = re.match(r"^[ab]e:(.*)$", trimmed)
    if legacy:
        try:
            val = json.loads(legacy.group(1))
            err_msg = val if isinstance(val, str) else (val.get("error") or val.get("message") or "Arena error")
        except Exception:
            err_msg = legacy.group(1)
        return ("error", str(err_msg))

    # Strip participant prefix if present (e.g. 'a0:' -> '0:')
    m = re.match(r"^[ab]([023dfg]):(.*)$", trimmed)
    if m:
        code, raw_val = m.group(1), m.group(2)
    elif ":" in trimmed:
        code, raw_val = trimmed.split(":", 1)
    else:
        return None

    try:
        val = json.loads(raw_val)
    except Exception:
        val = raw_val

    if code == "0":
        text = val if isinstance(val, str) else (val.get("text") or val.get("textDelta") or "")
        return ("text", text) if text else None
    elif code == "g":
        text = val if isinstance(val, str) else (val.get("thinking") or val.get("text") or val.get("textDelta") or "")
        return ("thinking", text) if text else None
    elif code == "2":
        return ("heartbeat", "")
    elif code == "d":
        if isinstance(val, dict) and val.get("finishReason") == "error":
            return ("error", "Arena stream finished with an error")
        return ("done", "")
    elif code == "3":
        err_msg = val if isinstance(val, str) else (val.get("error") or val.get("message") or "Unknown error")
        return ("error", str(err_msg))

    return None


class LMArenaAdapter(BaseModuleAdapter):
    """
    Adapter for LMSYS Chatbot Arena evaluation direct battle (arena.ai).
    """

    def _get_cookie(self, ctx: ModuleExecutionContext) -> str:
        cookie = (
            ctx.credentials.get("cookie")
            or ctx.credentials.get("apiKey")
            or ctx.credentials.get("api_key")
            or ""
        )
        return reconstruct_arena_cookie(str(cookie).strip())

    async def validate_credentials(
        self,
        ctx: ModuleExecutionContext,
    ) -> Tuple[bool, str, int]:
        cookie = self._get_cookie(ctx)
        if not cookie:
            return False, "Missing Arena session cookie (arena-auth-prod-v1)", 0

        # Verify cookie structure
        if "arena-auth-prod-v1=" not in cookie:
            return False, "Cookie must contain arena-auth-prod-v1", 0

        models = await self.list_models(ctx)
        return True, "Arena session cookie formatted properly", len(models)

    async def list_models(
        self,
        ctx: ModuleExecutionContext,
    ) -> List[DiscoveredModelData]:
        cookie = self._get_cookie(ctx)
        live_pool = await fetch_live_arena_models(cookie)
        pool = live_pool or ARENA_MODEL_MAP

        models_list = []
        for m_id, info in pool.items():
            ctx_len = 128000
            max_tokens = 8192
            if "gemini" in m_id.lower():
                ctx_len = 1000000
            elif "claude" in m_id.lower():
                ctx_len = 200000
            elif "gpt-5" in m_id.lower() or "o3" in m_id.lower() or "o4" in m_id.lower():
                ctx_len = 128000
                max_tokens = 16384
            elif any(w in m_id.lower() for w in ["qwen", "glm", "minimax", "kimi"]):
                ctx_len = 131072

            models_list.append(
                DiscoveredModelData(
                    provider_model_id=m_id,
                    display_name=info["name"],
                    capabilities={
                        "chat": True,
                        "streaming": True,
                        "vision": info.get("vision", False),
                        "tools": False,
                        "reasoning": info.get("reasoning", False),
                    },
                    context_length=ctx_len,
                    max_output_tokens=max_tokens,
                )
            )
        return models_list

    async def chat_completions(
        self,
        request: ChatCompletionRequest,
        ctx: ModuleExecutionContext,
    ) -> ChatCompletionResponse:
        full_content = ""
        full_reasoning = ""
        model_name = request.model or ctx.model_id or "claude-sonnet-5"

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

        msg = ChatMessage(role="assistant", content=full_content)
        if full_reasoning:
            msg.reasoning_content = full_reasoning

        return ChatCompletionResponse(
            id=f"chatcmpl-lma-{uuid.uuid4().hex[:12]}",
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
        cookie = self._get_cookie(ctx)
        if not cookie:
            raise RuntimeError("Missing Arena session cookie (arena-auth-prod-v1)")

        model_name = request.model or ctx.model_id or "claude-sonnet-5"
        arena_model_id = resolve_arena_model_id(model_name)
        prompt = format_arena_prompt(request.messages)

        req_body = {
            "id": generate_uuidv7(),
            "mode": "direct-battle",
            "modelAId": arena_model_id,
            "userMessageId": generate_uuidv7(),
            "modelAMessageId": generate_uuidv7(),
            "userMessage": {
                "content": prompt,
                "experimental_attachments": [],
                "metadata": {},
            },
            "modality": "chat",
        }
        recaptcha_token = (
            ctx.credentials.get("recaptcha_token")
            or ctx.credentials.get("recaptchaToken")
            or ctx.credentials.get("recaptchaV3Token")
        )
        if recaptcha_token:
            req_body["recaptchaV3Token"] = str(recaptcha_token).strip()

        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream, application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Origin": LMARENA_BASE_URL,
            "Referer": f"{LMARENA_BASE_URL}/direct",
            "Sec-Ch-Ua": '"Chromium";v="150", "Google Chrome";v="150", "Not-A.Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": USER_AGENT,
            "Cookie": cookie,
        }

        req_id = f"chatcmpl-lma-{uuid.uuid4().hex[:12]}"
        created_ts = int(time.time())
        role_emitted = False

        async with self.create_http_client(ctx) as client:
            async with client.stream("POST", LMARENA_STREAM_URL, headers=headers, json=req_body, timeout=ctx.timeout or 120.0) as resp:
                if resp.status_code != 200:
                    err_text = await resp.aread()
                    err_decoded = err_text.decode('utf-8', errors='ignore')
                    try:
                        err_json = json.loads(err_decoded)
                        if isinstance(err_json, dict) and "error" in err_json:
                            err_decoded = str(err_json["error"])
                    except Exception:
                        pass
                    raise RuntimeError(f"Arena error (HTTP {resp.status_code}): {err_decoded[:300]}")

                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    parsed = parse_arena_sse_line(line)
                    if not parsed:
                        continue
                    kind, val = parsed
                    if kind == "heartbeat":
                        continue
                    if kind == "done":
                        yield "data: [DONE]\n\n"
                        return
                    if kind == "error":
                        raise RuntimeError(f"Arena upstream error: {val}")

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

                    delta_dict = {"reasoning_content": val} if kind == "thinking" else {"content": val}
                    chunk = {
                        "id": req_id,
                        "object": "chat.completion.chunk",
                        "created": created_ts,
                        "model": model_name,
                        "choices": [{"index": 0, "delta": delta_dict, "finish_reason": None}],
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"

                yield "data: [DONE]\n\n"
