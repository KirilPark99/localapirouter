import { DocContent } from "./types";

export const es: DocContent = {
  "ui": {
    "searchPlaceholder": "Buscar en la documentación (ej. Ollama, Fallback, Fusion)...",
    "noSectionsFound": "No se encontraron secciones coincidentes.",
    "prevSection": "Sección anterior",
    "nextSection": "Sección siguiente",
    "copied": "¡Copiado!",
    "copy": "Copiar código",
    "endpoints": "Endpoints",
    "tocTitle": "Índice de documentación"
  },
  "sections": [
    {
      "id": "overview",
      "title": "Descripción general",
      "group": "intro",
      "description": "Pasarela LLM autohospedada universal con motores Direct, Priority Fallback y Model Fusion, agrupación de claves y compatibilidad con Ollama.",
      "subsections": [
        {
          "title": "Comparación de modos de enrutamiento",
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
        "3 motores de enrutamiento: Directo, Fallback prioritario (anidado) y Fusión de modelos",
        "Compatibilidad total con API OpenAI (/v1/chat/completions) y Ollama (/api/tags, /api/show)",
        "Seguridad empresarial: cifrado AES-128-CBC Fernet mediante ROUTER_MASTER_KEY",
        "Aislamiento de fallos por Circuit Breaker con autorrecuperación y proxies geo"
      ]
    },
    {
      "id": "quickstart",
      "title": "Guía de inicio rápido",
      "group": "intro",
      "description": "Conecte cualquier librería OpenAI, cURL o cliente Ollama a la pasarela MyAIrouter en segundos.",
      "subsections": [
        {
          "title": "1. Inicio rápido con cURL",
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
      "title": "Direccionamiento de modelos",
      "group": "models",
      "description": "Direccionamiento flexible multinivel: slugs canónicos, identificadores calificados por proveedor, rutas de fallback y jurados de fusión.",
      "subsections": [
        {
          "title": "Jerarquía de direccionamiento",
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
      "title": "Compatibilidad con Ollama API",
      "group": "models",
      "description": "Compatibilidad nativa con Ollama CLI, Continue.dev, Open WebUI y Obsidian Copilot sin modificar código cliente.",
      "subsections": [
        {
          "title": "Integración con Ollama CLI",
          "code": {
            "title": "Bash / Terminal",
            "lang": "bash",
            "content": "# Point your local Ollama client or IDE extension to MyAIrouter\nexport OLLAMA_HOST=http://localhost:8000\n\n# View all registered models, route profiles, and fusion profiles\nollama list\n\n# Execute queries directly through the OpenAI-compatible gateway\nollama run gemini-2.5-flash \"Write a Fibonacci function in Go\" "
          }
        },
        {
          "title": "Puntos finales compatibles de Ollama",
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
      "title": "Calificaciones y Benchmarks",
      "group": "models",
      "description": "Métricas automáticas de Artificial Analysis: Índice de calidad (0-100), velocidad de generación, precios y ventana de contexto.",
      "subsections": [
        {
          "title": "Métricas de Benchmark",
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
      "title": "Límites y cuotas de API",
      "group": "models",
      "description": "Control de tasa en dos niveles: proteja cuentas upstream con límites RPM/TPM por credencial y controle el uso de clientes.",
      "subsections": [
        {
          "title": "Control de límites en dos capas",
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
      "title": "Niveles de razonamiento (CoT)",
      "group": "routing",
      "description": "Parámetro universal reasoning_effort con traducción automática entre OpenAI, Anthropic, Google Gemini y Groq.",
      "subsections": [
        {
          "title": "Ejemplo de parámetro de razonamiento",
          "code": {
            "title": "cURL Reasoning Request",
            "lang": "bash",
            "content": "# Send standard reasoning_effort to any provider\ncurl http://localhost:8000/v1/chat/completions \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\n    \"model\": \"gemini-2.5-flash\",\n    \"messages\": [{\"role\": \"user\", \"content\": \"Prove that the square root of 2 is irrational.\"}],\n    \"reasoning_effort\": \"high\"\n  }'"
          }
        },
        {
          "title": "Matriz de traducción entre proveedores",
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
      "title": "Enrutamiento directo (Direct)",
      "group": "routing",
      "description": "Enrutamiento directo ultrarrápido al modelo especificado con balanceo round-robin y conmutación automática entre claves.",
      "subsections": [
        {
          "title": "Ejemplo de enrutamiento directo",
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
      "title": "Cadenas de Fallback prioritario",
      "group": "routing",
      "description": "Colas de conmutación multinivel en caso de cuotas 429 o fallos 5xx, con perfiles anidados y grupos de claves.",
      "subsections": [
        {
          "title": "Mecánica de Fallback",
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
      "title": "Fusión de modelos (Ensembles)",
      "group": "routing",
      "description": "Ejecute varios LLM en paralelo y sintetice la respuesta definitiva mediante un modelo Juez con transmisión de razonamiento en tiempo real.",
      "subsections": [
        {
          "title": "Ejemplo de deliberación en streaming",
          "code": {
            "title": "SSE Fusion Stream",
            "lang": "bash",
            "content": "curl http://localhost:8000/v1/chat/completions \\\n  -H \"Content-Type: application/json\" \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\n    \"model\": \"fusion/code-jury\",\n    \"messages\": [{\"role\": \"user\", \"content\": \"Analyze time complexity of quicksort\"}],\n    \"stream\": true\n  }'\n\n# Streamed SSE chunks contain real-time deliberation in reasoning_content:\n# data: {\"choices\":[{\"delta\":{\"reasoning_content\":\"### 🧬 Fusion Ensemble Deliberation\\n...\"}}]}\n# ...\n# data: {\"choices\":[{\"delta\":{\"content\":\"Final evaluated answer...\"}}]}"
          }
        },
        {
          "title": "Estrategias de arbitraje del Juez",
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
      "title": "Proveedores compatibles y modo sin clave",
      "group": "management",
      "description": "Integración nativa con más de 12 proveedores de LLM en la nube y entornos locales, con modo sin clave para instancias de Ollama.",
      "subsections": [
        {
          "title": "Matriz de capacidades de proveedores",
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
          "title": "Configuración de Ollama local sin clave",
          "code": {
            "title": "Add Ollama via API or UI",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/credentials \\\n  -H \"Content-Type: application/json\" \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\" \\\n  -d '{\n    \"provider\": \"ollama\",\n    \"name\": \"Local Workstation Ollama\",\n    \"api_key\": \"keyless\",\n    \"base_url\": \"http://127.0.0.1:11434\",\n    \"is_active\": true\n  }'"
          }
        }
      ],
      "badge": "Multi-Provider",
      "highlights": [
        "Soporte integral para OpenAI, Anthropic, Gemini, Groq, DeepSeek, Cerebras, Mistral, xAI, OpenRouter",
        "Modo sin clave: conecte Ollama local (http://localhost:11434) sin necesidad de claves falsas",
        "Soporte de Base URL personalizada para vLLM, LM Studio y pasarelas empresariales OpenAI",
        "Vinculación de proxy HTTP/SOCKS5 dedicada por credencial de proveedor"
      ]
    },
    {
      "id": "credentials",
      "title": "Credenciales y bóveda de claves",
      "group": "management",
      "description": "Almacenamiento cifrado de nivel bancario para claves API de proveedores, con comprobaciones de estado y grupos de etiquetas.",
      "subsections": [
        {
          "title": "Verificación manual de credenciales",
          "code": {
            "title": "Health Check Endpoint",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/credentials/cred_abc123/health-check \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\"\n\n# Response:\n# {\n#   \"status\": \"healthy\",\n#   \"latency_ms\": 142.5,\n#   \"checked_at\": \"2026-09-13T14:15:00Z\"\n# }"
          }
        }
      ],
      "badge": "Encrypted Vault",
      "highlights": [
        "Cifrado simétrico AES-128-CBC Fernet: las claves se cifran antes de guardarse en SQLite",
        "Enmascaramiento de claves: los secretos nunca se exponen en UI o registros (ej. sk-ant...7a9f)",
        "Verificaciones proactivas de estado: sondeo de prueba contra los endpoints del proveedor",
        "Grupos de credenciales: organice claves en carpetas (Producción, Pruebas, Respaldo)"
      ]
    },
    {
      "id": "api-keys",
      "title": "Claves API del enrutador y permisos",
      "group": "management",
      "description": "Emita, supervise y revoque tokens de acceso de clientes (sk-router-...) con límites de tasa por clave y listas blancas de modelos.",
      "subsections": [
        {
          "title": "Referencia de parámetros de claves",
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
        "Hash unidireccional SHA-256: las claves secretas nunca se guardan en texto claro en la base de datos",
        "Límites de tasa: control granular de solicitudes por minuto (RPM) y tokens por minuto (TPM)",
        "Lista blanca de modelos: restrinja claves a modelos o perfiles de enrutamiento autorizados",
        "Caducidad automática: configure fechas de expiración para accesos temporales o demostraciones"
      ]
    },
    {
      "id": "proxies",
      "title": "Gestión de proxies y etiquetado geográfico",
      "group": "management",
      "description": "Enrute el tráfico ascendente mediante proxies HTTP y SOCKS5 autenticados con medición de latencia y etiquetas regionales.",
      "subsections": [
        {
          "title": "Ejemplos de formato de proxy",
          "code": {
            "title": "Supported Proxy URI Formats",
            "lang": "bash",
            "content": "# Standard HTTP proxy:\nhttp://proxy.corporate.internal:8080\n\n# Authenticated HTTP proxy:\nhttp://username:<PROXY_PASSWORD>@us-east.proxy-vendor.com:3128\n\n# Authenticated SOCKS5 proxy:\nsocks5://proxyuser:<PROXY_PASSWORD>@sg-node.vpn-provider.net:1080"
          }
        }
      ],
      "badge": "Egress & Geo",
      "highlights": [
        "Soporte completo de protocolos: HTTP, HTTPS y SOCKS5 (socks5://user:pass@host:port)",
        "Banderas de país: asigne códigos ISO (US, DE, SG, JP) para cumplir requisitos geográficos",
        "Pruebas de latencia: medición del tiempo de ida y vuelta (RTT) en tiempo real",
        "Aislamiento por credencial: asigne proxies dedicados a claves o proveedores individuales"
      ]
    },
    {
      "id": "backup-restore",
      "title": "Copia de seguridad cifrada y recuperación",
      "group": "system",
      "description": "Exporte y restaure configuraciones completas con cifrado AES-GCM derivado de contraseña, incluyendo modelos, rutas y credenciales.",
      "subsections": [
        {
          "title": "Exportar copia de seguridad vía API",
          "code": {
            "title": "Encrypted Backup Endpoint",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/system/backup \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{\"passphrase\": \"<BACKUP_PASSPHRASE>\"}' \\\n  -o router_backup_2026-09-13.enc"
          }
        }
      ],
      "badge": "Disaster Recovery",
      "highlights": [
        "Derivación de claves PBKDF2 HMAC-SHA256 con sal aleatoria de 16 bytes y autenticación AES-256-GCM",
        "Instantánea completa: modelos, credenciales, perfiles de ruta, jurados de fusión, proxies y claves",
        "Restauración selectiva o completa: opción de fusionar entidades existentes o sustituirlas",
        "Sin dependencia de proveedor: migración sencilla entre nodos VPS, Docker o regiones en la nube"
      ]
    },
    {
      "id": "analytics",
      "title": "Analítica, registros e inspector de trazas",
      "group": "system",
      "description": "Telemetría de tráfico integral con contabilidad de tokens, estimación de costos, gráficos de latencia e inspección Waterfall.",
      "subsections": [
        {
          "title": "Esquema del registro de logs",
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
        "Contabilidad de tokens triple: seguimiento independiente de tokens de prompt, completado y razonamiento",
        "Inspector Waterfall: desglose visual paso a paso de cada intento de conexión, tiempo de espera y reintento",
        "Estimación de costos: cálculo en tiempo real en dólares según las tarifas oficiales de cada proveedor",
        "Registro de auditoría exportable: filtre y descargue registros por código, clave de cliente o fecha"
      ]
    },
    {
      "id": "circuit-breaker",
      "title": "Disyuntor de circuito y aislamiento de fallos",
      "group": "system",
      "description": "Máquina de estados finitos que detiene el tráfico a proveedores en fallo o sobrecargados, protegiendo a los clientes de tiempos de espera en cascada.",
      "subsections": [
        {
          "title": "Ciclo de vida de estados FSM",
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
        "3 estados operativos: CLOSED (saludable), OPEN (aislado, tráfico desviado), HALF-OPEN (probando recuperación)",
        "Condición de activación: se activa automáticamente tras 5 errores 5xx consecutivos o tiempos de espera",
        "Período de enfriamiento: desvía el tráfico durante 30 segundos antes de enviar una prueba de sondeo",
        "Transparente para el cliente: el siguiente candidato en Fallback asume la solicitud sin errores"
      ]
    },
    {
      "id": "api-reference",
      "title": "Referencia completa de endpoints API",
      "group": "system",
      "description": "Índice completo de todos los endpoints REST públicos de inferencia y administración provistos por el servidor MyAIrouter.",
      "subsections": [
        {
          "title": "Tabla de endpoints públicos y administrativos",
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
        "Entrada OpenAI: /v1/chat/completions, /v1/models (compatibilidad inmediata con cualquier cliente)",
        "Protocolo Ollama: /api/tags, /api/show, /api/version, /api/chat",
        "Gestión principal: /api/v1/credentials, /api/v1/models, /api/v1/routes, /api/v1/fusion",
        "Sistema y salud: /health, /api/v1/system/backup, /api/v1/system/restore, /api/v1/system/stats"
      ]
    },
    {
      "id": "errors",
      "title": "Códigos de error HTTP y solución de problemas",
      "group": "system",
      "description": "Desglose detallado de los códigos de estado HTTP devueltos por el enrutador, especificaciones de error JSON y solución de problemas.",
      "subsections": [
        {
          "title": "Catálogo de códigos de estado HTTP",
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
        "Esquema estándar OpenAI: {\"error\": {\"message\": \"...\", \"type\": \"...\", \"code\": \"...\"}}",
        "Distinción clara: separa errores de configuración del cliente (4xx) de fallos del proveedor (502/504)",
        "Diagnósticos prácticos: mensajes específicos indican si el fallo fue por cuota, autenticación o modelo",
        "Control de límites: las respuestas 429 ofrecen pistas claras sobre ventanas de tiempo para RPM y TPM"
      ]
    },
    {
      "id": "env-config",
      "title": "Variables de entorno y despliegue",
      "group": "system",
      "description": "Opciones de configuración para alojar MyAIrouter en producción con Docker, PostgreSQL, systemd y seguridad avanzada.",
      "subsections": [
        {
          "title": "Variables de entorno principales",
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
          "title": "Ejemplo de Docker Compose para producción",
          "code": {
            "title": "docker-compose.prod.yml",
            "lang": "yaml",
            "content": "version: \"3.8\"\n\nservices:\n  myairouter:\n    image: myairouter:latest\n    restart: always\n    ports:\n      - \"8000:8000\"\n    environment:\n      - ROUTER_MASTER_KEY=<GENERATED_ROUTER_MASTER_KEY>\n      - DATABASE_URL=postgresql+asyncpg://router:<POSTGRES_PASSWORD>@postgres:5432/routerdb\n      - ROUTER_PORT=8000\n      - ROUTER_HOST=0.0.0.0\n      - LOG_LEVEL=INFO\n      - DEFAULT_TIMEOUT=45.0\n      - CORS_ORIGINS=https://ai.yourcompany.internal\n    depends_on:\n      - postgres\n\n  postgres:\n    image: postgres:16-alpine\n    restart: always\n    environment:\n      POSTGRES_USER: router\n      POSTGRES_PASSWORD: <POSTGRES_PASSWORD>\n      POSTGRES_DB: routerdb\n    volumes:\n      - pgdata:/var/lib/postgresql/data\n\nvolumes:\n  pgdata:"
          }
        }
      ],
      "badge": "Deployment",
      "highlights": [
        "ROUTER_MASTER_KEY: Clave base64 de 32 bytes crítica para cifrar credenciales en reposo",
        "DATABASE_URL: Cambie de SQLite por defecto a PostgreSQL de alta concurrencia",
        "CORS_ORIGINS: Lista de orígenes permitidos separados por comas para acceso web seguro",
        "OLLAMA_BASE_URL: Dirección por defecto para el servicio de Ollama (http://localhost:11434)"
      ]
    }
  ]
};
