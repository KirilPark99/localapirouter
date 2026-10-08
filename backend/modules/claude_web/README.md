# Claude Web (OmniRoute port)

Derived from OmniRoute commit `61e07fb7e0d4e1e76111495d3718c9e4d06d2a62`.
The upstream MIT copyright/permission notice is preserved in `LICENSE`.
This is an unofficial, account-session provider, not the Anthropic API.
Only offline synthetic transport/browser checks have been run; live availability,
account entitlements, browser challenge passage and UI selectors are not verified.

## Profile

Use the generic **Claude Web** custom-module profile:

- `cookie`: full Cookie header containing exactly one `sessionKey`, or its bare
  value. Programmatic credentials also accept `sessionKey` / `session_key` and
  the generic adapter's `api_key` alias. Cookies are password fields, encrypted
  through the existing profile mechanism; never paste credentials into logs.
- `orgId`: optional organization UUID. Every request validates membership against
  the authenticated organization list. Without it, exactly one organization must
  exist: the module never guesses the first organization of a multi-org account.
- `deviceId`: optional Anthropic browser device ID (password field).
- `locale`: language tag, default `en-US`.
- `timezone`: IANA zone name, default `UTC`.
- `browser_fallback`: default `false`. Opt-in only for a recognized Cloudflare
  403 challenge, not arbitrary authentication failures, rate limits or 5xx.

The router-provided proxy and positive finite request timeout are used, including
organization lookup. Environment proxies and redirects are disabled on the direct
path. Credential validation only lists organizations; it does not send a chat.
Model listing is entirely local/static and does not validate account access.
Install the backend's optional `web` dependencies (`curl-cffi`, `playwright`);
Chromium is needed only for enabled browser fallback.

## Request and response behavior

- Native async `curl_cffi` Chrome TLS impersonation is the default. Its own Chrome
  profile supplies UA/client hints; the upstream's mismatched hard-coded Chrome
  149 UA / Chrome 146 TLS pair is intentionally not copied.
- Each chat creates a fresh UUID via the reference's completion endpoint and
  exact `create_conversation_params`, message UUIDs, normal style, rendering,
  effort/thinking, empty attachment/file/source fields. No separate create call.
- All caller history is retained. Multi-message requests use the reference's
  explicit recovery-prompt disclaimer and escaped role blocks, with each entire
  supported message serialized as JSON. System/developer instructions, tool IDs,
  names, arguments/results and plaintext reasoning are not silently dropped.
  **This is prompt recovery, not native continuation or native tool-result replay.**
  It costs context and lacks the original server-side conversation identity.
- Text messages (strings or plain `text` parts), streaming/nonstreaming, reasoning
  text/summary and reasoning signatures are translated. Caller function tools
  become native tool definitions; declared `tool_use` blocks become OpenAI tool
  calls after their JSON object arguments validate. Tool support is account/model
  dependent and therefore advertised as `unknown`, not guaranteed.
- Efforts: `none`, `low`, `medium`, `high`, `xhigh`, `max`; plain
  `thinking: {"type":"enabled"}` means `low`. Opus 5 follows the reference's
  `thinking_mode:auto` / default `high` behavior, even for requested `none`.
- Strict SSE handles UTF-8 split boundaries, LF/CRLF and multiline data. Unknown
  events/blocks, mismatched block deltas, malformed tool JSON, retractions and
  premature EOF fail instead of returning successful truncated answers.
  `message_stop` closes upstream immediately; there is exactly one finish and
  `[DONE]` on successful streams. **No idle timer manufactures tool completion**:
  a held-open tool stream eventually times out instead of committing false success.
- Reasoning signatures are retained in `reasoning_details`; replay of signed or
  opaque history is explicitly rejected, since recovery cannot preserve its native
  semantics. Opaque tool `extra_content`, cache metadata and tool-result error
  metadata are likewise rejected before sending a request.
- Known metadata events have bounded allowlisted fields in the streaming
  `claude_web.event` extension. The shared nonstream collector has no provider
  extension field, so those informational events are not returned nonstreaming.
  Usage stays `null`/absent: partial web usage is not treated as authoritative
  billable token counts, and no estimates/zero placeholders are fabricated.
- HTTP/SSE auth, rate and provider errors use existing router normalization;
  numeric bounded Retry-After values are retained. Upstream error bodies and
  transport exception text are not exposed (may contain credentials). All stream,
  response, TLS session and browser resources close on completion, failure,
  cancellation or timeout.

## Optional browser path

Only after an opted-in recognized challenge, Playwright starts a fresh headless
Chromium and ephemeral cookie context using the same proxy, locale and timezone.
No real browser profile, persistent cookie store, account file or database is read.
For a completion it intercepts and aborts the authenticated UI request, captures
its account styles/tools/tool states, then closes that page before sending the
prepared completion in a second page in the same context. Explicit caller tools
win; prepared conversation/model/UUID/reasoning fields always win. Browser cookies
are never exported back into curl. There are no challenge-solving algorithms,
stealth patches or manufactured anti-bot cookies. A challenge may still fail.

Browser responses are bounded to 16 MiB and buffered before OpenAI streaming;
**fallback is not low-latency streaming**. Resources are per request, not pooled.
Account-native browser tools without caller-declared names cannot be represented
as client tool calls and fail closed if emitted. Browser fallback is optional,
selector-sensitive and mock-tested only; it is not a promised anti-bot bypass.

## Deliberate limits

No vision/uploads, native existing-conversation/retry linking, quota discovery,
custom styles on the direct path or persistent conversation cache. The top-level
OmniRoute `claude_web` extension (conversation/parent UUID, operation, tool states)
is not part of MyAIrouter's `ChatCompletionRequest`; this port does not claim it
works through that schema. Do not use it: the shared schema ignores unknown fields.
Native retry/linking would require an explicit shared-schema/API change first.
Unsupported representable generation options are rejected: token caps, sampling,
stop/seed/penalties/bias, response format, parallel tool calls, non-auto tool choice,
strict tool schemas, reasoning token budgets, multiple choices and cache keys.
No model context/output limits are invented. Ten model IDs are copied from the
reference's actual registry (its accompanying seven-model documentation is stale):

```
claude-fable-5-1
claude-fable-5
claude-opus-5
claude-opus-4-8
claude-opus-4-7
claude-opus-4-6
claude-sonnet-5
claude-sonnet-5-5
claude-sonnet-4-6
claude-haiku-4-5-20251001
```

## Offline regressions

From `backend/`, with the optional `web` and `dev` dependencies installed:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest --noconftest -p no:cacheprovider -q tests/test_claude_web_offline.py
```

The handler-only tests initialize real synthetic Settings without reading dotenv,
and block sockets, native curl requests and provider browser launches. They do
not create profiles or connect a database. Do not run ordinary app fixtures.
Router-generated companion thinking budgets do not override the chosen effort;
explicit unsupported client budgets still fail.
