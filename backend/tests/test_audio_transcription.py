"""Offline STT contract: real multipart HTTP, no metered provider calls."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select

from app.api.deps import get_router_key_dep
from app.api.v1.router import router
from app.core.database import AsyncSessionLocal
from app.core.errors import RouterException
from app.core.http_client import http_client_manager
from app.adapters.openai import GenericOpenAIAdapter
from app.models.entities import Provider, ProviderCredential, DiscoveredModel
from app.services.audio_service import AudioService, TranscriptionRequest, is_transcription_model
from app.services.model_discovery_service import ModelDiscoveryService
from app.schemas.entities import DiscoveredModelUpdate
from app.routing.engine import RoutingEngine


@pytest.mark.asyncio
async def test_audio_multipart_modes_validation_and_auth(monkeypatch):
    app = FastAPI()
    app.include_router(router)
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test')
    transcribe = AsyncMock(return_value={'text': 'Проверка ✓'})
    monkeypatch.setattr(AudioService, 'transcribe', transcribe)
    async with client:
        denied = await client.post('/v1/audio/transcriptions', data={'model': 'groq/whisper-large-v3'}, files={'file': ('probe.wav', b'audio')})
        assert denied.status_code == 401
        app.dependency_overrides[get_router_key_dep] = lambda: None
        for fmt in ('json', 'verbose_json', 'text'):
            transcribe.return_value = 'Проверка ✓' if fmt == 'text' else {'text': 'Проверка ✓'}
            result = await client.post('/v1/audio/transcriptions', data={'model': 'groq/whisper-large-v3', 'response_format': fmt, 'language': 'ru'},
                files={'file': ('probe.wav', b'audio', 'audio/wav')})
            assert result.status_code == 200, result.text
            assert result.headers['x-request-id'].startswith('req_')
            assert result.text == 'Проверка ✓' if fmt == 'text' else result.json()['text'] == 'Проверка ✓'
        count = transcribe.await_count
        for data, file, status in (({'model': 'x'}, ('probe.wav', b''), 400),
                ({'model': 'x'}, ('probe.exe', b'audio'), 400),
                ({'model': 'x', 'temperature': 'nan'}, ('probe.wav', b'audio'), 422),
                ({'model': 'x', 'timestamp_granularities[]': 'word'}, ('probe.wav', b'audio'), 422),
                ({'model': 'x', 'url': 'http://internal'}, ('probe.wav', b'audio'), 400),
                ({}, ('probe.wav', b'audio'), 422)):
            result = await client.post('/v1/audio/transcriptions', data=data, files={'file': file})
            assert result.status_code == status, result.text
        assert transcribe.await_count == count
        import app.services.audio_service as audio_service
        monkeypatch.setattr(audio_service, 'MAX_AUDIO_BYTES', 1024)
        result = await client.post('/v1/audio/transcriptions', data={'model': 'x'}, files={'file': ('probe.wav', b'x' * 2048)})
        assert result.status_code == 413
        result = await client.post('/v1/audio/transcriptions', data={'model': 'x'}, files={'file': ('probe.wav', b'x' * 70000)})
        assert result.status_code == 413
        assert transcribe.await_count == count


@pytest.mark.asyncio
async def test_audio_adapter_repeated_fields_and_no_paid_replay(monkeypatch):
    seen = []
    def upstream(request):
        body = request.read()
        assert request.url.path == '/openai/v1/audio/transcriptions'
        assert request.headers['content-type'].startswith('multipart/form-data; boundary=')
        assert request.headers['authorization'] == 'Bearer test-secret'
        assert body.count(b'name="timestamp_granularities[]"') == 2
        assert b'groq/whisper-large-v3' not in body
        assert 'подсказка ✓'.encode() in body and b'\x00\x01AUDIO' in body
        seen.append(request)
        return httpx.Response(200, json={'text': 'Текст ✓', 'words': [{'word': 'Текст', 'start': 0, 'end': 1}]})
    client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    monkeypatch.setattr(http_client_manager, 'get_client', AsyncMock(return_value=client))
    adapter = GenericOpenAIAdapter()
    args = dict(base_url='https://api.groq.com/openai/v1', api_key='test-secret', model_id='whisper-large-v3',
        payload=TranscriptionRequest(model='groq/whisper-large-v3', prompt='подсказка ✓', response_format='verbose_json', timestamp_granularities=['word', 'segment']),
        audio=b'\x00\x01AUDIO', filename='probe.wav', content_type='audio/wav', extra_headers={'content-type': 'application/json'}, configuration={})
    async with client:
        assert (await adapter.transcribe_audio(**args))['text'] == 'Текст ✓'
    for exception, replay_safe in ((httpx.ReadTimeout('accepted possibly'), False), (httpx.ConnectTimeout('not sent'), True)):
        def fail(request):
            raise exception
        async with httpx.AsyncClient(transport=httpx.MockTransport(fail)) as failing:
            monkeypatch.setattr(http_client_manager, 'get_client', AsyncMock(return_value=failing))
            with pytest.raises(RouterException) as caught:
                await adapter.transcribe_audio(**args)
            assert caught.value.replay_safe is replay_safe
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={'bad': 'response'}))) as invalid:
        monkeypatch.setattr(http_client_manager, 'get_client', AsyncMock(return_value=invalid))
        with pytest.raises(RouterException) as caught:
            await adapter.transcribe_audio(**args)
        assert not caught.value.replay_safe
    assert len(seen) == 1


@pytest.mark.asyncio
async def test_audio_model_discovery_manual_update_and_chat_guard(monkeypatch):
    async with AsyncSessionLocal() as db:
        provider = Provider(name='Audio fixture', slug='audio-fixture', adapter_type='groq', base_url='http://fixture', configuration={}, extra_headers={})
        db.add(provider)
        await db.commit()
        model = await ModelDiscoveryService.add_model_manually(db, provider.id, None, 'whisper-large-v3', 'Whisper')
        assert model.model_type == 'audio'
        assert model.supported_endpoints == ['/audio/transcriptions']
        assert model.capabilities['chat'] is False
        await ModelDiscoveryService.update_model(db, model.id, DiscoveredModelUpdate(model_type='openai'))
        await ModelDiscoveryService.batch_update_models(db, [model.id], model_type='audio', set_model_type=True)
        batch = await ModelDiscoveryService.get_model_read(db, model.id)
        assert batch.model_type == 'audio' and batch.capabilities['chat'] is False
        await ModelDiscoveryService.update_model(db, model.id, DiscoveredModelUpdate(model_type='openai'))
        cred = ProviderCredential(provider_id=provider.id, name='fixture', encrypted_api_key='not-used', masked_key='fixture', key_fingerprint='audio-fixture')
        db.add(cred)
        await db.commit()
        discovered = SimpleNamespace(provider_model_id='whisper-large-v3', display_name='Whisper', capabilities={'chat': True},
            supported_endpoints=['/chat/completions'], context_length=None, max_output_tokens=None, input_price_per_1m=None, output_price_per_1m=None)
        monkeypatch.setattr(GenericOpenAIAdapter, 'list_models', AsyncMock(return_value=[discovered]))
        monkeypatch.setattr('app.services.model_discovery_service.decrypt_secret', lambda _: 'fixture')
        await ModelDiscoveryService.fetch_models_for_credential(db, cred.id)
        stored = await db.get(DiscoveredModel, model.id)
        await db.refresh(stored)
        assert stored.model_type == 'audio' and stored.capabilities['transcription'] is True
        with pytest.raises(RouterException, match='audio/transcriptions'):
            await RoutingEngine._reserve_dispatch(cred, provider, stored, None)
        assert is_transcription_model('groq/whisper-large-v3-turbo')
        assert is_transcription_model('whisper:free')
        assert is_transcription_model('whisper-tiny-en:free')
        assert not is_transcription_model('llama-3.3-70b-versatile')


@pytest.mark.asyncio
async def test_audio_seconds_fail_closed_under_text_quotas(monkeypatch):
    from app.services.quota_service import QuotaService
    async with AsyncSessionLocal() as db:
        provider = Provider(name='Quota audio fixture', slug='quota-audio-fixture', adapter_type='groq', base_url='http://fixture', configuration={}, extra_headers={})
        db.add(provider)
        await db.flush()
        cred = ProviderCredential(provider_id=provider.id, name='quota fixture', encrypted_api_key='not-used', masked_key='fixture', key_fingerprint='audio-quota-fixture',
            quota_rules=[{'id':'a' * 32,'enabled':True,'scope':'key','period':'day','tokens':1000}])
        db.add(cred)
        await db.commit()
        with pytest.raises(RouterException, match='Audio seconds'):
            await QuotaService.reserve_dispatch(provider, SimpleNamespace(canonical_slug='groq/whisper-large-v3'),
                TranscriptionRequest(model='groq/whisper-large-v3'), credential=cred)


@pytest.mark.asyncio
@pytest.mark.parametrize('outer_deadline', [False, True])
async def test_audio_engine_timeout_does_not_fallback_and_releases_capacity(monkeypatch, outer_deadline):
    from app.core.admission import admission
    from app.core.circuit_breaker import circuit_breaker
    from app.services.quota_service import QuotaService
    from app.services.log_service import LogService
    provider = SimpleNamespace(id=998, name='fixture', enabled=True, adapter_type='groq', base_url='http://fixture', extra_headers={}, configuration={})
    model = SimpleNamespace(id=998, provider_id=998, provider=provider, enabled=True, available=True, model_type='audio',
        provider_model_id='whisper-large-v3', canonical_slug='groq/whisper-large-v3', supported_endpoints=['/audio/transcriptions'])
    def credential(id):
        return SimpleNamespace(id=id, provider_id=998, name='fixture', enabled=True, tpm_limit=None, rpm_limit=None,
            max_concurrency=1, proxy=None, encrypted_api_key='fixture')
    creds = [credential(998), credential(999)]
    monkeypatch.setattr(RoutingEngine, '_get_candidate_credentials_for_model', AsyncMock(return_value=[(c,model) for c in creds]))
    monkeypatch.setattr(QuotaService, 'reserve_dispatch', AsyncMock(return_value=(None, None)))
    monkeypatch.setattr('app.services.audio_service.decrypt_secret', lambda _: 'fixture')
    monkeypatch.setattr(LogService, 'record_request_log', AsyncMock())
    if outer_deadline:
        import asyncio
        real_timeout = asyncio.timeout
        monkeypatch.setattr('app.services.audio_service.asyncio.timeout', lambda _: real_timeout(0.01))
        async def pending(**kwargs):
            await asyncio.sleep(10)
        upstream = AsyncMock(side_effect=pending)
    else:
        upstream = AsyncMock(side_effect=TimeoutError('overall deadline'))
    monkeypatch.setattr(GenericOpenAIAdapter, 'transcribe_audio', upstream)
    monkeypatch.setattr(circuit_breaker, 'record_failure', lambda *a, **k: None)
    with pytest.raises(RouterException) as caught:
        await AudioService.transcribe(None, TranscriptionRequest(model='groq/whisper-large-v3'), b'audio', 'probe.wav', 'audio/wav', request_id='req_fixture')
    assert not caught.value.replay_safe and upstream.await_count == 1
    released = admission.reserve('credential', 998, concurrency=1)
    released.finish()


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['quota', 'rpm', 'concurrency', 'auth', 'router-quota'])
async def test_audio_credential_fallback_preserves_global_limits(monkeypatch, failure):
    from app.core.admission import admission
    from app.core.circuit_breaker import circuit_breaker
    from app.services.quota_service import QuotaService
    from app.services.log_service import LogService
    from app.core.errors import ErrorCategory
    provider = SimpleNamespace(id=9001, name='fixture', enabled=True, adapter_type='groq', base_url='http://fixture', extra_headers={}, configuration={})
    model = SimpleNamespace(provider_id=9001, provider=provider, enabled=True, available=True, model_type='audio',
        provider_model_id='whisper-large-v3', canonical_slug='groq/whisper-large-v3', supported_endpoints=['/audio/transcriptions'])
    creds = [SimpleNamespace(id=i, provider_id=9001, name='fixture', enabled=True, tpm_limit=None,
        rpm_limit=0 if failure == 'rpm' and i == 9001 else None,
        max_concurrency=0 if failure == 'concurrency' and i == 9001 else 1,
        proxy=None, encrypted_api_key=str(i)) for i in (9001,9002)]
    monkeypatch.setattr(RoutingEngine, '_get_candidate_credentials_for_model', AsyncMock(return_value=[(c,model) for c in creds]))
    ticket = SimpleNamespace(finish=AsyncMock())
    denial = RouterException('quota reached', ErrorCategory.RATE_LIMIT, raw_error={'local_admission': True,
        **({'credential_id': 9001} if failure == 'quota' else {})})
    quota = AsyncMock(side_effect=[denial, (None,None)] if failure in ('quota','router-quota') else [(ticket,None),(None,None)])
    monkeypatch.setattr(QuotaService, 'reserve_dispatch', quota)
    monkeypatch.setattr('app.services.audio_service.decrypt_secret', lambda value: value)
    monkeypatch.setattr(LogService, 'record_request_log', AsyncMock())
    failures = []
    monkeypatch.setattr(circuit_breaker, 'record_failure', lambda *args: failures.append(args))
    monkeypatch.setattr(circuit_breaker, 'record_success', lambda *args: None)
    auth_error = RouterException('invalid key', ErrorCategory.AUTH_ERROR, replay_safe=True)
    upstream = AsyncMock(side_effect=[auth_error, {'text':'ok'}] if failure == 'auth' else [{'text':'ok'}])
    monkeypatch.setattr(GenericOpenAIAdapter, 'transcribe_audio', upstream)
    args=(None, TranscriptionRequest(model='groq/whisper-large-v3'), b'audio', 'probe.wav', 'audio/wav')
    if failure == 'router-quota':
        with pytest.raises(RouterException, match='quota reached'):
            await AudioService.transcribe(*args, request_id='req_fixture')
        assert quota.await_count == 1 and upstream.await_count == 0
    else:
        assert await AudioService.transcribe(*args, request_id='req_fixture') == {'text':'ok'}
        assert quota.await_count == 2
        assert upstream.await_count == (2 if failure == 'auth' else 1)
        assert upstream.call_args.kwargs['api_key'] == '9002'
        if failure in ('rpm','concurrency'):
            ticket.finish.assert_awaited_once_with(success=False, dispatched=False)
        assert len(failures) == (1 if failure == 'auth' else 0)
