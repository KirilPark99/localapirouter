"""Offline regressions: message metadata survives compression; direct timeout is configurable."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.compression.base import CompressionContext, StageExecutionResult
from app.compression.pipeline import CompressionPipelineService
from app.compression.registry import StageRegistry
from app.compression.stages.custom_regex import CustomRegexStage
from app.core.config import settings
from app.routing import engine
from app.schemas.chat import ChatCompletionRequest, ChatCompletionResponse, ChatMessage


BLOCK = "\n".join(["A sufficiently long repeated block of ordinary prose." for _ in range(6)])
PROSE = "Sure, please note that the answer is really very simple. " * 30
ARRAY = json.dumps([{"long_column_name": i, "another_column_name": "value"} for i in range(10)], indent=4)
CASES = [
    ("lite", "hello" + " " * 100 + "\n\n\n\nworld", {}, 0),
    ("lite", [{"type": "text", "text": "hello" + " " * 100}], {}, 0),
    ("rtk", "\x1b[32mhello\x1b[0m\n" * 40, {}, 0),
    ("responses_tool", ARRAY, {}, 0),
    ("headroom", ARRAY, {}, 0),
    ("caveman", PROSE, {}, 0),
    ("llmlingua", PROSE, {}, 0),
    ("ultra", PROSE, {}, 0),
    ("relevance", PROSE, {}, 0),
    ("omniglyph", PROSE * 4, {}, 0),
    ("aggressive", PROSE, {"recent_turns_verbatim": 1, "summarize_depth": 1}, 0),
    ("aggressive", "\n\n".join([PROSE] * 5), {"recent_turns_verbatim": 1, "summarize_depth": 10}, 0),
    ("ccr", PROSE, {}, 0),
    ("ccr", "\n\n".join([PROSE] * 2), {}, 0),
    ("session_dedup", BLOCK, {}, 1),
    ("session_dedup", "different prefix\n" + BLOCK, {}, 1),
    ("custom_regex", PROSE, {"rules": [{"pattern": "Sure, please note that", "replacement": ""}]}, 0),
]


def tool_message(role, content):
    return ChatMessage(
        role=role, content=content, name="synthetic_tool", reasoning_content="retained reasoning",
        tool_call_id="call_synthetic" if role == "tool" else None,
        tool_calls=[{"id": "call_synthetic", "function": {"name": "lookup", "arguments": '{"q":"test"}'}}] if role == "assistant" else None,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["assistant", "tool"])
@pytest.mark.parametrize("stage_id,content,config,target", CASES, ids=[f"{case[0]}-{i}" for i, case in enumerate(CASES)])
async def test_every_reconstruction_preserves_non_content_fields(stage_id, content, config, target, role):
    stage = CustomRegexStage() if stage_id == "custom_regex" else StageRegistry.get_stage(stage_id)
    message = tool_message(role, content)
    messages = ([ChatMessage(role="user", content=BLOCK)] if target else []) + [message]
    messages += [ChatMessage(role="user", content="answer simple"), ChatMessage(role="assistant", content="recent")]
    original = [m.model_dump() for m in messages]
    result = await stage.compress(messages, config, CompressionContext(supports_vision=True, preserve_recent_turns=0))
    unavailable = stage_id in {"ccr", "omniglyph"}
    protected_target = unavailable or stage_id == "ultra" or (
        role == "tool" and stage_id in {"caveman", "llmlingua", "relevance", "aggressive", "custom_regex"}
    )
    if protected_target:
        # New fidelity contract protects complete tool data/call contents.
        assert result.messages[target].model_dump() == message.model_dump(), stage_id
        if unavailable:
            assert result.messages == messages
            assert not result.compressed
            assert result.warning  # No invented retrieval/image representation.
    else:
        assert result.compressed, stage_id
        assert result.messages[target].content != content
    assert result.messages[target].model_dump(exclude={"content"}) == message.model_dump(exclude={"content"})
    # Preserve every sibling's metadata, including when only a sibling advances.
    for before, after in zip(messages, result.messages):
        assert before.model_dump(exclude={"content"}) == after.model_dump(exclude={"content"})
    assert [m.model_dump() for m in messages] == original


@pytest.mark.asyncio
async def test_noop_reconstructions_survive_a_sibling_change():
    messages = [tool_message("assistant", [{"type": "text", "text": "unchanged"}]),
                tool_message("tool", "unique short text"),
                ChatMessage(role="user", content="trim me" + " " * 100)]
    for stage_id in ("lite", "session_dedup", "llmlingua", "ultra"):
        result = await StageRegistry.get_stage(stage_id).compress(messages, {}, CompressionContext())
        assert result.messages[0].model_dump() == messages[0].model_dump()
        assert result.messages[1].model_dump(exclude={"content"}) == messages[1].model_dump(exclude={"content"})


def pipeline_config(monkeypatch, records, **overrides):
    config = SimpleNamespace(enabled=True, trigger_token_threshold=0, preserve_recent_turns=0,
                             preserve_system_prompt_mode="never", min_savings_bailout_percent=0, fail_open=True)
    for key, value in overrides.items():
        setattr(config, key, value)
    monkeypatch.setattr(CompressionPipelineService, "get_global_settings", AsyncMock(return_value=config))
    monkeypatch.setattr(CompressionPipelineService, "get_stages", AsyncMock(return_value=records))


def stage_record(stage_id):
    return SimpleNamespace(id=stage_id, name=stage_id, icon="test", enabled=True, config_json={})


@pytest.mark.asyncio
async def test_pipeline_and_preview_preserve_tool_exchange(monkeypatch):
    pipeline_config(monkeypatch, [stage_record("lite"), stage_record("responses_tool")])
    messages = [tool_message("assistant", None), tool_message("tool", ARRAY),
                tool_message("assistant", [{"type": "text", "text": "unchanged"}])]
    output, summary = await CompressionPipelineService.optimize_messages(None, messages)
    preview = await CompressionPipelineService.preview_compression(None, messages)
    assert summary["compressed"]
    assert output[1].content != messages[1].content
    assert preview["compressed_messages"] == [m.model_dump() for m in output]
    for before, after in zip(messages, output):
        assert before.model_dump(exclude={"content"}) == after.model_dump(exclude={"content"})


@pytest.mark.asyncio
@pytest.mark.parametrize("bailout", [False, True])
async def test_pipeline_does_not_advance_noop_or_bailed_stage(monkeypatch, bailout):
    messages = [tool_message("assistant", None), tool_message("tool", ARRAY)]
    pipeline_config(monkeypatch, [stage_record("synthetic")], min_savings_bailout_percent=50 if bailout else 0)
    stage = SimpleNamespace(compress=AsyncMock(return_value=StageExecutionResult(
        stage_id="synthetic", stage_name="synthetic", messages=[ChatMessage(role="tool", content="lost")],
        compressed=bailout, savings_percent=1,
    )))
    monkeypatch.setattr(StageRegistry, "get_stage", Mock(return_value=stage))
    output, summary = await CompressionPipelineService.optimize_messages(None, messages)
    assert output == messages
    assert not summary["compressed"]
    assert not summary["breakdown"][0]["advanced"]
    if not bailout:
        preview = await CompressionPipelineService.preview_compression(None, messages)
        assert preview["compressed_messages"] == [m.model_dump() for m in messages]


@pytest.mark.asyncio
@pytest.mark.parametrize("timeout", [17.0, 120.0, 240.0])
@pytest.mark.parametrize("stream", [False, True])
async def test_direct_routing_uses_configured_timeout(monkeypatch, timeout, stream):
    monkeypatch.setattr(settings, "DEFAULT_TIMEOUT_SECONDS", timeout)
    provider = SimpleNamespace(adapter_type="synthetic", base_url="https://invalid.test", extra_headers={}, adapter_configuration={}, name="synthetic")
    credential = SimpleNamespace(provider=provider, encrypted_api_key="synthetic", proxy=None, id="synthetic", name="synthetic", metadata_json={})
    model = SimpleNamespace(provider_model_id="synthetic", display_name="synthetic")
    monkeypatch.setattr(engine.RoutingEngine, "_get_candidate_credentials_for_model", AsyncMock(return_value=[(credential, model)]))
    monkeypatch.setattr(engine, "decrypt_secret", Mock(return_value="synthetic"))
    monkeypatch.setattr(engine.circuit_breaker, "record_success", Mock())
    adapter = Mock()
    adapter.chat_completions = AsyncMock(return_value=ChatCompletionResponse(model="synthetic", choices=[]))
    seen = []

    async def stream_chat(**kwargs):
        seen.append(kwargs)
        yield "data: [DONE]\n\n"

    adapter.stream_chat = stream_chat
    monkeypatch.setattr(engine, "get_adapter", Mock(return_value=adapter))
    request = ChatCompletionRequest(model="synthetic", messages=[ChatMessage(role="user", content="offline")])
    if stream:
        chunks = [chunk async for chunk in engine.RoutingEngine.route_stream_chat(object(), request, record_log=False)]
        assert chunks[-1] == "data: [DONE]\n\n"
        assert seen[0]["timeout"] == timeout
    else:
        await engine.RoutingEngine.route_chat_completions(object(), request, record_log=False)
        assert adapter.chat_completions.await_args.kwargs["timeout"] == timeout
