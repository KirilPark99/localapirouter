import { DocContent } from "./types";

export const ja: DocContent = {
  "ui": {
    "searchPlaceholder": "ドキュメントを検索（例: Ollama、Fallback、Fusion、APIキー）...",
    "noSectionsFound": "一致するセクションが見つかりません。",
    "prevSection": "前のセクション",
    "nextSection": "次のセクション",
    "copied": "コピー完了！",
    "copy": "コードをコピー",
    "endpoints": "エンドポイント",
    "tocTitle": "目次"
  },
  "sections": [
    {
      "id": "overview",
      "title": "システム概要",
      "group": "intro",
      "description": "Direct、Priority Fallback、Model Fusionの3つのルーティングエンジンとOllama互換性を備えたセルフホスト型LLMゲートウェイ。",
      "subsections": [
        {
          "title": "ルーティングモードの比較",
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
        "3つのルーティングエンジン：ダイレクト、優先度フォールバック（入れ子対応）、モデル融合",
        "OpenAI API (/v1/chat/completions) および Ollama (/api/tags) との完全互換",
        "強固なセキュリティ：ROUTER_MASTER_KEY による AES-128-CBC 暗号化",
        "サーキットブレーカーによる障害自動隔離とジオプロキシ連携"
      ]
    },
    {
      "id": "quickstart",
      "title": "クイックスタート",
      "group": "intro",
      "description": "OpenAI SDK、cURL、またはOllamaクライアントをわずか数秒でMyAIrouterに接続。",
      "subsections": [
        {
          "title": "1. cURL クイックスタート",
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
      "title": "モデルのアドレッシングと解決",
      "group": "models",
      "description": "柔軟なマルチモードアドレッシング：正規スラッグ、プロバイダー修飾子、フォールバックルート、フュージョン審査団。",
      "subsections": [
        {
          "title": "アドレッシングの階層",
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
      "title": "Ollama API 互換性",
      "group": "models",
      "description": "クライアントコードを変更することなく、Ollama CLI、Continue.dev、Open WebUI、Obsidian Copilotをそのまま利用可能。",
      "subsections": [
        {
          "title": "Ollama CLI との統合",
          "code": {
            "title": "Bash / Terminal",
            "lang": "bash",
            "content": "# Point your local Ollama client or IDE extension to MyAIrouter\nexport OLLAMA_HOST=http://localhost:8000\n\n# View all registered models, route profiles, and fusion profiles\nollama list\n\n# Execute queries directly through the OpenAI-compatible gateway\nollama run gemini-2.5-flash \"Write a Fibonacci function in Go\" "
          }
        },
        {
          "title": "サポートされる Ollama エンドポイント",
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
      "title": "レーティングとベンチマーク",
      "group": "models",
      "description": "Artificial Analysisの自動ベンチマーク連携：品質スコア（0-100）、生成速度（tok/s）、料金、コンテキスト長。",
      "subsections": [
        {
          "title": "ベンチマーク指標",
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
      "title": "API 制限とクォータ",
      "group": "models",
      "description": "2層構造のレート制限：認証情報ごとのRPM/TPM制限で上流アカウントを保護し、クライアント利用を細かく制御。",
      "subsections": [
        {
          "title": "2層制限の仕組み",
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
      "title": "思考レベル (CoT)",
      "group": "routing",
      "description": "OpenAI、Anthropic、Google Gemini、Groqの間で自動相互変換されるユニバーサルな reasoning_effort パラメータ。",
      "subsections": [
        {
          "title": "思考パラメータのリクエスト例",
          "code": {
            "title": "cURL Reasoning Request",
            "lang": "bash",
            "content": "# Send standard reasoning_effort to any provider\ncurl http://localhost:8000/v1/chat/completions \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\n    \"model\": \"gemini-2.5-flash\",\n    \"messages\": [{\"role\": \"user\", \"content\": \"Prove that the square root of 2 is irrational.\"}],\n    \"reasoning_effort\": \"high\"\n  }'"
          }
        },
        {
          "title": "プロバイダー変換マトリクス",
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
      "title": "ダイレクトルーティング",
      "group": "routing",
      "description": "ラウンドロビン方式のキー分散と障害時の自動フェイルオーバーを備えた超高速ダイレクトルーティング。",
      "subsections": [
        {
          "title": "ダイレクト指定のコード例",
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
      "title": "優先度とフォールバックチェーン",
      "group": "routing",
      "description": "429 レート制限や 5xx 障害発生時に自動切り替えを行う多層フォールバックキュー。入れ子プロファイルやキーグループに対応。",
      "subsections": [
        {
          "title": "フォールバックの動作原理",
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
      "title": "モデル融合 (Model Fusion)",
      "group": "routing",
      "description": "複数のLLMを並行実行し、Judgeモデルが最適な回答を統合・生成。審査過程の思考ストリーミングにも完全対応。",
      "subsections": [
        {
          "title": "審査思考ストリーミングの例",
          "code": {
            "title": "SSE Fusion Stream",
            "lang": "bash",
            "content": "curl http://localhost:8000/v1/chat/completions \\\n  -H \"Content-Type: application/json\" \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\n    \"model\": \"fusion/code-jury\",\n    \"messages\": [{\"role\": \"user\", \"content\": \"Analyze time complexity of quicksort\"}],\n    \"stream\": true\n  }'\n\n# Streamed SSE chunks contain real-time deliberation in reasoning_content:\n# data: {\"choices\":[{\"delta\":{\"reasoning_content\":\"### 🧬 Fusion Ensemble Deliberation\\n...\"}}]}\n# ...\n# data: {\"choices\":[{\"delta\":{\"content\":\"Final evaluated answer...\"}}]}"
          }
        },
        {
          "title": "Judge 戦略の比較",
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
      "title": "対応プロバイダーとKeylessモード",
      "group": "management",
      "description": "12以上のクラウドLLMプロバイダーとローカルランタイムにネイティブ対応。自前Ollamaインスタンス向けのKeylessモードも完備。",
      "subsections": [
        {
          "title": "プロバイダー機能マトリクス",
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
          "title": "ローカルOllamaのKeylessモード設定",
          "code": {
            "title": "Add Ollama via API or UI",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/credentials \\\n  -H \"Content-Type: application/json\" \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\" \\\n  -d '{\n    \"provider\": \"ollama\",\n    \"name\": \"Local Workstation Ollama\",\n    \"api_key\": \"keyless\",\n    \"base_url\": \"http://127.0.0.1:11434\",\n    \"is_active\": true\n  }'"
          }
        }
      ],
      "badge": "Multi-Provider",
      "highlights": [
        "OpenAI、Anthropic、Gemini、Groq、DeepSeek、Cerebras、Mistral、xAI、OpenRouterに完全対応",
        "Keylessモード：ローカルOllama（http://localhost:11434）をダミーキー不要で直接連携",
        "vLLM、LM Studio、OpenAI互換の企業内エンドポイント向けのカスタムBase URL設定",
        "プロバイダー認証情報ごとに専用のHTTP/SOCKS5プロキシを設定可能"
      ]
    },
    {
      "id": "credentials",
      "title": "上流プロバイダー認証情報と暗号化保管庫",
      "group": "management",
      "description": "アップストリームAPIキーを銀行水準で暗号化保存。健全性チェック、障害自動切り離し、グループフォルダ管理に対応。",
      "subsections": [
        {
          "title": "認証情報のヘルスチェック実行",
          "code": {
            "title": "Health Check Endpoint",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/credentials/cred_abc123/health-check \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\"\n\n# Response:\n# {\n#   \"status\": \"healthy\",\n#   \"latency_ms\": 142.5,\n#   \"checked_at\": \"2026-09-13T14:15:00Z\"\n# }"
          }
        }
      ],
      "badge": "Encrypted Vault",
      "highlights": [
        "AES-128-CBC Fernet 暗号化：SQLite 保存前に全キーを暗号化、メモリ内でのみ復号",
        "キーのマスキング表示：UIやログには生キーを出力せず末尾のみ表示（例: sk-ant...7a9f）",
        "プロアクティブな死活監視：プロバイダーのエンドポイントへ定期的にヘルスチェック",
        "認証情報グループ：本番環境、ステージング、バックアッププールなどのフォルダ分類"
      ]
    },
    {
      "id": "api-keys",
      "title": "クライアントAPIキーとアクセス権限",
      "group": "management",
      "description": "クライアント用アクセストークン（sk-router-...）の発行・監視・失効管理。キーごとのRPM/TPM制限やモデル許可リストを設定可能。",
      "subsections": [
        {
          "title": "クライアントキー パラメータ仕様",
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
        "SHA-256 一方向ハッシュ：秘密キーは平文保存されず、データベース流出時も復元不可能",
        "レート制限：分あたりリクエスト数（RPM）と分あたりトークン数（TPM）を個別制御",
        "モデル許可リスト：指定したモデルやルートプロファイルのみ呼び出し可能に制限",
        "有効期限（TTL）：一時的な開発チームやデモ用に自動失効日時を設定可能"
      ]
    },
    {
      "id": "proxies",
      "title": "プロキシ管理と地域タグルーティング",
      "group": "management",
      "description": "認証付きHTTP/SOCKS5プロキシを経由して上流通信をルーティング。遅延測定機能や国別タグによる地域制限回避に対応。",
      "subsections": [
        {
          "title": "プロキシ接続文字列の形式例",
          "code": {
            "title": "Supported Proxy URI Formats",
            "lang": "bash",
            "content": "# Standard HTTP proxy:\nhttp://proxy.corporate.internal:8080\n\n# Authenticated HTTP proxy:\nhttp://username:<PROXY_PASSWORD>@us-east.proxy-vendor.com:3128\n\n# Authenticated SOCKS5 proxy:\nsocks5://proxyuser:<PROXY_PASSWORD>@sg-node.vpn-provider.net:1080"
          }
        }
      ],
      "badge": "Egress & Geo",
      "highlights": [
        "全プロトコル対応：HTTP、HTTPS、SOCKS5（socks5://user:pass@host:port）を完全サポート",
        "国・地域タグ設定：ISO国コード（US, DE, SG, JP）を指定して各社の地域制限をスマートに回避",
        "リアルタイム遅延計測：プロキシ保存時およびヘルスチェック時にRTT往復遅延を測定",
        "認証情報ごとの独立割当：特定のAPIキーやプロバイダー専用のプロキシ経路をバインド可能"
      ]
    },
    {
      "id": "backup-restore",
      "title": "暗号化バックアップとディザスタリカバリ",
      "group": "system",
      "description": "パスフレーズから導出したAES-GCM暗号化により、ルーター全設定（モデル、ルート、資格情報、プロキシ、クライアントキー）を安全にバックアップ・復元。",
      "subsections": [
        {
          "title": "API経由でのバックアップ暗号化エクスポート",
          "code": {
            "title": "Encrypted Backup Endpoint",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/system/backup \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{\"passphrase\": \"<BACKUP_PASSPHRASE>\"}' \\\n  -o router_backup_2026-09-13.enc"
          }
        }
      ],
      "badge": "Disaster Recovery",
      "highlights": [
        "PBKDF2 HMAC-SHA256 鍵導出関数とランダムソルト、AES-256-GCM による強力な暗号化",
        "完全システムスナップショット：モデル、プロバイダー鍵、ルート、審査設定、プロキシ、クライアント鍵",
        "柔軟なリストア：既存データとのマージ統合、または完全クリーンインストールを選択可能",
        "完全セルフホスト：VPS間、Dockerコンテナ間、クラウドリージョン間の移行が瞬時に完了"
      ]
    },
    {
      "id": "analytics",
      "title": "分析、リアルタイムログ、トレース検査",
      "group": "system",
      "description": "トークン消費集計、リアルタイム利用料金試算、レイテンシ推移、フォールバックの全試行履歴を可視化するウォーターフォールトレースを完備。",
      "subsections": [
        {
          "title": "リクエストログのデータ構造",
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
        "3方向トークン計測：プロンプト、完了、および思考プロセス（Reasoning）の各トークンを完全独立集計",
        "ウォーターフォールトレース：フォールバック発生時の試行履歴、エラー原因、所要時間を可視化",
        "リアルタイム料金試算：プロバイダー公式価格に基づきリクエスト単位でUSDコストを自動計算",
        "監査ログエクスポート：ステータスコード、クライアントキー、モデル名、期間で絞り込み・CSV出力"
      ]
    },
    {
      "id": "circuit-breaker",
      "title": "サーキットブレーカーと障害自動隔離",
      "group": "system",
      "description": "ダウンまたは過負荷の上流プロバイダーへの通信を自動遮断する有限ステートマシン。連鎖タイムアウトを防ぎ、自動プローブで復旧。",
      "subsections": [
        {
          "title": "状態遷移ライフサイクル",
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
        "3つの運用状態：CLOSED（正常）、OPEN（遮断・代替経路へ迂回）、HALF-OPEN（テストプローブ送信中）",
        "トリガー条件：5回連続で5xxエラーまたはタイムアウトが発生した場合に自動跳開",
        "クールダウン期間：障害発生から30秒間遮断を維持し、その後少数の通信で復旧を確認",
        "クライアント完全透過：優先度フォールバックの次候補が即時リクエストを代行しエラーを防止"
      ]
    },
    {
      "id": "api-reference",
      "title": "完全なREST APIエンドポイント一覧",
      "group": "system",
      "description": "MyAIrouter が提供するすべての公開推論エンドポイントおよび管理者向け管理RESTエンドポイントの完全な一覧仕様。",
      "subsections": [
        {
          "title": "公開および管理者向けエンドポイント仕様表",
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
        "OpenAI互換：/v1/chat/completions、/v1/models（各社SDKをそのまま差し替え可能）",
        "Ollamaプロトコル：/api/tags、/api/show、/api/version、/api/chat",
        "構成管理：/api/v1/credentials、/api/v1/models、/api/v1/routes、/api/v1/fusion",
        "システム＆死活監視：/health、/api/v1/system/backup、/api/v1/system/restore、/api/v1/system/stats"
      ]
    },
    {
      "id": "errors",
      "title": "HTTPエラーコードとトラブルシューティング",
      "group": "system",
      "description": "ルーターが返却するHTTPステータスコードの詳細一覧、OpenAI互換のJSONエラーレスポンス構造、および実践的なトラブルシューティング手順。",
      "subsections": [
        {
          "title": "HTTPステータスコード一覧",
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
        "標準OpenAIエラー構造：{\"error\": {\"message\": \"...\", \"type\": \"...\", \"code\": \"...\"}} に完全準拠",
        "明確な責任区分：クライアント側のパラメータ不備（4xx）と上流プロバイダー障害（502/504）を明確に分離",
        "実践的な診断メッセージ：認証エラー、クォータ枯渇、タイムアウト、候補ゼロなどの原因を具体的に明示",
        "レート制限バックオフ：429応答時にRPMおよびTPMの超過要因を明快に通知"
      ]
    },
    {
      "id": "env-config",
      "title": "環境変数と本番デプロイ",
      "group": "system",
      "description": "Docker、PostgreSQL、systemd、および高度なセキュリティ設定を用いて MyAIrouter を本番環境で運用するための環境変数リファレンス。",
      "subsections": [
        {
          "title": "主要な環境変数一覧",
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
          "title": "本番環境向け Docker Compose 構成例",
          "code": {
            "title": "docker-compose.prod.yml",
            "lang": "yaml",
            "content": "version: \"3.8\"\n\nservices:\n  myairouter:\n    image: myairouter:latest\n    restart: always\n    ports:\n      - \"8000:8000\"\n    environment:\n      - ROUTER_MASTER_KEY=<GENERATED_ROUTER_MASTER_KEY>\n      - DATABASE_URL=postgresql+asyncpg://router:<POSTGRES_PASSWORD>@postgres:5432/routerdb\n      - ROUTER_PORT=8000\n      - ROUTER_HOST=0.0.0.0\n      - LOG_LEVEL=INFO\n      - DEFAULT_TIMEOUT=45.0\n      - CORS_ORIGINS=https://ai.yourcompany.internal\n    depends_on:\n      - postgres\n\n  postgres:\n    image: postgres:16-alpine\n    restart: always\n    environment:\n      POSTGRES_USER: router\n      POSTGRES_PASSWORD: <POSTGRES_PASSWORD>\n      POSTGRES_DB: routerdb\n    volumes:\n      - pgdata:/var/lib/postgresql/data\n\nvolumes:\n  pgdata:"
          }
        }
      ],
      "badge": "Deployment",
      "highlights": [
        "ROUTER_MASTER_KEY：全上流APIキーを保管時に暗号化するための重要な32バイトBase64マスターキー",
        "DATABASE_URL：デフォルトのSQLiteから高並行処理対応のPostgreSQLへ簡単に切り替え可能",
        "CORS_ORIGINS：Webフロントエンドから安全に通信するためのオリジン許可リスト（カンマ区切り）",
        "OLLAMA_BASE_URL：Ollamaデーモンの検出先URL（デフォルト: http://localhost:11434）"
      ]
    }
  ]
};
