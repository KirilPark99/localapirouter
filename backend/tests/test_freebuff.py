"""Offline Freebuff module contract; run with --noconftest and synthetic Settings."""
import asyncio
import importlib.util
import json
from pathlib import Path
from contextlib import aclosing

import httpx
import pytest

from app.modules.base import ModuleExecutionContext
from app.schemas.chat import ChatCompletionRequest
from app.core.errors import RouterException

MODULE = Path(__file__).resolve().parents[1] / 'modules' / 'freebuff'


def load():
    assert (MODULE / 'manifest.json').is_file(), 'Freebuff manifest missing'
    spec = importlib.util.spec_from_file_location('freebuff_test_handler', MODULE / 'handler.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_manifest():
    load()
    data = json.loads((MODULE / 'manifest.json').read_text())
    assert data['id'] == 'freebuff' and not data['default_models']


@pytest.mark.asyncio
async def test_wire_and_safe_errors(monkeypatch):
    module = load()
    adapter = module.FreebuffAdapter()
    ctx = ModuleExecutionContext(model_id='exact/id', extra_config={'credential_id': 7})
    calls = []
    data = [
        {'id': 'test', 'choices': [{'index': 0, 'delta': {'role': 'assistant', 'content': 'Привет'}, 'finish_reason': None}]},
        {'id': 'test', 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}],
         'usage': {'prompt_tokens': 2, 'completion_tokens': 1, 'total_tokens': 3}},
    ]
    wire = ''.join('data: ' + json.dumps(x) + '\r\n\r\n' for x in data) + 'data: [DONE]\r\n\r\n'

    class Stream(httpx.AsyncByteStream):
        closed = False
        async def __aiter__(self):
            for i in range(0, len(wire.encode()), 3):
                yield wire.encode()[i:i+3]
        async def aclose(self):
            self.closed = True

    stream = Stream()
    def upstream(request):
        calls.append(request)
        assert request.headers['authorization'] == 'Bearer synthetic'
        assert 'cookie' not in request.headers
        assert str(request.url).startswith('http://127.0.0.1:9999/')
        if request.url.path == '/api/accounts/refresh':
            return httpx.Response(200, json={'ok': True})
        if request.url.path == '/v1/models':
            return httpx.Response(200, json={'data': [{'id': 'exact/id', 'display_name': 'Test', 'context_window': 100}]})
        if request.url.path == '/v1/chat/completions':
            body = json.loads(request.content)
            assert body['model'] == 'exact/id' and body['stream'] is True
            return httpx.Response(200, headers={'content-type': 'text/event-stream'}, stream=stream)
        return httpx.Response(502, json={'error': {'message': 'SECRET upstream token'}})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(module, '_client', lambda runtime, timeout: real_client(
        base_url=runtime['url'], headers={'Authorization': 'Bearer ' + runtime['token']},
        transport=httpx.MockTransport(upstream), trust_env=False, timeout=timeout))
    async def runtime(_):
        return {'url': 'http://127.0.0.1:9999', 'token': 'synthetic'}
    monkeypatch.setattr(adapter, '_runtime', runtime)
    models = await adapter.list_models(ctx)
    assert models[0].provider_model_id == 'exact/id' and models[0].context_length == 100
    request = ChatCompletionRequest(model='route/name', messages=[{'role': 'user', 'content': 'hi'}])
    response = await adapter.chat_completions(request, ctx)
    assert response.model == 'exact/id' and response.choices[0].message.content == 'Привет'
    assert response.usage.total_tokens == 3 and stream.closed
    assert request.model == 'route/name' and request.stream is False
    with pytest.raises(RouterException) as error:
        await adapter.login_start(ctx)
    assert 'SECRET' not in str(error.value) and error.value.replay_safe is False


@pytest.mark.asyncio
async def test_early_stream_close(monkeypatch):
    module = load()
    adapter = module.FreebuffAdapter()
    closed = asyncio.Event()
    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'data: {"choices":[{"index":0,"delta":{"content":"x"},"finish_reason":null}]}\n\n'
            await asyncio.Event().wait()
        async def aclose(self):
            closed.set()
    real_client = httpx.AsyncClient
    monkeypatch.setattr(module, '_client', lambda runtime, timeout: real_client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200,
            headers={'content-type': 'text/event-stream'}, stream=Stream())), timeout=timeout))
    async def runtime(_):
        return {'url': 'http://127.0.0.1:9999', 'token': 'synthetic'}
    monkeypatch.setattr(adapter, '_runtime', runtime)
    request = ChatCompletionRequest(model='m', messages=[{'role': 'user', 'content': 'hi'}])
    source = adapter.stream_chat(request, ModuleExecutionContext())
    async with aclosing(source):
        assert 'x' in await anext(source)
    assert closed.is_set() and request._upstream_submission_started


