"""
DeepSeek Web Chat Custom Module Handler
Reverse-engineered from chat.deepseek.com based on OmniRoute architecture.

Features:
- Bearer token authentication via userToken (from browser localStorage)
- Token caching & auto-renewal (/api/v0/users/current)
- Session lifecycle management (create / reuse / auto-cleanup)
- High-performance DeepSeekHashV1 Proof-of-Work (PoW) challenge solving via WASM/JS
- Full R1 reasoning/thinking delta stream support (reasoning_content)
- Real-time web search citation extraction and markdown appending
- Multi-turn rolling history window transcript
- OpenAI tool-call serialization and tag parsing
- Seamless proxy support (HTTP, HTTPS, SOCKS5)
"""

import asyncio
import base64
import json
import logging
import re
import secrets
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

import httpx

from app.adapters.base import DiscoveredModelData
from app.modules.base import BaseModuleAdapter, ModuleExecutionContext
from app.schemas.chat import (
    ChatCompletionChoice,
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionChunkDelta,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    FunctionCall,
    ToolCall,
    UsageInfo,
)

try:
    from .pow.pow_solver import solve_deepseek_pow
except (ImportError, ValueError):
    from pow.pow_solver import solve_deepseek_pow

logger = logging.getLogger("app.modules.deepseek_web")

DEEPSEEK_WEB_BASE = "https://chat.deepseek.com"
DEEPSEEK_API_BASE = f"{DEEPSEEK_WEB_BASE}/api"
COMPLETION_URL = f"{DEEPSEEK_API_BASE}/v0/chat/completion"

FAKE_HEADERS: Dict[str, str] = {
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": DEEPSEEK_WEB_BASE,
    "Referer": f"{DEEPSEEK_WEB_BASE}/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
    ),
    "X-Client-Bundle-Id": "com.deepseek.chat",
    "X-Client-Locale": "en-US",
    "X-Client-Platform": "web",
    "X-Client-Version": "2.0.0",
}


def generate_fake_cookie() -> str:
    """Generate realistic browser fingerprint cookies expected by DeepSeek."""
    ts = int(time.time() * 1000)
    hex18 = secrets.token_hex(9)
    uid1 = str(uuid.uuid4())
    uid2 = str(uuid.uuid4())
    return (
        f"intercom-HWWAFSESTIME={ts}; "
        f"HWWAFSESID={hex18}; "
        f"Hm_lvt_{uid1}={ts // 1000}; "
        f"_frid={uid2}"
    )


def extract_user_token(credentials: Dict[str, Any]) -> str:
    """Extract raw userToken string from direct field or JSON-wrapped string."""
    raw = (
        credentials.get("user_token")
        or credentials.get("api_key")
        or credentials.get("apiKey")
        or credentials.get("accessToken")
    )
    if not raw or not isinstance(raw, str):
        return ""
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and isinstance(parsed.get("value"), str):
            return parsed["value"].strip()
    except Exception:
        pass
    return raw.strip()


def clean_deepseek_token(text: str) -> str:
    cleaned = text.replace("FINISHED", "")
    cleaned = re.sub(r"^(SEARCH|WEB_SEARCH|SEARCHING)\s*", "", cleaned, flags=re.IGNORECASE)
    return cleaned


