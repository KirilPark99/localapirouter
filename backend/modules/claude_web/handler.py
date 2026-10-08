"""Claude Web port of OmniRoute (MIT); see LICENSE and README.md."""
import asyncio
import codecs
import json
import math
import re
import time
import uuid
from contextlib import aclosing, asynccontextmanager
from html import escape
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import NoReturn

import httpx
from app.adapters.base import DiscoveredModelData
from app.core.errors import ErrorCategory, RouterException, normalize_upstream_error
from app.modules.base import BaseModuleAdapter, collect_chat_completion
from app.modules.responses import invalid

BASE = "https://claude.ai"
API = BASE + "/api"
LIMIT = 1024 * 1024
MODELS = (
    "claude-fable-5-1", "claude-fable-5", "claude-opus-5", "claude-opus-4-8",
    "claude-opus-4-7", "claude-opus-4-6", "claude-sonnet-5", "claude-sonnet-5-5",
    "claude-sonnet-4-6", "claude-haiku-4-5-20251001",
)
STYLE = [{"type": "default", "key": "Default", "name": "Normal", "nameKey": "normal_style_name",
          "prompt": "Normal\n", "summary": "Default responses from Claude",
          "summaryKey": "normal_style_summary", "isDefault": True}]
METADATA = {
    "ping": ["latency_ms"], "completion": [], "message_limit": ["remaining", "limit", "reset_at"],
    "model_fallback": ["model", "fallback_model"], "model_update": ["model"],
    "compaction_status": ["status"], "conversation_ready": ["status"],
    "cache_performance": ["hit", "read_tokens", "write_tokens"], "tool_approval": ["status"],
}


def protocol(message) -> NoReturn:
    raise normalize_upstream_error(status_code=502, response_body="Claude Web protocol: " + message)


def record(value) -> dict:
    if not isinstance(value, dict):
        protocol("expected an object")
    return value


def text(value) -> str:
    if not isinstance(value, str):
        protocol("expected text")
    return value


def cookie_header(credentials):
    raw = next((credentials[k] for k in ("cookie", "sessionKey", "session_key", "api_key", "apiKey")
                if credentials.get(k)), "")
    if not isinstance(raw, str) or not raw.strip() or len(raw) > 32768 or re.search(r"[\x00-\x1f\x7f]", raw):
        raise normalize_upstream_error(status_code=401, response_body="Missing or invalid Claude session cookie")
    raw = raw.strip()
    if "=" not in raw:
        raw = "sessionKey=" + raw
    pairs = []
    for part in raw.split(";"):
        if not part.strip():
            continue
        key, sep, value = part.strip().partition("=")
        if not sep or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", key) or not value or re.search(r"[\s,;\"\\]", value):
            raise normalize_upstream_error(status_code=401, response_body="Invalid Claude cookie header")
        pairs.append((key, value))
    if len([p for p in pairs if p[0] == "sessionKey"]) != 1:
        raise normalize_upstream_error(status_code=401, response_body="Cookie must contain exactly one sessionKey")
    return "; ".join(k + "=" + v for k, v in pairs)