def test_node_bridge_preserves_split_utf8(tmp_path):
    import os
    import shutil
    import subprocess
    source = Path('/home/kiril/PythonProjects/freebuff-proxy/cli-bridge/bridge.ts')
    node = shutil.which('node')
    assert node and source.is_file()
    fake = tmp_path / 'bun-bytes'
    fake.write_text('#!' + node + '\n' + r'''
const text = 'data: {"text":"Привет 😀"}\n\n>{"text":"Привет 😀"}\n';
const bytes = Buffer.from(text), cut = bytes.indexOf(Buffer.from('П')) + 1;
process.stdout.write(bytes.subarray(0, cut));
setTimeout(() => process.stdout.write(bytes.subarray(cut)), 30);
''')
    fake.chmod(0o700)
    script = f"import {{callBunStream}} from {json.dumps(source.as_uri())};\n" + r'''
import assert from 'node:assert/strict';
let lines = [];
await new Promise((resolve, reject) => callBunStream({cfg:{proxy:null}}, {
    onLine: line => lines.push(line), onSummary: resolve, onError: reject, timeoutMs: 2000,
}));
assert(lines.join('\n').includes('Привет 😀'), JSON.stringify(lines));
'''
    run = subprocess.run([node, '--input-type=module', '-e', script], text=True, capture_output=True,
        env={'PATH': os.environ['PATH'], 'HOME': str(tmp_path), 'FREEBUFF_BUN_BIN': str(fake)}, timeout=5)
    assert run.returncode == 0, run.stdout + run.stderr


def test_loader_and_profile_identity(monkeypatch, tmp_path):
    from datetime import datetime, timezone
    from types import SimpleNamespace
    import app.modules.loader as loader
    from app.services.credential_service import CredentialService
    (tmp_path / 'freebuff').symlink_to(MODULE, target_is_directory=True)
    monkeypatch.setattr(loader, 'MODULES_DIR', tmp_path)
    monkeypatch.setattr(loader.ModuleLoader, '_modules', {})
    monkeypatch.setattr(loader.ModuleLoader, '_adapters', {})
    monkeypatch.setattr(loader.ModuleLoader, '_retired_adapters', [])
    assert loader.ModuleLoader.scan_modules()['freebuff'].status == 'ready'
    adapter = loader.ModuleLoader.get_adapter('freebuff')
    assert not adapter._workers
    loader.ModuleLoader.scan_modules()
    assert loader.ModuleLoader.get_adapter('freebuff')._workers is adapter._workers
    provider = SimpleNamespace(adapter_configuration={'module_id': 'freebuff'})
    first = SimpleNamespace(id=7, created_at=datetime(2026, 1, 1), metadata_json={})
    second = SimpleNamespace(id=7, created_at=datetime(2026, 1, 2, tzinfo=timezone.utc), metadata_json={})
    a = CredentialService.module_runtime_configuration(provider, first)
    b = CredentialService.module_runtime_configuration(provider, second)
    assert a['credential_instance'] != b['credential_instance']
    first.created_at = first.created_at.replace(tzinfo=timezone.utc)
    assert CredentialService.module_runtime_configuration(provider, first) == a


@pytest.mark.asyncio
@pytest.mark.parametrize('tail', ['data: [DONE]\n\n', 'data: broken\n\n',
    'data: {"error":{"message":"SECRET"}}\n\n', ''])
async def test_invalid_stream_is_not_complete_or_replayable(monkeypatch, tail):
    module = load()
    adapter = module.FreebuffAdapter()
    wire = 'data: {"choices":[{"index":0,"delta":{"content":"partial"}}]}\n\n' + tail
    real_client = httpx.AsyncClient
    monkeypatch.setattr(module, '_client', lambda runtime, timeout: real_client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text=wire,
            headers={'content-type': 'text/event-stream'}))))
    async def runtime(_):
        return {'url': 'http://127.0.0.1:9999', 'token': 'synthetic'}
    monkeypatch.setattr(adapter, '_runtime', runtime)
    with pytest.raises(RouterException) as error:
        await adapter.chat_completions(ChatCompletionRequest(model='m', messages=[]), ModuleExecutionContext())
    assert error.value.replay_safe is False and 'SECRET' not in str(error.value)


