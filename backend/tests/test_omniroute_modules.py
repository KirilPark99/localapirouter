import json
import base64
import struct
import pytest
from app.modules.loader import ModuleLoader
from app.modules.base import ModuleExecutionContext
from app.schemas.chat import ChatMessage, ChatCompletionRequest

# 1. DuckDuckGo imports
from modules.duckduckgo_web.handler import (
    normalize_model as ddg_normalize_model,
    solve_challenge_sync,
)

# 2. Cline & Clinepass imports
from modules.cline.handler import ClineAdapter
from modules.clinepass.handler import ClinePassAdapter

# 3. Qoder imports
from modules.qoder.handler import QoderAdapter

# 4. Kimi imports
from modules.kimi_web.handler import (
    frame_connect_message,
    decode_connect_frame,
    extract_delta as kimi_extract_delta,
    fold_messages as kimi_fold_messages,
)

# 5. LMArena imports
from modules.lmarena.handler import (
    reconstruct_arena_cookie,
    resolve_arena_model_id,
    parse_arena_sse_line,
    format_arena_prompt,
    generate_uuidv7,
)

# 6. Notion Web imports
from modules.notion_web.handler import (
    resolve_codename as notion_resolve_codename,
    normalize_cookie as notion_normalize_cookie,
    extract_text_from_stream as notion_extract_text,
    NotionWebAdapter,
)

# 7. Zai Web imports
from modules.zai_web.handler import (
    extract_zai_user_id,
    build_zai_signature,
    build_completion_url,
    parse_zai_sse_line,
)


def test_all_modules_discovery():
    modules = ModuleLoader.scan_modules()
    expected_modules = [
        "deepseek_web",
        "duckduckgo_web",
        "cline",
        "clinepass",
        "qoder",
        "kimi_web",
        "lmarena",
        "notion_web",
        "zai_web",
        "agy_cli",
        "codex_cli",
        "grok_builder_cli",
    ]
    for mid in expected_modules:
        assert mid in modules, f"Module {mid} was not discovered"
        m = modules[mid]
        assert m.status == "ready", f"Module {mid} status is {m.status}: {m.error}"
        assert len(m.manifest.default_models) > 0, f"Module {mid} has no default models"

        adapter = ModuleLoader.get_adapter(mid)
        assert adapter is not None, f"No adapter found for module {mid}"


@pytest.mark.asyncio
async def test_duckduckgo_web_module():
    adapter = ModuleLoader.get_adapter("duckduckgo_web")
    ctx = ModuleExecutionContext(model_id="gpt-5.4-mini")
    models = await adapter.list_models(ctx)
    assert len(models) >= 6
    model_ids = [m.provider_model_id for m in models]
    assert "gpt-5.6-luna" in model_ids
    assert "gpt-5.4-mini" in model_ids
    assert "claude-haiku-4-5" in model_ids

    assert ddg_normalize_model("gpt-4o-mini") == "gpt-5.4-mini"
    assert ddg_normalize_model("o3-mini") == "gpt-5.4-mini"
    assert ddg_normalize_model("duckduckgo-web/claude-haiku-4-5") == "claude-haiku-4-5"


@pytest.mark.asyncio
async def test_cline_and_clinepass():
    cline_adapter = ModuleLoader.get_adapter("cline")
    clinepass_adapter = ModuleLoader.get_adapter("clinepass")

    ctx = ModuleExecutionContext(credentials={"api_key": "test_token"})
    cline_models = await cline_adapter.list_models(ctx)
    clinepass_models = await clinepass_adapter.list_models(ctx)

    assert any(m.provider_model_id == "z-ai/glm-5.2" for m in cline_models)
    assert any(m.provider_model_id == "cline-pass/glm-5.2" for m in clinepass_models)
    assert any(m.provider_model_id == "cline-pass/deepseek-v4-pro" for m in clinepass_models)

    # Missing token fails validation
    empty_ctx = ModuleExecutionContext()
    valid, msg, _ = await cline_adapter.validate_credentials(empty_ctx)
    assert not valid
    assert "Missing" in msg


@pytest.mark.asyncio
async def test_qoder_module():
    adapter = ModuleLoader.get_adapter("qoder")
    ctx = ModuleExecutionContext(credentials={"api_key": "sk-test", "api_base": "https://custom.qoder.com/v1"})
    assert adapter._get_base_url(ctx) == "https://custom.qoder.com/v1"

    models = await adapter.list_models(ctx)
    assert any(m.provider_model_id == "qwen3.8-max-preview" for m in models)


