"""Google Flash-Lite thinking-off compatibility without changing client requests."""
import json
from unittest.mock import AsyncMock

import httpx
import pytest

from app.adapters.google import GoogleAIStudioAdapter
from app.adapters.openai import GenericOpenAIAdapter
from app.core.http_client import http_client_manager
from app.routing.engine import RoutingEngine
from app.schemas.chat import ChatCompletionRequest


@pytest.mark.asyncio
@pytest.mark.parametrize('stream', [False, True])
@pytest.mark.parametrize('model', ['gemini-3.5-flash-lite', 'models/gemini-3.1-flash-lite-preview'])
@pytest.mark.parametrize('control', [
    {'reasoning_effort': 'none'}, {'reasoning_effort': 'off'}, {'reasoning_effort': 'disabled'},
    {'reasoning': {'effort': 'none'}}, {'thinking': {'type': 'disabled'}},
    {'reasoning_effort': 'low'}, {'reasoning_effort': 'medium'}, {'reasoning_effort': 'high'}, {},
])
async def test_google_reasoning_floor_on_both_transports(monkeypatch, stream, model, control):
    request = ChatCompletionRequest(model='route/gemini-flash-lite', messages=[
        {'role': 'system', 'content': 'Generate a title'}, {'role': 'user', 'content': 'Synthetic task'}],
        response_format={'type': 'json_object'}, **control)
    before = request.model_dump()
    effective = RoutingEngine._apply_model_defaults(request, eff_thinking='high')
    effort = effective.get_effective_reasoning_effort()
    expected = 'minimal' if effort in ('none', 'off', 'disabled') else effort
    seen = []
    def upstream(req):
        body = json.loads(req.content)
        seen.append(body)
        assert body['reasoning_effort'] == expected
        assert body['model'] == model.removeprefix('models/')
        assert body['messages'] == [m.model_dump(exclude_none=True) for m in request.messages]
        assert body['response_format'] == request.response_format
        if stream:
            return httpx.Response(200, text='data: {"choices":[{"index":0,"delta":{"content":"title"}}]}\n\ndata: [DONE]\n\n')
        return httpx.Response(200, json={'choices': [{'message': {'role': 'assistant', 'content': 'title'}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as client:
        monkeypatch.setattr(http_client_manager, 'get_client', AsyncMock(return_value=client))
        kwargs = dict(base_url='https://generativelanguage.googleapis.com', api_key='synthetic',
            model_id=model, request=effective, extra_headers={}, configuration={})
        if stream:
            chunks = [chunk async for chunk in GoogleAIStudioAdapter().stream_chat(**kwargs)]
            assert chunks[-1] == 'data: [DONE]\n\n'
        else:
            assert (await GoogleAIStudioAdapter().chat_completions(**kwargs)).choices[0].message.content == 'title'
    assert len(seen) == 1 and request.model_dump() == before
    assert effective.get_effective_reasoning_effort() == effort


def test_reasoning_floor_is_google_flash_lite_only():
    request = ChatCompletionRequest(model='route/gemini-flash-lite', messages=[], reasoning_effort='none')
    for model in ('gemini-2.5-flash-lite', 'gemini-3.1-pro-preview', 'gemini-3.5-flash', 'gpt-6.1-sol'):
        assert GoogleAIStudioAdapter._prepare_reasoning_request(model, request) is request
    assert GenericOpenAIAdapter()._prepare_payload('gemini-3.5-flash-lite', request)['reasoning_effort'] == 'none'
    for model in ('gemini-3-flash-lite', 'google/gemini-3.5-flash-lite'):
        assert GoogleAIStudioAdapter._prepare_reasoning_request(model, request).reasoning_effort == 'minimal'
