# MyAIrouter — Universal Self-Hosted AI API Router & LLM Gateway

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61dafb.svg)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7-blue.svg)](https://www.typescriptlang.org)
[![Tailwind CSS](https://img.shields.io/badge/TailwindCSS-3.4-38bdf8.svg)](https://tailwindcss.com)

**MyAIrouter** is a production-ready, self-hosted universal AI API Gateway and intelligent LLM Router. It acts as a resilient, single-entry-point reverse proxy between client applications (OpenAI Python/Node SDK, Anthropic Claude Code, Cursor, Continue.dev, LangChain, LlamaIndex, OpenWebUI, CLI tools, custom frontends) and multiple upstream AI providers.

Supported upstream ecosystems include **Google AI Studio (Gemini)**, **OpenAI (GPT-4o, o-series)**, **Anthropic (Claude 3.5/3.7)**, **OpenRouter**, **Groq**, **DeepSeek**, **Mistral**, **Together AI**, **xAI (Grok)**, **Fireworks**, **Kilo AI Gateway**, **Ollama**, **vLLM**, and any custom OpenAI-compatible endpoint.

---

## 🌟 Key Features

### 1. Strict Key Separation & Privacy-by-Default
- **Upstream Credentials** (`ProviderCredential`): Stored with authenticated AES-128/256-CBC symmetric encryption (via Fernet). Duplicate registration is blocked via HMAC-SHA256 fingerprinting without decrypting or exposing raw secrets. Sensitive keys are permanently masked in the UI (`AIzaSy...B82P`).
- **Router Client API Keys** (`RouterApiKey`): Granular keys issued to client applications with the standard `sk-router-...` prefix. Keys are argon2/bcrypt/sha256 hashed in database storage, support customizable RPM/TPM rate limits, and enforce granular access lists (`allowed_models`, `allowed_routes`, `allowed_fusions`).
- **Privacy-First Logging**: Full prompt and completion text payloads are **not logged** unless explicitly enabled by the administrator in Settings (`LOG_REQUEST_CONTENT=true`).

### 2. Live Direct API Model Limits & Quota Tracking
- **Zero Static / Hardcoded Limits**: Context length, output limits, and rate limit quotas are extracted dynamically from upstream provider APIs (e.g. Google AI Studio native `inputTokenLimit` and `outputTokenLimit`, OpenAI `/models`).
- **Real-Time HTTP Header Extraction**: Upstream response headers (`x-ratelimit-limit-requests`, `x-ratelimit-remaining-requests`, `x-ratelimit-limit-tokens`, `x-ratelimit-remaining-tokens`, `x-ratelimit-reset-requests`, `x-ratelimit-reset-tokens`) are captured live to monitor requests per minute (RPM), tokens per minute (TPM), requests per day (RPD), remaining quotas, and reset countdowns.
- **Zero-Delay Preloading**: Limits are preloaded directly alongside model lists (`GET /api/admin/models` via `DiscoveredModelRead.limits`) and accessible on-demand via `GET /api/admin/models/{id}/limits`.
- **Intelligent Rendering**: Empty limit blocks are hidden cleanly when upstream providers do not report rate limits.

### 3. Artificial Analysis Intelligence & Benchmarks
- **Integrated Quality & Coding Ratings**: Embedded benchmark scores powered by [Artificial Analysis](https://artificialanalysis.ai) for models across the catalog.
- **Key Benchmark Metrics**:
  - **Quality Index**: Overall model intelligence score (0–100 scale).
  - **Coding Index**: Code generation and refactoring benchmark score.
  - **Agentic Index (`agentic_index`)**: Multi-step tool use, reasoning, and autonomous agent capabilities.
  - **Reasoning Model Detection (`is_reasoning`)**: Visual indicators for native reasoning and CoT models.
- **One-Click Web Sync**: Synchronize benchmark scores anytime with `POST /api/admin/models/sync-ratings`.
- **Rich Catalog Filtering & Sorting**: Filter models by Agentic Index (20+), Quality (50+, 70+), Coding (50+, 70+), and sort by benchmark metrics in the web console.

### 4. Dedicated Reasoning Effort & Thinking Parameters (`reasoning_effort` / `reasoning` / `thinking`)
- **First-Class `reasoning_effort` Parameter**: Full native support for modern reasoning models (OpenAI o1/o3, DeepSeek R1, Gemini 2.5, Claude 3.7) using the standard `reasoning_effort` string (`"low"`, `"medium"`, `"high"`, `"minimal"`, `"max"`, `"none"` / `"off"`).
- **Interactive Playground & Route Overrides**: Set `reasoning_effort` visually in the Playground or per-candidate in Priority & Fallback routing profiles (with custom effort strings or exact token counts).
- **Bi-Directional Cross-Provider Protocol Translation**:
  - **OpenAI o1/o3/r1**: Injects `reasoning_effort: "low" | "medium" | "high"`, strips unsupported parameters (`temperature`, penalties), and strips raw `thinking` objects to prevent 400 rejection errors.
  - **OpenRouter**: Normalizes to `reasoning: {"effort": "..."}` and `reasoning_effort`.
  - **Anthropic Claude 3.7**: Seamlessly translates `reasoning_effort` to `thinking: {"type": "enabled", "budget_tokens": N}` (`low` → 1,024, `medium` → 4,096, `high` → 16,384), enforces `max_tokens > budget_tokens`, and removes `temperature`.
  - **Google Gemini**: Maps `reasoning_effort` through the OpenAI compatibility layer and native Gemini `thinking_config`.

### 5. Multi-Proxy Support per Credential
- **Supported Protocols**: SOCKS5, SOCKS5H (with remote DNS resolution `rdns=True`), HTTP, and HTTPS CONNECT.
- **Granular Per-Key Proxies**: Proxies are linked individually per upstream credential. A single provider can have Key #1 on direct connection, Key #2 through a US SOCKS5 proxy, and Key #3 through an EU HTTP proxy.
- **Quick-Paste Auto-Parser**: Parses proxy formats automatically: `ip:port:user:pass`, `socks5://user:pass@ip:port`, `user:pass@ip:port`, etc.
- **Outbound Server IP Detection**: Live outbound IP lookup (`GET /api/admin/proxies/server-ip`) allows whitelisting your server's egress IP in proxy provider dashboards (Proxy-Seller, Webshare, ProxyLine).

### 6. Keyless & Public Gateway Providers
- **Unlimited Keyless Credentials**: Add multiple zero-key credentials for public or local endpoints (Kilo AI Gateway, Ollama, vLLM, LocalAI) without duplicate HMAC collisions.
- **Proxy Routing for Public Gateways**: Route different keyless endpoints through different geographic proxies (e.g. Kilo Direct, Kilo via US SOCKS5, Kilo via EU SOCKS5).

### 7. Four Intelligent Routing Modes

```
                              CLIENT REQUEST
                                    │
       ┌──────────────────┬─────────┴─────────┬──────────────────┐
       ▼                  ▼                   ▼                  ▼
 DIRECT ROUTING    PRIORITY FALLBACK    MODEL FUSION      JEV SYSTEM ONE
(google/gemini)     (route/coding)    (fusion/best-of-3)  (experientiallabs/jev)
       │                  │                   │                  │
Round-robin keys  Waterfall candidate  Parallel async      Discrete Decision
instant failover  chain + CoT budget   fan-out + Judge     Primitives (choice,
on 429/5xx error  fallback control     deliberation & SSE  score, noul) & Calibrated
       │                  │                   │            Probabilities
       └──────────────────┴─────────┬─────────┴──────────────────┘
                                    ▼
                          CIRCUIT BREAKER CHECK
                                    │
                                    ▼
                         UPSTREAM ADAPTER LAYER
                   (OpenAI / Google / Anthropic / Jev)
                                    │
                                    ▼
                        INDIVIDUAL PROXY TRANSPORTS
                      (Direct / SOCKS5H / HTTP / HTTPS)
```

1. **DIRECT ROUTING with Multi-Key Auto-Failover** (`openai/gpt-4o`, `google/gemini-2.5-flash`):
   - Direct model addressing by `canonical_slug` (`provider/model`) or raw `provider_model_id`.
   - Balanced round-robin load distribution across all healthy credentials for that provider.
   - **Automatic On-the-Fly Key Failover**: If Key #1 encounters a rate limit (HTTP 429), upstream 5xx, network timeout, or auth error, the router automatically retries the request using Key #2 in the same invocation. The failing key is isolated into cooldown, and the client receives a seamless 200 OK.
2. **PRIORITY & FALLBACK ROUTING** (`route/{slug}`):
   - Prioritized candidate waterfall. Candidate #1 is tried first; on retryable failure (429, 5xx, timeout, network error), the router falls back to Candidate #2, Candidate #3, etc.
   - **Nested Profiles**: A routing candidate can be another routing profile, enabling hierarchical fallback chains with built-in circular dependency prevention.
   - **Per-Candidate Thinking Overrides**: Configure custom thinking token budgets for individual candidates in the fallback chain.
   - **Fast-Fail on Non-Retryable Errors**: Client errors (400 Bad Request, context length exceeded, content policy violations) immediately return to the caller without wasting upstream retries.
3. **MODEL FUSION (Multi-LLM Ensemble)** (`fusion/{slug}`):
   - Async fan-out in parallel across diverse models, providers, and credentials.
   - Collects candidate responses and invokes an AI Judge model using one of 4 strategies:
     - `synthesize`: Blends the best insights and reasoning from all candidates into a unified answer.
     - `best_of_n`: Selects the single most accurate, comprehensive candidate response.
     - `consensus`: Identifies agreements across models and clarifies discrepancies.
     - `critique_and_rewrite`: Critiques each answer, eliminates errors, and outputs a revised synthesis.
   - Real-time Server-Sent Events (SSE) streaming of the judge synthesis.
4. **JEV (SYSTEM ONE) DECISION ENGINE** (`/v1/systemone`, `/v1/decisions`):
   - Fast intuitive System One evaluation against discrete rubrics and structured criteria.
   - **3 Decision Primitives**:
     - `choice`: Discrete multi-class selection with calibrated softmax probability distribution.
     - `score`: Numeric evaluation against defined criteria (e.g. 0.0 - 1.0 or 1 - 5) with confidence metrics.
     - `noul`: Binary / boolean decision predicate with confidence score.
   - **Native Zero-Delay Routing**: Direct pass-through dispatch to providers with native System One support (`drex.nace`, `experientiallabs`, `typesafe.ai`).
   - **Universal Structured LLM Emulation**: Any general LLM (Gemini 2.5, GPT-4o, Claude 3.5, Groq, Ollama) marked with `model_type: "jev"` is automatically emulated via strict JSON schema prompting.
   - **Transparent Chat Compatibility**: `POST /v1/chat/completions` transparently accepts Jev decision payloads and returns compliant structured responses.

### 8. Model Catalog Types & Batch Management (`openai` vs `jev`)
- **Default Mode (`openai`)**: All registered models default to OpenAI-compatible conversational chat and vision generation.
- **System One Mode (`jev`)**: Models toggled to `jev` serve as discrete decision engines for fast classification and guardrails.
- **Catalog Filter Chips**: Filter models instantly by `All Types`, `OpenAI`, or `⚡ Jev`.
- **Batch Update Modal**: Easily change model execution types in bulk via the "Set Model Type" modal or individual edit dialog in `/models`.
- **API Visibility**: Model type metadata is returned in `GET /v1/models` and `GET /v1/models/{id}` (`model_type: "openai" | "jev"`).

### 9. Interactive Playground Decision Studio
- **Dedicated ⚡ Jev Tab**: Interactive workspace alongside Chat, Single, and Compare modes in `/playground`.
- **State Context Editor**: Define the exact conversation, code diff, transaction, or security log being evaluated.
- **Visual Question Builder**: Add question primitives (`choice`, `score`, `noul`) with options and live schema validation, or edit raw JSON.
- **4 Built-in Presets**:
  - *Customer Support Escalation* (urgency triage and department routing)
  - *Content Moderation Guardrail* (toxicity, PII, and safety enforcement)
  - *PR Code Review* (quality score, regression risk, and approval assertion)
  - *Financial Fraud Risk* (transaction risk category and step-up 2FA trigger)
- **Calibrated Probability Charts & Export**: Real-time distribution graphs, confidence gauges, and instant code generation (cURL, Python, Node.js).

### 10. Circuit Breaker & Health Tracking
- **Automated Failure Quarantine**: Tracks consecutive failures per credential. After threshold failures (default: 3), the key transitions to `COOLDOWN` (default: 60s).
- **HTTP 429 Awareness**: Honors upstream `Retry-After` headers for dynamic cooldown durations.
- **State Progression**: `HEALTHY` ➔ `DEGRADED` ➔ `COOLDOWN` / `RATE_LIMITED` ➔ automatic half-open probe ➔ `HEALTHY`.
- **Manual Reset**: One-click circuit breaker reset from the web console.

### 11. Dynamic Activity Timeline & Analytics
- **Continuous 24-Bucket Hourly Timeline**: Gap-free time series visualization in the Analytics Dashboard.
- **Flexible Time Horizons**: Toggle between 24 Hours (hourly buckets), 7 Days (daily), 30 Days (daily), or All Time.
- **Tracked Operational Metrics**: Request volume, Success rate (%), Total prompt/completion tokens, Estimated cost in USD, and Average latency (ms).
- **Breakdown Tables**: Detailed usage tables by Router Key, Provider, Model, Credential, and Routing Profile.

### 12. Unified Multi-Protocol Endpoints
- **OpenAI Compatible**:
  - `GET /v1/models`: Standard model list exposing direct models, routes, fusions, and model types (`openai` / `jev`).
  - `POST /v1/chat/completions`: Full non-streaming JSON and real-time SSE streaming (`stream: true`), plus transparent Jev decision routing.
  - `POST /v1/responses`: OpenAI Responses API alias.
- **Jev System One Decisions**:
  - `POST /v1/systemone`: Dedicated discrete decision engine evaluation endpoint.
  - `POST /v1/decisions`: Alias for `/v1/systemone`.
- **Anthropic Native Messages Protocol**:
  - `POST /v1/messages`: Translates native Anthropic messages payloads, allowing tools like Claude Code to connect directly to MyAIrouter.

---

## 🚀 Quick Start Guide

### Prerequisites
- Linux / macOS (Ubuntu 20.04+, Debian 11+, macOS 12+)
- Python 3.11 or 3.12
- Node.js 18+ and npm

### 1. Installation & Environment Setup

```bash
# Clone repository
git clone https://github.com/your-repo/MyAIrouter.git
cd MyAIrouter

# Create virtual environment and install backend dependencies
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Configure environment variables
cd ..
cp .env.example .env

# Generate values and put them into the blank fields in .env.
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
# Set ADMIN_PASSWORD (at least 12 characters), JWT_SECRET, ROUTER_MASTER_KEY,
# and FINGERPRINT_SALT before starting the server.

# Run database migrations
cd backend
.venv/bin/alembic upgrade head
```

### 2. Build the Frontend Console

```bash
cd ../frontend
npm install
npm run build
```
*(The compiled static assets are saved to `frontend/dist` and automatically served by FastAPI on port 8000).*

### 3. Run the Gateway Server

```bash
cd ..
backend/.venv/bin/uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```

Access points:
- **Admin Console**: [http://localhost:8000/](http://localhost:8000/) *(Use the `ADMIN_USERNAME` and `ADMIN_PASSWORD` values from `.env`.)*
- **Interactive OpenAPI Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **OpenAI Compatible API Base**: `http://localhost:8000/v1`

---

## 💻 Client SDK & cURL Examples

### 1. Generate a Router Client API Key
In the Admin Console under **Router API Keys**, or via API:
```bash
# Obtain Admin JWT
TOKEN=$(curl -s -X POST http://localhost:8000/api/admin/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "<ADMIN_USERNAME>", "password": "<ADMIN_PASSWORD>"}' | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

# Create Client Router Key
curl -s -X POST http://localhost:8000/api/admin/keys \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production App",
    "permissions": ["direct", "routes", "fusion"],
    "allowed_models": ["*"],
    "allowed_routes": ["*"],
    "allowed_fusions": ["*"]
  }'
```
Response:
```json
{
  "id": 1,
  "name": "Production App",
  "raw_api_key": "sk-router-<KEY_SHOWN_ONCE>",
  "masked_key": "sk-router-••••<LAST4>"
}
```

---

### 2. Python (Official `openai` SDK)

#### Standard Chat Completion (Direct Routing with Multi-Key Failover)
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="sk-router-YOUR_CLIENT_KEY",
)

response = client.chat.completions.create(
    model="google-ai/gemini-2.5-flash",
    messages=[
        {"role": "system", "content": "You are a concise, helpful assistant."},
        {"role": "user", "content": "Explain how an API gateway achieves zero-downtime failover."}
    ],
    temperature=0.7,
)

print(response.choices[0].message.content)
```

#### Dedicated Reasoning Effort & Thinking Control
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="sk-router-YOUR_CLIENT_KEY",
)

# 1. Standard OpenAI reasoning_effort parameter (works across OpenAI o1/o3, Gemini 2.5, DeepSeek R1, and Claude 3.7)
response = client.chat.completions.create(
    model="openai/o3-mini",
    messages=[
        {"role": "user", "content": "Solve this complex mathematical optimization problem step by step..."}
    ],
    reasoning_effort="high",  # "low" | "medium" | "high" | "minimal" | "max" | "none"
)
print(response.choices[0].message.content)

# 2. Or pass Claude 3.7 token budget - router automatically adapts between tokens and effort!
response_claude = client.chat.completions.create(
    model="anthropic/claude-3-7-sonnet-20250219",
    messages=[
        {"role": "user", "content": "Analyze potential race conditions in this concurrent code..."}
    ],
    reasoning_effort="medium",  # router converts to Anthropic thinking: {type: "enabled", budget_tokens: 4096}
)
print(response_claude.choices[0].message.content)
```

#### Calling a Priority Fallback Route with Real-Time Streaming
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="sk-router-YOUR_CLIENT_KEY",
)

# "route/coding" will try Candidate 1 -> Candidate 2 -> Candidate 3
stream = client.chat.completions.create(
    model="route/coding",
    messages=[
        {"role": "user", "content": "Write an asynchronous worker pool implementation in Rust."}
    ],
    stream=True,
)

for chunk in stream:
    if chunk.choices and chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
print()
```

#### Model Fusion (Multi-LLM Ensemble Synthesis Stream)
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="sk-router-YOUR_CLIENT_KEY",
)

# "fusion/architecture-review" queries multiple models concurrently and streams the Judge's synthesis
stream = client.chat.completions.create(
    model="fusion/architecture-review",
    messages=[
        {"role": "user", "content": "Critique this distributed database design proposal: ..."}
    ],
    stream=True,
)

for chunk in stream:
    if chunk.choices and chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
print()
```

#### Jev System One Decision Engine (`/v1/systemone` or native provider)
```python
import requests

# Query high-speed System One decision engine with discrete question primitives
response = requests.post(
    "http://localhost:8000/v1/systemone",
    headers={
        "Authorization": "Bearer sk-router-YOUR_CLIENT_KEY",
        "Content-Type": "application/json",
    },
    json={
        "model": "experientiallabs/jev-latest",
        "state": "Customer support ticket: 'Urgent: Payment charged twice, please refund ASAP.'",
        "questions": [
            {
                "id": "triage_priority",
                "text": "What is the priority level of this ticket?",
                "type": "choice",
                "options": ["low", "normal", "high", "critical"]
            },
            {
                "id": "sentiment_score",
                "text": "Customer sentiment score (0.0=furious to 1.0=delighted)",
                "type": "score"
            },
            {
                "id": "requires_immediate_escalation",
                "text": "Does this require supervisor tier-2 escalation?",
                "type": "noul"
            }
        ]
    }
)

decisions = response.json().get("decisions", {})
print("Priority:", decisions["triage_priority"]["choice"])
print("Probabilities:", decisions["triage_priority"]["probabilities"])
print("Escalate:", decisions["requires_immediate_escalation"]["value"])
```

---

### 3. Node.js / TypeScript SDK Example

```typescript
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "http://localhost:8000/v1",
  apiKey: "sk-router-YOUR_CLIENT_KEY",
});

async function main() {
  const completion = await client.chat.completions.create({
    model: "route/coding",
    messages: [{ role: "user", content: "Implement LRU Cache in TypeScript" }],
  });

  console.log(completion.choices[0].message.content);
}

main();
```

---

### 4. cURL Examples

#### A. Direct Model Call with Thinking Effort
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer sk-router-YOUR_CLIENT_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "google-ai/gemini-2.5-flash",
    "messages": [{"role": "user", "content": "Prove that the square root of 2 is irrational."}],
    "reasoning_effort": "high"
  }'
```

#### B. Jev System One Decision Primitive API (`/v1/systemone`)
```bash
curl -X POST http://localhost:8000/v1/systemone \
  -H "Authorization: Bearer sk-router-YOUR_CLIENT_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "experientiallabs/jev-latest",
    "state": "Security audit: 12 failed SSH logins from IP 203.0.113.19 within 30 seconds.",
    "questions": [
      {
        "id": "threat_level",
        "text": "Assess the intrusion threat level",
        "type": "choice",
        "options": ["benign", "suspicious", "severe_bruteforce"]
      },
      {
        "id": "block_ip",
        "text": "Should IP address be automatically added to firewall blocklist?",
        "type": "noul"
      }
    ]
  }'
```

#### C. Anthropic Native Messages Endpoint (`/v1/messages`)
```bash
curl -X POST http://localhost:8000/v1/messages \
  -H "x-api-key: sk-router-YOUR_CLIENT_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "anthropic/claude-3-7-sonnet-20250219",
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "Hello from Claude Code!"}]
  }'