def process_deepseek_sse_data(
    data: Dict[str, Any],
    current_path: str,
    thinking_model: bool,
) -> Tuple[str, List[Tuple[str, str]], List[Dict[str, Any]]]:
    """
    Process one parsed SSE data payload from DeepSeek web API.
    Returns:
        (updated_path: str, chunks: List[Tuple[target_path ("thinking"|"content"), text]], new_search_results: List)
    """
    p = data.get("p")
    v = data.get("v")
    chunks: List[Tuple[str, str]] = []
    search_results: List[Dict[str, Any]] = []

    def apply_fragment_type(frag: Any):
        nonlocal current_path
        if not isinstance(frag, dict):
            return
        ftype = str(frag.get("type", "")).upper()
        if ftype == "THINK":
            current_path = "thinking"
        elif ftype in ("ANSWER", "RESPONSE", "TEXT"):
            current_path = "content"

    def handle_fragment(frag: Any, set_path: bool = True):
        if set_path:
            apply_fragment_type(frag)
        if not isinstance(frag, dict):
            return
        if not set_path:
            apply_fragment_type(frag)
        c = frag.get("content")
        if isinstance(c, str) and c:
            text = clean_deepseek_token(c)
            if text:
                target = current_path if current_path else ("thinking" if thinking_model else "content")
                chunks.append((target, text))

    # 1. Initial or updated response envelope
    if isinstance(v, dict) and "response" in v:
        resp_obj = v["response"]
        if resp_obj.get("thinking_enabled") is True:
            current_path = "thinking"
        elif resp_obj.get("thinking_enabled") is False:
            current_path = "content"
        fragments = resp_obj.get("fragments")
        if isinstance(fragments, list):
            for frag in fragments:
                handle_fragment(frag, set_path=False)

    # 2. Fragments arrival / update (e.g. {"p": "response/fragments", "v": [{"type": "RESPONSE", ...}]})
    if p == "response/fragments":
        frags = v if isinstance(v, list) else [v]
        for frag in frags:
            handle_fragment(frag, set_path=True)

    # 3. Path hints
    if isinstance(p, str):
        if p == "response/fragments/-1/elapsed_secs" or "elapsed_secs" in p:
            current_path = "content"
        elif "response/fragments/1" in p or "response/fragments/2" in p:
            current_path = "content"
        elif "response/fragments/0" in p and not current_path:
            current_path = "thinking"

    # 4. Batch updates or direct thinking_enabled toggle
    if p == "response" and isinstance(v, list):
        for entry in v:
            if isinstance(entry, dict):
                ep = entry.get("p")
                ev = entry.get("v")
                if (ep == "response/thinking_enabled" or ep == "thinking_enabled") and ev is False:
                    current_path = "content"
                elif ep == "response" and isinstance(ev, dict) and ev.get("thinking_enabled") is False:
                    current_path = "content"

    if p == "response/thinking_enabled":
        if v is False:
            current_path = "content"
        elif v is True:
            current_path = "thinking"

    # 5. Search results
    if p == "response/search_results" and isinstance(v, list):
        search_results.extend(v)

    # 6. Direct string delta tokens (e.g. {"v": " word"})
    if isinstance(v, str):
        text = clean_deepseek_token(v)
        if text:
            if "</think>" in text:
                parts = text.split("</think>", 1)
                before = parts[0].strip()
                after = parts[1].lstrip()
                if before:
                    chunks.append(("thinking", before))
                current_path = "content"
                if after:
                    chunks.append(("content", after))
            else:
                target = current_path if current_path else ("thinking" if thinking_model else "content")
                chunks.append((target, text))

    return current_path, chunks, search_results


def extract_message_text(content: Any) -> str:
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return str(content or "")


def is_thinking_model(model: str) -> bool:
    m = model.lower()
    return "r1" in m or "think" in m or "reason" in m


def is_search_model(model: str) -> bool:
    m = model.lower()
    return "search" in m


def append_search_citations(search_results: List[Dict[str, Any]], model: str) -> str:
    if not search_results or "search-silent" in model.lower():
        return ""
    valid = [r for r in search_results if r.get("cite_index")]
    valid.sort(key=lambda r: int(r.get("cite_index", 0)))
    lines = [
        f"[{r['cite_index']}]: [{r.get('title', 'Source')}]({r.get('url', '')})"
        for r in valid
        if r.get("url")
    ]
    return "\n".join(lines)


def serialize_tools_prompt(tools: List[Dict[str, Any]], nonce: str) -> str:
    """Serialize OpenAI tools into DeepSeek strict prompt contract."""
    lines = []
    for t in tools:
        fn = t.get("function") if isinstance(t, dict) else None
        if not fn or not fn.get("name"):
            continue
        name = fn.get("name")
        desc = fn.get("description", "")
        params = fn.get("parameters")
        param_str = json.dumps(params) if params else ""
        line = f"- {name}"
        if desc:
            line += f": {desc}"
        if param_str:
            line += f"\n  parameters: {param_str}"
        lines.append(line)

    if not lines:
        return ""

    return (
        "You can call tools. To call a tool, output ONLY this exact block (no markdown fence):\n"
        f'<tool>{{"name": "<tool_name>", "arguments": {{ ... }}, "_nonce": "{nonce}"}}</tool>\n'
        "Rules:\n"
        "- Use exactly <tool>...</tool>. Do NOT use <tool:name>, <tool_call>, <name>, <parameter>, id=/name= attributes, or code fences.\n"
        f'- Include the secret binding "_nonce": "{nonce}" exactly as shown.\n'
        '- "name" must be one of the tools below; "arguments" must be a JSON object.\n'
        "- When a tool is needed, emit the <tool> block instead of only describing the plan.\n"
        "- Emit one <tool> block per call; you may put several blocks back to back.\n"
        "- If no tool is needed, just answer normally without any <tool> block.\n\n"
        "Available tools:\n" + "\n".join(lines)
    )


