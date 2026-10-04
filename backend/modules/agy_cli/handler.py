import json
import time
import uuid
import logging
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

import httpx
from app.core.config import settings
from app.modules.base import BaseModuleAdapter, ModuleExecutionContext
from app.schemas.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatMessage,
    UsageInfo,
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
        # In-memory cache for refreshed access tokens: {cache_key: {"access_token": str, "expires_at": float}}
        self._token_cache: Dict[str, Dict[str, Any]] = {}

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
        auto_detect_raw = creds.get("auto_detect_local")
        if auto_detect_raw is None or auto_detect_raw == "":
            auto_detect = True
        elif isinstance(auto_detect_raw, bool):
            auto_detect = auto_detect_raw
        else:
            auto_detect = str(auto_detect_raw).strip().lower() in ("true", "1", "yes")

        # 1. Direct credentials
        access_token = _get_str(creds, "access_token")
        refresh_token = _get_str(creds, "refresh_token")
        project_id = _get_str(creds, "project_id")
        auth_json_str = _get_str(creds, "auth_json")

        if auth_json_str:
            try:
                parsed = json.loads(auth_json_str)
                token_inner = parsed.get("token") if isinstance(parsed.get("token"), dict) else parsed
                return {
                    "access_token": _clean_str(token_inner.get("access_token")) or access_token,
                    "refresh_token": _clean_str(token_inner.get("refresh_token")) or refresh_token,
                    "project_id": project_id or _clean_str(parsed.get("project_id")) or _clean_str(token_inner.get("project_id")),
                    "expiry": _clean_str(token_inner.get("expiry") or token_inner.get("expires_at")),
                }
            except Exception as e:
                logger.warning(f"Failed to parse pasted auth_json: {e}")

        if access_token or refresh_token:
            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "project_id": project_id,
            }

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
                        "expiry": _clean_str(token_inner.get("expiry") or token_inner.get("expires_at")),
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
        project_id = _clean_str(raw.get("project_id")) or "aicode-consumers"

        cache_key = refresh_token or access_token
        cached = self._token_cache.get(cache_key)
        now = time.time()
        if cached and cached.get("expires_at", 0) > now + 60:
            return cached["access_token"], project_id

        # If we have refresh_token, attempt refresh
        if refresh_token and AGY_CLIENT_ID and AGY_CLIENT_SECRET:
            async with self.create_http_client(ctx) as client:
                try:
                    resp = await client.post(
                        GOOGLE_OAUTH_TOKEN_URL,
                        data={
                            "client_id": AGY_CLIENT_ID,
                            "client_secret": AGY_CLIENT_SECRET,
                            "grant_type": "refresh_token",
                            "refresh_token": refresh_token,
                        },
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                        timeout=15.0,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        new_access = data.get("access_token")
                        expires_in = data.get("expires_in", 3600)
                        if new_access:
                            self._token_cache[cache_key] = {
                                "access_token": new_access,
                                "expires_at": now + expires_in,
                            }
                            return new_access, project_id
                    else:
                        logger.warning(f"Google OAuth refresh returned HTTP {resp.status_code}: {resp.text[:200]}")
                except Exception as e:
                    logger.warning(f"Google OAuth refresh failed: {e}")

        if access_token:
            return access_token, project_id

        raise ValueError("No Antigravity CLI token available. Please log in with `agy login` or configure credentials.")

    def _build_cloudcode_headers(self, access_token: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "User-Agent": "antigravity/cli/1.0.0 (aidev_client; os_type=darwin; arch=arm64; auth_method=consumer)",
            "Accept": "application/json, text/event-stream",
        }

    async def validate_credentials(
        self,
        ctx: ModuleExecutionContext,
    ) -> Tuple[bool, str, int]:
        try:
            access_token, project_id = await self._get_valid_access_token(ctx)
            if not access_token:
                return False, "Failed to resolve valid access token", 0

            # Test identity via userinfo
            email = None
            async with self.create_http_client(ctx) as client:
                resp = await client.get(
                    GOOGLE_USERINFO_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    email = resp.json().get("email")

                # Test Code Assist bootstrap / project discovery
                headers = self._build_cloudcode_headers(access_token)
                res = await client.post(
                    f"{CLOUDCODE_BASE_URLS[0]}/v1internal:loadCodeAssist",
                    headers=headers,
                    json={"metadata": {"ideType": "ANTIGRAVITY"}},
                    timeout=10.0,
                )
                if res.status_code == 200:
                    ca_data = res.json()
                    discovered_proj = ca_data.get("cloudaicompanionProject")
                    tier = ca_data.get("currentTier", {}).get("name", "Antigravity")
                    if discovered_proj and not ctx.credentials.get("project_id"):
                        project_id = discovered_proj
                    models = await self.list_models(ctx)
                    return (
                        True,
                        f"Antigravity CLI authenticated: {email or 'Google Account'} ({tier}, project: {project_id})",
                        len(models),
                    )
                elif resp.status_code == 200:
                    models = await self.list_models(ctx)
                    return True, f"Google OAuth valid for {email}, Cloud Code project: {project_id}", len(models)
                else:
                    return False, f"Cloud Code responded with HTTP {res.status_code}: {res.text[:200]}", 0

        except Exception as e:
            return False, f"Antigravity validation error: {str(e)}", 0

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

        for m in messages:
            role = (m.role or "user").lower()
            text = str(m.content or "")
            if role == "system":
                if text:
                    system_texts.append(text)
            elif role in ("assistant", "model"):
                contents.append({"role": "model", "parts": [{"text": text}]})
            else:
                contents.append({"role": "user", "parts": [{"text": text}]})

        # Inject system instructions into the first user message if present
        if system_texts:
            prefix = "System Instructions:\n" + "\n\n".join(system_texts) + "\n\nUser Question:\n"
            if contents and contents[0]["role"] == "user":
                orig_text = contents[0]["parts"][0].get("text", "")
                contents[0]["parts"][0]["text"] = prefix + orig_text
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
                    "maxOutputTokens": request.max_tokens or 8192,
                },
            },
        }
        return envelope

    async def chat_completions(
        self,
        request: ChatCompletionRequest,
        ctx: ModuleExecutionContext,
    ) -> ChatCompletionResponse:
        full_content = ""
        model_name = request.model or ctx.model_id or "gemini-3.8-flash-low"
        if model_name.startswith("agy_cli/"):
            model_name = model_name[8:]

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

        return ChatCompletionResponse(
            id=f"chatcmpl-agy-{uuid.uuid4().hex[:12]}",
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
        access_token, project_id = await self._get_valid_access_token(ctx)
        model = request.model or ctx.model_id or "gemini-3.8-flash-low"
        headers = self._build_cloudcode_headers(access_token)
        envelope = self._build_cloudcode_envelope(request, project_id, model)

        async with self.create_http_client(ctx) as client:
            last_err = None
            for base_url in CLOUDCODE_BASE_URLS:
                url = f"{base_url}/v1internal:streamGenerateContent?alt=sse"
                try:
                    async with client.stream(
                        "POST",
                        url,
                        headers=headers,
                        json=envelope,
                        timeout=ctx.timeout or 120.0,
                    ) as resp:
                        if resp.status_code == 429:
                            err_text = await resp.aread()
                            raise RuntimeError(
                                f"Antigravity Quota/Resource Exhausted (HTTP 429). Google Cloud Code requires active quota or a custom GCP Project ID: {err_text.decode('utf-8', errors='ignore')[:200]}"
                            )
                        if resp.status_code != 200:
                            err_text = await resp.aread()
                            last_err = f"HTTP {resp.status_code}: {err_text.decode('utf-8', errors='ignore')[:300]}"
                            continue

                        chunk_id = f"chatcmpl-agy-{uuid.uuid4().hex[:12]}"
                        created = int(time.time())

                        async for line in resp.aiter_lines():
                            if not line or not line.startswith("data: "):
                                continue
                            raw_data = line[6:].strip()
                            if not raw_data:
                                continue
                            try:
                                payload = json.loads(raw_data)
                                candidates = (
                                    payload.get("response", {}).get("candidates")
                                    or payload.get("candidates")
                                    or []
                                )
                                if not candidates:
                                    continue
                                parts = candidates[0].get("content", {}).get("parts", [])
                                text_piece = "".join([p.get("text", "") for p in parts if "text" in p])
                                if text_piece:
                                    openai_chunk = {
                                        "id": chunk_id,
                                        "object": "chat.completion.chunk",
                                        "created": created,
                                        "model": model,
                                        "choices": [
                                            {
                                                "index": 0,
                                                "delta": {"content": text_piece},
                                                "finish_reason": None,
                                            }
                                        ],
                                    }
                                    yield f"data: {json.dumps(openai_chunk, ensure_ascii=False)}\n\n"
                            except Exception:
                                continue

                        yield "data: [DONE]\n\n"
                        return

                except Exception as e:
                    if "429" in str(e):
                        raise
                    last_err = str(e)

            raise RuntimeError(f"Antigravity Cloud Code streaming failed across endpoints: {last_err}")