```

---

## 🛡️ Error Handling & Fallback Classification

Every upstream error is normalized into a strict taxonomy determining whether fallback or key-failover should trigger:

| HTTP Status / Cause | Normalized Error Category | Direct Multi-Key Failover? | Priority Fallback Eligible? | Router Behavior |
| :--- | :--- | :---: | :---: | :--- |
| **HTTP 429** | `RATE_LIMIT` | **YES** | **YES** | Trips key circuit breaker, sets dynamic cooldown, fails over to next key / candidate |
| **HTTP 500, 502, 503, 504** | `UPSTREAM_5XX` | **YES** | **YES** | Logs upstream server fault, immediate failover to next key / candidate |
| **Connect / Read Timeout** | `TIMEOUT` | **YES** | **YES** | Failover to next key / candidate within route timeout budget |
| **Proxy / DNS / Network Reset** | `NETWORK_ERROR` | **YES** | **YES** | Isolates proxy/connection error, fails over to next candidate |
| **HTTP 401 / 403** (Invalid Upstream Key) | `AUTH_ERROR` | **YES** | **NO** | Direct routing tries other keys of provider; marks bad key as `INVALID` |
| **HTTP 404** (Model Not Found) | `MODEL_NOT_FOUND` | **NO** | **YES** | Fails over to next candidate if configured in profile conditions |
| **HTTP 400** (Malformed Request) | `INVALID_REQUEST` | **NO** | **NO** | Returns HTTP 400 immediately to caller (prompt syntax/param issue) |
| **HTTP 400** (Context Window Exceeded) | `CONTEXT_LENGTH_EXCEEDED` | **NO** | **NO** | Returns HTTP 400 immediately (prompt exceeds model token capacity) |
| **HTTP 400 / 403** (Content Safety Filter) | `CONTENT_POLICY_VIOLATION` | **NO** | **NO** | Returns HTTP 400 immediately to caller |
| **Invalid Router API Key** | `AUTHENTICATION_ERROR` | **NO** | **NO** | Returns HTTP 401 Unauthorized directly to client |

---

## 📊 Complete API Reference

### OpenAI-Compatible & Decision Public Routes (`/v1`)
| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/v1/models` | List available models, routes (`route/*`), fusions (`fusion/*`), and model types (`openai`, `jev`) |
| `POST` | `/v1/chat/completions` | Create chat completion (Direct, Fallback Route, or Fusion; supports JSON, SSE streaming, and Jev decisions) |
| `POST` | `/v1/systemone` | Jev System One discrete decision engine evaluation (`choice`, `score`, `noul`) |
| `POST` | `/v1/decisions` | Alias for `/v1/systemone` |
| `POST` | `/v1/responses` | Alias for `/v1/chat/completions` (OpenAI Responses API compatibility) |
| `POST` | `/v1/messages` | Native Anthropic Messages API inbound endpoint |