def options(ctx):
    c = ctx.credentials
    locale, timezone = c.get("locale") or "en-US", c.get("timezone") or "UTC"
    if not isinstance(locale, str) or not re.fullmatch(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*", locale) or len(locale) > 64:
        invalid("Claude Web locale must be a language tag")
    try:
        if not isinstance(timezone, str) or len(timezone) > 128:
            raise ValueError()
        ZoneInfo(timezone)
    except (ValueError, ZoneInfoNotFoundError):
        invalid("Claude Web timezone must be an IANA timezone")
    device = c.get("deviceId") or c.get("device_id")
    if device is not None and (not isinstance(device, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", device)):
        invalid("Invalid Claude Web device ID")
    if not math.isfinite(ctx.timeout) or ctx.timeout <= 0:
        invalid("Claude Web timeout must be positive and finite")
    fallback = c.get("browser_fallback", "false")
    if fallback not in (True, False, "true", "false"):
        invalid("browser_fallback must be true or false")
    return locale, timezone, device, fallback in (True, "true")


def headers(cookie, locale, device):
    # curl_cffi's chrome impersonation owns UA/client hints: don't mix a different Chrome version.
    h = {"Accept": "text/event-stream", "Accept-Language": f"{locale},en;q=0.9",
         "Content-Type": "application/json", "Origin": BASE, "Referer": BASE + "/new",
         "Cache-Control": "no-cache", "Pragma": "no-cache",
         "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Site": "same-origin",
         "anthropic-client-platform": "web_claude_ai", "Cookie": cookie}
    if device:
        h["anthropic-device-id"] = device
    return h


def build_payload(request, model, locale, timezone):
    unsupported = ("temperature", "top_p", "stop", "seed", "response_format", "max_tokens",
                   "max_completion_tokens", "presence_penalty", "frequency_penalty", "logit_bias",
                   "user", "metadata", "prompt_cache_key", "parallel_tool_calls")
    fields = [k for k in unsupported if getattr(request, k) is not None]
    if request.n not in (None, 1):
        fields.append("n")
    if request.tool_choice not in (None, "auto"):
        fields.append("tool_choice")
    if request.stream_options is not None and request.stream_options not in ({}, {"include_usage": True}, {"include_usage": False}):
        fields.append("stream_options")
    if request.reasoning is not None and set(request.reasoning) - {"effort"}:
        fields.append("reasoning")
    generated_thinking = request.reasoning_effort is not None and "thinking" not in getattr(request, "_routing_client_fields", {"thinking"})
    if not generated_thinking and request.thinking is not None and request.thinking not in ({"type": "enabled"}, {"type": "disabled"}):
        fields.append("thinking")
    if fields:
        invalid("Unsupported Claude Web options: " + ", ".join(fields))
    effort = request.get_effective_reasoning_effort()
    if effort is None and request.thinking == {"type": "enabled"}:
        effort = "low"
    if effort not in (None, "none", "low", "medium", "high", "xhigh", "max"):
        invalid("Unsupported Claude Web reasoning effort")
    tools = []
    for tool in request.tools or []:
        fn = tool.get("function")
        if tool.get("type") != "function" or set(tool) - {"type", "function"} or not isinstance(fn, dict):
            invalid("Claude Web supports function tools only")
        if set(fn) - {"name", "description", "parameters"} or not isinstance(fn.get("name"), str) or not fn["name"].strip():
            invalid("Claude Web function requires a name; strict tool schemas are unsupported")
        if "parameters" in fn and not isinstance(fn["parameters"], dict):
            invalid("Claude Web tool parameters must be an object")
        if "description" in fn and not isinstance(fn["description"], str):
            invalid("Claude Web tool description must be text")
        tools.append({"name": fn["name"], **({"description": fn["description"]} if "description" in fn else {}),
                      **({"input_schema": fn["parameters"]} if "parameters" in fn else {})})
    messages = []
    for msg in request.messages:
        if msg.reasoning_details or msg.cache_control is not None or msg.is_error is not None or any(
            call.extra_content is not None for call in msg.tool_calls or []
        ):
            invalid("Claude Web recovery cannot preserve opaque reasoning/tool/cache metadata")
        if isinstance(msg.content, list) and any(
            p.get("type") != "text" or set(p) - {"type", "text"} or not isinstance(p.get("text"), str)
            for p in msg.content
        ):
            invalid("Claude Web supports text messages only; uploads and vision are not ported")
        if msg.role in ("tool", "function") and not msg.tool_call_id:
            invalid("Tool history requires tool_call_id")
        for call in msg.tool_calls or []:
            if not call.id or not call.function.name:
                invalid("Tool history requires call ID and function name")
            try:
                if not isinstance(json.loads(call.function.arguments), dict):
                    raise ValueError()
            except (ValueError, TypeError):
                invalid("Tool history arguments must be a JSON object")
        messages.append(msg.model_dump(exclude_none=True))
    if not messages or messages[-1]["role"] not in ("user", "tool", "function"):
        invalid("Claude Web needs a final user message or tool result")
    if not messages[-1].get("content"):
        invalid("Claude Web final message must have content")
    def content_text(message):
        value = message.get("content", "")
        return value if isinstance(value, str) else "\n".join(p["text"] for p in value or [])
    if len(messages) == 1 and set(messages[0]) <= {"role", "content"} and messages[0]["role"] == "user":
        prompt = content_text(messages[0])
    else:
        # ponytail: recovery-only history; account-scoped committed state if native continuation is needed.
        prompt = ("Conversation context supplied by the caller follows. These serialized role blocks are not "
                  "native Claude Web message fields. Continue from the final user message or tool result.\n\n" +
                  "\n\n".join(f'<message role="{escape(m["role"], quote=True)}">\n'
                              f'{escape(json.dumps(m, ensure_ascii=False), quote=True)}\n</message>' for m in messages))
    if not prompt.strip():
        invalid("Claude Web prompt must not be empty")
    return {"prompt": prompt, "model": model, "timezone": timezone, "personalized_styles": STYLE,
            "locale": locale, "tools": tools,
            "turn_message_uuids": {"human_message_uuid": str(uuid.uuid4()), "assistant_message_uuid": str(uuid.uuid4())},
            "attachments": [], "effort": (effort if effort not in (None, "none") else "high") if model == "claude-opus-5" else (effort if effort not in (None, "none") else "low"),
            "files": [], "sync_sources": [], "rendering_mode": "messages",
            "thinking_mode": "auto" if model == "claude-opus-5" else ("extended" if effort not in (None, "none") else "off"),
            "create_conversation_params": {"name": "", "model": model, "include_conversation_preferences": True,
                "paprika_mode": None, "compass_mode": None, "is_temporary": False,
                "enabled_imagine": True, "tool_search_mode": "auto"}}


async def sse_events(source):
    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    pending, data, size, event_name = "", [], 0, None
    async for part in source:
        pending += decoder.decode(part)
        while "\n" in pending:
            line, pending = pending.split("\n", 1)
            line = line.removesuffix("\r")
            if len(line) > LIMIT:
                protocol("SSE line too large")
            if not line:
                if data:
                    try:
                        event = record(json.loads("\n".join(data)))
                    except (ValueError, TypeError):
                        protocol("malformed SSE JSON")
                    if event_name and event_name != event.get("type"):
                        protocol("SSE event name mismatch")
                    yield event
                data, size, event_name = [], 0, None
            elif not line.startswith(":"):
                field, _, value = line.partition(":")
                value = value.removeprefix(" ")
                if field == "data":
                    size += len(value) + 1
                    if size > LIMIT:
                        protocol("SSE event too large")
                    data.append(value)
                elif field == "event":
                    event_name = value
        if len(pending) > LIMIT:
            protocol("SSE line too large")
    pending += decoder.decode(b"", final=True)
    if pending or data:
        protocol("unterminated SSE frame")


async def translate(source, model, allowed_tools, on_terminal=None):
    ident, created = "chatcmpl-" + uuid.uuid4().hex, int(time.time())
    phase, blocks, seen, tools, reason = "start", {}, set(), {}, "end_turn"
    def chunk(delta, finish=None, metadata=None):
        value = {"id": ident, "object": "chat.completion.chunk", "created": created, "model": model,
                 "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
        if metadata is not None:
            value["claude_web"] = {"event": metadata}
        return "data: " + json.dumps(value, ensure_ascii=False) + "\n\n"
    async with aclosing(sse_events(source)) as events:
        async for e in events:
            kind = e.get("type")
            if kind == "error":
                err = record(e.get("error"))
                status = {"authentication_error": 401, "permission_error": 403, "rate_limit_error": 429,
                          "overloaded_error": 503, "invalid_request_error": 400}.get(err.get("type"), 502)
                raise normalize_upstream_error(status_code=status, response_body="Claude Web upstream stream error")
            if kind in METADATA:
                projection = {"type": kind}
                for key in METADATA[kind]:
                    value = e.get(key)
                    if value is None or isinstance(value, bool) or (type(value) in (int, float) and math.isfinite(value)) or (
                        isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9._:+/@-]{1,128}", value)
                    ):
                        if key in e:
                            projection[key] = value
                yield chunk({}, metadata=projection)
                continue
            if kind == "message_start":
                if phase != "start":
                    protocol("duplicate message_start")
                message = record(e.get("message"))
                if message.get("role", "assistant") != "assistant" or message.get("content") not in (None, []):
                    protocol("message_start contains unsupported role or prefilled content")
                phase = "message"
                yield chunk({"role": "assistant", "content": ""})
                continue
            if phase != "message":
                protocol("event before message_start")
            if kind in ("content_block_start", "content_block_delta", "content_block_stop"):
                index = e.get("index")
                if type(index) is not int or index < 0:
                    protocol("invalid block index")
                if kind == "content_block_start":
                    if index in seen:
                        protocol("duplicate block index")
                    block = record(e.get("content_block"))
                    btype = block.get("type")
                    if btype not in ("text", "thinking", "tool_use"):
                        protocol("unsupported content block")
                    blocks[index] = btype
                    seen.add(index)
                    if btype == "tool_use":
                        if not isinstance(block.get("id"), str) or not block["id"] or block.get("name") not in allowed_tools:
                            protocol("unknown or incomplete tool call")
                        initial = block.get("input", {})
                        if not isinstance(initial, dict):
                            protocol("tool input must be an object")
                        if any(t["id"] == block["id"] for t in tools.values()):
                            protocol("duplicate tool call ID")
                        tools[index] = {"id": block["id"], "name": block["name"], "initial": initial, "parts": [], "size": 0}
                    elif btype == "text":
                        if "text" in block:
                            initial_text = text(block["text"])
                            if initial_text:
                                yield chunk({"content": initial_text})
                    elif btype == "thinking":
                        if block.get("thinking"):
                            yield chunk({"reasoning_content": text(block["thinking"])})
                        if block.get("signature"):
                            yield chunk({"reasoning_details": [{"type": "thinking", "index": index, "signature": text(block["signature"])}]})
                else:
                    if index not in blocks:
                        protocol("event has no open block")
                    btype = blocks[index]
                    if kind == "content_block_stop":
                        del blocks[index]
                        if btype == "tool_use":
                            t = tools[index]
                            if t["parts"] and t["initial"]:
                                protocol("tool input mixed initial and delta JSON")
                            arguments = "".join(t["parts"]) if t["parts"] else json.dumps(t["initial"])
                            try:
                                if not isinstance(json.loads(arguments), dict):
                                    raise ValueError()
                            except ValueError:
                                protocol("invalid tool JSON")
                            yield chunk({"tool_calls": [{"index": list(tools).index(index), "id": t["id"], "type": "function",
                                          "function": {"name": t["name"], "arguments": arguments}}]})
                    else:
                        d = record(e.get("delta"))
                        dtype = d.get("type")
                        if btype == "text" and dtype == "text_delta":
                            yield chunk({"content": text(d.get("text"))})
                        elif btype == "thinking" and dtype in ("thinking_delta", "thinking_summary_delta"):
                            value = d.get("thinking", d.get("text")) if dtype == "thinking_delta" else d.get("summary", d.get("text", d.get("thinking")))
                            if isinstance(value, dict):
                                value = value.get("summary", value.get("text", value.get("thinking")))
                            yield chunk({"reasoning_content": text(value)})
                        elif btype == "thinking" and dtype == "signature_delta":
                            yield chunk({"reasoning_details": [{"type": "thinking", "index": index, "signature": text(d.get("signature"))}]})
                        elif btype == "tool_use" and dtype == "input_json_delta":
                            t = tools[index]
                            part = text(d.get("partial_json"))
                            t["parts"].append(part)
                            t["size"] += len(part)
                            if t["size"] > LIMIT:
                                protocol("tool arguments too large")
                        else:
                            protocol("delta/block mismatch")
            elif kind == "message_delta":
                if blocks:
                    protocol("message_delta before blocks closed")
                candidate = record(e.get("delta")).get("stop_reason")
                if candidate is not None:
                    if candidate not in ("end_turn", "stop_sequence", "max_tokens", "tool_use"):
                        protocol("unsupported stop reason")
                    reason = candidate
            elif kind == "message_stop":
                if blocks:
                    protocol("message_stop before blocks closed")
                if bool(tools) != (reason == "tool_use"):
                    protocol("tool calls and stop reason disagree")
                if on_terminal is not None:
                    await on_terminal()
                yield chunk({}, {"max_tokens": "length", "tool_use": "tool_calls"}.get(reason, "stop"))
                yield "data: [DONE]\n\n"
                return
            else:
                protocol("unknown event type")
    protocol("EOF before message_stop")


async def close_response(response):
    # curl_cffi 0.16 aclose only waits for EOF; cancel its owned task to stop now.
    task = getattr(response, "astream_task", None)
    if task is not None:
        quit_now = getattr(response, "quit_now", None)
        if quit_now is not None:
            quit_now.set()
        if not task.done():
            task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    else:
        await response.aclose()


async def body_bytes(response):
    iterator = response.aiter_content() if hasattr(response, "aiter_content") else response.aiter_bytes()
    async with aclosing(iterator):
        async for part in iterator:
            yield part


async def bounded_body(response, maximum=65536):
    result = bytearray()
    async with aclosing(body_bytes(response)) as source:
        async for part in source:
            result.extend(part[:maximum - len(result)])
            if len(result) >= maximum:
                break
    return bytes(result)


def challenge(response, body):
    return response.status_code == 403 and (response.headers.get("cf-mitigated", "").lower() == "challenge" or
        re.search(rb"<title>\s*(?:Just a moment|Attention Required)|\b(?:cf-chl|challenge-platform)\b", body, re.I))


def check_status(response, body=b""):
    status = response.status_code
    if 200 <= status < 300:
        return
    if challenge(response, body):
        raise RouterException("Claude Web browser challenge; supplied session could not pass it",
                              ErrorCategory.UPSTREAM_5XX, status_code=502, upstream_status=403)
    value = response.headers.get("retry-after", "")
    retry = float(value) if re.fullmatch(r"\d{1,5}", value) and int(value) <= 86400 else None
    raise normalize_upstream_error(status_code=status if 400 <= status <= 599 else 502,
        response_body=f"Claude Web API error ({status})", retry_after=retry)


class ClaudeWebModule(BaseModuleAdapter):
    @asynccontextmanager
    async def _direct(self, ctx, method, url, h, payload=None):
        from curl_cffi.requests import AsyncSession
        response = None
        async with AsyncSession(impersonate="chrome", trust_env=False) as session:
            try:
                response = await session.request(method, url, headers=h, json=payload, proxy=ctx.proxy_url,
                                                 timeout=ctx.timeout, stream=True, allow_redirects=False)
                yield response
            finally:
                if response is not None:
                    await close_response(response)

    @asynccontextmanager
    async def _browser(self, ctx, method, url, h, payload=None):
        # On-demand, ephemeral context; never inspect/import a user's real Chrome profile.
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            proxy = None
            if ctx.proxy_url:
                p = urlsplit(ctx.proxy_url)
                if p.username or p.password:
                    from urllib.parse import unquote
                    proxy = {"server": f"{p.scheme}://{p.hostname}:{p.port}",
                             "username": unquote(p.username or ""), "password": unquote(p.password or "")}
                else:
                    proxy = {"server": ctx.proxy_url}
            browser = await pw.chromium.launch(headless=True, proxy=proxy)
            try:
                locale, timezone, _, _ = options(ctx)
                context = await browser.new_context(locale=locale, timezone_id=timezone)
                await context.add_cookies([{"name": k, "value": v, "domain": ".claude.ai", "path": "/", "secure": True}
                    for k, v in (part.split("=", 1) for part in h["Cookie"].split("; "))])
                page = await context.new_page()
                await page.goto(BASE + "/new", wait_until="domcontentloaded", timeout=ctx.timeout * 1000)
                prepared = payload
                if payload is not None:
                    loop = asyncio.get_running_loop()
                    captured = loop.create_future()
                    expected_org = url.split("/organizations/", 1)[1].split("/", 1)[0]
                    async def intercept(route):
                        req = route.request
                        try:
                            segments = urlsplit(req.url).path.split("/")
                            if len(segments) != 7 or segments[3] != expected_org or req.method != "POST":
                                raise ValueError()
                            ui = req.post_data_json
                            if not isinstance(ui, dict) or not isinstance(ui.get("tools"), list) or not isinstance(ui.get("personalized_styles"), list):
                                raise ValueError()
                            merged = {**payload, "personalized_styles": ui["personalized_styles"]}
                            if not payload["tools"]:
                                merged["tools"] = ui["tools"]
                            if "tool_states" in ui:
                                merged["tool_states"] = ui["tool_states"]
                            if not captured.done():
                                captured.set_result(merged)
                        except Exception:
                            if not captured.done():
                                captured.set_exception(ValueError("Claude Web UI request capture failed"))
                        finally:
                            await route.abort()
                    await page.route("**/api/organizations/*/chat_conversations/*/completion*", intercept)
                    await page.locator("div[contenteditable='true']").first.fill(payload["prompt"])
                    await page.keyboard.press("Enter")
                    prepared = await captured
                    await page.close()
                    page = await context.new_page()
                    await page.goto(BASE + "/new", wait_until="domcontentloaded", timeout=ctx.timeout * 1000)
                filtered = {k: v for k, v in h.items() if k.lower() not in ("cookie", "origin", "referer") and not k.lower().startswith("sec-")}
                result = await page.evaluate("""async ({url,method,headers,payload}) => {
                    const r = await fetch(url,{method,headers,credentials:'include',redirect:'error',
                        ...(payload ? {body:JSON.stringify(payload)} : {})});
                    const reader=r.body?.getReader(); let size=0; const chunks=[];
                    try { while(reader) { const {value,done}=await reader.read(); if(done) break;
                        size+=value.length; if(size>16*1024*1024) throw Error('Response too large');
                        let s=''; for(let i=0;i<value.length;i+=32768) s+=String.fromCharCode(...value.subarray(i,i+32768));
                        chunks.push(btoa(s)); } }
                    finally { await reader?.cancel(); reader?.releaseLock(); }
                    return {status:r.status,headers:Object.fromEntries(r.headers),chunks};
                }""", {"url": url, "method": method, "headers": filtered, "payload": prepared})
                import base64
                response = httpx.Response(result["status"], headers=result["headers"],
                                          content=b"".join(base64.b64decode(p) for p in result["chunks"]))
                try:
                    yield response
                finally:
                    await close_response(response)
            finally:
                await browser.close()

    @asynccontextmanager
    async def _request(self, ctx, method, url, h, payload=None):
        fallback = options(ctx)[3]
        retry_browser = False
        async with self._direct(ctx, method, url, h, payload) as response:
            if 200 <= response.status_code < 300:
                yield response
                return
            body = await bounded_body(response)
            retry_browser = bool(challenge(response, body)) and fallback
            if not retry_browser:
                check_status(response, body)
        if retry_browser:
            async with self._browser(ctx, method, url, h, payload) as response:
                check_status(response, await bounded_body(response) if response.status_code >= 300 else b"")
                yield response

    async def _organization(self, ctx, h):
        async with self._request(ctx, "GET", API + "/organizations", h) as response:
            try:
                organizations = json.loads(await bounded_body(response, LIMIT))
            except ValueError:
                protocol("invalid organization response")
        ids = []
        if not isinstance(organizations, list):
            protocol("organizations must be an array")
        for org in organizations:
            identifier = org.get("uuid", org.get("id")) if isinstance(org, dict) else None
            if not isinstance(identifier, str) or not re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", identifier):
                protocol("invalid organization identifier")
            ids.append(identifier)
        wanted = ctx.credentials.get("orgId") or ctx.credentials.get("org_id")
        if wanted:
            if wanted not in ids:
                invalid("Configured orgId is not in the authenticated organization list")
            return wanted
        if not ids:
            protocol("authenticated account has no organizations")
        if len(set(ids)) != 1:
            invalid("Set orgId when the account does not have exactly one organization")
        return ids[0]

    async def validate_credentials(self, ctx):
        try:
            locale, _, device, _ = options(ctx)
            h = headers(cookie_header(ctx.credentials), locale, device)
            async with asyncio.timeout(ctx.timeout):
                await self._organization(ctx, h)
            return True, "Claude Web session verified; model catalog is static, not entitlement checked", len(MODELS)
        except asyncio.CancelledError:
            raise
        except RouterException as exc:
            return False, exc.message, 0
        except Exception:
            return False, "Claude Web validation connection failed", 0

    async def list_models(self, ctx):
        return [DiscoveredModelData(provider_model_id=m, display_name=m + " (Web)", context_length=None,
                    max_output_tokens=None, capabilities={"chat": True, "streaming": True, "vision": False,
                                                         "tools": "unknown", "reasoning": True}) for m in MODELS]

    async def chat_completions(self, request, ctx):
        return await collect_chat_completion(self.stream_chat(request, ctx), ctx.model_id or request.model, require_complete=True)

    async def stream_chat(self, request, ctx):
        model = ctx.model_id or request.model
        if model not in MODELS:
            invalid("Unknown Claude Web model; use an exact static catalog ID")
        locale, timezone, device, _ = options(ctx)
        payload = build_payload(request, model, locale, timezone)
        h = headers(cookie_header(ctx.credentials), locale, device)
        try:
            async with asyncio.timeout(ctx.timeout):
                organization = await self._organization(ctx, h)
                url = f"{API}/organizations/{organization}/chat_conversations/{uuid.uuid4()}/completion"
                async with self._request(ctx, "POST", url, h, payload) as response:
                    if "text/event-stream" not in response.headers.get("content-type", "").lower():
                        protocol("completion response is not SSE")
                    async with aclosing(body_bytes(response)) as source:
                        async with aclosing(translate(source, model, {t["name"] for t in payload["tools"]}, lambda: close_response(response))) as output:
                            async for part in output:
                                yield part
        except RouterException:
            raise
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            raise normalize_upstream_error(exception=TimeoutError()) from None
        except Exception as exc:
            if getattr(exc, "code", None) == 28 or type(exc).__name__ == "TimeoutError":
                raise normalize_upstream_error(exception=TimeoutError()) from None
            raise RouterException("Claude Web connection or stream decoding failed", ErrorCategory.NETWORK_ERROR,
                                  status_code=502) from None
