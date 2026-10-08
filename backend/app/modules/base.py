import os
from contextlib import aclosing
import json
import time
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, List, Literal, Optional, Tuple
from pydantic import BaseModel, Field, ConfigDict
import httpx

from app.schemas.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatMessage,
    UsageInfo,
)
from app.adapters.base import DiscoveredModelData


class ModuleField(BaseModel):
    """Defines a configuration / credential field required by the custom module."""
    key: str
    label: str
    type: str = "text"  # "text" | "password" | "textarea" | "number" | "select"
    required: bool = True
    default: Optional[Any] = None
    placeholder: Optional[str] = None
    description: Optional[str] = None
    options: Optional[List[Dict[str, str]]] = None  # For select fields: [{"label": "...", "value": "..."}]


class ModuleDefaultModel(BaseModel):
    """Default model exposed by the module if live model listing is not dynamically available."""
    id: str
    name: str
    context_length: Optional[int] = 32768
    max_output_tokens: Optional[int] = 4096
    reasoning_effort: Optional[str] = None
    capabilities: Dict[str, Any] = Field(default_factory=lambda: {
        "chat": True,
        "streaming": True,
        "vision": "unknown",
        "tools": "unknown",
        "reasoning": "unknown",
    })


class ModuleManifest(BaseModel):
    """Manifest describing a custom provider module."""
    id: str  # Unique slug, e.g. "codex_oauth", "deepseek_web"
    name: str  # Display name, e.g. "Codex OAuth Provider"
    version: str = "1.0.0"
    description: str = ""
    author: Optional[str] = None
    icon: Optional[str] = "Puzzle"  # Lucide icon name, e.g. "Puzzle", "Bot", "MessageSquare", "KeyRound"
    auth_type: str = "custom_fields"  # "custom_fields" | "oauth_device" | "bearer"
    fields: List[ModuleField] = Field(default_factory=list)
    default_models: List[ModuleDefaultModel] = Field(default_factory=list)
    folder_path: Optional[str] = None


class ModuleExecutionContext(BaseModel):
    """Runtime execution context passed to custom module handlers."""
    credentials: Dict[str, Any] = Field(default_factory=dict)
    proxy_url: Optional[str] = None
    model_id: str = ""
    timeout: float = 60.0
    extra_config: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True)


class SubscriptionLimit(BaseModel):
    """Only provider-reported values; missing numbers are not zero/unlimited."""
    name: str
    model: Optional[str] = None
    used_percent: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    remaining_percent: Optional[float] = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    limit: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    used: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    remaining: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    unit: Optional[str] = None
    reset_at: Optional[str] = None
    window_seconds: Optional[int] = Field(default=None, ge=0)


class SubscriptionLimits(BaseModel):
    status: Literal["ok", "unsupported", "unavailable"] = "ok"
    plan: Optional[str] = None
    limits: List[SubscriptionLimit] = Field(default_factory=list)
    message: Optional[str] = None
    checked_at: Optional[str] = None


