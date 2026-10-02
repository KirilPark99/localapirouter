"""
Custom Provider Module Handler Template

To create your own custom module:
1. Copy this folder `_template` to `backend/modules/<your_module_slug>` (without leading underscore).
2. Edit `manifest.json` with your unique `id`, `name`, `fields`, and `default_models`.
3. Implement the logic below in `handler.py`.
4. Go to the web console -> "Modules" -> click "Rescan Modules".
5. Create profiles with your custom fields and assign any SOCKS5/HTTP proxies!
"""

import json
import time
import uuid
from typing import AsyncGenerator, List, Tuple
from app.modules.base import BaseModuleAdapter, ModuleExecutionContext
from app.adapters.base import DiscoveredModelData
from app.schemas.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatMessage,
    UsageInfo,
)


class TemplateCustomModule(BaseModuleAdapter):
    """
    Example handler for a custom module.
    """

    async def validate_credentials(
        self,
        ctx: ModuleExecutionContext,
    ) -> Tuple[bool, str, int]:
        """
        Validate credentials and proxy connectivity.
        Return: (success: bool, message: str, models_found_count: int)
        """
        user_token = ctx.credentials.get("user_token")
        if not user_token:
            return False, "user_token is required", 0

        # You can make an HTTP request through the assigned proxy using self.create_http_client(ctx)
        # async with self.create_http_client(ctx) as client:
        #     resp = await client.get("https://api.example.com/user")
        #     if resp.status_code == 200:
        #         return True, "Connected successfully", 1
        #     return False, f"HTTP Error {resp.status_code}", 0

        return True, "Profile credentials validated successfully", 1

    async def list_models(
        self,
        ctx: ModuleExecutionContext,
    ) -> List[DiscoveredModelData]:
        """
        Fetch available models dynamically from the upstream service,
        or return static models.
        """
        return [
            DiscoveredModelData(
                provider_model_id="custom-chat",
                display_name="Custom Model (Default)",
                context_length=32768,
                max_output_tokens=4096,
            )
        ]

    async def chat_completions(
        self,
        request: ChatCompletionRequest,
        ctx: ModuleExecutionContext,
    ) -> ChatCompletionResponse:
        """
        Handle a non-streaming chat completion request.
        """
        user_token = ctx.credentials.get("user_token")
        proxy_url = ctx.proxy_url  # SOCKS5/HTTP proxy string if assigned to profile

        # Example of making a request through proxy:
        # async with self.create_http_client(ctx) as client:
        #     upstream_res = await client.post(...)

        content = f"[Custom Module Response] Model: {request.model}. Messages count: {len(request.messages)}."
        if proxy_url:
            content += f" Routed via proxy: {proxy_url}."

        return ChatCompletionResponse(
            id=f"chatcmpl-mod-{uuid.uuid4().hex[:8]}",
            model=request.model,
            created=int(time.time()),
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=content),
                    finish_reason="stop",
                )
            ],
            usage=UsageInfo(
                prompt_tokens=sum(len(m.content or "") for m in request.messages) // 4,
                completion_tokens=len(content) // 4,
                total_tokens=(sum(len(m.content or "") for m in request.messages) + len(content)) // 4,
            ),
        )

    async def stream_chat(
        self,
        request: ChatCompletionRequest,
        ctx: ModuleExecutionContext,
    ) -> AsyncGenerator[str, None]:
        """
        Handle a streaming chat completion request.
        Yields standard SSE lines: data: {json}\n\n followed by data: [DONE]\n\n
        """
        req_id = f"chatcmpl-mod-{uuid.uuid4().hex[:8]}"
        created = int(time.time())

        # Yield initial role delta
        first_chunk = {
            "id": req_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": request.model,
            "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}],
        }
        yield f"data: {json.dumps(first_chunk)}\n\n"

        words = ["Hello", "from", "your", "custom", "module!"]
        for word in words:
            chunk = {
                "id": req_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": request.model,
                "choices": [{"index": 0, "delta": {"content": word + " "}, "finish_reason": None}],
            }
            yield f"data: {json.dumps(chunk)}\n\n"

        # Final stop chunk
        stop_chunk = {
            "id": req_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": request.model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        yield f"data: {json.dumps(stop_chunk)}\n\n"
        yield "data: [DONE]\n\n"
