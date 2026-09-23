import { DocContent } from "./types";

export const be: DocContent = {
  "ui": {
    "searchPlaceholder": "Пошук па дакументацыі (напрыклад, Ollama, Fallback, Fusion)...",
    "noSectionsFound": "Раздзелы дакументацыі не знойдзены.",
    "prevSection": "Папярэдні раздзел",
    "nextSection": "Наступны раздзел",
    "copied": "Скапіявана!",
    "copy": "Скапіяваць код",
    "endpoints": "Эндпоінты",
    "tocTitle": "Змест"
  },
  "sections": [
    {
      "id": "overview",
      "title": "Агляд сістэмы",
      "group": "intro",
      "description": "Універсальны self-hosted ШІ-шлюз з 3 рухавікамі маршрутызацыі (Direct, Priority Fallback, Fusion), пулам ключоў і падтрымкай OpenAI і Ollama.",
      "subsections": [
        {
          "title": "Параўнанне рухавікоў маршрутызацыі",
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
        "3 рухавікі маршрутызацыі: Прамы, Прыярытэтны Fallback (укладзены), Ансамбль Model Fusion",
        "Поўная сумяшчальнасць з OpenAI API (/v1/chat/completions) і Ollama (/api/tags, /api/show)",
        "Надзейнае шыфраванне ключоў: AES-128-CBC Fernet пад кіраваннем ROUTER_MASTER_KEY",
        "Аўтаматычны Circuit Breaker з самааднаўленнем і прывязкай геа-проксі"
      ]
    },
    {
      "id": "quickstart",
      "title": "Хуткі старт",
      "group": "intro",
      "description": "Падключэнне любой бібліятэкі OpenAI SDK, cURL або Ollama-кліента да шлюза MyAIrouter за лічаныя секунды.",
      "subsections": [
        {
          "title": "1. Хуткі выклік праз cURL",
          "code": {
            "title": "cURL Chat Completion",
            "lang": "bash",
            "content": "curl http://localhost:8000/v1/chat/completions \\\n  -H \"Content-Type: application/json\" \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\n    \"model\": \"gemini-2.5-flash\",\n    \"messages\": [{\"role\": \"user\", \"content\": \"Explain quantum computing in one sentence.\"}],\n    \"temperature\": 0.7\n  }'"
          }
        },
        {
          "title": "2. Python SDK (OpenAI)",
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
      "title": "Адрасацыя і выбар мадэляў",
      "group": "models",
      "description": "Гнуткая шматузроўневая адрасацыя мадэляў: кананічныя slug-імёны, прамыя шляхі правайдэраў, ланцужкі fallback і ансамблі fusion.",
      "subsections": [
        {
          "title": "Іерархія адрасацыі мадэляў",
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
      "title": "Сумяшчальнасць з Ollama API",
      "group": "models",
      "description": "Натыўная сумяшчальнасць з утылітай Ollama CLI, плагінамі Continue.dev, Open WebUI і Obsidian Copilot без змен у кліенцкім кодзе.",
      "subsections": [
        {
          "title": "Выкарыстанне праз Ollama CLI",
          "code": {
            "title": "Bash / Terminal",
            "lang": "bash",
            "content": "# Point your local Ollama client or IDE extension to MyAIrouter\nexport OLLAMA_HOST=http://localhost:8000\n\n# View all registered models, route profiles, and fusion profiles\nollama list\n\n# Execute queries directly through the OpenAI-compatible gateway\nollama run gemini-2.5-flash \"Write a Fibonacci function in Go\" "
          }
        },
        {
          "title": "Падтрымліваемыя эндпоінты Ollama",
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
      "title": "Рэйтынгі і бенчмаркі",
      "group": "models",
      "description": "Аўтаматычная інтэграцыя бенчмаркаў Artificial Analysis: індэкс якасці (0-100), хуткасць генерацыі (ток/с), кошт і кантэкст.",
      "subsections": [
        {
          "title": "Ключавыя паказчыкі мадэляў",
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
      "title": "Ліміты API і квоты",
      "group": "models",
      "description": "Двухузроўневае абмежаванне хуткасці: абарона upstream-акаўнтаў (RPM/TPM па ключах) і кантроль квот кліентаў шлюза.",
      "subsections": [
        {
          "title": "Двухузроўневы кантроль лімітаў",
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
      "title": "Узроўні разваг (CoT)",
      "group": "routing",
      "description": "Універсальны параметр reasoning_effort з двухбаковай трансляцыяй фарматаў паміж OpenAI, Anthropic, Google Gemini і Groq.",
      "subsections": [
        {
          "title": "Прыклад запыту з reasoning_effort",
          "code": {
            "title": "cURL Reasoning Request",
            "lang": "bash",
            "content": "# Send standard reasoning_effort to any provider\ncurl http://localhost:8000/v1/chat/completions \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\n    \"model\": \"gemini-2.5-flash\",\n    \"messages\": [{\"role\": \"user\", \"content\": \"Prove that the square root of 2 is irrational.\"}],\n    \"reasoning_effort\": \"high\"\n  }'"
          }
        },
        {
          "title": "Матрыца трансляцыі параметраў",
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
      "title": "Прамая маршрутызацыя (Direct)",
      "group": "routing",
      "description": "Высокахуткасная прамая адпраўка запыту ў канкрэтную мадэль з балансаваннем Round-robin і імгненным пераключэннем ключоў.",
      "subsections": [
        {
          "title": "Прыклады прамога звароту",
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
      "title": "Прыярытэты і Fallback",
      "group": "routing",
      "description": "Шматузроўневыя чэргі пераключэння пры 429 лімітах або 5xx памылках, падтрымка ўкладзеных профіляў і груп ключоў.",
      "subsections": [
        {
          "title": "Прынцып працы ланцужка",
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
      "title": "Model Fusion (Ансамблі ШІ)",
      "group": "routing",
      "description": "Паралельнае выкананне некалькіх мадэляў і сінтэз эталоннага адказу мадэллю-суддзёй з струменевай перадачай ходу разваг.",
      "subsections": [
        {
          "title": "Струменевы вывад ходу абмеркавання",
          "code": {
            "title": "SSE Fusion Stream",
            "lang": "bash",
            "content": "curl http://localhost:8000/v1/chat/completions \\\n  -H \"Content-Type: application/json\" \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\n    \"model\": \"fusion/code-jury\",\n    \"messages\": [{\"role\": \"user\", \"content\": \"Analyze time complexity of quicksort\"}],\n    \"stream\": true\n  }'\n\n# Streamed SSE chunks contain real-time deliberation in reasoning_content:\n# data: {\"choices\":[{\"delta\":{\"reasoning_content\":\"### 🧬 Fusion Ensemble Deliberation\\n...\"}}]}\n# ...\n# data: {\"choices\":[{\"delta\":{\"content\":\"Final evaluated answer...\"}}]}"
          }
        },
        {
          "title": "Стратэгіі працы суддзі",
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
      "title": "Падтрымліваемыя правайдэры і Keyless-рэжым",
      "group": "management",
      "description": "Натыўная інтэграцыя з 12+ воблачнымі правайдэрамі і лакальнымі асяроддзямі, уключаючы Keyless-рэжым для ўласнага інстанса Ollama.",
      "subsections": [
        {
          "title": "Матрыца магчымасцей правайдэраў",
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
          "title": "Налада Keyless-рэжыму для Ollama",
          "code": {
            "title": "Add Ollama via API or UI",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/credentials \\\n  -H \"Content-Type: application/json\" \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\" \\\n  -d '{\n    \"provider\": \"ollama\",\n    \"name\": \"Local Workstation Ollama\",\n    \"api_key\": \"keyless\",\n    \"base_url\": \"http://127.0.0.1:11434\",\n    \"is_active\": true\n  }'"
          }
        }
      ],
      "badge": "Multi-Provider",
      "highlights": [
        "Падтрымка OpenAI, Anthropic, Gemini, Groq, DeepSeek, Cerebras, Mistral, xAI, OpenRouter",
        "Keyless-рэжым: падключэнне лакальнай Ollama (http://localhost:11434) без фіктыўных ключоў",
        "Уласны Base URL для vLLM, LM Studio і карпаратыўных OpenAI-сумяшчальных шлюзаў",
        "Прывязка вылучаных HTTP/SOCKS5 проксі да ўліковых запісаў правайдэраў"
      ]
    },
    {
      "id": "credentials",
      "title": "Кіраванне ключамі правайдэраў (Vault)",
      "group": "management",
      "description": "Сховішча API-ключаў з банкаўскім шыфраваннем, аўтаматычнай праверкай працаздольнасці і групаваннем па папках.",
      "subsections": [
        {
          "title": "Ручны запуск праверкі ключа",
          "code": {
            "title": "Health Check Endpoint",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/credentials/cred_abc123/health-check \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\"\n\n# Response:\n# {\n#   \"status\": \"healthy\",\n#   \"latency_ms\": 142.5,\n#   \"checked_at\": \"2026-09-13T14:15:00Z\"\n# }"
          }
        }
      ],
      "badge": "Encrypted Vault",
      "highlights": [
        "Сіметрычнае шыфраванне AES-128-CBC Fernet: ключы шыфруюцца перад запісам у SQLite",
        "Маскіраванне ключоў: сакрэты ніколі не перадаюцца ў інтэрфейс (напрыклад, sk-ant...7a9f)",
        "Аўтаматычныя Health-чэкі: рэгулярная праверка валіднасці ключоў і квот правайдэра",
        "Групы ўліковых запісаў: падзел ключоў па папках (Production, Staging, Backup, Team)"
      ]
    },
    {
      "id": "api-keys",
      "title": "Кліенцкія API-ключы і правы доступу",
      "group": "management",
      "description": "Выпуск, маніторынг і адкліканне кліенцкіх токенаў доступу (sk-router-...) з індывідуальнымі лімітамі RPM/TPM і белымі спісамі мадэляў.",
      "subsections": [
        {
          "title": "Параметры кліенцкага ключа",
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
        "Незваротнае хэшаванне SHA-256: сакрэтныя ключы не захоўваюцца ў адкрытым выглядзе ў БД",
        "Квоты і ліміты: асобны кантроль запытаў у хвіліну (RPM) і токенаў у хвіліну (TPM)",
        "Белыя спісы мадэляў: абмежаванне доступу толькі да дазволеных мадэляў і профіляў",
        "Тэрмін дзеяння (TTL): аўтаматычнае адключэнне ключоў пасля заканчэння пазначанай даты"
      ]
    },
    {
      "id": "proxies",
      "title": "Проксі-серверы і геа-маршрутызацыя",
      "group": "management",
      "description": "Маршрутызацыя запытаў да правайдэраў праз HTTP і SOCKS5 проксі з вымярэннем затрымкі і абыходам блакаванняў.",
      "subsections": [
        {
          "title": "Фарматы URI проксі-сервераў",
          "code": {
            "title": "Supported Proxy URI Formats",
            "lang": "bash",
            "content": "# Standard HTTP proxy:\nhttp://proxy.corporate.internal:8080\n\n# Authenticated HTTP proxy:\nhttp://username:<PROXY_PASSWORD>@us-east.proxy-vendor.com:3128\n\n# Authenticated SOCKS5 proxy:\nsocks5://proxyuser:<PROXY_PASSWORD>@sg-node.vpn-provider.net:1080"
          }
        }
      ],
      "badge": "Egress & Geo",
      "highlights": [
        "Падтрымка пратаколаў: HTTP, HTTPS і SOCKS5 (socks5://user:pass@host:port)",
        "Геа-меткі краін: прывязка ISO-кодаў (US, DE, SG, JP) для абыходу абмежаванняў правайдэраў",
        "Замер пінгу і затрымкі: аўтаматычны тэст RTT пры даданні і планавай праверцы",
        "Ізаляцыя на ўзроўні ключа: прывязка вылучанага проксі да канкрэтнага ключа ці правайдэра"
      ]
    },
    {
      "id": "backup-restore",
      "title": "Рэзервовае капіраванне і аднаўленне",
      "group": "system",
      "description": "Экспарт і імпарт поўнай канфігурацыі шлюза з шыфраваннем AES-GCM па паролі (мадэлі, маршруты, ключы, проксі і кліенты).",
      "subsections": [
        {
          "title": "Экспарт рэзервовай копіі праз API",
          "code": {
            "title": "Encrypted Backup Endpoint",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/system/backup \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{\"passphrase\": \"<BACKUP_PASSPHRASE>\"}' \\\n  -o router_backup_2026-09-13.enc"
          }
        }
      ],
      "badge": "Disaster Recovery",
      "highlights": [
        "Дэрывацыя ключа PBKDF2 HMAC-SHA256 з выпадковай соллю 16 байт і аўтэнтыфікацыяй AES-256-GCM",
        "Поўны здымак сістэмы: мадэлі, ключы правайдэраў, профілі маршрутаў, журы Fusion, проксі і кліенты",
        "Гнуткае аднаўленне: магчымасць аб'яднання з існуючымі запісамі або поўнага перазапісу",
        "Адсутнасць прывязкі: імгненны перанос паміж серверамі, VPS і Docker-кантэйнерамі"
      ]
    },
    {
      "id": "analytics",
      "title": "Аналітыка, логі і Waterfall-трасіроўка",
      "group": "system",
      "description": "Скразная тэлеметрыя трафіка з улікам токенаў, разлікам выдаткаў, графікамі затрымак і інтэрактыўнай Waterfall-трасіроўкай.",
      "subsections": [
        {
          "title": "Схема запісу лога",
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
        "Трохмерны ўлік токенаў: асобны падлік prompt-, completion- і reasoning-токенаў",
        "Waterfall-трасіроўка: пакрокавая візуалізацыя кожнай спробы, таймаўта і пераключэння на fallback",
        "Фінансавы ўлік: разлік ацэначнага кошту ў USD на аснове тарыфаў правайдэраў",
        "Экспарт аўдыту: фільтрацыя і выгрузка логаў па статусах адказаў, кліентах, мадэлях і датах"
      ]
    },
    {
      "id": "circuit-breaker",
      "title": "Circuit Breaker і ізаляцыя збояў",
      "group": "system",
      "description": "Аўтамат станаў, які ізалюе нестабільных або перагружаных правайдэраў, абараняючы кліенцкія праграмы ад каскадных таймаўтаў.",
      "subsections": [
        {
          "title": "Жыццёвы цыкл станаў аўтамата",
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
        "3 працоўныя станы: CLOSED (норма, трафік ідзе), OPEN (ізаляваны, перанакіраванне), HALF-OPEN (праверка)",
        "Парог спрацоўвання: аўтаматычнае размыканне пасля 5 запар памылак 5xx або таймаўтаў",
        "Перыяд астуджэння: 30 секунд утрымання перад адпраўкай спробнага запыту для праверкі даступнасці",
        "Незаўважна для кліентаў: наступны кандыдат у профілі Fallback імгненна апрацоўвае запыт без памылак"
      ]
    },
    {
      "id": "api-reference",
      "title": "Поўны даведнік REST API",
      "group": "system",
      "description": "Поўны каталог усіх публічных эндпоінтаў інферэнсу і адміністрацыйных інтэрфейсаў кіравання шлюзам MyAIrouter.",
      "subsections": [
        {
          "title": "Табліца публічных і адміністрацыйных эндпоінтаў",
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
        "Сумяшчальнасць з OpenAI: /v1/chat/completions, /v1/models (прамая замена ў любых SDK)",
        "Пратакол Ollama: /api/tags, /api/show, /api/version, /api/chat",
        "Кіраванне канфігурацыяй: /api/v1/credentials, /api/v1/models, /api/v1/routes, /api/v1/fusion",
        "Сістэма і маніторынг: /health, /api/v1/system/backup, /api/v1/system/restore, /api/v1/system/stats"
      ]
    },
    {
      "id": "errors",
      "title": "Коды памылак HTTP і дыягностыка",
      "group": "system",
      "description": "Падрабязны разбор кодаў стану HTTP, якія вяртаюцца шлюзам, спецыфікацыя фармату памылак JSON і інструкцыі па іх выпраўленні.",
      "subsections": [
        {
          "title": "Каталог кодаў стану HTTP",
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
        "Стандартная схема памылак OpenAI: {\"error\": {\"message\": \"...\", \"type\": \"...\", \"code\": \"...\"}}",
        "Выразнае раздзяленне: размежаванне памылак кліента (4xx) і збояў правайдэраў (502/504)",
        "Інфарматыўныя апісанні: паведамленні паказваюць канкрэтную прычыну (няслушны ключ, вычарпаны ліміт або мадэль не знойдзена)",
        "Апрацоўка Rate Limit: адказы 429 змяшчаюць інфармацыю аб перавышэнні лімітаў RPM або TPM"
      ]
    },
    {
      "id": "env-config",
      "title": "Пераменныя асяроддзя і дэплой",
      "group": "system",
      "description": "Поўны пералік параметраў канфігурацыі для прамысловага разгортвання MyAIrouter з Docker, PostgreSQL і systemd.",
      "subsections": [
        {
          "title": "Асноўныя пераменныя асяроддзя",
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
          "title": "Прыклад Docker Compose для продакшана",
          "code": {
            "title": "docker-compose.prod.yml",
            "lang": "yaml",
            "content": "version: \"3.8\"\n\nservices:\n  myairouter:\n    image: myairouter:latest\n    restart: always\n    ports:\n      - \"8000:8000\"\n    environment:\n      - ROUTER_MASTER_KEY=<GENERATED_ROUTER_MASTER_KEY>\n      - DATABASE_URL=postgresql+asyncpg://router:<POSTGRES_PASSWORD>@postgres:5432/routerdb\n      - ROUTER_PORT=8000\n      - ROUTER_HOST=0.0.0.0\n      - LOG_LEVEL=INFO\n      - DEFAULT_TIMEOUT=45.0\n      - CORS_ORIGINS=https://ai.yourcompany.internal\n    depends_on:\n      - postgres\n\n  postgres:\n    image: postgres:16-alpine\n    restart: always\n    environment:\n      POSTGRES_USER: router\n      POSTGRES_PASSWORD: <POSTGRES_PASSWORD>\n      POSTGRES_DB: routerdb\n    volumes:\n      - pgdata:/var/lib/postgresql/data\n\nvolumes:\n  pgdata:"
          }
        }
      ],
      "badge": "Deployment",
      "highlights": [
        "ROUTER_MASTER_KEY: крытычна важны 32-байтны base64 ключ для шыфравання ўсіх сакрэтаў у БД",
        "DATABASE_URL: пераключэнне са стандартнай SQLite на высоканагружаную PostgreSQL",
        "CORS_ORIGINS: падзелены коскамі спіс дазволеных даменаў для бяспечнага доступу вэб-інтэрфейсу",
        "OLLAMA_BASE_URL: базавы адрас дэмана Ollama для аўтаматычнага выяўлення мадэляў (па змаўч. http://localhost:11434)"
      ]
    }
  ]
};