def test_kimi_web_connect_framing():
    payload = {"message": {"text": {"content": "hello"}}}
    framed = frame_connect_message(payload)
    assert len(framed) == 5 + len(json.dumps(payload).encode("utf-8"))

    consumed, flags, msg = decode_connect_frame(framed)
    assert consumed == len(framed)
    assert flags == 0
    assert msg == payload

    # Test delta extraction
    assert kimi_extract_delta({"op": "append", "mask": "block.text.content", "block": {"text": {"content": "answer"}}}) == ("text", "answer")
    assert kimi_extract_delta({"op": "append", "mask": "block.think.content", "block": {"think": {"content": "reasoning"}}}) == ("think", "reasoning")

    # Test prompt folding
    msgs = [
        ChatMessage(role="system", content="Be helpful"),
        ChatMessage(role="user", content="Hi"),
        ChatMessage(role="assistant", content="Hello"),
        ChatMessage(role="user", content="How are you?"),
    ]
    prompt, sys_prompt = kimi_fold_messages(msgs)
    assert sys_prompt == "Be helpful"
    assert prompt.startswith("Hi")
    assert "Assistant: Hello" in prompt
    assert "User: How are you?" in prompt


@pytest.mark.asyncio
async def test_kimi_web_models():
    adapter = ModuleLoader.get_adapter("kimi_web")
    assert adapter is not None
    ctx = ModuleExecutionContext(credentials={"access_token": "test_token"})
    models = await adapter.list_models(ctx)
    model_ids = [m.provider_model_id for m in models]

    assert "kimi-k2.8" in model_ids
    assert "kimi-k2.8-thinking" in model_ids
    assert "k2d8" in model_ids
    assert "k2.8" in model_ids
    assert "k3" in model_ids
    assert "kimi-k3" in model_ids
    assert "kimi-k3-thinking" in model_ids
    assert "k2d6" in model_ids
    assert "kimi-k2.6" in model_ids
    assert "k2.6" in model_ids

    # Verify k2.8 has vision and reasoning capabilities
    k28_model = next(m for m in models if m.provider_model_id == "kimi-k2.8")
    assert k28_model.capabilities.get("vision") is True
    assert k28_model.capabilities.get("reasoning") is True
    assert k28_model.capabilities.get("streaming") is True


def test_lmarena_module_cookie_and_models():
    # Single cookie
    assert reconstruct_arena_cookie("arena-auth-prod-v1=xyz") == "arena-auth-prod-v1=xyz"

    # Chunked cookie
    chunked = "arena-auth-prod-v1.0=abc; arena-auth-prod-v1.1=def; other=123"
    reconstructed = reconstruct_arena_cookie(chunked)
    assert "arena-auth-prod-v1=abcdef" in reconstructed
    assert "other=123" in reconstructed

    # Model resolution
    assert resolve_arena_model_id("claude-sonnet-5") == "019f19f2-41f1-7c6d-9891-48d02fd9952c"
    assert resolve_arena_model_id("lmarena/gpt-5.2-high") == "019b1449-0313-7911-b836-419e2ed79b2e"

    # Prompt formatting
    prompt = format_arena_prompt([
        ChatMessage(role="user", content="Hello"),
        ChatMessage(role="assistant", content="World"),
        ChatMessage(role="user", content="Again"),
    ])
    assert "User: Hello" in prompt
    assert "Assistant: World" in prompt

    # SSE parser
    assert parse_arena_sse_line('0:"hello"') == ("text", "hello")
    assert parse_arena_sse_line('g:"thinking"') == ("thinking", "thinking")
    assert parse_arena_sse_line('d:{"finishReason":"stop"}') == ("done", "")
    assert parse_arena_sse_line('2:[{"type":"heartbeat"}]') == ("heartbeat", "")
    assert parse_arena_sse_line('d:{"finishReason":"error"}') == ("error", "Arena stream finished with an error")

    # UUIDv7 generation
    import uuid as py_uuid
    u_str = generate_uuidv7()
    u = py_uuid.UUID(u_str)
    assert u.version == 7
    assert u.variant == py_uuid.RFC_4122


@pytest.mark.asyncio
async def test_lmarena_models_list():
    adapter = ModuleLoader.get_adapter("lmarena")
    assert adapter is not None
    ctx = ModuleExecutionContext()
    models = await adapter.list_models(ctx)
    assert len(models) >= 10
    model_ids = [m.provider_model_id for m in models]
    assert "claude-sonnet-5" in model_ids
    assert "gemini-3.6-flash" in model_ids
    assert "gpt-5.5-instant" in model_ids
    assert "minimax-m3" in model_ids


