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

logger = logging.getLogger("app.modules.clinepass")

CLINE_COMPLETIONS_URL = "https://api.cline.bot/api/v1/chat/completions"


class ClinePassAdapter(BaseModuleAdapter):
    """
    Adapter for ClinePass subscription gateway (api.cline.bot).
    Forces streaming upstream and handles cline-pass/* models.
    """

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
            "Accept": "text/event-stream",
            "HTTP-Referer": "https://cline.bot",
            "X-Title": "Cline",
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
            return False, "Missing ClinePass Token / Key", 0

        try:
            async with self.create_http_client(ctx) as client:
                headers = self._build_headers(ctx)
                payload = {
                    "model": "cline-pass/deepseek-v4-flash",
                    "messages": [{"role": "user", "content": "ping"}],
                    "stream": True,
                    "max_tokens": 1,
                }
                async with client.stream(
                    "POST", CLINE_COMPLETIONS_URL, headers=headers, json=payload, timeout=15.0
                ) as resp:
                    if resp.status_code == 401 or resp.status_code == 403:
                        return False, f"Authentication failed: HTTP {resp.status_code}", 0
                    if resp.status_code >= 400:
                        err_text = await resp.aread()
                        return False, f"ClinePass API returned HTTP {resp.status_code}: {err_text.decode('utf-8', errors='ignore')[:200]}", 0

                    models = await self.list_models(ctx)
                    return True, "ClinePass Gateway is active and authorized", len(models)
        except Exception as e:
            return False, f"Connection failed: {str(e)}", 0

    async def list_models(
        self,
        ctx: ModuleExecutionContext,
    ) -> List[DiscoveredModelData]:
        catalog = [
            ("cline-pass/glm-5.2", "GLM-5.2 (ClinePass)", 1048576, 131072, True, False, True),
            ("cline-pass/deepseek-v4-pro", "DeepSeek V4 Pro (ClinePass)", 1048576, 384000, True, False, True),
            ("cline-pass/deepseek-v4-flash", "DeepSeek V4 Flash (ClinePass)", 1048576, 65536, True, False, True),
            ("cline-pass/kimi-k3", "Kimi K3 (ClinePass)", 1048576, 1048576, True, True, True),
            ("cline-pass/minimax-m3", "MiniMax-M3 (ClinePass)", 1048576, 512000, True, True, True),
            ("cline-pass/qwen3.8-max", "Qwen3.8 Max (ClinePass)", 1000000, 65536, True, False, True),
            ("cline-pass/qwen3.7-plus", "Qwen3.7 Plus (ClinePass)", 1000000, 65536, True, True, True),
        ]
        return [
            DiscoveredModelData(
                provider_model_id=m_id,
                display_name=name,
                capabilities={"chat": True, "streaming": True, "vision": vis, "tools": tools, "reasoning": reas},
                context_length=ctx_len,
                max_output_tokens=out_tokens,
            )
            for m_id, name, ctx_len, out_tokens, tools, vis, reas in catalog
        ]

    async def chat_completions(
        self,
        request: ChatCompletionRequest,
        ctx: ModuleExecutionContext,
    ) -> ChatCompletionResponse:
        model = (request.model or ctx.model_id or "cline-pass/deepseek-v4-flash").removeprefix("clinepass/")
        return await collect_chat_completion(self.stream_chat(request, ctx), model, require_complete=True)

    async def stream_chat(
        self,
        request: ChatCompletionRequest,
        ctx: ModuleExecutionContext,
    ) -> AsyncGenerator[str, None]:
        model = request.model or ctx.model_id or "cline-pass/deepseek-v4-flash"
        if model.startswith("clinepass/"):
            model = model[10:]

        payload = request.model_dump(exclude_none=True)
        payload["model"] = model
        payload["stream"] = True

        async with self.create_http_client(ctx) as client:
            headers = self._build_headers(ctx)
            async with client.stream(
                "POST", CLINE_COMPLETIONS_URL, headers=headers, json=payload, timeout=ctx.timeout or 120.0
            ) as resp:
                if resp.status_code != 200:
                    err_body = await resp.aread()
                    raise normalize_upstream_error(status_code=resp.status_code, response_body=(await resp.aread()).decode("utf-8", errors="replace"))

                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data:"):
                        yield f"{line}\n\n"
                        if line.strip() == "data: [DONE]":
                            break
