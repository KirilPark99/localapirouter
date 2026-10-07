"""Gemini tool-history compatibility at the shared outbound payload boundary."""
import json
from unittest.mock import AsyncMock

import httpx
import pytest

from app.adapters.google import GoogleAIStudioAdapter
from app.adapters.openai import GenericOpenAIAdapter
from app.core.errors import RouterException
from app.core.http_client import http_client_manager
from app.modules.responses import messages_to_input
from app.schemas.chat import ChatCompletionRequest

MARKER = "skip_thought_signature_validator"
SIGNATURE = "synthetic-opaque-signature"


def history(signature=None):
    first = {"id": "call_first", "function": {"name": "skill_view", "arguments": "{}"},
             "extra_content": {"other": {"opaque": "keep"}}}
    if signature is not None:
        first["extra_content"]["google"] = {"thought_signature": signature, "opaque": "keep"}
    return ChatCompletionRequest(model="judge/hermes-judge", messages=[
        {"role": "user", "content": "Synthetic task"},
        {"role": "assistant", "tool_calls": [first,
            {"id": "call_parallel", "function": {"name": "lookup", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "call_first", "content": "first result"},
        {"role": "tool", "tool_call_id": "call_parallel", "content": "parallel result"},
        {"role": "assistant", "tool_calls": [{"id": "call_next", "function": {"name": "lookup", "arguments": "{}"},
            "extra_content": {"google": {"thought_signature": SIGNATURE}}}]},
        {"role": "tool", "tool_call_id": "call_next", "content": "next result"}],
        tools=[{"type": "function", "function": {"name": "skill_view", "parameters": {"type": "object"}}}],
        tool_choice="auto", parallel_tool_calls=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("adapter_cls", [GoogleAIStudioAdapter, GenericOpenAIAdapter])
async def test_gemini_signed_and_imported_history_on_both_transports(monkeypatch, stream, adapter_cls):
    captured = []
    def upstream(req):
        body = json.loads(req.content)
        captured.append(body)
        for message in body["messages"]:
            if message.get("tool_calls"):
                assert message["tool_calls"][0]["extra_content"]["google"]["thought_signature"]
        output = {"tool_calls": [{"id": "call_reply", "type": "function",
            "function": {"name": "lookup", "arguments": "{}"},
            "extra_content": {"google": {"thought_signature": SIGNATURE}}}]}
        if body["stream"]:
            event = {"choices": [{"index": 0, "delta": output, "finish_reason": "tool_calls"}]}
            return httpx.Response(200, text="data: " + json.dumps(event) + "\n\ndata: [DONE]\n\n")
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", **output}, "finish_reason": "tool_calls"}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as client:
        monkeypatch.setattr(http_client_manager, "get_client", AsyncMock(return_value=client))
        for signature in (None, SIGNATURE):
            request = history(signature)
            before = request.model_dump()
            kwargs = dict(base_url="https://generativelanguage.googleapis.com/v1beta/openai", api_key="synthetic",
                model_id="gemini-3.6-flash", request=request, extra_headers={}, configuration={})
            if stream:
                chunks = [chunk async for chunk in adapter_cls().stream_chat(**kwargs)]
                assert chunks[-1] == "data: [DONE]\n\n"
                assert json.loads(chunks[0][6:])["choices"][0]["delta"]["tool_calls"][0]["extra_content"]["google"]["thought_signature"] == SIGNATURE
            else:
                response = await adapter_cls().chat_completions(**kwargs)
                assert response.choices[0].message.tool_calls[0].extra_content["google"]["thought_signature"] == SIGNATURE
            body = captured[-1]
            calls = body["messages"][1]["tool_calls"]
            assert calls[0]["extra_content"]["google"]["thought_signature"] == (signature or MARKER)
            assert calls[0]["extra_content"]["other"] == {"opaque": "keep"}
            if signature:
                assert calls[0] == request.messages[1].tool_calls[0].model_dump(exclude_none=True)
            assert "extra_content" not in calls[1]
            assert body["messages"][4]["tool_calls"][0]["extra_content"]["google"]["thought_signature"] == SIGNATURE
            assert body["tools"] == request.tools and body["tool_choice"] == "auto" and body["parallel_tool_calls"] is True
            assert request.model_dump() == before


def test_resolved_model_gating_and_cross_provider_history():
    adapter = GenericOpenAIAdapter()
    request = history(SIGNATURE)
    before = request.model_dump()
    cli_before = messages_to_input(request.messages)
    for model in ("gpt-6.1-sol", "muse-spark-1.3-contributor-free", "kimi-k2.6", "claude-sonnet", "not-gemini-proxy"):
        payload = adapter._prepare_payload(model, request)
        first = payload["messages"][1]["tool_calls"][0]
        assert first["extra_content"] == {"other": {"opaque": "keep"}}
        assert "extra_content" not in payload["messages"][4]["tool_calls"][0]
        assert MARKER not in json.dumps(payload)
    unsigned = history()
    for model in ("models/gemini-3.6-flash", "google/gemini-3.6-flash"):
        payload = adapter._prepare_payload(model, unsigned)
        assert payload["messages"][1]["tool_calls"][0]["extra_content"]["google"]["thought_signature"] == MARKER
    assert request.model_dump() == before and messages_to_input(request.messages) == cli_before
    assert "extra_content" not in json.dumps(cli_before)
    plain = history()
    plain.messages[4].tool_calls[0].extra_content = None
    assert adapter._prepare_payload("gpt-6.1-sol", plain)["messages"] == [m.model_dump(exclude_none=True) for m in plain.messages]


@pytest.mark.parametrize("google", ["invalid", {"thought_signature": 123}])
def test_malformed_google_signature_is_a_request_error(google):
    request = history()
    request.messages[1].tool_calls[0].extra_content["google"] = google
    before = request.model_dump()
    with pytest.raises(RouterException) as caught:
        GenericOpenAIAdapter()._prepare_payload("gemini-3.6-flash", request)
    assert caught.value.status_code == 400 and request.model_dump() == before


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
async def test_direct_route_and_judge_use_resolved_gemini_boundary(monkeypatch, stream):
    from pathlib import Path
    from uuid import uuid4
    from app.core.database import AsyncSessionLocal, engine
    from app.core.crypto import encrypt_secret
    from app.models.entities import (Provider, ProviderCredential, DiscoveredModel,
        RoutingProfile, RoutingCandidate, JudgeProfile, JudgeCandidate)
    from app.routing.engine import RoutingEngine
    from app.judge.engine import JudgeEngine

    fixture = Path(engine.url.database).resolve()
    assert fixture == Path(AsyncSessionLocal.kw["bind"].url.database).resolve()
    assert fixture.name.startswith("myairouter_test_")
    slug = "gemini-history-" + uuid4().hex
    captured = []
    def upstream(req):
        body = json.loads(req.content)
        captured.append(body)
        assert body["model"] == "gemini-3.6-flash"
        assert body["messages"][1]["tool_calls"][0]["extra_content"]["google"]["thought_signature"] == MARKER
        assert body["messages"][4]["tool_calls"][0]["extra_content"]["google"]["thought_signature"] == SIGNATURE
        if body["stream"]:
            return httpx.Response(200, text='data: {"choices":[{"index":0,"delta":{"content":"ok"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n')
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}]})
    async with AsyncSessionLocal() as db, httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as client:
        provider = Provider(name=slug, slug=slug, adapter_type="google", base_url="https://generativelanguage.googleapis.com/v1beta/openai")
        db.add(provider)
        await db.flush()
        credential = ProviderCredential(provider_id=provider.id, name=slug,
            encrypted_api_key=encrypt_secret("synthetic"), key_fingerprint=slug, masked_key="synthetic")
        db.add(credential)
        await db.flush()
        model = DiscoveredModel(provider_id=provider.id, credential_id=credential.id,
            provider_model_id="gemini-3.6-flash", display_name=slug, canonical_slug=slug)
        route = RoutingProfile(name=slug, slug=slug, retry_count=0)
        judge = JudgeProfile(name=slug, slug=slug)
        db.add_all([model, route, judge])
        await db.flush()
        target = dict(provider_id=provider.id, credential_id=credential.id, model_id=model.id)
        db.add_all([RoutingCandidate(profile_id=route.id, **target), JudgeCandidate(profile_id=judge.id, **target)])
        await db.commit()
        monkeypatch.setattr(http_client_manager, "get_client", AsyncMock(return_value=client))
        for alias in (slug, "route/" + slug, "judge/" + slug):
            request = history()
            request.model = alias
            before = request.model_dump()
            is_judge = alias.startswith("judge/")
            if stream:
                source = JudgeEngine.execute_judge_stream(db, request) if is_judge else RoutingEngine.route_stream_chat(db, request)
                chunks = [chunk async for chunk in source]
                assert "[DONE]" in "".join(chunks) and '"error"' not in "".join(chunks)
            else:
                response = await (JudgeEngine.execute_judge(db, request) if is_judge else RoutingEngine.route_chat_completions(db, request))
                assert response.choices[0].message.content == "ok"
            assert request.model_dump() == before
        assert len(captured) == 3
