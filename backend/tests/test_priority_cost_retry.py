"""Offline regressions for selected priorities 4, 5 and 9."""
import asyncio
import json
import math
from types import SimpleNamespace
from unittest.mock import AsyncMock
import uuid

import pytest
from app.core.database import AsyncSessionLocal
from app.core.errors import ErrorCategory, RouterException
from app.routing.engine import RoutingEngine
from app.schemas.chat import ChatCompletionRequest, ChatMessage, ChatCompletionResponse, ChatCompletionChoice, UsageInfo
from app.services.log_service import LogService, request_log_context


def request():
    return ChatCompletionRequest(model='synthetic/model', messages=[ChatMessage(role='user', content='offline')])


def parts(input_price=2.0, output_price=3.0):
    provider = SimpleNamespace(name='renamed provider', enabled=True, id=1, configuration={})
    model = SimpleNamespace(enabled=True, available=True, provider_id=1, provider_model_id='model',
        canonical_slug='synthetic/model', input_price_per_1m=input_price, output_price_per_1m=output_price, max_output_tokens=20)
    cred = SimpleNamespace(id=int(uuid.uuid4().hex[:8], 16), provider_id=1, enabled=True,
        rpm_limit=None, tpm_limit=None, max_concurrency=None)
    return provider, model, cred


def response():
    return ChatCompletionResponse(id='synthetic', created=1, model='model',
        choices=[ChatCompletionChoice(index=0, message=ChatMessage(role='assistant', content='ok'), finish_reason='stop')],
        usage=UsageInfo(prompt_tokens=10, completion_tokens=2, total_tokens=12))


@pytest.mark.parametrize('input_price,output_price,expected', [(2.0, 3.0, .000026), (0.0, 0.0, 0.0),
    (None, 3.0, None), (math.inf, 3.0, None), (True, 3.0, None)])
def test_dispatch_snapshots_known_and_unknown_price(input_price, output_price, expected):
    provider, model, _ = parts(input_price, output_price)
    with request_log_context():
        dispatch = LogService.start_dispatch(provider, model, request(), stream=False)
        model.input_price_per_1m = 999.0  # Later catalog changes cannot rewrite this call's price.
        LogService.dispatch_usage(dispatch, {'prompt_tokens': 10, 'completion_tokens': 2})
        assert dispatch['cost_usd'] == pytest.approx(expected) if expected is not None else dispatch['cost_usd'] is None
        assert dispatch['prices']['input_per_1m'] == (input_price if isinstance(input_price, (int, float)) and not isinstance(input_price, bool) and math.isfinite(input_price) else None)


@pytest.mark.asyncio
async def test_mixed_dispatch_prices_not_last_model_price():
    with request_log_context() as telemetry:
        for price in (2.0, 10.0):
            provider, model, _ = parts(price, price)
            dispatch = LogService.start_dispatch(provider, model, request(), stream=False)
            LogService.dispatch_usage(dispatch, {'prompt_tokens': 1_000_000, 'completion_tokens': 0})
            LogService.finish_dispatch(dispatch, 'SUCCESS', 1)
        async with AsyncSessionLocal() as db:
            row = await LogService.record_request_log(db, 'priority-cost-' + uuid.uuid4().hex, 'fusion/test',
                'FUSION', 'SUCCESS', 200, 1, input_price_per_1m=999.0)
        assert row.estimated_cost_usd == 12.0
        assert row.metadata_json['telemetry']['cost']['complete'] is True


@pytest.mark.asyncio
async def test_partial_dispatch_cost_not_reported_as_free():
    with request_log_context():
        for price in (2.0, None):
            provider, model, _ = parts(price, price)
            dispatch = LogService.start_dispatch(provider, model, request(), stream=False)
            LogService.dispatch_usage(dispatch, {'prompt_tokens': 1_000_000, 'completion_tokens': 0})
            LogService.finish_dispatch(dispatch, 'SUCCESS', 1)
        async with AsyncSessionLocal() as db:
            row = await LogService.record_request_log(db, 'priority-partial-' + uuid.uuid4().hex, 'route/test',
                'PRIORITY', 'SUCCESS', 200, 1, input_price_per_1m=999.0)
        cost = row.metadata_json['telemetry']['cost']
        assert row.estimated_cost_usd == 2.0 and cost['known_usd'] == 2.0
        assert cost['complete'] is False and cost['unknown_dispatches'] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('stream', [False, True])
