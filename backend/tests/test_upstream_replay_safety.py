"""Offline replay fences; run with isolated settings and --noconftest."""
import asyncio
import time
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.errors import ErrorCategory as Cat, RouterException, normalize_upstream_error
from app.routing.engine import RoutingEngine as Router
from app.jev.engine import JevEngine
from app.judge.engine import JudgeEngine
from app.schemas.chat import ChatCompletionRequest, ChatMessage
from app.schemas.jev import JevRequest


def request():
    return ChatCompletionRequest(model='synthetic/model', messages=[ChatMessage(role='user', content='offline')])


@pytest.fixture
def parts(monkeypatch):
    import app.routing.engine as routing
    import app.jev.engine as jev
    import app.judge.engine as judge
    provider = NS(id=1, name='synthetic', enabled=True, adapter_type='custom_module',
                  base_url='https://invalid.test', configuration={}, adapter_configuration={}, extra_headers={})
    model = NS(id=1, enabled=True, available=True, provider_id=1, provider=provider,
               provider_model_id='model', canonical_slug='synthetic/model', display_name='model',
               reasoning_effort=None, temperature=None, capabilities={}, max_output_tokens=10)
    creds = [NS(id=i, name='synthetic', provider=provider, enabled=True, provider_id=1,
                encrypted_api_key='synthetic', proxy=None) for i in (1, 2)]
    monkeypatch.setattr(Router, '_eligible', staticmethod(lambda *a: True))
    monkeypatch.setattr(Router, '_pause_retry', AsyncMock(return_value=True))
    monkeypatch.setattr(routing.circuit_breaker, 'is_available', lambda *a: (True, 'ok'))
    monkeypatch.setattr(routing.circuit_breaker, 'record_failure', lambda *a: None)
    monkeypatch.setattr(routing.circuit_breaker, 'record_success', lambda *a: None)
    async def reserve(c, p, m, req):
        return NS(finish=lambda *a: None), req.model_copy(), None
    monkeypatch.setattr(Router, '_reserve_dispatch', reserve)
    monkeypatch.setattr(routing.LogService, 'start_dispatch', lambda *a, **kw: None)
    monkeypatch.setattr(routing.LogService, 'finish_dispatch', lambda *a: None)
    monkeypatch.setattr(routing.LogService, 'dispatch_usage', lambda *a: None)
    monkeypatch.setattr(routing.LogService, 'record_request_log', AsyncMock())
    monkeypatch.setattr(routing.CredentialService, 'module_runtime_configuration', lambda *a: {})
    for module in (routing, jev, judge):
        monkeypatch.setattr(module, 'decrypt_secret', lambda *a: 'synthetic')
    return provider, model, creds


@pytest.mark.parametrize('category', list(Cat))
def test_error_policy(category):
    safe = RouterException('synthetic', category)
    assert safe.replay_safe is True
    assert safe.is_retryable == category.is_retryable
    assert safe.is_fallback_eligible == category.is_fallback_eligible
    unsafe = RouterException('synthetic', category, replay_safe=False)
    assert not unsafe.is_retryable and not unsafe.is_fallback_eligible
    assert unsafe.to_openai_dict() == safe.to_openai_dict()


@pytest.mark.parametrize('stream', [False, True])
@pytest.mark.parametrize('submitted', [False, True])
@pytest.mark.parametrize('failure', ['typed', 'network', 'timeout', 'auth', 'rate'])
def test_dispatch_fences_actual_request(parts, stream, submitted, failure):
    provider, model, creds = parts
    original = request()
    seen = []
    async def chat(**kw):
        seen.append(kw['request'])
        assert kw['request'] is not original  # Reservation can replace it.
        if submitted:
            object.__setattr__(kw['request'], '_upstream_submission_started', True)
        if failure == 'timeout':
            await asyncio.Event().wait()  # Router's deadline, not provider timeout.
        if failure == 'network':
            raise httpx.ReadError('ambiguous')
        raise RouterException('synthetic', {'typed': Cat.UPSTREAM_5XX, 'auth': Cat.AUTH_ERROR,
                                          'rate': Cat.RATE_LIMIT}[failure])
    async def chunks(**kw):
        await chat(**kw)
        yield 'unreachable'
    adapter = NS(chat_completions=chat, stream_chat=chunks, normalize_error=normalize_upstream_error)
    async def run():
        with pytest.raises(RouterException) as caught:
            if stream:
                _ = [c async for c in Router._dispatch_stream(adapter, creds[0], provider, model,
                     request=original, retry_count=1, timeout=.01 if failure == 'timeout' else 1)]
            else:
                await Router._dispatch_chat(adapter, creds[0], provider, model,
                     request=original, retry_count=1, timeout=.01 if failure == 'timeout' else 1)
        assert caught.value.replay_safe is not submitted
        assert len(seen) == (1 if submitted or failure in ('auth', 'rate') else 2)
        assert not getattr(original, '_upstream_submission_started', False)
    asyncio.run(run())


