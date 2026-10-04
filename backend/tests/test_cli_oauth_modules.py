import json
from typing import Any
import pytest
from pathlib import Path
from app.modules.loader import ModuleLoader
from app.modules.base import ModuleExecutionContext
from app.schemas.chat import ChatMessage, ChatCompletionRequest

# 1. Antigravity CLI module
from modules.agy_cli.handler import AgyCliAdapter

# 2. OpenAI Codex CLI module
from modules.codex_cli.handler import CodexCliAdapter, _decode_jwt_payload

# 3. xAI Grok Builder CLI module
from modules.grok_builder_cli.handler import GrokBuilderCliAdapter


def test_cli_modules_discovery_and_manifests():
    """Verify that agy_cli, codex_cli, and grok_builder_cli are properly discovered with valid manifests."""
    modules = ModuleLoader.scan_modules()

    for mid in ["agy_cli", "codex_cli", "grok_builder_cli"]:
        assert mid in modules, f"Module {mid} not found in discovered modules"
        loaded = modules[mid]
        assert loaded.status == "ready"
        assert loaded.error is None
        manifest = loaded.manifest
        assert manifest.auth_type == "custom_fields"
        assert len(manifest.fields) >= 2
        assert len(manifest.default_models) >= 4

        adapter = ModuleLoader.get_adapter(mid)
        assert adapter is not None


@pytest.mark.asyncio
async def test_agy_cli_adapter_token_resolution():
    adapter = AgyCliAdapter()

    # 1. Direct tokens
    ctx = ModuleExecutionContext(
        credentials={
            "access_token": "ya29.test-access",
            "refresh_token": "1//test-refresh",
            "project_id": "test-custom-proj",
        }
    )
    tokens = adapter._resolve_raw_tokens(ctx)
    assert tokens["access_token"] == "ya29.test-access"
    assert tokens["refresh_token"] == "1//test-refresh"
    assert tokens["project_id"] == "test-custom-proj"

    # 2. Pasted auth_json
    pasted = json.dumps({
        "token": {
            "access_token": "ya29.pasted-access",
            "refresh_token": "1//pasted-refresh",
            "expiry": "2026-10-05T00:00:00Z",
        },
        "project_id": "pasted-proj"
    })
    ctx_pasted = ModuleExecutionContext(credentials={"auth_json": pasted})
    tokens_pasted = adapter._resolve_raw_tokens(ctx_pasted)
    assert tokens_pasted["access_token"] == "ya29.pasted-access"
    assert tokens_pasted["refresh_token"] == "1//pasted-refresh"
    assert tokens_pasted["project_id"] == "pasted-proj"


@pytest.mark.asyncio
async def test_agy_cli_adapter_message_conversion_and_envelope():
    adapter = AgyCliAdapter()
    req = ChatCompletionRequest(
        model="gemini-2.5-pro",
        messages=[
            ChatMessage(role="system", content="You are a helpful assistant"),
            ChatMessage(role="user", content="Hello world"),
            ChatMessage(role="assistant", content="Hi! How can I help?"),
            ChatMessage(role="user", content="Tell me a joke"),
        ],
        temperature=0.5,
        max_tokens=2048,
    )

    envelope = adapter._build_cloudcode_envelope(req, "test-proj", "gemini-2.5-pro")
    assert envelope["project"] == "test-proj"
    assert envelope["model"] == "gemini-2.5-pro"
    assert envelope["userAgent"] == "antigravity"
    assert envelope["requestType"] == "agent"

    contents = envelope["request"]["contents"]
    assert len(contents) == 3
    # System message was prepended to the first user turn
    assert "System Instructions:" in contents[0]["parts"][0]["text"]
    assert "You are a helpful assistant" in contents[0]["parts"][0]["text"]
    assert "Hello world" in contents[0]["parts"][0]["text"]
    assert contents[1]["role"] == "model"
    assert contents[2]["role"] == "user"

    # Models catalog
    models = await adapter.list_models(ModuleExecutionContext())
    assert len(models) >= 5
    model_ids = [m.provider_model_id for m in models]
    assert "gemini-3.8-flash-high" in model_ids
    assert "gemini-3.1-pro-high" in model_ids
    assert "claude-sonnet-4-6" in model_ids