async def test_retries_pause_and_release_before_second_attempt(monkeypatch, stream):
    import app.routing.engine as routing
    provider, model, cred = parts()
    calls = []
    async def chat(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise RouterException('transient', ErrorCategory.UPSTREAM_5XX, retry_after=.5)
        return response()
    async def chunks(**kwargs):
        await chat(**kwargs)
        yield 'data: {"choices":[{"delta":{"content":"ok"},"finish_reason":"stop"}]}\n\n'
        yield 'data: [DONE]\n\n'
    sleep = AsyncMock()
    monkeypatch.setattr(routing.asyncio, 'sleep', sleep)
    adapter = SimpleNamespace(chat_completions=chat, stream_chat=chunks)
    kwargs = {'request': request(), 'retry_count': 1, 'timeout': 10.0}
    if stream:
        assert [chunk async for chunk in RoutingEngine._dispatch_stream(adapter, cred, provider, model, **kwargs)]
    else:
        assert await RoutingEngine._dispatch_chat(adapter, cred, provider, model, **kwargs)
    assert len(calls) == 2 and sleep.await_count == 1
    assert sleep.await_args.args[0] >= .5


@pytest.mark.asyncio
async def test_started_stream_does_not_retry_or_pause(monkeypatch):
    import app.routing.engine as routing
    provider, model, cred = parts()
    calls = []
    async def chunks(**kwargs):
        calls.append(True)
        yield 'data: {"choices":[{"delta":{"content":"first"}}]}\n\n'
        raise RouterException('transient', ErrorCategory.UPSTREAM_5XX)
    sleep = AsyncMock()
    monkeypatch.setattr(routing.asyncio, 'sleep', sleep)
    with pytest.raises(RouterException):
        async for _ in RoutingEngine._dispatch_stream(SimpleNamespace(stream_chat=chunks), cred, provider, model,
                request=request(), retry_count=2, timeout=10):
            pass
    assert calls == [True] and sleep.await_count == 0


@pytest.mark.asyncio
async def test_retry_after_cannot_exceed_total_deadline(monkeypatch):
    import app.routing.engine as routing
    provider, model, cred = parts()
    calls = []
    async def chat(**kwargs):
        calls.append(True)
        raise RouterException('transient', ErrorCategory.UPSTREAM_5XX, retry_after=1000)
    sleep = AsyncMock()
    monkeypatch.setattr(routing.asyncio, 'sleep', sleep)
    with pytest.raises(RouterException):
        await RoutingEngine._dispatch_chat(SimpleNamespace(chat_completions=chat), cred, provider, model,
            request=request(), retry_count=2, timeout=.01)
    assert calls == [True] and sleep.await_count == 0


def test_payload_cache_markers_preserve_prefix_on_renamed_destination():
    from app.compression.caching_aware import should_preserve_system_prompt
    messages = [ChatMessage(role='system', content=[{'type': 'text', 'text': 'prefix', 'cache_control': {'type': 'ephemeral'}}])]
    assert should_preserve_system_prompt('when_caching', 'unusual-model', provider_name='unrelated', messages=messages)
    assert not should_preserve_system_prompt('never', 'unusual-model', messages=messages)
    assert should_preserve_system_prompt('when_caching', 'unknown', provider_name='anthropic')


@pytest.mark.asyncio
async def test_native_decision_uses_same_cost_and_retry_boundary(monkeypatch):
    import app.jev.engine as native
    import app.routing.engine as routing
    from app.jev.engine import JevEngine
    from app.schemas.jev import JevRequest
    provider, model, cred = parts()
    cred.encrypted_api_key = 'synthetic'
    calls = []
    async def call(*args):
        calls.append(True)
        if len(calls) == 1:
            raise RouterException('transient', ErrorCategory.UPSTREAM_5XX)
        return {'q': {'type': 'noul', 'answer': True, 'probability': 1}}, {'input_tokens': 10, 'output_tokens': 2}
    monkeypatch.setattr(JevEngine, '_is_native_jev_provider', staticmethod(lambda *args: True))
    monkeypatch.setattr(JevEngine, '_call_native_jev_upstream', call)
    monkeypatch.setattr(native, 'decrypt_secret', lambda value: 'synthetic')
    sleep = AsyncMock()
    monkeypatch.setattr(routing.asyncio, 'sleep', sleep)
    with request_log_context() as telemetry:
        await JevEngine._dispatch_decision(cred, provider, model,
            JevRequest(model='synthetic/model', state='offline', questions={'q': {'type': 'noul', 'instructions': 'ok'}}),
            None, 10, retry_count=1)
    assert sleep.await_count == 1 and len(telemetry['dispatches']) == 2
    assert telemetry['dispatches'][-1]['cost_usd'] == pytest.approx(.000026)

