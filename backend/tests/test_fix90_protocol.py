"""Correctness regressions for the approved 90-point audit; synthetic upstreams only."""
import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import select

from app.adapters.anthropic import AnthropicAdapter
from app.adapters.google import GoogleAIStudioAdapter
from app.adapters.openai import GenericOpenAIAdapter
from app.core.errors import ErrorCategory, RouterException
from app.core.http_client import http_client_manager
from app.schemas.chat import ChatCompletionRequest, ChatMessage, ResponsesRequest


def request(**kwargs):
    return ChatCompletionRequest(model='fixture-model', messages=[ChatMessage(role='user',content='synthetic')],**kwargs)


def mock_client(monkeypatch, handler):
    client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(http_client_manager,'get_client',AsyncMock(return_value=client))
    return client


def events(*data):
    return ''.join('data: '+json.dumps(d)+'\n\n' for d in data)


@pytest.mark.asyncio
async def test_p01_anthropic_stream_tools_thinking_signature_usage(monkeypatch):
    body=events(
        {'type':'message_start','message':{'id':'msg_fixture','usage':{'input_tokens':7,'output_tokens':1}}},
        {'type':'content_block_start','index':0,'content_block':{'type':'thinking','thinking':''}},
        {'type':'content_block_delta','index':0,'delta':{'type':'thinking_delta','thinking':'plan'}},
        {'type':'content_block_delta','index':0,'delta':{'type':'signature_delta','signature':'opaque-sig'}},
        {'type':'content_block_stop','index':0},
        {'type':'content_block_start','index':1,'content_block':{'type':'tool_use','id':'call_fixture','name':'lookup','input':{}}},
        {'type':'content_block_delta','index':1,'delta':{'type':'input_json_delta','partial_json':'{"q":"x"}'}},
        {'type':'content_block_stop','index':1},
        {'type':'message_delta','delta':{'stop_reason':'tool_use'},'usage':{'output_tokens':3}},
        {'type':'message_stop'})
    async with mock_client(monkeypatch,lambda r:httpx.Response(200,text=body,headers={'content-type':'text/event-stream'})):
        chunks=[c async for c in AnthropicAdapter().stream_chat('https://fixture.invalid','synthetic','m',request(),{}, {})]
    data=[json.loads(c[6:]) for c in chunks if '[DONE]' not in c]
    assert chunks[-1]=='data: [DONE]\n\n'
    assert any(c['choices'] and c['choices'][0]['finish_reason']=='tool_calls' for c in data)
    deltas=[c['choices'][0]['delta'] for c in data if c['choices']]
    assert ''.join(d.get('reasoning_content','') for d in deltas)=='plan'
    assert any(d.get('reasoning_details',[{}])[0].get('signature')=='opaque-sig' for d in deltas)
    calls=[x for d in deltas for x in d.get('tool_calls',[])]
    assert calls[0]['id']=='call_fixture' and calls[0]['function']['name']=='lookup'
    assert ''.join(c['function'].get('arguments','') for c in calls)=='{"q":"x"}'
    assert data[-1]['usage']=={'prompt_tokens':7,'completion_tokens':3,'total_tokens':10}


@pytest.mark.asyncio
@pytest.mark.parametrize('body,expected',[(events({'type':'error','error':{'type':'overloaded_error','message':'fixture overload'}}),ErrorCategory.UPSTREAM_5XX),
    (events({'type':'content_block_delta','index':0,'delta':{'type':'text_delta','text':'partial'}}),ErrorCategory.NETWORK_ERROR)])
async def test_p01_anthropic_error_and_eof_are_not_success(monkeypatch,body,expected):
    async with mock_client(monkeypatch,lambda r:httpx.Response(200,text=body)):
        with pytest.raises(RouterException) as err:
            _=[c async for c in AnthropicAdapter().stream_chat('https://fixture.invalid','synthetic','m',request(),{}, {})]
    assert err.value.category==expected


def test_p02_anthropic_tool_history_choice_and_developer():
    req=ChatCompletionRequest(model='m',messages=[{'role':'system','content':'policy'},
        {'role':'assistant','tool_calls':[{'id':'call_fixture','function':{'name':'lookup','arguments':'{"q":"x"}'}}]},
        {'role':'tool','tool_call_id':'call_fixture','content':'result'}],
        tools=[{'type':'function','function':{'name':'lookup','parameters':{'type':'object'}}}],
        tool_choice={'type':'function','function':{'name':'lookup'}},parallel_tool_calls=False)
    p=AnthropicAdapter()._prepare_payload('m',req)
    assistant=next(m for m in p['messages'] if m['role']=='assistant')
    assert {'type':'tool_use','id':'call_fixture','name':'lookup','input':{'q':'x'}} in assistant['content']
    assert p['messages'][-1]['content']==[{'type':'tool_result','tool_use_id':'call_fixture','content':'result'}]
    assert p['tool_choice']=={'type':'tool','name':'lookup','disable_parallel_tool_use':True}


