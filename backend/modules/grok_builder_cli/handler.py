import os
import json
import time
import uuid
import logging
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

import httpx
from app.modules.base import BaseModuleAdapter, ModuleExecutionContext, collect_chat_completion
from app.modules.responses import messages_to_input, tool_options, responses_to_chat
from app.schemas.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
)
from app.adapters.base import DiscoveredModelData
from app.core.errors import normalize_upstream_error

logger = logging.getLogger("app.modules.grok_builder_cli")

GROK_TOKEN_URL = "https://auth.x.ai/oauth2/token"
GROK_PROXY_BASE_URL = "https://cli-chat-proxy.grok.com/v1"
GROK_RESPONSES_URL = f"{GROK_PROXY_BASE_URL}/responses"
GROK_MODELS_URL = f"{GROK_PROXY_BASE_URL}/models"

# Public Grok CLI OAuth Client ID
GROK_CLIENT_ID = "b1a00492-073a-47ea-816f-4c329264a828"
GROK_CLIENT_VERSION = "1.0.13"
GROK_USER_AGENT = f"grok-shell/{GROK_CLIENT_VERSION} (linux; x86_64)"

LOCAL_AUTH_PATHS = [
    Path.home() / ".grok" / "auth.json",
    Path.home() / ".config" / "grok" / "auth.json",
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


class GrokBuilderCliAdapter(BaseModuleAdapter):
    """
    Adapter for xAI Grok Builder CLI (`grok`).
    Supports local token auto-discovery from ~/.grok/auth.json,
    automatic token refresh via auth.x.ai, and live model discovery.
    """

    def __init__(self):
        super().__init__()
        self._token_cache: Dict[str, Dict[str, Any]] = {}

    def _find_local_auth_file(self) -> Optional[Path]:
        for p in LOCAL_AUTH_PATHS:
            if p.exists() and p.is_file():
                return p
        return None

    def _resolve_raw_tokens(self, ctx: ModuleExecutionContext) -> Dict[str, Any]:
        creds = ctx.credentials or {}
        auto_detect_raw = creds.get("auto_detect_local")
        if auto_detect_raw is None or auto_detect_raw == "":
            auto_detect = True
        elif isinstance(auto_detect_raw, bool):
            auto_detect = auto_detect_raw
        else:
            auto_detect = str(auto_detect_raw).strip().lower() in ("true", "1", "yes")

        access_token = _get_str(creds, "access_token") or _get_str(creds, "key")
        refresh_token = _get_str(creds, "refresh_token")
        auth_json_str = _get_str(creds, "auth_json")

        if auth_json_str:
            try:
                parsed = json.loads(auth_json_str)
                # Find entry inside object
                for entry in parsed.values():
                    if isinstance(entry, dict) and ("key" in entry or "access_token" in entry):
                        return {
                            "access_token": _clean_str(entry.get("key") or entry.get("access_token")) or access_token,
                            "refresh_token": _clean_str(entry.get("refresh_token")) or refresh_token,
                            "email": _clean_str(entry.get("email")),
                            "user_id": _clean_str(entry.get("user_id")),
                        }
            except Exception as e:
                logger.warning(f"Failed to parse pasted auth_json for grok: {e}")

        if access_token or refresh_token:
            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "email": _get_str(creds, "email"),
            }

        if auto_detect:
            local_path = self._find_local_auth_file()
            if local_path:
                try:
                    with open(local_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    for entry in data.values():
                        if isinstance(entry, dict) and ("key" in entry or "access_token" in entry):
                            return {
                                "access_token": _clean_str(entry.get("key") or entry.get("access_token")),
                                "refresh_token": _clean_str(entry.get("refresh_token")),
                                "email": _clean_str(entry.get("email")),
                                "user_id": _clean_str(entry.get("user_id")),
                            }
                except Exception as e:
                    logger.warning(f"Failed to read local grok auth file at {local_path}: {e}")

        return {}

    async def _get_valid_access_token(self, ctx: ModuleExecutionContext) -> Tuple[str, str]:
        """
        Returns (access_token, email), auto-refreshing via xAI OAuth if needed.
        """
        raw = self._resolve_raw_tokens(ctx)
        refresh_token = _clean_str(raw.get("refresh_token"))
        access_token = _clean_str(raw.get("access_token"))
        email = _clean_str(raw.get("email"))

        cache_key = refresh_token or access_token
        cached = self._token_cache.get(cache_key)
        now = time.time()
        if cached and cached.get("expires_at", 0) > now + 60:
            return cached["access_token"], email or cached.get("email", "")

        if refresh_token:
            async with self.create_http_client(ctx) as client:
                try:
                    resp = await client.post(
                        GROK_TOKEN_URL,
                        data={
                            "grant_type": "refresh_token",
                            "client_id": GROK_CLIENT_ID,
                            "refresh_token": refresh_token,
                        },
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                        timeout=15.0,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        new_access = data.get("access_token")
                        expires_in = data.get("expires_in", 21600)
                        if new_access:
                            self._token_cache[cache_key] = {
                                "access_token": new_access,
                                "email": email,
                                "expires_at": now + expires_in,
                            }
                            return new_access, email
                    else:
                        logger.warning(f"xAI OAuth refresh returned HTTP {resp.status_code}: {resp.text[:200]}")
                except Exception as e:
                    logger.warning(f"xAI OAuth refresh failed: {e}")

        if access_token:
            return access_token, email

        raise ValueError("No xAI Grok Builder CLI token found. Log in via `grok login` or configure credentials.")

    def _build_headers(self, access_token: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": GROK_USER_AGENT,
            "x-grok-client-version": GROK_CLIENT_VERSION,
            "x-grok-client-identifier": "grok-shell",
            "x-grok-client-mode": "headless",
            "X-XAI-Token-Auth": "xai-grok-cli",
            "Content-Type": "application/json",
            "Accept": "text/event-stream, application/json",
        }

    async def validate_credentials(
        self,
        ctx: ModuleExecutionContext,
    ) -> Tuple[bool, str, int]:
        try:
            access_token, email = await self._get_valid_access_token(ctx)
            if not access_token:
                return False, "Failed to resolve valid xAI Grok token", 0

            headers = self._build_headers(access_token)
            headers["Accept"] = "application/json"

            async with self.create_http_client(ctx) as client:
                resp = await client.get(
                    GROK_MODELS_URL,
                    headers=headers,
                    timeout=15.0,
                )
                if resp.status_code == 200:
                    models = await self.list_models(ctx)
                    return (
                        True,
                        f"xAI Grok Builder CLI authenticated: {email or 'xAI Account'}",
                        len(models),
                    )
                elif resp.status_code in (401, 403):
                    err_text = resp.text[:200]
                    return False, f"Grok authorization rejected (HTTP {resp.status_code}): {err_text}", 0
                else:
                    return False, f"Grok proxy returned HTTP {resp.status_code}: {resp.text[:200]}", 0

        except Exception as e:
            return False, f"Grok validation error: {str(e)}", 0

    async def list_models(
        self,
        ctx: ModuleExecutionContext,
    ) -> List[DiscoveredModelData]:
        # Try dynamic discovery first
        try:
            access_token, _ = await self._get_valid_access_token(ctx)
            if access_token:
                headers = self._build_headers(access_token)
                headers["Accept"] = "application/json"
                async with self.create_http_client(ctx) as client:
                    resp = await client.get(GROK_MODELS_URL, headers=headers, timeout=8.0)
                    if resp.status_code == 200:
                        data = resp.json().get("data", [])
                        discovered = []
                        for m in data:
                            m_id = m.get("id") or m.get("model")
                            m_name = m.get("name") or m_id
                            ctx_win = m.get("context_window", 256000)
                            discovered.append(
                                DiscoveredModelData(
                                    provider_model_id=m_id,
                                    display_name=f"{m_name} (Grok Build)",
                                    capabilities={
                                        "chat": True,
                                        "streaming": True,
                                        "vision": True,
                                        "tools": True,
                                        "reasoning": True,
                                    },
                                    context_length=ctx_win,
                                    max_output_tokens=128000,
                                )
                            )
                        if discovered:
                            return discovered
        except Exception as e:
            logger.debug(f"Dynamic Grok model listing failed, falling back to static catalog: {e}")

        # Fallback static catalog
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

    def _convert_messages_to_responses_input(self, messages: List[ChatMessage]) -> List[Dict[str, Any]]:
        return messages_to_input(messages)

    async def chat_completions(
        self,
        request: ChatCompletionRequest,
        ctx: ModuleExecutionContext,
    ) -> ChatCompletionResponse:
        model = request.model or ctx.model_id or "grok-4.7"
        model = model.removeprefix("grok_builder_cli/")
        return await collect_chat_completion(self.stream_chat(request, ctx), model)

    async def stream_chat(
        self,
        request: ChatCompletionRequest,
        ctx: ModuleExecutionContext,
    ) -> AsyncGenerator[str, None]:
        access_token, _ = await self._get_valid_access_token(ctx)
        model = request.model or ctx.model_id or "grok-4.7"
        if model.startswith("grok_builder_cli/"):
            model = model[17:]

        headers = self._build_headers(access_token)
        input_items = self._convert_messages_to_responses_input(request.messages)

        body = {
            "model": model,
            "input": input_items,
            "stream": True,
            "store": False,
            "include": ["reasoning.encrypted_content"],
        }

        body.update(tool_options(request))

        async with self.create_http_client(ctx) as client:
            async with client.stream(
                "POST",
                GROK_RESPONSES_URL,
                headers=headers,
                json=body,
                timeout=ctx.timeout or 120.0,
            ) as resp:
                if resp.status_code != 200:
                    err_body = await resp.aread()
                    raise normalize_upstream_error(
                        status_code=resp.status_code,
                        response_body=err_body.decode("utf-8", errors="replace"),
                    )

                chunk_id = f"chatcmpl-grok-{uuid.uuid4().hex[:12]}"
                created = int(time.time())

                async for chunk in responses_to_chat(resp.aiter_lines(), model, chunk_id, created):
                    yield chunk