def parse_tool_calls_from_text(text: str, nonce: str) -> Tuple[str, List[ToolCall]]:
    """Parse <tool>{...}</tool> blocks from generated text into ToolCall objects."""
    tool_calls: List[ToolCall] = []
    pattern = re.compile(r"<tool>(.*?)</tool>", re.DOTALL)

    def repl(match: re.Match) -> str:
        body = match.group(1).strip()
        try:
            parsed = json.loads(body)
            if isinstance(parsed, dict) and parsed.get("_nonce") == nonce:
                name = parsed.get("name", "")
                args = parsed.get("arguments", {})
                args_str = json.dumps(args) if isinstance(args, dict) else str(args)
                tool_calls.append(
                    ToolCall(
                        id=f"call_{uuid.uuid4().hex[:12]}",
                        type="function",
                        function=FunctionCall(name=name, arguments=args_str),
                    )
                )
                return ""
        except Exception:
            pass
        return match.group(0)

    cleaned_text = pattern.sub(repl, text).strip()
    return cleaned_text, tool_calls


def build_prompt_from_messages(
    messages: List[ChatMessage],
    history_window: int = 20,
    tool_system_prompt: str = "",
) -> str:
    """Format chat messages into DeepSeek single-prompt string."""
    system_parts: List[str] = []
    if tool_system_prompt:
        system_parts.append(tool_system_prompt)

    conversation: List[Tuple[str, str]] = []
    call_name_by_id: Dict[str, str] = {}
    last_user_content = ""

    for m in messages:
        text = extract_message_text(m.content).strip()
        role = m.role

        if role == "system":
            if text:
                system_parts.append(text)
        elif role in ("user", "assistant"):
            if text:
                conversation.append((role, text))
            if role == "user":
                last_user_content = text
            if m.tool_calls:
                for tc in m.tool_calls:
                    if tc.id and tc.function and tc.function.name:
                        call_name_by_id[tc.id] = tc.function.name
        elif role == "tool":
            if text:
                name = call_name_by_id.get(m.tool_call_id or "", m.name or "tool")
                conversation.append(("tool", f"({name}) {text}"))

    parts: List[str] = []
    if system_parts:
        parts.append("\n\n".join(system_parts))

    effective_window = history_window if history_window > 0 else (20 if len(conversation) > 1 else 0)

    if effective_window > 0 and len(conversation) > 1:
        recent = conversation[-effective_window:]
        transcript_lines = []
        for r, t in recent:
            if r == "assistant":
                transcript_lines.append(f"Assistant: {t}")
            elif r == "tool":
                transcript_lines.append(f"Tool result {t}")
            else:
                transcript_lines.append(f"User: {t}")
        parts.append("\n\n".join(transcript_lines))
    elif last_user_content:
        parts.append(last_user_content)

    full_prompt = "\n\n".join(parts)
    # Strip any markdown image URLs per omniroute
    full_prompt = re.sub(r"!\[.*?\]\(.*?\)", "", full_prompt)
    return full_prompt


