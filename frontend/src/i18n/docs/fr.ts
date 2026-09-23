import { DocContent } from "./types";

export const fr: DocContent = {
  "ui": {
    "searchPlaceholder": "Rechercher dans la documentation (ex. Ollama, Fallback, Fusion)...",
    "noSectionsFound": "Aucune section correspondante trouvée.",
    "prevSection": "Section précédente",
    "nextSection": "Section suivante",
    "copied": "Copié !",
    "copy": "Copier le code",
    "endpoints": "Points de terminaison",
    "tocTitle": "Sommaire"
  },
  "sections": [
    {
      "id": "overview",
      "title": "Présentation du système",
      "group": "intro",
      "description": "Passerelle LLM auto-hébergée universelle avec moteurs Direct, Repli prioritaire et Fusion, mutualisation de clés et compatibilité Ollama.",
      "subsections": [
        {
          "title": "Comparaison des modes de routage",
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
        "3 moteurs de routage : Direct, Repli prioritaire (imbriqué) et Fusion de modèles",
        "Compatibilité directe avec l'API OpenAI (/v1/chat/completions) et Ollama (/api/tags)",
        "Sécurité renforcée : chiffrement AES-128-CBC Fernet via ROUTER_MASTER_KEY",
        "Disjoncteur automatique (Circuit Breaker) avec auto-guérison et liaison proxy"
      ]
    },
    {
      "id": "quickstart",
      "title": "Démarrage rapide",
      "group": "intro",
      "description": "Connectez n'importe quelle bibliothèque OpenAI, cURL ou client Ollama à MyAIrouter en quelques secondes.",
      "subsections": [
        {
          "title": "1. Appel rapide avec cURL",
          "code": {
            "title": "cURL Chat Completion",
            "lang": "bash",
            "content": "curl http://localhost:8000/v1/chat/completions \\\n  -H \"Content-Type: application/json\" \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\n    \"model\": \"gemini-2.5-flash\",\n    \"messages\": [{\"role\": \"user\", \"content\": \"Explain quantum computing in one sentence.\"}],\n    \"temperature\": 0.7\n  }'"
          }
        },
        {
          "title": "2. SDK Python OpenAI",
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
      "title": "Adressage et résolution des modèles",
      "group": "models",
      "description": "Adressage flexible à plusieurs niveaux : slugs canoniques, identifiants qualifiés par fournisseur, routes de repli et jurys de fusion.",
      "subsections": [
        {
          "title": "Hiérarchie d'adressage",
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
      "title": "Compatibilité API Ollama",
      "group": "models",
      "description": "Prise en charge native directe d'Ollama CLI, Continue.dev, Open WebUI et Obsidian Copilot sans modifier le code client.",
      "subsections": [
        {
          "title": "Intégration Ollama CLI",
          "code": {
            "title": "Bash / Terminal",
            "lang": "bash",
            "content": "# Point your local Ollama client or IDE extension to MyAIrouter\nexport OLLAMA_HOST=http://localhost:8000\n\n# View all registered models, route profiles, and fusion profiles\nollama list\n\n# Execute queries directly through the OpenAI-compatible gateway\nollama run gemini-2.5-flash \"Write a Fibonacci function in Go\" "
          }
        },
        {
          "title": "Points de terminaison Ollama pris en charge",
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
      "title": "Notes et bancs d'essai",
      "group": "models",
      "description": "Métriques intégrées d'Artificial Analysis : Indice de qualité (0-100), vitesse de génération, tarification et contexte.",
      "subsections": [
        {
          "title": "Indicateurs d'évaluation",
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
      "title": "Limites et quotas d'API",
      "group": "models",
      "description": "Limitation de débit à deux niveaux : protégez les comptes amont via des limites RPM/TPM par clé et gérez les quotas clients.",
      "subsections": [
        {
          "title": "Contrôle des limites à double niveau",
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
      "title": "Niveaux de raisonnement (CoT)",
      "group": "routing",
      "description": "Paramètre universel reasoning_effort avec conversion transparente entre OpenAI, Anthropic, Google Gemini et Groq.",
      "subsections": [
        {
          "title": "Exemple de paramètre de raisonnement",
          "code": {
            "title": "cURL Reasoning Request",
            "lang": "bash",
            "content": "# Send standard reasoning_effort to any provider\ncurl http://localhost:8000/v1/chat/completions \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\n    \"model\": \"gemini-2.5-flash\",\n    \"messages\": [{\"role\": \"user\", \"content\": \"Prove that the square root of 2 is irrational.\"}],\n    \"reasoning_effort\": \"high\"\n  }'"
          }
        },
        {
          "title": "Matrice de conversion des fournisseurs",
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
      "title": "Moteur de routage direct",
      "group": "routing",
      "description": "Routage direct ultra-rapide vers un modèle spécifique avec équilibrage round-robin et basculement automatique de clé.",
      "subsections": [
        {
          "title": "Exemple d'appel direct",
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
      "title": "Chaînes de repli prioritaire",
      "group": "routing",
      "description": "Files d'attente multi-niveaux en cas de quota 429 ou d'erreur 5xx, avec profils imbriqués et groupes de clés.",
      "subsections": [
        {
          "title": "Mécanisme de basculement",
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
      "title": "Fusion de modèles (Ensembles IA)",
      "group": "routing",
      "description": "Exécutez plusieurs LLM en parallèle et synthétisez la réponse optimale grâce à un modèle Juge avec streaming des réflexions.",
      "subsections": [
        {
          "title": "Exemple de délibération en streaming",
          "code": {
            "title": "SSE Fusion Stream",
            "lang": "bash",
            "content": "curl http://localhost:8000/v1/chat/completions \\\n  -H \"Content-Type: application/json\" \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\n    \"model\": \"fusion/code-jury\",\n    \"messages\": [{\"role\": \"user\", \"content\": \"Analyze time complexity of quicksort\"}],\n    \"stream\": true\n  }'\n\n# Streamed SSE chunks contain real-time deliberation in reasoning_content:\n# data: {\"choices\":[{\"delta\":{\"reasoning_content\":\"### 🧬 Fusion Ensemble Deliberation\\n...\"}}]}\n# ...\n# data: {\"choices\":[{\"delta\":{\"content\":\"Final evaluated answer...\"}}]}"
          }
        },
        {
          "title": "Stratégies d'arbitrage du Juge",
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
      "title": "Fournisseurs pris en charge et mode sans clé",
      "group": "management",
      "description": "Intégration native avec plus de 12 fournisseurs de LLM cloud et moteurs locaux, avec mode sans clé pour les instances Ollama.",
      "subsections": [
        {
          "title": "Matrice des capacités des fournisseurs",
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
          "title": "Configuration d'Ollama local sans clé",
          "code": {
            "title": "Add Ollama via API or UI",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/credentials \\\n  -H \"Content-Type: application/json\" \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\" \\\n  -d '{\n    \"provider\": \"ollama\",\n    \"name\": \"Local Workstation Ollama\",\n    \"api_key\": \"keyless\",\n    \"base_url\": \"http://127.0.0.1:11434\",\n    \"is_active\": true\n  }'"
          }
        }
      ],
      "badge": "Multi-Provider",
      "highlights": [
        "Prise en charge d'OpenAI, Anthropic, Gemini, Groq, DeepSeek, Cerebras, Mistral, xAI, OpenRouter",
        "Mode sans clé : connectez Ollama local (http://localhost:11434) sans fausses clés API",
        "URL de base personnalisée pour vLLM, LM Studio et passerelles d'entreprise compatibles OpenAI",
        "Liaison de proxy HTTP/SOCKS5 dédiée par identifiant de fournisseur"
      ]
    },
    {
      "id": "credentials",
      "title": "Identifiants amont et coffre-fort de clés",
      "group": "management",
      "description": "Stockage chiffré de niveau bancaire pour les clés API des fournisseurs, avec vérification de santé et balisage par groupe.",
      "subsections": [
        {
          "title": "Vérification manuelle des identifiants",
          "code": {
            "title": "Health Check Endpoint",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/credentials/cred_abc123/health-check \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\"\n\n# Response:\n# {\n#   \"status\": \"healthy\",\n#   \"latency_ms\": 142.5,\n#   \"checked_at\": \"2026-09-13T14:15:00Z\"\n# }"
          }
        }
      ],
      "badge": "Encrypted Vault",
      "highlights": [
        "Chiffrement symétrique AES-128-CBC Fernet : clés chiffrées avant insertion SQLite",
        "Masquage des clés : les secrets ne sont jamais exposés dans l'interface (ex. sk-ant...7a9f)",
        "Contrôles de santé proactifs : tests de connectivité réguliers auprès des fournisseurs",
        "Groupes d'identifiants : organisez les clés en dossiers logiques (Prod, Staging, Backup)"
      ]
    },
    {
      "id": "api-keys",
      "title": "Clés API du routeur et autorisations",
      "group": "management",
      "description": "Émettez, surveillez et révoquez des jetons clients (sk-router-...) avec limites de débit par clé et listes blanches de modèles.",
      "subsections": [
        {
          "title": "Paramètres des clés clientes",
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
        "Hachage SHA-256 unidirectionnel : les clés secrètes ne sont jamais enregistrées en clair",
        "Limites de débit : contrôle précis des requêtes par minute (RPM) et tokens par minute (TPM)",
        "Liste blanche de modèles : restreignez l'accès à des modèles ou profils spécifiques",
        "Expiration automatique : définissez des dates de fin de validité pour les accès temporaires"
      ]
    },
    {
      "id": "proxies",
      "title": "Gestion des proxys et étiquetage géographique",
      "group": "management",
      "description": "Acheminez le trafic amont via des proxys HTTP et SOCKS5 avec authentification, suivi de latence et drapeaux géographiques.",
      "subsections": [
        {
          "title": "Exemples de format de proxy",
          "code": {
            "title": "Supported Proxy URI Formats",
            "lang": "bash",
            "content": "# Standard HTTP proxy:\nhttp://proxy.corporate.internal:8080\n\n# Authenticated HTTP proxy:\nhttp://username:<PROXY_PASSWORD>@us-east.proxy-vendor.com:3128\n\n# Authenticated SOCKS5 proxy:\nsocks5://proxyuser:<PROXY_PASSWORD>@sg-node.vpn-provider.net:1080"
          }
        }
      ],
      "badge": "Egress & Geo",
      "highlights": [
        "Prise en charge complète : HTTP, HTTPS et SOCKS5 (socks5://user:pass@host:port)",
        "Drapeaux géographiques : associez des codes ISO (US, DE, SG, JP) pour contourner les blocages",
        "Mesure de latence : test du temps d'aller-retour (RTT) en temps réel à chaque vérification",
        "Isolation par identifiant : assignez un proxy dédié à une clé ou un fournisseur spécifique"
      ]
    },
    {
      "id": "backup-restore",
      "title": "Sauvegarde chiffrée et reprise après sinistre",
      "group": "system",
      "description": "Exportez et restaurez des configurations complètes avec chiffrement AES-GCM basé sur mot de passe, couvrant modèles, routes et proxys.",
      "subsections": [
        {
          "title": "Exporter la sauvegarde via API",
          "code": {
            "title": "Encrypted Backup Endpoint",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/system/backup \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{\"passphrase\": \"<BACKUP_PASSPHRASE>\"}' \\\n  -o router_backup_2026-09-13.enc"
          }
        }
      ],
      "badge": "Disaster Recovery",
      "highlights": [
        "Dérivation de clé PBKDF2 HMAC-SHA256 avec sel aléatoire de 16 octets et tag AES-256-GCM",
        "Instantané système complet : modèles, identifiants, routes, jurys de fusion, proxys et clés",
        "Restauration sélective ou totale : option pour fusionner avec l'existant ou remplacement complet",
        "Zéro dépendance : migration facile entre serveurs VPS, conteneurs Docker ou régions cloud"
      ]
    },
    {
      "id": "analytics",
      "title": "Analytique, journaux et inspecteur de traces",
      "group": "system",
      "description": "Télémétrie complète du trafic avec comptabilisation des tokens, estimation des coûts, graphiques de latence et inspection Waterfall.",
      "subsections": [
        {
          "title": "Schéma des entrées du journal",
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
        "Comptabilisation triple des tokens : suivi indépendant des tokens de prompt, complétion et raisonnement",
        "Inspecteur Waterfall : décomposition visuelle étape par étape de chaque saut, délai et tentative",
        "Calcul des coûts : estimation financière en USD en temps réel selon les barèmes des fournisseurs",
        "Journaux d'audit exportables : filtrez et téléchargez les journaux par code d'état, clé ou modèle"
      ]
    },
    {
      "id": "circuit-breaker",
      "title": "Disjoncteur et isolation des pannes",
      "group": "system",
      "description": "Machine à états finis qui bloque le trafic vers les fournisseurs défaillants ou surchargés, évitant les expirations en cascade.",
      "subsections": [
        {
          "title": "Cycle de vie des états FSM",
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
        "3 états opérationnels : CLOSED (sain), OPEN (isolé, trafic dévié), HALF-OPEN (test de reprise)",
        "Déclenchement automatique : bascule après 5 erreurs 5xx consécutives ou délais d'attente réseau",
        "Période de refroidissement : bloque le trafic pendant 30 secondes avant d'envoyer une sonde de test",
        "Transparence totale pour le client : le modèle suivant dans la chaîne de repli prend le relais sans erreur"
      ]
    },
    {
      "id": "api-reference",
      "title": "Référence complète des points de terminaison",
      "group": "system",
      "description": "Index exhaustif de tous les points de terminaison REST publics d'inférence et d'administration de MyAIrouter.",
      "subsections": [
        {
          "title": "Tableau des points de terminaison publics et admin",
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
        "Ingestion OpenAI : /v1/chat/completions, /v1/models (remplacement direct pour tout client)",
        "Protocole Ollama : /api/tags, /api/show, /api/version, /api/chat",
        "Gestion principale : /api/v1/credentials, /api/v1/models, /api/v1/routes, /api/v1/fusion",
        "Système et santé : /health, /api/v1/system/backup, /api/v1/system/restore, /api/v1/system/stats"
      ]
    },
    {
      "id": "errors",
      "title": "Codes d'erreur HTTP et dépannage",
      "group": "system",
      "description": "Détail des codes d'état HTTP retournés par le routeur, spécifications des erreurs JSON et étapes de dépannage.",
      "subsections": [
        {
          "title": "Catalogue des codes d'état HTTP",
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
        "Schéma d'erreur standard OpenAI : {\"error\": {\"message\": \"...\", \"type\": \"...\", \"code\": \"...\"}}",
        "Distinction claire : sépare les erreurs client (4xx) des défaillances de fournisseurs amont (502/504)",
        "Diagnostics exploitables : messages précis indiquant si la panne est due au quota, à l'auth ou au modèle",
        "Gestion des limites : les réponses 429 fournissent des indications claires de temporisation"
      ]
    },
    {
      "id": "env-config",
      "title": "Variables d'environnement et déploiement",
      "group": "system",
      "description": "Options de configuration pour héberger MyAIrouter en production avec Docker, PostgreSQL, systemd et sécurité renforcée.",
      "subsections": [
        {
          "title": "Variables d'environnement clés",
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
          "title": "Exemple Docker Compose pour production",
          "code": {
            "title": "docker-compose.prod.yml",
            "lang": "yaml",
            "content": "version: \"3.8\"\n\nservices:\n  myairouter:\n    image: myairouter:latest\n    restart: always\n    ports:\n      - \"8000:8000\"\n    environment:\n      - ROUTER_MASTER_KEY=<GENERATED_ROUTER_MASTER_KEY>\n      - DATABASE_URL=postgresql+asyncpg://router:<POSTGRES_PASSWORD>@postgres:5432/routerdb\n      - ROUTER_PORT=8000\n      - ROUTER_HOST=0.0.0.0\n      - LOG_LEVEL=INFO\n      - DEFAULT_TIMEOUT=45.0\n      - CORS_ORIGINS=https://ai.yourcompany.internal\n    depends_on:\n      - postgres\n\n  postgres:\n    image: postgres:16-alpine\n    restart: always\n    environment:\n      POSTGRES_USER: router\n      POSTGRES_PASSWORD: <POSTGRES_PASSWORD>\n      POSTGRES_DB: routerdb\n    volumes:\n      - pgdata:/var/lib/postgresql/data\n\nvolumes:\n  pgdata:"
          }
        }
      ],
      "badge": "Deployment",
      "highlights": [
        "ROUTER_MASTER_KEY : Clé base64 critique de 32 octets pour chiffrer les identifiants au repos",
        "DATABASE_URL : Basculez du SQLite par défaut vers un PostgreSQL haute performance",
        "CORS_ORIGINS : Liste d'origines autorisées séparées par des virgules pour sécuriser le web",
        "OLLAMA_BASE_URL : URL de détection pour le démon Ollama (par défaut http://localhost:11434)"
      ]
    }
  ]
};