@pytest.mark.parametrize('state', [{'flows': {}}, {'flows': ''}, {'flows': [None]},
    {'flows': [{}]}, {'flows': [{'id': 'not-a-uuid', 'status': 'done'}]}, [], None])
def test_malformed_flow_state_cannot_change_pin(tmp_path, state):
    import hashlib
    import subprocess
    import sys
    root = tmp_path / 'pool'
    (root / 'data').mkdir(parents=True)
    pin = hashlib.sha256(json.dumps(None).encode()).hexdigest()
    (root / 'egress.json').write_text(pin)
    (root / 'data/login-flows.json').write_text(json.dumps(state))
    cfg = {'root': str(root), 'proxy': 'http://127.0.0.1:1', 'token': 'synthetic',
        'bun': '/bin/true', 'node': '/bin/true', 'source': str(tmp_path)}
    run = subprocess.run([sys.executable, '-I', str(MODULE / 'handler.py')], input=json.dumps(cfg) + '\n',
        text=True, capture_output=True, timeout=5)
    assert run.returncode == 0 and not (root / 'config.json').exists()
    assert (root / 'egress.json').read_text() == pin


@pytest.mark.asyncio
@pytest.mark.parametrize('body,field', [({'logprobs': True}, 'logprobs'), ({'future_option': 1}, 'future_option'),
    ({'messages': [{'role': 'user', 'content': 'x', 'audio': {}}]}, 'audio')])
async def test_unknown_parameters_never_disappear_before_freebuff(monkeypatch, body, field):
    from app.adapters.openai import GenericOpenAIAdapter
    adapter = load().FreebuffAdapter()
    request = ChatCompletionRequest.model_validate({'model': 'm', 'messages': [], **body})
    pristine = ChatCompletionRequest.model_validate(request.model_dump())
    # Existing providers retain their original serialization behavior.
    assert GenericOpenAIAdapter()._prepare_payload('m', request) == GenericOpenAIAdapter()._prepare_payload('m', pristine)
    async def forbidden(_):
        pytest.fail('Unsupported fields must be refused before runtime/upstream')
    monkeypatch.setattr(adapter, '_runtime', forbidden)
    with pytest.raises(RouterException, match=field) as error:
        await adapter.chat_completions(request.model_copy(deep=True), ModuleExecutionContext())
    assert error.value.status_code == 400


@pytest.mark.asyncio
async def test_unknown_parameters_refused_before_response_cache(monkeypatch):
    from types import SimpleNamespace as NS
    from unittest.mock import AsyncMock
    from app.routing.engine import RoutingEngine
    provider = NS(enabled=True, configuration={'module_id': 'freebuff'}, adapter_type='custom_module',
        base_url='module://freebuff', adapter_configuration={'module_id': 'freebuff'}, extra_headers={})
    model = NS(enabled=True, available=True, provider_model_id='m', canonical_slug='module_freebuff/m', capabilities={})
    credential = NS(enabled=True, provider=provider)
    monkeypatch.setattr(RoutingEngine, '_get_candidate_credentials_for_model', AsyncMock(return_value=[(credential, model)]))
    request = ChatCompletionRequest.model_validate({'model': 'm', 'messages': [], 'logprobs': True})
    with pytest.raises(RouterException, match='logprobs'):
        await RoutingEngine.prepare_effective_request(None, request)


@pytest.mark.asyncio
async def test_registry_proxy_changes_close_exact_freebuff_profile(monkeypatch):
    from unittest.mock import AsyncMock
    from types import SimpleNamespace
    from app.core.database import AsyncSessionLocal
    from app.models.entities import Provider, ProviderCredential, Proxy
    from app.services.proxy_service import ProxyService
    from app.services.credential_service import CredentialService
    from app.schemas.entities import ProxyUpdate
    from app.modules.loader import ModuleLoader
    closed = AsyncMock()
    monkeypatch.setattr(ModuleLoader, 'get_adapter', lambda mid:
        SimpleNamespace(close_profile=closed) if mid == 'freebuff' else None)
    async with AsyncSessionLocal() as db:
        provider = Provider(name='Freebuff proxy fixture', slug='freebuff-proxy-fixture',
            adapter_type='custom_module', base_url='module://freebuff', configuration={'module_id': 'freebuff'})
        proxy = Proxy(name='Local registry', scheme='http', host='127.0.0.1', port=8000, enabled=True)
        db.add_all([provider, proxy]); await db.flush()
        cred = ProviderCredential(provider_id=provider.id, name='Local proxy credential', proxy_id=proxy.id,
            encrypted_api_key='not-used', key_fingerprint='freebuff-proxy-fixture', masked_key='synthetic')
        db.add(cred); await db.commit()
        config = CredentialService.module_runtime_configuration(provider, cred)
        assert config['profile_proxy_id'] == proxy.id
        await ProxyService.update_proxy(db, proxy.id, ProxyUpdate(name='renamed'))
        closed.assert_not_awaited()
        await ProxyService.update_proxy(db, proxy.id, ProxyUpdate(enabled=False))
        closed.assert_awaited_once_with(cred.id)
        adapter = load().FreebuffAdapter()
        context = ModuleExecutionContext(extra_config=config, proxy_url='http://stale.invalid:80')
        with pytest.raises(RouterException, match='missing or disabled'):
            await adapter._runtime(context)
        await ProxyService.delete_proxy(db, proxy.id)
        assert closed.await_count == 2
        with pytest.raises(RouterException, match='missing or disabled'):
            await adapter._runtime(context)


