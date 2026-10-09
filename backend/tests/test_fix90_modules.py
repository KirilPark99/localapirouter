"""Offline correctness regressions for approved points 15–23 / 60–68."""
import asyncio
import base64
import importlib
import inspect
import json
import struct
import threading
from urllib.parse import parse_qs

import httpx
import pytest
from app.modules.base import ModuleExecutionContext, ChatStreamAccumulator, collect_chat_completion
from app.modules.responses import responses_to_chat
from app.adapters.module_adapter import CustomModuleAdapter
from app.schemas.chat import ChatCompletionRequest, ChatMessage
from app.core.errors import RouterException


def adapter(mid):
    mod = importlib.import_module('modules.' + mid + '.handler')
    cls = next(v for v in vars(mod).values() if inspect.isclass(v) and v.__module__ == mod.__name__ and hasattr(v, 'stream_chat'))
    a = cls()
    if hasattr(a, '_find_local_auth_file'):
        a._find_local_auth_file = lambda: pytest.fail('Local discovery forbidden')
    return a


def ctx(**kw):
    return ModuleExecutionContext(credentials={'auto_detect_local': False, 'access_token': 'fixture-access', 'api_key': 'fixture-key', 'user_token': 'fixture-user', 'cookie': 'arena-auth-prod-v1=fixture', 'token_v2': 'fixture'}, model_id='synthetic', timeout=151, **kw)


def req(**kw):
    return ChatCompletionRequest(model='synthetic', messages=[ChatMessage(role='user', content='hello')], **kw)


def wire(data):
    return 'data: ' + json.dumps(data) + '\n\n'


def install(a, handler):
    clients = []
    def client(*args, **kwargs):
        c = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        clients.append(c)
        return c
    a.create_http_client = client
    return clients


async def consume(a, r=None, c=None):
    return [x async for x in a.stream_chat(r or req(), c or ctx())]


async def deepseek(a, body, status=200, tracked=None):
    clients = install(a, lambda r: httpx.Response(status, text=body) if tracked is None else httpx.Response(status, stream=tracked))
    async def token(*args): return 'fixture-access'
    async def session(*args): return 'fixture-session'
    prompts, deleted = [], []
    async def completion(client, access, sid, model, thinking, search, prompt):
        prompts.append(prompt)
        # Echo only the bound nonce supplied by the real handler prompt.
        import re
        nonce = re.search(r'"_nonce": "([a-f0-9]+)"', prompt)
        if body == 'TOOLS':
            value = '<tool>' + json.dumps({'name': 'lookup', 'arguments': {'x': 1}, '_nonce': nonce.group(1)}) + '</tool>'
            return httpx.Response(200, text=wire({'v': value}) + 'data: [DONE]\n\n')
        return await client.send(client.build_request('POST', 'https://fixture.invalid/completion'), stream=True)
    async def delete(*args): deleted.append(True)
    a._acquire_access_token, a._create_session = token, session
    a._send_completion_request, a._delete_session = completion, delete
    return clients, prompts, deleted


async def zai(monkeypatch, a, body):
    mod = importlib.import_module(a.__module__)
    async def fe(client): return 'fixture-version'
    monkeypatch.setattr(mod, 'get_zai_fe_version', fe)
    records = []
    def handler(r):
        payload = json.loads(r.content)
        records.append(payload)
        return httpx.Response(200, json={'id': 'fixture-chat'}) if 'chat' in payload else httpx.Response(200, text=body)
    clients = install(a, handler)
    jwt = 'fixture.' + base64.urlsafe_b64encode(json.dumps({'id': 'fixture-user'}).encode()).decode().rstrip('=') + '.fixture'
    c = ModuleExecutionContext(credentials={'token': jwt}, model_id='glm-5.3')
    return c, records, clients


POINTS = list(range(15, 24)) + list(range(60, 69))


