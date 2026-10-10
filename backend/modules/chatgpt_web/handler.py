"""Browser-owned common ChatGPT Web port. Upstream MIT attribution: see LICENSE.

No HTTP client, credential files, synthetic Sentinel tokens, or startup browser.
"""
import asyncio
import copy
import json
import math
import re
import time
import uuid
from contextlib import suppress
from pathlib import Path
from urllib.parse import unquote, urlsplit

from app.adapters.base import DiscoveredModelData
from app.core.errors import ErrorCategory, RouterException, normalize_upstream_error
from app.modules.base import BaseModuleAdapter, ChatStreamAccumulator, ModuleExecutionContext, collect_chat_completion
from app.schemas.chat import ChatCompletionRequest, ChatMessage

PAGE_URL = "https://chatgpt.com/?temporary-chat=true"
MAX_RESPONSE_BYTES = 16 * 1024 * 1024


def invalid(message):
    return RouterException("ChatGPT Web: " + message, ErrorCategory.INVALID_REQUEST)


def first_party(host):
    return isinstance(host, str) and any(host.lower().lstrip(".") == root or host.lower().lstrip(".").endswith("." + root)
                                         for root in ("chatgpt.com", "openai.com"))


def read_storage_state(credentials):
    raw = credentials.get("storage_state")
    if not raw:
        header = credentials.get("cookie")
        if not isinstance(header, str) or not header.strip():
            raise RouterException("ChatGPT Web requires browser storage_state JSON or a Cookie header", ErrorCategory.AUTH_ERROR)
        header = re.sub(r"^Cookie:\s*", "", header.strip(), flags=re.I)
        cookies = []
        for part in header.split(";"):
            name, sep, value = part.strip().partition("=")
            if not sep or not name or not value:
                raise RouterException("ChatGPT Web Cookie header is invalid", ErrorCategory.AUTH_ERROR)
            cookies.append(dict(name=name, value=value, domain=".chatgpt.com", path="/", expires=-1,
                                httpOnly=name.startswith(("__Secure-", "__Host-")), secure=True, sameSite="Lax"))
        if not any(re.fullmatch(r"__Secure-next-auth\.session-token(?:\.\d+)?", c["name"]) for c in cookies):
            raise RouterException("ChatGPT Web Cookie header is missing the session cookie", ErrorCategory.AUTH_ERROR)
        raw = {"cookies": cookies, "origins": []}
    try:
        state = json.loads(raw) if isinstance(raw, str) else copy.deepcopy(raw)
        if not isinstance(state, dict) or not isinstance(state.get("cookies"), list) or not isinstance(state.get("origins"), list):
            raise ValueError()
        for c in state["cookies"]:
            if not isinstance(c, dict) or not all(isinstance(c.get(k), str) for k in ("name", "value", "domain", "path")):
                raise ValueError()
            if not c["name"] or not first_party(c["domain"]) or not c["path"].startswith("/"):
                raise ValueError()
            if type(c.get("expires")) not in (int, float) or not math.isfinite(c["expires"]):
                raise ValueError()
            if type(c.get("httpOnly")) is not bool or type(c.get("secure")) is not bool or c.get("sameSite") not in ("Strict", "Lax", "None"):
                raise ValueError()
            if c["name"].startswith("__Host-"):
                c.update(domain=c["domain"].lstrip("."), path="/", secure=True)
        for origin in state["origins"]:
            url = urlsplit(origin["origin"])
            if url.scheme != "https" or not first_party(url.hostname) or not isinstance(origin.get("localStorage"), list):
                raise ValueError()
            if any(not isinstance(e, dict) or not isinstance(e.get("name"), str) or not isinstance(e.get("value"), str) for e in origin["localStorage"]):
                raise ValueError()
        return state
    except (ValueError, TypeError, KeyError, AttributeError):
        raise RouterException("ChatGPT Web browser storage state is invalid or contains foreign domains", ErrorCategory.AUTH_ERROR) from None