@pytest.mark.asyncio
async def test_codex_cli_adapter():
    adapter = CodexCliAdapter()

    # 1. Direct tokens and account ID
    ctx = ModuleExecutionContext(
        credentials={
            "access_token": "ey-access-token",
            "refresh_token": "ey-refresh-token",
            "account_id": "test-account-1234",
        }
    )
    tokens = adapter._resolve_raw_tokens(ctx)
    assert tokens["access_token"] == "ey-access-token"
    assert tokens["refresh_token"] == "ey-refresh-token"
    assert tokens["account_id"] == "test-account-1234"

    # 2. Pasted auth_json
    pasted = json.dumps({
        "tokens": {
            "access_token": "ey-pasted-access",
            "refresh_token": "ey-pasted-refresh",
            "account_id": "pasted-account-5678",
        }
    })
    ctx_pasted = ModuleExecutionContext(credentials={"auth_json": pasted})
    tokens_pasted = adapter._resolve_raw_tokens(ctx_pasted)
    assert tokens_pasted["access_token"] == "ey-pasted-access"
    assert tokens_pasted["account_id"] == "pasted-account-5678"

    # 3. Message conversion to Responses API input format
    messages = [
        ChatMessage(role="user", content="Write a quicksort in Python"),
        ChatMessage(role="assistant", content="def quicksort(arr): ..."),
    ]
    input_items = adapter._convert_messages_to_responses_input(messages)
    assert len(input_items) == 2
    assert input_items[0]["role"] == "user"
    assert input_items[0]["content"][0]["type"] == "input_text"
    assert input_items[0]["content"][0]["text"] == "Write a quicksort in Python"
    assert input_items[1]["role"] == "assistant"

    # 4. Headers
    headers = adapter._build_headers("my-access-token", "my-acc-id")
    assert headers["Authorization"] == "Bearer my-access-token"
    assert headers["ChatGPT-Account-Id"] == "my-acc-id"
    assert "codex-cli" in headers["User-Agent"]
    assert headers["Openai-Beta"] == "responses=experimental"

    # 5. Models catalog
    models = await adapter.list_models(ModuleExecutionContext())
    assert len(models) >= 5
    model_ids = [m.provider_model_id for m in models]
    assert "gpt-5.5" in model_ids
    assert "gpt-5.6-sol" in model_ids
    assert "gpt-6.1-sol" in model_ids
    assert "gpt-4o" not in model_ids


def test_codex_jwt_payload_decoding():
    # Test valid mock JWT extraction
    header = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    payload_dict = {
        "email": "test@example.com",
        "https://api.openai.com/auth": {
            "chatgpt_account_id": "extracted-acc-id-9999",
            "chatgpt_plan_type": "pro"
        }
    }
    import base64
    payload = base64.urlsafe_b64encode(json.dumps(payload_dict).encode("utf-8")).decode("utf-8").rstrip("=")
    fake_jwt = f"{header}.{payload}.sig"

    decoded = _decode_jwt_payload(fake_jwt)
    assert decoded["email"] == "test@example.com"
    auth_info = decoded["https://api.openai.com/auth"]
    assert auth_info["chatgpt_account_id"] == "extracted-acc-id-9999"


@pytest.mark.asyncio
async def test_grok_builder_cli_adapter():
    adapter = GrokBuilderCliAdapter()

    # 1. Direct credentials
    ctx = ModuleExecutionContext(
        credentials={
            "access_token": "grok-access-jwt",
            "refresh_token": "grok-refresh-token",
            "email": "user@example.com",
        }
    )
    tokens = adapter._resolve_raw_tokens(ctx)
    assert tokens["access_token"] == "grok-access-jwt"
    assert tokens["refresh_token"] == "grok-refresh-token"
    assert tokens["email"] == "user@example.com"

    # 2. Pasted auth.json format
    pasted = json.dumps({
        "https://auth.x.ai::b1a00492-073a-47ea-816f-4c329264a828": {
            "key": "pasted-grok-key",
            "refresh_token": "pasted-grok-refresh",
            "email": "grok-user@x.ai",
            "user_id": "u-12345"
        }
    })
    ctx_pasted = ModuleExecutionContext(credentials={"auth_json": pasted})
    tokens_pasted = adapter._resolve_raw_tokens(ctx_pasted)
    assert tokens_pasted["access_token"] == "pasted-grok-key"
    assert tokens_pasted["refresh_token"] == "pasted-grok-refresh"
    assert tokens_pasted["email"] == "grok-user@x.ai"

    # 3. Message conversion
    messages = [
        ChatMessage(role="user", content="Hello Grok"),
    ]
    input_items = adapter._convert_messages_to_responses_input(messages)
    assert len(input_items) == 1
    assert input_items[0]["role"] == "user"
    assert input_items[0]["content"][0]["text"] == "Hello Grok"

    # 4. Headers
    headers = adapter._build_headers("grok-access-jwt")
    assert headers["Authorization"] == "Bearer grok-access-jwt"
    assert headers["X-XAI-Token-Auth"] == "xai-grok-cli"
    assert headers["x-grok-client-identifier"] == "grok-shell"
    assert headers["x-grok-client-version"] == "1.0.13"
    assert "grok-shell/1.0.13" in headers["User-Agent"]

    # 5. Models catalog
    models = await adapter.list_models(ModuleExecutionContext())
    assert len(models) >= 4
    model_ids = [m.provider_model_id for m in models]
    assert any("grok-4" in m or "grok-3" in m for m in model_ids)