def test_notion_web_module():
    assert notion_normalize_cookie("token123") == "token_v2=token123"
    assert notion_normalize_cookie("token_v2=token123") == "token_v2=token123"

    assert notion_resolve_codename("gpt-6.1-sol") == "omniberry-sundae"
    assert notion_resolve_codename("gpt-5.6-terra") == "orchid-muffin"
    assert notion_resolve_codename("sonnet-5") == "angel-cake-high"
    assert notion_resolve_codename("notion_web/gemini-3.7-flash") == "grapefruit-zeppole"
    assert notion_resolve_codename("claude-opus-4-6") == "avocado-froyo-medium"
    assert notion_resolve_codename("claude-sonnet-4-6") == "almond-croissant-low"
    assert notion_resolve_codename("claude-fable-5") == "acai-budino-high"
    assert notion_resolve_codename("grok-4.6") == "soursop-shortcake"
    assert notion_resolve_codename("glm-5.3-flash") == "baseten-glm-5.3-flash"
    assert notion_resolve_codename("deepseek-v4-flash") == "baseten-deepseek-v4-flash"
    assert notion_resolve_codename("kimi-k3") == "fireworks-kimi-k3"
    assert notion_resolve_codename("notion-ai") == ""

    # Text extraction from stream
    ndjson_sample = (
        '{"type":"markdown-chat","value":"Hello from <lang:en>Notion</lang>!"}\n'
        '{"type":"record-map","recordMap":{"thread_message":{"m1":{"value":{"value":{"step":{"type":"markdown-chat","value":"Longer final response text"}}}}}}}\n'
    )
    extracted = notion_extract_text(ndjson_sample)
    assert extracted == "Longer final response text"

    # Test error detection: premium-feature-unavailable
    ndjson_limit_err = (
        '{"type":"premium-feature-unavailable","featureAvailability":{"type":"unavailable","limit":{"type":"cumulative","current":54,"total":50}}}\n'
        '{"type":"record-map","recordMap":{"thread_message":{"m1":{"value":{"value":{"step":{"type":"markdown-chat","value":"Hello! I am ready to assist. How can I help you today?"}}}}}}}\n'
    )
    with pytest.raises(RuntimeError) as exc_info:
        notion_extract_text(ndjson_limit_err)
    assert "Plan limit exceeded (54/50 requests used)" in str(exc_info.value)

    # Test prompt greeting exclusion from fallback recordMap
    greeting = "Hello! I am ready to assist. How can I help you today?"
    ndjson_with_greeting = (
        '{"type":"record-map","recordMap":{"thread_message":{"m1":{"value":{"value":{"step":{"type":"markdown-chat","value":"' + greeting + '"}}}}}}}\n'
    )
    # When excluded, should return empty instead of echoing prompt greeting
    assert notion_extract_text(ndjson_with_greeting, exclude_texts={greeting}) == ""

    # Test transcript builder strips leading assistant greeting
    adapter = NotionWebAdapter()
    tr = adapter._build_transcript(
        [
            ChatMessage(role="assistant", content=greeting),
            ChatMessage(role="user", content="Hi there"),
        ],
        model_codename="angel-cake-high",
        space_id="space-123",
        user_id="user-456",
    )
    # The transcript should only have config, context, and user (no assistant step before first user)
    types = [step["type"] for step in tr]
    assert types == ["config", "context", "user"]
    assert tr[2]["value"] == [["Hi there"]]


def test_zai_web_module():
    # Fake JWT with user id
    fake_payload = base64.urlsafe_b64encode(json.dumps({"id": "usr_998877"}).encode()).decode().rstrip("=")
    fake_jwt = f"eyJhbGciOiJIUzI1NiJ9.{fake_payload}.fake_signature"
    assert extract_zai_user_id(fake_jwt) == "usr_998877"

    # Test HMAC signature matches verified reference
    sig = build_zai_signature("hello", "req123", 1700000000000, "user456")
    assert sig == "f5272eee580c691659817cd55f6e9da5c45dadf9af3e29db915f600f5b283f81"

    # SSE Parser - success frames
    assert parse_zai_sse_line('data: {"choices":[{"delta":{"content":"Hi"},"finish_reason":null}]}') == ("text", "Hi", False)
    assert parse_zai_sse_line('data: {"data":{"phase":"thinking","delta_content":"Thought"}}') == ("thinking", "Thought", False)
    assert parse_zai_sse_line("data: [DONE]") == ("text", "", True)

    # SSE Parser - nested upstream error frame detection
    error_frame = 'data: {"data":{"data":{"done":true,"error":{"captcha_error_type":"missing_param","code":"FRONTEND_CAPTCHA_REQUIRED","detail":"Please refresh the page to update the app, then try again.","error_code":"FRONTEND_CAPTCHA_REQUIRED"}},"done":true,"error":{"captcha_error_type":"missing_param","code":"FRONTEND_CAPTCHA_REQUIRED","detail":"Please refresh the page to update the app, then try again.","error_code":"FRONTEND_CAPTCHA_REQUIRED"}},"type":"chat:completion"}'
    try:
        parse_zai_sse_line(error_frame)
        assert False, "Should have raised RuntimeError on upstream error frame"
    except RuntimeError as e:
        assert "FRONTEND_CAPTCHA_REQUIRED" in str(e)
        assert "captcha_verify_param" in str(e)

    # Completion URL parameters check
    comp_url = build_completion_url("req_test", 1700000000000, "fake_token", "user456")
    assert "local_time=" in comp_url
    assert "utc_time=" in comp_url
    assert "powered+by+GLM-5.3-Flash" in comp_url or "powered%20by%20GLM-5.3-Flash" in comp_url or "GLM-5.3-Flash" in comp_url
