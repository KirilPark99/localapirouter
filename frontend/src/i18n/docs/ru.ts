import { DocContent } from "./types";

export const ru: DocContent = {
  "ui": {
    "searchPlaceholder": "Поиск по документации (например, Ollama, Fallback, Fusion)...",
    "noSectionsFound": "Разделы документации не найдены.",
    "prevSection": "Предыдущий раздел",
    "nextSection": "Следующий раздел",
    "copied": "Скопировано!",
    "copy": "Скопировать код",
    "endpoints": "Эндпоинты",
    "tocTitle": "Содержание"
  },
  "sections": [
    {
      "id": "overview",
      "title": "Обзор системы",
      "group": "intro",
      "description": "Универсальный self-hosted ИИ-шлюз с 3 движками маршрутизации (Direct, Priority Fallback, Fusion), пулом ключей и поддержкой протоколов OpenAI и Ollama.",
      "subsections": [
        {
          "title": "Сравнение движков маршрутизации",
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
        "3 движка маршрутизации: Прямой, Приоритетный Fallback (вложенный), Ансамбль Model Fusion",
        "Совместимость с протоколами OpenAI (/v1/chat/completions) и Ollama (/api/tags, /api/show)",
        "Надежное шифрование ключей: AES-128-CBC Fernet под управлением ROUTER_MASTER_KEY",
        "Автоматический Circuit Breaker с самовосстановлением и привязкой гео-прокси"
      ]
    },
    {
      "id": "quickstart",
      "title": "Быстрый старт",
      "group": "intro",
      "description": "Подключение любой библиотеки OpenAI SDK, cURL или Ollama-клиента к шлюзу MyAIrouter за считанные секунды.",
      "subsections": [
        {
          "title": "1. Быстрый вызов через cURL",
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
      "title": "Адресация и выбор моделей",
      "group": "models",
      "description": "Гибкая многоуровневая адресация моделей: канонические slug-имена, прямые провайдерные пути, цепочки fallback и ансамбли fusion.",
      "subsections": [
        {
          "title": "Иерархия адресации моделей",
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
      "title": "Совместимость с Ollama API",
      "group": "models",
      "description": "Нативная совместимость с утилитой Ollama CLI, плагинами Continue.dev, Open WebUI и Obsidian Copilot без изменения клиентского кода.",
      "subsections": [
        {
          "title": "Использование через Ollama CLI",
          "code": {
            "title": "Bash / Terminal",
            "lang": "bash",
            "content": "# Point your local Ollama client or IDE extension to MyAIrouter\nexport OLLAMA_HOST=http://localhost:8000\n\n# View all registered models, route profiles, and fusion profiles\nollama list\n\n# Execute queries directly through the OpenAI-compatible gateway\nollama run gemini-2.5-flash \"Write a Fibonacci function in Go\" "
          }
        },
        {
          "title": "Поддерживаемые эндпоинты Ollama",
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
      "title": "Рейтинги и бенчмарки",
      "group": "models",
      "description": "Автоматическая интеграция бенчмарков Artificial Analysis: индекс качества (0-100), скорость генерации (ток/с), стоимость и контекст.",
      "subsections": [
        {
          "title": "Ключевые показатели моделей",
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
      "title": "Лимиты API и квоты",
      "group": "models",
      "description": "Двухуровневое ограничение скорости: защита upstream-аккаунтов (RPM/TPM по ключам) и управление квотами клиентов шлюза.",
      "subsections": [
        {
          "title": "Двухуровневый контроль лимитов",
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
      "title": "Уровни рассуждений (CoT)",
      "group": "routing",
      "description": "Универсальный параметр reasoning_effort с двусторонней трансляцией форматов между OpenAI, Anthropic, Google Gemini и Groq.",
      "subsections": [
        {
          "title": "Пример запроса с reasoning_effort",
          "code": {
            "title": "cURL Reasoning Request",
            "lang": "bash",
            "content": "# Send standard reasoning_effort to any provider\ncurl http://localhost:8000/v1/chat/completions \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\n    \"model\": \"gemini-2.5-flash\",\n    \"messages\": [{\"role\": \"user\", \"content\": \"Prove that the square root of 2 is irrational.\"}],\n    \"reasoning_effort\": \"high\"\n  }'"
          }
        },
        {
          "title": "Матрица трансляции параметров",
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
      "title": "Прямая маршрутизация (Direct)",
      "group": "routing",
      "description": "Высокоскоростная прямая отправка запроса в конкретную модель с балансировкой Round-robin и мгновенным переключением ключей.",
      "subsections": [
        {
          "title": "Примеры прямого обращения",
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
      "title": "Приоритеты и Fallback",
      "group": "routing",
      "description": "Многоуровневые очереди переключения при 429 лимитах или 5xx ошибках, поддержка вложенных профилей и групп ключей.",
      "subsections": [
        {
          "title": "Принцип работы цепочки",
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
      "title": "Model Fusion (Ансамбли ИИ)",
      "group": "routing",
      "description": "Параллельное выполнение нескольких моделей и синтез эталонного ответа моделью-судьей с потоковой передачей хода рассуждений.",
      "subsections": [
        {
          "title": "Потоковый вывод хода обсуждения",
          "code": {
            "title": "SSE Fusion Stream",
            "lang": "bash",
            "content": "curl http://localhost:8000/v1/chat/completions \\\n  -H \"Content-Type: application/json\" \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\n    \"model\": \"fusion/code-jury\",\n    \"messages\": [{\"role\": \"user\", \"content\": \"Analyze time complexity of quicksort\"}],\n    \"stream\": true\n  }'\n\n# Streamed SSE chunks contain real-time deliberation in reasoning_content:\n# data: {\"choices\":[{\"delta\":{\"reasoning_content\":\"### 🧬 Fusion Ensemble Deliberation\\n...\"}}]}\n# ...\n# data: {\"choices\":[{\"delta\":{\"content\":\"Final evaluated answer...\"}}]}"
          }
        },
        {
          "title": "Стратегии работы судьи",
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
      "title": "Поддерживаемые провайдеры и Keyless-режим",
      "group": "management",
      "description": "Нативная интеграция с 12+ облачными провайдерами и локальными средами исполнения, включая Keyless-режим для собственного инстанса Ollama.",
      "subsections": [
        {
          "title": "Матрица возможностей провайдеров",
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
          "title": "Настройка Keyless-режима для Ollama",
          "code": {
            "title": "Add Ollama via API or UI",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/credentials \\\n  -H \"Content-Type: application/json\" \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\" \\\n  -d '{\n    \"provider\": \"ollama\",\n    \"name\": \"Local Workstation Ollama\",\n    \"api_key\": \"keyless\",\n    \"base_url\": \"http://127.0.0.1:11434\",\n    \"is_active\": true\n  }'"
          }
        }
      ],
      "badge": "Multi-Provider",
      "highlights": [
        "Поддержка OpenAI, Anthropic, Gemini, Groq, DeepSeek, Cerebras, Mistral, xAI, OpenRouter",
        "Keyless-режим: подключение локальной Ollama (http://localhost:11434) без фиктивных API-ключей",
        "Пользовательский Base URL для vLLM, LM Studio и корпоративных OpenAI-совместимых шлюзов",
        "Привязка выделенных HTTP/SOCKS5 прокси к учетным записям провайдеров"
      ]
    },
    {
      "id": "credentials",
      "title": "Управление ключами провайдеров (Vault)",
      "group": "management",
      "description": "Хранилище API-ключей с шифрованием банковского уровня, автоматической проверкой работоспособности и группировкой по папкам.",
      "subsections": [
        {
          "title": "Ручной запуск проверки ключа",
          "code": {
            "title": "Health Check Endpoint",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/credentials/cred_abc123/health-check \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\"\n\n# Response:\n# {\n#   \"status\": \"healthy\",\n#   \"latency_ms\": 142.5,\n#   \"checked_at\": \"2026-09-13T14:15:00Z\"\n# }"
          }
        }
      ],
      "badge": "Encrypted Vault",
      "highlights": [
        "Симметричное шифрование AES-128-CBC Fernet: ключи шифруются перед записью в SQLite",
        "Маскирование ключей: исходные секреты никогда не передаются в интерфейс (например, sk-ant...7a9f)",
        "Автоматические Health-чеки: регулярная проверка валидности ключей и квот провайдера",
        "Группы учетных записей: разделение ключей по папкам (Production, Staging, Backup, Team)"
      ]
    },
    {
      "id": "api-keys",
      "title": "Клиентские API-ключи и права доступа",
      "group": "management",
      "description": "Выпуск, мониторинг и отзыв клиентских токенов доступа (sk-router-...) с индивидуальными лимитами RPM/TPM и белыми списками моделей.",
      "subsections": [
        {
          "title": "Параметры клиентского ключа",
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
        "Необратимое хеширование SHA-256: секретные ключи не хранятся в открытом виде в БД",
        "Квоты и лимиты: раздельный контроль запросов в минуту (RPM) и токенов в минуту (TPM)",
        "Белые списки моделей: ограничение доступа только к разрешенным моделям и профилям",
        "Срок действия (TTL): автоматическое отключение ключей по истечении заданной даты"
      ]
    },
    {
      "id": "proxies",
      "title": "Прокси-серверы и гео-маршрутизация",
      "group": "management",
      "description": "Маршрутизация запросов к провайдерам через HTTP и SOCKS5 прокси с измерением задержки и обходом региональных блокировок.",
      "subsections": [
        {
          "title": "Форматы URI прокси-серверов",
          "code": {
            "title": "Supported Proxy URI Formats",
            "lang": "bash",
            "content": "# Standard HTTP proxy:\nhttp://proxy.corporate.internal:8080\n\n# Authenticated HTTP proxy:\nhttp://username:<PROXY_PASSWORD>@us-east.proxy-vendor.com:3128\n\n# Authenticated SOCKS5 proxy:\nsocks5://proxyuser:<PROXY_PASSWORD>@sg-node.vpn-provider.net:1080"
          }
        }
      ],
      "badge": "Egress & Geo",
      "highlights": [
        "Поддержка протоколов: HTTP, HTTPS и SOCKS5 (socks5://user:pass@host:port)",
        "Гео-метки стран: привязка ISO-кодов (US, DE, SG, JP) для обхода ограничений провайдеров",
        "Замер пинга и задержки: автоматический тест RTT при добавлении и плановой проверке",
        "Изоляция на уровне ключа: привязка выделенного прокси к конкретному ключу или провайдеру"
      ]
    },
    {
      "id": "backup-restore",
      "title": "Резервное копирование и восстановление",
      "group": "system",
      "description": "Экспорт и импорт полной конфигурации шлюза с шифрованием AES-GCM по мастер-паролю (модели, маршруты, ключи, прокси и клиенты).",
      "subsections": [
        {
          "title": "Экспорт резервной копии через API",
          "code": {
            "title": "Encrypted Backup Endpoint",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/system/backup \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{\"passphrase\": \"<BACKUP_PASSPHRASE>\"}' \\\n  -o router_backup_2026-09-13.enc"
          }
        }
      ],
      "badge": "Disaster Recovery",
      "highlights": [
        "Деривация ключа PBKDF2 HMAC-SHA256 со случайной солью 16 байт и аутентификацией AES-256-GCM",
        "Полный снимок системы: модели, ключи провайдеров, профили маршрутов, жюри Fusion, прокси и клиенты",
        "Гибкое восстановление: возможность объединения с существующими записями или полной перезаписи",
        "Отсутствие привязки к инфраструктуре: мгновенный перенос между серверами, VPS и Docker-контейнерами"
      ]
    },
    {
      "id": "analytics",
      "title": "Аналитика, логи и Waterfall-трассировка",
      "group": "system",
      "description": "Сквозная телеметрия трафика с учетом токенов, расчетом затрат, графиками задержек и интерактивной Waterfall-трассировкой.",
      "subsections": [
        {
          "title": "Схема записи лога",
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
        "Трехмерный учет токенов: раздельный подсчет prompt-, completion- и reasoning-токенов",
        "Waterfall-трассировка: пошаговая визуализация каждой попытки, таймаута и переключения на fallback",
        "Финансовый учет: расчет оценочной стоимости в USD на основе тарифов провайдеров",
        "Экспорт аудита: фильтрация и выгрузка логов по статусам ответов, клиентам, моделям и датам"
      ]
    },
    {
      "id": "circuit-breaker",
      "title": "Circuit Breaker и изоляция сбоев",
      "group": "system",
      "description": "Автомат состояний, изолирующий сбоящих или перегруженных провайдеров, защищая клиентские приложения от каскадных таймаутов.",
      "subsections": [
        {
          "title": "Жизненный цикл состояний автомата",
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
        "3 рабочих состояния: CLOSED (норма, трафик идет), OPEN (изолирован, перенаправление), HALF-OPEN (проверка)",
        "Порог срабатывания: автоматическое размыкание цепи после 5 подряд ошибок 5xx или таймаутов",
        "Период охлаждения: 30 секунд удержания перед отправкой пробного запроса для проверки доступности",
        "Незаметно для клиентов: следующий кандидат в профиле Fallback мгновенно обрабатывает запрос без ошибок"
      ]
    },
    {
      "id": "api-reference",
      "title": "Полный справочник REST API",
      "group": "system",
      "description": "Полный каталог всех публичных эндпоинтов инференса и административных интерфейсов управления шлюзом MyAIrouter.",
      "subsections": [
        {
          "title": "Таблица публичных и административных эндпоинтов",
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
        "Совместимость с OpenAI: /v1/chat/completions, /v1/models (прямая замена в любых SDK)",
        "Протокол Ollama: /api/tags, /api/show, /api/version, /api/chat",
        "Управление конфигурацией: /api/v1/credentials, /api/v1/models, /api/v1/routes, /api/v1/fusion",
        "Система и мониторинг: /health, /api/v1/system/backup, /api/v1/system/restore, /api/v1/system/stats"
      ]
    },
    {
      "id": "errors",
      "title": "Коды ошибок HTTP и диагностика",
      "group": "system",
      "description": "Подробный разбор кодов состояния HTTP, возвращаемых шлюзом, спецификация формата ошибок JSON и инструкции по их устранению.",
      "subsections": [
        {
          "title": "Каталог кодов состояния HTTP",
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
        "Стандартная схема ошибок OpenAI: {\"error\": {\"message\": \"...\", \"type\": \"...\", \"code\": \"...\"}}",
        "Четкое разделение: разграничение ошибок клиента (4xx) и сбоев вышестоящих провайдеров (502/504)",
        "Информативные описания: сообщения указывают конкретную причину (неверный ключ, исчерпан лимит или модель не найдена)",
        "Обработка Rate Limit: ответы 429 содержат информацию о превышении лимитов RPM или TPM"
      ]
    },
    {
      "id": "env-config",
      "title": "Переменные окружения и деплой",
      "group": "system",
      "description": "Полный перечень параметров конфигурации для промышленного развертывания MyAIrouter с Docker, PostgreSQL и systemd.",
      "subsections": [
        {
          "title": "Основные переменные окружения",
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
          "title": "Пример Docker Compose для продакшена",
          "code": {
            "title": "docker-compose.prod.yml",
            "lang": "yaml",
            "content": "version: \"3.8\"\n\nservices:\n  myairouter:\n    image: myairouter:latest\n    restart: always\n    ports:\n      - \"8000:8000\"\n    environment:\n      - ROUTER_MASTER_KEY=<GENERATED_ROUTER_MASTER_KEY>\n      - DATABASE_URL=postgresql+asyncpg://router:<POSTGRES_PASSWORD>@postgres:5432/routerdb\n      - ROUTER_PORT=8000\n      - ROUTER_HOST=0.0.0.0\n      - LOG_LEVEL=INFO\n      - DEFAULT_TIMEOUT=45.0\n      - CORS_ORIGINS=https://ai.yourcompany.internal\n    depends_on:\n      - postgres\n\n  postgres:\n    image: postgres:16-alpine\n    restart: always\n    environment:\n      POSTGRES_USER: router\n      POSTGRES_PASSWORD: <POSTGRES_PASSWORD>\n      POSTGRES_DB: routerdb\n    volumes:\n      - pgdata:/var/lib/postgresql/data\n\nvolumes:\n  pgdata:"
          }
        }
      ],
      "badge": "Deployment",
      "highlights": [
        "ROUTER_MASTER_KEY: критически важный 32-байтный base64 ключ для шифрования всех секретов в БД",
        "DATABASE_URL: переключение со стандартной SQLite на высоконагруженную PostgreSQL",
        "CORS_ORIGINS: разделенный запятыми список разрешенных доменов для безопасного доступа веб-интерфейса",
        "OLLAMA_BASE_URL: базовый адрес демона Ollama для автоматического обнаружения моделей (по умолч. http://localhost:11434)"
      ]
    }
  ]
};
