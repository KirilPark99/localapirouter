from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field
import json
import time
import uuid

class FunctionCall(BaseModel):
    name: str
    arguments: str

class ToolCall(BaseModel):
    id: str = Field(default_factory=lambda: f"call_{uuid.uuid4().hex[:12]}")
    type: Literal["function"] = "function"
    function: FunctionCall
    extra_content: Optional[Dict[str, Any]] = None

class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool", "function"]
    content: Optional[Union[str, List[Dict[str, Any]]]] = None
    reasoning_content: Optional[str] = None
    name: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None

class ResponsesRequest(BaseModel):
    model: str
    input: Union[str, List[Dict[str, Any]]]
    instructions: Optional[str] = None
    stream: bool = False
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_output_tokens: Optional[int] = None
    reasoning: Optional[Dict[str, Any]] = None
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    parallel_tool_calls: Optional[bool] = None
    prompt_cache_key: Optional[str] = Field(default=None, max_length=512)

    def to_chat_request(self) -> "ChatCompletionRequest":
        messages: List[ChatMessage] = []
        if self.instructions:
            messages.append(ChatMessage(role="system", content=self.instructions))
        if isinstance(self.input, str):
            messages.append(ChatMessage(role="user", content=self.input))
        else:
            for item in self.input:
                if not isinstance(item, dict):
                    raise ValueError("Responses input items must be objects")
                kind = item.get("type", "message")
                if kind in ("function_call", "function_call_output") and not item.get("call_id"):
                    raise ValueError("Responses tool items require a non-empty call_id")
                if kind == "function_call":
                    messages.append(ChatMessage(role="assistant", tool_calls=[ToolCall(
                        id=item["call_id"], function=FunctionCall(name=item["name"], arguments=item["arguments"]),
                        extra_content=item.get("extra_content"),
                    )]))
                elif kind == "function_call_output":
                    output = item.get("output", "")
                    messages.append(ChatMessage(role="tool", tool_call_id=item["call_id"],
                        content=output if isinstance(output, str) else json.dumps(output)))
                elif kind == "message":
                    role = item.get("role", "user")
                    if role == "developer":
                        role = "system"
                    content = item.get("content")
                    if isinstance(content, list):
                        content = [{**part, "type": "text"} if part.get("type") in ("input_text", "output_text") else part for part in content]
                    messages.append(ChatMessage(role=role, content=content,
                        tool_calls=item.get("tool_calls"), tool_call_id=item.get("tool_call_id")))
                elif kind != "reasoning":
                    raise ValueError(f"Unsupported Responses input item type: {kind}")
        tools = None if self.tools is None else [
            {"type": "function", "function": {k: tool[k] for k in
                ("name", "description", "parameters", "strict") if k in tool}}
            if tool.get("type") == "function" and "function" not in tool else tool
            for tool in self.tools
        ]
        choice = self.tool_choice
        if isinstance(choice, dict) and choice.get("type") == "function" and "name" in choice:
            choice = {"type": "function", "function": {"name": choice["name"]}}
        return ChatCompletionRequest(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            top_p=self.top_p,
            max_tokens=self.max_output_tokens,
            stream=self.stream,
            reasoning=self.reasoning,
            tools=tools,
            tool_choice=choice,
            parallel_tool_calls=self.parallel_tool_calls,
            prompt_cache_key=self.prompt_cache_key,
        )

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    n: Optional[int] = 1
    stream: Optional[bool] = False
    stream_options: Optional[Dict[str, Any]] = None
    stop: Optional[Union[str, List[str]]] = None
    max_tokens: Optional[int] = None
    max_completion_tokens: Optional[int] = None
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None
    response_format: Optional[Dict[str, Any]] = None
    seed: Optional[int] = None
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    parallel_tool_calls: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None
    reasoning_effort: Optional[str] = None
    reasoning: Optional[Dict[str, Any]] = None
    thinking: Optional[Dict[str, Any]] = None
    prompt_cache_key: Optional[str] = Field(default=None, max_length=512)

    def get_effective_max_tokens(self) -> Optional[int]:
        return self.max_completion_tokens if self.max_completion_tokens is not None else self.max_tokens

    def get_effective_reasoning_effort(self) -> Optional[str]:
        """
        Returns the unified reasoning effort ('low', 'medium', 'high', 'minimal', 'max', 'none', etc.)
        extracted from reasoning_effort, reasoning.effort, or thinking.
        """
        if self.reasoning_effort:
            return self.reasoning_effort
        if self.reasoning and isinstance(self.reasoning, dict):
            if "effort" in self.reasoning:
                return str(self.reasoning["effort"])
        if self.thinking and isinstance(self.thinking, dict):
            t_type = self.thinking.get("type")
            if t_type == "disabled":
                return "none"
            budget = self.thinking.get("budget_tokens")
            if budget:
                if budget <= 2048:
                    return "low"
                elif budget <= 8192:
                    return "medium"
                else:
                    return "high"
        return None

    def get_effective_thinking_budget(self) -> Optional[int]:
        """
        Returns token budget for Anthropic / Gemini thinking APIs.
        """
        if self.thinking and isinstance(self.thinking, dict):
            budget = self.thinking.get("budget_tokens")
            if budget:
                return int(budget)
        if self.reasoning and isinstance(self.reasoning, dict):
            max_t = self.reasoning.get("max_tokens")
            if max_t:
                return int(max_t)
        effort = self.get_effective_reasoning_effort()
        if effort:
            if effort.isdigit():
                return int(effort)
            eff_lower = effort.lower()
            if eff_lower in ("off", "none", "disabled"):
                return 0
            budget_map = {
                "minimal": 1024,
                "low": 1024,
                "medium": 4096,
                "high": 16384,
                "xhigh": 24576,
                "max": 32000,
            }
            return budget_map.get(eff_lower, 4096)
        return None

class UsageInfo(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    prompt_tokens_details: Optional[Dict[str, int]] = None
    completion_tokens_details: Optional[Dict[str, int]] = None

class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: ChatMessage
    finish_reason: Optional[str] = "stop"

class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[ChatCompletionChoice]
    usage: Optional[UsageInfo] = None
    system_fingerprint: Optional[str] = None

class ChatCompletionChunkDelta(BaseModel):
    role: Optional[str] = None
    content: Optional[str] = None
    reasoning_content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None

class ChatCompletionChunkChoice(BaseModel):
    index: int = 0
    delta: ChatCompletionChunkDelta
    finish_reason: Optional[str] = None

class ChatCompletionChunk(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex}")
    object: str = "chat.completion.chunk"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[ChatCompletionChunkChoice]
    usage: Optional[UsageInfo] = None