### Admin Management API (`/api/admin`)
| Module | Method | Path | Description |
| :--- | :--- | :--- | :--- |
| **Auth** | `POST` | `/api/admin/auth/login` | Authenticate admin, issue JWT, set HttpOnly cookie |
| | `GET` | `/api/admin/auth/me` | Current authenticated admin profile |
| | `POST` | `/api/admin/auth/change-password` | Update admin password |
| **Dashboard** | `GET` | `/api/admin/dashboard/stats` | KPI counters (creds, healthy, models, 24h metrics) |
| | `GET` | `/api/admin/dashboard/detailed-stats` | Continuous timeline metrics & entity breakdowns (`24h`, `7d`, `30d`, `all`) |
| **Providers** | `GET` | `/api/admin/providers` | List configured providers with model/key counts |
| | `POST` | `/api/admin/providers` | Add custom or preset provider |
| | `DELETE`| `/api/admin/providers/{id}` | Remove provider |
| **Credentials** | `GET` | `/api/admin/credentials` | List upstream encrypted credentials |
| | `POST` | `/api/admin/credentials` | Add credential (supports keyless mode & proxy linking) |
| | `POST` | `/api/admin/credentials/{id}/test` | Live test credential upstream connectivity |
| | `POST` | `/api/admin/credentials/{id}/reset-circuit-breaker` | Reset circuit breaker to HEALTHY |
| **Models** | `GET` | `/api/admin/models` | Model catalog with ratings & preloaded live limits |
| | `GET` | `/api/admin/models/{id}/limits` | On-demand live API limit extraction |
| | `POST` | `/api/admin/models/fetch/{cred_id}` | Dynamically discover models from provider API |
| | `POST` | `/api/admin/models/fetch-all` | Discover models across all active credentials |
| | `POST` | `/api/admin/models/sync-ratings` | Sync Artificial Analysis intelligence & coding ratings |
| | `POST` | `/api/admin/models/batch-update` | Bulk enable/disable models |
| **Routes** | `GET` | `/api/admin/routes` | List priority fallback routing profiles |
| | `POST` | `/api/admin/routes` | Create routing profile (with nested profiles & CoT settings) |
| | `PUT` | `/api/admin/routes/{id}` | Update profile candidates and fallback conditions |
| | `DELETE`| `/api/admin/routes/{id}` | Delete routing profile |
| **Fusion** | `GET` | `/api/admin/fusion` | List multi-LLM fusion profiles |
| | `POST` | `/api/admin/fusion` | Create fusion profile with strategy & judge model |
| | `DELETE`| `/api/admin/fusion/{id}` | Delete fusion profile |
| **Proxies** | `GET` | `/api/admin/proxies` | List SOCKS5/HTTP proxies |
| | `POST` | `/api/admin/proxies` | Create proxy configuration |
| | `POST` | `/api/admin/proxies/parse` | Parse raw proxy string into host, port, credentials |
| | `GET` | `/api/admin/proxies/server-ip` | Fetch server's outbound public IP |
| | `POST` | `/api/admin/proxies/{id}/test` | Test proxy connection upstream |
| **Keys** | `GET` | `/api/admin/keys` | List client router API keys |
| | `POST` | `/api/admin/keys` | Create client router API key with permissions |
| | `DELETE`| `/api/admin/keys/{id}` | Revoke client router API key |
| **Logs** | `GET` | `/api/admin/logs` | Paginated request logs with multi-candidate attempt traces |
| **Settings** | `GET` | `/api/admin/settings` | Server settings & encryption status |
| | `POST` | `/api/admin/settings` | Update settings (privacy logging, timeouts, retries) |

