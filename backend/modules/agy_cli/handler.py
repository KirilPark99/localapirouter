import json
import time
import uuid
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

import httpx
from app.core.config import settings
from app.modules.base import BaseModuleAdapter, ModuleExecutionContext, SubscriptionLimit, SubscriptionLimits, collect_chat_completion
from app.core.errors import ErrorCategory, RouterException, normalize_upstream_error
from app.schemas.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
)
from app.adapters.base import DiscoveredModelData

logger = logging.getLogger("app.modules.agy_cli")

GOOGLE_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo"
CLOUDCODE_BASE_URLS = [
    "https://cloudcode-pa.googleapis.com",
    "https://daily-cloudcode-pa.googleapis.com",
]

# OAuth application credentials come from local settings, never hardcoded defaults.
AGY_CLIENT_ID = settings.ANTIGRAVITY_OAUTH_CLIENT_ID
AGY_CLIENT_SECRET = settings.ANTIGRAVITY_OAUTH_CLIENT_SECRET.get_secret_value()

LOCAL_TOKEN_PATHS = [
    Path.home() / ".gemini" / "antigravity-cli" / "antigravity-oauth-token",
    Path.home() / ".config" / "antigravity" / "token.json",
    Path.home() / ".config" / "antigravity-cli" / "token.json",
]


def _clean_str(val: Any) -> str:
    if val is None:
        return ""
    return str(val).strip()


def _get_str(d: Dict[str, Any], key: str, default: str = "") -> str:
    val = d.get(key)
    if val is None:
        return default
    return str(val).strip()