@pytest.mark.parametrize('stream', [False, True])
@pytest.mark.parametrize('path', ['direct', 'priority', 'nested', 'winner'])
@pytest.mark.parametrize('submitted', [False, True])
@pytest.mark.parametrize('category', [Cat.UPSTREAM_5XX, Cat.AUTH_ERROR])
def test_chat_fallbacks(parts, monkeypatch, stream, path, submitted, category):
    import app.routing.engine as routing
    import app.judge.engine as judge
    provider, model, creds = parts
    calls = []
    async def chat(**kw):
        calls.append(True)
        if len(calls) == 1:
            if submitted:
                object.__setattr__(kw['request'], '_upstream_submission_started', True)
            raise RouterException('synthetic', category)
        return NS(usage=None, model='model')
    async def chunks(**kw):
        await chat(**kw)
        yield 'data: [DONE]\n\n'
    adapter = NS(chat_completions=chat, stream_chat=chunks, normalize_error=normalize_upstream_error)
    monkeypatch.setattr(routing, 'get_adapter', lambda *a: adapter)
    monkeypatch.setattr(judge, 'get_adapter', lambda *a: adapter)
    monkeypatch.setattr(Router, '_get_candidate_credentials_for_model', AsyncMock(return_value=[(c, model) for c in creds]))
    monkeypatch.setattr(Router, '_candidate_credentials', AsyncMock(return_value=creds))
    import app.routing.cache_affinity as affinity
    monkeypatch.setattr(affinity, 'apply_prompt_cache_affinity', lambda pairs, req: (pairs, None))
    cand = NS(candidate_type='model', target_profile_id=None, target_profile=None, is_active=True,
              provider=provider, model=model, credential_id=None, credential_group=None,
              temperature=None, thinking_effort=None, priority_order=0)
    profile = NS(id=1, slug='root', name='root', enabled=True, candidates=[cand], strategy='priority',
                 randomize_keys=False, retry_count=0, timeout_seconds=1, fallback_conditions=None,
                 temperature=None, thinking_effort=None)
    child = NS(**{**vars(profile), 'id': 2, 'slug': 'child'})
    if path == 'nested':
        profile.candidates = [NS(candidate_type='profile', target_profile_id=2, target_profile=child,
                                 is_active=True, priority_order=0), cand]
    monkeypatch.setattr(routing.RoutingService, 'get_profile_by_slug', AsyncMock(side_effect=lambda db, slug: child if slug == 'route/child' else profile))
    async def run():
        req = request()
        async def invoke():
            if path == 'winner':
                result = await JudgeEngine._winner_dispatch(None, cand, req, 1, stream=stream)
            elif path == 'direct':
                result = (Router._handle_direct_stream if stream else Router._handle_direct_route)(
                    None, req, req.model, None, 'req_offline', time.perf_counter(), record_log=False)
            else:
                result = (Router._handle_priority_stream if stream else Router._handle_priority_route)(
                    None, req, 'route/root', None, 'req_offline', time.perf_counter(), record_log=False)
            if stream:
                return [c async for c in result]
            return await result if path != 'winner' else result
        if submitted or (path == 'winner' and category == Cat.AUTH_ERROR):
            with pytest.raises(RouterException) as caught:
                await invoke()
            assert caught.value.replay_safe is not submitted and len(calls) == 1
        else:
            assert await invoke()
            assert len(calls) == 2
    asyncio.run(run())


