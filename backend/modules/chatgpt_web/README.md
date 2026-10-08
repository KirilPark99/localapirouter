# ChatGPT Web (Browser)

Common clean-room ChatGPT Web port from OmniRoute commit
`61e07fb7e0d4e1e76111495d3718c9e4d06d2a62`, under its MIT license (preserved in `LICENSE`).
Reference: `chatgpt-web.ts`, `chatgptWebExecutorAdapter.ts`,
`chatgptWebBrowserSession.ts`, `chatgptWebFirstParty.ts`,
`chatgptWebDeltaV1.ts`, `chatgptWebTransport.ts`, `chatgptWebAttachments.ts`,
and the common provider registry. This is **not** the Codex variant.
The reference's `CHATGPT_WEB.md` retirement notice does not describe this executor.

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

## Intentional limitations

* Text messages only. System/developer/user/assistant history is flattened with
  role labels into a fresh temporary conversation, exactly as the common adapter;
  system messages are not native privileged instructions. Tools, tool history,
  reasoning history, attachments/images/files/audio, structured output, sampling,
  token limits, and multiple choices are rejected explicitly, not silently dropped.
* Buffered SSE, not token-live streaming. The terminal assistant document must
  contain text, `status=finished_successfully`, and `end_turn=true` before returning
  any OpenAI chunks. `[DONE]` alone is not success. Usage is unknown, never guessed.
  Buffered OpenAI output also respects the shared collector's 8 MiB assembly limit.
* Direct buffered snapshots and `delta_encoding: v1` are supported. WebSocket-only
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
provider rejection, timeout, cancellation and browser cleanup. With Node available,
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