@pytest.mark.asyncio
async def test_native_quota_unknown_and_safe_parameter_refusal(monkeypatch):
    module = load(); adapter = module.FreebuffAdapter()
    async def quota(*args, **kwargs):
        return {'accounts': [{'quota': {'byModel': {
            'used': {'limit': 6, 'recentCount': 1.25},
            'zero': {'limit': 6, 'recentCount': 6}, 'unknown': {},
        }}}]}
    monkeypatch.setattr(adapter, '_json', quota)
    limits = (await adapter.get_subscription_limits(ModuleExecutionContext())).limits
    assert [x.remaining for x in limits] == [4.75, 0, None]
    assert all(x.unit == 'session_units' for x in limits)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(module, '_client', lambda rt, timeout: real_client(
        transport=httpx.MockTransport(lambda _: httpx.Response(400, json={'error': {
            'code': 'unsupported_parameter', 'param': 'temperature', 'message': 'SECRET'}}))))
    async def runtime(_):
        return {'url': 'http://127.0.0.1:9999', 'token': 'synthetic'}
    monkeypatch.setattr(adapter, '_runtime', runtime)
    with pytest.raises(RouterException, match='temperature') as error:
        await adapter.chat_completions(ChatCompletionRequest(model='m', messages=[], temperature=0), ModuleExecutionContext())
    assert error.value.status_code == 400 and not error.value.is_retryable and 'SECRET' not in str(error.value)