def playwright_proxy(raw):
    if not raw:
        return None
    try:
        url = urlsplit(raw)
        if url.scheme not in ("http", "https", "socks5") or not url.hostname or not url.port or url.path not in ("", "/") or url.query or url.fragment:
            raise ValueError()
        if url.scheme == "socks5" and url.username is not None:
            raise ValueError()  # Chromium does not support authenticated SOCKS proxies.
        host = f"[{url.hostname}]" if ":" in url.hostname else url.hostname
        result = {"server": f"{url.scheme}://{host}:{url.port}"}
        if url.username is not None:
            result.update(username=unquote(url.username), password=unquote(url.password or ""))
        return result
    except (ValueError, TypeError):
        raise invalid("unsupported proxy; use HTTP(S) or unauthenticated SOCKS5") from None


def prepare_request(request, model):
    # ponytail: text-only port; add uploads only with offline registration/SSRF tests.
    for key in ("temperature", "top_p", "stop", "max_tokens", "max_completion_tokens", "presence_penalty", "frequency_penalty",
                "logit_bias", "seed", "response_format", "thinking", "parallel_tool_calls"):
        if key == "thinking" and request.reasoning_effort is not None and "thinking" not in getattr(request, "_routing_client_fields", {"thinking"}):
            continue  # The router's companion budget is not a client web option.
        if getattr(request, key) is not None:
            raise invalid(f"{key} is unsupported by the browser path")
    if request.n not in (None, 1) or request.tools or request.tool_choice not in (None, "none"):
        raise invalid("multiple choices and tools are unsupported")
    if request.reasoning and set(request.reasoning) - {"effort"}:
        raise invalid("only reasoning.effort is supported")
    if request.stream_options and set(request.stream_options) - {"include_usage"}:
        raise invalid("unsupported stream_options")
    messages = []
    for message in request.messages:
        if message.role not in ("system", "developer", "user", "assistant") or message.tool_calls or message.tool_call_id:
            raise invalid("tool history is unsupported")
        if message.reasoning_details or message.reasoning_content:
            raise invalid("reasoning history is unsupported")
        text = message.content
        if isinstance(text, list):
            if any(p.get("type") not in ("text", "input_text") or not isinstance(p.get("text"), str) for p in text):
                raise invalid("attachments, audio, and other non-text content are unsupported")
            text = "".join(p["text"] for p in text)
        if not isinstance(text, str):
            raise invalid("messages require text content")
        messages.append((message.role, text))
    if not messages:
        raise invalid("messages are required")
    prompt = messages[0][1] if len(messages) == 1 and messages[0][0] == "user" else "\n\n".join(f"{role.capitalize()}:\n{text}" for role, text in messages)
    if not prompt.strip() or len(prompt.encode()) > 4 * 1024 * 1024:
        raise invalid("prompt must be nonempty and no larger than 4 MiB")
    normalized = re.sub(r"^(?:chatgpt-web|cgpt-web)/", "", model.strip().lower()).replace(".", "-")
    if normalized in ("gpt-5-6-luna-free", "gpt-5-6-luna-free-thinking"):
        selection = {"kind": "free", "thinkEnabled": normalized.endswith("-thinking")}
    else:
        base = "gpt-5-6" if normalized in ("gpt-5-6", "gpt-5-6-instant", "gpt-5-6-thinking", "gpt-5-6-sol", "gpt-5-6-pro") else "gpt-5-5"
        if normalized not in (base, base + "-instant", base + "-thinking", base + "-pro", "gpt-5-6-sol"):
            raise invalid("unsupported model")
        if normalized.endswith("-pro"):
            index = 4
        elif normalized.endswith("-instant") or normalized == "gpt-5-6":
            index = 0
        else:
            effort = request.get_effective_reasoning_effort()
            effort = effort.lower() if isinstance(effort, str) else "medium"
            indexes = {"none": 0, "off": 0, "minimal": 0, "low": 0, "medium": 1, "high": 2, "xhigh": 3, "max": 3}
            if effort not in indexes:
                raise invalid("unsupported reasoning effort")
            index = indexes[effort]
        selection = {"kind": "picker", "modelLabel": "GPT-5.6 Sol" if base == "gpt-5-6" else "GPT-5.5", "effortIndex": index}
    return prompt, selection


