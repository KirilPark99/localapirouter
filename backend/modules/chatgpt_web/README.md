# ChatGPT Web (Browser)

Common clean-room ChatGPT Web port from OmniRoute commit
`61e07fb7e0d4e1e76111495d3718c9e4d06d2a62`, under its MIT license (preserved in `LICENSE`).
Reference: `chatgpt-web.ts`, `chatgptWebExecutorAdapter.ts`,
`chatgptWebBrowserSession.ts`, `chatgptWebFirstParty.ts`,
`chatgptWebDeltaV1.ts`, `chatgptWebTransport.ts`, `chatgptWebAttachments.ts`,
and the common provider registry. This is **not** the Codex variant.
The reference's `CHATGPT_WEB.md` retirement notice does not describe this executor.
Session verification and submission guards selectively adapt the behavior of
`codex-chatgpt-web` v6.1.7 / `f9ad4ae` (MIT notice also preserved in `LICENSE`);
its Codex/Electron/MCP runtime is not imported.

## Credentials and runtime

Paste **either** first-party Playwright `storage_state` JSON (with `cookies` and
`origins`) **or** the browser Cookie header containing
`__Secure-next-auth.session-token` (chunked cookies also accepted) into the generic
module credential form. Both fields are encrypted password fields. No account or
profile is created by this module. No cookie/auth files are read. Storage state is
passed as an in-memory object, never a filesystem path; foreign domains are rejected.

Playwright is imported only when an actual completion is requested. Install its
Chromium runtime or supply `chrome_executable_path`. The reference uses headed
Chromium; a working desktop display/Xvfb is therefore required. Every request owns
an isolated browser/context, closed on success, error, timeout, or cancellation.
There is no persistent browser pool or credential-state writeback.
Configured HTTP(S) and unauthenticated SOCKS5 proxies are honored; authenticated
SOCKS and other schemes fail explicitly rather than silently bypassing the proxy.
Router `ctx.timeout` bounds the whole turn (plus bounded resource cleanup).

**Credential validation is local format validation only**: successful validation
explicitly says login/model access were not checked. Model discovery returns the
reference's static eight routes, not a claim that an account can access them.
There are no automatic login, captcha-solving, quota, or subscription-reset calls.
An actual completion verifies `/api/auth/session` inside its assigned browser/proxy
before sending: redirects, non-JSON, empty user, session errors and expired sessions
fail closed. This does not check model entitlement and does not open a login URL.

The browser awaits a request-bound Send fence before `/f/conversation`. From that
point, errors and dispatch timeouts disable automatic retry and fallback, even
before any client chunk appears. A successful HTTP response is acceptance evidence,
not completion; ambiguous failures are deliberately not resent. Explicit new user
requests remain possible. Disconnect/cancellation closes only the owned request's
browser/context and cancels blocked binding tasks; server-side stopping is not guaranteed.

## Intentional limitations

* Text messages only. System/developer/user/assistant history is flattened with
  role labels into a fresh temporary conversation, exactly as the common adapter;
  system messages are not native privileged instructions. Tools, tool history,
  reasoning history, attachments/images/files/audio, structured output, sampling,
  token limits, and multiple choices are rejected explicitly, not silently dropped.
* Incremental SSE: browser chunks cross an awaited Playwright binding into a
  bounded queue, with stable assistant-text prefixes emitted during generation.
  Assistant identity changes, text rewrites and explicit stream errors fail closed;
  explicit analysis-channel text is ignored before final-answer binding; later
  reclassification fails. Legacy channel-less snapshots retain their existing
  final-text interpretation; streamed prefixes cannot be retracted. Success requires
  `status=finished_successfully` and `end_turn=true`; `[DONE]` alone is not success.
  A failure after partial text never emits a successful finish. Usage is unknown
  in this module (the outer router may estimate it). Upstream response is bounded
  to 16 MiB and assembled OpenAI output to the shared collector's 8 MiB limit.
* Direct snapshots and `delta_encoding: v1` are supported. WebSocket-only
  handoff, tool-result rendered-text fallback, and unknown encodings fail closed.
* Exact common model selection mappings are retained, including Free Luna Think,
  GPT-5.6 Sol/GPT-5.5 Instant/Thinking/Pro, aliases and effort indexes. Pro is not
  max effort. **The current reference hot path does not use the composer or picker**:
  it imports the real loaded first-party module and submits through that module.
  As in its `directModel`, nonzero non-Pro efforts become the page's `reason` hint;
  distinct low/medium/high/xhigh execution budgets are not guaranteed.
* Real browser modules own session auth and Sentinel/Turnstile/proof production.
  The page discovers semantic module exports and uses its first-party challenge
  functions (including the reference integrity-module resolver). No offline
  substitute, hardcoded proof, Sentinel token, or Python HTTP auth request exists.
  Changes to upstream module exports/CSP can break this private integration;
  contract failures are errors, not fabricated completions. Resource discovery is
  bounded; browser pooling, global module caches and stealth engines are omitted.
* `stream_options.include_usage` is accepted but no unavailable usage is invented.
  Client metadata/user/cache hints are not sent to the browser provider.

## Offline verification

No live provider access is required or claimed. The regression uses synthetic
storage state and a fake Playwright runtime, blocks socket connections, disables
repo dotenv, isolates required Settings, and uses a unique synthetic DB path
without creating a database. It covers selection/history, credential/proxy
validation, terminal snapshot/delta decoding, shared completion collection,
provider rejection, timeout, cancellation, full-queue cleanup, live delivery before
completion, fragmented CRLF/Unicode, rewrite/identity errors and browser cleanup.
With Node available,
it also compiles the unchanged embedded JavaScript and executes eight synthetic
legacy/integrity-resolver turns against fake page resources, module imports and
fetch; no browser or real network participates.

From `backend/`, with the optional `web` and `dev` dependencies installed:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest --noconftest -p no:cacheprovider -q tests/test_chatgpt_web_offline.py
```

The regression uses Python Playwright's `page.url` property (not the TypeScript
`page.url()` method), and covers module discovery plus both bridge transport paths.
Router-generated companion thinking budgets use the supplied effort; explicit
unsupported client thinking options still fail.


Only offline behavior has been exercised. No authenticated provider browser or
ChatGPT/Claude request has been made, and no real provider credential file has
been accessed. A separate installation smoke check used only blank local HTML
in a fresh Chromium context with all network routes blocked.