@pytest.mark.asyncio
@pytest.mark.skipif(__import__('os').environ.get('FREEBUFF_RUNTIME_CHECK') != '1', reason='opt-in local Node worker runtime')
async def test_managed_full_service(monkeypatch, tmp_path):
    """Actual supervisor → worker.js → pinned loopback proxy/upstream; no live accounts."""
    import hashlib
    import os
    import shutil
    import sys
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import urlsplit
    import select
    import socket
    source = Path('/home/kiril/PythonProjects/freebuff2api-wokers')
    assert (source / 'worker.js').is_file() and shutil.which('node')
    seen = []
    class Upstream(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            self.reply()
        def do_POST(self):
            self.reply()
        def do_DELETE(self):
            self.reply()
        def do_CONNECT(self):
            host, _, port = self.path.rpartition(':')
            if host != '127.0.0.1':
                self.send_error(502)
                return
            with socket.create_connection((host, int(port)), timeout=5) as peer:
                self.send_response(200); self.end_headers()
                for _ in range(250):
                    readable, _, _ = select.select([peer, self.connection], [], [], .2)
                    for endpoint in readable:
                        data = endpoint.recv(65536)
                        if not data:
                            return
                        (peer if endpoint is self.connection else self.connection).sendall(data)
        def reply(self):
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
            route = urlsplit(self.path).path
            seen.append((route, body))
            if route == '/api/v1/chat/completions':
                self.send_response(200); self.send_header('Content-Type', 'text/event-stream'); self.end_headers()
                tool = next((tool for tool in body.get('tools', [])
                    if 'fixture_lookup' in tool.get('function', {}).get('name', '')), None)
                if tool and body['messages'][-1]['role'] != 'tool':
                    delta = {'tool_calls': [{'index': 0, 'id': 'call-native', 'type': 'function',
                        'function': {'name': tool['function']['name'], 'arguments': '{"key":"значение"}'}}]}
                    finish = 'tool_calls'
                else:
                    delta, finish = {'content': 'Проверка managed'}, 'stop'
                self.wfile.write(('data: ' + json.dumps({'id': 'local-answer', 'choices': [{'index': 0,
                    'delta': delta, 'finish_reason': finish}]}, ensure_ascii=False) +
                    '\n\ndata: [DONE]\n\n').encode())
                return
            if route == '/api/v1/freebuff/models':
                result = {'fetchId': 'local-fid', 'refreshAt': 9999999999999, 'rows': [
                    {'key': 'm-00032eaeec', 'displayName': 'Local Test', 'handle': 'fbm1.local', 'costMode': 'free'}]}
            elif route == '/api/v1/freebuff/session' and self.command == 'POST':
                result = {'status': 'active', 'instanceId': self.headers['x-freebuff-instance-id'],
                    'model': 'mimo/mimo-v2.5', 'accessTier': 'full', 'admittedAt': '2026-10-12T00:00:00Z',
                    'expiresAt': '2099-01-01T00:00:00Z', 'remainingMs': 3600000}
            elif route == '/api/v1/freebuff/device-keys': result = {'keyId': 'local-key'}
            elif route == '/api/v1/agent-runs': result = {'runId': 'local-run'}
            else: result = {'status': 'none', 'accessTier': 'full'}
            raw = json.dumps(result).encode()
            self.send_response(200); self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    api = f'http://127.0.0.1:{server.server_port}'

    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path / 'state'))
    monkeypatch.setenv('HTTPS_PROXY', 'http://127.0.0.1:1')
    monkeypatch.setenv('FREEBUFF_PROXY_DATA_DIR', str(tmp_path / 'wrong-data'))
    module = load(); adapter = module.FreebuffAdapter()
    from fastapi import FastAPI
    from unittest.mock import AsyncMock
    from app.api.admin import modules as admin_modules
    from app.api.v1.router import router as inference_router
    from app.api.deps import get_current_admin, get_router_key_dep
    from app.core.database import AsyncSessionLocal, engine
    from app.services.credential_service import CredentialService
    from app.core.crypto import decrypt_secret
    from app.models.entities import Proxy
    from app.adapters.module_adapter import CustomModuleAdapter
    from app.modules.base import ModuleManifest
    from app.modules.loader import ModuleLoader, LoadedModule
    from app.modules import profile_loader
    assert 'freebuff-offline-' in str(engine.url.database)
    manifest = ModuleManifest.model_validate_json((MODULE / 'manifest.json').read_text())
    monkeypatch.setattr(ModuleLoader, '_modules', {'freebuff': LoadedModule(manifest=manifest)})
    monkeypatch.setattr(ModuleLoader, '_adapters', {'freebuff': adapter})
    monkeypatch.setattr(profile_loader, 'sync_profiles_from_disk', AsyncMock(return_value={}))
    app = FastAPI()
    app.include_router(admin_modules.router, prefix='/api/admin')
    app.include_router(inference_router)
    app.dependency_overrides[get_current_admin] = lambda: 'local-admin'
    app.dependency_overrides[get_router_key_dep] = lambda: None
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fixture')
    base = '/api/admin/modules/freebuff/profiles'
    async with AsyncSessionLocal() as db:
        proxy = Proxy(name='Local Freebuff egress fixture', scheme='http', host='127.0.0.1', port=server.server_port)
        db.add(proxy); await db.commit(); await db.refresh(proxy)
        proxy_id = proxy.id
    fields = {'project_path': str(source), 'node_path': shutil.which('node'), 'api_base': api, 'startup_timeout': 10}
    created = await client.post(base, json={'name': 'Local Freebuff', 'fields': fields, 'proxy_id': proxy_id})
    assert created.status_code == 201, created.text
    profile_id = created.json()['id']
    target = base + '/' + str(profile_id)
    async with AsyncSessionLocal() as db:
        cred = await CredentialService.get_credential(db, profile_id)
        _, ctx = CustomModuleAdapter()._resolve_context(decrypt_secret(cred.encrypted_api_key),
            CredentialService.module_runtime_configuration(cred.provider, cred))
    try:
        # Migration reads the old private pool at startup, not arbitrary later file edits.
        cfg = adapter._settings(ctx)
        legacy_root = tmp_path / 'state' / 'MyAIrouter' / 'freebuff' / f"{cfg['profile']}-{cfg['instance']}"
        creds = legacy_root / 'data' / 'credentials'
        creds.mkdir(parents=True)
        (creds / 'synthetic.json').write_text(json.dumps({'id': 'synthetic', 'email': 'local@example.invalid', 'authToken': 'local-token'}))
        rt = await adapter._runtime(ctx)
        assert await adapter._runtime(ctx) is rt and not seen
        assert rt['root'].stat().st_mode & 0o777 == 0o700
        assert rt['configuration']['proxy'] == api and rt['configuration']['engine'] == 'freebuff2api-wokers'
        assert not (rt['root'] / 'config.json').exists()
        assert not (tmp_path / 'wrong-data').exists()
        peer_ctx = ctx.model_copy(update={'extra_config': {'credential_id': 702, 'credential_instance': 'local-record-2'}})
        peer = await adapter._runtime(peer_ctx)
        assert peer['url'] != rt['url'] and peer['root'] != rt['root']

        models = await adapter.list_models(ctx)
        assert models
        ctx.model_id = models[0].provider_model_id
        answer = await adapter.chat_completions(ChatCompletionRequest(model='local/alias', messages=[
            {'role': 'user', 'content': 'complete'}]), ctx)
        assert answer.choices[0].message.content == 'Проверка managed' and answer.usage is None
        assert any(route == '/api/v1/chat/completions' for route, _ in seen)
        synced = await client.post(target + '/sync-models')
        assert synced.status_code == 200 and synced.json()['models_discovered'] == 1
        catalog = (await client.get('/v1/models')).json()['data']
        model = next(row['id'] for row in catalog if row['id'].startswith('module_freebuff/'))
        for extra in ({'logprobs': True}, {'future_parameter': 1}):
            before = len(seen)
            refused = await client.post('/v1/chat/completions', json={'model': model,
                'messages': [{'role': 'user', 'content': 'complete'}], **extra})
            assert refused.status_code == 400 and next(iter(extra)) in refused.text
            assert len(seen) == before
        for streaming in (False, True):
            reply = await client.post('/v1/chat/completions', json={'model': model,
                'messages': [{'role': 'user', 'content': 'complete'}], 'stream': streaming})
            assert reply.status_code == 200, reply.text
            if streaming:
                from app.modules.base import ChatStreamAccumulator
                accumulator = ChatStreamAccumulator(); accumulator.feed(reply.text)
                assert accumulator.response(model, require_complete=True).choices[0].message.content == 'Проверка managed'
            else:
                assert reply.json()['choices'][0]['message']['content'] == 'Проверка managed'
        tool_request = ChatCompletionRequest(model='local/alias', messages=[{'role': 'user', 'content': 'client tool'}],
            tools=[{'type': 'function', 'function': {'name': 'fixture_lookup',
                'parameters': {'type': 'object', 'properties': {'key': {'type': 'string'}}}}}], tool_choice='auto')
        tool_result = await adapter.chat_completions(tool_request, ctx)
        call = tool_result.choices[0].message.tool_calls[0]
        assert call.id == 'call-native' and call.function.name == 'fixture_lookup'
        assert json.loads(call.function.arguments) == {'key': 'значение'}
        from app.schemas.chat import ChatMessage
        continuation = tool_request.model_copy(update={'messages': [*tool_request.messages,
            tool_result.choices[0].message, ChatMessage(role='tool', tool_call_id=call.id, content='client-only result')]})
        final = await adapter.chat_completions(continuation, ctx)
        assert final.choices[0].message.content == 'Проверка managed'
        forwarded = next(body for route, body in reversed(seen) if route == '/api/v1/chat/completions')
        assert forwarded['messages'][-1]['tool_call_id'] == call.id
        assert forwarded['messages'][-1]['content'] == 'client-only result'
        saved = await client.put(target, json={'fields': {'startup_timeout': 11}})
        assert saved.status_code == 200 and rt['process'].returncode is not None
        assert (await client.get(base)).json()[0]['fields']['startup_timeout'] == 11
        deleted = await client.delete(target)
        assert deleted.status_code == 200 and (await client.get(base)).json() == []
        assert peer['process'].returncode is None
        peer['process'].stdin.close()
        await asyncio.wait_for(peer['process'].wait(), 25)
        assert peer['process'].returncode is not None
        # Existing account cannot be silently moved to another egress.
        moved = ctx.model_copy(update={'proxy_url': 'http://127.0.0.1:1',
            'extra_config': {k: v for k, v in ctx.extra_config.items() if k != 'profile_proxy_id'}})
        with pytest.raises(RouterException):
            await adapter._runtime(moved)
        replacement = ctx.model_copy(update={'extra_config': {'credential_id': profile_id, 'credential_instance': 'new-record'}})
        fresh = await adapter._runtime(replacement)
        assert fresh['root'] != rt['root'] and not list((fresh['root'] / 'data/credentials').glob('*.json'))
    finally:
        await client.aclose()
        await adapter.close()
        server.shutdown(); server.server_close(); thread.join(timeout=5)


