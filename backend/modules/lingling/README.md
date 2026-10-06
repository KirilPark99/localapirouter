# Lingling module

Uses the existing local Lingling source and the real OpenCode client through its Tor/MITM relay. It does not copy or modify Lingling.

## Setup

- Install backend dependencies (`uv sync`). The bridge requires `stem==1.8.2`; cryptography is already a backend dependency.
- Install the system Tor binary and GeoIP data, and OpenCode. On Linux, Lingling does not download Tor automatically.
- Open **Modules → Lingling · OpenCode over Tor → Add Profile**.
- Keep the source directory pointing to the existing Lingling checkout. Configure the number of lanes, country lists and cold-start timeout as needed.
- Leave the ordinary profile proxy empty. Optional binary paths override PATH detection.
- **Test** checks the local configuration and OpenCode model catalog without starting Tor. **Sync Models** refreshes the free-model catalog from the installed OpenCode client.

## Requests and lifecycle

Use a model from this module through the usual router/playground. DIRECT requests for first-party OpenCode Zen free models present in the Lingling manifest also use an enabled Lingling profile automatically; the requested name and API-key permissions stay unchanged, and logs record the actual Lingling provider/profile. Paid or unlisted Zen models retain their HTTP route. If Lingling is disabled, unavailable or has no healthy profile, free Zen requests return 503 instead of falling back to generic HTTP. Explicit PRIORITY candidates are not rewritten: select the Lingling model in those profiles.

The first generation starts an isolated Tor/OpenCode worker; bootstrap can take several minutes. Later requests reuse it. Each profile owns private runtime directories under `$XDG_STATE_HOME/MyAIrouter/lingling` or `~/.local/state/MyAIrouter/lingling`. Chat-only and client-tool requests use separate owned workers because their native denial policies differ.

Chat completions support non-streaming and SSE, text history, system instructions, reasoning output, inline base64 images where supported, temperature/top_p and an output-token limit. History is passed as a JSON transcript because OpenCode's prompt endpoint accepts user parts, not arbitrary assistant message imports; previous tool/function calls and their results are preserved as context, never replayed. A final `tool` result with its original `tool_call_id` continues the model turn. Reasoning effort must match a variant exposed by the selected OpenCode model.

Client function tools (for example Hermes tools) are exposed through one request-owned stdio MCP schema server. The server never executes functions. The bridge captures genuine OpenCode call IDs and parsed arguments, denies native execution, and returns OpenAI `tool_calls` / streaming `delta.tool_calls` with `finish_reason: "tool_calls"`. The API client executes its own tools and sends their real results in the next request. External names are mapped to collision-free MCP aliases and restored in the response. Schemas are disconnected and removed at request completion/cancellation.

Absent `tool_choice` and `"auto"` allow either a client call or a text answer; `"none"` disables supplied definitions. `"required"` requires a genuine client call. Named function selection exposes only the matching schema. `parallel_tool_calls: false` requires at most one call. If OpenCode ignores these constraints, the bridge reports an upstream error rather than inventing calls or silently changing the request. The client-tool runtime starts with `experimental.continue_loop_on_deny=false`; waiting for a completed tool message and then aborting is not a safe barrier against another upstream request. Chat-only requests retain native rejection plus continuation; bounded explicit continuation after native denial in agent mode also never approves execution. Usage counts completed denied-tool turns once.

Host MCP servers/plugins remain disabled; only the request-owned client schema server is registered. Every native local operation requires approval, and the bridge never approves tools or interactive questions. Remote/file image URLs, image history, multiple completions, stop sequences, seed, structured-output and nonzero penalty options are rejected rather than silently ignored. The bridge has no direct upstream fallback. Cold-start readiness requires an owned live Tor process, complete bootstrap and an upstream probe; a probe alone does not prove model generation succeeds.

Changing, disabling or deleting a profile releases its worker. Module reload and application shutdown stop owned processes, including cancellation-safe cleanup. Diagnostics (`worker.log`, `opencode.log`, `proof.log`) stay in the private runtime directory; do not share them blindly because client diagnostics can include conversation data.
