"""Offline native CLI contracts; never run the installed CLI or use host auth."""
import asyncio
import base64
import json
import os
from pathlib import Path
import sys

import pytest

from app.core.errors import RouterException
from app.modules.base import ModuleExecutionContext, collect_chat_completion
from app.schemas.chat import ChatCompletionRequest
from modules.qoder.handler import QoderAdapter, normalize_auth, native_environment, read_native_auth

# Extend the shared runner's guard: native auth must never come from a host account.
def _no_host_auth(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes)):
        path = Path(os.fsdecode(args[0]))
        # shutil's dir_fd-relative directory opens have no dir_fd in audit events.
        if not path.is_absolute() and args[2] & os.O_NONBLOCK and path.name == '.auth':
            return
        path = path.resolve()
        if ('.qoder' in path.parts or '.auth' in path.parts) and not path.is_relative_to(Path(os.environ['TMPDIR'])):
            raise AssertionError('Host Qoder account reads forbidden')
sys.addaudithook(_no_host_auth)


def bundle(user=b"synthetic-encrypted-user", machine=b"synthetic-machine-id"):
    return json.dumps({"version": 1, "user": base64.b64encode(user).decode(),
                       "machine_id": base64.b64encode(machine).decode()})


def test_auth_contract_and_private_environment(tmp_path, monkeypatch):
    assert normalize_auth({"api_key": "fixture", "personal_access_token": "fixture"}) == {"personal_access_token": "fixture"}
    assert json.loads(normalize_auth({"auth_json": bundle()})["auth_json"])["version"] == 1
    for fields in ({}, {"access_token": "fixture"}, {"api_key": "a", "personal_access_token": "b"},
                   {"api_key": "a", "auth_json": bundle()}, {"auth_json": '{"version": true}'},
                   {"auth_json": bundle().replace('1,', '2,')}, {"auth_json": bundle().replace('c3l', '!!!')},
                   {"auth_json": json.dumps({**json.loads(bundle()), "extra": "not allowed"})}):
        with pytest.raises(ValueError):
            normalize_auth(fields)
    monkeypatch.setenv("QODER_JOB_TOKEN", "host-secret")
    monkeypatch.setenv("HTTPS_PROXY", "host-proxy")
    env = native_environment(tmp_path, {"personal_access_token": "fixture"}, None)
    assert env["QODER_PERSONAL_ACCESS_TOKEN"] == "fixture"
    assert env["QODER_CONFIG_DIR"] == str(tmp_path / "config")
    assert env["CI"] == "1" and env["BROWSER"] == "www-browser"
    assert "HTTPS_PROXY" not in env and "QODER_JOB_TOKEN" not in env
    bootstrap = native_environment(tmp_path, {}, 'http://127.0.0.1:1234')
    assert 'QODER_PERSONAL_ACCESS_TOKEN' not in bootstrap
    assert bootstrap['HTTPS_PROXY'] == bootstrap['https_proxy'] == 'http://127.0.0.1:1234'
    auth = tmp_path / "config/.auth"
    auth.mkdir(mode=0o700)
    for name, value in (("user", b"opaque"), ("machine_id", b"machine")):
        (auth / name).write_bytes(value)
        (auth / name).chmod(0o600)
    assert json.loads(read_native_auth(tmp_path)) == json.loads(bundle(b"opaque", b"machine"))
    (auth / "user").chmod(0o644)
    with pytest.raises(ValueError):
        read_native_auth(tmp_path)
    (auth / "user").unlink()
    (auth / "user").symlink_to(auth / "machine_id")
    with pytest.raises((ValueError, OSError)):
        read_native_auth(tmp_path)