def test_workers_settings_preserve_legacy_profile_and_validate_origin():
    adapter = load().FreebuffAdapter()
    ctx = ModuleExecutionContext(credentials={'project_path': '/home/kiril/PythonProjects/freebuff-proxy',
        'bun_path': '/missing/unused/bun'}, extra_config={'credential_id': 7, 'credential_instance': 'fixture'})
    cfg = adapter._settings(ctx)
    assert cfg['source'] == '/home/kiril/PythonProjects/freebuff2api-wokers'
    assert cfg['engine'] == 'freebuff2api-wokers' and 'bun' not in cfg
    assert cfg['accounts'] == [] and cfg['apiBase'] == 'https://www.codebuff.com'
    with pytest.raises(RouterException, match='origin'):
        adapter._settings(ctx.model_copy(update={'credentials': {'api_base': 'https://user:password@example.invalid'}}))
    with pytest.raises(RouterException, match='authToken'):
        adapter._settings(ctx.model_copy(update={'credentials': {'auth_token': 'token-one,token-two'}}))


@pytest.mark.asyncio
async def test_worker_update_refusal_remains_safe_nonretryable(monkeypatch):
    module = load(); adapter = module.FreebuffAdapter()
    real_client = httpx.AsyncClient
    monkeypatch.setattr(module, '_client', lambda runtime, timeout: real_client(
        transport=httpx.MockTransport(lambda _: httpx.Response(410, json={
            'error': {'code': 'freebuff_update_required', 'message': 'SECRET upstream material'}}))))
    async def runtime(_):
        return {'url': 'http://127.0.0.1:9999', 'token': 'synthetic'}
    monkeypatch.setattr(adapter, '_runtime', runtime)
    with pytest.raises(RouterException, match='freebuff_update_required') as error:
        await adapter.chat_completions(ChatCompletionRequest(model='m', messages=[]), ModuleExecutionContext())
    assert error.value.status_code == 502 and error.value.upstream_status == 410
    assert not error.value.is_retryable and not error.value.is_fallback_eligible
    assert 'SECRET' not in str(error.value)