class ChatGPTResponseDecoder:
    """Bounded snapshot/delta decoder shared by buffered and live SSE paths."""
    def __init__(self):
        self.document = self.last_path = self.last_op = self.message_id = None
        self.buffer, self.event, self.data = "", "message", []
        self.text, self.latest, self.size = "", None, 0

    @property
    def complete(self):
        return self.latest is not None

    def _safe(self, value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in ("__proto__", "constructor", "prototype"):
                    raise ValueError()
                self._safe(item)
        elif isinstance(value, list):
            for item in value:
                self._safe(item)

    def _append(self, current, value):
        if current is None:
            return value
        if isinstance(current, str) and isinstance(value, str):
            return current + value
        if isinstance(current, list):
            return current + (value if isinstance(value, list) else [value])
        if isinstance(current, dict) and isinstance(value, dict):
            return {**current, **value}
        raise ValueError()

    def _apply(self, path, op, value):
        self._safe(value)
        if not isinstance(path, str) or op not in ("add", "replace", "append", "patch"):
            raise ValueError()
        if path == "":
            if op == "patch":
                if not isinstance(value, list):
                    raise ValueError()
                for entry in value:
                    self._apply(entry["p"], entry["o"], entry.get("v"))
            else:
                self.document = self._append(self.document, value) if op == "append" else value
            return
        if not path.startswith("/") or op == "patch":
            raise ValueError()
        parts = [p.replace("~1", "/").replace("~0", "~") for p in path[1:].split("/")]
        if any(p in ("__proto__", "constructor", "prototype") for p in parts):
            raise ValueError()
        parent = self.document
        for part in parts[:-1]:
            parent = parent[self._array_index(part, len(parent), False)] if isinstance(parent, list) else parent[part]
        key = parts[-1]
        if isinstance(parent, list):
            index = self._array_index(key, len(parent), op == "add")
            if op == "add":
                parent.insert(index, value)
            else:
                parent[index] = self._append(parent[index], value) if op == "append" else value
        elif isinstance(parent, dict):
            if op != "add" and key not in parent:
                raise ValueError()
            parent[key] = self._append(parent[key], value) if op == "append" else value
        else:
            raise ValueError()

    def _array_index(self, part, length, allow_end):
        if part == "-" and allow_end:
            return length
        if not re.fullmatch(r"0|[1-9]\d*", part):
            raise ValueError()
        index = int(part)
        if index >= length + int(allow_end):
            raise ValueError()
        return index

    def _observe(self):
        bound = self.message_id is not None or bool(self.text) or self.complete
        message = self.document.get("message") if isinstance(self.document, dict) else None
        if not isinstance(message, dict):
            if bound:
                raise ValueError("Assistant document was removed")
            return ""
        content = message.get("content") or {}
        # ponytail: legacy snapshots omit channel; reject later reclassification.
        channel = message.get("channel") or (message.get("metadata") or {}).get("channel")
        if (message.get("author", {}).get("role") != "assistant"
                or content.get("content_type") != "text" or channel not in (None, "final")):
            if bound:
                raise ValueError("Assistant eligibility changed")
            return ""
        parts = content.get("parts")
        if not isinstance(parts, list) or any(not isinstance(p, str) for p in parts):
            raise ValueError()
        identity = message.get("id")
        if self.message_id is not None and identity != self.message_id:
            raise ValueError("Assistant identity changed")
        if identity is not None:
            self.message_id = identity
        text = "".join(parts)
        if not text.startswith(self.text) or self.complete and text != self.latest:
            raise ValueError("Assistant text was rewritten")
        delta, self.text = text[len(self.text):], text
        if message.get("status") == "finished_successfully" and message.get("end_turn") is True:
            self.latest = text
        elif self.complete:
            raise ValueError("Assistant completion was revoked")
        return delta

    def _event(self):
        raw, event = "\n".join(self.data), self.event
        self.data, self.event = [], "message"
        if not raw or raw == "[DONE]":
            return ""
        value = json.loads(raw)
        if isinstance(value, dict) and value.get("error"):
            raise ValueError("Upstream stream error")
        if event == "delta_encoding":
            if value != "v1" or self.text:
                raise ValueError()
            self.document, self.last_path, self.last_op = None, None, None
        elif event == "delta":
            self.last_path = value.get("p", self.last_path)
            self.last_op = value.get("o", self.last_op)
            self._apply(self.last_path, self.last_op, value.get("v"))
        elif isinstance(value, dict) and "message" in value:
            self._safe(value)
            self.document = value
        return self._observe()

    def feed(self, chunk):
        if not isinstance(chunk, str):
            raise RouterException("ChatGPT Web stream chunk is invalid", ErrorCategory.UPSTREAM_5XX)
        self.size += len(chunk.encode())
        if self.size > MAX_RESPONSE_BYTES:
            raise RouterException("ChatGPT Web response is oversized", ErrorCategory.UPSTREAM_5XX)
        self.buffer += chunk
        deltas = []
        try:
            # Keep a trailing CR until the next chunk to handle fragmented CRLF.
            while match := re.search(r"\r\n|\r(?!$)|\n", self.buffer):
                line, self.buffer = self.buffer[:match.start()], self.buffer[match.end():]
                if not line:
                    delta = self._event()
                    if delta:
                        deltas.append(delta)
                    continue
                key, _, value = line.partition(":")
                value = value[1:] if value.startswith(" ") else value
                if key == "event":
                    self.event = value or "message"
                elif key == "data":
                    self.data.append(value)
            return deltas
        except (ValueError, KeyError, TypeError, IndexError, AttributeError, RecursionError):
            self.latest = None
            raise RouterException("ChatGPT Web assistant stream is inconsistent or unsupported", ErrorCategory.UPSTREAM_5XX) from None

    def finish(self):
        self.feed("\n\n")
        if not self.complete:
            raise RouterException("ChatGPT Web assistant document is incomplete or unsupported", ErrorCategory.UPSTREAM_5XX)
        return self.latest


def parse_response(sse):
    decoder = ChatGPTResponseDecoder()
    decoder.feed(sse)
    return decoder.finish()


# Derived from chatgptWebFirstParty.ts at 61e07fb7e0d4e1e76111495d3718c9e4d06d2a62.
# Only the real page module produces challenge artifacts; no Python HTTP path.
BROWSER_TURN = r'''async ({prompt, selection}) => {
  if (location.origin !== 'https://chatgpt.com') throw new Error('first-party origin required');
  const assetPattern = /^\/(?:cdn|unauth-mweb|auth-mweb)\/(?:assets|scripts)\/[A-Za-z0-9._-]+\.js$/;
  const valid = value => { try { const u = new URL(value); return u.origin === location.origin && assetPattern.test(u.pathname); } catch { return false; } };
  const queue = [], seen = new Set(), symbols = {}, assets = {};
  const exported = (source, name) => {
    if (!name) return null;
    const block = source.slice(source.lastIndexOf('export{') + 7);
    return block.match(new RegExp('(?:^|,)' + name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ' as ([A-Za-z_$][\\w$]*)'))?.[1] || name;
  };
  const deadline = Date.now() + 15000;
  let resolver = null;
  while (Date.now() <= deadline && seen.size < 512) {
    queue.push(...performance.getEntriesByType('resource').map(e => e.name),
               ...Array.from(document.querySelectorAll('link[rel="modulepreload"][href]'), e => e.href));
    while (queue.length && seen.size < 512) {
      const url = queue.shift();
      if (!valid(url) || seen.has(url)) continue;
      seen.add(url);
      const response = await fetch(url, {signal: AbortSignal.timeout(20000)});
      if (!response.ok) continue;
      const source = await response.text();
      if (new TextEncoder().encode(source).length > 24 * 1024 * 1024) throw new Error('asset size limit');
      const enforcement = source.match(/Promise\.all\(\[([A-Za-z_$][\w$]*)\.getEnforcementToken\(t,\{forceSync:!0\}\),([A-Za-z_$][\w$]*)\.getEnforcementToken\(t\)\]\)/);
      const local = {
        finalizeRequirements: source.match(/function ([A-Za-z_$][\w$]*)\(e=!1,t=`none`(?:,n=[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)?)?\)\{return [A-Za-z_$][\w$]*\(`finalized`,e,t(?:,n)?\)\}/)?.[1] || source.match(/finalizeChatRequirements\s*:\s*\(\)\s*=>\s*([A-Za-z_$][\w$]*)/)?.[1],
        proofManager: enforcement?.[1] || source.match(/([A-Za-z_$][\w$]*)\.getEnforcementToken\([^)]*forceSync\s*:\s*!0/)?.[1], turnstileManager: enforcement?.[2],
        requestClient: source.match(/([A-Za-z_$][\w$]*)\.(?:safePost|post)\([`"]\/sentinel\/chat-requirements\/prepare[`"]/)?.[1],
        buildSentinelHeaders: source.match(/function ([A-Za-z_$][\w$]*)\(e,t,n,r,i,a\)\{let o=\{\};return e\?\.token\?o\[`OpenAI-Sentinel-Chat-Requirements-Token`\]/)?.[1]
      };
      for (const [key, name] of Object.entries(local)) if (name && !symbols[key]) {symbols[key] = exported(source, name); assets[key] = url;}
      const integrity = source.match(/(?:^|\}\),)([A-Za-z0-9_$]+):\(function\(e,t,n\)\{n\.d\(t,\{([^}]+)\}\);[\s\S]{0,1800}?async function ([A-Za-z_$][\w$]*)\(e\)\{let t=[A-Za-z_$][\w$]*\(\),n=[A-Za-z_$][\w$]*\(await e\(t\)\)/);
      if (integrity) {
        const name = integrity[2].match(new RegExp('(?:^|,)\\s*([A-Za-z_$][\\w$]*):\\(\\)=>' + integrity[3] + '(?:,|$)'))?.[1];
        if (name) resolver = {url, id: integrity[1], name};
      }
      if (resolver || ['finalizeRequirements','proofManager','turnstileManager','requestClient','buildSentinelHeaders'].every(k => symbols[k])) break;
      for (const match of source.matchAll(/["']\.\/([A-Za-z0-9_-]+\.js)["']/g)) queue.push(new URL('./' + match[1], url).href);
    }
    if (resolver || ['finalizeRequirements','proofManager','turnstileManager','requestClient','buildSentinelHeaders'].every(k => symbols[k])) break;
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  // Native first-party imports; fail closed if deployment contract changes.
  let client, headers;
  const controller = new AbortController();
  window.__myairouterChatGPTAbort = controller;
  try {
    // Server evidence, not cookie/composer presence; never follow an auth redirect.
    const sessionResponse = await fetch('/api/auth/session', {credentials:'include',cache:'no-store',redirect:'error',
      headers:{Accept:'application/json'},signal:controller.signal});
    if (!sessionResponse.ok) {await sessionResponse.body?.cancel(); return {status:sessionResponse.status};}
    if (!sessionResponse.headers.get('content-type')?.includes('application/json')) throw new Error('invalid session response');
    const session = await sessionResponse.json();
    const user = session?.user;
    if (!user || typeof user !== 'object' || Array.isArray(user) || !Object.keys(user).length ||
        ![undefined,null,''].includes(session.error) ||
        session.expires != null && (typeof session.expires !== 'string' || !Number.isFinite(Date.parse(session.expires)) || Date.parse(session.expires) <= Date.now())) {
      return {status:401};
    }
    if (resolver) {
      const upstream = await import(resolver.url), exports = {};
      const factory = upstream.__webpack_modules__?.[resolver.id];
      if (typeof factory !== 'function') throw new Error('integrity module unavailable');
      const requireShim = id => { if (id === 'TI') return {a: () => crypto.randomUUID()}; throw new Error('unsupported integrity dependency'); };
      requireShim.d = (target, definitions) => {for (const [name, getter] of Object.entries(definitions)) Object.defineProperty(target, name, {enumerable:true, get:getter});};
      factory({}, exports, requireShim);
      client = {safePost: async (path, options={}) => {
        const headers = new Headers(options.additionalHeaders || {});
        if (typeof session?.accessToken === 'string' && session.accessToken) headers.set('Authorization','Bearer ' + session.accessToken);
        headers.set('Accept','application/json'); headers.set('Content-Type','application/json');
        const response = await fetch('/backend-api' + path, {method:'POST',credentials:'include',headers,
          body:JSON.stringify(options.requestBody || {}),signal:controller.signal});
        if (options.skipJsonTransform) return response;
        if (!response.ok) throw new Error('request status ' + response.status);
        return response.json();
      }};
      const integrity = await exports[resolver.name](proof => client.safePost('/sentinel/chat-requirements/prepare', {requestBody:{p:proof}}));
      headers = integrity?.headers || {};
    } else {
      const bridge = {};
      for (const key of ['finalizeRequirements','proofManager','turnstileManager','requestClient','buildSentinelHeaders']) {
        if (!symbols[key]) throw new Error('first-party module contract unavailable');
        bridge[key] = (await import(assets[key]))[symbols[key]];
      }
      if (typeof bridge.finalizeRequirements !== 'function' || typeof bridge.proofManager?.getEnforcementToken !== 'function' ||
          typeof bridge.turnstileManager?.getEnforcementToken !== 'function' || typeof bridge.requestClient?.safePost !== 'function' ||
          typeof bridge.buildSentinelHeaders !== 'function') throw new Error('first-party bridge incomplete');
      const requirements = await bridge.finalizeRequirements(false, 'none');
      const [proof, turnstile] = await Promise.all([bridge.proofManager.getEnforcementToken(requirements,{forceSync:true}), bridge.turnstileManager.getEnforcementToken(requirements)]);
      headers = bridge.buildSentinelHeaders(requirements,turnstile,proof,null,null,null);
      client = bridge.requestClient;
    }
    const base = selection.kind === 'free' ? 'auto' : selection.modelLabel === 'GPT-5.6 Sol' ? 'gpt-5-6' : 'gpt-5-5';
    const model = selection.kind === 'picker' && selection.effortIndex === 4 ? base + '-pro' : base;
    const reason = selection.kind === 'free' ? selection.thinkEnabled : selection.effortIndex > 0 && selection.effortIndex !== 4;
    // Await the request owner's fence BEFORE touching the physical Send path.
    await window.__myairouterChatGPTEvent({type:'send_activated'});
    const response = await client.safePost('/f/conversation', {
      requestBody: {action:'next',messages:[{id:crypto.randomUUID(),author:{role:'user'},create_time:Date.now()/1000,
        content:{content_type:'text',parts:[prompt]},metadata:{...(reason ? {system_hints:['reason']} : {}),serialization_metadata:{custom_symbol_offsets:[]}}}],
        parent_message_id:'client-created-root',model,timezone_offset_min:new Date().getTimezoneOffset(),timezone:Intl.DateTimeFormat().resolvedOptions().timeZone,
        history_and_training_disabled:true,conversation_mode:{kind:'primary_assistant'},system_hints:reason ? ['reason'] : [],supports_buffering:true,supported_encodings:['v1']},
      additionalHeaders:headers,signal:controller.signal,skipJsonTransform:true
    });
    if (!(response instanceof Response)) throw new Error('invalid conversation response');
    if (!response.ok) {await response.body?.cancel(); return {status:response.status};}
    if (!response.headers.get('content-type')?.includes('text/event-stream')) throw new Error('unsupported conversation transport');
    await window.__myairouterChatGPTEvent({type:'accepted'});
    const reader = response.body?.getReader();
    if (!reader) throw new Error('empty conversation response');
    const decoder = new TextDecoder(); let total = 0;
    try {
      for (;;) {const {done,value} = await reader.read(); if(done) break; if(!value) continue;
        total += value.byteLength; if(total > 16*1024*1024) {await reader.cancel(); throw new Error('response size limit');}
        await window.__myairouterChatGPTEvent({type:'chunk',text:decoder.decode(value,{stream:true})});}
      const tail = decoder.decode();
      if (tail) await window.__myairouterChatGPTEvent({type:'chunk',text:tail});
    } finally {reader.releaseLock();}
    return {finished:true};
  } finally {delete window.__myairouterChatGPTAbort;}
}'''


def _playwright():
    from playwright.async_api import async_playwright
    return async_playwright()


class ChatGPTWebAdapter(BaseModuleAdapter):
    async def validate_credentials(self, ctx):
        try:
            read_storage_state(ctx.credentials)
            playwright_proxy(ctx.proxy_url)
            return True, "Browser credential format valid; login and model access not checked (offline validation)", 8
        except RouterException as error:
            return False, str(error), 0

    async def list_models(self, ctx):
        manifest = json.loads(Path(__file__).with_name("manifest.json").read_text())
        return [DiscoveredModelData(provider_model_id=m["id"], display_name=m["name"], capabilities=m["capabilities"])
                for m in manifest["default_models"]]

    async def _turn(self, prompt, selection, state, ctx, *, on_text=None, on_send=None):
        manager, browser, context = None, None, None
        decoder, sent, accepted = ChatGPTResponseDecoder(), False, False
        bindings, closing = set(), False

        async def deliver(text):
            if on_text:
                for offset in range(0, len(text), 4096):
                    await on_text(text[offset:offset + 4096])

        def fenced(error):
            if sent:
                error.replay_safe = False
                error.message += "; automatic resend is disabled because the prompt may already have been accepted"
            return error

        try:
            async with asyncio.timeout(ctx.timeout):
                manager = await _playwright().start()
                launch = {"headless": False}
                if ctx.credentials.get("chrome_executable_path"):
                    launch["executable_path"] = ctx.credentials["chrome_executable_path"]
                proxy = playwright_proxy(ctx.proxy_url)
                if proxy:
                    launch["proxy"] = proxy
                browser = await manager.chromium.launch(**launch)
                context = await browser.new_context(storage_state=state, locale=ctx.credentials.get("locale") or "en-US",
                                                    timezone_id=ctx.credentials.get("timezone") or "America/New_York")
                page = await context.new_page()

                async def event(source, payload):
                    nonlocal sent, accepted
                    task = asyncio.current_task()
                    bindings.add(task)
                    try:
                        if closing or source["page"] is not page or source["frame"] is not page.main_frame:
                            raise invalid("foreign or closed browser event")
                        kind = payload.get("type") if isinstance(payload, dict) else None
                        if kind == "send_activated" and not sent:
                            sent = True
                            if on_send:
                                on_send()
                        elif kind == "accepted" and sent and not accepted:
                            accepted = True
                        elif kind == "chunk" and accepted:
                            for delta in decoder.feed(payload.get("text")):
                                await deliver(delta)
                        else:
                            raise invalid("unexpected browser event")
                    finally:
                        bindings.discard(task)

                await page.expose_binding("__myairouterChatGPTEvent", event)
                await page.goto(PAGE_URL, wait_until="domcontentloaded", timeout=min(ctx.timeout * 1000, 30000))
                if urlsplit(page.url).scheme != "https" or urlsplit(page.url).netloc != "chatgpt.com":
                    raise RouterException("ChatGPT Web browser is not logged in at the first-party origin", ErrorCategory.AUTH_ERROR)
                result = await page.evaluate(BROWSER_TURN, {"prompt": prompt, "selection": selection})
                if result.get("status"):
                    raise normalize_upstream_error(status_code=result["status"], response_body={"message": "ChatGPT Web conversation or session rejected"})
                if not accepted or result.get("finished") is not True:
                    raise RouterException("ChatGPT Web browser stream did not finish", ErrorCategory.UPSTREAM_5XX)
                before = decoder.text
                text = decoder.finish()
                await deliver(text[len(before):])
                return text
        except RouterException as error:
            raise fenced(error)
        except TimeoutError as error:
            raise fenced(normalize_upstream_error(exception=error)) from None
        except Exception as error:
            # Classify only safe signals; never expose auth-bearing browser diagnostics.
            if type(error).__name__ == "TimeoutError":
                raise fenced(normalize_upstream_error(exception=TimeoutError())) from None
            detail = str(error)
            status = re.search(r"\b(?:status|HTTP)[_\s-]*(401|403|429|5\d\d)\b", detail, re.I)
            if status or re.search(r"rate[-_\s]?limit|quota\s+(?:exhausted|reached|exceeded)", detail, re.I):
                raise fenced(normalize_upstream_error(status_code=int(status[1]) if status else 429,
                                               response_body={"message": "ChatGPT Web first-party request rejected"})) from None
            raise fenced(RouterException("ChatGPT Web browser execution failed; check browser installation, display, login, and first-party module compatibility", ErrorCategory.UPSTREAM_5XX)) from None
        finally:
            closing = True
            # Playwright bindings run in separate tasks; a full queue must not orphan them.
            for task in tuple(bindings):
                task.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await task
            # Close the context to abort in-page requests even if evaluate was cancelled.
            for resource, method in ((context, "close"), (browser, "close"), (manager, "stop")):
                if resource is not None:
                    with suppress(asyncio.CancelledError, Exception):
                        await asyncio.wait_for(getattr(resource, method)(), 5)

    async def stream_chat(self, request: ChatCompletionRequest, ctx: ModuleExecutionContext):
        model = ctx.model_id or request.model
        prompt, selection = prepare_request(request, model)
        state = read_storage_state(ctx.credentials)
        if not math.isfinite(ctx.timeout) or ctx.timeout <= 0:
            raise invalid("timeout must be finite and positive")
        queue = asyncio.Queue(maxsize=16)
        def on_send():
            # Dispatch deadline can cancel the task before this adapter emits text.
            object.__setattr__(request, "_upstream_submission_started", True)
        producer = asyncio.create_task(self._turn(prompt, selection, state, ctx, on_text=queue.put, on_send=on_send))
        metadata = {"id": "chatcmpl-" + uuid.uuid4().hex, "object": "chat.completion.chunk", "created": int(time.time()), "model": model}
        size, started, pending = 0, False, None
        def frame(delta, finish=None):
            nonlocal size
            chunk = "data: " + json.dumps({**metadata, "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}, ensure_ascii=False) + "\n\n"
            size += len(chunk.encode())
            if size + len("data: [DONE]\n\n") > ChatStreamAccumulator.MAX_BYTES:
                raise RouterException("ChatGPT Web completion exceeds the shared assembly limit", ErrorCategory.UPSTREAM_5XX)
            return chunk
        try:
            while True:
                pending = asyncio.create_task(queue.get())
                done, _ = await asyncio.wait((pending, producer), return_when=asyncio.FIRST_COMPLETED)
                if pending in done:
                    text = pending.result()
                else:
                    pending.cancel()
                    with suppress(asyncio.CancelledError):
                        await pending
                    if queue.empty():
                        break
                    text = queue.get_nowait()
                if not started:
                    yield frame({"role": "assistant"})
                    started = True
                yield frame({"content": text})
            await producer  # Propagate producer errors; never emit a false terminal.
            if not started:
                yield frame({"role": "assistant"})
            yield frame({}, "stop")
            yield "data: [DONE]\n\n"
        except RouterException as error:
            if getattr(request, "_upstream_submission_started", False):
                error.replay_safe = False
            raise
        finally:
            for task in (pending, producer):
                if task is not None:
                    if not task.done():
                        task.cancel()
                    with suppress(asyncio.CancelledError, Exception):
                        await task

    async def chat_completions(self, request, ctx):
        return await collect_chat_completion(self.stream_chat(request, ctx), ctx.model_id or request.model, require_complete=True)
