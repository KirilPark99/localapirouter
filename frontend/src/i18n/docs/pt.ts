import { DocContent } from "./types";

export const pt: DocContent = {
  "ui": {
    "searchPlaceholder": "Pesquisar documentação (ex: Ollama, Fallback, Fusion)...",
    "noSectionsFound": "Nenhuma seção correspondente encontrada.",
    "prevSection": "Seção anterior",
    "nextSection": "Próxima seção",
    "copied": "Copiado!",
    "copy": "Copiar código",
    "endpoints": "Endpoints",
    "tocTitle": "Índice da Documentação"
  },
  "sections": [
    {
      "id": "overview",
      "title": "Visão Geral do Sistema",
      "group": "intro",
      "description": "Gateway LLM universal auto-hospedado com motores Direct, Priority Fallback e Model Fusion, pool de chaves e compatibilidade com Ollama.",
      "subsections": [
        {
          "title": "Comparação dos Modos de Roteamento",
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
        "3 motores de roteamento: Direto, Fallback prioritário (aninhado) e Fusão de modelos",
        "Compatibilidade total com OpenAI API (/v1/chat/completions) e Ollama (/api/tags)",
        "Segurança avançada: criptografia AES-128-CBC Fernet usando ROUTER_MASTER_KEY",
        "Isolamento automático de falhas com Circuit Breaker e suporte a proxies"
      ]
    },
    {
      "id": "quickstart",
      "title": "Início Rápido",
      "group": "intro",
      "description": "Conecte qualquer biblioteca OpenAI, cURL ou cliente Ollama ao gateway MyAIrouter em segundos.",
      "subsections": [
        {
          "title": "1. Início rápido com cURL",
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
      "title": "Endereçamento e Resolução de Modelos",
      "group": "models",
      "description": "Endereçamento flexível em vários modos: slugs canônicos, identificadores por provedor, rotas de fallback e júris de fusão.",
      "subsections": [
        {
          "title": "Hierarquia de Endereçamento",
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
      "title": "Compatibilidade com Ollama API",
      "group": "models",
      "description": "Suporte nativo a Ollama CLI, Continue.dev, Open WebUI e Obsidian Copilot sem alterar código cliente.",
      "subsections": [
        {
          "title": "Integração com Ollama CLI",
          "code": {
            "title": "Bash / Terminal",
            "lang": "bash",
            "content": "# Point your local Ollama client or IDE extension to MyAIrouter\nexport OLLAMA_HOST=http://localhost:8000\n\n# View all registered models, route profiles, and fusion profiles\nollama list\n\n# Execute queries directly through the OpenAI-compatible gateway\nollama run gemini-2.5-flash \"Write a Fibonacci function in Go\" "
          }
        },
        {
          "title": "Endpoints Ollama Suportados",
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
      "title": "Classificações e Benchmarks",
      "group": "models",
      "description": "Métricas automáticas de Artificial Analysis: Índice de qualidade (0-100), velocidade de geração, preços e limite de contexto.",
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
      "title": "Limites e Cotas de API",
      "group": "models",
      "description": "Controle de taxa em dois níveis: proteja contas upstream com limites de RPM/TPM por credencial e regule clientes.",
      "subsections": [
        {
          "title": "Controle de Limites em Duas Camadas",
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
      "title": "Níveis de Raciocínio (CoT)",
      "group": "routing",
      "description": "Parâmetro universal reasoning_effort com tradução bidirecional entre OpenAI, Anthropic, Google Gemini e Groq.",
      "subsections": [
        {
          "title": "Exemplo de Parâmetro de Raciocínio",
          "code": {
            "title": "cURL Reasoning Request",
            "lang": "bash",
            "content": "# Send standard reasoning_effort to any provider\ncurl http://localhost:8000/v1/chat/completions \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\n    \"model\": \"gemini-2.5-flash\",\n    \"messages\": [{\"role\": \"user\", \"content\": \"Prove that the square root of 2 is irrational.\"}],\n    \"reasoning_effort\": \"high\"\n  }'"
          }
        },
        {
          "title": "Matriz de Tradução entre Provedores",
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
      "title": "Roteamento Direto (Direct)",
      "group": "routing",
      "description": "Roteamento direto ultrarrápido para um modelo específico com balanceamento round-robin e failover automático de chaves.",
      "subsections": [
        {
          "title": "Exemplo de Roteamento Direto",
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
      "title": "Cadeias de Fallback e Prioridade",
      "group": "routing",
      "description": "Filas de alternância em vários níveis em erros 429 ou 5xx, com suporte a perfis aninhados e grupos de chaves.",
      "subsections": [
        {
          "title": "Mecânica do Fallback",
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
      "title": "Fusão de Modelos (Ensembles)",
      "group": "routing",
      "description": "Execute múltiplos LLMs em paralelo e sintetize a resposta ideal usando um modelo Juiz com streaming de raciocínio em tempo real.",
      "subsections": [
        {
          "title": "Exemplo de Deliberação em Streaming",
          "code": {
            "title": "SSE Fusion Stream",
            "lang": "bash",
            "content": "curl http://localhost:8000/v1/chat/completions \\\n  -H \"Content-Type: application/json\" \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\n    \"model\": \"fusion/code-jury\",\n    \"messages\": [{\"role\": \"user\", \"content\": \"Analyze time complexity of quicksort\"}],\n    \"stream\": true\n  }'\n\n# Streamed SSE chunks contain real-time deliberation in reasoning_content:\n# data: {\"choices\":[{\"delta\":{\"reasoning_content\":\"### 🧬 Fusion Ensemble Deliberation\\n...\"}}]}\n# ...\n# data: {\"choices\":[{\"delta\":{\"content\":\"Final evaluated answer...\"}}]}"
          }
        },
        {
          "title": "Estratégias de Avaliação do Juiz",
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
      "title": "Provedores Suportados e Modo Keyless",
      "group": "management",
      "description": "Integração nativa com mais de 12 provedores de LLM na nuvem e runtimes locais, com modo Keyless para instâncias do Ollama.",
      "subsections": [
        {
          "title": "Matriz de Recursos dos Provedores",
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
          "title": "Configurando Ollama Local em Modo Keyless",
          "code": {
            "title": "Add Ollama via API or UI",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/credentials \\\n  -H \"Content-Type: application/json\" \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\" \\\n  -d '{\n    \"provider\": \"ollama\",\n    \"name\": \"Local Workstation Ollama\",\n    \"api_key\": \"keyless\",\n    \"base_url\": \"http://127.0.0.1:11434\",\n    \"is_active\": true\n  }'"
          }
        }
      ],
      "badge": "Multi-Provider",
      "highlights": [
        "Suporte total a OpenAI, Anthropic, Gemini, Groq, DeepSeek, Cerebras, Mistral, xAI, OpenRouter",
        "Modo Keyless: conecte o Ollama local (http://localhost:11434) sem necessidade de chaves falsas",
        "Suporte a Base URL personalizada para vLLM, LM Studio e gateways corporativos",
        "Vinculação dedicada de proxy HTTP/SOCKS5 por credencial de provedor"
      ]
    },
    {
      "id": "credentials",
      "title": "Credenciais Upstream e Cofre de Chaves",
      "group": "management",
      "description": "Armazenamento criptografado de nível bancário para chaves API com verificações de integridade e organização em grupos.",
      "subsections": [
        {
          "title": "Disparando Verificação de Integridade",
          "code": {
            "title": "Health Check Endpoint",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/credentials/cred_abc123/health-check \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\"\n\n# Response:\n# {\n#   \"status\": \"healthy\",\n#   \"latency_ms\": 142.5,\n#   \"checked_at\": \"2026-09-13T14:15:00Z\"\n# }"
          }
        }
      ],
      "badge": "Encrypted Vault",
      "highlights": [
        "Criptografia simétrica AES-128-CBC Fernet: chaves criptografadas antes da gravação",
        "Mascaramento de chaves: os segredos nunca são exibidos na interface (ex: sk-ant...7a9f)",
        "Verificações ativas de integridade: testes automáticos de conectividade e cotas",
        "Grupos de credenciais: organize chaves em pastas (Produção, Staging, Backup)"
      ]
    },
    {
      "id": "api-keys",
      "title": "Chaves API do Router e Permissões",
      "group": "management",
      "description": "Emita, monitore e revogue tokens de clientes (sk-router-...) com limites individuais de taxa e listas de modelos permitidos.",
      "subsections": [
        {
          "title": "Parâmetros da Chave do Cliente",
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
        "Hash unidirecional SHA-256: chaves secretas nunca são salvas em texto simples no banco",
        "Limitação de taxa: controle granular de requisições por minuto (RPM) e tokens por minuto (TPM)",
        "Whitelist de modelos: restrinja chaves a modelos ou perfis de roteamento específicos",
        "Expiração automática: defina prazos de validade para acessos temporários de equipe"
      ]
    },
    {
      "id": "proxies",
      "title": "Gerenciamento de Proxies e Geo-Tagging",
      "group": "management",
      "description": "Roteie o tráfego upstream através de proxies HTTP e SOCKS5 autenticados com medição de latência e tags regionais.",
      "subsections": [
        {
          "title": "Exemplos de Formato de Proxy",
          "code": {
            "title": "Supported Proxy URI Formats",
            "lang": "bash",
            "content": "# Standard HTTP proxy:\nhttp://proxy.corporate.internal:8080\n\n# Authenticated HTTP proxy:\nhttp://username:<PROXY_PASSWORD>@us-east.proxy-vendor.com:3128\n\n# Authenticated SOCKS5 proxy:\nsocks5://proxyuser:<PROXY_PASSWORD>@sg-node.vpn-provider.net:1080"
          }
        }
      ],
      "badge": "Egress & Geo",
      "highlights": [
        "Suporte completo a protocolos: HTTP, HTTPS e SOCKS5 (socks5://user:pass@host:port)",
        "Tags de país: atribua códigos ISO (US, DE, SG, JP) para cumprir requisitos regionais",
        "Benchmarking de latência: teste de tempo de ida e volta (RTT) em tempo real",
        "Isolamento por credencial: associe proxies dedicados a chaves ou provedores específicos"
      ]
    },
    {
      "id": "backup-restore",
      "title": "Backup Criptografado e Recuperação",
      "group": "system",
      "description": "Exporte e restaure configurações completas com criptografia AES-GCM derivada de senha, cobrindo modelos, rotas e proxies.",
      "subsections": [
        {
          "title": "Exportando Backup via API",
          "code": {
            "title": "Encrypted Backup Endpoint",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/system/backup \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{\"passphrase\": \"<BACKUP_PASSPHRASE>\"}' \\\n  -o router_backup_2026-09-13.enc"
          }
        }
      ],
      "badge": "Disaster Recovery",
      "highlights": [
        "Derivação de chaves PBKDF2 HMAC-SHA256 com salt aleatório e autenticação AES-256-GCM",
        "Snapshot completo: modelos, credenciais, perfis de rota, júris de fusão, proxies e chaves API",
        "Restauração flexível: mesclar com registros existentes ou substituição completa",
        "Sem dependência de fornecedor: migre facilmente entre instâncias VPS e contêineres Docker"
      ]
    },
    {
      "id": "analytics",
      "title": "Análise, Logs e Inspetor de Rastreamento",
      "group": "system",
      "description": "Telemetria de tráfego de ponta a ponta com contabilidade de tokens, estimativa de custos, gráficos de latência e inspeção Waterfall.",
      "subsections": [
        {
          "title": "Esquema da Entrada de Log",
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
        "Contabilidade tripla de tokens: rastreamento independente de prompt, completion e raciocínio",
        "Inspetor Waterfall: detalhamento visual passo a passo de cada salto, timeout e tentativa de fallback",
        "Medidor de gastos: estimativa de custo em USD em tempo real com base nos preços dos provedores",
        "Logs de auditoria exportáveis: filtre e baixe registros por código de status, cliente ou data"
      ]
    },
    {
      "id": "circuit-breaker",
      "title": "Circuit Breaker e Isolamento de Falhas",
      "group": "system",
      "description": "Máquina de estados finitos que bloqueia tráfego para provedores com falhas, protegendo clientes contra timeouts em cascata.",
      "subsections": [
        {
          "title": "Ciclo de Vida do FSM",
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
        "3 estados operacionais: CLOSED (saudável), OPEN (isolado, tráfego desviado), HALF-OPEN (testando recuperação)",
        "Condição de disparo: ativa-se após 5 erros 5xx consecutivos ou tempos limite de rede",
        "Período de resfriamento: mantém o tráfego afastado por 30 segundos antes de enviar um probe de teste",
        "Transparente para o cliente: o próximo candidato no Fallback assume sem erros visíveis"
      ]
    },
    {
      "id": "api-reference",
      "title": "Referência Completa de Endpoints da API",
      "group": "system",
      "description": "Índice abrangente de todos os endpoints REST públicos de inferência e administração do MyAIrouter.",
      "subsections": [
        {
          "title": "Tabela de Endpoints Públicos e Administrativos",
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
        "Entrada OpenAI: /v1/chat/completions, /v1/models (compatibilidade direta com qualquer SDK)",
        "Protocolo Ollama: /api/tags, /api/show, /api/version, /api/chat",
        "Gerenciamento principal: /api/v1/credentials, /api/v1/models, /api/v1/routes, /api/v1/fusion",
        "Sistema e integridade: /health, /api/v1/system/backup, /api/v1/system/restore, /api/v1/system/stats"
      ]
    },
    {
      "id": "errors",
      "title": "Códigos de Erro HTTP e Resolução de Problemas",
      "group": "system",
      "description": "Detalhamento dos códigos de status HTTP retornados pelo router, especificações do JSON de erro e passos para solução de problemas.",
      "subsections": [
        {
          "title": "Catálogo de Códigos de Status HTTP",
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
        "Esquema de erro padrão OpenAI: {\"error\": {\"message\": \"...\", \"type\": \"...\", \"code\": \"...\"}}",
        "Distinção clara: diferencia erros do cliente (4xx) de falhas nos provedores upstream (502/504)",
        "Diagnósticos acionáveis: mensagens específicas indicando se a falha foi cota, autenticação ou modelo",
        "Controle de taxa: respostas 429 fornecem orientações claras de espera para limites RPM e TPM"
      ]
    },
    {
      "id": "env-config",
      "title": "Variáveis de Ambiente e Implantação",
      "group": "system",
      "description": "Opções de configuração para hospedar o MyAIrouter em produção com Docker, PostgreSQL, systemd e configurações de segurança.",
      "subsections": [
        {
          "title": "Principais Variáveis de Ambiente",
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
          "title": "Exemplo de Docker Compose para Produção",
          "code": {
            "title": "docker-compose.prod.yml",
            "lang": "yaml",
            "content": "version: \"3.8\"\n\nservices:\n  myairouter:\n    image: myairouter:latest\n    restart: always\n    ports:\n      - \"8000:8000\"\n    environment:\n      - ROUTER_MASTER_KEY=<GENERATED_ROUTER_MASTER_KEY>\n      - DATABASE_URL=postgresql+asyncpg://router:<POSTGRES_PASSWORD>@postgres:5432/routerdb\n      - ROUTER_PORT=8000\n      - ROUTER_HOST=0.0.0.0\n      - LOG_LEVEL=INFO\n      - DEFAULT_TIMEOUT=45.0\n      - CORS_ORIGINS=https://ai.yourcompany.internal\n    depends_on:\n      - postgres\n\n  postgres:\n    image: postgres:16-alpine\n    restart: always\n    environment:\n      POSTGRES_USER: router\n      POSTGRES_PASSWORD: <POSTGRES_PASSWORD>\n      POSTGRES_DB: routerdb\n    volumes:\n      - pgdata:/var/lib/postgresql/data\n\nvolumes:\n  pgdata:"
          }
        }
      ],
      "badge": "Deployment",
      "highlights": [
        "ROUTER_MASTER_KEY: Chave base64 de 32 bytes crítica para criptografar credenciais em repouso",
        "DATABASE_URL: Mude do SQLite padrão para PostgreSQL para alta concorrência",
        "CORS_ORIGINS: Lista de origens permitidas separadas por vírgula para acesso seguro à web",
        "OLLAMA_BASE_URL: URL padrão para o serviço Ollama (padrão: http://localhost:11434)"
      ]
    }
  ]
};