---

## ⚙️ Environment Variables Reference

Configure these in `.env`:

| Variable | Description | Default |
| :--- | :--- | :--- |
| `HOST` | Network interface binding | `0.0.0.0` |
| `PORT` | HTTP server port | `8000` |
| `DEBUG` | Enable verbose debugging logs | `false` |
| `DATABASE_URL` | SQLAlchemy async connection string (`sqlite+aiosqlite` or `postgresql+asyncpg`) | `sqlite+aiosqlite:///myairouter.db` |
| `ROUTER_MASTER_KEY` | Generated Fernet key used to encrypt upstream API keys | **Required; no default** |
| `JWT_SECRET` | Secret key for signing admin authentication tokens | **Required; no default** |
| `ADMIN_USERNAME` | Administrator username | `admin` |
| `ADMIN_PASSWORD` | Administrator password (minimum 12 characters) | **Required; no default** |
| `LOG_REQUEST_CONTENT` | Log full prompt and completion bodies (Privacy toggle) | `false` |
| `FINGERPRINT_SALT` | Installation-specific HMAC salt for duplicate detection | **Required; no default** |
| `CORS_ORIGINS` | Comma-separated browser origin allowlist | `http://localhost:5173,http://127.0.0.1:5173` |
| `COOKIE_SECURE` | Mark admin session cookies as Secure | `true` |
| `DEFAULT_TIMEOUT_SECONDS` | Default timeout for individual upstream requests | `60.0` |
| `FUSION_TIMEOUT_SECONDS` | Timeout for entire parallel multi-LLM fusion operations | `120.0` |
| `MAX_FALLBACK_ATTEMPTS` | Maximum retry attempts within a fallback chain | `5` |

