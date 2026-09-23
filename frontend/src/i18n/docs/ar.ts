import { DocContent } from "./types";

export const ar: DocContent = {
  "ui": {
    "searchPlaceholder": "بحث في التوثيق (مثل Ollama, Fallback, Fusion, مفاتيح API)...",
    "noSectionsFound": "لم يتم العثور على أقسام مطابقة.",
    "prevSection": "القسم السابق",
    "nextSection": "القسم التالي",
    "copied": "تم النسخ!",
    "copy": "نسخ الكود",
    "endpoints": "نقاط النهاية",
    "tocTitle": "فهرس التوثيق"
  },
  "sections": [
    {
      "id": "overview",
      "title": "نظرة عامة على النظام",
      "group": "intro",
      "description": "بوابة نماذج لغوية ذاتية الاستضافة مع محركات التوجيه المباشر والاحتياطي والدمج، وتجمع المفاتيح وتوافق Ollama.",
      "subsections": [
        {
          "title": "مقارنة أوضاع التوجيه",
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
        "3 محركات توجيه: المباشر، والاحتياطي ذو الأولوية (المتداخل)، ودمج النماذج",
        "توافق فوري مع واجهات OpenAI (/v1/chat/completions) وOllama (/api/tags)",
        "تشفير عالي الأمان: AES-128-CBC Fernet محمي بمفتاح ROUTER_MASTER_KEY",
        "قاطع الدائرة الكهربائية (Circuit Breaker) لعزل الأعطال مع دعم البروكسي الجغرافي"
      ]
    },
    {
      "id": "quickstart",
      "title": "دليل البدء السريع",
      "group": "intro",
      "description": "اربط أي مكتبة متوافقة مع OpenAI أو cURL أو عميل Ollama ببوابة MyAIrouter في ثوانٍ.",
      "subsections": [
        {
          "title": "1. البدء السريع عبر cURL",
          "code": {
            "title": "cURL Chat Completion",
            "lang": "bash",
            "content": "curl http://localhost:8000/v1/chat/completions \\\n  -H \"Content-Type: application/json\" \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\n    \"model\": \"gemini-2.5-flash\",\n    \"messages\": [{\"role\": \"user\", \"content\": \"Explain quantum computing in one sentence.\"}],\n    \"temperature\": 0.7\n  }'"
          }
        },
        {
          "title": "2. مكتبة Python OpenAI",
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
      "title": "عنونة النماذج والتحليل",
      "group": "models",
      "description": "عنونة مرنة متعددة الأنماط: المعرفات القياسية، وتحديد المزود، ومسارات الاحتياط، ولجان التحكيم المندمجة.",
      "subsections": [
        {
          "title": "تسلسل العنونة",
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
      "title": "توافق واجهة برمجة تطبيقات Ollama",
      "group": "models",
      "description": "دعم أصلي مباشر لـ Ollama CLI وContinue.dev وOpen WebUI وObsidian Copilot دون تعديل كود العميل.",
      "subsections": [
        {
          "title": "التكامل مع أداة سطر أوامر Ollama",
          "code": {
            "title": "Bash / Terminal",
            "lang": "bash",
            "content": "# Point your local Ollama client or IDE extension to MyAIrouter\nexport OLLAMA_HOST=http://localhost:8000\n\n# View all registered models, route profiles, and fusion profiles\nollama list\n\n# Execute queries directly through the OpenAI-compatible gateway\nollama run gemini-2.5-flash \"Write a Fibonacci function in Go\" "
          }
        },
        {
          "title": "نقاط نهاية Ollama المدعومة",
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
      "title": "التقييمات والمعايير القياسية",
      "group": "models",
      "description": "مقاييس Artificial Analysis الآلية: مؤشر الجودة (0-100)، سرعة التوليد (رمز/ثانية)، التسعير، وحدود السياق.",
      "subsections": [
        {
          "title": "معايير القياس",
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
      "title": "حدود واجهة برمجة التطبيقات والحصص",
      "group": "models",
      "description": "تحديد المعدل على مستويين: حماية حسابات المزودين بحدود RPM/TPM لكل مفتاح، مع تنظيم استخدام عملاء البوابة.",
      "subsections": [
        {
          "title": "آلية تطبيق الحدود المزدوجة",
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
      "title": "مستويات التفكير والمنطق (CoT)",
      "group": "routing",
      "description": "معلمة reasoning_effort الموحدة مع ترجمة تلقائية متوافقة عبر OpenAI وAnthropic وGoogle Gemini وGroq.",
      "subsections": [
        {
          "title": "مثال على معلمة التفكير",
          "code": {
            "title": "cURL Reasoning Request",
            "lang": "bash",
            "content": "# Send standard reasoning_effort to any provider\ncurl http://localhost:8000/v1/chat/completions \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\n    \"model\": \"gemini-2.5-flash\",\n    \"messages\": [{\"role\": \"user\", \"content\": \"Prove that the square root of 2 is irrational.\"}],\n    \"reasoning_effort\": \"high\"\n  }'"
          }
        },
        {
          "title": "مصفوفة ترجمة بروتوكولات المزودين",
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
      "title": "محرك التوجيه المباشر (Direct)",
      "group": "routing",
      "description": "توجيه فائق السرعة نحو نموذج محدد مباشرة مع موازنة المفاتيح بنظام Round-robin والتبديل التلقائي عند الخطأ.",
      "subsections": [
        {
          "title": "أمثلة الاستدعاء المباشر",
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
      "title": "سلاسل الأولوية والاحتياط (Fallback)",
      "group": "routing",
      "description": "قوائم تبديل متعددة المستويات عند استنفاد الحصص 429 أو أخطاء الخوادم 5xx، مع دعم المسارات المتداخلة ومجموعات المفاتيح.",
      "subsections": [
        {
          "title": "آلية عمل السلسلة الاحتياطية",
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
      "title": "دمج النماذج (Model Fusion)",
      "group": "routing",
      "description": "تشغيل نماذج لغوية متعددة بالتوازي وتوليف إجابة موحدة عبر نموذج الحكم مع بث خطوات التفكير المباشرة.",
      "subsections": [
        {
          "title": "مثال على بث خطوات التفكير",
          "code": {
            "title": "SSE Fusion Stream",
            "lang": "bash",
            "content": "curl http://localhost:8000/v1/chat/completions \\\n  -H \"Content-Type: application/json\" \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\n    \"model\": \"fusion/code-jury\",\n    \"messages\": [{\"role\": \"user\", \"content\": \"Analyze time complexity of quicksort\"}],\n    \"stream\": true\n  }'\n\n# Streamed SSE chunks contain real-time deliberation in reasoning_content:\n# data: {\"choices\":[{\"delta\":{\"reasoning_content\":\"### 🧬 Fusion Ensemble Deliberation\\n...\"}}]}\n# ...\n# data: {\"choices\":[{\"delta\":{\"content\":\"Final evaluated answer...\"}}]}"
          }
        },
        {
          "title": "استراتيجيات التحكيم",
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
      "title": "المزودون المدعومون والوضع بدون مفتاح",
      "group": "management",
      "description": "تكامل أصلي مع أكثر من 12 مزوداً سحابياً للنماذج اللغوية ومحركات التشغيل المحلية، مع دعم الوضع بدون مفتاح لمثيلات Ollama.",
      "subsections": [
        {
          "title": "مصفوفة إمكانيات المزودين",
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
          "title": "إعداد الوضع بدون مفتاح لـ Ollama المحلي",
          "code": {
            "title": "Add Ollama via API or UI",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/credentials \\\n  -H \"Content-Type: application/json\" \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\" \\\n  -d '{\n    \"provider\": \"ollama\",\n    \"name\": \"Local Workstation Ollama\",\n    \"api_key\": \"keyless\",\n    \"base_url\": \"http://127.0.0.1:11434\",\n    \"is_active\": true\n  }'"
          }
        }
      ],
      "badge": "Multi-Provider",
      "highlights": [
        "دعم شامل لـ OpenAI وAnthropic وGemini وGroq وDeepSeek وCerebras وMistral وxAI وOpenRouter",
        "الوضع بدون مفتاح: ربط Ollama المحلي (http://localhost:11434) دون الحاجة لمفاتيح وهمية",
        "دعم العناوين الأساسية المخصصة (Base URL) لـ vLLM وLM Studio والبوابات المؤسسية المتوافقة",
        "ربط بروكسي HTTP/SOCKS5 مخصص لكل مزود ومفتاح اعتماد"
      ]
    },
    {
      "id": "credentials",
      "title": "بيانات اعتماد المزودين وخزنة المفاتيح المشفرة",
      "group": "management",
      "description": "تخزين مشفر بمعايير بنكية لمفاتيح مزودي الخدمة مع فحوصات دورية للسلامة والتعطيل التلقائي وإدارة المجموعات.",
      "subsections": [
        {
          "title": "تشغيل فحص السلامة يدوياً",
          "code": {
            "title": "Health Check Endpoint",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/credentials/cred_abc123/health-check \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\"\n\n# Response:\n# {\n#   \"status\": \"healthy\",\n#   \"latency_ms\": 142.5,\n#   \"checked_at\": \"2026-09-13T14:15:00Z\"\n# }"
          }
        }
      ],
      "badge": "Encrypted Vault",
      "highlights": [
        "تشفير متماثل AES-128-CBC Fernet: تشفير المفاتيح بالكامل قبل حفظها في قاعدة البيانات",
        "إخفاء الأسرار: عدم عرض المفاتيح الأصلية في الواجهة أو السجلات (مثل sk-ant...7a9f)",
        "فحوصات سلامة استباقية: اختبار آلي لصلاحية المفتاح ورصيد الحساب لدى المزود",
        "مجموعات الاعتماد: تنظيم المفاتيح في مجلدات منطقية (إنتاج، تجارب، احتياط)"
      ]
    },
    {
      "id": "api-keys",
      "title": "مفاتيح API للعملاء وصلاحيات الوصول",
      "group": "management",
      "description": "إصدار ومراقبة وإلغاء رموز وصول العملاء (sk-router-...) مع تحديد حدود الطلبات وحصص النماذج المصرح بها.",
      "subsections": [
        {
          "title": "مرجع معلمات مفتاح العميل",
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
        "تشفير أحادي الاتجاه SHA-256: لا يتم تخزين المفاتيح كنصوص صريحة نهائياً في قاعدة البيانات",
        "تحديد معدل الاستخدام: ضبط دقيق لعدد الطلبات في الدقيقة (RPM) والرموز في الدقيقة (TPM)",
        "القوائم البيضاء للنماذج: قصر صلاحية المفتاح على نماذج معينة دون غيرها لمنع الاستنزاف",
        "انتهاء الصلاحية التلقائي: تحديد تاريخ ووقت انتهاء الصلاحية للمفاتيح المؤقتة"
      ]
    },
    {
      "id": "proxies",
      "title": "إدارة البروكسي والتوجيه الجغرافي",
      "group": "management",
      "description": "توجيه حركة المرور عبر بروكسيات HTTP وSOCKS5 مصادق عليها مع قياس زمن الاستجابة وتصنيف الدول لتجاوز الحجب الجغرافي.",
      "subsections": [
        {
          "title": "أمثلة على صيغ البروكسي",
          "code": {
            "title": "Supported Proxy URI Formats",
            "lang": "bash",
            "content": "# Standard HTTP proxy:\nhttp://proxy.corporate.internal:8080\n\n# Authenticated HTTP proxy:\nhttp://username:<PROXY_PASSWORD>@us-east.proxy-vendor.com:3128\n\n# Authenticated SOCKS5 proxy:\nsocks5://proxyuser:<PROXY_PASSWORD>@sg-node.vpn-provider.net:1080"
          }
        }
      ],
      "badge": "Egress & Geo",
      "highlights": [
        "دعم كامل للبروتوكولات: HTTP وHTTPS وSOCKS5 (بالمصادقة الكاملة)",
        "أعلام ورموز الدول: تعيين رموز ISO (مثل US وDE وSG وJP) لتخطي القيود الإقليمية للمزودين",
        "قياس زمن الاستجابة: فحص مباشر لزمن انتقال البيانات ذهاباً وإياباً (RTT) عند كل اختبار",
        "عزل لكل اعتماد: تخصيص بروكسي مستقل لكل مفتاح API أو لكل مزود خدمة"
      ]
    },
    {
      "id": "backup-restore",
      "title": "النسخ الاحتياطي المشفر والتعافي من الكوارث",
      "group": "system",
      "description": "تصدير واستعادة كامل إعدادات الراوتر المشفرة بكلمة مرور عبر خوارزمية AES-GCM، شاملة النماذج والمسارات والبروكسيات.",
      "subsections": [
        {
          "title": "تصدير النسخة الاحتياطية عبر واجهة API",
          "code": {
            "title": "Encrypted Backup Endpoint",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/system/backup \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{\"passphrase\": \"<BACKUP_PASSPHRASE>\"}' \\\n  -o router_backup_2026-09-13.enc"
          }
        }
      ],
      "badge": "Disaster Recovery",
      "highlights": [
        "اشتقاق مفاتيح قوي عبر PBKDF2 HMAC-SHA256 مع ملح عشوائي وتشفير موثوق AES-256-GCM",
        "لقطة كاملة للنظام: النماذج، مفاتيح المزودين، ملفات المسارات، لجان الدمج، البروكسيات والمفاتيح",
        "استعادة مرنة أو كاملة: خيار الدمج مع الإعدادات الحالية أو الاستبدال الشامل بنقرة واحدة",
        "استقلالية تامة: نقل سلس بين خوادم VPS وحاويات Docker في ثوانٍ معدودة"
      ]
    },
    {
      "id": "analytics",
      "title": "التحليلات والسجلات ومفتش مسارات التتبع",
      "group": "system",
      "description": "تتبع شامل للبيانات مع رصد دقيق للرموز، وتقدير فوري للتكلفة المالية، ورسوم بيانية لأزمنة الاستجابة ومسارات الفشل والتعافي.",
      "subsections": [
        {
          "title": "مخطط حقول سجل الطلبات",
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
        "محاسبة ثلاثية للرموز: تتبع مستقل لرموز الإدخال (Prompt) والإكمال (Completion) والتفكير (Reasoning)",
        "مفتش المسار الشلالي (Waterfall): تفصيل مرئي خطوة بخطوة لكل محاولة فاشلة وزمن انتظار وإعادة توجيه",
        "حاسبة التكاليف المباشرة: تقدير التكلفة بالدولار الأمريكي وفق تسعيرة المزودين المعتمدة لكل رمز",
        "تصدير سجلات التدقيق: تصفية وتنزيل السجلات حسب رمز الحالة أو مفتاح العميل أو النموذج أو التاريخ"
      ]
    },
    {
      "id": "circuit-breaker",
      "title": "قاطع الدائرة الكهربائية وعزل الأعطال",
      "group": "system",
      "description": "آلية آلية ذات حالات محددة لعزل المزودين المتعطلين أو المرهقين، وحماية تطبيقات العملاء من التوقف التراكمي وتسهيل التعافي.",
      "subsections": [
        {
          "title": "دورة حياة حالات الآلة",
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
        "3 حالات تشغيلية: CLOSED (سليم وطبيعي)، OPEN (معطول ومحول)، HALF-OPEN (اختبار التعافي)",
        "شرط الفصل: ينفصل القاطع تلقائياً بعد 5 أخطاء متتالية من نوع 5xx أو انتهاء زمن الانتظار",
        "فترة التبريد: تحويل الحركة لمدة 30 ثانية قبل إرسال طلب تجريبي واحد للتحقق من العودة",
        "تجربة عميل سلسة: يتولى النموذج التالي في مسار Fallback تنفيذ الطلب دون أي خطأ ظاهر للعميل"
      ]
    },
    {
      "id": "api-reference",
      "title": "المرجع الكامل لواجهات برمجة التطبيقات (API)",
      "group": "system",
      "description": "فهرس شامل لجميع نقاط النهاية العامة للاستدلال وإدارة النظام التي يوفرها خادم MyAIrouter.",
      "subsections": [
        {
          "title": "جدول نقاط النهاية العامة والإدارية",
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
        "واجهة OpenAI المتوافقة: /v1/chat/completions و/v1/models (إحلال مباشر لجميع التطبيقات)",
        "بروتوكول Ollama: /api/tags و/api/show و/api/version و/api/chat",
        "الإدارة المركزية: /api/v1/credentials و/api/v1/models و/api/v1/routes و/api/v1/fusion",
        "النظام والسلامة: /health و/api/v1/system/backup و/api/v1/system/restore و/api/v1/system/stats"
      ]
    },
    {
      "id": "errors",
      "title": "رموز أخطاء HTTP واستكشاف الأعطال وإصلاحها",
      "group": "system",
      "description": "تحليل شامل لرموز استجابة HTTP التي يرجعها النظام، ومواصفات كائن الخطأ بصيغة JSON، وخطوات عملية لحل المشكلات.",
      "subsections": [
        {
          "title": "دليل رموز استجابة HTTP",
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
        "مخطط خطأ قياسي متوافق مع OpenAI: {\"error\": {\"message\": \"...\", \"type\": \"...\", \"code\": \"...\"}}",
        "تمييز دقيق للمسؤولية: تفريق واضح بين أخطاء العميل (4xx) وأعطال مزودي الخدمة الخارجيين (502/504)",
        "تشخيصات واضحة وقابلة للتنفيذ: توضيح دقيق لسبب العطل سواء كان نفاد الرصيد أو خطأ بالمفتاح أو عدم توفر النموذج",
        "إرشادات تجاوز معدل الاستخدام: استجابات 429 توفر إرشادات واضحة حول فترات الانتظار لتجاوز حدود RPM وTPM"
      ]
    },
    {
      "id": "env-config",
      "title": "متغيرات البيئة والنشر الإنتاجي",
      "group": "system",
      "description": "خيارات التهيئة لاستضافة MyAIrouter في بيئة الإنتاج باستخدام Docker وPostgreSQL وإعدادات الأمان المتقدمة.",
      "subsections": [
        {
          "title": "متغيرات البيئة الأساسية",
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
          "title": "مثال Docker Compose للإنتاج",
          "code": {
            "title": "docker-compose.prod.yml",
            "lang": "yaml",
            "content": "version: \"3.8\"\n\nservices:\n  myairouter:\n    image: myairouter:latest\n    restart: always\n    ports:\n      - \"8000:8000\"\n    environment:\n      - ROUTER_MASTER_KEY=<GENERATED_ROUTER_MASTER_KEY>\n      - DATABASE_URL=postgresql+asyncpg://router:<POSTGRES_PASSWORD>@postgres:5432/routerdb\n      - ROUTER_PORT=8000\n      - ROUTER_HOST=0.0.0.0\n      - LOG_LEVEL=INFO\n      - DEFAULT_TIMEOUT=45.0\n      - CORS_ORIGINS=https://ai.yourcompany.internal\n    depends_on:\n      - postgres\n\n  postgres:\n    image: postgres:16-alpine\n    restart: always\n    environment:\n      POSTGRES_USER: router\n      POSTGRES_PASSWORD: <POSTGRES_PASSWORD>\n      POSTGRES_DB: routerdb\n    volumes:\n      - pgdata:/var/lib/postgresql/data\n\nvolumes:\n  pgdata:"
          }
        }
      ],
      "badge": "Deployment",
      "highlights": [
        "ROUTER_MASTER_KEY: مفتاح رئيسي مشفر بحجم 32 بايت بصيغة base64 لتشفير كافة اعتمادات المزودين في قاعدة البيانات",
        "DATABASE_URL: التبديل من SQLite الافتراضية إلى خادم PostgreSQL المخصص للأحمال العالية",
        "CORS_ORIGINS: قائمة النطاقات المسموح بها للتواصل الآمن مع واجهة الويب الأمامية",
        "OLLAMA_BASE_URL: عنوان اكتشاف خدمة Ollama المحلية أو البعيدة (الافتراضي: http://localhost:11434)"
      ]
    }
  ]
};