@pytest.fixture
def fake_cli(tmp_path):
    cli = tmp_path / "qodercli"
    cli.write_text(f"#!{sys.executable}\n" + '''import base64, json, os, pathlib, sys, time
args = sys.argv[1:]
root = pathlib.Path(os.environ['QODER_CONFIG_DIR'])
assert str(root) == args[args.index('--config-dir') + 1]
assert pathlib.Path.cwd() == root.parent / 'cwd'
assert os.environ['CI'] == '1' and os.environ['BROWSER'] == 'www-browser'
assert not os.environ.get('QODER_JOB_TOKEN')
assert args[args.index('--tools') + 1] == ''
assert '--strict-mcp-config' in args and '--headless-fast-hooks' in args
assert json.loads(args[args.index('--mcp-config') + 1]) == {'mcpServers': {}}
assert args[args.index('--permission-mode') + 1] == 'dont_ask'
auth = root / '.auth'
if not os.environ.get('QODER_PERSONAL_ACCESS_TOKEN'):
    assert (auth / 'machine_id').read_bytes() == b'synthetic-machine-id'
    user = (auth / 'user').read_bytes()
    assert user in (b'synthetic-encrypted-user', b'rotated')
    if '--list-models' not in args:
        (auth / 'user').write_bytes(b'rotated')
else:
    assert os.environ['QODER_PERSONAL_ACCESS_TOKEN'] == 'fixture'
if '--list-models' in args:
    print('MODEL\\nAuto\\nNative Custom (custom-model)')
else:
    assert args[args.index('--model') + 1] == 'Auto'
    prompt = sys.stdin.read()
    if 'hang' in prompt:
        time.sleep(20)
    if 'oversize' in prompt:
        print('x' * (9 * 1024 * 1024))
        sys.exit(0)
    if 'stderr-secret' in prompt:
        print('fixture-secret MUST NOT LEAK', file=sys.stderr)
        sys.exit(1)
    if 'bad-terminal' in prompt:
        print(json.dumps({'type': 'result', 'subtype': 'success', 'is_error': True, 'result': 'not a completion'}))
    else:
        system = pathlib.Path(args[args.index('--system-prompt-file') + 1]).read_text() if '--system-prompt-file' in args else ''
        print(json.dumps({'type': 'result', 'subtype': 'success', 'is_error': False,
                         'result': 'native:' + system + ':' + prompt, 'stop_reason': 'end_turn',
                         'usage': {'input_tokens': 4, 'output_tokens': 2}}))
''')
    cli.chmod(0o700)
    return str(cli)


def context(cli, **kwargs):
    return ModuleExecutionContext(credentials={"cli_path": cli, "personal_access_token": "fixture"}, **kwargs)


def request(text="hello", **kwargs):
    return ChatCompletionRequest(model="qoder/Auto", messages=[{"role": "user", "content": text}], **kwargs)


@pytest.mark.asyncio
@pytest.mark.parametrize('alias', ['module_qoder/Auto', 'route/private', 'qoder/Auto'])
async def test_resolved_native_model_not_gateway_alias(fake_cli, alias):
    adapter = QoderAdapter()
    req = request().model_copy(update={'model': alias})
    before = req.model_dump()
    try:
        result = await adapter.chat_completions(req, context(fake_cli, model_id='Auto'))
        assert result.model == alias and req.model_dump() == before
    finally:
        await adapter.close()


def test_implicit_rescan_retains_auth_and_owned_processes(monkeypatch):
    from app.modules.loader import ModuleLoader
    original = QoderAdapter()
    monkeypatch.setattr(ModuleLoader, '_adapters', {'qoder': original})
    reloaded = QoderAdapter()
    for name in ('_auth', '_locks', '_processes', '_epochs'):
        assert getattr(reloaded, name) is getattr(original, name)