@pytest.mark.asyncio
async def test_worker_access_refusal_is_not_retryable_502(monkeypatch):
    module = load(); adapter = module.FreebuffAdapter()
    calls = []
    def denied(request):
        calls.append(request)
        return httpx.Response(403, json={'error': {'code': 'freebuff_access_blocked',
            'reason': 'region_locked', 'message': 'SECRET upstream account'}})
    real_client = httpx.AsyncClient
    monkeypatch.setattr(module, '_client', lambda runtime, timeout: real_client(
        transport=httpx.MockTransport(denied)))
    async def runtime(_):
        return {'url': 'http://127.0.0.1:9999', 'token': 'synthetic'}
    monkeypatch.setattr(adapter, '_runtime', runtime)
    with pytest.raises(RouterException) as error:
        await adapter.chat_completions(ChatCompletionRequest(model='m', messages=[]), ModuleExecutionContext())
    assert error.value.status_code == 403 and error.value.upstream_status == 403
    assert error.value.category.value == 'AUTH_ERROR'
    assert not error.value.is_retryable and not error.value.is_fallback_eligible
    assert error.value.replay_safe is False and 'region_locked' in str(error.value)
    assert len(calls) == 1 and 'SECRET' not in str(error.value)


@pytest.mark.asyncio
async def test_freebuff_blocked_profile_is_explicit_on_another_model(monkeypatch):
    from app.core.database import AsyncSessionLocal
    from app.core.circuit_breaker import CircuitBreaker
    from app.models.entities import Provider, ProviderCredential, DiscoveredModel
    import app.routing.engine as routing
    breaker = CircuitBreaker()
    monkeypatch.setattr(routing, 'circuit_breaker', breaker)
    alias = 'module_freebuff/upstage/solar-mini4'
    async with AsyncSessionLocal() as db:
        provider = Provider(name='Blocked Freebuff fixture', slug='blocked-freebuff-fixture',
            adapter_type='custom_module', base_url='module://freebuff', configuration={'module_id': 'freebuff'})
        db.add(provider); await db.flush()
        credential = ProviderCredential(provider_id=provider.id, name='Blocked fixture',
            encrypted_api_key='not-used', key_fingerprint='blocked-freebuff-fixture', masked_key='synthetic')
        db.add(credential); await db.flush()
        model = DiscoveredModel(provider_id=provider.id, provider_model_id='upstage/solar-mini4',
            display_name='Solar Mini 4', canonical_slug=alias, enabled=True, available=True)
        db.add(model); await db.commit()
        reason = 'Freebuff blocked access for this account or region: region_locked'
        from app.core.errors import ErrorCategory
        breaker.record_failure(credential.id, ErrorCategory.AUTH_ERROR, error_message=reason,
            model_id='upstage/solar-pro4')
        with pytest.raises(RouterException, match='region_locked') as error:
            await routing.RoutingEngine._get_candidate_credentials_for_model(db, alias)
        assert error.value.status_code == 403 and error.value.upstream_status == 403
        assert error.value.replay_safe is False and not error.value.is_retryable
        with pytest.raises(RouterException, match='region_locked'):
            await routing.RoutingEngine._candidate_credentials(db, provider, model, credential_id=credential.id)
        assert not breaker.is_available(credential.id)[0], 'Known block must not be auto-reset'
        breaker.reset(credential.id)
        assert len(await routing.RoutingEngine._get_candidate_credentials_for_model(db, alias)) == 1
        breaker.record_failure(credential.id, ErrorCategory.AUTH_ERROR, error_message='SECRET unknown failure')
        assert await routing.RoutingEngine._get_candidate_credentials_for_model(db, alias) == []
        breaker.reset(credential.id)
        breaker.record_failure(credential.id, ErrorCategory.RATE_LIMIT, error_message='model rate limit',
            model_id='upstage/solar-pro4')
        assert len(await routing.RoutingEngine._get_candidate_credentials_for_model(db, alias)) == 1
        breaker.reset(credential.id)
        breaker.record_failure(credential.id, ErrorCategory.AUTH_ERROR, error_message=reason)
        good = ProviderCredential(provider_id=provider.id, name='Available fixture',
            encrypted_api_key='not-used', key_fingerprint='available-freebuff-fixture', masked_key='synthetic')
        db.add(good); await db.commit()
        assert [c.id for c, _ in await routing.RoutingEngine._get_candidate_credentials_for_model(db, alias)] == [good.id]
        assert [c.id for c in await routing.RoutingEngine._candidate_credentials(db, provider, model)] == [good.id]
        provider.configuration = {'module_id': 'other'}
        db.add(provider); await db.commit()
        breaker.record_failure(good.id, ErrorCategory.AUTH_ERROR, error_message=reason)
        assert await routing.RoutingEngine._get_candidate_credentials_for_model(db, alias) == []