class AgyCliAdapter(BaseModuleAdapter):
    """
    Adapter for Google Antigravity CLI (`agy`).
    Supports local token auto-discovery, Google OAuth refresh, Cloud Code routing,
    and Gemini/Claude models.
    """

    def __init__(self):
        super().__init__()
        self._token_cache: Dict[Tuple[Any, str, str], Dict[str, Any]] = {}

    def _find_local_token_file(self) -> Optional[Path]:
        for p in LOCAL_TOKEN_PATHS:
            if p.exists() and p.is_file():
                return p
        return None

    def _resolve_raw_tokens(self, ctx: ModuleExecutionContext) -> Dict[str, Any]:
        """
        Extract token dictionary from credentials, pasted auth_json, or local file.
        """
        creds = ctx.credentials or {}
        explicit = any(creds.get(key) for key in ("access_token", "refresh_token", "auth_json", "project_id"))
        profile_id = ctx.extra_config.get("credential_id")
        auto_detect_raw = creds.get("auto_detect_local")
        if auto_detect_raw is None or auto_detect_raw == "":
            auto_detect = not explicit and profile_id is None
        elif isinstance(auto_detect_raw, bool):
            auto_detect = auto_detect_raw
        else:
            auto_detect = str(auto_detect_raw).strip().lower() in ("true", "1", "yes")

        # 1. Direct credentials
        access_token = _get_str(creds, "access_token")
        refresh_token = _get_str(creds, "refresh_token")
        project_id = _get_str(creds, "project_id")
        auth_json_str = _get_str(creds, "auth_json")

        if access_token or refresh_token:
            return {"access_token": access_token, "refresh_token": refresh_token, "project_id": project_id,
                    "expiry": creds.get("expiry", creds.get("expires_at"))}

        if auth_json_str:
            try:
                parsed = json.loads(auth_json_str)
                token_inner = parsed.get("token") if isinstance(parsed.get("token"), dict) else parsed
                return {
                    "access_token": _clean_str(token_inner.get("access_token")),
                    "refresh_token": _clean_str(token_inner.get("refresh_token")),
                    "project_id": project_id or _clean_str(parsed.get("project_id")) or _clean_str(token_inner.get("project_id")),
                    "expiry": token_inner.get("expiry", token_inner.get("expires_at")),
                }
            except (ValueError, TypeError, AttributeError) as exc:
                raise ValueError("Invalid Antigravity auth_json") from exc

        # 2. Local token auto-detection
        if auto_detect:
            local_path = self._find_local_token_file()
            if local_path:
                try:
                    with open(local_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    token_inner = data.get("token") if isinstance(data.get("token"), dict) else data
                    return {
                        "access_token": _clean_str(token_inner.get("access_token")),
                        "refresh_token": _clean_str(token_inner.get("refresh_token")),
                        "project_id": project_id or _clean_str(data.get("project_id")) or _clean_str(token_inner.get("project_id")),
                        "expiry": token_inner.get("expiry", token_inner.get("expires_at")),
                    }
                except Exception as e:
                    logger.warning(f"Failed to read local agy token file at {local_path}: {e}")

        return {}

    async def _get_valid_access_token(self, ctx: ModuleExecutionContext) -> Tuple[str, str]:
        """
        Returns (access_token, project_id), auto-refreshing via Google OAuth if expired or missing.
        """
        raw = self._resolve_raw_tokens(ctx)
        refresh_token = _clean_str(raw.get("refresh_token"))
        access_token = _clean_str(raw.get("access_token"))
        project_id = _clean_str(raw.get("project_id"))
        cache_key = (ctx.extra_config.get("credential_id"), refresh_token, access_token)
        cached = self._token_cache.get(cache_key)
        now = time.time()
        if cached and cached.get("expires_at", 0) > now + 60:
            return cached["access_token"], project_id

        expiry = raw.get("expiry")
        expires_at = None
        if expiry is not None and expiry != "":
            try:
                expires_at = float(expiry)
            except (ValueError, TypeError):
                try:
                    parsed = datetime.fromisoformat(str(expiry).replace("Z", "+00:00"))
                    if parsed.tzinfo is None:
                        raise ValueError("Token expiry must include a timezone")
                    expires_at = parsed.timestamp()
                except (ValueError, TypeError, OverflowError) as exc:
                    raise ValueError("Invalid Antigravity token expiry") from exc
            if not math.isfinite(expires_at):
                raise ValueError("Invalid Antigravity token expiry")
        if access_token and (expires_at is not None and expires_at > now + 60 or expires_at is None and not refresh_token):
            return access_token, project_id
        if not refresh_token or not AGY_CLIENT_ID or not AGY_CLIENT_SECRET:
            if access_token and (expires_at is None or expires_at > now):
                return access_token, project_id
            raise ValueError("No usable Antigravity token or OAuth refresh credentials available")

        async with self.create_http_client(ctx) as client:
            try:
                resp = await client.post(
                    GOOGLE_OAUTH_TOKEN_URL,
                    data={"client_id": AGY_CLIENT_ID, "client_secret": AGY_CLIENT_SECRET,
                          "grant_type": "refresh_token", "refresh_token": refresh_token},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=ctx.timeout,
                )
            except httpx.HTTPError as exc:
                raise normalize_upstream_error(exception=exc) from exc
        if resp.status_code != 200:
            if resp.status_code in (400, 401, 403):
                raise RouterException("Antigravity OAuth refresh rejected", ErrorCategory.AUTH_ERROR,
                                      upstream_status=resp.status_code)
            raise normalize_upstream_error(status_code=resp.status_code,
                                           response_body="Antigravity OAuth refresh rejected")
        try:
            data = resp.json()
            new_access = data.get("access_token")
            if not isinstance(new_access, str) or not new_access or not new_access.isascii() or any(c.isspace() for c in new_access):
                raise ValueError("Invalid refreshed access token")
            expires_in = data.get("expires_in")
            if expires_in is not None:
                if isinstance(expires_in, bool):
                    raise ValueError("Invalid refresh lifetime")
                lifetime = float(expires_in)
                if not math.isfinite(lifetime) or lifetime <= 0:
                    raise ValueError("Invalid refresh lifetime")
                self._token_cache[cache_key] = {"access_token": new_access, "expires_at": now + lifetime}
        except (ValueError, TypeError, AttributeError) as exc:
            raise RouterException("Invalid Antigravity OAuth refresh response", ErrorCategory.UPSTREAM_5XX) from exc
        return new_access, project_id

    def _build_cloudcode_headers(self, access_token: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "User-Agent": "antigravity/cli/1.0.0 (aidev_client; os_type=darwin; arch=arm64; auth_method=consumer)",
            "Accept": "application/json, text/event-stream",
        }

    async def _load_code_assist(self, ctx: ModuleExecutionContext, access_token: str, project_id: str) -> Tuple[str, Optional[str]]:
        body: Dict[str, Any] = {"metadata": {"ideType": "ANTIGRAVITY"}}
        if project_id:
            body["cloudaicompanionProject"] = project_id
        async with self.create_http_client(ctx) as client:
            resp = await client.post(f"{CLOUDCODE_BASE_URLS[0]}/v1internal:loadCodeAssist",
                                     headers=self._build_cloudcode_headers(access_token), json=body)
        if resp.status_code != 200:
            raise normalize_upstream_error(status_code=resp.status_code, response_body="Antigravity bootstrap rejected")
        data = resp.json()
        if not isinstance(data, dict) or data.get("error"):
            raise ValueError("Invalid Antigravity bootstrap response")
        discovered = data.get("cloudaicompanionProject")
        if isinstance(discovered, dict):
            discovered = discovered.get("id")
        if not isinstance(discovered, str):
            discovered = ""
        tier = data.get("paidTier") or data.get("currentTier") or {}
        plan = (tier.get("name") or tier.get("id")) if isinstance(tier, dict) else None
        plan = plan if isinstance(plan, str) and plan.strip() else None
        if not discovered.strip() and not plan:
            raise ValueError("Antigravity bootstrap returned no project or tier")
        resolved = project_id or discovered.strip()
        if not resolved:
            raise ValueError("Antigravity bootstrap returned no project; onboarding is required")
        return resolved, plan

    async def get_subscription_limits(self, ctx: ModuleExecutionContext) -> SubscriptionLimits:
        checked_at = datetime.now(timezone.utc).isoformat()
        plan = None
        try:
            access_token, project_id = await self._get_valid_access_token(ctx)
            project_id, plan = await self._load_code_assist(ctx, access_token, project_id)
            async with self.create_http_client(ctx) as client:
                resp = await client.post(f"{CLOUDCODE_BASE_URLS[0]}/v1internal:fetchAvailableModels",
                                         headers=self._build_cloudcode_headers(access_token), json={"project": project_id})
            if resp.status_code != 200:
                return SubscriptionLimits(status="unavailable", plan=plan, checked_at=checked_at,
                                          message=f"Antigravity quota request failed (HTTP {resp.status_code})")
            data = resp.json()
            models = data.get("models") if isinstance(data, dict) and not data.get("error") else None
            if not isinstance(models, dict):
                raise ValueError("Invalid Antigravity models response")
            limits = []
            for model, info in models.items():
                quota = info.get("quotaInfo") if isinstance(info, dict) else None
                if not isinstance(quota, dict):
                    continue
                fraction = quota.get("remainingFraction")
                remaining = None
                if isinstance(fraction, (int, float)) and not isinstance(fraction, bool) and 0 <= fraction <= 1 and math.isfinite(fraction):
                    remaining = fraction * 100
                reset = quota.get("resetTime")
                if isinstance(reset, str):
                    try:
                        if datetime.fromisoformat(reset.replace("Z", "+00:00")).tzinfo is None:
                            reset = None
                    except ValueError:
                        reset = None
                else:
                    reset = None
                if remaining is not None or reset is not None:
                    limits.append(SubscriptionLimit(name=model, model=model, remaining_percent=remaining,
                                                    used_percent=100 - remaining if remaining is not None else None,
                                                    reset_at=reset))
            return SubscriptionLimits(status="ok" if limits else "unavailable", plan=plan, limits=limits,
                                      checked_at=checked_at, message=None if limits else "Antigravity returned no usable native quotas")
        except Exception as exc:
            # Provider bodies and token/proxy exception strings must not reach the admin UI.
            return SubscriptionLimits(status="unavailable", plan=plan, checked_at=checked_at,
                                      message=f"Antigravity quota lookup failed ({type(exc).__name__})")

    async def validate_credentials(
        self,
        ctx: ModuleExecutionContext,
    ) -> Tuple[bool, str, int]:
        try:
            access_token, project_id = await self._get_valid_access_token(ctx)
            project_id, tier = await self._load_code_assist(ctx, access_token, project_id)
            models = await self.list_models(ctx)
            return True, f"Antigravity CLI authenticated ({tier or 'unknown tier'}, project: {project_id})", len(models)
        except RouterException as exc:
            return False, f"Antigravity validation failed (HTTP {exc.upstream_status or exc.status_code})", 0
        except Exception as exc:
            return False, f"Antigravity validation failed ({type(exc).__name__})", 0

    async def list_models(
        self,
        ctx: ModuleExecutionContext,
    ) -> List[DiscoveredModelData]:
        # One catalog for manifest seeding and handler discovery.
        catalog = json.loads(Path(__file__).with_name("manifest.json").read_text(encoding="utf-8"))["default_models"]
        return [
            DiscoveredModelData(
                provider_model_id=model["id"],
                display_name=model["name"],
                capabilities=model["capabilities"],
                context_length=model.get("context_length"),
                max_output_tokens=model.get("max_output_tokens"),
            )
            for model in catalog
        ]

    def _convert_messages_to_gemini(self, messages: List[ChatMessage]) -> List[Dict[str, Any]]:
        contents: List[Dict[str, Any]] = []
        system_texts: List[str] = []
        call_names: Dict[str, str] = {}

        for m in messages:
            if (m.cache_control is not None
                    or isinstance(m.content, list) and any(p.get("cache_control") is not None for p in m.content)
                    or any((c.extra_content or {}).get("anthropic", {}).get("cache_control") is not None for c in m.tool_calls or [])):
                raise RouterException("AGY cannot preserve explicit cache metadata", ErrorCategory.INVALID_REQUEST)
            role = (m.role or "user").lower()
            text = ("".join(p.get("text", "") for p in m.content if p.get("type") in ("text", "input_text", "output_text"))
                    if isinstance(m.content, list) else str(m.content or ""))
            if role in ("system", "developer"):
                if text:
                    system_texts.append(text)
                continue
            parts: List[Dict[str, Any]] = []
            if role in ("tool", "function"):
                if role == "tool" and not m.tool_call_id:
                    raise RouterException("Tool results require a non-empty tool_call_id", ErrorCategory.INVALID_REQUEST)
                name = call_names.get(m.tool_call_id or "") or m.name
                if not name or (m.tool_call_id and m.tool_call_id not in call_names):
                    raise RouterException("Tool result has no matching call or function name", ErrorCategory.INVALID_REQUEST)
                try:
                    result = json.loads(text)
                except (ValueError, TypeError):
                    result = text
                response = {"name": name, "response": result if isinstance(result, dict) else {"result": result}}
                if m.tool_call_id:
                    response["id"] = m.tool_call_id
                parts.append({"functionResponse": response})
            else:
                if text:
                    parts.append({"text": text})
                for call in m.tool_calls or []:
                    try:
                        args = json.loads(call.function.arguments)
                    except (ValueError, TypeError) as exc:
                        raise RouterException("Tool arguments must be a JSON object", ErrorCategory.INVALID_REQUEST) from exc
                    if not isinstance(args, dict):
                        raise RouterException("Tool arguments must be a JSON object", ErrorCategory.INVALID_REQUEST)
                    call_names[call.id] = call.function.name
                    part = {"functionCall": {"id": call.id, "name": call.function.name, "args": args}}
                    signature = ((call.extra_content or {}).get("google") or {}).get("thought_signature")
                    if signature:
                        part["thoughtSignature"] = signature
                    parts.append(part)
            native_role = "model" if role == "assistant" else "user"
            if parts:
                if contents and contents[-1]["role"] == native_role:
                    contents[-1]["parts"].extend(parts)
                else:
                    contents.append({"role": native_role, "parts": parts})

        # Inject system instructions into the first user message if present
        if system_texts:
            prefix = "System Instructions:\n" + "\n\n".join(system_texts) + "\n\nUser Question:\n"
            if contents and contents[0]["role"] == "user":
                parts = contents[0]["parts"]
                if "text" in parts[0]:
                    parts[0]["text"] = prefix + parts[0]["text"]
                else:
                    parts.insert(0, {"text": prefix})
            else:
                contents.insert(0, {"role": "user", "parts": [{"text": "\n\n".join(system_texts)}]})

        if not contents:
            contents.append({"role": "user", "parts": [{"text": "Hello"}]})

        return contents

    def _build_cloudcode_envelope(
        self,
        request: ChatCompletionRequest,
        project_id: str,
        model_name: str,
    ) -> Dict[str, Any]:
        contents = self._convert_messages_to_gemini(request.messages)
        clean_model = model_name
        if clean_model.startswith("agy_cli/"):
            clean_model = clean_model[8:]

        envelope: Dict[str, Any] = {
            "project": project_id,
            "model": clean_model,
            "requestId": str(uuid.uuid4()),
            "userAgent": "antigravity",
            "requestType": "agent",
            "request": {
                "contents": contents,
                "generationConfig": {
                    "temperature": request.temperature if request.temperature is not None else 0.7,
                    "maxOutputTokens": request.get_effective_max_tokens() or 8192,
                },
            },
        }
        if request.tools:
            declarations = []
            for tool in request.tools:
                if tool.get("cache_control") is not None:
                    raise RouterException("AGY cannot preserve explicit cache metadata", ErrorCategory.INVALID_REQUEST)
                function = tool.get("function", {})
                if tool.get("type") != "function" or not isinstance(function, dict) or not function.get("name"):
                    raise RouterException("AGY supports named function tools only", ErrorCategory.INVALID_REQUEST)
                declarations.append({key: function[key] for key in ("name", "description", "parameters") if key in function})
            envelope["request"]["tools"] = [{"functionDeclarations": declarations}]
        if request.tools or request.tool_choice is not None:
            choice = request.tool_choice or "auto"
            config: Dict[str, Any] = {}
            if isinstance(choice, dict):
                function = choice.get("function")
                name = function.get("name") if isinstance(function, dict) else None
                if choice.get("type") != "function" or not name or name not in [t["function"]["name"] for t in request.tools or []]:
                    raise RouterException("tool_choice must name a declared function", ErrorCategory.INVALID_REQUEST)
                config = {"mode": "ANY", "allowedFunctionNames": [name]}
            elif choice in ("auto", "none", "required"):
                config = {"mode": {"auto": "AUTO", "none": "NONE", "required": "ANY"}[choice]}
                if choice == "required" and not request.tools:
                    raise RouterException("Required tool_choice needs function tools", ErrorCategory.INVALID_REQUEST)
            else:
                raise RouterException("Unsupported tool_choice", ErrorCategory.INVALID_REQUEST)
            envelope["request"]["toolConfig"] = {"functionCallingConfig": config}
        return envelope

    async def chat_completions(
        self,
        request: ChatCompletionRequest,
        ctx: ModuleExecutionContext,
    ) -> ChatCompletionResponse:
        model_name = (request.model or ctx.model_id or "gemini-3.8-flash-low").removeprefix("agy_cli/")
        return await collect_chat_completion(self.stream_chat(request, ctx), model_name)

    async def stream_chat(
        self,
        request: ChatCompletionRequest,
        ctx: ModuleExecutionContext,
    ) -> AsyncGenerator[str, None]:
        model = (request.model or ctx.model_id or "gemini-3.8-flash-low").removeprefix("agy_cli/")
        # Validate the native payload before auth or local credential discovery.
        envelope = self._build_cloudcode_envelope(request, "", model)
        try:
            access_token, project_id = await self._get_valid_access_token(ctx)
            if not project_id:
                project_id, _ = await self._load_code_assist(ctx, access_token, project_id)
        except RouterException:
            raise
        except ValueError as exc:
            raise RouterException(str(exc), ErrorCategory.AUTH_ERROR) from exc
        except Exception as exc:
            raise normalize_upstream_error(exception=exc) from exc
        headers = self._build_cloudcode_headers(access_token)
        envelope["project"] = project_id
        chunk_id = f"chatcmpl-agy-{uuid.uuid4().hex[:12]}"
        created = int(time.time())
        call_count = 0
        finish_reason = "stop"
        usage = None
        emitted = False

        def chunk(delta, reason=None):
            result = {
                "id": chunk_id, "object": "chat.completion.chunk", "created": created, "model": model,
                "choices": [{"index": 0, "delta": delta, "finish_reason": reason}],
            }
            if reason is not None and usage is not None:
                result["usage"] = usage
            return f"data: {json.dumps(result, ensure_ascii=False)}\n\n"

        async def sse_data(resp):
            lines = []
            async for line in resp.aiter_lines():
                if line.startswith("data:"):
                    value = line[5:]
                    lines.append(value[1:] if value.startswith(" ") else value)
                elif not line and lines:
                    yield "\n".join(lines)
                    lines.clear()
            if lines:
                yield "\n".join(lines)

        async with self.create_http_client(ctx) as client:
            last_err = RouterException("No Cloud Code endpoint available", ErrorCategory.UPSTREAM_5XX)
            for base_url in CLOUDCODE_BASE_URLS:
                saw_candidate = False
                usage = None
                finish_reason = "stop"
                url = f"{base_url}/v1internal:streamGenerateContent?alt=sse"
                try:
                    async with client.stream("POST", url, headers=headers, json=envelope, timeout=ctx.timeout or 120.0) as resp:
                        if resp.status_code != 200:
                            body = (await resp.aread()).decode("utf-8", errors="replace")
                            try:
                                retry_after = float(resp.headers["Retry-After"])
                            except (KeyError, ValueError):
                                retry_after = None
                            raise normalize_upstream_error(status_code=resp.status_code, response_body=body, retry_after=retry_after)

                        async for raw_data in sse_data(resp):
                            if raw_data == "[DONE]":
                                break
                            if not raw_data:
                                continue
                            try:
                                payload = json.loads(raw_data)
                            except ValueError as exc:
                                raise RouterException("Invalid Cloud Code SSE JSON", ErrorCategory.UPSTREAM_5XX) from exc
                            if not isinstance(payload, dict):
                                raise RouterException("Invalid Cloud Code SSE payload", ErrorCategory.UPSTREAM_5XX)
                            payload = payload if payload.get("error") else payload.get("response", payload)
                            if not isinstance(payload, dict):
                                raise RouterException("Invalid Cloud Code response", ErrorCategory.UPSTREAM_5XX)
                            if payload.get("error"):
                                error = payload["error"]
                                code = error.get("code", 502) if isinstance(error, dict) else 502
                                raise normalize_upstream_error(status_code=code, response_body=payload)
                            metadata = payload.get("usageMetadata")
                            if metadata:
                                usage = {"prompt_tokens": metadata.get("promptTokenCount", 0),
                                         "completion_tokens": metadata.get("candidatesTokenCount", 0),
                                         "total_tokens": metadata.get("totalTokenCount", 0)}
                                for native, detail, key in (
                                    ("cachedContentTokenCount", "prompt_tokens_details", "cached_tokens"),
                                    ("thoughtsTokenCount", "completion_tokens_details", "reasoning_tokens"),
                                ):
                                    value = metadata.get(native)
                                    if type(value) is int and value >= 0:
                                        usage[detail] = {key: value}
                            candidates = payload.get("candidates", [])
                            if not candidates:
                                continue
                            saw_candidate = True
                            candidate = candidates[0]
                            native_finish = candidate.get("finishReason")
                            if native_finish:
                                finish_reason = {"STOP": "stop", "MAX_TOKENS": "length", "SAFETY": "content_filter", "RECITATION": "content_filter", "BLOCKLIST": "content_filter", "PROHIBITED_CONTENT": "content_filter"}.get(native_finish, "stop")
                            delta: Dict[str, Any] = {}
                            for part in candidate.get("content", {}).get("parts", []):
                                if "text" in part:
                                    key = "reasoning_content" if part.get("thought") else "content"
                                    delta[key] = delta.get(key, "") + part["text"]
                                if "functionCall" in part:
                                    call = part["functionCall"]
                                    if not call.get("name") or not isinstance(call.get("args", {}), dict):
                                        raise RouterException("Invalid Cloud Code function call", ErrorCategory.UPSTREAM_5XX)
                                    delta.setdefault("tool_calls", []).append({
                                        "index": call_count, "id": call.get("id") or f"call_{uuid.uuid4().hex[:12]}", "type": "function",
                                        "function": {"name": call["name"], "arguments": json.dumps(call.get("args", {}), ensure_ascii=False)},
                                    })
                                    if part.get("thoughtSignature"):
                                        delta["tool_calls"][-1]["extra_content"] = {"google": {"thought_signature": part["thoughtSignature"]}}
                                    call_count += 1
                            if delta:
                                emitted = True
                                yield chunk(delta)
                        if not saw_candidate:
                            raise RouterException("Cloud Code stream returned no candidates", ErrorCategory.UPSTREAM_5XX)
                        yield chunk({}, "tool_calls" if call_count and finish_reason == "stop" else finish_reason)
                        yield "data: [DONE]\n\n"
                        return
                except Exception as exc:
                    last_err = exc if isinstance(exc, RouterException) else normalize_upstream_error(exception=exc)
                    # Never replay a partially emitted completion against another endpoint.
                    if emitted or last_err.category not in (ErrorCategory.MODEL_NOT_FOUND, ErrorCategory.UPSTREAM_5XX, ErrorCategory.NETWORK_ERROR, ErrorCategory.TIMEOUT):
                        raise last_err from exc
            raise last_err