@pytest.mark.parametrize('profile', [False, True])
@pytest.mark.parametrize('category', list(Cat))
@pytest.mark.parametrize('replay_safe', [False, True])
def test_jev_legacy_policy_and_replay_fence(parts, monkeypatch, profile, category, replay_safe):
    import app.jev.engine as jev
    provider, model, creds = parts
    error = RouterException('synthetic', category, replay_safe=replay_safe)
    dispatch = AsyncMock(side_effect=error)
    monkeypatch.setattr(JevEngine, '_dispatch_decision', dispatch)
    monkeypatch.setattr(JevEngine, '_is_native_jev_provider', lambda *a: False)
    monkeypatch.setattr(JevEngine, '_get_candidates_for_model', AsyncMock(return_value=[(c, model) for c in creds]))
    monkeypatch.setattr(Router, '_candidate_credentials', AsyncMock(return_value=creds))
    cand = NS(is_active=True, provider=provider, model=model, credential_id=None, credential_group=None, priority_order=0)
    route = NS(id=1, name='offline', candidates=[cand, cand], randomize_keys=False, strategy='priority',
               fallback_conditions=None, timeout_seconds=1, retry_count=0)
    from app.services.routing_service import RoutingService
    monkeypatch.setattr(RoutingService, 'get_profile_by_slug', AsyncMock(return_value=route))
    req = JevRequest(model='synthetic/model', state='offline', questions={'q': {'type': 'noul'}})
    async def run():
        with pytest.raises(RouterException) as caught:
            await (JevEngine._handle_profile_decision if profile else JevEngine._handle_direct_decision)(
                None, req, req.model, None, 'req_offline', time.perf_counter(), record_log=False)
        expected = (4 if profile else 2) if replay_safe and (not profile or category.is_fallback_eligible) else 1
        assert caught.value is error and dispatch.await_count == expected
    asyncio.run(run())


@pytest.mark.parametrize('submitted', [False, True])
@pytest.mark.parametrize('stage', ['dispatch', 'parse'])
def test_judge_evaluation_preserves_only_safe_fallback(parts, monkeypatch, submitted, stage):
    import app.judge.engine as judge
    provider, model, creds = parts
    candidate = NS(candidate_type='model', target_profile=None, model=model, label='offline',
                   task_types=[], description=None, thinking_effort=None, complexity_level='low')
    profile = NS(judge_type='model', judge_model=model, judge_provider=provider,
                 judge_credential_id=None, judge_credential_group=None, fallback_candidate_id=None,
                 strategy='offline', system_prompt=None, judge_temperature=None, timeout_seconds=1)
    monkeypatch.setattr(Router, '_candidate_credentials', AsyncMock(return_value=creds))
    async def chat(**kw):
        if submitted:
            object.__setattr__(kw['request'], '_upstream_submission_started', True)
        if stage == 'dispatch':
            raise RouterException('ambiguous', Cat.UPSTREAM_5XX)
        return NS(usage=None, choices=[NS(message=NS(content='invalid json'))])
    monkeypatch.setattr(judge, 'get_adapter', lambda *a: NS(chat_completions=chat))
    async def run():
        if submitted:
            with pytest.raises(RouterException) as caught:
                await JudgeEngine.evaluate_judge(None, profile, 'offline', [candidate, candidate], 'req_offline')
            assert not caught.value.replay_safe
        else:
            assert (await JudgeEngine.evaluate_judge(None, profile, 'offline', [candidate, candidate], 'req_offline'))[3] == 'FALLBACK'
    asyncio.run(run())


@pytest.mark.parametrize('stream', [False, True])
def test_custom_bridge_keeps_request_identity(parts, monkeypatch, stream):
    from app.adapters.module_adapter import CustomModuleAdapter, ModuleLoader
    provider, model, creds = parts
    seen = []
    async def chat(req, ctx):
        seen.append(req)
        object.__setattr__(req, '_upstream_submission_started', True)
        raise RouterException('ambiguous', Cat.UPSTREAM_5XX)
    async def chunks(req, ctx):
        await chat(req, ctx)
        yield 'unreachable'
    monkeypatch.setattr(ModuleLoader, 'get_adapter', lambda *a: NS(chat_completions=chat, stream_chat=chunks))
    req = request()
    accepted = request().model_copy()
    async def reserve(c, p, m, req):
        return NS(finish=lambda *a: None), accepted, None
    monkeypatch.setattr(Router, '_reserve_dispatch', reserve)
    async def run():
        with pytest.raises(RouterException) as caught:
            kw = dict(base_url=provider.base_url, api_key='synthetic', model_id='model', request=req,
                      extra_headers={}, configuration={'module_id': 'synthetic'}, timeout=1, retry_count=1)
            adapter = CustomModuleAdapter()
            if stream:
                _ = [c async for c in Router._dispatch_stream(adapter, creds[0], provider, model, **kw)]
            else:
                await Router._dispatch_chat(adapter, creds[0], provider, model, **kw)
        assert not caught.value.replay_safe and len(seen) == 1
        assert seen[0] is accepted and accepted._upstream_submission_started
    asyncio.run(run())


