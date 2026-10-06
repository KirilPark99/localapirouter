import os
import json
import time
import uuid
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

logger = logging.getLogger("app.modules.qoder")

DEFAULT_QODER_BASE = "https://api.qoder.com/v1"
DASHSCOPE_COMPAT_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"


class QoderAdapter(BaseModuleAdapter):
    """
    Adapter for Qoder Cloud AI.
    OpenAI-compatible endpoints with support for custom API base and Qoder error unwrap.
    """

    def _get_base_url(self, ctx: ModuleExecutionContext) -> str:
        custom = ctx.credentials.get("api_base") or ctx.extra_config.get("api_base")
        if custom and str(custom).strip():
            url = str(custom).strip().rstrip("/")
            if not url.startswith("http"):
                url = f"https://{url}"
            return url
        return DEFAULT_QODER_BASE

    def _get_token(self, ctx: ModuleExecutionContext) -> str:
        token = (
            ctx.credentials.get("api_key")
            or ctx.credentials.get("apiKey")
            or ctx.credentials.get("access_token")
            or ctx.credentials.get("token")
            or ""
        )
        return str(token).strip()

    def _build_headers(self, ctx: ModuleExecutionContext) -> Dict[str, str]:
        token = self._get_token(ctx)
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Qoder-Client/1.0",
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
            return False, "Missing Qoder API Key or Token", 0

        base_url = self._get_base_url(ctx)
        headers = self._build_headers(ctx)

        try:
            async with self.create_http_client(ctx) as client:
                # First try GET /models
                resp = await client.get(f"{base_url}/models", headers=headers, timeout=10.0)
                if resp.status_code == 200:
                    models = await self.list_models(ctx)
                    return True, "Qoder API credentials are valid", len(models)
                elif resp.status_code in (401, 403):
                    return False, f"Authentication failed: HTTP {resp.status_code}", 0

                # Try fallback minimal completion test
                payload = {
                    "model": "qwen3.8-max-preview",
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 1,
                }
                resp2 = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=15.0)
                if resp2.status_code in (200, 429):
                    models = await self.list_models(ctx)
                    return True, "Qoder API is authorized", len(models)
                elif resp2.status_code in (401, 403):
                    return False, f"Authentication failed: HTTP {resp2.status_code}", 0
                else:
                    return False, f"Qoder API returned HTTP {resp2.status_code}", 0
        except Exception as e:
            return False, f"Connection failed: {str(e)}", 0

    async def list_models(
        self,
        ctx: ModuleExecutionContext,
    ) -> List[DiscoveredModelData]:
        base_url = self._get_base_url(ctx)
        headers = self._build_headers(ctx)

        try:
            async with self.create_http_client(ctx) as client:
                resp = await client.get(f"{base_url}/models", headers=headers, timeout=10.0)
                if resp.status_code == 200:
                    data = resp.json()
                    models_list = data.get("data", [])
                    if isinstance(models_list, list) and models_list:
                        discovered = []
                        for m in models_list:
                            m_id = m.get("id")
                            if m_id:
                                discovered.append(
                                    DiscoveredModelData(
                                        provider_model_id=m_id,
                                        display_name=m.get("name") or m_id,
                                        capabilities={"chat": True, "streaming": True, "vision": True, "tools": True, "reasoning": True},
                                        context_length=1000000,
                                        max_output_tokens=16384,
                                    )
                                )
                        if discovered:
                            return discovered
        except Exception:
            pass

        # Static fallback models
        catalog = [
            ("qwen3.8-max-preview", "Qwen3.8 Max Preview", True, True, True),
            ("qwen3.7-max", "Qwen3.7 Max", True, True, False),
            ("qwen3.7-plus", "Qwen3.7 Plus", True, True, False),
            ("kimi-k3", "Kimi K3", True, True, False),
            ("kimi-k2.7-code", "Kimi K2.7 Code", True, True, False),
            ("glm-5.2", "GLM 5.2", True, True, True),
            ("deepseek-v4-pro", "DeepSeek V4 Pro", True, True, True),
            ("deepseek-v4-flash", "DeepSeek V4 Flash", True, True, True),
            ("minimax-m3", "MiniMax M3", True, True, False),
        ]
        return [
            DiscoveredModelData(
                provider_model_id=m_id,
                display_name=name,
                capabilities={"chat": True, "streaming": True, "vision": vis, "tools": tools, "reasoning": reas},
                context_length=1000000,
                max_output_tokens=16384,
            )
            for m_id, name, vis, tools, reas in catalog
        ]

    async def chat_completions(
        self,
        request: ChatCompletionRequest,
        ctx: ModuleExecutionContext,
    ) -> ChatCompletionResponse:
        base_url = self._get_base_url(ctx)
        headers = self._build_headers(ctx)
        model = request.model or ctx.model_id or "qwen3.8-max-preview"
        if model.startswith("qoder/"):
            model = model[6:]

        payload = request.model_dump(exclude_none=True)
        payload["model"] = model
        payload["stream"] = False

        async with self.create_http_client(ctx) as client:
            resp = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=ctx.timeout or 60.0)
            if resp.status_code != 200:
                raise normalize_upstream_error(status_code=resp.status_code, response_body=(await resp.aread()).decode("utf-8", errors="replace"))
            data = resp.json()
            return ChatCompletionResponse(**data)

    async def stream_chat(
        self,
        request: ChatCompletionRequest,
        ctx: ModuleExecutionContext,
    ) -> AsyncGenerator[str, None]:
        base_url = self._get_base_url(ctx)
        headers = self._build_headers(ctx)
        headers["Accept"] = "text/event-stream"
        model = request.model or ctx.model_id or "qwen3.8-max-preview"
        if model.startswith("qoder/"):
            model = model[6:]

        payload = request.model_dump(exclude_none=True)
        payload["model"] = model
        payload["stream"] = True

        async with self.create_http_client(ctx) as client:
            async with client.stream(
                "POST", f"{base_url}/chat/completions", headers=headers, json=payload, timeout=ctx.timeout or 120.0
            ) as resp:
                if resp.status_code != 200:
                    err_body = await resp.aread()
                    raise normalize_upstream_error(status_code=resp.status_code, response_body=(await resp.aread()).decode("utf-8", errors="replace"))

                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data:"):
                        raw_json = line[5:].strip()
                        if raw_json == "[DONE]":
                            yield "data: [DONE]\n\n"
                            break

                        # Check for Qoder HTTP 200 error wrapper {statusCodeValue, body}
                        try:
                            envelope = json.loads(raw_json)
                            status_val = envelope.get("statusCodeValue")
                            if status_val is not None and status_val != 200:
                                body_err = envelope.get("body") or f"status {status_val}"
                                raise normalize_upstream_error(status_code=int(status_val), response_body=body_err)
                        except json.JSONDecodeError:
                            pass

                        yield f"{line}\n\n"
