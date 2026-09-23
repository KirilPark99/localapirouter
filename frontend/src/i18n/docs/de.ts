import { DocContent } from "./types";

export const de: DocContent = {
  "ui": {
    "searchPlaceholder": "Dokumentation durchsuchen (z. B. Ollama, Fallback, Fusion)...",
    "noSectionsFound": "Keine passenden Abschnitte gefunden.",
    "prevSection": "Vorheriger Abschnitt",
    "nextSection": "Nächster Abschnitt",
    "copied": "Kopiert!",
    "copy": "Code kopieren",
    "endpoints": "Endpunkte",
    "tocTitle": "Inhaltsverzeichnis"
  },
  "sections": [
    {
      "id": "overview",
      "title": "Systemübersicht",
      "group": "intro",
      "description": "Universelles, selbst gehostetes LLM-Gateway mit Direct-, Priority-Fallback- und Fusion-Engines, Key-Pooling und Ollama-Kompatibilität.",
      "subsections": [
        {
          "title": "Vergleich der Routing-Modi",
          "table": {
            "headers": [
              "Mode / Мод",
              "Slug Prefix",
              "Target / Цель",
              "Strategy / Стратегия",
              "Latency / Задержка"
            ],
            "rows": [
              [
                "Direct Routing",
                "none or provider/",
                "Single Provider Model",
                "Round-robin across healthy credentials",
                "Lowest (single hop)"
              ],
              [
                "Priority Fallback",
                "route/*",
                "Ordered Chain of Models/Profiles",
                "Sequential try-next on 429 / 5xx error",
                "Fast on 1st, robust on failure"
              ],
              [
                "Model Fusion",
                "fusion/*",
                "Multi-Model Ensemble + Judge",
                "Parallel execution with consensus synthesis",
                "Higher (multi-model + judge deliberation)"
              ]
            ]
          }
        }
      ],
      "badge": "Core Architecture",
      "highlights": [
        "3 Routing-Engines: Direkt, Prioritäts-Fallback (verschachtelt) und Modell-Fusion",
        "Kompatibel mit OpenAI-API (/v1/chat/completions) und Ollama (/api/tags, /api/show)",
        "Sichere Schlüsselverwaltung: AES-128-CBC Fernet-Verschlüsselung mit ROUTER_MASTER_KEY",
        "Circuit Breaker zur automatischen Fehlerisolation mit Geo-Proxy-Unterstützung"
      ]
    },
    {
      "id": "quickstart",
      "title": "Schnellstart-Anleitung",
      "group": "intro",
      "description": "Verbinden Sie jedes OpenAI-SDK, cURL oder lokale Ollama-Clients in Sekundenschnelle mit MyAIrouter.",
      "subsections": [
        {
          "title": "1. cURL Schnellstart",
          "code": {
            "title": "cURL Chat Completion",
            "lang": "bash",
            "content": "curl http://localhost:8000/v1/chat/completions \\\n  -H \"Content-Type: application/json\" \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\n    \"model\": \"gemini-2.5-flash\",\n    \"messages\": [{\"role\": \"user\", \"content\": \"Explain quantum computing in one sentence.\"}],\n    \"temperature\": 0.7\n  }'"
          }
        },
        {
          "title": "2. Python OpenAI SDK",
          "code": {
            "title": "Python Client (Streaming)",
            "lang": "python",
            "content": "from openai import OpenAI\n\nclient = OpenAI(\n    base_url=\"http://localhost:8000/v1\",\n    api_key=\"sk-router-YOUR_KEY\"\n)\n\nresponse = client.chat.completions.create(\n    model=\"route/coding-fallback\",\n    messages=[\n        {\"role\": \"system\", \"content\": \"You are an expert engineer.\"},\n        {\"role\": \"user\", \"content\": \"Write an async Python client for SSE.\"}\n    ],\n    temperature=0.2,\n    stream=True\n)\n\nfor chunk in response:\n    if chunk.choices and chunk.choices[0].delta.content:\n        print(chunk.choices[0].delta.content, end=\"\", flush=True)"
          }
        },
        {
          "title": "3. Node.js / TypeScript",
          "code": {
            "title": "TypeScript OpenAI Client",
            "lang": "typescript",
            "content": "import OpenAI from \"openai\";\n\nconst client = new OpenAI({\n  baseURL: \"http://localhost:8000/v1\",\n  apiKey: \"sk-router-YOUR_KEY\",\n});\n\nasync function main() {\n  const completion = await client.chat.completions.create({\n    model: \"fusion/code-jury\",\n    messages: [{ role: \"user\", content: \"Compare Rust and Go for API gateways.\" }],\n  });\n  console.log(completion.choices[0].message.content);\n}\n\nmain();"
          }
        }
      ],
      "badge": "2-Minute Setup"
    },
    {
      "id": "models",
      "title": "Modell-Adressierung & Auflösung",
      "group": "models",
      "description": "Flexibles mehrstufiges Modell-Adressierungssystem: kanonische Slugs, Provider-Präfixe, Fallback-Routen und Fusion-Jurys.",
      "subsections": [
        {
          "title": "Adressierungshierarchie",
          "table": {
            "headers": [
              "Addressing Type / Тип",
              "Example Request / Пример",
              "Routing Behavior / Поведение"
            ],
            "rows": [
              [
                "Canonical Slug",
                "gemini-2.5-flash",
                "Resolves to highest priority provider with healthy credentials"
              ],
              [
                "Provider-Qualified",
                "openrouter/meta-llama/llama-3.3-70b",
                "Forces execution strictly via specified upstream provider"
              ],
              [
                "Route Profile",
                "route/coding-fallback",
                "Executes multi-tier priority fallback chain on 429/5xx errors"
              ],
              [
                "Fusion Profile",
                "fusion/code-jury",
                "Parallel multi-model execution synthesized by a Judge LLM"
              ]
            ]
          }
        }
      ],
      "badge": "Addressing"
    },
    {
      "id": "ollama",
      "title": "Ollama API-Kompatibilität",
      "group": "models",
      "description": "Native Unterstützung für Ollama CLI, Continue.dev, Open WebUI und Obsidian Copilot ohne Anpassung des Client-Codes.",
      "subsections": [
        {
          "title": "Ollama CLI Integration",
          "code": {
            "title": "Bash / Terminal",
            "lang": "bash",
            "content": "# Point your local Ollama client or IDE extension to MyAIrouter\nexport OLLAMA_HOST=http://localhost:8000\n\n# View all registered models, route profiles, and fusion profiles\nollama list\n\n# Execute queries directly through the OpenAI-compatible gateway\nollama run gemini-2.5-flash \"Write a Fibonacci function in Go\" "
          }
        },
        {
          "title": "Unterstützte Ollama-Endpunkte",
          "table": {
            "headers": [
              "Endpoint / Эндпоинт",
              "Method / Метод",
              "Description / Описание"
            ],
            "rows": [
              [
                "/api/tags",
                "GET",
                "Returns list of all active models and route profiles formatted as Ollama tags"
              ],
              [
                "/api/show",
                "POST",
                "Returns detailed model parameters, template info, and context length"
              ],
              [
                "/api/version",
                "GET",
                "Returns gateway compatibility version info"
              ]
            ]
          }
        }
      ],
      "badge": "Drop-in Ollama"
    },
    {
      "id": "intelligence-ratings",
      "title": "Bewertungen & Benchmarks",
      "group": "models",
      "description": "Automatische Artificial Analysis-Metriken: Qualitätsindex (0-100), Generierungsgeschwindigkeit, Preise und Kontextfenster.",
      "subsections": [
        {
          "title": "Benchmark-Metriken",
          "table": {
            "headers": [
              "Metric / Показатель",
              "Range / Диапазон",
              "Description / Значение"
            ],
            "rows": [
              [
                "Quality Index",
                "0 — 100",
                "Composite intelligence index based on coding, math, reasoning, and instruction following"
              ],
              [
                "Output Speed",
                "10 — 300+ tok/s",
                "Median streaming completion velocity measured on real workloads"
              ],
              [
                "Context Window",
                "4K — 2M+ tokens",
                "Maximum active input context supported by the model architecture"
              ],
              [
                "Pricing (1M tokens)",
                "$0.05 — $60.00",
                "Estimated blended cost per million prompt and completion tokens"
              ]
            ]
          }
        }
      ],
      "badge": "Benchmarks"
    },
    {
      "id": "model-limits",
      "title": "API-Limits & Kontingente",
      "group": "models",
      "description": "Zweistufige Ratenbegrenzung: Schützen Sie Upstream-Konten mit RPM/TPM-Grenzen und steuern Sie Client-Kontingente.",
      "subsections": [
        {
          "title": "Zweistufige Limitüberwachung",
          "table": {
            "headers": [
              "Layer / Уровень",
              "Target / Объект",
              "Configurable Parameters",
              "Behavior on Limit"
            ],
            "rows": [
              [
                "Upstream Layer",
                "Provider Credential",
                "RPM limit, TPM limit, max concurrency",
                "Skips busy key, routes to next available healthy key"
              ],
              [
                "Client Router Layer",
                "Router API Key",
                "RPM, TPM, total requests quota, expiration",
                "Returns HTTP 429 Too Many Requests to client app"
              ]
            ]
          }
        }
      ],
      "badge": "Quotas & RPM"
    },
    {
      "id": "thinking-cot",
      "title": "Denkstufen & CoT",
      "group": "routing",
      "description": "Universeller Parameter reasoning_effort mit automatischer Übersetzung zwischen OpenAI, Anthropic, Google Gemini und Groq.",
      "subsections": [
        {
          "title": "Beispiel für Denkparameter",
          "code": {
            "title": "cURL Reasoning Request",
            "lang": "bash",
            "content": "# Send standard reasoning_effort to any provider\ncurl http://localhost:8000/v1/chat/completions \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\n    \"model\": \"gemini-2.5-flash\",\n    \"messages\": [{\"role\": \"user\", \"content\": \"Prove that the square root of 2 is irrational.\"}],\n    \"reasoning_effort\": \"high\"\n  }'"
          }
        },
        {
          "title": "Provider-Übersetzungsmatrix",
          "table": {
            "headers": [
              "Standard Parameter",
              "Anthropic Claude",
              "Google Gemini",
              "Groq / DeepSeek"
            ],
            "rows": [
              [
                "low",
                "thinking: { budget_tokens: 1024 }",
                "thinkingBudget: 1024",
                "reasoning_effort: low"
              ],
              [
                "medium",
                "thinking: { budget_tokens: 4096 }",
                "thinkingBudget: 4096",
                "reasoning_effort: medium"
              ],
              [
                "high",
                "thinking: { budget_tokens: 8192 }",
                "thinkingBudget: 8192",
                "reasoning_effort: high"
              ],
              [
                "none",
                "thinking: disabled",
                "thinkingBudget: 0",
                "reasoning_format: none"
              ]
            ]
          }
        }
      ],
      "badge": "Reasoning Effort"
    },
    {
      "id": "direct-routing",
      "title": "Direct-Routing-Engine",
      "group": "routing",
      "description": "Ultraschnelles Direct-Routing zu einem bestimmten Modell mit Round-Robin-Key-Balancing und automatischem Schlüssel-Failover.",
      "subsections": [
        {
          "title": "Direct-Routing Codebeispiel",
          "code": {
            "title": "Direct Routing Requests",
            "lang": "bash",
            "content": "# 1. Canonical slug (auto-resolves primary provider)\ncurl http://localhost:8000/v1/chat/completions \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\"model\": \"gemini-2.5-flash\", \"messages\": [{\"role\":\"user\",\"content\":\"Hello!\"}]}'\n\n# 2. Provider-qualified addressing (forces specific provider)\ncurl http://localhost:8000/v1/chat/completions \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\"model\": \"openrouter/meta-llama/llama-3.3-70b-instruct\", \"messages\": [{\"role\":\"user\",\"content\":\"Hello!\"}]}'"
          }
        }
      ],
      "badge": "Low Latency"
    },
    {
      "id": "priority-fallback",
      "title": "Prioritäts- & Fallback-Ketten",
      "group": "routing",
      "description": "Mehrstufige Ausfallwarteschlangen bei 429-Quotenüberschreitungen oder 5xx-Fehlern, mit verschachtelten Profilen und Schlüsselgruppen.",
      "subsections": [
        {
          "title": "Fallback-Funktionsweise",
          "table": {
            "headers": [
              "Feature / Возможность",
              "Configuration / Настройка",
              "Benefit / Преимущество"
            ],
            "rows": [
              [
                "Candidate Sequence",
                "Ordered list (Candidate 1 -> 2 -> 3)",
                "Ensures primary low-cost models are tried first before expensive fallbacks"
              ],
              [
                "Nested Profiles",
                "candidate_type: 'profile'",
                "Allows sharing base queues (e.g. embed route/standard inside route/premium)"
              ],
              [
                "Credential Groups",
                "credential_group: 'folder_name' or 'all'",
                "Restricts fallback candidate to team keys or enables full provider pool"
              ],
              [
                "Overrides",
                "temperature, context_length, reasoning",
                "Fine-tunes behavior per fallback step independently of request"
              ]
            ]
          }
        }
      ],
      "badge": "Nested Chains"
    },
    {
      "id": "fusion",
      "title": "Modell-Fusion (KI-Ensembles)",
      "group": "routing",
      "description": "Führen Sie mehrere LLMs parallel aus und synthetisieren Sie die beste Antwort mit einem Judge-Modell inklusive Echtzeit-Deliberations-Streaming.",
      "subsections": [
        {
          "title": "Streaming-Deliberation Beispiel",
          "code": {
            "title": "SSE Fusion Stream",
            "lang": "bash",
            "content": "curl http://localhost:8000/v1/chat/completions \\\n  -H \"Content-Type: application/json\" \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\n    \"model\": \"fusion/code-jury\",\n    \"messages\": [{\"role\": \"user\", \"content\": \"Analyze time complexity of quicksort\"}],\n    \"stream\": true\n  }'\n\n# Streamed SSE chunks contain real-time deliberation in reasoning_content:\n# data: {\"choices\":[{\"delta\":{\"reasoning_content\":\"### 🧬 Fusion Ensemble Deliberation\\n...\"}}]}\n# ...\n# data: {\"choices\":[{\"delta\":{\"content\":\"Final evaluated answer...\"}}]}"
          }
        },
        {
          "title": "Judge-Strategien",
          "table": {
            "headers": [
              "Strategy / Стратегия",
              "ID",
              "Operation / Принцип работы"
            ],
            "rows": [
              [
                "Best-of-N",
                "best_of_n",
                "Compares all candidate drafts and selects the highest scoring complete response"
              ],
              [
                "Consensus",
                "consensus",
                "Synthesizes a unified response combining best points and resolving discrepancies"
              ],
              [
                "Critique & Rewrite",
                "critique_and_rewrite",
                "Critiques weaknesses in each draft and writes a superior comprehensive answer"
              ]
            ]
          }
        }
      ],
      "badge": "AI Ensembles"
    },
    {
      "id": "providers",
      "title": "Unterstützte Provider & Keyless-Modus",
      "group": "management",
      "description": "Native Integration von über 12 Cloud-LLM-Providern und lokalen Runtimes, inklusive Keyless-Modus für lokale Ollama-Instanzen.",
      "subsections": [
        {
          "title": "Provider-Leistungsmatrix",
          "table": {
            "headers": [
              "Provider",
              "ID",
              "Default Base URL",
              "Keyless",
              "Streaming"
            ],
            "rows": [
              [
                "OpenAI",
                "openai",
                "https://api.openai.com/v1",
                "No",
                "Yes (SSE)"
              ],
              [
                "Google Gemini",
                "gemini",
                "https://generativelanguage.googleapis.com",
                "No",
                "Yes (SSE)"
              ],
              [
                "Anthropic",
                "anthropic",
                "https://api.anthropic.com/v1",
                "No",
                "Yes (SSE)"
              ],
              [
                "Groq",
                "groq",
                "https://api.groq.com/openai/v1",
                "No",
                "Yes (SSE)"
              ],
              [
                "Ollama (Local)",
                "ollama",
                "http://localhost:11434",
                "Yes",
                "Yes (SSE/NDJSON)"
              ],
              [
                "DeepSeek",
                "deepseek",
                "https://api.deepseek.com",
                "No",
                "Yes (SSE)"
              ],
              [
                "Cerebras",
                "cerebras",
                "https://api.cerebras.ai/v1",
                "No",
                "Yes (SSE)"
              ],
              [
                "OpenRouter",
                "openrouter",
                "https://openrouter.ai/api/v1",
                "No",
                "Yes (SSE)"
              ],
              [
                "Mistral AI",
                "mistral",
                "https://api.mistral.ai/v1",
                "No",
                "Yes (SSE)"
              ],
              [
                "xAI (Grok)",
                "xai",
                "https://api.x.ai/v1",
                "No",
                "Yes (SSE)"
              ]
            ]
          }
        },
        {
          "title": "Lokalen Ollama Keyless-Modus konfigurieren",
          "code": {
            "title": "Add Ollama via API or UI",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/credentials \\\n  -H \"Content-Type: application/json\" \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\" \\\n  -d '{\n    \"provider\": \"ollama\",\n    \"name\": \"Local Workstation Ollama\",\n    \"api_key\": \"keyless\",\n    \"base_url\": \"http://127.0.0.1:11434\",\n    \"is_active\": true\n  }'"
          }
        }
      ],
      "badge": "Multi-Provider",
      "highlights": [
        "Vollständige Unterstützung für OpenAI, Anthropic, Gemini, Groq, DeepSeek, Cerebras, Mistral, xAI, OpenRouter",
        "Keyless-Modus: Lokale Ollama (http://localhost:11434) ohne Schein-API-Schlüssel verbinden",
        "Benutzerdefinierte Base-URLs für vLLM, LM Studio und OpenAI-kompatible Gateways",
        "Dedizierte HTTP/SOCKS5-Proxy-Bindung pro Provider-Anmeldedaten"
      ]
    },
    {
      "id": "credentials",
      "title": "Upstream-Anmeldedaten & Key-Vault",
      "group": "management",
      "description": "Bankenkonforme, verschlüsselte Speicherung für Upstream-API-Schlüssel mit Health-Checks, Auto-Disable und Gruppenverwaltung.",
      "subsections": [
        {
          "title": "Manuelle Health-Überprüfung anstoßen",
          "code": {
            "title": "Health Check Endpoint",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/credentials/cred_abc123/health-check \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\"\n\n# Response:\n# {\n#   \"status\": \"healthy\",\n#   \"latency_ms\": 142.5,\n#   \"checked_at\": \"2026-09-13T14:15:00Z\"\n# }"
          }
        }
      ],
      "badge": "Encrypted Vault",
      "highlights": [
        "Symmetrische AES-128-CBC Fernet-Verschlüsselung vor dem Speichern in SQLite",
        "Schlüssel-Maskierung: Rohe Schlüssel werden niemals in UI oder Logs angezeigt (z. B. sk-ant...7a9f)",
        "Proaktive Health-Checks: Regelmäßige Überprüfung der Gültigkeit und Quoten bei Providern",
        "Anmeldedaten-Gruppen: Strukturierung in logische Ordner (Produktion, Staging, Backup)"
      ]
    },
    {
      "id": "api-keys",
      "title": "Router-API-Schlüssel & Berechtigungen",
      "group": "management",
      "description": "Erstellen, überwachen und widerrufen Sie Client-Token (sk-router-...) mit individuellen RPM/TPM-Limits und Modell-Whitelists.",
      "subsections": [
        {
          "title": "Client-Schlüssel Parameter",
          "table": {
            "headers": [
              "Field",
              "Type",
              "Default",
              "Description"
            ],
            "rows": [
              [
                "name",
                "string",
                "Required",
                "Human-readable label for the client or application"
              ],
              [
                "rate_limit_rpm",
                "integer",
                "null (unlimited)",
                "Maximum allowed HTTP requests per 60-second window"
              ],
              [
                "rate_limit_tpm",
                "integer",
                "null (unlimited)",
                "Maximum total tokens allowed per 60-second window"
              ],
              [
                "allowed_models",
                "string[]",
                "null (all models)",
                "Array of model slugs permitted for inference"
              ],
              [
                "expires_at",
                "ISO string",
                "null (never)",
                "UTC timestamp after which requests return HTTP 401"
              ]
            ]
          }
        }
      ],
      "badge": "Access Governance",
      "highlights": [
        "SHA-256 One-Way-Hash: Geheime Schlüssel werden niemals im Klartext in der Datenbank gespeichert",
        "Ratenbegrenzung: Granulare Limits für Anfragen pro Minute (RPM) und Tokens pro Minute (TPM)",
        "Modell-Whitelist: Beschränken Sie Schlüssel auf ausgewählte Modelle oder Routing-Profile",
        "Automatischer Ablauf: Festlegen von Ablaufdaten für temporäre Test- oder Team-Schlüssel"
      ]
    },
    {
      "id": "proxies",
      "title": "Proxy-Verwaltung & Geo-Tagging",
      "group": "management",
      "description": "Leiten Sie Upstream-Traffic über authentifizierte HTTP- und SOCKS5-Proxies mit Latenz-Benchmarks und Geo-Länder-Tags.",
      "subsections": [
        {
          "title": "Proxy-Format-Beispiele",
          "code": {
            "title": "Supported Proxy URI Formats",
            "lang": "bash",
            "content": "# Standard HTTP proxy:\nhttp://proxy.corporate.internal:8080\n\n# Authenticated HTTP proxy:\nhttp://username:<PROXY_PASSWORD>@us-east.proxy-vendor.com:3128\n\n# Authenticated SOCKS5 proxy:\nsocks5://proxyuser:<PROXY_PASSWORD>@sg-node.vpn-provider.net:1080"
          }
        }
      ],
      "badge": "Egress & Geo",
      "highlights": [
        "Vollständige Protokollunterstützung: HTTP, HTTPS und SOCKS5 (socks5://user:pass@host:port)",
        "Länder-Tags: ISO-Codes (US, DE, SG, JP) zuweisen, um regionale Anforderungen zu erfüllen",
        "Latenz-Messung: Echtzeit-RTT-Test beim Speichern und bei periodischen Health-Checks",
        "Isolierung pro Anmeldedaten: Dedizierte Proxies einzelnen Schlüsseln oder Providern zuweisen"
      ]
    },
    {
      "id": "backup-restore",
      "title": "Verschlüsseltes Backup & Disaster Recovery",
      "group": "system",
      "description": "Exportieren und Wiederherstellen vollständiger Router-Konfigurationen mit Passphrase-basiertem AES-GCM-Schutz.",
      "subsections": [
        {
          "title": "Backup per API exportieren",
          "code": {
            "title": "Encrypted Backup Endpoint",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/system/backup \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{\"passphrase\": \"<BACKUP_PASSPHRASE>\"}' \\\n  -o router_backup_2026-09-13.enc"
          }
        }
      ],
      "badge": "Disaster Recovery",
      "highlights": [
        "PBKDF2 HMAC-SHA256-Schlüsselableitung mit 16-Byte-Salt und AES-256-GCM-Authentifizierung",
        "Vollständiger System-Snapshot: Modelle, Provider-Keys, Routen, Fusion-Juries, Proxies, API-Keys",
        "Selektive oder vollständige Wiederherstellung: Daten zusammenführen oder sauber ersetzen",
        "Kein Vendor-Lock-in: Nahtlose Migration zwischen VPS-Instanzen, Docker-Containern und Cloud-Zonen"
      ]
    },
    {
      "id": "analytics",
      "title": "Analytik, Logs & Trace-Inspektor",
      "group": "system",
      "description": "Vollständige Traffic-Telemetrie mit Token-Abrechnung, Kostenschätzung, Latenzdiagrammen und interaktiver Waterfall-Trace-Analyse.",
      "subsections": [
        {
          "title": "Log-Eintrags-Schema",
          "table": {
            "headers": [
              "Field",
              "Type",
              "Description"
            ],
            "rows": [
              [
                "id",
                "string (UUID)",
                "Unique identifier for the inference request transaction"
              ],
              [
                "timestamp",
                "ISO 8601",
                "UTC start time when client request was received"
              ],
              [
                "client_key_id",
                "string",
                "ID of the authorizing client API key (or 'master' / 'anon')"
              ],
              [
                "model_requested",
                "string",
                "Raw model parameter received in the client payload"
              ],
              [
                "model_resolved",
                "string",
                "Canonical model slug and provider that fulfilled the request"
              ],
              [
                "status_code",
                "integer",
                "Final HTTP response status returned to client (e.g. 200, 429, 502)"
              ],
              [
                "latency_ms",
                "float",
                "Total end-to-end response duration in milliseconds"
              ],
              [
                "prompt_tokens",
                "integer",
                "Token count of input messages"
              ],
              [
                "completion_tokens",
                "integer",
                "Token count of generated response (including reasoning)"
              ],
              [
                "cost_usd",
                "float",
                "Calculated monetary cost based on upstream token tariffs"
              ]
            ]
          }
        }
      ],
      "badge": "Observability",
      "highlights": [
        "Dreifache Token-Abrechnung: Separate Erfassung von Prompt-, Completion- und Reasoning-Tokens",
        "Waterfall-Failover-Inspektor: Schrittweise visuelle Analyse jedes Hops, Timeouts und Wiederholungsversuchs",
        "Kostenschätzung: Echtzeit-Berechnung in USD basierend auf aktuellen Provider-Preisen",
        "Exportierbares Audit-Protokoll: Filtern und Herunterladen von Logs nach Statuscode, Client-Key oder Datum"
      ]
    },
    {
      "id": "circuit-breaker",
      "title": "Circuit Breaker & Fehlerisolation",
      "group": "system",
      "description": "Finite-State-Machine, die Anfragen an fehlerhafte oder überlastete Provider stoppt und Clients vor Kaskaden-Timeouts schützt.",
      "subsections": [
        {
          "title": "FSM-Zustandslebenszyklus",
          "table": {
            "headers": [
              "Transition",
              "Condition",
              "Action Taken"
            ],
            "rows": [
              [
                "CLOSED -> OPEN",
                "5 consecutive failures (5xx / Timeout)",
                "Trip circuit breaker; mark credential unavailable; start 30s timer"
              ],
              [
                "OPEN -> HALF-OPEN",
                "Cooldown timer (30s) expires",
                "Allow 1 probe request through to verify upstream availability"
              ],
              [
                "HALF-OPEN -> CLOSED",
                "Probe succeeds with HTTP 200",
                "Reset failure count to 0; restore credential to active rotation pool"
              ],
              [
                "HALF-OPEN -> OPEN",
                "Probe fails or times out",
                "Restart 30s cooldown timer; keep credential isolated"
              ]
            ]
          }
        }
      ],
      "badge": "Resilience Engine",
      "highlights": [
        "3 Betriebszustände: CLOSED (gesund), OPEN (isoliert, Traffic umgeleitet), HALF-OPEN (Erholungstest)",
        "Auslösebedingung: Aktivierung nach 5 aufeinanderfolgenden 5xx-Fehlern oder Timeouts",
        "Abkühlphase: Leitet Anfragen für 30 Sekunden um, bevor eine einzelne Probe-Anfrage gesendet wird",
        "Transparent für Clients: Nächster Kandidat in der Fallback-Kette übernimmt sofort ohne Client-Fehler"
      ]
    },
    {
      "id": "api-reference",
      "title": "Vollständige API-Endpunkt-Referenz",
      "group": "system",
      "description": "Vollständiger Index aller öffentlichen Inferenz- und Administrations-REST-Endpunkte des MyAIrouter-Servers.",
      "subsections": [
        {
          "title": "Tabelle öffentlicher und administrativer Endpunkte",
          "table": {
            "headers": [
              "Method",
              "Path",
              "Auth Scheme",
              "Purpose"
            ],
            "rows": [
              [
                "POST",
                "/v1/chat/completions",
                "Bearer sk-router-...",
                "OpenAI-compatible text & vision chat completion (streaming supported)"
              ],
              [
                "GET",
                "/v1/models",
                "Bearer sk-router-...",
                "List all active models, aliases, fallback routes, and fusion juries"
              ],
              [
                "GET",
                "/api/tags",
                "Optional / None",
                "Ollama protocol: enumerate locally installed and routed models"
              ],
              [
                "POST",
                "/api/show",
                "Optional / None",
                "Ollama protocol: inspect model architecture, parameters, and license"
              ],
              [
                "GET",
                "/api/version",
                "None",
                "Ollama protocol: returns Ollama compatibility version tag"
              ],
              [
                "GET",
                "/api/v1/credentials",
                "Admin Session / Token",
                "List encrypted upstream provider credentials with health metrics"
              ],
              [
                "POST",
                "/api/v1/routes",
                "Admin Session / Token",
                "Create or update Priority Fallback route policies"
              ],
              [
                "POST",
                "/api/v1/fusion",
                "Admin Session / Token",
                "Create or update Model Fusion jury configurations"
              ],
              [
                "GET",
                "/api/v1/system/stats",
                "Admin Session / Token",
                "Retrieve real-time token volume, latency distributions, and costs"
              ],
              [
                "POST",
                "/api/v1/system/backup",
                "Admin Session / Token",
                "Generate encrypted passphrase-protected JSON backup archive"
              ]
            ]
          }
        }
      ],
      "badge": "REST Reference",
      "highlights": [
        "OpenAI-Eingang: /v1/chat/completions, /v1/models (vollständig kompatibel mit allen OpenAI-Clients)",
        "Ollama-Protokoll: /api/tags, /api/show, /api/version, /api/chat",
        "Kernverwaltung: /api/v1/credentials, /api/v1/models, /api/v1/routes, /api/v1/fusion",
        "System & Gesundheit: /health, /api/v1/system/backup, /api/v1/system/restore, /api/v1/system/stats"
      ]
    },
    {
      "id": "errors",
      "title": "HTTP-Fehlercodes & Fehlerbehebung",
      "group": "system",
      "description": "Detaillierte Aufschlüsselung der vom Router zurückgegebenen HTTP-Statuscodes, JSON-Fehlerformate und Fehlerbehebungsschritte.",
      "subsections": [
        {
          "title": "Katalog der HTTP-Statuscodes",
          "table": {
            "headers": [
              "Status",
              "Error Name",
              "Likely Cause",
              "Resolution"
            ],
            "rows": [
              [
                "400",
                "Bad Request",
                "Malformed JSON body or invalid parameter type",
                "Verify JSON syntax and data types against API specification"
              ],
              [
                "401",
                "Unauthorized",
                "Missing or invalid Bearer sk-router-... API key",
                "Generate a valid client API key in Admin UI and pass in Authorization header"
              ],
              [
                "403",
                "Forbidden",
                "Client key exists but requested model is not whitelisted",
                "Add the requested model to allowed_models in client key settings"
              ],
              [
                "404",
                "Not Found",
                "Requested model slug does not exist in router database",
                "Check /v1/models or create a model mapping / fallback route in router"
              ],
              [
                "422",
                "Unprocessable Entity",
                "Pydantic validation failed on payload fields",
                "Inspect error response details to locate offending field and type mismatch"
              ],
              [
                "429",
                "Rate Limit Exceeded",
                "Client exceeded configured RPM or TPM quota, or upstream 429",
                "Reduce request concurrency or increase RPM/TPM thresholds in client key settings"
              ],
              [
                "502",
                "Bad Gateway",
                "All upstream provider candidates failed or returned errors",
                "Verify upstream API keys, network connectivity, and proxy settings in router"
              ],
              [
                "504",
                "Gateway Timeout",
                "Upstream provider took longer than timeout threshold",
                "Increase model timeout limit or configure fallback route to faster provider (Groq/Cerebras)"
              ]
            ]
          }
        }
      ],
      "badge": "Troubleshooting",
      "highlights": [
        "Standardisiertes OpenAI-Fehlerschema: {\"error\": {\"message\": \"...\", \"type\": \"...\", \"code\": \"...\"}}",
        "Klare Unterscheidung: Trennt Client-Fehler (4xx) sauber von Upstream-Provider-Ausfällen (502/504)",
        "Handlungsorientierte Diagnose: Präzise Meldungen zeigen, ob Quote, Authentifizierung oder Modell fehlten",
        "Ratenlimit-Hinweise: 429-Antworten liefern klare Informationen zur Wiederholung nach RPM/TPM-Überschreitung"
      ]
    },
    {
      "id": "env-config",
      "title": "Umgebungsvariablen & Deployment",
      "group": "system",
      "description": "Konfigurationsoptionen für den produktiven Betrieb von MyAIrouter mit Docker, PostgreSQL, systemd und Sicherheitsrichtlinien.",
      "subsections": [
        {
          "title": "Wichtige Umgebungsvariablen",
          "table": {
            "headers": [
              "Variable",
              "Default",
              "Required",
              "Description"
            ],
            "rows": [
              [
                "ROUTER_MASTER_KEY",
                "(generated on first run)",
                "Recommended",
                "32-byte Base64 key for Fernet symmetric encryption of all API secrets"
              ],
              [
                "DATABASE_URL",
                "sqlite+aiosqlite:///./router.db",
                "No",
                "Async SQLAlchemy connection string (e.g. postgresql+asyncpg://user:pass@host/db)"
              ],
              [
                "ROUTER_HOST",
                "0.0.0.0",
                "No",
                "Network interface IP to bind the HTTP server listener"
              ],
              [
                "ROUTER_PORT",
                "8000",
                "No",
                "TCP port on which the router receives inference and admin traffic"
              ],
              [
                "LOG_LEVEL",
                "INFO",
                "No",
                "Logging verbosity: DEBUG, INFO, WARNING, ERROR, CRITICAL"
              ],
              [
                "DEFAULT_TIMEOUT",
                "60.0",
                "No",
                "Default timeout in seconds for upstream provider requests before fallback"
              ],
              [
                "CORS_ORIGINS",
                "*",
                "No",
                "Allowed origins for Cross-Origin Resource Sharing headers"
              ],
              [
                "OLLAMA_BASE_URL",
                "http://localhost:11434",
                "No",
                "Target host URL for discovering and routing to local Ollama models"
              ]
            ]
          }
        },
        {
          "title": "Produktions-Docker-Compose-Beispiel",
          "code": {
            "title": "docker-compose.prod.yml",
            "lang": "yaml",
            "content": "version: \"3.8\"\n\nservices:\n  myairouter:\n    image: myairouter:latest\n    restart: always\n    ports:\n      - \"8000:8000\"\n    environment:\n      - ROUTER_MASTER_KEY=<GENERATED_ROUTER_MASTER_KEY>\n      - DATABASE_URL=postgresql+asyncpg://router:<POSTGRES_PASSWORD>@postgres:5432/routerdb\n      - ROUTER_PORT=8000\n      - ROUTER_HOST=0.0.0.0\n      - LOG_LEVEL=INFO\n      - DEFAULT_TIMEOUT=45.0\n      - CORS_ORIGINS=https://ai.yourcompany.internal\n    depends_on:\n      - postgres\n\n  postgres:\n    image: postgres:16-alpine\n    restart: always\n    environment:\n      POSTGRES_USER: router\n      POSTGRES_PASSWORD: <POSTGRES_PASSWORD>\n      POSTGRES_DB: routerdb\n    volumes:\n      - pgdata:/var/lib/postgresql/data\n\nvolumes:\n  pgdata:"
          }
        }
      ],
      "badge": "Deployment",
      "highlights": [
        "ROUTER_MASTER_KEY: Kritischer 32-Byte-Base64-Schlüssel zur Verschlüsselung aller Anmeldedaten",
        "DATABASE_URL: Wechsel von Standard-SQLite zu hochverfügbarem PostgreSQL",
        "CORS_ORIGINS: Kommagetrennte Liste erlaubter Origins für sicheren Web-Frontend-Zugriff",
        "OLLAMA_BASE_URL: Standard-Erkennungs-URL für den Ollama-Dienst (Standard: http://localhost:11434)"
      ]
    }
  ]
};