@pytest.mark.asyncio
@pytest.mark.parametrize('data,status',[({'error':{'message':'synthetic unavailable','code':503}},502),({'choices':[]},502),([],502)])
async def test_p03_http200_errors_and_invalid_success(monkeypatch,data,status):
    async with mock_client(monkeypatch,lambda r:httpx.Response(200,json=data)):
        with pytest.raises(RouterException) as err:
            await GenericOpenAIAdapter().chat_completions('https://fixture.invalid','synthetic','m',request(),{}, {})
    assert err.value.status_code==status
    if isinstance(data,dict) and data.get("error"):
        assert err.value.upstream_status==503 and err.value.category==ErrorCategory.UPSTREAM_5XX


def test_p05_responses_image_conversion():
    req=ResponsesRequest(model='m',input=[{'role':'user','content':[{'type':'input_text','text':'image'},
        {'type':'input_image','image_url':'data:image/png;base64,AA==','detail':'high'}]}]).to_chat_request()
    assert req.messages[0].content==[{'type':'text','text':'image'},
        {'type':'image_url','image_url':{'url':'data:image/png;base64,AA==','detail':'high'}}]
    with pytest.raises(ValueError):
        ResponsesRequest(model='m',input=[{'content':[{'type':'unknown'}]}]).to_chat_request()


@pytest.mark.asyncio
async def test_p33_custom_stage_ids_unique_with_frozen_clock(monkeypatch):
    from app.compression.pipeline import CompressionPipelineService
    from app.core.database import AsyncSessionLocal
    monkeypatch.setattr('app.compression.pipeline.time.time',lambda:1700000000)
    async with AsyncSessionLocal() as db:
        a=await CompressionPipelineService.create_custom_stage(db,{'name':'fixture-a'})
        b=await CompressionPipelineService.create_custom_stage(db,{'name':'fixture-b'})
        assert a.id!=b.id


def test_p34_developer_role_preserved_and_translated():
    req=ChatCompletionRequest(model='m',messages=[{'role':'developer','content':'policy'},{'role':'user','content':'question'}])
    assert GenericOpenAIAdapter()._prepare_payload('m',req)['messages'][0]['role']=='developer'
    assert AnthropicAdapter()._prepare_payload('m',req)['system']=='policy'
    assert ResponsesRequest(model='m',input=[{'role':'developer','content':'policy'}]).to_chat_request().messages[0].role=='developer'


@pytest.mark.asyncio
@pytest.mark.parametrize('family',['anthropic','google'])
async def test_p37_discovery_all_pages_dedup_and_failure(monkeypatch,family):
    seen=[]
    def handler(req):
        seen.append(dict(req.url.params))
        if family=='anthropic':
            second=bool(req.url.params.get('after_id'))
            return httpx.Response(200,json={'data':[{'id':'m2' if second else 'm1'}],'has_more':not second,'last_id':'m1' if not second else 'm2'})
        second=bool(req.url.params.get('pageToken'))
        return httpx.Response(200,json={'models':[{'name':'models/m2' if second else 'models/m1','supportedGenerationMethods':['generateContent']}],
            **({} if second else {'nextPageToken':'next-fixture'})})
    adapter=AnthropicAdapter() if family=='anthropic' else GoogleAIStudioAdapter()
    async with mock_client(monkeypatch,handler):
        models=await adapter.list_models('https://fixture.invalid','synthetic',{}, {})
    assert [m.provider_model_id for m in models]==['m1','m2'] and len(seen)==2
    def failure(req):
        if req.url.params.get('after_id') or req.url.params.get('pageToken'):return httpx.Response(503,json={'error':{'message':'page2 synthetic failure'}})
        return handler(req)
    async with mock_client(monkeypatch,failure):
        with pytest.raises(RouterException):await adapter.list_models('https://fixture.invalid','synthetic',{}, {})


def test_p42_openai_logit_bias_transmitted():
    assert GenericOpenAIAdapter()._prepare_payload('m',request(logit_bias={'10':-4.0}))['logit_bias']=={'10':-4.0}
