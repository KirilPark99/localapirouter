import { DocContent } from "./types";

export const uk: DocContent = {
  "ui": {
    "searchPlaceholder": "Пошук по документації (наприклад, Ollama, Fallback, Fusion)...",
    "noSectionsFound": "Розділи документації не знайдені.",
    "prevSection": "Попередній розділ",
    "nextSection": "Наступний розділ",
    "copied": "Скопійовано!",
    "copy": "Скопіювати код",
    "endpoints": "Ендпоінти",
    "tocTitle": "Зміст"
  },
  "sections": [
    {
      "id": "overview",
      "title": "Огляд системи",
      "group": "intro",
      "description": "Універсальний self-hosted ШІ-шлюз із 3 механізмами маршрутизації (Direct, Priority Fallback, Fusion), пулом ключів та підтримкою протоколів OpenAI й Ollama.",
      "subsections": [
        {
          "title": "Порівняння рушіїв маршрутизації",
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
        "3 рушії маршрутизації: Прямий, Пріоритетний Fallback (вкладений), Ансамбль Model Fusion",
        "Повна сумісність з OpenAI API (/v1/chat/completions) та Ollama (/api/tags, /api/show)",
        "Надійне шифрування ключів: AES-128-CBC Fernet під контролем ROUTER_MASTER_KEY",
        "Автоматичний Circuit Breaker із самовідновленням та прив'язкою гео-проксі"
      ]
    },
    {
      "id": "quickstart",
      "title": "Швидкий старт",
      "group": "intro",
      "description": "Підключення будь-якої бібліотеки OpenAI SDK, cURL або Ollama-клієнта до шлюзу MyAIrouter за лічені секунди.",
      "subsections": [
        {
          "title": "1. Швидкий виклик через cURL",
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
      "title": "Адресація та вибір моделей",
      "group": "models",
      "description": "Гнучка багаторівнева адресація моделей: канонічні slug-імена, прямі провайдерні шляхи, ланцюжки fallback та ансамблі fusion.",
      "subsections": [
        {
          "title": "Ієрархія адресації моделей",
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
      "title": "Сумісність з Ollama API",
      "group": "models",
      "description": "Нативна сумісність з утилітою Ollama CLI, плагінами Continue.dev, Open WebUI та Obsidian Copilot без змін у клієнтському коді.",
      "subsections": [
        {
          "title": "Використання через Ollama CLI",
          "code": {
            "title": "Bash / Terminal",
            "lang": "bash",
            "content": "# Point your local Ollama client or IDE extension to MyAIrouter\nexport OLLAMA_HOST=http://localhost:8000\n\n# View all registered models, route profiles, and fusion profiles\nollama list\n\n# Execute queries directly through the OpenAI-compatible gateway\nollama run gemini-2.5-flash \"Write a Fibonacci function in Go\" "
          }
        },
        {
          "title": "Підтримувані ендпоінти Ollama",
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
      "title": "Рейтинги та бенчмарки",
      "group": "models",
      "description": "Автоматична інтеграція бенчмарків Artificial Analysis: індекс якості (0-100), швидкість генерації (ток/с), вартість та контекст.",
      "subsections": [
        {
          "title": "Ключові показники моделей",
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
      "title": "Ліміти API та квоти",
      "group": "models",
      "description": "Дворівневе обмеження швидкості: захист upstream-акаунтів (RPM/TPM за ключами) та контроль квот клієнтів шлюзу.",
      "subsections": [
        {
          "title": "Дворівневий контроль лімітів",
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
      "title": "Рівні міркувань (CoT)",
      "group": "routing",
      "description": "Універсальний параметр reasoning_effort із двосторонньою трансляцією форматів між OpenAI, Anthropic, Google Gemini та Groq.",
      "subsections": [
        {
          "title": "Приклад запиту з reasoning_effort",
          "code": {
            "title": "cURL Reasoning Request",
            "lang": "bash",
            "content": "# Send standard reasoning_effort to any provider\ncurl http://localhost:8000/v1/chat/completions \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\n    \"model\": \"gemini-2.5-flash\",\n    \"messages\": [{\"role\": \"user\", \"content\": \"Prove that the square root of 2 is irrational.\"}],\n    \"reasoning_effort\": \"high\"\n  }'"
          }
        },
        {
          "title": "Матриця трансляції параметрів",
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
      "title": "Пряма маршрутизація (Direct)",
      "group": "routing",
      "description": "Високошвидкісна пряма відправка запиту в конкретну модель із балансуванням Round-robin та миттєвим перемиканням ключів.",
      "subsections": [
        {
          "title": "Приклади прямого звернення",
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
      "title": "Пріоритети та Fallback",
      "group": "routing",
      "description": "Багаторівневі черги перемикання при 429 лімітах або 5xx помилках, підтримка вкладених профілів та груп ключів.",
      "subsections": [
        {
          "title": "Принцип роботи ланцюжка",
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
      "description": "Паралельне виконання кількох моделей та синтез еталонної відповіді моделлю-суддею з потоковою передачею ходу міркувань.",
      "subsections": [
        {
          "title": "Потокове виведення обговорення",
          "code": {
            "title": "SSE Fusion Stream",
            "lang": "bash",
            "content": "curl http://localhost:8000/v1/chat/completions \\\n  -H \"Content-Type: application/json\" \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\n    \"model\": \"fusion/code-jury\",\n    \"messages\": [{\"role\": \"user\", \"content\": \"Analyze time complexity of quicksort\"}],\n    \"stream\": true\n  }'\n\n# Streamed SSE chunks contain real-time deliberation in reasoning_content:\n# data: {\"choices\":[{\"delta\":{\"reasoning_content\":\"### 🧬 Fusion Ensemble Deliberation\\n...\"}}]}\n# ...\n# data: {\"choices\":[{\"delta\":{\"content\":\"Final evaluated answer...\"}}]}"
          }
        },
        {
          "title": "Стратегії роботи судді",
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
      "title": "Підтримувані провайдери та Keyless-режим",
      "group": "management",
      "description": "Нативна інтеграція з 12+ хмарними провайдерами та локальними середовищами виконання, включаючи Keyless-режим для власного інстансу Ollama.",
      "subsections": [
        {
          "title": "Матриця можливостей провайдерів",
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
          "title": "Налаштування Keyless-режиму для Ollama",
          "code": {
            "title": "Add Ollama via API or UI",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/credentials \\\n  -H \"Content-Type: application/json\" \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\" \\\n  -d '{\n    \"provider\": \"ollama\",\n    \"name\": \"Local Workstation Ollama\",\n    \"api_key\": \"keyless\",\n    \"base_url\": \"http://127.0.0.1:11434\",\n    \"is_active\": true\n  }'"
          }
        }
      ],
      "badge": "Multi-Provider",
      "highlights": [
        "Підтримка OpenAI, Anthropic, Gemini, Groq, DeepSeek, Cerebras, Mistral, xAI, OpenRouter",
        "Keyless-режим: підключення локальної Ollama (http://localhost:11434) без фіктивних ключів",
        "Власний Base URL для vLLM, LM Studio та корпоративних OpenAI-сумісних шлюзів",
        "Прив'язка виділених HTTP/SOCKS5 проксі до облікових записів провайдерів"
      ]
    },
    {
      "id": "credentials",
      "title": "Керування ключами провайдерів (Vault)",
      "group": "management",
      "description": "Сховище API-ключів із банківським шифруванням, автоматичною перевіркою працездатності та групуванням за папками.",
      "subsections": [
        {
          "title": "Ручний запуск перевірки ключа",
          "code": {
            "title": "Health Check Endpoint",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/credentials/cred_abc123/health-check \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\"\n\n# Response:\n# {\n#   \"status\": \"healthy\",\n#   \"latency_ms\": 142.5,\n#   \"checked_at\": \"2026-09-13T14:15:00Z\"\n# }"
          }
        }
      ],
      "badge": "Encrypted Vault",
      "highlights": [
        "Симетричне шифрування AES-128-CBC Fernet: ключі шифруються перед записом у SQLite",
        "Маскування ключів: секрети ніколи не потрапляють в інтерфейс чи логи (наприклад, sk-ant...7a9f)",
        "Автоматичні Health-чеки: регулярна перевірка валідності ключів та квот провайдера",
        "Групи облікових записів: розділення ключів по папках (Production, Staging, Backup, Team)"
      ]
    },
    {
      "id": "api-keys",
      "title": "Клієнтські API-ключі та права доступу",
      "group": "management",
      "description": "Випуск, моніторинг та відкликання клієнтських токенів доступу (sk-router-...) з індивідуальними лімітами RPM/TPM та білими списками моделей.",
      "subsections": [
        {
          "title": "Параметри клієнтського ключа",
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
        "Незворотне хешування SHA-256: секретні ключі не зберігаються у відкритому вигляді в БД",
        "Квоти та ліміти: окремий контроль запитів на хвилину (RPM) і токенів на хвилину (TPM)",
        "Білі списки моделей: обмеження доступу лише до дозволених моделей та профілів",
        "Термін дії (TTL): автоматичне відключення ключів після закінчення вказаної дати"
      ]
    },
    {
      "id": "proxies",
      "title": "Проксі-сервери та гео-маршрутизація",
      "group": "management",
      "description": "Маршрутизація запитів до провайдерів через HTTP та SOCKS5 проксі з вимірюванням затримки та обходом блокувань.",
      "subsections": [
        {
          "title": "Формати URI проксі-серверів",
          "code": {
            "title": "Supported Proxy URI Formats",
            "lang": "bash",
            "content": "# Standard HTTP proxy:\nhttp://proxy.corporate.internal:8080\n\n# Authenticated HTTP proxy:\nhttp://username:<PROXY_PASSWORD>@us-east.proxy-vendor.com:3128\n\n# Authenticated SOCKS5 proxy:\nsocks5://proxyuser:<PROXY_PASSWORD>@sg-node.vpn-provider.net:1080"
          }
        }
      ],
      "badge": "Egress & Geo",
      "highlights": [
        "Підтримка протоколів: HTTP, HTTPS та SOCKS5 (socks5://user:pass@host:port)",
        "Гео-мітки країн: прив'язка ISO-кодів (US, DE, SG, JP) для обходу обмежень провайдерів",
        "Замір пінгу та затримки: автоматичний тест RTT при додаванні та плановій перевірці",
        "Ізоляція на рівні ключа: прив'язка виділеного проксі до конкретного ключа чи провайдера"
      ]
    },
    {
      "id": "backup-restore",
      "title": "Резервне копіювання та відновлення",
      "group": "system",
      "description": "Експорт та імпорт повної конфігурації шлюзу з шифруванням AES-GCM за паролем (моделі, маршрути, ключі, проксі та клієнти).",
      "subsections": [
        {
          "title": "Експорт резервної копії через API",
          "code": {
            "title": "Encrypted Backup Endpoint",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/system/backup \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{\"passphrase\": \"<BACKUP_PASSPHRASE>\"}' \\\n  -o router_backup_2026-09-13.enc"
          }
        }
      ],
      "badge": "Disaster Recovery",
      "highlights": [
        "Деривація ключа PBKDF2 HMAC-SHA256 з випадковою сіллю 16 байт та аутентифікацією AES-256-GCM",
        "Повний знімок системи: моделі, ключі провайдерів, профілі маршрутів, журі Fusion, проксі та клієнти",
        "Гнучке відновлення: можливість об'єднання з існуючими записами або повного перезапису",
        "Відсутність прив'язки: миттєвий перенос між серверами, VPS та Docker-контейнерами"
      ]
    },
    {
      "id": "analytics",
      "title": "Аналітика, логи та Waterfall-трасування",
      "group": "system",
      "description": "Наскрізна телеметрія трафіку з обліком токенів, розрахунком витрат, графіками затримок та інтерактивним Waterfall-трасуванням.",
      "subsections": [
        {
          "title": "Схема запису лога",
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
        "Тривимірний облік токенів: окремий підрахунок prompt-, completion- та reasoning-токенів",
        "Waterfall-трасування: покрокова візуалізація кожної спроби, таймауту та перемикання на fallback",
        "Фінансовий облік: розрахунок оціночної вартості в USD на основі тарифів провайдерів",
        "Експорт аудиту: фільтрація та вивантаження логів за статусами відповідей, клієнтами, моделями та датами"
      ]
    },
    {
      "id": "circuit-breaker",
      "title": "Circuit Breaker та ізоляція збоїв",
      "group": "system",
      "description": "Автомат станів, що ізолює нестабільних або перевантажених провайдерів, захищаючи клієнтські застосунки від каскадних таймаутів.",
      "subsections": [
        {
          "title": "Життєвий цикл станів автомата",
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
        "3 робочих стани: CLOSED (норма, трафік іде), OPEN (ізольований, перенаправлення), HALF-OPEN (перевірка)",
        "Поріг спрацьовування: автоматичне розмикання ланцюга після 5 поспіль помилок 5xx або таймаутів",
        "Період охолодження: 30 секунд утримання перед відправкою пробного запиту для перевірки доступності",
        "Непомітно для клієнтів: наступний кандидат у профілі Fallback миттєво обробляє запит без помилок"
      ]
    },
    {
      "id": "api-reference",
      "title": "Повний довідник REST API",
      "group": "system",
      "description": "Повний каталог усіх публічних ендпоінтів інференсу та адміністративних інтерфейсів керування шлюзом MyAIrouter.",
      "subsections": [
        {
          "title": "Таблиця публічних та адміністративних ендпоінтів",
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
        "Сумісність з OpenAI: /v1/chat/completions, /v1/models (пряма заміна у будь-яких SDK)",
        "Протокол Ollama: /api/tags, /api/show, /api/version, /api/chat",
        "Керування конфігурацією: /api/v1/credentials, /api/v1/models, /api/v1/routes, /api/v1/fusion",
        "Система та моніторинг: /health, /api/v1/system/backup, /api/v1/system/restore, /api/v1/system/stats"
      ]
    },
    {
      "id": "errors",
      "title": "Коди помилок HTTP та діагностика",
      "group": "system",
      "description": "Детальний розбір кодів стану HTTP, що повертаються шлюзом, специфікація формату помилок JSON та інструкції з їх усунення.",
      "subsections": [
        {
          "title": "Каталог кодів стану HTTP",
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
        "Стандартна схема помилок OpenAI: {\"error\": {\"message\": \"...\", \"type\": \"...\", \"code\": \"...\"}}",
        "Чіткий поділ: розмежування помилок клієнта (4xx) та збоїв вищих провайдерів (502/504)",
        "Інформативні описи: повідомлення вказують конкретну причину (невірний ключ, вичерпаний ліміт або модель не знайдено)",
        "Обробка Rate Limit: відповіді 429 містять інформацію про перевищення лімітів RPM або TPM"
      ]
    },
    {
      "id": "env-config",
      "title": "Змінні оточення та деплой",
      "group": "system",
      "description": "Повний перелік параметрів конфігурації для промислового розгортання MyAIrouter з Docker, PostgreSQL та systemd.",
      "subsections": [
        {
          "title": "Основні змінні оточення",
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
          "title": "Приклад Docker Compose для продакшену",
          "code": {
            "title": "docker-compose.prod.yml",
            "lang": "yaml",
            "content": "version: \"3.8\"\n\nservices:\n  myairouter:\n    image: myairouter:latest\n    restart: always\n    ports:\n      - \"8000:8000\"\n    environment:\n      - ROUTER_MASTER_KEY=<GENERATED_ROUTER_MASTER_KEY>\n      - DATABASE_URL=postgresql+asyncpg://router:<POSTGRES_PASSWORD>@postgres:5432/routerdb\n      - ROUTER_PORT=8000\n      - ROUTER_HOST=0.0.0.0\n      - LOG_LEVEL=INFO\n      - DEFAULT_TIMEOUT=45.0\n      - CORS_ORIGINS=https://ai.yourcompany.internal\n    depends_on:\n      - postgres\n\n  postgres:\n    image: postgres:16-alpine\n    restart: always\n    environment:\n      POSTGRES_USER: router\n      POSTGRES_PASSWORD: <POSTGRES_PASSWORD>\n      POSTGRES_DB: routerdb\n    volumes:\n      - pgdata:/var/lib/postgresql/data\n\nvolumes:\n  pgdata:"
          }
        }
      ],
      "badge": "Deployment",
      "highlights": [
        "ROUTER_MASTER_KEY: критично важливий 32-байтний base64 ключ для шифрування всіх секретів у БД",
        "DATABASE_URL: перемикання зі стандартної SQLite на високонавантажену PostgreSQL",
        "CORS_ORIGINS: розділений комами список дозволених доменів для безпечного доступу веб-інтерфейсу",
        "OLLAMA_BASE_URL: базова адреса демона Ollama для автоматичного виявлення моделей (за замовч. http://localhost:11434)"
      ]
    }
  ]
};