@pytest.mark.asyncio
@pytest.mark.parametrize('point', POINTS)
async def test_point(point, monkeypatch):
    if point == 15:
        event = {'id': 'fixture-id', 'choices': [{'index': 0, 'delta': {'reasoning_content': 'thought', 'tool_calls': [{'index': 0, 'id': 'call_1', 'type': 'function', 'function': {'name': 'lookup', 'arguments': '{}'}}]}, 'finish_reason': 'tool_calls'}], 'usage': {'prompt_tokens': 10, 'completion_tokens': 4, 'total_tokens': 14}}
        for mid in ('cline', 'clinepass'):
            a = adapter(mid)
            clients = install(a, lambda r: httpx.Response(200, text=wire(event) + 'data: [DONE]\n\n'))
            result = await a.chat_completions(req(), ctx())
            assert result.choices[0].message.tool_calls[0].id == 'call_1'
            assert result.choices[0].message.reasoning_content == 'thought'
            assert result.choices[0].finish_reason == 'tool_calls' and result.usage.total_tokens == 14
            assert all(c.is_closed for c in clients)
            install(a, lambda r: httpx.Response(200, text=wire({'error': {'message': 'fixture failure', 'code': 503}}) + 'data: [DONE]\n\n'))
            with pytest.raises(RouterException, match='fixture failure'):
                await a.chat_completions(req(), ctx())
    elif point == 16:
        for mid in ('cline', 'clinepass', 'qoder', 'kimi_web', 'lmarena', 'notion_web'):
            for status in (400, 401, 403, 429, 503):
                a = adapter(mid)
                install(a, lambda r, status=status: httpx.Response(status, json={'error': {'message': 'fixture failure'}}))
                c = ctx()
                if mid == 'notion_web':
                    c = ModuleExecutionContext(credentials={'cookie': 'token_v2=fixture; notion_user_id=fixture-user', 'space_id': 'fixture-space'})
                with pytest.raises(RouterException) as caught:
                    await consume(a, c=c)
                err = CustomModuleAdapter().normalize_error(exception=caught.value)
                assert err.upstream_status == status and err.category.value == {400: 'INVALID_REQUEST', 401: 'AUTH_ERROR', 403: 'AUTH_ERROR', 429: 'RATE_LIMIT', 503: 'UPSTREAM_5XX'}[status]
                assert 'DuckDuckGo' not in str(err) and 'fixture failure' in str(err)
        a = adapter('qoder')
        install(a, lambda r: httpx.Response(200, text=wire({'statusCodeValue': 429, 'body': {'error': 'fixture failure'}})))
        with pytest.raises(RouterException) as caught: await consume(a)
        assert caught.value.upstream_status == 429
        err = CustomModuleAdapter().normalize_error(status_code=403, response_body='generic forbidden')
        assert 'DuckDuckGo' not in str(err)
    elif point == 17:
        a = adapter('notion_web')
        messages = [ChatMessage(role='system', content='KEEP_SYSTEM'), ChatMessage(role='assistant', content='DROP_GREETING'), ChatMessage(role='user', content='hi')]
        transcript = json.dumps(a._build_transcript(messages, '', 'fixture-space', 'fixture-user'))
        assert 'KEEP_SYSTEM' in transcript and 'DROP_GREETING' not in transcript
        records = []
        install(a, lambda r: records.append(json.loads(r.content)) or httpx.Response(200, text=json.dumps({'type': 'markdown-chat', 'value': 'answer'}) + '\n'))
        await a.chat_completions(ChatCompletionRequest(model='notion-ai', messages=messages), ModuleExecutionContext(credentials={'cookie': 'token_v2=fixture; notion_user_id=fixture-user', 'space_id': 'fixture-space'}))
        assert 'KEEP_SYSTEM' in json.dumps(records)
    elif point == 18:
        async def lines(): yield wire({'type': 'response.output_text.delta', 'delta': 'partial'}).strip()
        chunks = []
        with pytest.raises(RouterException):
            async for chunk in responses_to_chat(lines(), 'synthetic', 'id', 1): chunks.append(chunk)
        assert not any('[DONE]' in x or '"finish_reason": "stop"' in x for x in chunks)
        for mid in ('codex_cli', 'grok_builder_cli'):
            a = adapter(mid)
            install(a, lambda r: httpx.Response(200, text=wire({'type': 'response.output_text.delta', 'delta': 'partial'})))
            with pytest.raises(RouterException): await a.chat_completions(req(), ctx())
    elif point == 19:
        a = adapter('zai_web')
        c, records, _ = await zai(monkeypatch, a, wire({'choices': [{'delta': {'content': 'answer'}}]}) + 'data: [DONE]\n\n')
        with pytest.raises(RouterException) as caught:
            await consume(a, req(tools=[{'type': 'function', 'function': {'name': 'lookup'}}]), c)
        assert caught.value.status_code == 422 and not records
        r = req(reasoning={'effort': 'none'})
        r.model = 'glm-5.3'
        await consume(a, r, c)
        assert records[-1]['features']['reasoning_effort'] == 'none' and records[-1]['features']['enable_thinking'] is False
        assert records[0]['chat']['enable_thinking'] is False
        install(a, lambda r: httpx.Response(503))
        assert all(m.capabilities['tools'] is False for m in await a.list_models(ModuleExecutionContext()))
        install(a, lambda r: httpx.Response(200, json={'data': [{'id': 'glm-5.3', 'info': {'meta': {'capabilities': {'mcp': True}}}}]}))
        assert all(m.capabilities['tools'] is False for m in await a.list_models(c))
    elif point == 20:
        a = adapter('deepseek_web')
        with pytest.raises(RouterException): await consume(a, c=ModuleExecutionContext())
        await deepseek(a, json.dumps({'error': {'message': 'fixture failure'}}), status=503)
        with pytest.raises(RouterException) as caught: await consume(a)
        assert caught.value.upstream_status == 503
        await deepseek(a, wire({'error': {'message': 'fixture SSE failure'}}))
        with pytest.raises(RouterException, match='fixture SSE failure'): await consume(a)
        a = adapter('zai_web')
        c, _, _ = await zai(monkeypatch, a, wire({'choices': [{'delta': {'content': 'partial'}}]}) + wire({'data': {'done': True, 'error': {'code': 'FRONTEND_CAPTCHA_REQUIRED', 'detail': 'fixture failure'}}}))
        chunks = []
        with pytest.raises(RouterException):
            async for chunk in a.stream_chat(req(), c): chunks.append(chunk)
        assert not any('[DONE]' in x or '"finish_reason": "stop"' in x for x in chunks)
    elif point == 21:
        a = adapter('deepseek_web')
        clients, prompts, _ = await deepseek(a, 'TOOLS')
        r = req(tools=[{'type': 'function', 'function': {'name': 'lookup', 'parameters': {'type': 'object'}}}])
        chunks = await consume(a, r)
        acc = ChatStreamAccumulator()
        for x in chunks: acc.feed(x)
        streamed = acc.response('synthetic', require_complete=True)
        nonstream = await a.chat_completions(r, ctx())
        assert all('Available tools:' in p and 'lookup' in p for p in prompts)
        for result in (streamed, nonstream):
            assert result.choices[0].finish_reason == 'tool_calls'
            assert result.choices[0].message.tool_calls[0].function.name == 'lookup'
            assert json.loads(result.choices[0].message.tool_calls[0].function.arguments) == {'x': 1}
        assert all(c.is_closed for c in clients)
    elif point == 22:
        mod = importlib.import_module('modules.duckduckgo_web.handler')
        entered, release, exited = threading.Event(), threading.Event(), threading.Event()
        class Response:
            def close(self): release.set()
            def __enter__(self): return self
            def __exit__(self, *args): exited.set()
            def __iter__(self):
                yield b'data: {"message":"answer"}\n'
                entered.set()
                release.wait(2)
                yield b'data: [DONE]\n'
        class Opener:
            def open(self, *args, **kw): return Response()
        monkeypatch.setattr(mod, 'build_opener', lambda *args: Opener())
        a = adapter('duckduckgo_web')
        a._acquire_auth_headers_sync = lambda *args: {'x-vqd-4': 'fixture'}
        gen = a.stream_chat(req(), ctx())
        try:
            started = asyncio.get_running_loop().time()
            await asyncio.wait_for(anext(gen), .5)
            assert asyncio.get_running_loop().time() - started < .2
            await asyncio.to_thread(entered.wait, .5)
            await gen.aclose()
            assert release.is_set()
            assert await asyncio.to_thread(exited.wait, .5)
        finally:
            release.set()
            await gen.aclose()
    elif point == 23:
        from modules.deepseek_web.handler import process_deepseek_sse_data
        _, chunks, _ = process_deepseek_sse_data({'v': 'State FINISHED remains literal'}, '', False)
        assert chunks == [('content', 'State FINISHED remains literal')]
        _, chunks, _ = process_deepseek_sse_data({'p': 'response/status', 'v': 'FINISHED'}, '', False)
        assert not chunks
        a = adapter('deepseek_web')
        await deepseek(a, wire({'v': 'State FINISHED remains literal'}) + 'data: [DONE]\n\n')
        assert (await a.chat_completions(req(), ctx())).choices[0].message.content == 'State FINISHED remains literal'
    elif point == 60:
        for mid in ('kimi_web', 'lmarena', 'zai_web'):
            for terminal in (True, False):
                a = adapter(mid)
                c = ctx()
                if mid == 'kimi_web':
                    from modules.kimi_web.handler import frame_connect_message
                    body = frame_connect_message({'op': 'append', 'mask': 'block.text.content', 'block': {'text': {'content': 'answer'}}})
                    body += struct.pack('>BI', 2, 2) + b'{}' if terminal else b'\x00\x00'
                    install(a, lambda r: httpx.Response(200, content=body))
                elif mid == 'lmarena':
                    body = b'0:"answer"\n' + (b'd:{"finishReason":"length","usage":{"promptTokens":10,"completionTokens":4}}\n' if terminal else b'')
                    install(a, lambda r: httpx.Response(200, content=body))
                else:
                    body = wire({'choices': [{'delta': {'content': 'answer'}}]}) + (wire({'choices': [{'delta': {}, 'finish_reason': 'length'}], 'usage': {'prompt_tokens': 10, 'completion_tokens': 4, 'total_tokens': 14}}) if terminal else '')
                    c, _, _ = await zai(monkeypatch, a, body)
                if terminal:
                    acc = ChatStreamAccumulator()
                    for x in await consume(a, c=c): acc.feed(x)
                    result = acc.response('synthetic', require_complete=True)
                    assert result.choices[0].message.content == 'answer'
                    assert result.choices[0].finish_reason == ('stop' if mid == 'kimi_web' else 'length')
                    if mid != 'kimi_web': assert result.usage.total_tokens == 14
                else:
                    with pytest.raises(RouterException): await consume(a, c=c)
    elif point == 61:
        for mid in ('codex_cli', 'grok_builder_cli'):
            a = adapter(mid)
            records = []
            install(a, lambda r: records.append(json.loads(r.content)) or httpx.Response(200, text=wire({'type': 'response.completed', 'response': {}})))
            await consume(a, req(max_tokens=9, max_completion_tokens=7, reasoning={'effort': 'none'}, prompt_cache_key='fixture-cache'))
            assert records[0]['max_output_tokens'] == 7 and records[0]['reasoning']['effort'] == 'none' and records[0]['prompt_cache_key'] == 'fixture-cache'
            for field, value in [('temperature', .2), ('top_p', .8), ('stop', ['END']), ('seed', 1), ('response_format', {'type': 'json_object'}), ('n', 2), ('presence_penalty', .3), ('logit_bias', {'1': 1})]:
                count = len(records)
                if field in ('temperature', 'top_p'):
                    await consume(a, req(**{field: value}))
                    assert len(records) == count + 1 and field not in records[-1]
                    continue
                with pytest.raises(RouterException) as caught: await consume(a, req(**{field: value}))
                assert caught.value.status_code == 422 and len(records) == count
    elif point == 62:
        closed = []
        async def source():
            try: yield wire({'choices': [{'delta': {'content': 'answer'}, 'finish_reason': 'stop'}]}) + 'data: [DONE]\n\n'
            finally: closed.append(True)
        class A:
            def stream_chat(self, *args): return source()
        bridge = CustomModuleAdapter()
        bridge._resolve_context = lambda *args: (A(), ctx())
        gen = bridge.stream_chat('', '', 'synthetic', req(), {}, {})
        await anext(gen)
        await gen.aclose()
        assert closed
        closed.clear()
        async def broken():
            try:
                yield wire({'error': {'message': 'fixture failure'}})
                yield 'data: [DONE]\n\n'
            finally: closed.append(True)
        with pytest.raises(RouterException): await collect_chat_completion(broken(), 'synthetic')
        assert closed
        closed.clear()
        async def response_lines():
            try:
                yield wire({'type': 'response.completed', 'response': {}}).strip()
                await asyncio.sleep(30)
            finally: closed.append(True)
        for x in [x async for x in responses_to_chat(response_lines(), 'synthetic', 'id', 1)]: pass
        assert closed
    elif point == 63:
        class Tracked(httpx.AsyncByteStream):
            closed = False
            async def __aiter__(self):
                yield wire({'v': 'answer'}).encode()
                await asyncio.sleep(30)
            async def aclose(self): self.closed = True
        a = adapter('deepseek_web')
        stream = Tracked()
        clients, _, deleted = await deepseek(a, '', tracked=stream)
        gen = a.stream_chat(req(), ctx())
        await anext(gen)
        await gen.aclose()
        assert stream.closed and deleted and all(c.is_closed for c in clients)
    elif point == 64:
        for mid in ('codex_cli', 'grok_builder_cli'):
            a = adapter(mid)
            mod = importlib.import_module(a.__module__)
            now = [1000.0]
            monkeypatch.setattr(mod.time, 'time', lambda: now[0])
            calls, saved = [], []
            async def persist(fields): saved.append(dict(fields))
            c = ModuleExecutionContext(credentials={'auto_detect_local': False, 'refresh_token': 'fixture-first', 'access_token': 'fixture-old'}, extra_config={'credential_id': 'fixture-profile', 'persist_credentials': persist})
            async def handler(r):
                calls.append(parse_qs(r.content.decode()))
                await asyncio.sleep(.01)
                return httpx.Response(200, json={'access_token': 'fixture-new', 'refresh_token': 'fixture-rotated', 'expires_in': 120})
            install(a, handler)
            await asyncio.gather(a._get_valid_access_token(c), a._get_valid_access_token(c))
            assert len(calls) == 1 and len(saved) == 1, 'refresh must be singleflight and persisted'
            now[0] = 1061
            await a._get_valid_access_token(c)
            assert calls[-1]['refresh_token'][0] == saved[0]['refresh_token'], 'refresh must use rotation'
            now[0] = 1122
            install(a, lambda r: httpx.Response(400, json={'error': 'invalid_grant'}))
            with pytest.raises(RouterException): await a._get_valid_access_token(c)
    elif point == 65:
        from modules.deepseek_web.handler import parse_tool_calls_from_text
        text = '<tool>{"name":"","arguments":[1],"_nonce":"fixture"}</tool>'
        clean, calls = parse_tool_calls_from_text(text, 'fixture')
        assert not calls and clean == text
        for name, args in [('', {}), ('lookup', [1]), ('unknown', {})]:
            text = '<tool>' + json.dumps({'name': name, 'arguments': args, '_nonce': 'fixture'}) + '</tool>'
            clean, calls = parse_tool_calls_from_text(text, 'fixture', {'lookup'})
            assert not calls and clean == text
        text = '<tool>' + json.dumps({'name': 'lookup', 'arguments': {}, '_nonce': 'fixture'}) + '</tool>'
        clean, calls = parse_tool_calls_from_text(text, 'fixture', {'lookup'})
        assert clean == '' and calls[0].function.name == 'lookup'
    elif point == 66:
        from modules.deepseek_web.handler import build_prompt_from_messages
        messages = [ChatMessage(role='user', content='lookup'), ChatMessage(role='assistant', tool_calls=[{'id': 'call_old', 'function': {'name': 'lookup', 'arguments': '{"x":1}'}}]), ChatMessage(role='tool', tool_call_id='call_old', content='result')]
        prompt = build_prompt_from_messages(messages)
        calls = json.loads(prompt.split('Assistant: ', 1)[1].split('\n\n', 1)[0])
        assert prompt.count('call_old') == 2 and calls[0]['function']['arguments'] == '{"x":1}'
        a = adapter('deepseek_web')
        _, prompts, _ = await deepseek(a, wire({'v': 'answer'}) + 'data: [DONE]\n\n')
        await a.chat_completions(ChatCompletionRequest(model='synthetic', messages=messages), ctx())
        calls = json.loads(prompts[0].split('Assistant: ', 1)[1].split('\n\n', 1)[0])
        assert prompts[0].count('call_old') == 2 and calls[0]['function']['arguments'] == '{"x":1}'
    elif point == 67:
        from app.services.search.duckduckgo_lite import parse_duckduckgo_lite
        html = '<tr><td><a class="result-link" href="https://example.com/a">A</a></td></tr><tr><td><a class="result-link" href="https://example.com/b">B</a></td></tr><tr><td class="result-snippet">snippet B</td></tr>'
        results = parse_duckduckgo_lite(html)
        assert results[0]['snippet'] == '' and results[1]['snippet'] == 'snippet B'
    elif point == 68:
        for mid in ('codex_cli', 'grok_builder_cli'):
            for retry, expected in [('17', 17), ('invalid', None)]:
                a = adapter(mid)
                install(a, lambda r: httpx.Response(429, headers={'Retry-After': retry}, json={'error': {'message': 'fixture limit'}}))
                with pytest.raises(RouterException) as caught: await consume(a)
                assert caught.value.retry_after == expected and caught.value.upstream_status == 429


