import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse
from app.api.v1 import router as api
from app.schemas.chat import ChatCompletionChoice, ChatCompletionResponse, ChatMessage, UsageInfo
from app.modules.base import ChatStreamAccumulator


def completion(finish='stop', tools=False, responses=False):
    return ChatCompletionResponse(model='demo', choices=[ChatCompletionChoice(
        message=ChatMessage(role='assistant', content='hé', reasoning_details=[
            {'type': 'reasoning', 'id': 'rs_fixture', 'summary': [{'type': 'summary_text', 'text': 'consider'}]}
            if responses else {'type': 'thinking', 'thinking': 'consider', 'signature': 'opaque'}],
            tool_calls=[{'id': 'call_a', 'function': {'name': 'clock', 'arguments': '{}'}}] if tools else None),
        finish_reason=finish)], usage=UsageInfo(prompt_tokens=5, completion_tokens=7, total_tokens=12))


def request(body=None, raw=None):
    data = raw if raw is not None else json.dumps(body).encode()
    async def receive():
        return {'type': 'http.request', 'body': data, 'more_body': False}
    return Request({'type': 'http', 'headers': []}, receive)


async def source(finish='stop', error=False, done=True, closed=None, responses=False):
    try:
        data = [ {'choices': [{'index': 0, 'delta': {'content': 'hé', 'reasoning_details': [
            {'type': 'reasoning', 'index': 0, 'id': 'rs_fixture', 'summary': [{'type': 'summary_text', 'text': 'consider'}]}
            if responses else {'type': 'thinking', 'index': 0, 'thinking': 'consider', 'signature': 'opaque'}],
            'tool_calls': [{'index': 0, 'id': 'call_a', 'function': {'name': 'clock', 'arguments': '{}'}}]}, 'finish_reason': None}], 'usage': None}]
        if error:
            data.append({'error': {'type': 'upstream_error', 'message': 'fixture error'}})
        elif finish:
            data.extend([{'choices': [{'index': 0, 'delta': {}, 'finish_reason': finish}]},
                         {'choices': [], 'usage': {'prompt_tokens': 5, 'completion_tokens': 7, 'total_tokens': 12}}])
        wire = ''.join('data: '+json.dumps(d, ensure_ascii=False)+'\n\n' for d in data)
        if done:
            wire += 'data: [DONE]\n\n'
        raw = wire.encode()
        for i in range(0, len(raw), 7):
            yield raw[i:i+7]
    finally:
        if closed is not None:
            closed.append(True)


async def events(generator):
    return [json.loads(chunk.split('data: ', 1)[1]) async for chunk in generator]


@pytest.mark.parametrize('finish,status,reason', [('stop','completed',None), ('length','incomplete','max_output_tokens')])
def test_p06_responses_json(finish, status, reason):
    result = api._responses_payload(completion(finish, responses=True), 'resp_fixture')
    assert result['status'] == status
    assert result['incomplete_details'] == ({'reason': reason} if reason else None)


@pytest.mark.asyncio
@pytest.mark.parametrize('finish', ['stop','length','tool_calls'])
async def test_p06_p07_responses_fragmented_stream(finish):
    closed=[]
    result=await events(api._responses_event_stream(source(finish, closed=closed, responses=True), 'demo','resp_fixture'))
    assert result[-1]['type'] == ('response.incomplete' if finish=='length' else 'response.completed')
    assert result[-1]['response']['usage']['output_tokens']==7
    assert result[-1]['response']['output_text']=='hé'
    assert closed==[True]


@pytest.mark.asyncio
@pytest.mark.parametrize('bridge', [api._responses_event_stream, api._anthropic_event_stream])
@pytest.mark.parametrize('error,done', [(True,True),(False,False),(False,True)])
async def test_p07_error_or_unfinished_eof_never_success(bridge,error,done):
    closed=[]
    result=await events(bridge(source(None,error,done,closed),'demo','fixture_id'))
    assert result[-1]['type'] in ('error','response.failed')
    assert not any(e['type'] in ('message_stop','response.completed') for e in result)
    assert closed==[True]


