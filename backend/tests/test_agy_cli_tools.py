"""Offline AGY contract checks; runnable directly without database fixtures."""
import json
import unittest
from unittest.mock import AsyncMock, patch

import httpx

from app.core.errors import ErrorCategory, RouterException
from app.modules.base import ModuleExecutionContext
from app.schemas.chat import ChatCompletionRequest, ChatMessage
from modules.agy_cli.handler import AgyCliAdapter


class AgyToolsTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.adapter = AgyCliAdapter()
        self.ctx = ModuleExecutionContext(credentials={"auto_detect_local": False})
        self.request = ChatCompletionRequest(model="agy_cli/gemini-test", messages=[{"role": "user", "content": "weather"}], tools=[{"type": "function", "function": {"name": "weather", "description": "Weather", "parameters": {"type": "object", "properties": {"city": {"type": "string"}}}}}])

    def offline(self, transport):
        return patch.object(self.adapter, "create_http_client", side_effect=lambda *a, **k: httpx.AsyncClient(transport=httpx.MockTransport(transport)))

    def test_history_and_config(self):
        self.request.messages = ChatCompletionRequest(model="x", messages=[
            {"role": "system", "content": "rules"},
            {"role": "user", "content": "weather"},
            {"role": "assistant", "tool_calls": [
                {"id": "first", "function": {"name": "weather", "arguments": '{"city":"Paris"}'}},
                {"id": "second", "function": {"name": "weather", "arguments": '{"city":"Rome"}'}}]},
            {"role": "tool", "tool_call_id": "first", "content": '{"temp":20}'},
            {"role": "tool", "tool_call_id": "second", "content": "sunny"},
        ]).messages
        for choice, mode in [("auto", "AUTO"), ("none", "NONE"), ("required", "ANY"), ({"type": "function", "function": {"name": "weather"}}, "ANY")]:
            self.request.tool_choice = choice
            native = self.adapter._build_cloudcode_envelope(self.request, "synthetic-project", self.request.model)["request"]
            self.assertEqual(native["tools"][0]["functionDeclarations"][0]["name"], "weather")
            self.assertEqual(native["toolConfig"]["functionCallingConfig"]["mode"], mode)
            self.assertEqual(native["contents"][1]["parts"][1]["functionCall"]["id"], "second")
            responses = native["contents"][2]["parts"]
            self.assertEqual(responses[0]["functionResponse"], {"id": "first", "name": "weather", "response": {"temp": 20}})
            self.assertEqual(responses[1]["functionResponse"]["response"], {"result": "sunny"})
            if isinstance(choice, dict):
                self.assertEqual(native["toolConfig"]["functionCallingConfig"]["allowedFunctionNames"], ["weather"])

    async def test_stream_and_nonstream_parallel_calls(self):
        payloads = [
            {"response": {"candidates": [{"content": {"parts": [{"text": "checking"}, {"thoughtSignature": "synthetic-signature", "functionCall": {"id": "native-id", "name": "weather", "args": {"city": "Paris"}}}]}}]}},
            {"candidates": [{"content": {"parts": [{"functionCall": {"name": "weather", "args": {"city": "Rome"}}}]}, "finishReason": "STOP"}], "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 4, "totalTokenCount": 14}},
        ]
        def transport(request):
            self.assertEqual(json.loads(request.content)["model"], "gemini-test")
            return httpx.Response(200, text="".join("data:" + json.dumps(p) + "\n\n" for p in payloads))
        with patch.object(self.adapter, "_get_valid_access_token", AsyncMock(return_value=("synthetic-token", "synthetic-project"))), self.offline(transport):
            chunks = [c async for c in self.adapter.stream_chat(self.request, self.ctx)]
            self.assertEqual(chunks[-1], "data: [DONE]\n\n")
            data = [json.loads(c[5:]) for c in chunks[:-1]]
            calls = [t for c in data for t in c["choices"][0]["delta"].get("tool_calls", [])]
            self.assertEqual([t["index"] for t in calls], [0, 1])
            self.assertEqual(calls[0]["id"], "native-id")
            self.assertEqual(calls[0]["extra_content"]["google"]["thought_signature"], "synthetic-signature")
            self.assertEqual(data[-1]["choices"][0]["finish_reason"], "tool_calls")
            response = await self.adapter.chat_completions(self.request, self.ctx)
            self.assertEqual(response.choices[0].message.content, "checking")
            self.assertEqual([c.function.name for c in response.choices[0].message.tool_calls], ["weather", "weather"])
            self.assertEqual(json.loads(response.choices[0].message.tool_calls[1].function.arguments), {"city": "Rome"})
            self.assertEqual(response.choices[0].finish_reason, "tool_calls")
            self.assertEqual(response.usage.total_tokens, 14)
            followup = self.request.model_copy(update={"messages": [
                *self.request.messages, response.choices[0].message,
                *[ChatMessage(role="tool", tool_call_id=c.id, content="sunny") for c in response.choices[0].message.tool_calls],
            ]})
            native = self.adapter._build_cloudcode_envelope(followup, "synthetic-project", followup.model)["request"]
            self.assertEqual([p["functionResponse"]["id"] for p in native["contents"][-1]["parts"]], [c.id for c in response.choices[0].message.tool_calls])
            self.assertEqual(native["contents"][-2]["parts"][1]["thoughtSignature"], "synthetic-signature")

    async def test_normalized_http_and_transport_errors(self):
        for status, category in [(401, ErrorCategory.AUTH_ERROR), (429, ErrorCategory.RATE_LIMIT), (503, ErrorCategory.UPSTREAM_5XX)]:
            with patch.object(self.adapter, "_get_valid_access_token", AsyncMock(return_value=("synthetic-token", "synthetic-project"))), self.offline(lambda req: httpx.Response(status, json={"error": {"message": "failed"}}, headers={"Retry-After": "7"})):
                with self.assertRaises(RouterException) as caught:
                    await self.adapter.chat_completions(self.request, self.ctx)
                self.assertEqual(caught.exception.category, category)
                self.assertEqual(caught.exception.upstream_status, status)
                self.assertEqual(caught.exception.retry_after, 7)
        def timeout(req):
            raise httpx.ReadTimeout("synthetic timeout", request=req)
        with patch.object(self.adapter, "_get_valid_access_token", AsyncMock(return_value=("synthetic-token", "synthetic-project"))), self.offline(timeout):
            with self.assertRaises(RouterException) as caught:
                await self.adapter.chat_completions(self.request, self.ctx)
            self.assertEqual(caught.exception.category, ErrorCategory.TIMEOUT)

    async def test_no_retry_after_output(self):
        seen = []
        async def broken_stream():
            yield b'data: {"candidates":[{"content":{"parts":[{"text":"partial"}]}}]}\n\n'
            raise httpx.ReadError("interrupted")
        class Stream(httpx.AsyncByteStream):
            async def __aiter__(self):
                async for part in broken_stream():
                    yield part
        def transport(req):
            seen.append(req.url)
            return httpx.Response(200, stream=Stream())
        with patch.object(self.adapter, "_get_valid_access_token", AsyncMock(return_value=("synthetic-token", "synthetic-project"))), self.offline(transport):
            with self.assertRaises(RouterException):
                await self.adapter.chat_completions(self.request, self.ctx)
        self.assertEqual(len(seen), 1)

    async def test_inband_error_and_finish_reason(self):
        for payload, category in [({"error": {"code": 429, "message": "exhausted"}}, ErrorCategory.RATE_LIMIT), ({"broken": True}, ErrorCategory.UPSTREAM_5XX)]:
            with patch.object(self.adapter, "_get_valid_access_token", AsyncMock(return_value=("synthetic-token", "synthetic-project"))), self.offline(lambda req: httpx.Response(200, text="data: " + json.dumps(payload) + "\n\n")):
                with self.assertRaises(RouterException) as caught:
                    await self.adapter.chat_completions(self.request, self.ctx)
                self.assertEqual(caught.exception.category, category)
        with patch.object(self.adapter, "_get_valid_access_token", AsyncMock(return_value=("synthetic-token", "synthetic-project"))), self.offline(lambda req: httpx.Response(200, text='data: {"candidates":[{"content":{"parts":[{"text":"short"}]},"finishReason":"MAX_TOKENS"}]}\n\n')):
            response = await self.adapter.chat_completions(self.request, self.ctx)
            self.assertEqual(response.choices[0].finish_reason, "length")

    async def test_fallback_before_output_and_auth_failure(self):
        seen = []
        def transport(req):
            seen.append(req.url)
            if len(seen) == 1:
                return httpx.Response(503, json={"error": {"message": "unavailable"}})
            return httpx.Response(200, text='data: {"candidates":[{"content":{"parts":[{"text":"ok"}]},"finishReason":"STOP"}]}\n\n')
        with patch.object(self.adapter, "_get_valid_access_token", AsyncMock(return_value=("synthetic-token", "synthetic-project"))), self.offline(transport):
            result = await self.adapter.chat_completions(self.request, self.ctx)
            self.assertEqual(result.choices[0].message.content, "ok")
            self.assertEqual(len(seen), 2)
        with patch.object(self.adapter, "_get_valid_access_token", AsyncMock(side_effect=ValueError("synthetic missing token"))), patch.object(self.adapter, "create_http_client", side_effect=AssertionError("must not connect")):
            with self.assertRaises(RouterException) as caught:
                await self.adapter.chat_completions(self.request, self.ctx)
            self.assertEqual(caught.exception.category, ErrorCategory.AUTH_ERROR)

    def test_invalid_history(self):
        for messages in [[{"role": "assistant", "tool_calls": [{"id": "x", "function": {"name": "weather", "arguments": "invalid"}}]}], [{"role": "tool", "tool_call_id": "missing", "content": "x"}]]:
            request = ChatCompletionRequest(model="x", messages=messages)
            with self.assertRaises(RouterException) as caught:
                self.adapter._build_cloudcode_envelope(request, "p", "x")
            self.assertEqual(caught.exception.category, ErrorCategory.INVALID_REQUEST)


if __name__ == "__main__":
    unittest.main()