class BaseModuleAdapter(ABC):
    """
    Base class that all custom modules in `backend/modules/<name>/handler.py` must inherit from.
    """

    @abstractmethod
    async def validate_credentials(
        self,
        ctx: ModuleExecutionContext,
    ) -> Tuple[bool, str, int]:
        """
        Validate whether the given credentials and proxy connection are healthy and working.
        Returns: (success: bool, message: str, models_found_count: int)
        """
        pass

    @abstractmethod
    async def list_models(
        self,
        ctx: ModuleExecutionContext,
    ) -> List[DiscoveredModelData]:
        """
        Fetch or return the list of available models for this module profile.
        """
        pass

    @abstractmethod
    async def chat_completions(
        self,
        request: ChatCompletionRequest,
        ctx: ModuleExecutionContext,
    ) -> ChatCompletionResponse:
        """
        Execute a standard non-streaming chat completion request.
        """
        pass

    @abstractmethod
    async def stream_chat(
        self,
        request: ChatCompletionRequest,
        ctx: ModuleExecutionContext,
    ) -> AsyncGenerator[str, None]:
        """
        Execute a streaming chat completion request, yielding Server-Sent Events (SSE) data chunks:
        e.g. data: {"id":"...","choices":[{"delta":{"content":"..."}}]}\n\n
        Followed by: data: [DONE]\n\n
        """
        pass

    async def get_subscription_limits(self, ctx: ModuleExecutionContext) -> SubscriptionLimits:
        """Read native subscription quotas for this credential, not router quotas."""
        return SubscriptionLimits(status="unsupported")

    async def close(self) -> None:
        """Release owned subprocesses/resources on reload and application shutdown."""
        pass

    async def close_profile(self, credential_id: int) -> None:
        """Release this profile's resources after edits, disable or deletion."""
        pass

    def create_http_client(
        self,
        ctx: ModuleExecutionContext,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> httpx.AsyncClient:
        """
        Helper method to create an async HTTPX client preconfigured with the assigned proxy (if any).
        Supports HTTP, HTTPS, SOCKS5, and SOCKS5H proxies.
        """
        client_kwargs: Dict[str, Any] = {
            "timeout": timeout or ctx.timeout or 60.0,
            "follow_redirects": True,
        }
        if headers:
            client_kwargs["headers"] = headers

        if ctx.proxy_url:
            client_kwargs["proxy"] = ctx.proxy_url

        return httpx.AsyncClient(**client_kwargs)


class ChatStreamAccumulator:
    """One collector for CLI completion, safe stream redaction and cache writes."""
    MAX_BYTES = 8 * 1024 * 1024

    def __init__(self):
        import codecs
        self._decoder = codecs.getincrementaldecoder("utf-8")()
        self.buffer, self.choices = "", {}
        self.usage, self.error, self.response_id = None, None, None
        self.created, self.done, self.size = int(time.time()), False, 0

    def feed(self, chunk):
        if isinstance(chunk, bytes):
            chunk = self._decoder.decode(chunk)
        self.size += len(chunk.encode("utf-8"))
        if self.size > self.MAX_BYTES:
            raise ValueError("Response stream exceeds the 8 MiB assembly limit")
        self.buffer += chunk
        self.buffer = self.buffer.replace("\r\n", "\n")
        while "\n\n" in self.buffer:
            event, self.buffer = self.buffer.split("\n\n", 1)
            raw = "\n".join(line[5:].lstrip() for line in event.split("\n") if line.startswith("data:"))
            if not raw:
                continue
            if raw == "[DONE]":
                self.done = True
                continue
            data = json.loads(raw)
            if data.get("error"):
                self.error = data
                continue
            self.response_id = data.get("id") or self.response_id
            self.created = data.get("created", self.created)
            if data.get("usage"):
                self.usage = UsageInfo.model_validate(data["usage"])
            for choice in data.get("choices", []):
                state = self.choices.setdefault(choice.get("index", 0), {
                    "content": [], "reasoning": [], "reasoning_details": {}, "calls": {}, "finish": None,
                })
                delta = choice.get("delta") or choice.get("message") or {}
                if delta.get("content"):
                    state["content"].append(delta["content"])
                if delta.get("reasoning_content"):
                    state["reasoning"].append(delta["reasoning_content"])
                for position, detail in enumerate(delta.get("reasoning_details") or []):
                    target = state["reasoning_details"].setdefault(detail.get("index", position), {})
                    for key, value in detail.items():
                        if key in ("thinking", "signature", "text", "summary") and isinstance(value, str):
                            target[key] = target.get(key, "") + value
                        elif value is None and key in ("text", "summary", "signature"):
                            continue
                        else:
                            target[key] = value
                if choice.get("finish_reason"):
                    state["finish"] = choice["finish_reason"]
                for position, call in enumerate(delta.get("tool_calls") or []):
                    target = state["calls"].setdefault(call.get("index", position), {
                        "id": "", "type": "function", "function": {"name": "", "arguments": ""},
                    })
                    if call.get("id"):
                        target["id"] = call["id"]
                    if call.get("extra_content"):
                        target["extra_content"] = call["extra_content"]
                    function = call.get("function") or {}
                    target["function"]["name"] += function.get("name") or ""
                    target["function"]["arguments"] += function.get("arguments") or ""

    def response(self, model: str, require_complete: bool = False):
        from app.schemas.chat import ToolCall
        if self.error:
            from app.core.errors import normalize_upstream_error
            raise normalize_upstream_error(response_body=self.error)
        if require_complete and (not self.done or self.buffer.strip() or not self.choices or
                any(c["finish"] is None for c in self.choices.values())):
            raise ValueError("Only successfully completed streams can be cached")
        choices = []
        for index, state in sorted(self.choices.items()):
            calls = [ToolCall.model_validate(c) for _, c in sorted(state["calls"].items())] or None
            if calls and any(not c.id or not c.function.name for c in calls):
                raise ValueError("Incomplete streamed tool call")
            message = ChatMessage(role="assistant", content="".join(state["content"]) or (None if calls else ""),
                                  reasoning_content="".join(state["reasoning"]) or None,
                                  reasoning_details=list(state["reasoning_details"].values()) or None, tool_calls=calls)
            choices.append(ChatCompletionChoice(index=index, message=message,
                           finish_reason=state["finish"] or ("tool_calls" if calls else "stop")))
        if not choices and not require_complete:
            choices = [ChatCompletionChoice(message=ChatMessage(role="assistant", content=""))]
        kwargs = {"id": self.response_id} if self.response_id else {}
        return ChatCompletionResponse(model=model, created=self.created, choices=choices, usage=self.usage, **kwargs)


async def collect_chat_completion(source: AsyncGenerator[str, None], model: str, require_complete: bool = False) -> ChatCompletionResponse:
    accumulator = ChatStreamAccumulator()
    async with aclosing(source):
        async for chunk in source:
            accumulator.feed(chunk)
            if accumulator.error:
                accumulator.response(model)
            if accumulator.done:
                break
    return accumulator.response(model, require_complete=require_complete)