@pytest.mark.asyncio
@pytest.mark.parametrize('finish,stop', [('stop','end_turn'),('length','max_tokens'),('tool_calls','tool_use')])
async def test_p04_p36_messages_stream_tools_thinking_usage(finish,stop):
    result=await events(api._anthropic_event_stream(source(finish),'demo','msg_fixture'))
    blocks=[e['content_block'] for e in result if e['type']=='content_block_start']
    assert any(b['type']=='tool_use' and b['id']=='call_a' for b in blocks)
    assert any(e.get('delta',{}).get('signature')=='opaque' for e in result)
    terminal=next(e for e in result if e['type']=='message_delta')
    assert terminal['delta']['stop_reason']==stop
    assert terminal['usage']=={'input_tokens':5,'output_tokens':7}
    assert result[-1]['type']=='message_stop'


@pytest.mark.asyncio
@pytest.mark.parametrize('body', [[], None, {'model':'demo','max_tokens':10,'messages':{}},
    {'model':'demo','max_tokens':10,'messages':[{'role':'system','content':'x'}]},
    {'model':'demo','max_tokens':10,'messages':[{'role':'user','content':'x'}],'tool_choice':{'type':'bogus'}},
    {'model':'demo','max_tokens':10,'messages':[{'role':'user','content':[{'type':'image','source':[]}]}]}])
async def test_p35_bad_messages_are400(body):
    with patch.object(api,'chat_completions',AsyncMock()) as dispatch:
        result=await api.anthropic_messages_inbound(request(body),Response(),None,None)
    assert result.status_code==400
    dispatch.assert_not_called()


@pytest.mark.asyncio
async def test_p35_malformed_json400():
    result=await api.anthropic_messages_inbound(request(raw=b'{'),Response(),None,None)
    assert result.status_code==400


@pytest.mark.asyncio
@pytest.mark.parametrize('stream',[False,True])
async def test_p04_messages_history_images_choice_and_output(stream):
    body={'model':'demo','max_tokens':2048,'stream':stream,'thinking':{'type':'enabled','budget_tokens':1024},
      'tools':[{'name':'clock','input_schema':{'type':'object'}}],'tool_choice':{'type':'auto','disable_parallel_tool_use':True},
      'messages':[{'role':'user','content':[{'type':'image','source':{'type':'base64','media_type':'image/png','data':'aGVsbG8='}}]},
      {'role':'assistant','content':[{'type':'thinking','thinking':'consider','signature':'opaque'},
       {'type':'tool_use','id':'call_a','name':'clock','input':{}}]},
      {'role':'user','content':[{'type':'tool_result','tool_use_id':'call_a','content':'noon'}]}]}
    returned=StreamingResponse(source('tool_calls')) if stream else completion('tool_calls',True)
    with patch.object(api,'chat_completions',AsyncMock(return_value=returned)) as dispatch:
        result=await api.anthropic_messages_inbound(request(body),Response(),None,None)
    req=dispatch.call_args.args[0]
    assert req.tools[0]['function']['name']=='clock' and req.tool_choice=='auto'
    assert req.parallel_tool_calls is False and req.thinking==body['thinking']
    assert req.messages[0].content[0]['image_url']['url']=='data:image/png;base64,aGVsbG8='
    assert req.messages[1].reasoning_details[0]['signature']=='opaque'
    assert req.messages[1].tool_calls[0].id=='call_a'
    assert req.messages[2].tool_call_id=='call_a'
    if stream:
        assert (await events(result.body_iterator))[-1]['type']=='message_stop'
    else:
        assert result['stop_reason']=='tool_use'
        assert result['content'][-1]=={'type':'tool_use','id':'call_a','name':'clock','input':{}}


def test_p38_null_usage_absent_real_zero_present():
    acc=ChatStreamAccumulator()
    acc.feed('data: {"choices": [], "usage": null}\n\n')
    assert acc.usage is None
    acc.feed('data: {"choices": [], "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}\n\n')
    assert acc.usage is not None


@pytest.mark.asyncio
@pytest.mark.parametrize('bridge',[api._responses_event_stream,api._anthropic_event_stream])
async def test_native_aclose_closes_source(bridge):
    closed=[]
    gen=bridge(source(closed=closed),'demo','fixture')
    await anext(gen)
    await anext(gen)
    await gen.aclose()
    assert closed==[True]
