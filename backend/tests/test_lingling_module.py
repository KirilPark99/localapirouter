"""Lingling bridge regressions: synthetic OpenCode SSE, no Tor/upstream traffic."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from modules.lingling import handler as h
from app.modules.base import ModuleExecutionContext
from app.modules.loader import ModuleLoader
from app.schemas.chat import ChatCompletionRequest
from app.core.errors import RouterException
from app.services.credential_service import CredentialService


MODEL = "fixture-free"
INFO = {"id": MODEL, "name": "Fixture", "cost": {"input": 0, "output": 0},
        "limit": {"context": 8192, "output": 4096},
        "capabilities": {"input": {"image": True}, "reasoning": True, "toolcall": True}, "variants": {"low": {}}}


def request(**kw):
    return ChatCompletionRequest(model=MODEL, messages=[{"role": "user", "content": "hello"}], **kw)


class Events(httpx.AsyncByteStream):
    def __init__(self, events):
        self.events, self.closed = events, False

    async def __aiter__(self):
        for kind, props in self.events:
            raw = ("data: " + json.dumps({"id": "evt_fixture", "type": kind, "properties": props}) + "\r\n\r\n").encode()
            for offset in range(0, len(raw), 11):
                yield raw[offset:offset + 11]

    async def aclose(self):
        self.closed = True


def wire(sid="ses_fixture"):
    msg = {"id": "msg_assistant", "sessionID": sid, "role": "assistant",
           "time": {"created": 1}, "parentID": "msg_user", "modelID": MODEL,
           "providerID": "opencode", "mode": "router", "agent": "router",
           "path": {"cwd": "/fixture", "root": "/fixture"}, "cost": 0,
           "tokens": {"input": 10, "output": 3, "reasoning": 2, "cache": {"read": 1, "write": 0}}}
    part = {"id": "prt_text", "sessionID": sid, "messageID": msg["id"], "type": "text", "text": ""}
    return [
        ("message.updated", {"sessionID": "ses_other", "info": {**msg, "sessionID": "ses_other"}}),
        ("message.updated", {"sessionID": sid, "info": msg}),
        ("message.part.updated", {"sessionID": sid, "part": part, "time": 1}),
        ("message.part.delta", {"sessionID": sid, "messageID": msg["id"], "partID": part["id"], "field": "text", "delta": "OK"}),
        ("message.part.updated", {"sessionID": sid, "part": {**part, "text": "OK"}, "time": 2}),
        ("message.part.updated", {"sessionID": sid, "part": {**part, "id": "prt_think", "type": "reasoning", "text": "Think"}, "time": 2}),
        ("message.updated", {"sessionID": sid, "info": {**msg, "time": {"created": 1, "completed": 2}, "finish": "stop"}}),
        ("session.status", {"sessionID": sid, "status": {"type": "idle"}}),
    ]


def install(monkeypatch, events=None, root=None):
    adapter, calls, streams = h.LinglingAdapter(), [], []
    runtime = {"url": "http://127.0.0.1:1234", "password": "synthetic", "lock": asyncio.Lock()}
    limit = dict(INFO["limit"])

    async def fake_runtime(ctx, client_tools=False):
        runtime["root"] = root
        runtime["client_tools"] = client_tools
        return runtime

    def dispatch(req):
        body = json.loads(req.content) if req.content else None
        calls.append((req.method, req.url.path, body))
        if req.url.path == "/provider":
            return httpx.Response(200, json={"all": [{"id": "opencode", "models": {MODEL: {**INFO, "limit": dict(limit)}}}]})
        if req.url.path == "/config":
            if req.method == "GET":
                return httpx.Response(200, json={"experimental": {"continue_loop_on_deny": not runtime["client_tools"]}})
            limit.update(body["provider"]["opencode"]["models"][MODEL]["limit"])
            return httpx.Response(200, json={})
        if req.url.path == "/mcp":
            return httpx.Response(200, json={"client": {"status": "connected"}})
        if req.url.path == "/session" and req.method == "POST":
            return httpx.Response(200, json={"id": "ses_fixture"})
        if req.url.path == "/event":
            stream = Events(wire() if events is None else events)
            streams.append(stream)
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=stream)
        return httpx.Response(204)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(adapter, "_runtime", fake_runtime)
    monkeypatch.setattr(h.httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(dispatch), **kw))
    return adapter, calls, streams


def test_client_tool_mcp_advertises_schemas_but_never_executes(tmp_path):
    import os
    import subprocess
    import sys
    sentinel = tmp_path / "must-not-exist"
    tools = [{"name": "t0", "description": "Client-only fixture", "inputSchema": {"type": "object", "properties": {"command": {"type": "string"}}}}]
    schema = tmp_path / "tools.json"
    schema.write_text(json.dumps(tools))
    messages = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "t0", "arguments": {"command": "touch " + str(sentinel)}}}]
    run = subprocess.run([sys.executable, str(Path(h.__file__)), "--client-tools", str(schema)],
        input="".join(json.dumps(m) + "\n" for m in messages), text=True, capture_output=True,
        env={"PATH": os.environ.get("PATH", ""), "PYTHONPATH": "/home/kiril/PythonProjects/lingling", "PYTHONDONTWRITEBYTECODE": "1"}, timeout=10)
    assert run.returncode == 0, run.stderr
    replies = [json.loads(line) for line in run.stdout.splitlines()]
    assert [r["id"] for r in replies] == [1, 2, 3]
    assert replies[1]["result"]["tools"] == tools and replies[2]["result"]["isError"] is True
    assert not sentinel.exists()


def client_wire(count=1):
    # Same nested event envelope/ordering as the genuine-client MCP probe.
    msg = wire()[1][1]["info"]
    events = [("message.updated", {"info": msg})]
    for index in range(count):
        part = {"id": f"prt_tool{index}", "sessionID": "ses_fixture", "messageID": msg["id"],
            "type": "tool", "tool": f"client_t{index}", "callID": f"call_real_{index}"}
        events += [("message.part.updated", {"part": {**part, "state": {"status": "pending", "input": {}, "raw": ""}}}),
            ("permission.asked", {"sessionID": "ses_fixture", "id": f"per_external{index}", "permission": part["tool"],
                "metadata": {}, "tool": {"messageID": msg["id"], "callID": part["callID"]}, "patterns": ["*"], "always": ["*"]}),
            ("message.part.updated", {"part": {**part, "state": {"status": "running", "input": {"key": f"value-{index}"}}}}),
            ("message.part.updated", {"part": {**part, "state": {"status": "error", "input": {"key": f"value-{index}"}, "error": "Permission denied"}}})]
    final = {**msg, "finish": "tool-calls", "time": {"created": 1, "completed": 2}}
    return events + [("message.updated", {"info": final}), ("message.updated", {"info": final}),
        ("session.status", {"sessionID": "ses_fixture", "status": {"type": "idle"}})]


@pytest.mark.asyncio
@pytest.mark.parametrize("choice,count", [(None, 1), ("auto", 4), ("required", 1),
    ({"type": "function", "function": {"name": "fixture_lookup0"}}, 1)])
async def test_client_tools_actual_ids_arguments_nonstream_and_sse(monkeypatch, tmp_path, choice, count):
    adapter, calls, streams = install(monkeypatch, client_wire(count), root=tmp_path)
    definitions = [{"type": "function", "function": {"name": f"fixture_lookup{i}", "parameters": {"type": "object"}}} for i in range(count)]
    req = request(tools=definitions, tool_choice=choice)
    ctx = ModuleExecutionContext(model_id=MODEL, timeout=5)
    result = await adapter.chat_completions(req, ctx)
    assert result.choices[0].finish_reason == "tool_calls"
    invocations = result.choices[0].message.tool_calls
    assert invocations is not None and result.usage is not None
    assert len(invocations) == count and result.usage.total_tokens == 16
    for index, item in enumerate(invocations):
        assert item.id == f"call_real_{index}" and item.function.name == f"fixture_lookup{index}"
        assert json.loads(item.function.arguments) == {"key": f"value-{index}"}
    chunks = [x async for x in adapter.stream_chat(req.model_copy(update={"stream": True}), ctx)]
    decoded = [json.loads(c.removeprefix("data: ")) for c in chunks[:-1]]
    assert decoded[-1]["choices"][0]["finish_reason"] == "tool_calls" and chunks[-1] == "data: [DONE]\n\n"
    assert sum(len(c["choices"][0]["delta"].get("tool_calls", [])) for c in decoded) == count
    assert all(stream.closed for stream in streams) and not (tmp_path / "client-tools.json").exists()
    assert sum(path == "/mcp/client/disconnect" for _, path, _ in calls) == 2
    replies = [b for _, path, b in calls if path.startswith("/permission/")]
    assert len(replies) == count * 2 and all(b == {"reply": "reject"} for b in replies)
    assert not any("tools/call" in path for _, path, _ in calls)


@pytest.mark.asyncio
@pytest.mark.parametrize("events,choice,parallel,error", [
    (wire(), "required", None, "required tool_choice"),
    (client_wire(2), "auto", False, "parallel_tool_calls"),
    (client_wire(1)[:-2], "auto", None, "disconnected")])
async def test_client_tool_constraints_never_fabricate_success(monkeypatch, tmp_path, events, choice, parallel, error):
    adapter, calls, streams = install(monkeypatch, events, root=tmp_path)
    definitions = [{"type": "function", "function": {"name": f"fixture_lookup{i}", "parameters": {"type": "object"}}} for i in range(2)]
    with pytest.raises(RouterException, match=error):
        await adapter.chat_completions(request(tools=definitions, tool_choice=choice, parallel_tool_calls=parallel), ModuleExecutionContext(model_id=MODEL, timeout=5))
    assert all(stream.closed for stream in streams) and not (tmp_path / "client-tools.json").exists()
    assert any(path == "/mcp/client/disconnect" for _, path, _ in calls)


@pytest.mark.asyncio
async def test_client_tool_stream_close_releases_schema_and_session(monkeypatch, tmp_path):
    adapter, calls, streams = install(monkeypatch, client_wire(), root=tmp_path)
    source = adapter.stream_chat(request(tools=[{"type": "function", "function": {"name": "fixture"}}]), ModuleExecutionContext(model_id=MODEL, timeout=5))
    await anext(source)
    assert (tmp_path / "client-tools.json").exists()
    await source.aclose()
    assert streams[0].closed and not (tmp_path / "client-tools.json").exists()
    assert any(path == "/mcp/client/disconnect" for _, path, _ in calls)


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["/abort", "/mcp/client/disconnect"])
async def test_cancelled_cleanup_cannot_leave_client_schemas_reusable(monkeypatch, tmp_path, phase):
    adapter, calls, streams = install(monkeypatch, client_wire(), root=tmp_path)
    runtime_fn, factory = adapter._runtime, h.httpx.AsyncClient
    stopped = []
    async def owned_runtime(ctx, client_tools=False):
        runtime = await runtime_fn(ctx, client_tools=client_tools)
        runtime["process"] = SimpleNamespace(pid=12345)
        adapter._workers[str(tmp_path)] = runtime
        return runtime
    async def stop(proc):
        stopped.append(proc.pid)
    def cancel_factory(**kw):
        client = factory(**kw)
        post = client.post
        async def interrupted(path, **kwargs):
            if path.endswith(phase):
                raise asyncio.CancelledError()
            return await post(path, **kwargs)
        client.post = interrupted
        return client
    monkeypatch.setattr(adapter, "_runtime", owned_runtime)
    monkeypatch.setattr(h, "_stop_process", stop)
    monkeypatch.setattr(h.httpx, "AsyncClient", cancel_factory)
    source = adapter.stream_chat(request(tools=[{"type": "function", "function": {"name": "fixture"}}]), ModuleExecutionContext(model_id=MODEL, timeout=5))
    await anext(source)
    try:
        await source.aclose()
    except asyncio.CancelledError:
        pass
    assert streams[0].closed and not (tmp_path / "client-tools.json").exists()
    if phase == "/abort":
        assert any(path == "/mcp/client/disconnect" for _, path, _ in calls)
    else:
        assert stopped == [12345] and str(tmp_path) not in adapter._workers


def test_client_tool_names_map_without_collisions_and_forced_selection():
    adapter = h.LinglingAdapter()
    definitions = [{"type": "function", "function": {"name": n, "parameters": {"type": "object"}}} for n in ("send-mail", "send_mail")]
    assert {k: fn["name"] for k, fn in adapter._client_tools(request(tools=definitions)).items()} == {"client_t0": "send-mail", "client_t1": "send_mail"}
    selected = adapter._client_tools(request(tools=definitions, tool_choice={"type": "function", "function": {"name": "send_mail"}}))
    assert list(selected) == ["client_t1"]
    for malformed in (definitions + [definitions[0]], [{"type": "function", "function": {"name": "a", "description": {}}}],
                      [{"type": "not_function"}], [{"type": "function", "function": {"name": "n", "parameters": []}}]):
        with pytest.raises(RouterException):
            adapter._client_tools(request(tools=malformed))


@pytest.mark.asyncio
async def test_agent_native_denial_continues_without_approving_and_ignores_duplicate_idle(monkeypatch, tmp_path):
    original = wire()[1][1]["info"]
    events = [("message.updated", {"info": original}),
        ("permission.asked", {"sessionID": "ses_fixture", "id": "per_native", "permission": "bash"}),
        ("message.updated", {"info": {**original, "finish": "tool-calls", "time": {"completed": 2}}}),
        ("session.status", {"sessionID": "ses_fixture", "status": {"type": "idle"}}),
        ("session.idle", {"sessionID": "ses_fixture"})]
    for kind, props in wire()[1:]:
        props = json.loads(json.dumps(props).replace('msg_assistant', 'msg_continuation'))
        events.append((kind, props))
    adapter, calls, streams = install(monkeypatch, events, root=tmp_path)
    result = await adapter.chat_completions(request(tools=[{"type": "function", "function": {"name": "fixture"}}]), ModuleExecutionContext(model_id=MODEL, timeout=5))
    assert result.choices[0].message.content == "OK" and not result.choices[0].message.tool_calls
    assert sum(path.endswith("/prompt_async") for _, path, _ in calls) == 2
    assert all(body["reply"] == "reject" for _, path, body in calls if path.startswith("/permission/"))
    assert result.usage is not None and result.usage.total_tokens == 32


def test_profile_runtime_identity_and_settings(monkeypatch, tmp_path):
    provider = SimpleNamespace(adapter_configuration={"module_id": "lingling"})
    a = CredentialService.module_runtime_configuration(provider, SimpleNamespace(id=1, metadata_json={}))
    b = CredentialService.module_runtime_configuration(provider, SimpleNamespace(id=2, metadata_json={}))
    assert a["credential_id"] == 1 and b["credential_id"] == 2
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    adapter = h.LinglingAdapter()
    one = adapter._root(ModuleExecutionContext(extra_config=a), {})
    two = adapter._root(ModuleExecutionContext(extra_config=b), {})
    assert one != two and one.stat().st_mode & 0o777 == 0o700
    source = tmp_path / "source" / "lingling"
    source.mkdir(parents=True)
    for name in ("__init__.py", "lanes.py", "relay.py", "mitm.py"):
        (source / name).touch()
    fields = {"project_path": str(source.parent), "opencode_path": "/bin/true", "tor_path": "/bin/true"}
    cfg = adapter._settings(ModuleExecutionContext(credentials=fields))
    assert cfg["lanes"] == 5 and cfg["transport_mode"] == "tor"
    assert cfg["proxy_policy"] == "balance" and cfg["proxy_ids"] == []
    for update in ({"lanes": 0}, {"lanes": True}, {"startup_timeout": 1}, {"countries": "xyz"}):
        with pytest.raises(RouterException):
            adapter._settings(ModuleExecutionContext(credentials={**fields, **update}))
    with pytest.raises(RouterException):
        adapter._settings(ModuleExecutionContext(credentials=fields, proxy_url="http://fixture"))


def test_client_environment_and_catalog(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-do-not-pass")
    monkeypatch.setenv("HTTPS_PROXY", "http://fixture")
    env = h._client_env(tmp_path)
    assert "OPENAI_API_KEY" not in env and "HTTPS_PROXY" not in env
    cfg = json.loads((Path(env["XDG_CONFIG_HOME"]) / "opencode/opencode.json").read_text())
    assert cfg["permission"] == "ask" and cfg["agent"]["build"]["permission"] == "ask"
    assert cfg["experimental"]["continue_loop_on_deny"] is True
    assert "steps" not in cfg["agent"]["build"] and "tools" not in cfg["agent"]["build"]
    cfg["provider"] = {"opencode": {"models": {MODEL: {"limit": {"output": 32}}}}}
    config_path = Path(env["XDG_CONFIG_HOME"]) / "opencode/opencode.json"
    config_path.write_text(json.dumps(cfg))
    h._client_env(tmp_path)
    assert "provider" not in json.loads(config_path.read_text()), "Worker restart must reset persisted request limits"
    h._client_env(tmp_path, continue_on_deny=False)
    assert json.loads(config_path.read_text())["experimental"]["continue_loop_on_deny"] is False
    model = {**INFO, "providerID": "opencode"}
    text = "opencode/fixture-free\n" + json.dumps(model) + "\nopencode/paid\n" + json.dumps({**model, "id": "paid", "cost": {"input": 1, "output": 0}})
    assert [m["id"] for m in h._parse_models(text)] == [MODEL]


@pytest.mark.asyncio
async def test_completion_stream_and_sampling_reset(monkeypatch):
    adapter, calls, streams = install(monkeypatch)
    ctx = ModuleExecutionContext(model_id=MODEL, timeout=5)
    result = await adapter.chat_completions(request(max_tokens=32), ctx)
    assert result.choices[0].message.content == "OK"
    assert result.choices[0].message.reasoning_content == "Think"
    assert result.usage.total_tokens == 16
    assert streams[0].closed
    chunks = [x async for x in adapter.stream_chat(request(stream=True), ctx)]
    assert chunks[-1] == "data: [DONE]\n\n" and streams[-1].closed
    limits = [b["provider"]["opencode"]["models"][MODEL]["limit"]["output"] for method, path, b in calls if path == "/config"]
    assert limits == [32, 4096]
    assert sum(path.endswith("/abort") for _, path, _ in calls) == 2
    assert sum(method == "DELETE" for method, _, _ in calls) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("events", [[], wire()[:-2], [("session.error", {"sessionID": "ses_fixture", "error": {"name": "APIError", "data": {"statusCode": 429, "message": "limited"}}})]])
async def test_failed_or_cut_stream_never_returns_success(monkeypatch, events):
    adapter, calls, streams = install(monkeypatch, events)
    with pytest.raises(RouterException):
        await adapter.chat_completions(request(), ModuleExecutionContext(model_id=MODEL, timeout=5))
    assert streams[0].closed
    assert any(method == "DELETE" and path == "/session/ses_fixture" for method, path, _ in calls)


@pytest.mark.asyncio
async def test_aclose_aborts_only_current_session(monkeypatch):
    adapter, calls, streams = install(monkeypatch)
    source = adapter.stream_chat(request(stream=True), ModuleExecutionContext(model_id=MODEL, timeout=5))
    await anext(source)
    await source.aclose()
    assert streams[0].closed
    assert ("POST", "/session/ses_fixture/abort", None) in calls
    assert ("DELETE", "/session/ses_fixture", None) in calls


def test_prompt_preserves_history_and_refuses_invalid_options_or_remote_files():
    adapter = h.LinglingAdapter()
    req = ChatCompletionRequest(model=MODEL, messages=[{"role": "system", "content": "literal system"},
        {"role": "user", "content": "first"}, {"role": "assistant", "content": "answer"}, {"role": "user", "content": "next"}])
    prompt = adapter._prompt(req)
    assert prompt["system"].startswith("literal system\n\n") and "chat-only" in prompt["system"]
    assert '"content": "answer"' in prompt["parts"][0]["text"]
    assert prompt["parts"][-1] == {"type": "text", "text": "next"}
    assert prompt["agent"] == "build" and "tools" not in prompt
    for req in (request(tools=[{"type": "function", "function": {"name": "invalid/name"}}]), request(seed=0),
                ChatCompletionRequest(model=MODEL, messages=[{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "file:///etc/passwd"}}]}])):
        with pytest.raises(RouterException):
            adapter._prompt(req)


@pytest.mark.parametrize("choice", [None, "auto", "required", {"type": "function", "function": {"name": "fixture_lookup"}}])
def test_agent_prompt_accepts_client_tools_without_enabling_native_execution(choice):
    req = request(tools=[{"type": "function", "function": {"name": "fixture_lookup", "description": "Retrieve the client fixture",
        "parameters": {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}}}], tool_choice=choice)
    prompt = h.LinglingAdapter()._prompt(req)
    assert "fixture_lookup" in prompt["system"]
    assert "client" in prompt["system"] and "native" in prompt["system"]
    assert "tools" not in prompt


def test_agent_prompt_continues_after_actual_client_tool_result():
    req = ChatCompletionRequest(model=MODEL, tools=[{"type": "function", "function": {"name": "fixture_lookup", "parameters": {"type": "object"}}}], messages=[
        {"role": "system", "content": "Keep literal caller instructions"},
        {"role": "user", "content": "Retrieve and explain a fixture"},
        {"role": "assistant", "tool_calls": [{"id": "call_actual", "type": "function", "function": {"name": "fixture_lookup", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "call_actual", "content": "42 from the real client"}])
    prompt = h.LinglingAdapter()._prompt(req)
    assert prompt["system"].startswith("Keep literal caller instructions")
    assert '"tool_call_id": "call_actual"' in prompt["parts"][-1]["text"]
    assert "42 from the real client" in prompt["parts"][-1]["text"]


@pytest.mark.asyncio
@pytest.mark.parametrize("choice, tools", [(None, None), ("auto", []), ("none", None),
    ("none", [{"type": "function", "function": {"name": "fixture_lookup"}}])])
async def test_chat_accepts_disabled_tools_and_completed_tool_history(monkeypatch, choice, tools):
    adapter, calls, _ = install(monkeypatch)
    req = ChatCompletionRequest(model=MODEL, tool_choice=choice, tools=tools, messages=[
        {"role": "user", "content": "Look up the fixture"},
        {"role": "assistant", "tool_calls": [{"id": "call_fixture", "type": "function", "function": {"name": "fixture_lookup", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "call_fixture", "content": "Fixture result"},
        {"role": "function", "name": "legacy_lookup", "content": "Legacy result"},
        {"role": "user", "content": "Summarize the supplied results without running anything"}])
    result = await adapter.chat_completions(req, ModuleExecutionContext(model_id=MODEL, timeout=5))
    assert result.choices[0].message.content == "OK"
    prompt = next(body for method, path, body in calls if path.endswith("/prompt_async"))
    assert "tools" not in prompt and "tool_choice" not in prompt
    history = json.loads(prompt["parts"][0]["text"].split("\n", 1)[1])
    assert history[1]["tool_calls"][0]["id"] == "call_fixture"
    assert history[2]["role"] == "tool" and history[2]["tool_call_id"] == "call_fixture"
    assert history[2]["content"] == "Fixture result" and history[3]["role"] == "function"


@pytest.mark.parametrize("choice, tools", [("required", None),
    ({"type": "function", "function": {"name": "shell"}}, None),
    ("auto", [{"type": "function", "function": {"name": "shell", "parameters": {"type": "string"}}}])])
def test_invalid_client_tool_definitions_or_forced_choice_are_rejected(choice, tools):
    with pytest.raises(RouterException, match="client.*tool|tool_choice"):
        h.LinglingAdapter()._prompt(request(tool_choice=choice, tools=tools))


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
async def test_zen_free_direct_uses_lingling_without_changing_permissions_or_paid_models(monkeypatch, stream):
    import time
    import uuid
    from sqlalchemy import select
    from app.core.crypto import encrypt_secret
    from app.core.database import AsyncSessionLocal, engine
    from app.core.circuit_breaker import circuit_breaker
    from app.models.entities import Provider, ProviderCredential, DiscoveredModel, RequestLog
    from app.modules.base import ModuleManifest
    from app.modules.loader import LoadedModule
    from app.routing.engine import RoutingEngine

    assert Path(engine.url.database).name.startswith("myairouter_test_")
    adapter, calls, _ = install(monkeypatch)
    manifest = ModuleManifest.model_validate_json((Path(h.__file__).parent / "manifest.json").read_text())
    manifest.default_models = [manifest.default_models[0].model_copy(update={"id": MODEL})]
    monkeypatch.setattr(ModuleLoader, "_modules", {"lingling": LoadedModule(manifest=manifest)})
    monkeypatch.setattr(ModuleLoader, "_adapters", {"lingling": adapter})
    marker = uuid.uuid4().hex
    async with AsyncSessionLocal() as db:
        zen = Provider(name="Zen " + marker, slug="zen-" + marker, adapter_type="generic_openai", base_url="https://opencode.ai/zen/v1", enabled=True)
        native = Provider(name="Native " + marker, slug="native-" + marker, adapter_type="custom_module", base_url="module://lingling", configuration={"module_id": "lingling"}, enabled=True)
        db.add_all([zen, native])
        await db.flush()
        zen_key = ProviderCredential(provider_id=zen.id, name="HTTP", encrypted_api_key=encrypt_secret("synthetic"), key_fingerprint=marker + "z", masked_key="fixture", enabled=True)
        native_key = ProviderCredential(provider_id=native.id, name="CLI", encrypted_api_key=encrypt_secret("{}"), key_fingerprint=marker + "n", masked_key="fixture", enabled=True)
        original = DiscoveredModel(provider_id=zen.id, provider_model_id=MODEL, canonical_slug=zen.slug + "/" + MODEL, display_name="Free", enabled=True, available=True)
        paid = DiscoveredModel(provider_id=zen.id, provider_model_id="unlisted-free", canonical_slug=zen.slug + "/unlisted-free", display_name="Not in free catalog", enabled=True, available=True)
        routed = DiscoveredModel(provider_id=native.id, provider_model_id=MODEL, canonical_slug=native.slug + "/" + MODEL, display_name="Native free", enabled=True, available=True)
        db.add_all([zen_key, native_key, original, paid, routed])
        await db.commit()
        pairs = await RoutingEngine._get_candidate_credentials_for_model(db, original.canonical_slug)
        assert [(c.id, m.id) for c, m in pairs] == [(native_key.id, routed.id)]
        assert pairs[0][0].provider.id == native.id
        with monkeypatch.context() as missing_module:
            missing_module.setattr(ModuleLoader, "_adapters", {})
            with pytest.raises(RouterException, match="Lingling") as unavailable:
                await RoutingEngine._get_candidate_credentials_for_model(db, original.canonical_slug)
            assert unavailable.value.status_code == 503
        assert (await RoutingEngine._get_candidate_credentials_for_model(db, paid.canonical_slug))[0][0].id == zen_key.id
        for url in ("https://opencode.ai.evil.invalid/zen/v1", "https://opencode.ai@evil.invalid/zen/v1", "http://opencode.ai/zen/v1", "https://opencode.ai/zen/v1?other=1"):
            zen.base_url = url
            await db.flush()
            assert (await RoutingEngine._get_candidate_credentials_for_model(db, original.canonical_slug))[0][0].id == zen_key.id
        zen.base_url = "https://opencode.ai/zen/v1"
        for obj, field in ((zen, "enabled"), (original, "enabled"), (original, "available")):
            setattr(obj, field, False)
            await db.flush()
            assert await RoutingEngine._get_candidate_credentials_for_model(db, original.canonical_slug) == []
            setattr(obj, field, True)
        for obj, field in ((native, "enabled"), (routed, "enabled"), (routed, "available"), (native_key, "enabled")):
            setattr(obj, field, False)
            await db.flush()
            with pytest.raises(RouterException, match="Lingling") as error:
                await RoutingEngine._get_candidate_credentials_for_model(db, original.canonical_slug)
            assert error.value.status_code == 503
            setattr(obj, field, True)
        monkeypatch.setattr(circuit_breaker, "is_available", lambda cid, *args: (cid != native_key.id, None))
        await db.flush()
        with pytest.raises(RouterException, match="Lingling"):
            await RoutingEngine._get_candidate_credentials_for_model(db, original.canonical_slug)
        monkeypatch.setattr(circuit_breaker, "is_available", lambda *args: (True, None))
        await db.commit()
        req = request(stream=stream, tool_choice="auto").model_copy(update={"model": original.canonical_slug})
        with pytest.raises(RouterException) as denied:
            RoutingEngine._check_permissions(SimpleNamespace(permissions=["direct"], allowed_models=["other/model"]), req.model)
        assert denied.value.status_code == 403
        prepared, cache_context = await RoutingEngine.prepare_effective_request(db, req,
            SimpleNamespace(permissions=["direct"], allowed_models=[original.canonical_slug]))
        assert prepared.model == original.canonical_slug and cache_context["provider_name"] == native.name
        assert cache_context["resolved_model_id"] == MODEL and not cache_context["skip_response_cache"]
        request_id = "req_" + marker[:16]
        if stream:
            chunks = [x async for x in RoutingEngine._handle_direct_stream(db, req, req.model, None, request_id, time.perf_counter())]
            assert chunks[-1] == "data: [DONE]\n\n"
        else:
            result = await RoutingEngine._handle_direct_route(db, req, req.model, None, request_id, time.perf_counter())
            assert result.choices[0].message.content == "OK"
        assert req.model == original.canonical_slug and any(path.endswith("/prompt_async") for _, path, _ in calls)
        log = (await db.execute(select(RequestLog).where(RequestLog.request_id == request_id))).scalar_one()
        assert log.requested_model == original.canonical_slug and log.resolved_provider_id == native.id
        assert log.resolved_credential_id == native_key.id and log.mode == "DIRECT"
        native.enabled = False
        await db.commit()


@pytest.mark.asyncio
async def test_profile_crud_stops_owned_runtime(monkeypatch):
    from fastapi import FastAPI
    from unittest.mock import AsyncMock
    from app.api.admin import modules
    from app.api.deps import get_current_admin
    from app.modules.base import ModuleManifest
    from app.modules.loader import LoadedModule
    from app.modules import profile_loader
    from app.core.database import AsyncSessionLocal, engine
    from app.core.crypto import decrypt_secret
    from app.models.entities import ProviderCredential

    assert Path(engine.url.database).name.startswith("myairouter_test_")
    manifest = ModuleManifest.model_validate_json((Path(h.__file__).parent / "manifest.json").read_text())
    adapter = h.LinglingAdapter()
    assert callable(getattr(adapter, "close_profile", None)), "Profile deletion must release its worker"
    released = []
    async def close_profile(cid):
        released.append(cid)
    monkeypatch.setattr(adapter, "close_profile", close_profile)
    monkeypatch.setattr(adapter, "validate_credentials", AsyncMock(return_value=(True, "synthetic", 7)))
    monkeypatch.setattr(adapter, "list_models", AsyncMock(return_value=[
        h.DiscoveredModelData(provider_model_id=m.id, display_name=m.name, context_length=m.context_length,
                             max_output_tokens=m.max_output_tokens, capabilities=m.capabilities)
        for m in manifest.default_models]))
    monkeypatch.setattr(ModuleLoader, "_modules", {"lingling": LoadedModule(manifest=manifest)})
    monkeypatch.setattr(ModuleLoader, "_adapters", {"lingling": adapter})
    monkeypatch.setattr(profile_loader, "sync_profiles_from_disk", AsyncMock(return_value={}))
    async with AsyncSessionLocal() as db:
        await ModuleLoader.sync_with_db(db)  # Listing is read-only, so seed the synthetic catalog explicitly.
    app = FastAPI()
    app.include_router(modules.router, prefix="/api/admin")
    app.dependency_overrides[get_current_admin] = lambda: "synthetic-admin"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture") as client:
        base = "/api/admin/modules/lingling/profiles"
        listed = await client.get("/api/admin/modules")
        assert listed.json()[0]["status"] == "ready" and listed.json()[0]["models_count"] == 7
        fields = {f.key: f.default for f in manifest.fields}
        created = await client.post(base, json={"name": "lingling-fixture", "fields": fields})
        assert created.status_code == 201, created.text
        cid = created.json()["id"]
        target = base + "/" + str(cid)
        assert (await client.get(base)).json()[0]["fields"] == fields
        async with AsyncSessionLocal() as db:
            cred = await db.get(ProviderCredential, cid)
            assert json.loads(decrypt_secret(cred.encrypted_api_key)) == fields and cred.metadata_json == {}
            provider_id = cred.provider_id
        checked = await client.post(target + "/test")
        assert checked.status_code == 200 and checked.json()["success"]
        synced = await client.post(target + "/sync-models")
        assert synced.status_code == 200 and synced.json() == {"success": True, "models_discovered": 7}
        saved = await client.put(target, json={"fields": {"lanes": "2"}})
        assert saved.status_code == 200 and released == [cid]
        assert (await client.get(base)).json()[0]["fields"]["lanes"] == "2"
        deleted = await client.delete(target)
        assert deleted.status_code == 200 and released == [cid, cid]
        assert (await client.get(base)).json() == []
    from app.services.provider_service import ProviderService
    async with AsyncSessionLocal() as db:
        await ProviderService.delete_provider(db, provider_id)


@pytest.mark.asyncio
async def test_owned_process_group_and_reload_cleanup(monkeypatch):
    import sys
    proc = await asyncio.create_subprocess_exec(sys.executable, "-c", "import time; time.sleep(60)", start_new_session=True)
    await h._stop_process(proc)
    assert proc.returncode is not None
    adapter = h.LinglingAdapter()
    stopped = []
    async def stop(proc):
        stopped.append(proc)
    monkeypatch.setattr(h, "_stop_process", stop)
    adapter._workers = {"one": {"credential_id": 1, "process": "fixture-one"}, "two": {"credential_id": 2, "process": "fixture-two"}}
    await adapter.close_profile(1)
    assert stopped == ["fixture-one"] and list(adapter._workers) == ["two"]
    monkeypatch.setattr(ModuleLoader, "_adapters", {"lingling": adapter})
    await ModuleLoader.close_all()
    assert stopped == ["fixture-one", "fixture-two"] and not adapter._workers


@pytest.mark.asyncio
async def test_cancelled_close_and_failed_rescan_keep_ownership(monkeypatch, tmp_path):
    adapter = h.LinglingAdapter()
    entered, resume, stopped = asyncio.Event(), asyncio.Event(), []
    async def stop(proc):
        entered.set()
        await resume.wait()
        stopped.append(proc)
    monkeypatch.setattr(h, "_stop_process", stop)
    adapter._workers = {"one": {"process": "one"}, "two": {"process": "two"}}
    task = asyncio.create_task(adapter.close())
    await entered.wait()
    task.cancel()
    resume.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert stopped == ["one", "two"] and not adapter._workers
    monkeypatch.setattr(ModuleLoader, "_adapters", {"lingling": adapter})
    monkeypatch.setattr(ModuleLoader, "_modules", {})
    monkeypatch.setattr(ModuleLoader, "_retired_adapters", [])
    monkeypatch.setattr("app.modules.loader.MODULES_DIR", tmp_path)
    adapter._workers = {"one": {"process": "retired"}}
    ModuleLoader.scan_modules()
    assert ModuleLoader.get_adapter("lingling") is None
    await ModuleLoader.close_all()
    assert stopped[-1] == "retired" and not adapter._workers


@pytest.mark.asyncio
async def test_transport_fields_and_proxy_only_settings(monkeypatch, tmp_path):
    from app.modules.base import ModuleManifest
    manifest = ModuleManifest.model_validate_json((Path(h.__file__).parent / "manifest.json").read_text())
    fields = {f.key: f for f in manifest.fields}
    assert fields["transport_mode"].default == "tor"
    assert fields["proxy_policy"].default == "balance"
    assert fields["proxy_ids"].type == "textarea" and fields["proxy_ids"].default == []
    source = tmp_path / "lingling"
    source.mkdir()
    for name in ("__init__.py", "lanes.py", "relay.py", "mitm.py"):
        (source / name).touch()
    values = {"project_path": str(tmp_path), "opencode_path": "/bin/true", "transport_mode": "proxy",
              "proxy_ids": [2, 1], "tor_path": "/missing", "lanes": False, "countries": "invalid"}
    real_which = h.shutil.which
    monkeypatch.setattr(h.shutil, "which", lambda name: "/bin/true" if name == "tor" else real_which(name))
    tor_cfg = h.LinglingAdapter()._settings(ModuleExecutionContext(credentials={
        **values, "transport_mode": "tor", "tor_path": "", "lanes": 1, "countries": "us"}))
    assert tor_cfg["proxy_ids"] == [], "Dormant pool must be ignored when switching back to Tor"
    looked_up = []
    monkeypatch.setattr(h.shutil, "which", lambda name: (looked_up.append(name), real_which(name))[1])
    cfg = h.LinglingAdapter()._settings(ModuleExecutionContext(credentials=values))
    assert cfg["lanes"] == 0 and cfg["countries"] == [] and cfg["tor_path"] == ""
    assert cfg["proxy_ids"] == [2, 1] and looked_up == ["/bin/true"]
    for update in ({"transport_mode": []}, {"proxy_policy": "random"}, {"proxy_ids": "[1]"},
                   {"proxy_ids": [True]}, {"proxy_ids": [0]}, {"proxy_ids": ["1"]},
                   {"proxy_ids": [1, 1]}, {"proxy_ids": list(range(1, 18))}):
        with pytest.raises(RouterException):
            h.LinglingAdapter()._settings(ModuleExecutionContext(credentials={**values, **update}))
    with pytest.raises(RouterException, match="Tor|tor"):
        h.LinglingAdapter()._settings(ModuleExecutionContext(credentials={**values, "transport_mode": "tor"}, proxy_url="http://fixture:80"))
    import importlib.util
    from unittest.mock import AsyncMock
    adapter = h.LinglingAdapter()
    monkeypatch.setattr(adapter, "list_models", AsyncMock(return_value=[INFO]))
    with monkeypatch.context() as no_stem:
        no_stem.setattr(importlib.util, "find_spec", lambda name: pytest.fail("Proxy mode must not require stem"))
        success, message, count = await adapter.validate_credentials(ModuleExecutionContext(credentials=values))
    assert success and count == 1 and "proxy transport" in message


@pytest.mark.asyncio
async def test_resolved_pool_is_ordered_private_and_changes_worker_identity(monkeypatch, tmp_path):
    from unittest.mock import AsyncMock
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    source = tmp_path / "source" / "lingling"
    source.mkdir(parents=True)
    for name in ("__init__.py", "lanes.py", "relay.py", "mitm.py"):
        (source / name).touch()
    urls = ["socks5://user:secret@fixture:1080", "http://fixture:8080"]
    resolver = AsyncMock(return_value=urls)
    monkeypatch.setattr(h, "_resolve_proxy_pool", resolver)
    ctx = ModuleExecutionContext(credentials={"project_path": str(source.parent), "opencode_path": "/bin/true",
        "transport_mode": "proxy", "proxy_policy": "priority", "proxy_ids": [2, 1]}, proxy_url=urls[0])
    adapter = h.LinglingAdapter()
    cfg = await adapter._configuration(ctx)
    resolver.assert_awaited_once_with([2, 1])
    assert cfg["proxy_urls"] == urls and cfg["proxy_policy"] == "priority"
    ctx.proxy_url = "https://other-fixture"
    assert (await adapter._configuration(ctx))["proxy_urls"] == [*urls, ctx.proxy_url]
    ctx.proxy_url = urls[0]
    one = adapter._root(ctx, cfg)
    resolver.return_value = [urls[0].replace("secret", "changed"), urls[1]]
    ctx.proxy_url = None
    two = adapter._root(ctx, await adapter._configuration(ctx))
    assert one != two and not list(one.iterdir()) and "proxy_urls" not in ctx.credentials
    resolver.return_value = [urls[0].replace("fixture", "changed-endpoint"), urls[1]]
    assert adapter._root(ctx, await adapter._configuration(ctx)) not in (one, two)
    resolver.side_effect = ValueError("socks5://user:secret@fixture:1080")
    with pytest.raises(RouterException) as failure:
        await adapter._configuration(ctx)
    assert "secret" not in str(failure.value) and "fixture" not in str(failure.value)
    ctx.credentials["proxy_ids"] = []
    with pytest.raises(RouterException, match="empty|select"):
        await adapter._runtime(ctx)
    with pytest.raises(RouterException):
        await adapter._configuration(ctx.model_copy(update={"proxy_url": "file:///secret"}))


def test_transport_readiness_respects_cooldown_owned_tor_and_no_direct():
    class Stop:
        def __init__(self):
            self.stopped = False
        def is_set(self):
            return self.stopped
        def wait(self, seconds):
            self.stopped = True
    external = SimpleNamespace(proxy_url="http://fixture:8080", limited_until=0, healthy=False,
                               asked=False, probe_code=0)
    tor = SimpleNamespace(proxy_url="", process=None, healing=False, limited_until=0)
    probes, launches = [], []
    manager = SimpleNamespace(lanes=[external], start_lanes=lambda lanes: launches.append(lanes),
                              lane_usable=lambda lane: lane.healthy and lane.limited_until <= h.time.time(),
                              lane_bootstrap_pct=lambda lane: pytest.fail("Proxy bootstrap is forbidden"))
    daemon = SimpleNamespace(reachable=lambda lane, **kw: (probes.append(lane), setattr(lane, "healthy", True), 200)[2],
                             check_once=lambda: pytest.fail("No Tor maintenance for proxy readiness"),
                             on_refused=lambda lane, code: setattr(lane, "limited_until", h.time.time() + 60))
    cfg = {"transport_mode": "proxy", "startup_timeout": 30}
    assert h._wait_for_transport(manager, daemon, cfg, Stop()) == "proxy"
    assert probes == [external] and not launches
    external.limited_until = h.time.time() + 60
    with pytest.raises(RuntimeError, match="direct traffic is disabled"):
        h._wait_for_transport(manager, daemon, cfg, Stop())
    assert probes == [external]
    external.limited_until = 0
    reachable = daemon.reachable
    daemon.reachable = lambda lane, **kw: 429
    with pytest.raises(RuntimeError, match="direct traffic is disabled"):
        h._wait_for_transport(manager, daemon, cfg, Stop())
    assert external.limited_until > h.time.time()
    daemon.reachable = reachable
    manager.lanes = [tor]
    manager.lane_bootstrap_pct = lambda lane: 99
    daemon.check_once = lambda: None
    with pytest.raises(RuntimeError):
        h._wait_for_transport(manager, daemon, {**cfg, "transport_mode": "tor"}, Stop())
    assert probes == [external], "Foreign listeners cannot satisfy Tor readiness"
    tor.process = SimpleNamespace(poll=lambda: None)
    with pytest.raises(RuntimeError):
        h._wait_for_transport(manager, daemon, {**cfg, "transport_mode": "tor"}, Stop())
    assert probes == [external], "An owned process still needs complete bootstrap"
    manager.lane_bootstrap_pct = lambda lane: 100
    assert h._wait_for_transport(manager, daemon, {**cfg, "transport_mode": "tor"}, Stop()) == "tor"
    ready = {"url": "http://127.0.0.1:1234", "transport_mode": "proxy", "transport": "proxy", "tor": False}
    assert h._valid_readiness(ready, cfg)
    assert not h._valid_readiness({**ready, "tor": True}, cfg)
    assert not h._valid_readiness({**ready, "transport_mode": "tor"}, cfg)
    assert not h._valid_readiness({**ready, "transport": "direct"}, cfg)


def test_lane_readiness_requires_owned_live_process():
    lane = SimpleNamespace(process=None, socks_port=8007)
    assert not h._owned_lane_running(lane)
    lane.process = SimpleNamespace(poll=lambda: None)
    assert h._owned_lane_running(lane)
    lane.process = SimpleNamespace(poll=lambda: 1)
    assert not h._owned_lane_running(lane)


@pytest.mark.asyncio
async def test_saved_profile_proxy_uses_registry_and_edits_close_workers(monkeypatch, tmp_path):
    from unittest.mock import AsyncMock
    from app.core.database import AsyncSessionLocal
    from app.models.entities import Proxy
    from app.schemas.entities import ProxyUpdate
    from app.services.proxy_service import ProxyService
    source = tmp_path / "source" / "lingling"
    source.mkdir(parents=True)
    for name in ("__init__.py", "lanes.py", "relay.py", "mitm.py"):
        (source / name).touch()
    closed = AsyncMock()
    monkeypatch.setattr(ModuleLoader, "_adapters", {"lingling": SimpleNamespace(close=closed)})
    async with AsyncSessionLocal() as db:
        proxy = Proxy(name="registry-lingling", scheme="http", host="registry.invalid", port=8080, enabled=True)
        db.add(proxy)
        await db.commit()
        configuration = CredentialService.module_runtime_configuration(
            SimpleNamespace(adapter_configuration={"module_id": "lingling"}),
            SimpleNamespace(id=9001, metadata_json={}, proxy_id=proxy.id))
        assert configuration["profile_proxy_id"] == proxy.id
        ctx = ModuleExecutionContext(credentials={"project_path": str(source.parent), "opencode_path": "/bin/true",
            "transport_mode": "proxy"}, extra_config=configuration, proxy_url="http://stale.invalid:80")
        adapter = h.LinglingAdapter()
        cfg = await adapter._configuration(ctx)
        assert cfg["proxy_urls"] == ["http://registry.invalid:8080"]
        await ProxyService.update_proxy(db, proxy.id, ProxyUpdate(name="renamed"))
        closed.assert_not_awaited()
        await ProxyService.update_proxy(db, proxy.id, ProxyUpdate(enabled=False))
        assert closed.await_count == 1
        with pytest.raises(RouterException, match="unavailable"):
            await adapter._configuration(ctx)
        assert await ProxyService.delete_proxy(db, proxy.id)
        assert closed.await_count == 2
        assert await ProxyService.export_pool_fields(db, {"transport_mode": "tor", "proxy_ids": [proxy.id]}) == {
            "transport_mode": "tor", "proxy_refs": []}


def test_all_tor_lanes_retain_owned_process_guard():
    first = SimpleNamespace(proxy_url="", process=SimpleNamespace(poll=lambda: None), limited_until=0, running=lambda: True)
    foreign = SimpleNamespace(proxy_url="", process=None, limited_until=0, running=lambda: True)
    external = SimpleNamespace(proxy_url="http://fixture:80", limited_until=0, running=lambda: True)
    start = []
    manager = SimpleNamespace(lanes=[first, foreign, external], start_lanes=lambda lanes: start.extend(lanes),
        lane_bootstrap_pct=lambda lane: 100, lane_usable=lambda lane: True)
    daemon = SimpleNamespace(reachable=lambda lane, **kwargs: 200)
    stop = SimpleNamespace(is_set=lambda: False)
    assert h._wait_for_transport(manager, daemon, {"startup_timeout": 1}, stop) == "proxy"
    assert first.running() and not foreign.running() and external.running()
    assert start == [first]


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("kind, props, path", [
    ("permission.asked", {"id": "per_fixture", "permission": "bash", "patterns": ["*"], "metadata": {}, "always": []}, "/permission/per_fixture/reply"),
    ("question.asked", {"id": "que_fixture", "questions": [{"header": "Scope", "question": "Which scope?", "options": [{"label": "Chat", "description": "Text only"}]}]}, "/question/que_fixture/reject"),
])
async def test_internal_requests_are_rejected_then_chat_continues(monkeypatch, streaming, kind, props, path):
    # A denied tool turn consumes tokens too; only the following text turn is terminal.
    tool_turn = next(p["info"] for k, p in wire() if k == "message.updated" and p["info"].get("finish"))
    tool_turn = {**tool_turn, "id": "msg_tool", "finish": "tool-calls"}
    events = [("message.updated", {"sessionID": "ses_fixture", "info": tool_turn}),
              (kind, {**props, "sessionID": "ses_other"}),
              (kind, {**props, "sessionID": "ses_fixture"}), *wire()]
    adapter, calls, streams = install(monkeypatch, events)
    ctx = ModuleExecutionContext(model_id=MODEL, timeout=5)
    if streaming:
        chunks = [x async for x in adapter.stream_chat(request(stream=True), ctx)]
        assert chunks[-1] == "data: [DONE]\n\n"
        data = [json.loads(x[6:]) for x in chunks[:-1]]
        assert "".join(x["choices"][0]["delta"].get("content", "") for x in data) == "OK"
        assert data[-1]["usage"]["total_tokens"] == 32
    else:
        result = await adapter.chat_completions(request(), ctx)
        assert result.choices[0].message.content == "OK"
        assert result.usage is not None and result.usage.total_tokens == 32
    session = next(b for method, target, b in calls if target == "/session" and method == "POST")
    assert session["permission"] == [{"permission": "*", "pattern": "*", "action": "ask"}]
    replies = [(method, target, body) for method, target, body in calls if target.startswith(("/permission/", "/question/"))]
    assert len(replies) == 1 and replies[0][:2] == ("POST", path)
    if kind == "permission.asked":
        assert replies[0][2]["reply"] == "reject" and replies[0][2]["message"]
    else:
        assert replies[0][2] is None
    config = next(b for method, target, b in calls if target == "/config")
    assert config["experimental"]["continue_loop_on_deny"] is True
    assert ("POST", "/session/ses_fixture/abort", None) in calls and streams[0].closed


@pytest.mark.asyncio
async def test_internal_request_rejection_is_bounded(monkeypatch):
    events = [("permission.asked", {"sessionID": "ses_fixture", "id": f"per_fixture{i}", "permission": "bash", "patterns": ["*"], "metadata": {}, "always": []}) for i in range(4)]
    adapter, calls, streams = install(monkeypatch, events)
    with pytest.raises(RouterException, match="repeated.*tool"):
        await adapter.chat_completions(request(), ModuleExecutionContext(model_id=MODEL, timeout=5))
    replies = [b for method, path, b in calls if path.startswith("/permission/")]
    assert len(replies) == 3 and all(b["reply"] == "reject" for b in replies)
    assert ("POST", "/session/ses_fixture/abort", None) in calls and streams[0].closed


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_id", [None, 42, "per_../outside", "per_x?approve=always"])
async def test_invalid_internal_request_id_is_not_sent(monkeypatch, bad_id):
    events = [("permission.asked", {"sessionID": "ses_fixture", "id": bad_id, "permission": "bash", "patterns": [], "metadata": {}, "always": []})]
    adapter, calls, streams = install(monkeypatch, events)
    with pytest.raises(RouterException, match="invalid.*request ID"):
        await adapter.chat_completions(request(), ModuleExecutionContext(model_id=MODEL, timeout=5))
    assert not any(path.startswith("/permission/") for _, path, _ in calls)
    assert streams[0].closed


@pytest.mark.asyncio
async def test_tool_only_idle_is_not_a_completed_chat(monkeypatch):
    finished = next(p["info"] for k, p in wire() if k == "message.updated" and p["info"].get("finish"))
    events = [("message.updated", {"sessionID": "ses_fixture", "info": {**finished, "finish": "tool-calls"}}),
              ("session.status", {"sessionID": "ses_fixture", "status": {"type": "idle"}})]
    adapter, _, streams = install(monkeypatch, events)
    with pytest.raises(RouterException, match="completed response"):
        await adapter.chat_completions(request(), ModuleExecutionContext(model_id=MODEL, timeout=5))
    assert streams[0].closed


@pytest.mark.asyncio
async def test_catalog_uses_separate_config_from_running_worker(monkeypatch, tmp_path):
    adapter, envs = h.LinglingAdapter(), []
    monkeypatch.setattr(adapter, "_settings", lambda ctx: {"opencode_path": "/bin/true"})
    monkeypatch.setattr(adapter, "_root", lambda ctx, cfg: tmp_path)
    async def spawn(*args, **kwargs):
        envs.append(kwargs["env"])
        async def communicate():
            return ("opencode/fixture-free\n" + json.dumps({**INFO, "providerID": "opencode"})).encode(), None
        return SimpleNamespace(returncode=0, communicate=communicate)
    async def stop(proc):
        pass
    monkeypatch.setattr(h.asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(h, "_stop_process", stop)
    models = await adapter.list_models(ModuleExecutionContext(timeout=5))
    assert models[0].max_output_tokens == 4096
    assert Path(envs[0]["XDG_CONFIG_HOME"]) == tmp_path / "catalog" / "config"
