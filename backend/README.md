# MyAIrouter Backend

High-performance, async Python API Gateway and universal LLM router built with **FastAPI**, **SQLAlchemy (asyncio)**, **Pydantic V2**, and **HTTPX**.

---

## ⚡ Core Architecture

The backend serves as a resilient, single-entry-point reverse proxy and decision gateway between client applications and heterogeneous AI model providers.

```
                           CLIENT REQUEST
                                 │
        ┌────────────────┬───────┴────────┬────────────────┐
        ▼                ▼                ▼                ▼
  DIRECT ROUTING   FALLBACK ROUTE   MODEL FUSION     JEV SYSTEM ONE
  (round-robin)    (priority chain) (AI judge vote)  (discrete rubrics)
        │                │                │                │
        └────────────────┴───────┬────────┴────────────────┘
                                 ▼
                       CIRCUIT BREAKER & HEALTH
                                 │
                                 ▼
                       ASYNC UPSTREAM ADAPTER
                    (Direct, SOCKS5H, HTTP Proxy)
                                 │
                                 ▼
                     UPSTREAM PROVIDER INFERENCE
```

### Key Responsibilities
1. **Multi-Protocol Ingestion**:
   - `POST /v1/chat/completions` (OpenAI format, non-streaming & Server-Sent Events SSE streaming)
   - `POST /v1/systemone` & `POST /v1/decisions` (Jev System One discrete decision engine)
   - `POST /v1/messages` (Native Anthropic format for Claude Code compatibility)
   - `GET /v1/models` (OpenAI model discovery with `model_type: "openai" | "jev"`)
   - `/api/tags`, `/api/show`, `/api/version` (Ollama drop-in protocol)
2. **Four Routing Engines**:
   - **Direct Routing**: Round-robin across healthy credentials for a provider with instant on-the-fly failover on HTTP 429/5xx errors.
   - **Priority Fallback**: Configurable waterfall fallback chains with nested profiles and per-candidate reasoning/thinking token overrides.
   - **Model Fusion**: Multi-LLM asynchronous fan-out synthesized by a judge LLM using `synthesize`, `best_of_n`, `consensus`, or `critique_and_rewrite` with real-time streamed deliberation.
   - **Jev (System One) Decisions**: Millisecond-level evaluation against discrete rubrics (`choice`, `score`, `noul`) with calibrated probabilities.
3. **Key Management & Security**:
   - Upstream API keys encrypted with authenticated AES-128-CBC Fernet symmetric encryption.
   - Client router keys hashed with argon2/bcrypt/sha256 and subject to granular ACLs and rate limits.
   - Keyless Mode for local Ollama/vLLM instances without mock keys.
4. **Resilience & Networking**:
   - Circuit breaker tracking consecutive failures with automatic cooldown and half-open probing.
   - Granular per-credential HTTP/HTTPS/SOCKS5/SOCKS5H proxies.

---

## ⚡ Jev (System One) Decision Engine

The Jev System One engine provides ultra-fast evaluation of state against discrete rubrics, suited for autonomous agents, classification, safety guardrails, and compliance scoring.

### 1. Decision Primitives
- **`choice`**: Categorical classification returning a normalized softmax probability distribution summing to 1.0 across options.
- **`score`**: Quantitative evaluation against a numeric rubric (e.g. 0.0 - 1.0 or 1 - 5) with confidence metrics.
- **`noul`**: Binary boolean predicate assertion with confidence level.

### 2. Execution Modes
- **Native Pass-Through**: Direct dispatch to providers supporting native System One protocols (such as `drex.nace`, `experientiallabs`, `typesafe.ai`) with minimal overhead.
- **Universal LLM Structured Emulation**: Any standard model (e.g. Gemini 2.5 Flash, GPT-4o Mini, Claude 3.5 Haiku, Groq, Ollama) marked with `model_type: "jev"` is automatically emulated via strict JSON schema prompting and calibrated probability extraction.
- **Chat API Transparency**: Standard `POST /v1/chat/completions` transparently detects Jev payloads and returns compliant decision objects.

### 3. Model Catalog Types
- Models have a `model_type` attribute: `"openai"` (default) or `"jev"`.
- Configurable individually or via batch updates (`POST /api/admin/models/batch-update`).
- Returned in `GET /v1/models` and `GET /api/admin/models`.

---

## 📁 Directory Layout

```
backend/
├── app/
│   ├── api/
│   │   ├── admin/            # Admin control plane (auth, credentials, models, routes, fusion, proxies, logs)
│   │   ├── v1/               # Public OpenAI, Ollama, Anthropic & Jev endpoints
│   │   │   ├── chat.py       # /v1/chat/completions with transparent Jev handling
│   │   │   ├── decisions.py  # /v1/systemone & /v1/decisions
│   │   │   ├── models.py     # /v1/models (with model_type)
│   │   │   └── messages.py   # /v1/messages (Anthropic)
│   ├── core/
│   │   ├── config.py         # App configuration & environment validation
│   │   ├── database.py       # Async SQLAlchemy engine & session factory
│   │   ├── security.py       # Fernet AES encryption, key hashing & JWT tokens
│   │   └── circuit_breaker.py# Health status & failure tracking
│   ├── models/               # SQLAlchemy ORM declarative models
│   ├── schemas/              # Pydantic V2 schemas & validation models
│   ├── services/
│   │   ├── direct_router.py  # Round-robin credential dispatch & failover
│   │   ├── fallback_router.py# Waterfall candidate chain resolution
│   │   ├── fusion_service.py # Parallel ensemble & judge synthesis
│   │   ├── jev_service.py    # Jev System One native & emulated engine
│   │   └── http_client.py    # Async HTTPX client with proxy pool
│   └── main.py               # FastAPI application entrypoint
├── alembic/                  # Database schema migrations
└── tests/                    # Pytest test suite
```

---

## 🚀 Development & Run

### 1. Environment Configuration
Ensure `.env` exists in the project root with:
```bash
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_password_min_12_chars
JWT_SECRET=your_jwt_secret_random_bytes
ROUTER_MASTER_KEY=your_fernet_aes_key
DATABASE_URL=sqlite+aiosqlite:///./data/router.db
```

### 2. Run Database Migrations
```bash
cd backend
.venv/bin/alembic upgrade head
```

### 3. Start the Server
```bash
.venv/bin/uvicorn app.main:app --app-dir . --host 0.0.0.0 --port 8000 --reload
```

---

## 🧪 Testing

Run backend test suites:
```bash
cd backend
.venv/bin/pytest tests/ -v
```