@pytest.mark.asyncio
@pytest.mark.parametrize("module_id,adapter_class,count", [
    ("agy_cli", AgyCliAdapter, 14),
    ("codex_cli", CodexCliAdapter, 8),
    ("grok_builder_cli", GrokBuilderCliAdapter, 4),
])
async def test_current_cli_catalog_matches_manifest(module_id, adapter_class, count):
    manifest_path = Path(__file__).parents[1] / "modules" / module_id / "manifest.json"
    expected = json.loads(manifest_path.read_text())["default_models"]
    models = await adapter_class().list_models(ModuleExecutionContext(
        credentials={"auto_detect_local": False},
    ))
    ids = [m.provider_model_id for m in models]
    assert len(ids) == len(set(ids)) == count
    assert ids == [m["id"] for m in expected]
    assert [m.context_length for m in models] == [m["context_length"] for m in expected]
    assert [m.max_output_tokens for m in models] == [m["max_output_tokens"] for m in expected]


@pytest.mark.asyncio
@pytest.mark.parametrize("module_id,adapter_class", [
    ("codex_cli", CodexCliAdapter),
    ("grok_builder_cli", GrokBuilderCliAdapter),
])
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("upstream_status", [200, 400])
async def test_responses_history_and_errors(monkeypatch, module_id, adapter_class, stream, upstream_status):
    import httpx
    from app.adapters.module_adapter import CustomModuleAdapter
    from app.core.errors import ErrorCategory, RouterException

    adapter = adapter_class()
    monkeypatch.setattr(ModuleLoader, "get_adapter", lambda name: adapter if name == module_id else None)
    bridge = CustomModuleAdapter()

    def upstream(request):
        body = json.loads(request.content)
        assert [m["role"] for m in body["input"]] == ["system", "user", "assistant", "user"]
        assert [m["content"][0]["type"] for m in body["input"]] == [
            "input_text", "input_text", "output_text", "input_text",
        ]
        assert body["input"][2]["content"][0]["text"] == "Previous answer"
        if upstream_status == 400:
            return httpx.Response(400, json={"error": {"message": "Invalid input format"}})
        event = {"type": "response.output_text.delta", "delta": "OK"}
        return httpx.Response(200, text="data: " + json.dumps(event) + "\n\ndata: {\"type\":\"response.completed\"}\n\n",
                              headers={"Content-Type": "text/event-stream"})

    monkeypatch.setattr(adapter, "create_http_client", lambda *args, **kwargs:
                        httpx.AsyncClient(transport=httpx.MockTransport(upstream)))
    request = ChatCompletionRequest(model="test-model", stream=stream, messages=[
        ChatMessage(role="system", content="Be concise"),
        ChatMessage(role="user", content="Hello"),
        ChatMessage(role="assistant", content="Previous answer"),
        ChatMessage(role="user", content="Continue"),
    ])
    kwargs: dict[str, Any] = dict(base_url="", api_key=json.dumps({"auto_detect_local": False, "access_token": "dummy-token"}),
                  model_id="test-model", request=request, extra_headers={}, configuration={"module_id": module_id})

    async def invoke():
        if stream:
            return "".join([chunk async for chunk in bridge.stream_chat(**kwargs)])
        return (await bridge.chat_completions(**kwargs)).choices[0].message.content

    if upstream_status == 200:
        result = await invoke()
        assert result and "OK" in result
    else:
        with pytest.raises(RouterException) as caught:
            await invoke()
        error = bridge.normalize_error(exception=caught.value)
        assert error.category == ErrorCategory.INVALID_REQUEST
        assert error.status_code == error.upstream_status == 400
        assert error.message == "Invalid input format"


@pytest.mark.asyncio
async def test_live_local_cli_detection():
    """Verify that on the current machine, local tokens are automatically discovered and valid."""
    adapter_agy = AgyCliAdapter()
    tokens_agy = adapter_agy._resolve_raw_tokens(ModuleExecutionContext())
    assert tokens_agy.get("access_token") or tokens_agy.get("refresh_token")

    adapter_codex = CodexCliAdapter()
    tokens_codex = adapter_codex._resolve_raw_tokens(ModuleExecutionContext())
    assert tokens_codex.get("access_token") or tokens_codex.get("refresh_token")
    assert tokens_codex.get("account_id") == "4e009262-855b-4472-be81-59e1c750b71e"

    adapter_grok = GrokBuilderCliAdapter()
    tokens_grok = adapter_grok._resolve_raw_tokens(ModuleExecutionContext())
    assert tokens_grok.get("access_token") or tokens_grok.get("refresh_token")
