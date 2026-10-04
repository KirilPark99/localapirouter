import os
import json
import time
import uuid
import base64
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

logger = logging.getLogger("app.modules.codex_cli")

CODEX_TOKEN_URL = "https://auth.openai.com/oauth/token"
CODEX_RESPONSES_URL = "https://chatgpt.com/backend-api/codex/responses"
CODEX_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
CODEX_CLIENT_VERSION = "0.160.0"
CODEX_USER_AGENT = f"codex-cli/{CODEX_CLIENT_VERSION} (linux; x86_64)"

LOCAL_AUTH_PATHS = [
    Path.home() / ".codex" / "auth.json",
    Path.home() / ".config" / "codex" / "auth.json",
]


def _decode_jwt_payload(jwt_token: str) -> Dict[str, Any]:
    try:
        parts = jwt_token.split(".")
        if len(parts) < 2:
            return {}
        payload_b64 = parts[1]
        # Pad base64
        payload_b64 += "=" * ((4 - len(payload_b64) % 4) % 4)
        decoded_bytes = base64.urlsafe_b64decode(payload_b64.encode("utf-8"))
        return json.loads(decoded_bytes.decode("utf-8", errors="ignore"))
    except Exception:
        return {}


def _clean_str(val: Any) -> str:
    if val is None:
        return ""
    return str(val).strip()


def _get_str(d: Dict[str, Any], key: str, default: str = "") -> str:
    val = d.get(key)
    if val is None:
        return default
    return str(val).strip()


