import { DocContent } from "./types";

export const zh: DocContent = {
  "ui": {
    "searchPlaceholder": "搜索文档（例如 Ollama、Fallback、Fusion、API 密钥）...",
    "noSectionsFound": "未找到匹配的文档小节。",
    "prevSection": "上一小节",
    "nextSection": "下一小节",
    "copied": "已复制！",
    "copy": "复制代码",
    "endpoints": "接口列表",
    "tocTitle": "文档目录"
  },
  "sections": [
    {
      "id": "overview",
      "title": "系统架构概述",
      "group": "intro",
      "description": "自托管通用大模型网关，内置直连、优先级回退、模型融合与 Jev 快决策四大引擎，支持多提供商密钥池和 Ollama 协议兼容。",
      "subsections": [
        {
          "title": "路由模式特性对比",
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
              ],
              [
                "Jev System One",
                "direct, /v1/systemone, jev/*",
                "Discrete Decision Primitives",
                "Fast rubric & choice evaluation with calibrated probabilities",
                "Ultra-low / Instant"
              ]
            ]
          }
        }
      ],
      "badge": "Core Architecture",
      "highlights": [
        "四大路由引擎：直连路由、优先级回退（支持嵌套）、模型融合评审团与 Jev 快决策 (System One)",
        "完美兼容 OpenAI API (/v1/chat/completions) 与 Ollama (/api/tags, /api/show)",
        "企业级安全：基于 ROUTER_MASTER_KEY 的 AES-128-CBC Fernet 密钥加密存储",
        "断路器自动隔离故障节点，支持健康检测自愈与独立代理绑定"
      ]
    },
    {
      "id": "quickstart",
      "title": "快速上手指南",
      "group": "intro",
      "description": "秒级将任何 OpenAI SDK、cURL 脚本或本地 Ollama 客户端连接至 MyAIrouter 智能网关。",
      "subsections": [
        {
          "title": "1. cURL 命令行调用",
          "code": {
            "title": "cURL Chat Completion",
            "lang": "bash",
            "content": "curl http://localhost:8000/v1/chat/completions \\\n  -H \"Content-Type: application/json\" \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\n    \"model\": \"gemini-2.5-flash\",\n    \"messages\": [{\"role\": \"user\", \"content\": \"Explain quantum computing in one sentence.\"}],\n    \"temperature\": 0.7\n  }'"
          }
        },
        {
          "title": "2. Python OpenAI 官方库",
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
      "title": "模型寻址与解析机制",
      "group": "models",
      "description": "多层次模型寻址方案：标准规范名、指定提供商前缀、回退路由别名与融合评审团标识。",
      "subsections": [
        {
          "title": "寻址层级规范",
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
        },
        {
          "title": "模型执行类型：OpenAI 兼容模式 vs ⚡ Jev 快决策",
          "description": "MyAIrouter 支持为模型目录中的每一款模型独立配置执行模式：默认的 OpenAI 兼容模式或高并发 Jev System One 快速决策引擎。",
          "bullets": [
            "默认模型类型 ('openai')：支持标准的多轮对话、思维链推理与流式响应（涵盖 OpenAI、Gemini、Anthropic、Ollama 等）。",
            "Jev 决策模式 ('jev')：专用于 System One 快速离散评估（choice 选项、score 评分、noul 判定）并输出校准概率分布。",
            "原生执行与智能模拟：原生 Jev 服务商（drex.nace、experientiallabs）享受零延迟直传；通用大模型（GPT、Claude、Gemini、Groq）自动通过结构化 JSON 提示词无缝模拟。",
            "目录快捷管理：支持筛选标签（'All Types'、'OpenAI'、'⚡ Jev'）、单模型弹窗编辑与批量批量切换（'Set Model Type'）。",
            "API 字段支持：GET /v1/models 与 GET /v1/models/{id} 接口均完整返回 model_type 属性。"
          ]
        }
      ],
      "badge": "Addressing"
    },
    {
      "id": "ollama",
      "title": "Ollama 协议兼容接口",
      "group": "models",
      "description": "原生兼容 Ollama CLI 命令行工具、Continue.dev、Open WebUI 和 Obsidian Copilot，无需修改现有客户端代码。",
      "subsections": [
        {
          "title": "使用 Ollama CLI 访问网关",
          "code": {
            "title": "Bash / Terminal",
            "lang": "bash",
            "content": "# Point your local Ollama client or IDE extension to MyAIrouter\nexport OLLAMA_HOST=http://localhost:8000\n\n# View all registered models, route profiles, and fusion profiles\nollama list\n\n# Execute queries directly through the OpenAI-compatible gateway\nollama run gemini-2.5-flash \"Write a Fibonacci function in Go\" "
          }
        },
        {
          "title": "支持的 Ollama 接口列表",
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
      "title": "模型评测与基准数据",
      "group": "models",
      "description": "自动集成 Artificial Analysis 基准数据：综合质量评分 (0-100)、生成速度 (token/s)、百万 Token 价格与上下文窗口。",
      "subsections": [
        {
          "title": "评测指标解析",
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
      "title": "API 速率限制与配额",
      "group": "models",
      "description": "双层速率控制机制：为每个上游凭据设置独立 RPM/TPM 保护账号，同时对下游客户端密钥进行配额与并发监管。",
      "subsections": [
        {
          "title": "双层限流控制逻辑",
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
      "title": "思维链推理强度 (CoT)",
      "group": "routing",
      "description": "通用的 reasoning_effort 推理参数，自动在 OpenAI、Anthropic Claude、Google Gemini 和 Groq 间进行双向协议翻译。",
      "subsections": [
        {
          "title": "推理参数请求示例",
          "code": {
            "title": "cURL Reasoning Request",
            "lang": "bash",
            "content": "# Send standard reasoning_effort to any provider\ncurl http://localhost:8000/v1/chat/completions \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\n    \"model\": \"gemini-2.5-flash\",\n    \"messages\": [{\"role\": \"user\", \"content\": \"Prove that the square root of 2 is irrational.\"}],\n    \"reasoning_effort\": \"high\"\n  }'"
          }
        },
        {
          "title": "各厂商参数映射矩阵",
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
      "title": "直连路由引擎 (Direct)",
      "group": "routing",
      "description": "高性能直连调用指定模型，支持多密钥轮询负载均衡以及上游遭遇 429 时的同提供商内自动重试切换。",
      "subsections": [
        {
          "title": "直连模式调用示例",
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
      "title": "优先级与回退链路 (Fallback)",
      "group": "routing",
      "description": "当遇到上游 429 限流或 5xx 故障时自动切换的多级回退队列，支持嵌套路由配置、密钥分组与参数覆盖。",
      "subsections": [
        {
          "title": "回退链路工作机制",
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
      "title": "模型融合机制 (Model Fusion)",
      "group": "routing",
      "description": "多模型并发并行执行，由指定的评审模型 (Judge) 对候选草稿进行评优、共识提炼或批判重写，并实时流式传输评审思考链。",
      "subsections": [
        {
          "title": "流式评审过程示例",
          "code": {
            "title": "SSE Fusion Stream",
            "lang": "bash",
            "content": "curl http://localhost:8000/v1/chat/completions \\\n  -H \"Content-Type: application/json\" \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\n    \"model\": \"fusion/code-jury\",\n    \"messages\": [{\"role\": \"user\", \"content\": \"Analyze time complexity of quicksort\"}],\n    \"stream\": true\n  }'\n\n# Streamed SSE chunks contain real-time deliberation in reasoning_content:\n# data: {\"choices\":[{\"delta\":{\"reasoning_content\":\"### 🧬 Fusion Ensemble Deliberation\\n...\"}}]}\n# ...\n# data: {\"choices\":[{\"delta\":{\"content\":\"Final evaluated answer...\"}}]}"
          }
        },
        {
          "title": "评审团工作策略",
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
      "id": "jev-systemone",
      "title": "Jev 快决策 (System One) 引擎",
      "group": "routing",
      "description": "超高速 System One 快速决策引擎，面向自主智能体、意图分类、安全护栏与结构化规则评分，输出精确校准的概率分布。",
      "subsections": [
        {
          "title": "决策原语与评估规则",
          "table": {
            "headers": [
              "Primitive / Примитив",
              "Type / Тип",
              "Output Structure",
              "Description & Usage / Назначение"
            ],
            "rows": [
              [
                "choice",
                "Categorical / Категориальный",
                "probabilities: {option: float}, choice: string",
                "Calculates calibrated probability distribution across discrete options (e.g. intent routing, priority triage, sentiment)."
              ],
              [
                "score",
                "Quantitative / Числовой",
                "score: float, confidence: float",
                "Computes a numerical score within a defined rubric range (e.g. risk score 0.0-1.0, quality rating 1-5)."
              ],
              [
                "noul",
                "Binary / Булево",
                "value: bool, confidence: float",
                "Evaluates a strict boolean assertion or safety guardrail condition with associated confidence."
              ]
            ]
          }
        },
        {
          "title": "REST 接口规范 (POST /v1/systemone)",
          "code": {
            "title": "System One Decision Request",
            "lang": "bash",
            "content": "curl http://localhost:8000/v1/systemone \\\n  -H \"Content-Type: application/json\" \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\n    \"model\": \"experientiallabs/jev-latest\",\n    \"state\": \"User transaction: $4,990 from IP 198.51.100.4 (New Device, Location: Kyiv, Previous: New York 10m ago).\",\n    \"questions\": [\n      {\n        \"id\": \"fraud_risk\",\n        \"text\": \"What is the fraud probability category?\",\n        \"type\": \"choice\",\n        \"options\": [\"low\", \"suspicious\", \"critical_fraud\"]\n      },\n      {\n        \"id\": \"require_2fa\",\n        \"text\": \"Should step-up 2FA verification be enforced immediately?\",\n        \"type\": \"noul\"\n      }\n    ]\n  }'\n\n# Response format:\n# {\n#   \"id\": \"jev-9b2f4c1e\",\n#   \"model\": \"experientiallabs/jev-latest\",\n#   \"decisions\": {\n#     \"fraud_risk\": {\n#       \"choice\": \"critical_fraud\",\n#       \"probabilities\": {\"low\": 0.02, \"suspicious\": 0.11, \"critical_fraud\": 0.87},\n#       \"confidence\": 0.87\n#     },\n#     \"require_2fa\": {\n#       \"value\": true,\n#       \"confidence\": 0.96\n#     }\n#   }\n# }"
          }
        },
        {
          "title": "原生执行与智能模拟回退机制",
          "bullets": [
            "原生零延迟直通：针对原生支持 System One 决策架构的服务商（如 drex.nace、experientiallabs、typesafe.ai），网关直接透传专属协议，确保极致响应速度。",
            "通用大模型结构化模拟：当将普通模型（如 gemini-2.5-flash、gpt-4o-mini、claude-3-5-haiku 或本地 ollama）标记为 model_type='jev' 时，网关自动注入严密的结构化 JSON Prompt，校准概率分布并封装为标准决策对象。",
            "兼容 OpenAI Chat 端点：标准 POST /v1/chat/completions 接口可无缝接收 Jev 负载并自动按决策格式返回，现有 SDK 无需任何修改即可平滑接入。",
            "双路由别名支持：POST /v1/systemone 与 POST /v1/decisions 完全等价，均可作为决策接口的主入口。"
          ]
        },
        {
          "title": "Playground 可视化决策工作室与场景预设",
          "bullets": [
            "专属工作室模式：在 Web 控制台的 /playground 页面直接切换至 '⚡ Jev (System One)' 模式进行离散决策交互调试。",
            "State 上下文编辑器：输入待评估的完整上下文信息（如客户会话、审计日志、代码审查 Diff、支付交易详情或合规准则）。",
            "可视化原语构建器：轻松增删评估项，一键切换 choice、score、noul 原语类型并配置离散标签，支持无缝切换至底层 Raw JSON 编辑。",
            "内置4大场景预设：提供客服工单流转、内容安全审核、PR 代码合规审查、金融交易欺诈拦截等开箱即用的工业级预设。",
            "实时概率图表与多语言代码导出：提供校准概率条形图、置信度指标盘与 cURL、Python、Node.js 快速接入代码生成。"
          ]
        }
      ],
      "badge": "⚡ System One Decisions",
      "highlights": [
        "System One 极速决策引擎：面向分类、安全与合规审计的高并发评估，输出高精度校准概率",
        "三大决策原语：Choice（多选类别概率分布）、Score（量化规则评分）与 Noul（布尔断言决策）",
        "专用 REST 接口：POST /v1/systemone、POST /v1/decisions，并无缝兼容标准 POST /v1/chat/completions",
        "原生直连零延迟：原生 Jev 平台直通透传，通用 LLM 自动激活高质量结构化 JSON 提示词模拟回退",
        "Playground 可视化决策工作室：支持 State 上下文编辑、可视化问题构建器、4大场景预设及多语言代码导出"
      ]
    },
    {
      "id": "providers",
      "title": "支持的提供商与免密本地模式",
      "group": "management",
      "description": "原生支持 12+ 主流云端大模型服务商与本地推理引擎，特设免密模式无缝接入自建 Ollama 实例。",
      "subsections": [
        {
          "title": "服务商特性与协议矩阵",
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
          "title": "配置本地 Ollama 免密直连",
          "code": {
            "title": "Add Ollama via API or UI",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/credentials \\\n  -H \"Content-Type: application/json\" \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\" \\\n  -d '{\n    \"provider\": \"ollama\",\n    \"name\": \"Local Workstation Ollama\",\n    \"api_key\": \"keyless\",\n    \"base_url\": \"http://127.0.0.1:11434\",\n    \"is_active\": true\n  }'"
          }
        }
      ],
      "badge": "Multi-Provider",
      "highlights": [
        "全面支持 OpenAI, Anthropic, Gemini, Groq, DeepSeek, Cerebras, Mistral, xAI, OpenRouter 等主流平台",
        "免密模式 (Keyless)：连接本地 Ollama (http://localhost:11434) 无需填写伪造 API Key",
        "自定义 Base URL：支持自建 vLLM, LM Studio, LocalAI 以及各类企业内网兼容网关",
        "代理通道绑定：可为每个提供商凭证独立配置专用的 HTTP/SOCKS5 代理"
      ]
    },
    {
      "id": "credentials",
      "title": "上游服务凭证与加密保险库",
      "group": "management",
      "description": "银行级加密存储各类大模型上游 API Key，具备自动健康巡检、故障自动下线以及分组管理功能。",
      "subsections": [
        {
          "title": "手动触发凭证健康检查",
          "code": {
            "title": "Health Check Endpoint",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/credentials/cred_abc123/health-check \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\"\n\n# Response:\n# {\n#   \"status\": \"healthy\",\n#   \"latency_ms\": 142.5,\n#   \"checked_at\": \"2026-09-13T14:15:00Z\"\n# }"
          }
        }
      ],
      "badge": "Encrypted Vault",
      "highlights": [
        "AES-128-CBC Fernet 对称加密：入库前自动全密文存储，内存按需解密",
        "安全密钥脱敏：前端及日志永久脱敏展示（例如 sk-ant...7a9f），严防泄露",
        "主动健康巡检：一键与定时探活验证 API Key 有效性与可用配额",
        "凭证逻辑分组：支持自定义文件夹分组（生产组、预发组、备用池、各业务线）"
      ]
    },
    {
      "id": "api-keys",
      "title": "客户端 API 密钥与访问授权",
      "group": "management",
      "description": "签发、监管并吊销客户端访问令牌 (sk-router-...)，精细配置单密钥速率配额 (RPM/TPM) 及允许调用的模型白名单。",
      "subsections": [
        {
          "title": "客户端密钥参数规范",
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
        "SHA-256 单向哈希：数据库仅持久化密钥散列值，明文仅在创建瞬间展示一次",
        "严格速率配额：精细限制每分钟请求数 (RPM) 与每分钟 Token 吞吐量 (TPM)",
        "模型访问白名单：限定该密钥仅能调用指定模型或路由画像，防止未授权消耗",
        "有效期自动过期：支持为外包团队、临时测试或演示环境设置自动过期时间戳"
      ]
    },
    {
      "id": "proxies",
      "title": "代理池管理与地域标签路由",
      "group": "management",
      "description": "通过支持身份认证的 HTTP/SOCKS5 代理调度上游流量，内置实时延迟探测与国家区域标签，轻松突破地域限制。",
      "subsections": [
        {
          "title": "代理连接字符串格式示例",
          "code": {
            "title": "Supported Proxy URI Formats",
            "lang": "bash",
            "content": "# Standard HTTP proxy:\nhttp://proxy.corporate.internal:8080\n\n# Authenticated HTTP proxy:\nhttp://username:<PROXY_PASSWORD>@us-east.proxy-vendor.com:3128\n\n# Authenticated SOCKS5 proxy:\nsocks5://proxyuser:<PROXY_PASSWORD>@sg-node.vpn-provider.net:1080"
          }
        }
      ],
      "badge": "Egress & Geo",
      "highlights": [
        "全协议支持：完美兼容 HTTP, HTTPS 以及 SOCKS5 (socks5://user:pass@host:port)",
        "国家与地理标签：支持分配 ISO 国家代码（如 US, DE, SG, JP 等），满足合规与跨境访问",
        "实时延迟基准测试：添加与巡检时自动测试握手 RTT 往返耗时，直观标注优劣",
        "按凭证独立绑定：可为特定的 API Key 单独绑定代理，实现多账号多出口 IP 隔离"
      ]
    },
    {
      "id": "backup-restore",
      "title": "加密备份与全量灾难恢复",
      "group": "system",
      "description": "通过密码学 PBKDF2 与 AES-GCM 算法全量导出并恢复网关配置，涵盖模型映射、路由规则、加密密钥池、代理池及客户端凭证。",
      "subsections": [
        {
          "title": "通过 API 导出加密备份包",
          "code": {
            "title": "Encrypted Backup Endpoint",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/system/backup \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{\"passphrase\": \"<BACKUP_PASSPHRASE>\"}' \\\n  -o router_backup_2026-09-13.enc"
          }
        }
      ],
      "badge": "Disaster Recovery",
      "highlights": [
        "高强度密钥派生：基于 PBKDF2 HMAC-SHA256 算法生成高防碰撞密码衍生密钥并结合 AES-256-GCM",
        "全量系统快照：一键打包模型映射、上游密钥库、路由链路、融合评审团、代理列表及客户端授权",
        "增量合并或全量覆盖：支持与目标环境现有数据并集导入，或选择彻底重置后覆盖恢复",
        "无云端依赖：纯自托管离线迁移，秒级实现跨机房、跨 VPS 或 Docker 容器的高可用平滑迁移"
      ]
    },
    {
      "id": "analytics",
      "title": "实时指标、日志与链路追踪",
      "group": "system",
      "description": "端到端流量监控与遥测体系：实时 Token 精准核算、费用预估、各层延迟时序图，以及直观的瀑布流重试追踪。",
      "subsections": [
        {
          "title": "请求日志字段规范",
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
        "三维 Token 精准记账：提示词 (Prompt)、补全词 (Completion) 与思考链 (Reasoning) 分离核算",
        "瀑布流链路追踪 (Waterfall)：毫秒级呈现每一次重试跳点、错误状态码及备选路由切换路径",
        "实时成本估算：基于模型最新官方定价矩阵，秒级折算美元财务消耗与账单分布",
        "合规审计日志导出：支持按 HTTP 状态码、客户端 Key、模型名称及起止时间筛选并下载"
      ]
    },
    {
      "id": "circuit-breaker",
      "title": "断路器自愈与故障隔离机制",
      "group": "system",
      "description": "基于有限状态机 (FSM) 的自动容灾熔断引擎，主动切断向异常或宕机上游的无效请求，杜绝级联超时并平滑自愈。",
      "subsections": [
        {
          "title": "状态机跃迁逻辑",
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
        "三态状态机：CLOSED（健康，全量放行）、OPEN（熔断，流量旁路切走）、HALF-OPEN（半开，发送探针探测自愈）",
        "熔断触发条件：连续检测到 5 次 5xx 服务端错误或网络超时即自动跳闸",
        "冷却等待周期：熔断后静默 30 秒，随后仅允许单笔微量流量进行健康探活",
        "对客户端完全透明：Fallback 链路中的备用模型立即接管，客户端无感知、零报错"
      ]
    },
    {
      "id": "api-reference",
      "title": "完整 REST API 接口清单",
      "group": "system",
      "description": "汇总 MyAIrouter 提供的全部标准推理端点与管理员 REST 控制面接口规范。",
      "subsections": [
        {
          "title": "端点路由与鉴权要求清单",
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
                "POST",
                "/v1/systemone",
                "Bearer sk-router-...",
                "Jev System One decision engine: evaluate state against discrete criteria (choice, score, noul)"
              ],
              [
                "POST",
                "/v1/decisions",
                "Bearer sk-router-...",
                "Alias for /v1/systemone decision evaluation endpoint"
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
        "OpenAI 标准推理接口：/v1/chat/completions, /v1/models（主流客户端无缝无感替换）",
        "Jev System One 决策端点：/v1/systemone, /v1/decisions（离散评估与校准概率）",
        "Ollama 原生协议接口：/api/tags, /api/show, /api/version, /api/chat（兼容各类本地工具）",
        "核心配置控制面：/api/v1/credentials, /api/v1/models, /api/v1/routes, /api/v1/fusion",
        "系统运维与探针：/health, /api/v1/system/backup, /api/v1/system/restore, /api/v1/system/stats"
      ]
    },
    {
      "id": "errors",
      "title": "HTTP 状态码规范与排障指南",
      "group": "system",
      "description": "全面解析网关返回的标准 HTTP 状态码规范、OpenAI 兼容的错误响应体 JSON 结构及常见故障排查诊断指南。",
      "subsections": [
        {
          "title": "常见 HTTP 状态码速查表",
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
        "标准 OpenAI 错误协议：输出格式严格遵循 {\"error\": {\"message\": \"...\", \"type\": \"...\", \"code\": \"...\"}}",
        "责任边界清晰：严格区分客户端调用错误（4xx）与上游大模型服务商异常（502/504）",
        "精准诊断指引：明确标明报错是由于凭据无效、额度耗尽、超时还是路由无可用候选节点",
        "速率超限友好回退：返回 HTTP 429 时附带精准的原因说明（RPM 或 TPM 阈值超出）"
      ]
    },
    {
      "id": "env-config",
      "title": "环境变量配置与生产部署",
      "group": "system",
      "description": "MyAIrouter 生产级部署核心环境变量参考，支持 Docker Compose、PostgreSQL 数据库及生产安全加固。",
      "subsections": [
        {
          "title": "核心环境变量参考表",
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
          "title": "生产级 Docker Compose 编排范式",
          "code": {
            "title": "docker-compose.prod.yml",
            "lang": "yaml",
            "content": "version: \"3.8\"\n\nservices:\n  myairouter:\n    image: myairouter:latest\n    restart: always\n    ports:\n      - \"8000:8000\"\n    environment:\n      - ROUTER_MASTER_KEY=<GENERATED_ROUTER_MASTER_KEY>\n      - DATABASE_URL=postgresql+asyncpg://router:<POSTGRES_PASSWORD>@postgres:5432/routerdb\n      - ROUTER_PORT=8000\n      - ROUTER_HOST=0.0.0.0\n      - LOG_LEVEL=INFO\n      - DEFAULT_TIMEOUT=45.0\n      - CORS_ORIGINS=https://ai.yourcompany.internal\n    depends_on:\n      - postgres\n\n  postgres:\n    image: postgres:16-alpine\n    restart: always\n    environment:\n      POSTGRES_USER: router\n      POSTGRES_PASSWORD: <POSTGRES_PASSWORD>\n      POSTGRES_DB: routerdb\n    volumes:\n      - pgdata:/var/lib/postgresql/data\n\nvolumes:\n  pgdata:"
          }
        }
      ],
      "badge": "Deployment",
      "highlights": [
        "ROUTER_MASTER_KEY：用于底层加密所有上游 API 凭证的 32 字节 Base64 主密钥，生产环境严禁泄露",
        "DATABASE_URL：数据库连接串，支持从默认 SQLite 瞬间无缝切换至高并发生产级 PostgreSQL",
        "CORS_ORIGINS：跨域允许来源白名单，以逗号分隔，保障生产 Web UI 的安全隔离调用",
        "OLLAMA_BASE_URL：本地或局域网 Ollama 守护进程探测基地址（默认 http://localhost:11434）"
      ]
    }
  ]
};
