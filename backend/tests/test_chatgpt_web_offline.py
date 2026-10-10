"""Offline only: never import app startup, launch a browser, or load real auth."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import socket
import tempfile
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_handler():
    path = ROOT / "modules/chatgpt_web/handler.py"
    assert path.exists(), "ChatGPT Web handler must exist"
    spec = importlib.util.spec_from_file_location("chatgpt_web_offline", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_offline_contract_and_browser_lifecycle():
    def blocked(*args, **kwargs):
        raise AssertionError("Real network forbidden in ChatGPT Web offline tests")

    # Settings isolation precedes every app import and disables the repo dotenv.
    from pydantic_settings import BaseSettings
    original_init = BaseSettings.__init__

    def isolated_init(self, **kwargs):
        return original_init(self, **{**kwargs, "_env_file": None})

    scratch = Path(os.environ.get("TMPDIR", "/home/kiril/.hermes/cache/scratch"))
    with tempfile.TemporaryDirectory(prefix="chatgpt-web-offline-", dir=scratch) as temp:
        env = {"DATABASE_URL": f"sqlite+aiosqlite:///{temp}/synthetic.db",
               "ROUTER_MASTER_KEY": "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=", "JWT_SECRET": "j" * 32,
               "ADMIN_PASSWORD": "synthetic-test-password", "FINGERPRINT_SALT": "s" * 32}
        with patch.dict(os.environ, env), patch.object(BaseSettings, "__init__", isolated_init), \
             patch.object(socket.socket, "connect", blocked), patch.object(socket, "create_connection", blocked):
            from app.core.config import settings  # Bootstrap before later bridge imports.
            assert settings.DATABASE_URL == "sqlite+aiosqlite:///:memory:" or "offline-" in settings.DATABASE_URL or "synthetic.db" in settings.DATABASE_URL
            h = load_handler()
            asyncio.run(check_contract(h))
        assert not Path(temp, "synthetic.db").exists()


def check_browser_script(h, sse):
    """Execute the actual browser JavaScript against a closed, synthetic JS world."""
    import subprocess
    import shutil
    node = shutil.which("node")
    assert node, "Node is required for the offline embedded-JavaScript regression"
    script = r'''
const assert = require('node:assert/strict'), vm = require('node:vm');
const source = SOURCE, sse = SSE;
new vm.Script('(' + source + ')'); // Check unchanged production JS syntax.
const asset = 'https://chatgpt.com/cdn/assets/synthetic.js';
global.location = {origin:'https://chatgpt.com'};
global.performance = {getEntriesByType: () => [{name:asset}]};
global.document = {querySelectorAll: () => []};
let events = [], sessionPayload = {user:{id:'synthetic-user'},accessToken:'synthetic-browser-only'}, sessionType = 'application/json';
global.window = {__myairouterChatGPTEvent:async event => {events.push(event);}};
let variant = 'legacy', expected, calls = 0;
const legacySource = 'function finalize(e=!1,t=`none`){return helper(`finalized`,e,t)}' +
 'Promise.all([proof.getEnforcementToken(t,{forceSync:!0}),turnstile.getEnforcementToken(t)])' +
 'client.safePost(`/sentinel/chat-requirements/prepare`)' +
 'function headers(e,t,n,r,i,a){let o={};return e?.token?o[`OpenAI-Sentinel-Chat-Requirements-Token`]' +
 'export{finalize as F,proof as P,turnstile as T,client as C,headers as H}';
const resolverSource = 'abc:(function(e,t,n){n.d(t,{R:()=>integrity});async function integrity(e){let t=make(),n=extract(await e(t))';
function conversation(options) {
 const body = options.requestBody;
 assert.equal(body.model,expected.model); assert.equal(body.system_hints.includes('reason'),expected.reason);
 assert.equal(body.supports_buffering,true); assert.deepEqual(body.supported_encodings,['v1']);
 assert.equal(body.history_and_training_disabled,true); assert.equal(body.parent_message_id,'client-created-root');
 assert.equal(body.messages[0].content.parts[0],'hello'); calls++;
 assert.equal(events.at(-1).type,'send_activated');
 return new Response(sse,{headers:{'content-type':'text/event-stream'}});
}
global.fetch = async (url, options={}) => {
 if(url === asset) return new Response(variant === 'legacy' ? legacySource : resolverSource);
 if(url === '/api/auth/session') {
   assert.equal(options.redirect,'error'); assert.equal(options.cache,'no-store');
   return new Response(JSON.stringify(sessionPayload),{headers:{'content-type':sessionType}});
 }
 if(variant === 'resolver' && url === '/backend-api/sentinel/chat-requirements/prepare') {
   assert.equal(options.headers.get('Authorization'),'Bearer synthetic-browser-only');
   assert.deepEqual(JSON.parse(options.body),{p:'synthetic-proof'});
   return new Response(JSON.stringify({prepared:true}));
 }
 if(variant === 'resolver' && url === '/backend-api/f/conversation') {
   return conversation({requestBody:JSON.parse(options.body)});
 }
 throw new Error('Real fetch blocked: ' + url);
};
const fakeImport = async url => {
 assert.equal(url,asset);
 if(variant === 'resolver') return {__webpack_modules__:{abc:(_m,exports,requireShim) => {
   assert.equal(typeof requireShim('TI').a(),'string');
   requireShim.d(exports,{R:()=>async prepare=>{assert.deepEqual(await prepare('synthetic-proof'),{prepared:true});return {headers:{synthetic:'integrity'}};}});
 }}};
 return {F:async (cache,surface)=>{assert.equal(cache,false);assert.equal(surface,'none');return {token:'synthetic'};},
   P:{getEnforcementToken:async (_r,opts)=>{assert.deepEqual(opts,{forceSync:true});return 'synthetic-proof';}},
   T:{getEnforcementToken:async ()=> 'synthetic-turnstile'},
   C:{safePost:async (path,options)=>{assert.equal(path,'/f/conversation');return conversation(options);}},
   H:(_r,t,p)=>{assert.equal(t,'synthetic-turnstile');assert.equal(p,'synthetic-proof');return {};}};
};
// Replace only module loading with a fake; no real module import can run.
const turn = eval('(' + source.replaceAll('await import(', 'await fakeImport(') + ')');
(async () => {
 for(variant of ['legacy','resolver']) {
   for(const [selection,model,reason] of [
     [{kind:'picker',modelLabel:'GPT-5.6 Sol',effortIndex:0},'gpt-5-6',false],
     [{kind:'picker',modelLabel:'GPT-5.5',effortIndex:3},'gpt-5-5',true],
     [{kind:'picker',modelLabel:'GPT-5.6 Sol',effortIndex:4},'gpt-5-6-pro',false],
     [{kind:'free',thinkEnabled:true},'auto',true]]) {
       expected = {model,reason};
       events = [];
       assert.equal((await turn({prompt:'hello',selection})).finished,true);
       assert.deepEqual(events.slice(0,2).map(e=>e.type),['send_activated','accepted']);
       assert.equal(events.filter(e=>e.type==='chunk').map(e=>e.text).join(''),sse);
       assert.equal(window.__myairouterChatGPTAbort,undefined);
   }
 }
 assert.equal(calls,8);
 for(variant of ['legacy','resolver']) {
   for(sessionPayload of [{}, {user:{}}, {user:{id:'fake'},error:'expired'},
       {user:{id:'fake'},expires:'invalid'}, {user:{id:'fake'},expires:'2000-01-01T00:00:00Z'}]) {
     events=[]; assert.equal((await turn({prompt:'hello',selection:{kind:'free'}})).status,401);
     assert.equal(events.length,0); assert.equal(calls,8);
   }
   sessionType='text/html'; events=[];
   await assert.rejects(()=>turn({prompt:'hello',selection:{kind:'free'}}),/invalid session/);
   assert.equal(events.length,0); assert.equal(calls,8); sessionType='application/json';
 }
 console.log('Embedded JS: 8 synthetic legacy/resolver turns and auth/send guards passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
'''
    script = script.replace("SOURCE", json.dumps(h.BROWSER_TURN)).replace("SSE", json.dumps(sse))
    result = subprocess.run([node, "-"], input=script, text=True, capture_output=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "8 synthetic" in result.stdout
    print(result.stdout.strip())


async def check_contract(h):
    request = h.ChatCompletionRequest(model="gpt-5-6", messages=[{"role": "user", "content": "hello"}])
    assert h.prepare_request(request, request.model) == ("hello", {"kind": "picker", "modelLabel": "GPT-5.6 Sol", "effortIndex": 0})
    for effort, index in [("none", 0), ("low", 0), ("medium", 1), ("high", 2), ("max", 3), ("xhigh", 3)]:
        r = request.model_copy(update={"reasoning_effort": effort})
        assert h.prepare_request(r, "gpt-5.5-thinking")[1]["effortIndex"] == index
    assert h.prepare_request(request, "gpt-5-6-pro")[1]["effortIndex"] == 4
    assert h.prepare_request(request, "gpt-5.6-luna-free-thinking")[1] == {"kind": "free", "thinkEnabled": True}
    history = request.model_copy(update={"messages": [h.ChatMessage(role="system", content="Be brief"), h.ChatMessage(role="user", content="Hi")]})
    assert h.prepare_request(history, request.model)[0] == "System:\nBe brief\n\nUser:\nHi"
    for changed in [{"tools": [{"type": "function"}]}, {"temperature": 0.7}, {"n": 2},
                    {"messages": [h.ChatMessage(role="user", content=[{"type": "image_url", "image_url": "https://example.test/a.png"}])]}]:
        with pytest.raises(h.RouterException):
            h.prepare_request(request.model_copy(update=changed), request.model)
    with pytest.raises(h.RouterException):
        h.prepare_request(request, "unknown")

    cookie = {"name": "__Host-synthetic", "value": "fake", "domain": ".chatgpt.com", "path": "/wrong",
              "expires": -1, "httpOnly": True, "secure": False, "sameSite": "Lax"}
    state = {"cookies": [cookie], "origins": []}
    normalized = h.read_storage_state({"storage_state": json.dumps(state)})
    assert normalized["cookies"][0]["domain"] == "chatgpt.com"
    assert normalized["cookies"][0]["path"] == "/" and normalized["cookies"][0]["secure"] is True
    assert cookie["path"] == "/wrong"
    assert h.read_storage_state({"cookie": "__Secure-next-auth.session-token=fake=="})["cookies"][0]["value"] == "fake=="
    with pytest.raises(h.RouterException):
        h.read_storage_state({"storage_state": {"cookies": [{**cookie, "domain": ".evil.test"}], "origins": []}})
    with pytest.raises(h.RouterException):
        h.read_storage_state({"storage_state": "/home/someone/auth.json"})
    assert h.playwright_proxy("http://user:p%40ss@localhost:8080") == {"server": "http://localhost:8080", "username": "user", "password": "p@ss"}
    with pytest.raises(h.RouterException):
        h.playwright_proxy("socks5://user:pass@localhost:1080")

    doc = {"message": {"author": {"role": "assistant"}, "content": {"content_type": "text", "parts": ["answer"]},
                       "status": "finished_successfully", "end_turn": True}}
    def event(name, value):
        return f"event: {name}\ndata: {json.dumps(value)}\n\n"
    sse = event("delta_encoding", "v1") + event("delta", {"p": "", "o": "add", "v": doc}) + "data: [DONE]\n\n"
    assert h.parse_response(sse) == "answer"
    check_browser_script(h, sse)
    delta = event("delta_encoding", "v1") + event("delta", {"p": "", "o": "add", "v": {**doc, "message": {**doc["message"], "content": {"content_type": "text", "parts": ["a"]}, "status": "in_progress", "end_turn": False}}})
    delta += event("delta", {"p": "/message/content/parts/0", "o": "append", "v": "b"}) + event("delta", {"v": "c"})
    delta += event("delta", {"p": "", "o": "patch", "v": [{"p": "/message/status", "o": "replace", "v": "finished_successfully"}, {"p": "/message/end_turn", "o": "replace", "v": True}]})
    assert h.parse_response(delta) == "abc"
    assert h.parse_response(event("message", doc)) == "answer"
    for bad in ["data: [DONE]\n\n", event("delta", {"p": "/__proto__", "o": "add", "v": {}}),
                event("delta_encoding", "v2"), event("message", {"message": {**doc["message"], "end_turn": False}})]:
        with pytest.raises(h.RouterException):
            h.parse_response(bad)

    class Resource:
        def __init__(self):
            self.closed = False
        async def close(self):
            try:
                if getattr(self, "blocked", False):
                    entered.set()
                    await asyncio.Future()
            finally:
                self.closed = True

    class Page:
        main_frame = object()
        async def expose_binding(self, name, callback):
            assert name == '__myairouterChatGPTEvent'
            async def invoke(*args):
                task = asyncio.create_task(callback(*args))
                binding_tasks.append(task)
                return await asyncio.shield(task)  # Mirrors Playwright's independent binding tasks.
            self.callback = invoke
        async def goto(self, url, **kwargs):
            assert url == h.PAGE_URL
        @property
        def url(self):
            return "https://chatgpt.com/"
        async def evaluate(self, script, arg=None):
            assert script == h.BROWSER_TURN
            assert arg["prompt"] == "hello"
            source = {'page':self,'frame':self.main_frame}
            if mode[0] == 'early':
                return {'status':401}
            await self.callback(source, {'type':'send_activated'})
            if mode[0] == "wait":
                entered.set()
                await asyncio.Future()
            if mode[0] == "error":
                return {"status": 429}
            source = {'page':self,'frame':self.main_frame}
            await self.callback(source, {'type':'accepted'})
            if mode[0] in ('live','partial_failure','flood'):
                partial = {'message': {**doc['message'], 'id':'owned-stream', 'status':'in_progress', 'end_turn':False}}
                if mode[0] == 'flood':
                    for i in range(100):
                        partial['message']['content'] = {'content_type':'text','parts':['a'*(i+1)]}
                        await self.callback(source, {'type':'chunk','text':event('message',partial)})
                        if i == 16:
                            flood_ready.set()
                else:
                    await self.callback(source, {'type':'chunk','text':event('message',partial)})
                    entered.set()
                    await release.wait()
                    if mode[0] == 'partial_failure':
                        return {'finished':True}
                    partial['message'].update(status='finished_successfully',end_turn=True)
                    await self.callback(source, {'type':'chunk','text':event('message',partial)})
            else:
                await self.callback(source, {'type':'chunk','text':sse})
            return {'finished':True}

    class Context(Resource):
        async def new_page(self):
            return Page()

    class Browser(Resource):
        async def new_context(self, **kwargs):
            assert kwargs["storage_state"] == normalized
            return context

    class Chromium:
        async def launch(self, **kwargs):
            assert kwargs["headless"] is False
            return browser

    class Manager(Resource):
        chromium = Chromium()
        async def start(self):
            return self
        async def stop(self):
            self.closed = True

    adapter = h.ChatGPTWebAdapter()
    ctx = h.ModuleExecutionContext(credentials={"storage_state": state}, model_id=request.model, timeout=1)
    ok, message, count = await adapter.validate_credentials(ctx)
    assert ok and "not checked" in message and count == 8
    models = await adapter.list_models(ctx)
    assert len(models) == 8 and all(m.capabilities["vision"] is False for m in models)
    from app.modules.base import ModuleManifest
    manifest = ModuleManifest.model_validate_json(Path(h.__file__).with_name("manifest.json").read_text())
    assert all(field.type == "password" for field in manifest.fields if field.key in ("cookie", "storage_state"))
    mode, entered, binding_tasks = ["ok"], asyncio.Event(), []
    manager, browser, context = Manager(), Browser(), Context()
    with patch.object(h, "_playwright", side_effect=lambda: manager):
        result = await adapter.chat_completions(request, ctx)
        assert result.choices[0].message.content == "answer" and result.usage is None
        assert manager.closed and browser.closed and context.closed
        manager, browser, context = Manager(), Browser(), Context()
        mode[0] = "error"
        with pytest.raises(h.RouterException) as error:
            await adapter.chat_completions(request, ctx)
        assert error.value.category == h.ErrorCategory.RATE_LIMIT and error.value.replay_safe is False
        assert manager.closed and browser.closed and context.closed
        manager, browser, context = Manager(), Browser(), Context()
        mode[0] = "wait"
        task = asyncio.create_task(adapter.chat_completions(request, ctx))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert manager.closed and browser.closed and context.closed
        manager, browser, context = Manager(), Browser(), Context()
        with pytest.raises(h.RouterException) as error:
            await adapter.chat_completions(request, ctx.model_copy(update={"timeout": 0.01}))
        assert error.value.category == h.ErrorCategory.TIMEOUT and error.value.replay_safe is False
        assert manager.closed and browser.closed and context.closed
        mode[0] = 'early'
        manager, browser, context = Manager(), Browser(), Context()
        fresh = h.ChatCompletionRequest(model=request.model, messages=request.messages)
        with pytest.raises(h.RouterException) as error:
            await adapter.chat_completions(fresh, ctx)
        assert error.value.category == h.ErrorCategory.AUTH_ERROR
        assert not getattr(fresh, '_upstream_submission_started', False)
        assert manager.closed and browser.closed and context.closed

        # First disconnect can arrive while an ordinary auth error is tearing down.
        mode[0], entered = 'early', asyncio.Event()
        manager, browser, context = Manager(), Browser(), Context()
        context.blocked = True
        fresh = h.ChatCompletionRequest(model=request.model, messages=request.messages)
        source = adapter.stream_chat(fresh, ctx)
        consumer = asyncio.create_task(anext(source))
        await asyncio.wait_for(entered.wait(), 1)
        consumer.cancel()
        with pytest.raises(asyncio.CancelledError):
            await consumer
        await source.aclose()
        assert manager.closed and browser.closed and context.closed

        for scenario in ('live','partial_failure','flood'):
            mode[0] = scenario
            entered, release, flood_ready = asyncio.Event(), asyncio.Event(), asyncio.Event()
            manager, browser, context = Manager(), Browser(), Context()
            fresh = h.ChatCompletionRequest(model=request.model, messages=request.messages)
            source = adapter.stream_chat(fresh, ctx)
            frames = [await anext(source)]
            assert 'assistant' in frames[0] and fresh._upstream_submission_started
            assert '_upstream_submission_started' not in fresh.model_dump()
            assert not manager.closed  # First chunk is available before browser completion.
            if scenario == 'flood':
                await asyncio.wait_for(flood_ready.wait(), 1)
                await asyncio.wait_for(source.aclose(), 1)  # Full queue must not hang cleanup.
            else:
                frames.append(await anext(source))
                assert json.loads(frames[-1][6:])['choices'][0]['delta']['content'] == 'answer'
                await entered.wait()
                assert not release.is_set()
                release.set()
                if scenario == 'partial_failure':
                    with pytest.raises(h.RouterException) as error:
                        async for frame in source:
                            frames.append(frame)
                    assert error.value.replay_safe is False
                    assert all('[DONE]' not in f and '"finish_reason": "stop"' not in f for f in frames)
                else:
                    frames.extend([frame async for frame in source])
                    accumulator = h.ChatStreamAccumulator()
                    for frame in frames:
                        accumulator.feed(frame)
                    assert accumulator.response(request.model, require_complete=True).choices[0].message.content == 'answer'
            assert manager.closed and browser.closed and context.closed
            assert all(task.done() for task in binding_tasks)


def test_loader_bridge_and_routed_effort_without_profiles():
    from app.modules import loader
    from app.adapters.module_adapter import CustomModuleAdapter
    from app.core.config import settings
    from app.routing.engine import RoutingEngine
    from playwright.async_api import Page as RealPage, BrowserType
    from curl_cffi.requests import AsyncSession
    from contextlib import asynccontextmanager
    assert isinstance(RealPage.url, property)
    assert settings.DATABASE_URL == "sqlite+aiosqlite:///:memory:" or "offline-" in settings.DATABASE_URL or "synthetic.db" in settings.DATABASE_URL
    def blocked(*args, **kwargs):
        raise AssertionError("Network/browser prohibited during bridge regression")
    with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR"), prefix="web-loader-offline-") as temp:
        folder = Path(temp)
        for name in ("chatgpt_web", "claude_web"):
            (folder / name).symlink_to(ROOT / "modules" / name, target_is_directory=True)
        with patch.object(socket.socket, "connect", blocked), patch.object(AsyncSession, "request", blocked), \
             patch.object(BrowserType, "launch", blocked), patch.object(loader, "MODULES_DIR", folder), \
             patch.object(loader.ModuleLoader, "_modules", {}), patch.object(loader.ModuleLoader, "_adapters", {}), \
             patch.object(loader.ModuleLoader, "_retired_adapters", []):
            modules = loader.ModuleLoader.scan_modules()
            assert set(modules) == {"chatgpt_web", "claude_web"}
            assert all(m.status == "ready" and m.profiles_count == 0 for m in modules.values())
            async def run():
                import httpx
                from app.schemas.chat import ChatCompletionRequest
                from app.modules.base import ChatStreamAccumulator
                bridge, seen = CustomModuleAdapter(), []
                async def turn(prompt, selection, state, ctx, *, on_text, on_send):
                    seen.append(ctx)
                    assert selection["effortIndex"] == 2
                    on_send()
                    await on_text('synthetic answer')
                    return 'synthetic answer'
                @asynccontextmanager
                async def direct(ctx, method, url, headers, payload=None):
                    seen.append(ctx)
                    if method == "GET":
                        response = httpx.Response(200, json=[{"uuid":"11111111-1111-4111-8111-111111111111"}])
                    else:
                        assert payload["thinking_mode"] == "extended" and payload["effort"] == "high"
                        events = [{"type":"message_start","message":{"role":"assistant"}},
                            {"type":"content_block_start","index":0,"content_block":{"type":"text","text":"synthetic answer"}},
                            {"type":"content_block_stop","index":0}, {"type":"message_delta","delta":{"stop_reason":"end_turn"}},
                            {"type":"message_stop"}]
                        response = httpx.Response(200, headers={"content-type":"text/event-stream"},
                            content="".join("data: "+json.dumps(e)+"\n\n" for e in events).encode())
                    try:
                        yield response
                    finally:
                        await response.aclose()
                with patch.object(loader.ModuleLoader.get_adapter("chatgpt_web"), "_turn", turn), \
                     patch.object(loader.ModuleLoader.get_adapter("claude_web"), "_direct", direct):
                    for mid, model in (("chatgpt_web","gpt-5-6-thinking"),("claude_web","claude-sonnet-4-6")):
                        config = {"module_id":mid,"credential_id":123,"credential_metadata":{"marker":True}}
                        secret = json.dumps({"cookie":"__Secure-next-auth.session-token=synthetic" if mid == "chatgpt_web" else "synthetic"})
                        models = await bridge.list_models("module://"+mid, secret, {}, config)
                        assert [m.provider_model_id for m in models] == [m.id for m in modules[mid].manifest.default_models]
                        request = RoutingEngine._apply_thinking_effort(ChatCompletionRequest(model="route/synthetic", messages=[{"role":"user","content":"Hi"}]), "high")
                        args = ("module://"+mid, secret, model, request, {}, config)
                        result = await bridge.chat_completions(*args, proxy_url="http://127.0.0.1:9999", timeout=1)
                        assert result.choices[0].message.content == "synthetic answer"
                        accumulator = ChatStreamAccumulator()
                        async for frame in bridge.stream_chat(*args, proxy_url="http://127.0.0.1:9999", timeout=1):
                            accumulator.feed(frame)
                        assert accumulator.response(model, require_complete=True).choices[0].message.content == "synthetic answer"
                        assert request.thinking == {"type":"enabled","budget_tokens":16384}
                assert seen and all(c.proxy_url == "http://127.0.0.1:9999" and c.extra_config["credential_id"] == 123
                                    and c.credentials["marker"] is True for c in seen)
                await loader.ModuleLoader.close_all()
            asyncio.run(run())


def test_incremental_decoder_and_no_false_completion():
    h = load_handler()
    decoder = h.ChatGPTResponseDecoder()
    document = {"message": {"id": "owned-answer", "author": {"role": "assistant"},
        "content": {"content_type": "text", "parts": ["Привет"]},
        "status": "in_progress", "end_turn": False}}
    frame = "data: " + json.dumps(document, ensure_ascii=False) + "\r\n\r\n"
    deltas = []
    for char in frame:
        deltas.extend(decoder.feed(char))
    assert deltas == ["Привет"] and not decoder.complete
    with pytest.raises(h.RouterException):
        decoder.finish()  # Partial text must not masquerade as success.
    document["message"]["content"]["parts"] = ["Привет мир"]
    document["message"].update(status="finished_successfully", end_turn=True)
    assert decoder.feed("data: " + json.dumps(document) + "\n\n") == [" мир"]
    assert decoder.finish() == "Привет мир" and decoder.complete
    with pytest.raises(h.RouterException):
        decoder.feed('data: {"error":{"message":"provider failed"}}\n\n')
    for mutation in ({"id": "different-answer"}, {"content": {"content_type": "text", "parts": ["rewrite"]}}):
        other = h.ChatGPTResponseDecoder()
        other.feed(frame)
        changed = {"message": {**document["message"], **mutation}}
        with pytest.raises(h.RouterException):
            other.feed("data: " + json.dumps(changed) + "\n\n")
    assert not other.complete
    hidden = h.ChatGPTResponseDecoder()
    analysis = {"message": {**document["message"], "channel": "analysis"}}
    assert hidden.feed("data: " + json.dumps(analysis) + "\n\n") == []
    assert hidden.feed("data: " + json.dumps(document) + "\n\n") == ["Привет мир"]
    assert hidden.finish() == "Привет мир"
    with pytest.raises(h.RouterException):
        hidden.feed('event: delta\ndata: {"p":"","o":"replace","v":null}\n\n')
    assert not hidden.complete
    for mutation in ({"channel": "analysis"}, {"author": {"role": "user"}},
                     {"content": {"content_type": "code", "text": "unsupported"}}):
        other = h.ChatGPTResponseDecoder()
        other.feed("data: " + json.dumps(document) + "\n\n")
        changed = {"message": {**document["message"], **mutation,
                              "status": "in_progress", "end_turn": False}}
        with pytest.raises(h.RouterException):
            other.feed("data: " + json.dumps(changed) + "\n\n")
        assert not other.complete
        with pytest.raises(h.RouterException):
            other.finish()