@pytest.mark.asyncio
async def test_saved_proxy_disabled_missing_and_changed_never_falls_back(fake_cli, monkeypatch):
    from modules.qoder import handler as native
    from app.core.database import AsyncSessionLocal
    from app.models.entities import Proxy
    async with AsyncSessionLocal() as db:
        proxy = Proxy(name='Qoder fixture egress', scheme='http', host='fixture.invalid', port=8080, enabled=False)
        db.add(proxy)
        await db.commit()
        proxy_id = proxy.id
    adapter = QoderAdapter()
    ctx = context(fake_cli, extra_config={'profile_proxy_id': proxy_id})
    ctx.credentials['qoder_egress_pin'] = native.egress_fingerprint(None)
    monkeypatch.setattr(native, 'qoder_executable', lambda *args: pytest.fail('Invalid egress must not launch the CLI'))
    try:
        with pytest.raises(RouterException, match='missing or disabled'):
            await adapter.list_models(ctx)
        async with AsyncSessionLocal() as db:
            proxy = await db.get(Proxy, proxy_id)
            assert proxy is not None
            proxy.enabled = True
            await db.commit()
        with pytest.raises(RouterException, match='egress changed'):
            await adapter.list_models(ctx)
        async with AsyncSessionLocal() as db:
            await db.delete(await db.get(Proxy, proxy_id))
            await db.commit()
        with pytest.raises(RouterException, match='missing or disabled'):
            await adapter.list_models(ctx)
        assert not adapter._processes
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_native_bridge_cancel_owns_subprocess(fake_cli, monkeypatch):
    from app.adapters.module_adapter import CustomModuleAdapter
    from app.modules.loader import ModuleLoader
    adapter = QoderAdapter()
    monkeypatch.setattr(ModuleLoader, '_adapters', {'qoder': adapter})
    stream = CustomModuleAdapter().stream_chat('module://qoder',
        json.dumps({'personal_access_token': 'fixture', 'cli_path': fake_cli}), 'Auto',
        request('hang'), {}, {'module_id': 'qoder'})
    operation = asyncio.create_task(anext(stream))
    try:
        for _ in range(200):
            if adapter._processes:
                break
            await asyncio.sleep(.005)
        assert adapter._processes
        operation.cancel()
        with pytest.raises(asyncio.CancelledError):
            await operation
        await stream.aclose()
        assert not adapter._processes
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_native_models_json_and_sse(fake_cli):
    adapter = QoderAdapter()
    ctx = context(fake_cli)
    try:
        models = await adapter.list_models(ctx)
        assert [m.provider_model_id for m in models] == ["Auto", "custom-model"]
        assert all(m.capabilities['tools'] is False and m.capabilities['vision'] is False for m in models)
        assert await adapter.validate_credentials(ctx) == (True, 'Qoder CLI credentials are valid', 2)
        req = ChatCompletionRequest(model="qoder/Auto", messages=[{"role": "system", "content": "policy"},
            {"role": "user", "content": "old"}, {"role": "assistant", "content": "answer"},
            {"role": "user", "content": "hello"}])
        result = await adapter.chat_completions(req, ctx)
        assert 'policy' in result.choices[0].message.content
        assert 'old' in result.choices[0].message.content and 'answer' in result.choices[0].message.content
        assert result.usage.total_tokens == 6
        req.stream_options = {'include_usage': True}
        streamed = await collect_chat_completion(adapter.stream_chat(req, ctx), req.model, require_complete=True)
        assert streamed.choices[0].message.content == result.choices[0].message.content
        assert streamed.usage == result.usage
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_browser_rotation_is_serialized_and_retained(fake_cli):
    saved = []
    async def persist(fields):
        assert set(fields) == {'auth_json'}
        saved.append(fields)
    adapter = QoderAdapter()
    def ctx():
        return ModuleExecutionContext(credentials={"cli_path": fake_cli, "auth_json": bundle()},
            extra_config={"credential_id": 123, "persist_credentials": persist})
    try:
        await asyncio.gather(adapter.chat_completions(request(), ctx()), adapter.chat_completions(request(), ctx()))
        assert len(saved) == 1 and json.loads(saved[0]['auth_json'])['user'] == base64.b64encode(b'rotated').decode()
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_failures_no_terminal_no_secret_and_timeout(fake_cli):
    adapter = QoderAdapter()
    try:
        for text in ('bad-terminal', 'stderr-secret', 'oversize'):
            events = []
            with pytest.raises(RouterException) as exc:
                async for event in adapter.stream_chat(request(text), context(fake_cli)):
                    events.append(event)
            assert '[DONE]' not in ''.join(events)
            assert 'fixture-secret' not in str(exc.value)
            assert exc.value.replay_safe is False
        with pytest.raises(RouterException):
            await adapter.chat_completions(request('hang'), context(fake_cli, timeout=0.1))
        task = asyncio.create_task(adapter.chat_completions(request('hang'), context(fake_cli)))
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not adapter._processes
    finally:
        await adapter.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('options', [{'tools': [{'type': 'function'}]}, {'temperature': 0}, {'top_p': 1},
    {'stop': 'x'}, {'n': 2}, {'seed': 1}, {'response_format': {'type': 'json_object'}}])