@pytest.mark.parametrize('content', ['invalid json', '{"answers": {}}'])
def test_jev_parse_after_accepted_send_is_not_replayed(parts, monkeypatch, content):
    import app.jev.engine as jev
    provider, model, creds = parts
    async def chat(**kw):
        object.__setattr__(kw['request'], '_upstream_submission_started', True)
        return NS(usage=None, choices=[NS(message=NS(content=content))])
    # This helper owns its chat envelope; test its post-dispatch parsing too.
    monkeypatch.setattr(jev, 'get_adapter', lambda *a: NS(chat_completions=chat))
    req = JevRequest(model='synthetic/model', state='offline', questions={'q': {'type': 'noul'}})
    async def run():
        with pytest.raises(RouterException) as caught:
            await JevEngine._emulate_jev_via_adapter(provider, 'synthetic', model, req, credential=creds[0])
        assert not caught.value.replay_safe
    asyncio.run(run())


@pytest.mark.parametrize('submitted', [False, True])
@pytest.mark.parametrize('failure', ['typed', 'unsafe', 'network', 'raw', 'timeout', 'parse_choices', 'parse_usage'])
def test_fusion_participant_preserves_safe_advancement_only(parts, monkeypatch, submitted, failure):
    import app.fusion.engine as fusion
    provider, model, creds = parts
    calls = []
    seen_errors = []
    class Session:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def execute(self, query):
            return NS(scalars=lambda: NS(all=lambda: creds))
    monkeypatch.setattr(fusion, 'AsyncSessionLocal', Session)
    monkeypatch.setattr(fusion, 'decrypt_secret', lambda *a: 'synthetic')
    async def chat(**kw):
        calls.append(kw['request'])
        if len(calls) == 1:
            if submitted:
                object.__setattr__(kw['request'], '_upstream_submission_started', True)
            if failure == 'timeout':
                try:
                    await asyncio.Event().wait()
                finally:
                    # Cleanup outlives the deadline: an outer wait_for would
                    # cancel the shared dispatch before it fences its error.
                    await asyncio.sleep(.02)
            if failure == 'network':
                raise httpx.ReadError('synthetic')
            if failure == 'raw':
                raise ValueError('synthetic')
            if failure in ('typed', 'unsafe'):
                raise RouterException('synthetic', Cat.UPSTREAM_5XX, replay_safe=failure != 'unsafe')
            if failure == 'parse_choices':
                return NS(usage=None, choices=[NS(message=None)])
            if failure == 'parse_usage':
                return NS(usage=NS(model_dump=lambda **kw: {}, total_tokens=0), choices=[])
        return NS(usage=None, choices=[NS(message=NS(content='ok'))])
    def normalize(**kw):
        error = normalize_upstream_error(**kw)
        seen_errors.append(error)
        return error
    monkeypatch.setattr(fusion, 'get_adapter', lambda *a: NS(chat_completions=chat, normalize_error=normalize))
    part = NS(label='offline', participant_type='model', target_profile_id=None,
              provider=provider, model=model, credential=None, credential_id=None,
              credential_group=None, temperature=None, thinking_effort=None)
    async def run():
        result = await fusion.FusionEngine._execute_single_participant(
            0, part, request(), .01 if failure == 'timeout' else 1)
        stopped = submitted or failure == 'unsafe'
        assert len(calls) == (1 if stopped else 2)
        assert (result['content'] is None) == stopped
        assert bool(result['error']) == stopped
        if stopped and seen_errors:
            assert not seen_errors[-1].replay_safe
    asyncio.run(run())
