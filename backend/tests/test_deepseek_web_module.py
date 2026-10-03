import pytest
from app.modules.loader import ModuleLoader
from app.modules.base import ModuleExecutionContext
from app.schemas.chat import ChatMessage, ChatCompletionRequest
from modules.deepseek_web.pow.pow_solver import solve_deepseek_pow
from modules.deepseek_web.handler import (
    build_prompt_from_messages,
    serialize_tools_prompt,
    parse_tool_calls_from_text,
    append_search_citations,
    extract_user_token,
)


@pytest.mark.asyncio
async def test_deepseek_web_module_discovery():
    modules = ModuleLoader.scan_modules()
    assert "deepseek_web" in modules
    loaded = modules["deepseek_web"]
    assert loaded.status == "ready"
    assert loaded.manifest.id == "deepseek_web"
    assert len(loaded.manifest.default_models) >= 4

    adapter = ModuleLoader.get_adapter("deepseek_web")
    assert adapter is not None

    ctx = ModuleExecutionContext(credentials={"user_token": "dummy"})
    models = await adapter.list_models(ctx)
    model_ids = [m.provider_model_id for m in models]
    assert "deepseek-chat" in model_ids
    assert "deepseek-reasoner" in model_ids
    assert "deepseek-search" in model_ids


@pytest.mark.asyncio
async def test_deepseek_pow_solver():
    challenge = {
        "algorithm": "DeepSeekHashV1",
        "salt": "salt",
        "expire_at": 12345,
        "difficulty": 100,
        "challenge": "914ed66cf0f75040e91480161f08e0313dee03c0a895e08a0a28b8ebf1194308",
        "signature": "sig_test",
        "target_path": "/api/v0/chat/completion",
    }
    answer, b64_resp = await solve_deepseek_pow(challenge)
    assert answer == 42
    assert isinstance(b64_resp, str)
    assert len(b64_resp) > 50


def test_token_extraction():
    assert extract_user_token({"user_token": "token123"}) == "token123"
    assert extract_user_token({"user_token": '{"value": "token_inside_json"}'}) == "token_inside_json"
    assert extract_user_token({}) == ""


def test_prompt_formatting():
    messages = [
        ChatMessage(role="system", content="You are a helpful assistant."),
        ChatMessage(role="user", content="Hello!"),
        ChatMessage(role="assistant", content="Hi there!"),
        ChatMessage(role="user", content="What is 2+2?"),
    ]
    prompt = build_prompt_from_messages(messages, history_window=20)
    assert "You are a helpful assistant." in prompt
    assert "Assistant: Hi there!" in prompt
    assert "User: What is 2+2?" in prompt


def test_citations_formatting():
    results = [
        {"cite_index": 1, "title": "Example 1", "url": "https://example.com/1"},
        {"cite_index": 2, "title": "Example 2", "url": "https://example.com/2"},
    ]
    citations = append_search_citations(results, "deepseek-search")
    assert "[1]: [Example 1](https://example.com/1)" in citations
    assert "[2]: [Example 2](https://example.com/2)" in citations


def test_tool_calling_serialization_and_parsing():
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get current weather in city",
                "parameters": {"type": "object", "properties": {"city": {"type": "string"}}},
            },
        }
    ]
    nonce = "testnonce123"
    serialized = serialize_tools_prompt(tools, nonce)
    assert "get_weather" in serialized
    assert "testnonce123" in serialized

    # Simulate model emitting the tool block
    model_output = 'Checking weather now... <tool>{"name": "get_weather", "arguments": {"city": "Paris"}, "_nonce": "testnonce123"}</tool>'
    cleaned_text, tool_calls = parse_tool_calls_from_text(model_output, nonce)
    assert cleaned_text == "Checking weather now..."
    assert len(tool_calls) == 1
    assert tool_calls[0].function.name == "get_weather"
    assert "Paris" in tool_calls[0].function.arguments


def test_deepseek_reasoning_and_content_separation():
    from modules.deepseek_web.handler import process_deepseek_sse_data

    # 1. Initial envelope
    path, chunks, _ = process_deepseek_sse_data(
        {"v": {"response": {"thinking_enabled": True, "fragments": [{"type": "THINK", "content": ""}]}}},
        "",
        thinking_model=True,
    )
    assert path == "thinking"
    assert chunks == []

    # 2. Thinking tokens
    path, chunks, _ = process_deepseek_sse_data({"v": "Let us think."}, path, thinking_model=True)
    assert path == "thinking"
    assert chunks == [("thinking", "Let us think.")]

    # 3. Elapsed secs indicating thinking finished
    path, chunks, _ = process_deepseek_sse_data(
        {"p": "response/fragments/-1/elapsed_secs", "v": 1.2}, path, thinking_model=True
    )
    assert path == "content"

    # 4. Response fragment arrives
    path, chunks, _ = process_deepseek_sse_data(
        {"p": "response/fragments", "v": [{"id": 3, "type": "RESPONSE", "content": "The answer"}]},
        path,
        thinking_model=True,
    )
    assert path == "content"
    assert chunks == [("content", "The answer")]

    # 5. Subsequent answer string tokens
    path, chunks, _ = process_deepseek_sse_data({"v": " is 42."}, path, thinking_model=True)
    assert path == "content"
    assert chunks == [("content", " is 42.")]