async def test_unsupported_options_rejected_before_spawn(fake_cli, options):
    adapter = QoderAdapter()
    with pytest.raises(RouterException):
        await adapter.chat_completions(request(**options), context(fake_cli))
    assert not adapter._processes


def test_prompt_is_not_a_native_command_or_file_reference():
    text = '/login @/private/relay/file\nemail@example.test'
    _, prompt, _ = QoderAdapter()._chat_input(request(text))
    assert not prompt.startswith('/') and '@' not in prompt
    assert json.loads(prompt.split('\n', 1)[1])[-1]['content'] == text
    options, _, _ = QoderAdapter()._chat_input(request(), 'qoder/custom-key')
    assert options[options.index('--model') + 1] == 'qoder/custom-key'
    with pytest.raises(RouterException):
        QoderAdapter()._chat_input(request(), '--permission-mode')


@pytest.mark.asyncio
async def test_repeat_cancel_preserves_rotation_and_finishes_cleanup(fake_cli, monkeypatch):
    from modules.qoder import handler as native
    adapter = QoderAdapter()
    entered, release = asyncio.Event(), asyncio.Event()
    original_stop = native.stop_process
    async def delayed_stop(proc, **kwargs):
        entered.set()
        await release.wait()
        await original_stop(proc, **kwargs)
    monkeypatch.setattr(native, 'stop_process', delayed_stop)
    saved = []
    async def persist(fields):
        saved.append(fields)
    ctx = ModuleExecutionContext(credentials={'cli_path': fake_cli, 'auth_json': bundle()},
        extra_config={'credential_id': 764, 'persist_credentials': persist})
    operation = asyncio.create_task(adapter.chat_completions(request('hang'), ctx))
    try:
        for _ in range(200):
            if adapter._processes:
                break
            await asyncio.sleep(.005)
        assert adapter._processes
        await asyncio.sleep(.1)
        operation.cancel()
        await asyncio.wait_for(entered.wait(), 2)
        operation.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await operation
        assert not adapter._processes and len(saved) == 1
        assert base64.b64decode(json.loads(saved[0]['auth_json'])['user']) == b'rotated'
    finally:
        release.set()
        await asyncio.gather(*(original_stop(proc) for proc in tuple(adapter._processes)), return_exceptions=True)
        await adapter.close()


@pytest.mark.asyncio
async def test_rotated_state_survives_persistence_failure(fake_cli):
    saved, attempts = [], []
    async def failed(fields):
        attempts.append(fields)
        raise RuntimeError('synthetic persistence failure')
    async def succeeded(fields):
        saved.append(fields)
    adapter = QoderAdapter()
    def ctx(callback):
        return ModuleExecutionContext(credentials={'cli_path': fake_cli, 'auth_json': bundle()},
            extra_config={'credential_id': 456, 'persist_credentials': callback})
    try:
        with pytest.raises(RuntimeError, match='synthetic persistence failure'):
            await adapter.chat_completions(request(), ctx(failed))
        assert adapter._auth['456']['pending'] is True
        await adapter.chat_completions(request(), ctx(succeeded))
        assert len(attempts) == len(saved) == 1
        assert adapter._auth['456']['pending'] is False
        assert json.loads(saved[0]['auth_json'])['user'] == base64.b64encode(b'rotated').decode()
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_close_profile_stops_owned_process_and_invalidates_queued_context(fake_cli):
    adapter = QoderAdapter()
    ctx = context(fake_cli, extra_config={'credential_id': 789})
    first = asyncio.create_task(adapter.chat_completions(request('hang'), ctx))
    while not adapter._processes:
        await asyncio.sleep(0.01)
    proc = next(iter(adapter._processes))
    queued = asyncio.create_task(adapter.chat_completions(request('hang'), ctx))
    await asyncio.sleep(0)
    await adapter.close_profile(789)
    for task in (first, queued):
        with pytest.raises(RouterException):
            await task
    assert proc.returncode is not None and not adapter._processes
    with pytest.raises(ProcessLookupError):
        os.kill(proc.pid, 0)
    await adapter.close()