@pytest.mark.asyncio
async def test_worker_cannot_return_undeclared_signature_tool(monkeypatch):
    module = load(); adapter = module.FreebuffAdapter()
    wire = 'data: ' + json.dumps({'choices': [{'index': 0, 'delta': {'tool_calls': [{
        'index': 0, 'id': 'call-unrequested', 'type': 'function', 'function': {'name': 'decide', 'arguments': '{}'}}]},
        'finish_reason': 'tool_calls'}]}) + '\n\ndata: [DONE]\n\n'
    real_client = httpx.AsyncClient
    monkeypatch.setattr(module, '_client', lambda runtime, timeout: real_client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text=wire,
            headers={'content-type': 'text/event-stream'}))))
    async def runtime(_):
        return {'url': 'http://127.0.0.1:9999', 'token': 'synthetic'}
    monkeypatch.setattr(adapter, '_runtime', runtime)
    with pytest.raises(RouterException, match='undeclared tool') as error:
        await adapter.chat_completions(ChatCompletionRequest(model='m', messages=[]), ModuleExecutionContext())
    assert not error.value.is_retryable and not error.value.is_fallback_eligible


@pytest.mark.asyncio
async def test_worker_serializes_same_profile_without_changing_user_limits(monkeypatch):
    module = load(); adapter = module.FreebuffAdapter()
    runtime_state = {'url': 'http://127.0.0.1:9999', 'token': 'synthetic'}
    counters = {'active': 0, 'peak': 0}
    async def upstream(_):
        counters['active'] += 1
        counters['peak'] = max(counters['peak'], counters['active'])
        await asyncio.sleep(.03)
        counters['active'] -= 1
        return httpx.Response(200, text='data: {"choices":[{"index":0,"delta":{"content":"ok"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n',
            headers={'content-type': 'text/event-stream'})
    real_client = httpx.AsyncClient
    monkeypatch.setattr(module, '_client', lambda runtime, timeout: real_client(transport=httpx.MockTransport(upstream)))
    async def runtime(_):
        return runtime_state
    monkeypatch.setattr(adapter, '_runtime', runtime)
    await asyncio.gather(*(adapter.chat_completions(ChatCompletionRequest(model='m', messages=[]),
        ModuleExecutionContext()) for _ in range(2)))
    assert counters['peak'] == 1