class DeepSeekWebModule(BaseModuleAdapter):
    """
    Reverse-engineered DeepSeek Web Chat Provider module based on OmniRoute architecture.
    """

    def __init__(self):
        # user_token -> (access_token, expire_timestamp)
        self._token_cache: Dict[str, Tuple[str, float]] = {}
        # user_token -> session_id
        self._session_cache: Dict[str, str] = {}

    async def _acquire_access_token(
        self,
        client: httpx.AsyncClient,
        user_token: str,
    ) -> str:
        """Acquire short-lived access token from /api/v0/users/current."""
        now = time.time()
        cached = self._token_cache.get(user_token)
        if cached and cached[1] > now:
            return cached[0]

        headers = {
            "Authorization": f"Bearer {user_token}",
            **FAKE_HEADERS,
        }

        resp = await client.get(f"{DEEPSEEK_API_BASE}/v0/users/current", headers=headers)
        if resp.status_code in (401, 403):
            self._token_cache.pop(user_token, None)
            raise ValueError("DeepSeek userToken invalid or expired. Please extract fresh userToken from localStorage.")
        if resp.status_code != 200:
            raise RuntimeError(f"users/current HTTP {resp.status_code}: {resp.text}")

        data = resp.json()
        code = data.get("code")
        if code is not None and code != 0:
            err_msg = data.get("msg") or data.get("data", {}).get("biz_msg") or f"error code {code}"
            self._token_cache.pop(user_token, None)
            raise RuntimeError(f"DeepSeek rejected token: {err_msg}")

        biz_data = data.get("data", {}).get("biz_data") or data.get("biz_data") or {}
        access_token = biz_data.get("token")
        if not access_token:
            err_msg = data.get("msg") or "Failed to extract access token from biz_data"
            raise RuntimeError(err_msg)

        # Cache token for 55 minutes
        self._token_cache[user_token] = (access_token, now + 3300)
        return access_token

    async def _create_session(
        self,
        client: httpx.AsyncClient,
        access_token: str,
    ) -> str:
        """Create a new chat session on DeepSeek web backend."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Cookie": generate_fake_cookie(),
            **FAKE_HEADERS,
        }
        resp = await client.post(f"{DEEPSEEK_API_BASE}/v0/chat_session/create", headers=headers, json={})
        if resp.status_code != 200:
            raise RuntimeError(f"chat_session/create HTTP {resp.status_code}: {resp.text}")

        data = resp.json()
        biz_data = data.get("data", {}).get("biz_data") or data.get("biz_data") or {}
        session_id = biz_data.get("chat_session", {}).get("id")
        if not session_id:
            raise RuntimeError(f"No session ID in response: code={data.get('code')}")
        return session_id

    async def _delete_session(
        self,
        client: httpx.AsyncClient,
        access_token: str,
        session_id: str,
    ) -> None:
        """Clean up chat session on DeepSeek web backend (best effort)."""
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                **FAKE_HEADERS,
            }
            await client.post(
                f"{DEEPSEEK_API_BASE}/v0/chat_session/delete",
                headers=headers,
                json={"chat_session_id": session_id},
            )
        except Exception:
            pass

    async def _get_pow_challenge(
        self,
        client: httpx.AsyncClient,
        access_token: str,
    ) -> Dict[str, Any]:
        """Request Proof-of-Work challenge from DeepSeek server."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            **FAKE_HEADERS,
        }
        resp = await client.post(
            f"{DEEPSEEK_API_BASE}/v0/chat/create_pow_challenge",
            headers=headers,
            json={"target_path": "/api/v0/chat/completion"},
        )
        if resp.status_code != 200:
            raise RuntimeError(f"create_pow_challenge HTTP {resp.status_code}: {resp.text}")

        data = resp.json()
        biz_data = data.get("data", {}).get("biz_data") or data.get("biz_data") or {}
        challenge = biz_data.get("challenge")
        if not challenge or not challenge.get("challenge"):
            raise RuntimeError(f"Invalid PoW challenge response: code={data.get('code')}")
        return challenge

    async def validate_credentials(
        self,
        ctx: ModuleExecutionContext,
    ) -> Tuple[bool, str, int]:
        """Validate userToken and proxy connection by calling users/current."""
        user_token = extract_user_token(ctx.credentials)
        if not user_token:
            return False, "user_token is required. Paste your token from chat.deepseek.com localStorage.", 0

        try:
            async with self.create_http_client(ctx, timeout=15.0) as client:
                access_token = await self._acquire_access_token(client, user_token)
                if not access_token:
                    return False, "Could not acquire access token from DeepSeek", 0
            return True, "DeepSeek Web account connected and verified successfully!", 4
        except Exception as e:
            logger.error(f"DeepSeek Web validation error: {e}")
            return False, f"DeepSeek validation failed: {e}", 0

    async def list_models(
        self,
        ctx: ModuleExecutionContext,
    ) -> List[DiscoveredModelData]:
        """Return available DeepSeek Web model offerings."""
        return [
            DiscoveredModelData(
                provider_model_id="deepseek-chat",
                display_name="DeepSeek V3 (Chat Web)",
                context_length=64000,
                max_output_tokens=8192,
            ),
            DiscoveredModelData(
                provider_model_id="deepseek-reasoner",
                display_name="DeepSeek R1 (Reasoner Web)",
                context_length=64000,
                max_output_tokens=8192,
            ),
            DiscoveredModelData(
                provider_model_id="deepseek-search",
                display_name="DeepSeek Chat + Web Search",
                context_length=64000,
                max_output_tokens=8192,
            ),
            DiscoveredModelData(
                provider_model_id="deepseek-reasoner-search",
                display_name="DeepSeek R1 + Web Search",
                context_length=64000,
                max_output_tokens=8192,
            ),
        ]

    def _resolve_model_options(
        self,
        model_id: str,
        request: ChatCompletionRequest,
    ) -> Tuple[str, bool, bool]:
        """Resolve model_type ('default' | 'expert'), thinking_enabled, and search_enabled."""
        m = (model_id or request.model or "").lower()
        model_type = "expert" if ("pro" in m or "expert" in m) else "default"

        thinking_enabled = (
            "r1" in m
            or "think" in m
            or "reason" in m
            or getattr(request, "reasoning_effort", None) is not None
            or (request.thinking is not None and request.thinking.get("type") != "disabled")
            or request.reasoning is not None
        )

        search_enabled = "search" in m

        return model_type, thinking_enabled, search_enabled

    async def _send_completion_request(
        self,
        client: httpx.AsyncClient,
        access_token: str,
        session_id: str,
        model_type: str,
        thinking_enabled: bool,
        search_enabled: bool,
        prompt: str,
    ) -> httpx.Response:
        """Acquire PoW challenge, solve it via WASM/JS, and send completion request."""
        # 1. Fetch challenge
        challenge_dict = await self._get_pow_challenge(client, access_token)
        # 2. Solve challenge
        _, b64_pow_header = await solve_deepseek_pow(challenge_dict)

        headers = {
            **FAKE_HEADERS,
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "X-Ds-Pow-Response": b64_pow_header,
            "X-Client-Timezone-Offset": "-180",
            "Cookie": generate_fake_cookie(),
        }

        payload = {
            "chat_session_id": session_id,
            "parent_message_id": None,
            "model_type": model_type,
            "prompt": prompt,
            "ref_file_ids": [],
            "thinking_enabled": thinking_enabled,
            "search_enabled": search_enabled,
            "preempt": False,
        }

        req = client.build_request("POST", COMPLETION_URL, headers=headers, json=payload, timeout=120.0)
        resp = await client.send(req, stream=True)
        return resp

    async def chat_completions(
        self,
        request: ChatCompletionRequest,
        ctx: ModuleExecutionContext,
    ) -> ChatCompletionResponse:
        """Handle non-streaming chat completion request by consuming the upstream SSE stream."""
        user_token = extract_user_token(ctx.credentials)
        if not user_token:
            raise ValueError("user_token credential is required")

        persist_session = str(ctx.credentials.get("persist_session", "false")).lower() in ("true", "1", "yes")
        try:
            history_window = int(ctx.credentials.get("history_window", 20))
        except (ValueError, TypeError):
            history_window = 20

        model_id = ctx.model_id or request.model
        model_type, thinking_enabled, search_enabled = self._resolve_model_options(model_id, request)

        # Handle tools serialization
        nonce = uuid.uuid4().hex[:8]
        tool_prompt = serialize_tools_prompt(request.tools, nonce) if request.tools else ""
        prompt = build_prompt_from_messages(request.messages, history_window, tool_prompt)

        async with self.create_http_client(ctx, timeout=120.0) as client:
            access_token = await self._acquire_access_token(client, user_token)

            # Session handling
            session_id = None
            if persist_session and user_token in self._session_cache:
                session_id = self._session_cache[user_token]
            else:
                session_id = await self._create_session(client, access_token)
                if persist_session:
                    self._session_cache[user_token] = session_id

            try:
                resp = await self._send_completion_request(
                    client, access_token, session_id, model_type, thinking_enabled, search_enabled, prompt
                )

                # Retry once if session expired or failed with persistent session
                if resp.status_code != 200 and persist_session:
                    logger.warning("Reused session failed, creating fresh session and retrying...")
                    await resp.aclose()
                    self._session_cache.pop(user_token, None)
                    session_id = await self._create_session(client, access_token)
                    self._session_cache[user_token] = session_id
                    resp = await self._send_completion_request(
                        client, access_token, session_id, model_type, thinking_enabled, search_enabled, prompt
                    )

                if resp.status_code != 200:
                    body_text = await resp.aread()
                    await resp.aclose()
                    raise RuntimeError(f"DeepSeek upstream error HTTP {resp.status_code}: {body_text.decode('utf-8', errors='ignore')}")

                # Collect SSE stream
                content_accum: List[str] = []
                reasoning_accum: List[str] = []
                search_results: List[Dict[str, Any]] = []

                current_path = ""
                thinking_model = is_thinking_model(model_id)

                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data:"):
                        payload = line[5:].strip()
                        if payload == "[DONE]":
                            break
                        try:
                            data = json.loads(payload)
                        except Exception:
                            continue

                        current_path, chunks, s_results = process_deepseek_sse_data(
                            data, current_path, thinking_model
                        )
                        for target, text in chunks:
                            if target == "thinking":
                                reasoning_accum.append(text)
                            else:
                                content_accum.append(text)
                        if s_results:
                            search_results.extend(s_results)

                await resp.aclose()

                raw_content = "".join(content_accum)
                reasoning_content = "".join(reasoning_accum) or None

                # Append citations if any
                citations = append_search_citations(search_results, model_id)
                if citations:
                    raw_content = f"{raw_content}\n\n{citations}" if raw_content else citations

                # Parse tool calls if tools were requested
                tool_calls: Optional[List[ToolCall]] = None
                finish_reason = "stop"
                if request.tools:
                    raw_content, parsed_tools = parse_tool_calls_from_text(raw_content, nonce)
                    if parsed_tools:
                        tool_calls = parsed_tools
                        finish_reason = "tool_calls"

                choice = ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content=raw_content or ("" if tool_calls else None),
                        reasoning_content=reasoning_content,
                        tool_calls=tool_calls,
                    ),
                    finish_reason=finish_reason,
                )

                return ChatCompletionResponse(
                    id=f"chatcmpl-{uuid.uuid4().hex[:12]}",
                    model=model_id,
                    created=int(time.time()),
                    choices=[choice],
                    usage=UsageInfo(
                        prompt_tokens=len(prompt) // 4,
                        completion_tokens=(len(raw_content) + len(reasoning_content or "")) // 4,
                        total_tokens=(len(prompt) + len(raw_content) + len(reasoning_content or "")) // 4,
                    ),
                )
            finally:
                if not persist_session and session_id:
                    await self._delete_session(client, access_token, session_id)

    async def stream_chat(
        self,
        request: ChatCompletionRequest,
        ctx: ModuleExecutionContext,
    ) -> AsyncGenerator[str, None]:
        """Handle streaming chat completion request yielding OpenAI SSE chunks."""
        user_token = extract_user_token(ctx.credentials)
        if not user_token:
            err_chunk = ChatCompletionChunk(
                model=request.model,
                choices=[
                    ChatCompletionChunkChoice(
                        index=0,
                        delta=ChatCompletionChunkDelta(content="Error: user_token is required"),
                        finish_reason="stop",
                    )
                ],
            )
            yield f"data: {err_chunk.model_dump_json()}\n\ndata: [DONE]\n\n"
            return

        persist_session = str(ctx.credentials.get("persist_session", "false")).lower() in ("true", "1", "yes")
        try:
            history_window = int(ctx.credentials.get("history_window", 20))
        except (ValueError, TypeError):
            history_window = 20

        model_id = ctx.model_id or request.model
        model_type, thinking_enabled, search_enabled = self._resolve_model_options(model_id, request)

        # Build prompt
        prompt = build_prompt_from_messages(request.messages, history_window)

        client = self.create_http_client(ctx, timeout=120.0)
        session_id = None
        access_token = None

        try:
            await client.__aenter__()
            access_token = await self._acquire_access_token(client, user_token)

            if persist_session and user_token in self._session_cache:
                session_id = self._session_cache[user_token]
            else:
                session_id = await self._create_session(client, access_token)
                if persist_session:
                    self._session_cache[user_token] = session_id

            resp = await self._send_completion_request(
                client, access_token, session_id, model_type, thinking_enabled, search_enabled, prompt
            )

            # Retry once with fresh session if reused session failed
            if resp.status_code != 200 and persist_session:
                await resp.aclose()
                self._session_cache.pop(user_token, None)
                session_id = await self._create_session(client, access_token)
                self._session_cache[user_token] = session_id
                resp = await self._send_completion_request(
                    client, access_token, session_id, model_type, thinking_enabled, search_enabled, prompt
                )

            if resp.status_code != 200:
                body_text = await resp.aread()
                await resp.aclose()
                err_chunk = ChatCompletionChunk(
                    model=model_id,
                    choices=[
                        ChatCompletionChunkChoice(
                            index=0,
                            delta=ChatCompletionChunkDelta(
                                content=f"DeepSeek upstream error HTTP {resp.status_code}: {body_text.decode('utf-8', errors='ignore')}"
                            ),
                            finish_reason="stop",
                        )
                    ],
                )
                yield f"data: {err_chunk.model_dump_json()}\n\ndata: [DONE]\n\n"
                return

            completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
            created_ts = int(time.time())

            # Emit initial role chunk
            init_chunk = ChatCompletionChunk(
                id=completion_id,
                created=created_ts,
                model=model_id,
                choices=[
                    ChatCompletionChunkChoice(
                        index=0,
                        delta=ChatCompletionChunkDelta(role="assistant", content=""),
                        finish_reason=None,
                    )
                ],
            )
            yield f"data: {init_chunk.model_dump_json()}\n\n"

            current_path = ""
            thinking_model = is_thinking_model(model_id)
            search_results: List[Dict[str, Any]] = []

            async for line in resp.aiter_lines():
                if not line:
                    continue
                if line.startswith("data:"):
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        data = json.loads(payload)
                    except Exception:
                        continue

                    current_path, chunks, s_results = process_deepseek_sse_data(
                        data, current_path, thinking_model
                    )
                    if s_results:
                        search_results.extend(s_results)

                    for target, text in chunks:
                        if target == "thinking":
                            c = ChatCompletionChunk(
                                id=completion_id,
                                created=created_ts,
                                model=model_id,
                                choices=[
                                    ChatCompletionChunkChoice(
                                        index=0,
                                        delta=ChatCompletionChunkDelta(reasoning_content=text),
                                        finish_reason=None,
                                    )
                                ],
                            )
                            yield f"data: {c.model_dump_json()}\n\n"
                        else:
                            c = ChatCompletionChunk(
                                id=completion_id,
                                created=created_ts,
                                model=model_id,
                                choices=[
                                    ChatCompletionChunkChoice(
                                        index=0,
                                        delta=ChatCompletionChunkDelta(content=text),
                                        finish_reason=None,
                                    )
                                ],
                            )
                            yield f"data: {c.model_dump_json()}\n\n"

            await resp.aclose()

            # Append citations at the end if web search was enabled
            citations = append_search_citations(search_results, model_id)
            if citations:
                citation_chunk = ChatCompletionChunk(
                    id=completion_id,
                    created=created_ts,
                    model=model_id,
                    choices=[
                        ChatCompletionChunkChoice(
                            index=0,
                            delta=ChatCompletionChunkDelta(content=f"\n\n{citations}"),
                            finish_reason=None,
                        )
                    ],
                )
                yield f"data: {citation_chunk.model_dump_json()}\n\n"

            # Final finish stop chunk
            stop_chunk = ChatCompletionChunk(
                id=completion_id,
                created=created_ts,
                model=model_id,
                choices=[
                    ChatCompletionChunkChoice(
                        index=0,
                        delta=ChatCompletionChunkDelta(),
                        finish_reason="stop",
                    )
                ],
            )
            yield f"data: {stop_chunk.model_dump_json()}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"Error in DeepSeek Web stream: {e}", exc_info=True)
            err_chunk = ChatCompletionChunk(
                model=model_id,
                choices=[
                    ChatCompletionChunkChoice(
                        index=0,
                        delta=ChatCompletionChunkDelta(content=f"\n[Error: {str(e)}]"),
                        finish_reason="stop",
                    )
                ],
            )
            yield f"data: {err_chunk.model_dump_json()}\n\ndata: [DONE]\n\n"

        finally:
            if not persist_session and session_id and access_token:
                try:
                    await self._delete_session(client, access_token, session_id)
                except Exception:
                    pass
            try:
                await client.__aexit__(None, None, None)
            except Exception:
                pass
