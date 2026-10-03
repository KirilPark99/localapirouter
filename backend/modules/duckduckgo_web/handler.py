import os
import json
import time
import uuid
import logging
import asyncio
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from app.modules.base import BaseModuleAdapter, ModuleExecutionContext
from app.schemas.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatMessage,
    UsageInfo,
)
from app.core.errors import RouterException, ErrorCategory
from app.adapters.base import DiscoveredModelData

logger = logging.getLogger("app.modules.duckduckgo_web")

SOLVE_CJS_PATH = Path(__file__).parent / "solve.cjs"

DUCKDUCKGO_BASE = "https://duckduckgo.com"
STATUS_URL = f"{DUCKDUCKGO_BASE}/duckchat/v1/status"
CHAT_URL = f"{DUCKDUCKGO_BASE}/duckchat/v1/chat"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
)

MODELS_URL = f"{DUCKDUCKGO_BASE}/duckchat/v1/models"

MODEL_ALIASES = {
    "gpt-4o-mini": "gpt-5.4-mini",
    "gpt-5-mini": "gpt-5.4-mini",
    "gpt-5.4-nano": "gpt-5.4-mini",
    "o3-mini": "gpt-5.4-mini",
    "claude-3-5-haiku-20241022": "claude-haiku-4-5",
    "mistral-small-24b-instruct-2501": "mistral-small-2603",
    "mistral-small-2501": "mistral-small-2603",
    "gpt-oss-120b": "tinfoil/gpt-oss-120b",
    "gemma4-31b": "tinfoil/gemma4-31b",
    "llama-3.3-70b-instruct": "gpt-5.6-luna",
    "llama-4-scout": "gpt-5.6-luna",
}

# Only free, anonymous models that require zero subscription/credentials
STATIC_DEFAULT_MODELS: List[DiscoveredModelData] = [
    DiscoveredModelData(
        provider_model_id="gpt-5.6-luna",
        display_name="GPT-5.6 Luna (Everyday Use)",
        capabilities={"chat": True, "streaming": True, "vision": True, "tools": True, "reasoning": True},
        context_length=128000,
        max_output_tokens=4096,
    ),
    DiscoveredModelData(
        provider_model_id="gpt-5.4-mini",
        display_name="GPT-5.4 mini",
        capabilities={"chat": True, "streaming": True, "vision": True, "tools": True, "reasoning": True},
        context_length=128000,
        max_output_tokens=4096,
    ),
    DiscoveredModelData(
        provider_model_id="claude-haiku-4-5",
        display_name="Claude Haiku 4.5",
        capabilities={"chat": True, "streaming": True, "vision": True, "tools": True, "reasoning": True},
        context_length=200000,
        max_output_tokens=4096,
        reasoning_effort="low",
    ),
    DiscoveredModelData(
        provider_model_id="mistral-small-2603",
        display_name="Mistral Small 4",
        capabilities={"chat": True, "streaming": True, "vision": False, "tools": False, "reasoning": False},
        context_length=128000,
        max_output_tokens=4096,
    ),
    DiscoveredModelData(
        provider_model_id="tinfoil/gpt-oss-120b",
        display_name="gpt-oss 120B",
        capabilities={"chat": True, "streaming": True, "vision": False, "tools": True, "reasoning": True},
        context_length=128000,
        max_output_tokens=4096,
        reasoning_effort="low",
    ),
    DiscoveredModelData(
        provider_model_id="tinfoil/gemma4-31b",
        display_name="Gemma 4 31B",
        capabilities={"chat": True, "streaming": True, "vision": True, "tools": True, "reasoning": True},
        context_length=128000,
        max_output_tokens=4096,
    ),
]


def normalize_model(model_name: Optional[str]) -> str:
    if not model_name:
        return "gpt-5.6-luna"
    clean = model_name
    if clean.startswith("duckduckgo_web/"):
        clean = clean[len("duckduckgo_web/"):]
    elif clean.startswith("duckduckgo-web/"):
        clean = clean[len("duckduckgo-web/"):]
    return MODEL_ALIASES.get(clean, clean)