def test_reasoning_details_collector():
    acc = ChatStreamAccumulator()
    fragments = [
        [{'type': 'thinking', 'index': 0, 'thinking': 'first ', 'signature': 'opaque-'}],
        [{'type': 'thinking', 'index': 0, 'thinking': 'second', 'signature': 'signature'},
         {'type': 'redacted_thinking', 'index': 1, 'data': 'opaque-redacted'}],
    ]
    for details in fragments:
        acc.feed(wire({'choices': [{'index': 0, 'delta': {'reasoning_details': details, 'reasoning_content': 'text'}, 'finish_reason': None}]}))
    acc.feed(wire({'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]}) + 'data: [DONE]\n\n')
    message = acc.response('synthetic', require_complete=True).choices[0].message
    assert message.reasoning_details == [
        {'type': 'thinking', 'index': 0, 'thinking': 'first second', 'signature': 'opaque-signature'},
        {'type': 'redacted_thinking', 'index': 1, 'data': 'opaque-redacted'},
    ]
    assert message.reasoning_content == 'texttext'


@pytest.mark.asyncio
@pytest.mark.parametrize('mid', ['cline', 'clinepass', 'qoder', 'kimi_web', 'lmarena', 'codex_cli', 'grok_builder_cli', 'deepseek_web', 'zai_web'])
async def test_real_handler_bridge_abort_and_cancel(mid, monkeypatch):
    a = adapter(mid)
    c = ctx()
    if mid == 'kimi_web':
        from modules.kimi_web.handler import frame_connect_message
        body = frame_connect_message({'op': 'append', 'mask': 'block.text.content', 'block': {'text': {'content': 'answer'}}})
    elif mid == 'lmarena':
        body = b'0:"answer"\n'
    elif mid in ('codex_cli', 'grok_builder_cli'):
        body = wire({'type': 'response.output_text.delta', 'delta': 'answer'}).encode()
    elif mid == 'deepseek_web':
        body = wire({'v': 'answer'}).encode()
    else:
        body = wire({'choices': [{'index': 0, 'delta': {'content': 'answer'}}]}).encode()
    streams = []
    class Stream(httpx.AsyncByteStream):
        closed = False
        async def __aiter__(self):
            yield body
            await asyncio.sleep(30)
        async def aclose(self): self.closed = True
    def response(r):
        stream = Stream()
        streams.append(stream)
        return httpx.Response(200, stream=stream)
    clients = install(a, response)
    if mid == 'deepseek_web':
        async def token(*args): return 'fixture'
        async def session(*args): return 'fixture-session'
        async def completion(client, *args): return await client.send(client.build_request('POST', 'https://fixture.invalid/completion'), stream=True)
        async def delete(*args): pass
        a._acquire_access_token, a._create_session = token, session
        a._send_completion_request, a._delete_session = completion, delete
    elif mid == 'zai_web':
        mod = importlib.import_module(a.__module__)
        async def fe(client): return 'fixture'
        async def chat(*args): return 'fixture-chat', 'fixture-message'
        monkeypatch.setattr(mod, 'get_zai_fe_version', fe)
        a._create_chat = chat
        token = 'fixture.' + base64.urlsafe_b64encode(b'{"id":"fixture"}').decode().rstrip('=') + '.fixture'
        c = ModuleExecutionContext(credentials={'token': token})
    bridge = CustomModuleAdapter()
    bridge._resolve_context = lambda *args: (a, c)
    gen = bridge.stream_chat('', '', 'synthetic', req(), {}, {})
    await anext(gen)
    await gen.aclose()
    assert all(s.closed for s in streams) and all(client.is_closed for client in clients)
    started = asyncio.Event()
    async def pending(r):
        started.set()
        await asyncio.sleep(30)
    clients = install(a, pending)
    task = asyncio.create_task(a.chat_completions(req(), c))
    await asyncio.wait_for(started.wait(), .5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError): await task
    assert all(client.is_closed for client in clients)


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['normal', 'error', 'flood-abort'])
async def test_ddg_bounded_worker_delivery(mode, monkeypatch):
    mod = importlib.import_module('modules.duckduckgo_web.handler')
    exited, closed = threading.Event(), threading.Event()
    class Response:
        def close(self): closed.set()
        def __enter__(self): return self
        def __exit__(self, *args): exited.set()
        def __iter__(self):
            count = 256 if mode == 'flood-abort' else 1
            for _ in range(count):
                if closed.is_set(): return
                yield b'data: {"message":"answer"}\n'
            if mode == 'error': raise OSError('fixture worker failure')
            yield b'data: [DONE]\n'
    class Opener:
        def open(self, *args, **kwargs): return Response()
    monkeypatch.setattr(mod, 'build_opener', lambda *args: Opener())
    a = adapter('duckduckgo_web')
    a._acquire_auth_headers_sync = lambda *args: {'x-vqd-4': 'fixture'}
    if mode == 'flood-abort':
        gen = a.stream_chat(req(), ctx())
        await asyncio.wait_for(anext(gen), .5)
        await asyncio.sleep(.02)
        await asyncio.wait_for(gen.aclose(), 1)
    elif mode == 'error':
        with pytest.raises(RouterException, match='fixture worker failure'):
            await asyncio.wait_for(consume(a), 1)
    else:
        chunks = await asyncio.wait_for(consume(a), 1)
        acc = ChatStreamAccumulator()
        for chunk in chunks: acc.feed(chunk)
        assert acc.response('synthetic', require_complete=True).choices[0].message.content == 'answer'
    assert closed.is_set() and await asyncio.to_thread(exited.wait, .5)
