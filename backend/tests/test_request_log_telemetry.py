"""Request-local telemetry: real dispatch/log paths, offline transports, no live data."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select

from app.api.deps import get_inference_key_dep
from app.api.v1.router import router
from app.compression.pipeline import CompressionPipelineService
from app.compression.tokenizer import count_messages_tokens
from app.core.crypto import encrypt_secret
from app.core.database import AsyncSessionLocal, engine
from app.core.http_client import http_client_manager
from app.models.entities import (DiscoveredModel, FusionParticipant, FusionProfile, JudgeCandidate, JudgeProfile,
    Provider, ProviderCredential, RequestLog, RouterApiKey, RoutingCandidate, RoutingProfile)
from app.services.log_service import LogService, request_log_context, request_telemetry


async def seed(db):
    fixture = Path(engine.url.database).resolve()
    assert fixture == Path(AsyncSessionLocal.kw['bind'].url.database).resolve()
    assert fixture.name.startswith('myairouter_test_')
    slug = 'log-telemetry-' + uuid4().hex
    provider = Provider(name=slug, slug=slug, adapter_type='openai', base_url='https://synthetic.invalid/v1')
    db.add(provider)
    await db.flush()
    credential = ProviderCredential(provider_id=provider.id, name=slug,
        encrypted_api_key=encrypt_secret('synthetic'), key_fingerprint=slug, masked_key='synthetic')
    db.add(credential)
    await db.flush()
    model = DiscoveredModel(provider_id=provider.id, credential_id=credential.id,
        provider_model_id='synthetic-model', display_name=slug, canonical_slug=slug, reasoning_effort='high')
    route = RoutingProfile(name=slug, slug=slug + '-route', retry_count=0)
    judge = JudgeProfile(name=slug, slug=slug + '-judge')
    db.add_all([model, route, judge])
    await db.flush()
    target = dict(provider_id=provider.id, credential_id=credential.id, model_id=model.id)
    db.add_all([RoutingCandidate(profile_id=route.id, thinking_effort='max', **target),
                JudgeCandidate(profile_id=judge.id, thinking_effort='max', **target)])
    await db.commit()
    return slug


@pytest.mark.asyncio
@pytest.mark.parametrize('stream', [False, True])
@pytest.mark.parametrize('cache_count', [None, 0, 60])
async def test_api_dispatch_and_logs_preserve_usage_compression_and_effort(monkeypatch, stream, cache_count):
    usage = {'prompt_tokens': 100, 'completion_tokens': 12, 'total_tokens': 112,
             'completion_tokens_details': {'reasoning_tokens': 4}}
    if cache_count is not None:
        usage['prompt_tokens_details'] = {'cached_tokens': cache_count}
    captured = []
    def upstream(req):
        body = json.loads(req.content)
        captured.append(body)
        assert body['messages'][0]['content'] == 'short'
        if body['stream']:
            event = {'choices': [{'index': 0, 'delta': {'content': 'ok'}, 'finish_reason': 'stop'}], 'usage': usage}
            # Repeated usage is cumulative, not extra billed tokens.
            return httpx.Response(200, text='data: ' + json.dumps(event) + '\n\ndata: ' + json.dumps({'choices': [], 'usage': usage}) + '\n\ndata: [DONE]\n\n')
        return httpx.Response(200, json={'choices': [{'message': {'role': 'assistant', 'content': 'ok'}, 'finish_reason': 'stop'}], 'usage': usage})
    async def compression(**kwargs):
        before = count_messages_tokens(kwargs['messages'])
        messages = [message.model_copy(update={'content': 'short'}) for message in kwargs['messages']]
        after = count_messages_tokens(messages)
        return messages, {'compressed': True, 'tokens_before': before, 'tokens_after': after,
            'tokens_saved': before - after, 'savings_percent': 50, 'token_count_is_estimate': True,
            'breakdown': [{'stage_id': 'synthetic', 'stage_name': 'Synthetic', 'tokens_before': before,
                           'tokens_after': after, 'advanced': True, 'rules': ['PRIVATE-RULE-CONTENT']}]}
    monkeypatch.setattr(CompressionPipelineService, 'get_global_settings', AsyncMock(return_value=SimpleNamespace(fail_open=True, enable_telemetry=True)))
    monkeypatch.setattr(CompressionPipelineService, 'optimize_messages', compression)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_inference_key_dep] = lambda: None
    async with AsyncSessionLocal() as db, httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as provider_client:
        slug = await seed(db)
        monkeypatch.setattr(http_client_manager, 'get_client', AsyncMock(return_value=provider_client))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fixture') as client:
            for alias, effort in ((slug, 'high'), ('route/' + slug + '-route', 'max'), ('judge/' + slug + '-judge', 'max')):
                response = await client.post('/v1/chat/completions', json={'model': alias,
                    'messages': [{'role': 'user', 'content': 'PRIVATE-PROMPT ' * 100}], 'stream': stream})
                assert response.status_code == 200 and '"error"' not in response.text
                log = await db.scalar(select(RequestLog).where(RequestLog.requested_model == alias).order_by(RequestLog.id.desc()))
                assert log is not None
                details = log.metadata_json['telemetry']
                assert details['compression']['tokens_saved'] > 0
                assert details['compression']['token_count_is_estimate'] is True
                dispatch = details['dispatches'][-1]
                assert dispatch['status'] == 'SUCCESS' and dispatch['parameters']['reasoning_effort'] == effort
                assert dispatch['parameters']['reasoning_source'] == 'defaults'
                assert dispatch['usage']['input_tokens'] == 100 and dispatch['usage']['output_tokens'] == 12
                assert dispatch['usage']['cached_tokens'] == cache_count
                assert dispatch['usage']['new_tokens'] == (None if cache_count is None else 100 - cache_count)
                assert details['usage']['source'] == 'upstream' and details['usage']['reasoning_tokens'] == 4
                assert details['usage']['new_tokens'] == dispatch['usage']['new_tokens']
                assert log.cached_tokens == (cache_count or 0) and log.reasoning_tokens == 4
                assert log.prompt_content is None and 'PRIVATE' not in json.dumps(log.metadata_json)
                assert request_telemetry.get() is None
        assert len(captured) == 3


@pytest.mark.asyncio
async def test_log_trace_concurrency_unknowns_and_snapshots():
    async def record(label, cached):
        with request_log_context() as details:
            call = {'provider': label, 'model': label, 'parameters': {}, 'status': 'SUCCESS', 'usage': None}
            details['dispatches'].append(call)
            usage = {'prompt_tokens': 10, 'completion_tokens': 2}
            if cached is not None:
                usage['prompt_tokens_details'] = {'cached_tokens': cached}
            LogService.dispatch_usage(call, usage)
            await asyncio.sleep(0)
            async with AsyncSessionLocal() as db:
                row = await LogService.record_request_log(db=db, request_id=uuid4().hex,
                    requested_model=label, mode='DIRECT', status='SUCCESS', status_code=200,
                    latency_ms=1, input_tokens=10, output_tokens=2, metadata_json={'existing': 'keep'})
                call['parameters']['after_snapshot'] = True
                assert row.metadata_json['existing'] == 'keep'
                assert row.metadata_json['telemetry']['dispatches'][0]['provider'] == label
                assert 'after_snapshot' not in json.dumps(row.metadata_json)
                assert row.metadata_json['telemetry']['usage']['new_tokens'] == (None if cached is None else 10 - cached)
                assert row.metadata_json['telemetry']['usage']['reasoning_tokens'] is None
    await asyncio.gather(record('first', 0), record('second', None))
    assert request_telemetry.get() is None


@pytest.mark.asyncio
@pytest.mark.parametrize('stream', [False, True])
async def test_multicall_judge_fusion_and_local_response_cache(monkeypatch, stream):
    usage = {'prompt_tokens': 100, 'completion_tokens': 12, 'total_tokens': 112,
             'prompt_tokens_details': {'cached_tokens': 60}, 'completion_tokens_details': {'reasoning_tokens': 4}}
    def upstream(req):
        body = json.loads(req.content)
        evaluating = 'expert AI Routing Judge' in str(body['messages'])
        text = json.dumps({'selected_candidate_index': 0}) if evaluating else 'ok'
        if body['stream']:
            event = {'choices': [{'index': 0, 'delta': {'content': text}, 'finish_reason': 'stop'}], 'usage': usage}
            return httpx.Response(200, text='data: ' + json.dumps(event) + '\n\ndata: [DONE]\n\n')
        return httpx.Response(200, json={'choices': [{'message': {'role': 'assistant', 'content': text}, 'finish_reason': 'stop'}], 'usage': usage})
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_inference_key_dep] = lambda: None
    async with AsyncSessionLocal() as db, httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as provider_client:
        slug = await seed(db)
        model = await db.scalar(select(DiscoveredModel).where(DiscoveredModel.canonical_slug == slug))
        target = dict(provider_id=model.provider_id, credential_id=model.credential_id, model_id=model.id)
        judge = await db.scalar(select(JudgeProfile).where(JudgeProfile.slug == slug + '-judge'))
        judge.judge_provider_id, judge.judge_credential_id, judge.judge_model_id = model.provider_id, model.credential_id, model.id
        fusion = FusionProfile(name=slug, slug=slug + '-fusion', judge_provider_id=model.provider_id,
            judge_credential_id=model.credential_id, judge_model_id=model.id, judge_thinking_effort='high')
        db.add_all([fusion, JudgeCandidate(profile_id=judge.id, **target)])
        await db.flush()
        db.add_all([FusionParticipant(profile_id=fusion.id, thinking_effort=effort, **target) for effort in ('low', 'high')])
        await db.commit()
        monkeypatch.setattr(http_client_manager, 'get_client', AsyncMock(return_value=provider_client))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fixture') as client:
            for alias, count in (('judge/' + judge.slug, 2), ('fusion/' + fusion.slug, 3)):
                result = await client.post('/v1/chat/completions', json={'model': alias, 'stream': stream,
                    'messages': [{'role': 'user', 'content': 'hello'}]})
                assert result.status_code == 200 and '"error"' not in result.text, result.text
                row = await db.scalar(select(RequestLog).where(RequestLog.requested_model == alias).order_by(RequestLog.id.desc()))
                details = row.metadata_json['telemetry']
                assert len(details['dispatches']) == count
                assert all(call['status'] == 'SUCCESS' for call in details['dispatches'])
                assert details['usage'] == dict(input_tokens=count * 100, output_tokens=count * 12,
                    cached_tokens=count * 60, new_tokens=count * 40, reasoning_tokens=count * 4, source='upstream')
                assert not any(call['parameters']['reasoning_source'] == 'client' for call in details['dispatches'])
            principal = RouterApiKey(name=slug, key_prefix='synthetic', key_hash=slug, masked_key='synthetic', permissions=['direct'], allowed_models=['*'])
            db.add(principal)
            await db.commit()
            app.dependency_overrides[get_inference_key_dep] = lambda: principal
            data = {'model': slug, 'temperature': 0, 'stream': stream, 'reasoning_effort': 'low',
                    'messages': [{'role': 'user', 'content': 'unique-cache-message'}]}
            for _ in range(2):
                result = await client.post('/v1/chat/completions', json=data)
                assert result.status_code == 200, result.text
            assert result.headers.get('x-cache') == 'HIT'
            row = await db.scalar(select(RequestLog).where(RequestLog.requested_model == slug).order_by(RequestLog.id.desc()))
            details = row.metadata_json['telemetry']
            assert row.mode == 'CACHE' and details['dispatches'] == []
            assert details['usage']['source'] == 'local_response_cache'
            assert details['usage']['input_tokens'] == details['usage']['output_tokens'] == 0
            assert details['usage']['cached_tokens'] is None and details['usage']['new_tokens'] is None
            assert details['saved_response_usage']['input_tokens'] == 100
    assert request_telemetry.get() is None


def test_malformed_cache_counts_and_client_reasoning_source():
    from app.schemas.chat import ChatCompletionRequest, ChatMessage
    request = ChatCompletionRequest(model='test', reasoning_effort='high', messages=[ChatMessage(role='user', content='hello')])
    provider = SimpleNamespace(name='test', configuration={'module_id': 'codex_cli'})
    model = SimpleNamespace(provider_model_id='test')
    with request_log_context() as details:
        details['requested_parameters'] = LogService.request_parameters(request)
        call = LogService.start_dispatch(provider, model, request, stream=False)
        assert call is not None
        assert call['parameters']['reasoning_source'] == 'client'
        assert call['parameters']['thinking_budget_tokens'] is None
        for cache in (True, -1, 20, '10'):
            LogService.dispatch_usage(call, {'prompt_tokens': 10, 'completion_tokens': 2, 'prompt_tokens_details': {'cached_tokens': cache}})
            assert call['usage']['new_tokens'] is None
        LogService.dispatch_usage(call, {'prompt_tokens': 10, 'completion_tokens': 2,
            'prompt_tokens_details': 'malformed', 'completion_tokens_details': 1})
        assert call['usage']['cached_tokens'] is call['usage']['reasoning_tokens'] is None


def test_parameter_telemetry_never_stores_arbitrary_reasoning():
    from app.schemas.chat import ChatCompletionRequest, ChatMessage
    for fields in ({'reasoning': {'effort': {'secret': 'PRIVATE-SENTINEL'}}},
                   {'reasoning_effort': 'PRIVATE-SENTINEL'},
                   {'thinking': {'budget_tokens': {'secret': 'PRIVATE-SENTINEL'}}}):
        request = ChatCompletionRequest(model='test', messages=[ChatMessage(role='user', content='hello')], **fields)
        parameters = LogService.request_parameters(request)
        assert 'PRIVATE' not in json.dumps(parameters)
        assert parameters['reasoning_effort'] is None


@pytest.mark.asyncio
@pytest.mark.parametrize('other_unknown', [False, True])
async def test_failed_dispatch_known_usage_is_counted_and_partial_is_labelled(other_unknown):
    with request_log_context() as details:
        call = {'status': 'FAILED', 'usage': None}
        details['dispatches'].append(call)
        LogService.dispatch_usage(call, {'prompt_tokens': 100, 'completion_tokens': 12,
            'prompt_tokens_details': {'cached_tokens': 60}, 'completion_tokens_details': {'reasoning_tokens': 4}})
        if other_unknown:
            details['dispatches'].append({'status': 'CANCELLED', 'usage': None})
        async with AsyncSessionLocal() as db:
            row = await LogService.record_request_log(db=db, request_id=uuid4().hex, requested_model='test',
                mode='DIRECT', status='FAILED', status_code=502, latency_ms=1)
            usage = row.metadata_json['telemetry']['usage']
            assert usage['input_tokens'] == 100 and usage['output_tokens'] == 12
            assert usage['source'] == ('upstream_partial' if other_unknown else 'upstream')
            assert usage['new_tokens'] == (None if other_unknown else 40)


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['DIRECT', 'PRIORITY', 'JUDGE', 'FUSION'])
@pytest.mark.parametrize('wire', ['chat/completions', 'responses', 'messages'])
@pytest.mark.parametrize('outcome', ['complete', 'cleanup_error', 'incomplete'])
async def test_stream_terminal_waits_for_cleanup_and_journal(monkeypatch, mode, wire, outcome):
    """Real ASGI disconnect at the wire terminal must not cancel the journal write."""
    cleaned, sent = [], []
    disconnected = asyncio.Event()
    usage = {'prompt_tokens': 10, 'completion_tokens': 2, 'total_tokens': 12}
    delta = {'content': 'ok', 'reasoning_content': 'reasoning-ok', 'tool_calls': [
        {'index': 0, 'id': 'call_synthetic', 'type': 'function',
         'function': {'name': 'clock', 'arguments': '{}'}}]}

    class Upstream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield ('data: ' + json.dumps({'choices': [{'index': 0, 'delta': delta,
                'finish_reason': None if outcome == 'incomplete' else 'tool_calls'}], 'usage': usage}) + '\n\n').encode()
            if outcome == 'incomplete':
                return
            yield b'data: [DONE]\n\n'

        async def aclose(self):
            await asyncio.sleep(0)  # The real Lingling cleanup also awaits after [DONE].
            cleaned.append(True)
            if outcome == 'cleanup_error':
                raise httpx.ReadError('synthetic post-terminal cleanup failure')

    def upstream(req):
        body = json.loads(req.content)
        if body.get('stream'):
            return httpx.Response(200, stream=Upstream())
        text = json.dumps({'selected_candidate_index': 0}) if 'expert AI Routing Judge' in str(body['messages']) else 'ok'
        return httpx.Response(200, json={'choices': [{'message': {'role': 'assistant', 'content': text},
            'finish_reason': 'stop'}], 'usage': usage})

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_inference_key_dep] = lambda: None
    async with AsyncSessionLocal() as db, httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as provider_client:
        slug = await seed(db)
        model = await db.scalar(select(DiscoveredModel).where(DiscoveredModel.canonical_slug == slug))
        fusion = FusionProfile(name=slug, slug=slug + '-fusion', judge_provider_id=model.provider_id,
            judge_credential_id=model.credential_id, judge_model_id=model.id)
        db.add(fusion)
        await db.flush()
        db.add_all([FusionParticipant(profile_id=fusion.id, provider_id=model.provider_id,
            credential_id=model.credential_id, model_id=model.id) for _ in range(2)])
        await db.commit()
        alias = {'DIRECT': slug, 'PRIORITY': 'route/' + slug + '-route',
                 'JUDGE': 'judge/' + slug + '-judge', 'FUSION': 'fusion/' + slug + '-fusion'}[mode]
        monkeypatch.setattr(http_client_manager, 'get_client', AsyncMock(return_value=provider_client))
        body = {'model': alias, 'stream': True, 'max_tokens': 512}
        body.update({'input': 'hello'} if wire == 'responses' else {'messages': [{'role': 'user', 'content': 'hello'}]})
        pending_body = json.dumps(body).encode()

        async def receive():
            nonlocal pending_body
            if pending_body is not None:
                data, pending_body = pending_body, None
                return {'type': 'http.request', 'body': data, 'more_body': False}
            await disconnected.wait()
            return {'type': 'http.disconnect'}

        async def send(message):
            if message['type'] == 'http.response.start':
                assert message['status'] == 200
                return
            text = message.get('body', b'').decode()
            sent.append(text)
            terminal = ('data: [DONE]' in text if wire == 'chat/completions' else
                        'event: response.completed' in text or 'event: response.failed' in text if wire == 'responses' else
                        'event: message_stop' in text or 'event: error' in text)
            if terminal:
                assert cleaned, 'terminal escaped before upstream cleanup'
                rows = (await db.scalars(select(RequestLog).where(RequestLog.requested_model == alias))).all()
                assert len(rows) == 1, 'terminal escaped before journal commit (or duplicate row)'
                expected = 'FUSION_SUCCESS' if mode == 'FUSION' else 'SUCCESS'
                assert rows[0].status == (expected if outcome == 'complete' else 'FAILED')
                assert rows[0].mode == mode
                disconnected.set()  # Client closes immediately after the terminal, like an SDK.

        await asyncio.wait_for(app({'type': 'http', 'asgi': {'version': '3.0', 'spec_version': '2.0'},
            'http_version': '1.1', 'method': 'POST', 'scheme': 'http', 'path': '/v1/' + wire,
            'raw_path': ('/v1/' + wire).encode(), 'query_string': b'',
            'headers': [(b'content-type', b'application/json')],
            'server': ('fixture', 80), 'client': ('fixture', 1234)}, receive, send), timeout=10)
        text = ''.join(sent)
        assert disconnected.is_set(), text
        rows = (await db.scalars(select(RequestLog).where(RequestLog.requested_model == alias))).all()
        assert len(rows) == 1 and cleaned
        assert 'call_synthetic' in text and 'ok' in text
        data = [json.loads(line[6:]) for line in text.splitlines()
                if line.startswith('data: ') and line[6:] != '[DONE]']
        assert any(item.get('error') or item.get('type') == 'response.failed' for item in data) == (outcome != 'complete')
        if wire == 'chat/completions':
            assert text.count('data: [DONE]') == 1
            assert 'reasoning-ok' in text and '"prompt_tokens"' in text