def solve_challenge_sync(challenge_b64: str, user_agent: str = DEFAULT_USER_AGENT) -> str:
    res = subprocess.run(
        ["node", str(SOLVE_CJS_PATH), challenge_b64, user_agent],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if res.returncode != 0:
        raise RuntimeError(f"Failed to solve DuckDuckGo challenge: {res.stderr.strip()}")
    return res.stdout.strip()


def build_opener(proxy_url: Optional[str] = None) -> urllib.request.OpenerDirector:
    handlers: List[Any] = []
    if proxy_url:
        handlers.append(urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url}))
    return urllib.request.build_opener(*handlers)


class DuckDuckGoWebAdapter(BaseModuleAdapter):
    """
    Adapter for DuckDuckGo AI Chat (free, anonymous, reverse-engineered).
    """

    async def validate_credentials(
        self,
        ctx: ModuleExecutionContext,
    ) -> Tuple[bool, str, int]:
        def _check():
            opener = build_opener(ctx.proxy_url)
            req = urllib.request.Request(
                STATUS_URL,
                headers={"User-Agent": DEFAULT_USER_AGENT, "x-vqd-accept": "1"},
            )
            with opener.open(req, timeout=15) as resp:
                vqd4 = resp.headers.get("x-vqd-4")
                vqd_hash1 = resp.headers.get("x-vqd-hash-1")
                return resp.status == 200 and (bool(vqd4) or bool(vqd_hash1))

        try:
            ok = await asyncio.to_thread(_check)
            if ok:
                models = await self.list_models(ctx)
                return True, "DuckDuckGo AI Chat is operational (VQD acquired)", len(models)
            return False, "Failed to acquire VQD token from DuckDuckGo", 0
        except Exception as e:
            return False, f"Connection failed: {str(e)}", 0

    async def list_models(
        self,
        ctx: ModuleExecutionContext,
    ) -> List[DiscoveredModelData]:
        has_pro_cookie = bool(ctx.credentials.get("cookie"))

        def _fetch_live() -> Optional[List[DiscoveredModelData]]:
            try:
                opener = build_opener(ctx.proxy_url)
                req_headers = {
                    "User-Agent": DEFAULT_USER_AGENT,
                    "Accept": "application/json",
                    "Origin": DUCKDUCKGO_BASE,
                    "Referer": f"{DUCKDUCKGO_BASE}/",
                }
                if has_pro_cookie:
                    req_headers["Cookie"] = str(ctx.credentials["cookie"]).strip()

                req = urllib.request.Request(MODELS_URL, headers=req_headers)
                with opener.open(req, timeout=10) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode())
                        raw_models = data.get("models", [])
                        if raw_models:
                            result = []
                            for m in raw_models:
                                m_id = m.get("id")
                                name = m.get("name") or m_id
                                is_free = m.get("entityHasAccess", True) or ("free" in m.get("accessTier", []))
                                # Only expose paid/restricted models if the user supplied a Pro cookie
                                if not has_pro_cookie and not is_free:
                                    continue

                                supports_tools = bool(m.get("supportedTools"))
                                supports_vision = bool(m.get("supportsImageUpload"))
                                reasoning_supported = bool(m.get("supportedReasoningEffort"))
                                tier_list = m.get("accessTier", [])
                                tier_str = "/".join(tier_list)
                                display = f"{name} ({tier_str})" if not is_free else name
                                result.append(
                                    DiscoveredModelData(
                                        provider_model_id=m_id,
                                        display_name=display,
                                        capabilities={
                                            "chat": True,
                                            "streaming": True,
                                            "vision": supports_vision,
                                            "tools": supports_tools,
                                            "reasoning": reasoning_supported,
                                        },
                                        context_length=200000 if "claude" in m_id else 128000,
                                        max_output_tokens=4096,
                                    )
                                )
                            return result
            except Exception as e:
                logger.debug(f"Failed to query live DuckDuckGo models endpoint: {e}")
            return None

        live = await asyncio.to_thread(_fetch_live)
        if live:
            return live
        return STATIC_DEFAULT_MODELS

    def _acquire_auth_headers_sync(
        self,
        proxy_url: Optional[str] = None,
        cookie: Optional[str] = None,
    ) -> Dict[str, str]:
        opener = build_opener(proxy_url)
        base_cookie = "5=1; ah=wt-wt; dcs=1; dcm=3; isRecentChatOn=1"
        cookie_header = f"{base_cookie}; {cookie.strip()}" if cookie and cookie.strip() else base_cookie

        headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "*/*",
            "Cache-Control": "no-store",
            "x-vqd-accept": "1",
            "Cookie": cookie_header,
        }
        req = urllib.request.Request(STATUS_URL, headers=headers)
        try:
            with opener.open(req, timeout=15) as resp:
                vqd4 = resp.headers.get("x-vqd-4")
                vqd_hash1 = resp.headers.get("x-vqd-hash-1")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise RouterException(
                    "DuckDuckGo временно ограничил этот IP по частоте запросов (HTTP 429). Привяжите прокси к профилю модуля в админ-панели или подождите минуту.",
                    category=ErrorCategory.RATE_LIMIT,
                    status_code=429,
                )
            raise

        if vqd4:
            return {"x-vqd-4": vqd4}
        if vqd_hash1:
            solved = solve_challenge_sync(vqd_hash1, DEFAULT_USER_AGENT)
            return {"x-vqd-hash-1": solved}

        raise RuntimeError("No VQD token or challenge header returned by DuckDuckGo")

    def _build_payload(self, request: ChatCompletionRequest, model: str) -> Dict[str, Any]:
        reasoning_effort = "none"
        if model == "tinfoil/gpt-oss-120b":
            reasoning_effort = "low"
        elif model in ("claude-haiku-4-5", "gpt-5.4-mini", "gpt-5.6-luna", "tinfoil/gemma4-31b"):
            user_effort = getattr(request, "reasoning_effort", None)
            if user_effort in ("low", "medium"):
                reasoning_effort = user_effort
            elif model == "claude-haiku-4-5":
                reasoning_effort = "low"

        # DuckDuckGo strictly rejects role: "system" with HTTP 400 ERR_BAD_REQUEST.
        # We fold any system instructions cleanly into the first user message turn.
        system_prompts: List[str] = []
        conversation_messages: List[Dict[str, str]] = []
        for m in request.messages:
            content = m.content if isinstance(m.content, str) else json.dumps(m.content)
            if not content:
                continue
            if m.role == "system":
                system_prompts.append(content)
            elif m.role in ("user", "assistant"):
                conversation_messages.append({"role": m.role, "content": content})

        if system_prompts:
            combined_system = "\n\n".join(system_prompts)
            if conversation_messages:
                first = conversation_messages[0]
                if first["role"] == "user":
                    first["content"] = f"[System Instructions: {combined_system}]\n\n{first['content']}"
                else:
                    conversation_messages.insert(0, {"role": "user", "content": f"[System Instructions: {combined_system}]"})
            else:
                conversation_messages.append({"role": "user", "content": f"[System Instructions: {combined_system}]"})

        if not conversation_messages:
            conversation_messages = [{"role": "user", "content": "Hello"}]

        payload: Dict[str, Any] = {
            "model": model,
            "messages": conversation_messages,
        }
        if model != "mistral-small-2603":
            payload["reasoningEffort"] = reasoning_effort
        return payload

    async def chat_completions(
        self,
        request: ChatCompletionRequest,
        ctx: ModuleExecutionContext,
    ) -> ChatCompletionResponse:
        full_content = ""
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
                if content:
                    full_content += content
            except Exception:
                pass

        model_name = normalize_model(request.model or ctx.model_id)
        return ChatCompletionResponse(
            id=f"chatcmpl-ddg-{uuid.uuid4().hex[:12]}",
            object="chat.completion",
            created=int(time.time()),
            model=model_name,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=full_content),
                    finish_reason="stop",
                )
            ],
            usage=UsageInfo(
                prompt_tokens=len(str(request.messages)) // 4,
                completion_tokens=len(full_content) // 4,
                total_tokens=(len(str(request.messages)) + len(full_content)) // 4,
            ),
        )

    async def stream_chat(
        self,
        request: ChatCompletionRequest,
        ctx: ModuleExecutionContext,
    ) -> AsyncGenerator[str, None]:
        model = normalize_model(request.model or ctx.model_id)
        payload = self._build_payload(request, model)

        queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
        req_id = f"chatcmpl-ddg-{uuid.uuid4().hex[:12]}"
        created_ts = int(time.time())

        def _worker():
            try:
                cookie_val = ctx.credentials.get("cookie")
                opener = build_opener(ctx.proxy_url)
                auth_headers = self._acquire_auth_headers_sync(ctx.proxy_url, cookie_val)

                base_cookie = "5=1; ah=wt-wt; dcs=1; dcm=3; isRecentChatOn=1"
                cookie_header = f"{base_cookie}; {cookie_val.strip()}" if cookie_val and cookie_val.strip() else base_cookie

                headers = {
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream",
                    "User-Agent": DEFAULT_USER_AGENT,
                    "Origin": DUCKDUCKGO_BASE,
                    "Referer": f"{DUCKDUCKGO_BASE}/",
                    "Cookie": cookie_header,
                    **auth_headers,
                }

                data_bytes = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(CHAT_URL, data=data_bytes, headers=headers, method="POST")

                try:
                    resp = opener.open(req, timeout=60)
                except urllib.error.HTTPError as e:
                    # Retry once if 418 challenge occurred
                    if e.code == 418:
                        next_hash = e.headers.get("x-vqd-hash-1")
                        if next_hash:
                            headers["x-vqd-hash-1"] = solve_challenge_sync(next_hash, DEFAULT_USER_AGENT)
                            headers.pop("x-vqd-4", None)
                        else:
                            auth_headers = self._acquire_auth_headers_sync(ctx.proxy_url, cookie_val)
                            headers.update(auth_headers)
                        req = urllib.request.Request(CHAT_URL, data=data_bytes, headers=headers, method="POST")
                        resp = opener.open(req, timeout=60)
                    else:
                        err_body = e.read().decode("utf-8", errors="ignore")
                        if "ERR_MODEL_RESTRICTED" in err_body or e.code == 404:
                            queue.put_nowait(f"__RESTRICTED__:{model}")
                            return
                        if "ERR_RATE_LIMIT" in err_body or e.code == 429:
                            queue.put_nowait(f"__RATELIMIT__:{e.code}")
                            return
                        raise RuntimeError(f"DuckDuckGo error {e.code}: {err_body[:300]}")

                with resp:
                    for line_bytes in resp:
                        line = line_bytes.decode("utf-8", errors="ignore").strip()
                        if not line:
                            continue
                        if line.startswith("data: "):
                            raw_data = line[6:].strip()
                            if raw_data == "[DONE]":
                                break
                            try:
                                data = json.loads(raw_data)
                                content = data.get("message") or data.get("content") or ""
                                if content:
                                    chunk = {
                                        "id": req_id,
                                        "object": "chat.completion.chunk",
                                        "created": created_ts,
                                        "model": model,
                                        "choices": [
                                            {
                                                "index": 0,
                                                "delta": {"content": content},
                                                "finish_reason": None,
                                            }
                                        ],
                                    }
                                    queue.put_nowait(f"data: {json.dumps(chunk)}\n\n")
                            except Exception:
                                pass
            except Exception as e:
                logger.error(f"DuckDuckGo stream error: {e}")
                queue.put_nowait(f"__ERROR__:{str(e)}")
            finally:
                queue.put_nowait(None)

        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, _worker)

        while True:
            item = await queue.get()
            if item is None:
                break
            if item.startswith("__RESTRICTED__:"):
                m_name = item[len("__RESTRICTED__:"):]
                raise RouterException(
                    f"Модель '{m_name}' доступна только по платной подписке DuckDuckGo Pro. Доступные бесплатные модели: gpt-5.6-luna, gpt-5.4-mini, claude-haiku-4-5, mistral-small-2603, tinfoil/gpt-oss-120b, tinfoil/gemma4-31b.",
                    category=ErrorCategory.AUTH_ERROR,
                    status_code=403,
                )
            if item.startswith("__RATELIMIT__:"):
                raise RouterException(
                    "DuckDuckGo временно ограничил этот IP по частоте запросов (HTTP 429). Привяжите прокси к профилю DuckDuckGo в панели управления или подождите минуту.",
                    category=ErrorCategory.RATE_LIMIT,
                    status_code=429,
                )
            if item.startswith("__ERROR__:"):
                raise RuntimeError(item[len("__ERROR__:"):])
            yield item

        yield "data: [DONE]\n\n"