---

## 🧪 Automated Testing

Run the full pytest suite:

```bash
cd backend
.venv/bin/pytest -v
```

All test suites verify:
- Authenticated AES/Fernet encryption, decryption, and secret masking.
- HMAC-SHA256 duplicate credential detection without plain-text storage.
- Circuit breaker state transitions, exponential cooldown, and rate limit backoff.
- Multi-key automatic failover during direct model routing.
- Priority fallback routing on HTTP 429 and error classification filtering.
- Multi-LLM parallel fan-out fusion with AI Judge synthesis.
- Official `openai.AsyncOpenAI` SDK compatibility for model listing, chat completions, and real-time chunk streaming.

---

## 🏭 Production Deployment Guide

1. **Persistent Encryption Key**: Ensure `ROUTER_MASTER_KEY` is set in `.env`. Never lose this key, as it encrypts all stored provider secrets.
2. **Production Database**: For enterprise loads, point `DATABASE_URL` to PostgreSQL:
   ```env
   DATABASE_URL=postgresql+asyncpg://postgres:secret@localhost:5432/myairouter
   ```
   Run migrations: `alembic upgrade head`.
3. **Reverse Proxy (Nginx / Caddy)**:
   Disable proxy buffering for Server-Sent Events (SSE) streaming:
   ```nginx
   location / {
       proxy_pass http://127.0.0.1:8000;
       proxy_set_header Host $host;
       proxy_set_header X-Real-IP $remote_addr;
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       proxy_set_header X-Forwarded-Proto $scheme;
       proxy_http_version 1.1;
       proxy_set_header Connection "";
       proxy_buffering off;
       proxy_cache off;
       proxy_read_timeout 600s;
   }
   ```
4. **Systemd Service Unit**:
   ```ini
   [Unit]
   Description=MyAIrouter Gateway Service
   After=network.target

   [Service]
   Type=simple
   User=www-data
   WorkingDirectory=/opt/MyAIrouter
   ExecStart=/opt/MyAIrouter/backend/.venv/bin/uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --workers 4
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```

---

## 📄 License
MIT License. Free for personal, academic, and commercial use.