class CodexCliAdapter(BaseModuleAdapter):
    """
    Adapter for OpenAI Codex CLI (`codex`).
    Supports local token auto-discovery from ~/.codex/auth.json,
    automatic token refresh against auth.openai.com,
    and routing to ChatGPT Responses API.
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

        access_token = _get_str(creds, "access_token")
        refresh_token = _get_str(creds, "refresh_token")
        account_id = _get_str(creds, "account_id")
        auth_json_str = _get_str(creds, "auth_json")

        if auth_json_str:
            try:
                parsed = json.loads(auth_json_str)
                tokens = parsed.get("tokens") if isinstance(parsed.get("tokens"), dict) else parsed
                return {
                    "access_token": _clean_str(tokens.get("access_token")) or access_token,
                    "refresh_token": _clean_str(tokens.get("refresh_token")) or refresh_token,
                    "id_token": _clean_str(tokens.get("id_token")),
                    "account_id": _clean_str(tokens.get("account_id")) or account_id,
                }
            except Exception as e:
                logger.warning(f"Failed to parse pasted auth_json for codex: {e}")

        if access_token or refresh_token:
            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "account_id": account_id,
            }

        if auto_detect:
            local_path = self._find_local_auth_file()
            if local_path:
                try:
                    with open(local_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    tokens = data.get("tokens") if isinstance(data.get("tokens"), dict) else data
                    return {
                        "access_token": _clean_str(tokens.get("access_token")),
                        "refresh_token": _clean_str(tokens.get("refresh_token")),
                        "id_token": _clean_str(tokens.get("id_token")),
                        "account_id": account_id or _clean_str(tokens.get("account_id")),
                    }
                except Exception as e:
                    logger.warning(f"Failed to read local codex auth file at {local_path}: {e}")

        return {}

    async def _get_valid_access_token(self, ctx: ModuleExecutionContext) -> Tuple[str, str]:
        """
        Returns (access_token, account_id), auto-refreshing via OpenAI OAuth if needed.
        """
        raw = self._resolve_raw_tokens(ctx)
        refresh_token = _clean_str(raw.get("refresh_token"))
        access_token = _clean_str(raw.get("access_token"))
        account_id = _clean_str(raw.get("account_id"))
        id_token = _clean_str(raw.get("id_token"))

        # Extract account_id from id_token if not set
        if not account_id and id_token:
            claims = _decode_jwt_payload(id_token)
            auth_info = claims.get("https://api.openai.com/auth", {})
            account_id = auth_info.get("chatgpt_account_id") or ""
            if not account_id:
                orgs = auth_info.get("organizations", [])
                if orgs and isinstance(orgs, list) and isinstance(orgs[0], dict):
                    account_id = orgs[0].get("id", "")

        cache_key = refresh_token or access_token
        cached = self._token_cache.get(cache_key)
        now = time.time()
        if cached and cached.get("expires_at", 0) > now + 60:
            return cached["access_token"], account_id or cached.get("account_id", "")

        # Refresh if we have refresh_token
        if refresh_token:
            async with self.create_http_client(ctx) as client:
                try:
                    resp = await client.post(
                        CODEX_TOKEN_URL,
                        data={
                            "client_id": CODEX_CLIENT_ID,
                            "grant_type": "refresh_token",
                            "refresh_token": refresh_token,
                        },
                        headers={
                            "Content-Type": "application/x-www-form-urlencoded",
                            "User-Agent": CODEX_USER_AGENT,
                        },
                        timeout=15.0,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        new_access = data.get("access_token")
                        new_id_token = data.get("id_token")
                        expires_in = data.get("expires_in", 3600)

                        if not account_id and new_id_token:
                            claims = _decode_jwt_payload(new_id_token)
                            auth_info = claims.get("https://api.openai.com/auth", {})
                            account_id = auth_info.get("chatgpt_account_id") or ""

                        if new_access:
                            self._token_cache[cache_key] = {
                                "access_token": new_access,
                                "account_id": account_id,
                                "expires_at": now + expires_in,
                            }
                            return new_access, account_id
                    else:
                        logger.warning(f"OpenAI OAuth refresh returned HTTP {resp.status_code}: {resp.text[:200]}")
                except Exception as e:
                    logger.warning(f"OpenAI OAuth refresh failed: {e}")

        if access_token:
            return access_token, account_id

        raise ValueError("No OpenAI Codex CLI token found. Log in via `codex login` or configure credentials.")

    def _build_headers(self, access_token: str, account_id: str) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Version": CODEX_CLIENT_VERSION,
            "User-Agent": CODEX_USER_AGENT,
            "Openai-Beta": "responses=experimental",
            "Content-Type": "application/json",
            "Accept": "text/event-stream, application/json",
        }
        if account_id:
            headers["ChatGPT-Account-Id"] = account_id
        return headers

    async def validate_credentials(
        self,
        ctx: ModuleExecutionContext,
    ) -> Tuple[bool, str, int]:
        try:
            access_token, account_id = await self._get_valid_access_token(ctx)
            if not access_token:
                return False, "Failed to resolve valid OpenAI Codex access token", 0

            # Test by issuing a minimal dry request or ping to responses endpoint
            headers = self._build_headers(access_token, account_id)
            body = {
                "model": "gpt-6.1-sol",
                "input": [{"role": "user", "content": [{"type": "input_text", "text": "ping"}]}],
                "stream": True,
                "store": False,
            }

            async with self.create_http_client(ctx) as client:
                async with client.stream(
                    "POST",
                    CODEX_RESPONSES_URL,
                    headers=headers,
                    json=body,
                    timeout=15.0,
                ) as resp:
                    if resp.status_code in (401, 403):
                        err_text = await resp.aread()
                        return False, f"Codex auth rejected (HTTP {resp.status_code}): {err_text.decode('utf-8', errors='ignore')[:200]}", 0
                    if resp.status_code == 200:
                        models = await self.list_models(ctx)
                        return (
                            True,
                            f"OpenAI Codex CLI authorized (Account ID: {account_id or 'default'})",
                            len(models),
                        )
                    err_text = await resp.aread()
                    return False, f"Codex Responses API returned HTTP {resp.status_code}: {err_text.decode('utf-8', errors='ignore')[:200]}", 0

        except Exception as e:
            return False, f"Codex validation error: {str(e)}", 0

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

    def _convert_messages_to_responses_input(self, messages: List[ChatMessage]) -> List[Dict[str, Any]]:
        return messages_to_input(messages)

    async def chat_completions(
        self,
        request: ChatCompletionRequest,
        ctx: ModuleExecutionContext,
    ) -> ChatCompletionResponse:
        model = request.model or ctx.model_id or "gpt-6.1-sol"
        model = model.removeprefix("codex_cli/")
        return await collect_chat_completion(self.stream_chat(request, ctx), model)

    async def stream_chat(
        self,
        request: ChatCompletionRequest,
        ctx: ModuleExecutionContext,
    ) -> AsyncGenerator[str, None]:
        access_token, account_id = await self._get_valid_access_token(ctx)
        model = request.model or ctx.model_id or "gpt-6.1-sol"
        if model.startswith("codex_cli/"):
            model = model[10:]

        headers = self._build_headers(access_token, account_id)
        input_items = self._convert_messages_to_responses_input(request.messages)

        body = {
            "model": model,
            "input": input_items,
            "stream": True,
            "store": False,
        }

        body.update(tool_options(request))

        async with self.create_http_client(ctx) as client:
            async with client.stream(
                "POST",
                CODEX_RESPONSES_URL,
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

                chunk_id = f"chatcmpl-codex-{uuid.uuid4().hex[:12]}"
                created = int(time.time())

                async for chunk in responses_to_chat(resp.aiter_lines(), model, chunk_id, created):
                    yield chunk
