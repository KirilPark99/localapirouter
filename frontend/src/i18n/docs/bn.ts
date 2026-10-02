import { DocContent } from "./types";

export const bn: DocContent = {
  "ui": {
    "searchPlaceholder": "ডকুমেন্টেশন অনুসন্ধান করুন (যেমন Ollama, Fallback, Fusion)...",
    "noSectionsFound": "কোনো বিভাগ পাওয়া যায়নি।",
    "prevSection": "পূর্ববর্তী বিভাগ",
    "nextSection": "পরবর্তী বিভাগ",
    "copied": "কপি করা হয়েছে!",
    "copy": "কোড কপি করুন",
    "endpoints": "এন্ডপয়েন্ট",
    "tocTitle": "সূচিপত্র"
  },
  "sections": [
    {
      "id": "overview",
      "title": "সিস্টেম ওভারভিউ",
      "group": "intro",
      "description": "ইউনিভার্সাল সেলফ-হোস্টেড এলএলএম গেটওয়ে: ডাইরেক্ট, প্রায়োরিটি ফলব্যাক, মডেল ফিউশন এবং জেভ (Jev) সিস্টেম ওয়ান ডিসিশন ইঞ্জিন, মাল্টি-প্রোভাইডার কি পুলিং এবং ওলামা সামঞ্জস্য।",
      "subsections": [
        {
          "title": "রাউটিং মোডের তুলনা",
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
        "৪টি রাউটিং ইঞ্জিন: ডাইরেক্ট, প্রায়োরিটি ফলব্যাক (নেস্টেড), মডেল ফিউশন এবং জেভ (Jev) সিস্টেম ওয়ান ডিসিশন",
        "OpenAI API (/v1/chat/completions) এবং Ollama (/api/tags) এর সাথে সম্পূর্ণ সামঞ্জস্য",
        "নিরাপদ কী স্টোরেজ: ROUTER_MASTER_KEY চালিত AES-128-CBC ফার্নেট এনক্রিপশন",
        "সার্কিট ব্রেকার স্বয়ংক্রিয় ত্রুটি বিচ্ছিন্নকরণ এবং প্রক্সি ইন্টিগ্রেশন"
      ]
    },
    {
      "id": "quickstart",
      "title": "কুইকস্টার্ট গাইড",
      "group": "intro",
      "description": "কয়েক সেকেন্ডের মধ্যে যেকোনো ওপেনএআই লাইব্রেরি, cURL, বা ওলামা ক্লায়েন্টকে MyAIrouter এর সাথে যুক্ত করুন।",
      "subsections": [
        {
          "title": "1. cURL কুইকস্টার্ট",
          "code": {
            "title": "cURL Chat Completion",
            "lang": "bash",
            "content": "curl http://localhost:8000/v1/chat/completions \\\n  -H \"Content-Type: application/json\" \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\n    \"model\": \"gemini-2.5-flash\",\n    \"messages\": [{\"role\": \"user\", \"content\": \"Explain quantum computing in one sentence.\"}],\n    \"temperature\": 0.7\n  }'"
          }
        },
        {
          "title": "2. পাইথন ওপেনএআই এসডিকে",
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
      "title": "মডেল অ্যাড্রেসিং ও রেজোলিউশন",
      "group": "models",
      "description": "মাল্টি-মোড মডেল অ্যাড্রেসিং: ক্যানোনিকাল স্ল্যাগ, প্রোভাইডার-কোয়ালিফাইড পাথ, ফলব্যাক রুট এবং ফিউশন জুরি।",
      "subsections": [
        {
          "title": "অ্যাড্রেসিং হায়ারার্কি",
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
          "title": "মডেলের প্রকারভেদ: ওপেনএআই সামঞ্জস্যপূর্ণ বনাম ⚡ জেভ (Jev System One)",
          "description": "MyAIrouter ক্যাটালগের প্রতিটি মডেলের জন্য এক্সিকিউশন মোড কনফিগার করতে দেয়: ডিফল্ট ওপেনএআই সামঞ্জস্যপূর্ণ বা উচ্চ-গতির জেভ (Jev) সিস্টেম ওয়ান ডিসিশন ইঞ্জিন।",
          "bullets": [
            "ডিফল্ট মডেলের ধরন ('openai'): স্ট্যান্ডার্ড টেক্সট জেনারেশন, রিজনিং টোকেন এবং স্ট্রিমিং (OpenAI, Gemini, Anthropic, Ollama ইত্যাদি)।",
            "জেভ মোড ('jev'): ক্যালিব্রেটেড সম্ভাব্যতা সহ ডিসক্রিট মানদণ্ডের (choice, score, noul) উপর ভিত্তি করে দ্রুত সিস্টেম ওয়ান সিদ্ধান্ত মূল্যায়ন।",
            "নেটিভ বনাম এমুলেশন: নেটিভ প্রোভাইডার (drex.nace, experientiallabs) সরাসরি জিরো-লেটেন্সি পেলোড পায়; সাধারণ এলএলএম (GPT, Claude, Gemini, Groq) স্বয়ংক্রিয় কাঠামোগত JSON এমুলেশনের মাধ্যমে চালিত হয়।",
            "ক্যাটালগ পরিচালনা: দ্রুত ফিল্টার চিপস ('All Types', 'OpenAI', '⚡ Jev'), একক মডেল সম্পাদনা এবং ওয়েব ইউআই-তে ব্যাচ আপডেট ('Set Model Type')।",
            "এপিআই সমর্থন: model_type ফিল্ড ('openai' | 'jev') GET /v1/models এবং GET /v1/models/{id}-এ ফেরত দেওয়া হয়।"
          ]
        }
      ],
      "badge": "Addressing"
    },
    {
      "id": "ollama",
      "title": "ওলামা এপিআই সামঞ্জস্য",
      "group": "models",
      "description": "ক্লায়েন্ট কোড পরিবর্তন না করেই ওলামা সিএলআই, Continue.dev, Open WebUI, এবং Obsidian Copilot এর জন্য নেটিভ সমর্থন।",
      "subsections": [
        {
          "title": "ওলামা সিএলআই ইন্টিগ্রেশন",
          "code": {
            "title": "Bash / Terminal",
            "lang": "bash",
            "content": "# Point your local Ollama client or IDE extension to MyAIrouter\nexport OLLAMA_HOST=http://localhost:8000\n\n# View all registered models, route profiles, and fusion profiles\nollama list\n\n# Execute queries directly through the OpenAI-compatible gateway\nollama run gemini-2.5-flash \"Write a Fibonacci function in Go\" "
          }
        },
        {
          "title": "সমর্থিত ওলামা এন্ডপয়েন্ট",
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
      "title": "রেটিং এবং বেঞ্চমার্ক",
      "group": "models",
      "description": "আর্টিফিশিয়াল অ্যানালাইসিস বেঞ্চমার্ক ইন্টিগ্রেশন: গুণমান সূচক (0-100), উৎপাদন গতি (টোকেন/সেকেন্ড), মূল্য এবং কনটেক্সট উইন্ডো।",
      "subsections": [
        {
          "title": "বেঞ্চমার্ক মেট্রিক্স",
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
      "title": "এপিআই সীমা এবং কোটা",
      "group": "models",
      "description": "দ্বি-স্তরীয় রেট লিমিটিং: আপস্ট্রিম অ্যাকাউন্ট রক্ষা করতে আরপিএম/টিপিএম সীমাবদ্ধতা এবং ক্লায়েন্ট কোটা নিয়ন্ত্রণ।",
      "subsections": [
        {
          "title": "দ্বৈত-স্তর লিমিট প্রয়োগ",
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
      "title": "রিজনিং লেভেলস (CoT)",
      "group": "routing",
      "description": "OpenAI, Anthropic, Google Gemini এবং Groq এর জন্য স্বয়ংক্রিয় অনুবাদ সহ ইউনিভার্সাল reasoning_effort প্যারামিটার।",
      "subsections": [
        {
          "title": "রিজনিং প্যারামিটারের উদাহরণ",
          "code": {
            "title": "cURL Reasoning Request",
            "lang": "bash",
            "content": "# Send standard reasoning_effort to any provider\ncurl http://localhost:8000/v1/chat/completions \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\n    \"model\": \"gemini-2.5-flash\",\n    \"messages\": [{\"role\": \"user\", \"content\": \"Prove that the square root of 2 is irrational.\"}],\n    \"reasoning_effort\": \"high\"\n  }'"
          }
        },
        {
          "title": "প্রোভাইডার ট্রান্সলেশন ম্যাট্রিক্স",
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
      "title": "ডাইরেক্ট রাউটিং ইঞ্জিন",
      "group": "routing",
      "description": "নির্দিষ্ট মডেলে সরাসরি উচ্চ-গতির রাউটিং, রাউন্ড-রবিন লোড ব্যালেন্সিং এবং স্বয়ংক্রিয় কী ফেইলওভার।",
      "subsections": [
        {
          "title": "ডাইরেক্ট রাউটিং কোড উদাহরণ",
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
      "title": "প্রায়োরিটি এবং ফলব্যাক চেইন",
      "group": "routing",
      "description": "429 কোটা বা 5xx ত্রুটিতে স্বয়ংক্রিয় মাল্টি-লেভেল ফলব্যাক সারি, নেস্টেড প্রোফাইল এবং কী-গ্রুপ সমর্থন।",
      "subsections": [
        {
          "title": "ফলব্যাক কাজের পদ্ধতি",
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
      "title": "মডেল ফিউশন (AI সমাহার)",
      "group": "routing",
      "description": "একসাথে একাধিক এলএলএম পরিচালনা করুন এবং রিয়েল-টাইম রিজনিং স্ট্রিমিং সহ জাজ মডেল দ্বারা চূড়ান্ত প্রতিক্রিয়া তৈরি করুন।",
      "subsections": [
        {
          "title": "স্ট্রিমিং ডিলিবারেশন উদাহরণ",
          "code": {
            "title": "SSE Fusion Stream",
            "lang": "bash",
            "content": "curl http://localhost:8000/v1/chat/completions \\\n  -H \"Content-Type: application/json\" \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\n    \"model\": \"fusion/code-jury\",\n    \"messages\": [{\"role\": \"user\", \"content\": \"Analyze time complexity of quicksort\"}],\n    \"stream\": true\n  }'\n\n# Streamed SSE chunks contain real-time deliberation in reasoning_content:\n# data: {\"choices\":[{\"delta\":{\"reasoning_content\":\"### 🧬 Fusion Ensemble Deliberation\\n...\"}}]}\n# ...\n# data: {\"choices\":[{\"delta\":{\"content\":\"Final evaluated answer...\"}}]}"
          }
        },
        {
          "title": "জাজ কার্যকৌশল",
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
      "title": "জেভ (Jev) সিস্টেম ওয়ান ডিসিশন ইঞ্জিন",
      "group": "routing",
      "description": "স্বায়ত্তশাসিত এজেন্ট, ক্লাসিফিকেশন, সুরক্ষা গার্ডরেল এবং ক্যালিব্রেটেড সম্ভাব্যতা বিতরণের জন্য অতি-দ্রুত সিস্টেম ওয়ান ডিসিশন ইঞ্জিন।",
      "subsections": [
        {
          "title": "ডিসিশন প্রিমিটিভ ও মূল্যায়ন রুব্রিক্স",
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
          "title": "REST এপিআই স্পেসিফিকেশন (POST /v1/systemone)",
          "code": {
            "title": "System One Decision Request",
            "lang": "bash",
            "content": "curl http://localhost:8000/v1/systemone \\\n  -H \"Content-Type: application/json\" \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\n    \"model\": \"experientiallabs/jev-latest\",\n    \"state\": \"User transaction: $4,990 from IP 198.51.100.4 (New Device, Location: Kyiv, Previous: New York 10m ago).\",\n    \"questions\": [\n      {\n        \"id\": \"fraud_risk\",\n        \"text\": \"What is the fraud probability category?\",\n        \"type\": \"choice\",\n        \"options\": [\"low\", \"suspicious\", \"critical_fraud\"]\n      },\n      {\n        \"id\": \"require_2fa\",\n        \"text\": \"Should step-up 2FA verification be enforced immediately?\",\n        \"type\": \"noul\"\n      }\n    ]\n  }'\n\n# Response format:\n# {\n#   \"id\": \"jev-9b2f4c1e\",\n#   \"model\": \"experientiallabs/jev-latest\",\n#   \"decisions\": {\n#     \"fraud_risk\": {\n#       \"choice\": \"critical_fraud\",\n#       \"probabilities\": {\"low\": 0.02, \"suspicious\": 0.11, \"critical_fraud\": 0.87},\n#       \"confidence\": 0.87\n#     },\n#     \"require_2fa\": {\n#       \"value\": true,\n#       \"confidence\": 0.96\n#     }\n#   }\n# }"
          }
        },
        {
          "title": "নেটিভ এক্সিকিউশন বনাম ইন্টেলিজেন্ট এমুলেশন",
          "bullets": [
            "নেটিভ জিরো-ডিলে রাউটিং: সিস্টেম ওয়ান ডিসিশনে বিশেষজ্ঞ প্রদানকারীরা (যেমন drex.nace, experientiallabs, typesafe.ai) ন্যূনতম লেটেন্সিতে সরাসরি অনুরোধ গ্রহণ করে।",
            "ইউনিভার্সাল এলএলএম স্ট্রাকচার্ড এমুলেশন: যদি কোনো সাধারণ মডেল (যেমন gemini-2.5-flash, gpt-4o-mini, claude-3-5-haiku, ollama)-এ model_type='jev' থাকে, তবে MyAIrouter স্বয়ংক্রিয়ভাবে একটি কঠোর JSON প্রম্পটের মাধ্যমে আউটপুট প্রক্রিয়া করে।",
            "স্বচ্ছ চ্যাট সামঞ্জস্য: স্ট্যান্ডার্ড POST /v1/chat/completions জেভ পেলোড গ্রহণ করে স্বয়ংক্রিয়ভাবে ডিসিশন রেসপন্স ফেরত দেয়।",
            "উপনাম সমর্থন: POST /v1/systemone এবং POST /v1/decisions দুটি এন্ডপয়েন্টই সম্পূর্ণ সমতুল্য।"
          ]
        },
        {
          "title": "প্লেগ্রাউন্ড স্টুডিও এবং ভিজ্যুয়াল প্রিসেট",
          "bullets": [
            "ডেডিকেটেড স্টুডিও মোড: ওয়েব কনসোলে (/playground) '⚡ Jev (System One)' ট্যাবের মাধ্যমে ডিসিশন মডেল ইন্টারঅ্যাক্টিভভাবে পরীক্ষা করুন।",
            "State কনটেক্সট এডিটর: মূল্যায়নের জন্য সম্পূর্ণ বিবরণ (ইউজার প্রোফাইল, অডিট লগ, কোড ডিফস, লেনদেন বা পলিসি ডকুমেন্ট) প্রদান করুন।",
            "ভিজ্যুয়াল প্রশ্ন নির্মাতা: প্রশ্ন যোগ করুন, প্রিমিটিভের ধরন (choice, score, noul) নির্বাচন করুন এবং সরাসরি র' JSON-এ স্যুইচ করুন।",
            "৪টি প্রস্তুত প্রিসেট: কাস্টমার সাপোর্ট এস্কেলেশন, কনটেন্ট মডারেশন, পিআর কোড রিভিউ এবং আর্থিক জালিয়াতি ঝুঁকির জন্য রেডিমেড টেমপ্লেট।",
            "লাইভ চার্ট ও কোড এক্সপোর্ট: ক্যালিব্রেটেড সম্ভাব্যতা বার চার্ট, কনফিডেন্স গজ এবং cURL, Python, Node.js-এর জন্য তাৎক্ষণিক কোড রপ্তানি।"
          ]
        }
      ],
      "badge": "⚡ System One Decisions",
      "highlights": [
        "সিস্টেম ওয়ান ডিসিশন ইঞ্জিন: ক্যালিব্রেটেড সম্ভাব্যতা সহ সাব-সেকেন্ড ক্লাসিফিকেশন এবং রুব্রিক মূল্যায়ন",
        "৩টি ডিসিশন প্রিমিটিভ: Choice (ক্যাটেগরিক্যাল সম্ভাবনা বণ্টন), Score (সংখ্যাসূচক স্কোর) এবং Noul (বুলিয়ান সিদ্ধান্ত)",
        "ডেডিকেটেড এন্ডপয়েন্ট: POST /v1/systemone, POST /v1/decisions এবং সম্পূর্ণ স্বচ্ছ POST /v1/chat/completions সামঞ্জস্য",
        "জেভ প্রোভাইডারদের জন্য নেটিভ জিরো-ডিলে রাউটিং + যেকোনো এলএলএম-এর জন্য বুদ্ধিমান স্ট্রাকচার্ড JSON এমুলেশন",
        "ইন্টারেক্টিভ প্লেগ্রাউন্ড স্টুডিও: State কনটেক্সট এডিটর, ভিজ্যুয়াল বিল্ডার, ৪টি প্রিসেট, সম্ভাব্যতা চার্ট এবং কোড এক্সপোর্ট"
      ]
    },
    {
      "id": "providers",
      "title": "সমর্থিত প্রদানকারী এবং কী-লেস মোড",
      "group": "management",
      "description": "১২টিরও বেশি ক্লাউড এলএলএম প্রদানকারী এবং লোকাল রানটাইমের সাথে নেটিভ ইন্টিগ্রেশন, ওলামা ইন্সট্যান্সের জন্য কী-লেস মোড সহ।",
      "subsections": [
        {
          "title": "প্রদানকারী সক্ষমতা ম্যাট্রিক্স",
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
          "title": "স্থানীয় ওলামা কী-লেস মোড কনফিগারেশন",
          "code": {
            "title": "Add Ollama via API or UI",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/credentials \\\n  -H \"Content-Type: application/json\" \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\" \\\n  -d '{\n    \"provider\": \"ollama\",\n    \"name\": \"Local Workstation Ollama\",\n    \"api_key\": \"keyless\",\n    \"base_url\": \"http://127.0.0.1:11434\",\n    \"is_active\": true\n  }'"
          }
        }
      ],
      "badge": "Multi-Provider",
      "highlights": [
        "OpenAI, Anthropic, Gemini, Groq, DeepSeek, Cerebras, Mistral, xAI, OpenRouter এর সম্পূর্ণ সমর্থন",
        "কী-লেস মোড: ডামি চাবি ছাড়াই স্থানীয় ওলামা (http://localhost:11434) সংযুক্ত করুন",
        "vLLM, LM Studio এবং কর্পোরেট গেটওয়ের জন্য কাস্টম বেস URL সমর্থন",
        "প্রতিটি প্রদানকারীর জন্য পৃথক HTTP/SOCKS5 প্রক্সি সংযোগ"
      ]
    },
    {
      "id": "credentials",
      "title": "আপস্ট্রিম শংসাপত্র এবং কী ভল্ট",
      "group": "management",
      "description": "আপস্ট্রিম এপিআই কীগুলির জন্য ব্যাংক-গ্রেড এনক্রিপ্ট করা স্টোরেজ, অটো হেলথ চেক এবং গ্রুপ সংগঠনের সুবিধা সহ।",
      "subsections": [
        {
          "title": "ম্যানুয়াল হেলথ ভেরিফিকেশন চালানো",
          "code": {
            "title": "Health Check Endpoint",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/credentials/cred_abc123/health-check \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\"\n\n# Response:\n# {\n#   \"status\": \"healthy\",\n#   \"latency_ms\": 142.5,\n#   \"checked_at\": \"2026-09-13T14:15:00Z\"\n# }"
          }
        }
      ],
      "badge": "Encrypted Vault",
      "highlights": [
        "AES-128-CBC ফার্নেট এনক্রিপশন: ডাটাবেসে সেভ করার পূর্বে প্রতিটি কী এনক্রিপ্ট করা হয়",
        "কী মাস্কিং: গোপন কোড কখনই ইন্টারফেসে প্রকাশিত হয় না (যেমন sk-ant...7a9f)",
        "অটোমেটিক হেলথ চেক: প্রদানকারীর কাছে নিয়মিত পরীক্ষা ও কোটা যাচাইকরণ",
        "শংসাপত্র গ্রুপিং: চাবিগুলিকে ফোল্ডারে সংগঠিত করুন (প্রোডাকশন, স্টেজিং, ব্যাকআপ)"
      ]
    },
    {
      "id": "api-keys",
      "title": "রাউটার এপিআই কী এবং অনুমতি",
      "group": "management",
      "description": "ক্লায়েন্ট অ্যাক্সেস টোকেন (sk-router-...) ইস্যু এবং প্রত্যাহার করুন, প্রতি-কী রেট সীমা এবং মডেল হোয়াইটলিস্ট সহ।",
      "subsections": [
        {
          "title": "ক্লায়েন্ট কী প্যারামিটার রেফারেন্স",
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
        "SHA-256 ওয়ান-ওয়ে হ্যাশ: গোপন চাবি ডাটাবেসে প্লেইন টেক্সট হিসেবে সংরক্ষিত থাকে না",
        "রেট লিমিটিং: প্রতি মিনিটে রিকোয়েস্ট (RPM) এবং টোকেন (TPM) এর সুনির্দিষ্ট নিয়ন্ত্রণ",
        "মডেল হোয়াইটলিস্ট: নির্দিষ্ট মডেল বা রুটে অ্যাক্সেস সীমাবদ্ধ করুন",
        "স্বয়ংক্রিয় মেয়াদোত্তীর্ণ: অস্থায়ী অ্যাক্সেসের জন্য এক্সপায়ারি তারিখ নির্ধারণ করুন"
      ]
    },
    {
      "id": "proxies",
      "title": "প্রক্সি পরিচালনা এবং জিও-ট্যাগিং",
      "group": "management",
      "description": "প্রমাণীকৃত HTTP এবং SOCKS5 প্রক্সির মাধ্যমে ট্র্যাফিক রুট করুন, লেটেন্সি পরিমাপ এবং আঞ্চলিক ট্যাগিং সহ।",
      "subsections": [
        {
          "title": "প্রক্সি ফরম্যাটের উদাহরণ",
          "code": {
            "title": "Supported Proxy URI Formats",
            "lang": "bash",
            "content": "# Standard HTTP proxy:\nhttp://proxy.corporate.internal:8080\n\n# Authenticated HTTP proxy:\nhttp://username:<PROXY_PASSWORD>@us-east.proxy-vendor.com:3128\n\n# Authenticated SOCKS5 proxy:\nsocks5://proxyuser:<PROXY_PASSWORD>@sg-node.vpn-provider.net:1080"
          }
        }
      ],
      "badge": "Egress & Geo",
      "highlights": [
        "সম্পূর্ণ প্রোটোকল সমর্থন: HTTP, HTTPS এবং SOCKS5 (socks5://user:pass@host:port)",
        "দেশ ও জিও ট্যাগ: আঞ্চলিক বিধিনিষেধ অতিক্রম করতে ISO কোড (US, DE, SG, JP) নির্ধারণ করুন",
        "লেটেন্সি বেঞ্চমার্কিং: রিয়েল-টাইমে রাউন্ড-ট্রিপ সময় (RTT) পরীক্ষা",
        "চাবি অনুযায়ী পৃথক প্রক্সি: নির্দিষ্ট চাবি বা সরবরাহকারীর জন্য ডেডিকেটেড প্রক্সি বরাদ্দ করুন"
      ]
    },
    {
      "id": "backup-restore",
      "title": "এনক্রিপ্ট করা ব্যাকআপ এবং দুর্যোগ পুনরুদ্ধার",
      "group": "system",
      "description": "পাসফ্রেজ-চালিত AES-GCM এনক্রিপশনের মাধ্যমে সম্পূর্ণ রাউটার কনফিগারেশন ব্যাকআপ এবং পুনরুদ্ধার করুন।",
      "subsections": [
        {
          "title": "এপিআই এর মাধ্যমে ব্যাকআপ এক্সপোর্ট",
          "code": {
            "title": "Encrypted Backup Endpoint",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/system/backup \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{\"passphrase\": \"<BACKUP_PASSPHRASE>\"}' \\\n  -o router_backup_2026-09-13.enc"
          }
        }
      ],
      "badge": "Disaster Recovery",
      "highlights": [
        "PBKDF2 HMAC-SHA256 কী ডেরিভেশন এবং AES-256-GCM প্রমাণীকরণ সহ শক্তিশালী সুরক্ষা",
        "সম্পূর্ণ সিস্টেম স্ন্যাপশট: মডেল, সরবরাহকারী চাবি, রুট প্রোফাইল, ফিউশন জুরি, প্রক্সি এবং ক্লায়েন্ট চাবি",
        "নির্বাচনমূলক বা সম্পূর্ণ পুনরুদ্ধার: বিদ্যমান রেকর্ডের সাথে মার্জ বা সম্পূর্ণ প্রতিস্থাপনের বিকল্প",
        "সহজ মাইগ্রেশন: VPS এবং ডকার কন্টেইনারের মধ্যে দ্রুত ও মসৃণভাবে স্থানান্তর করুন"
      ]
    },
    {
      "id": "analytics",
      "title": "অ্যানালিটিক্স, লগ এবং ট্রেস পরিদর্শক",
      "group": "system",
      "description": "টোকেন অ্যাকাউন্টিং, ব্যয় অনুমান, লেটেন্সি চার্ট এবং ইন্টারেক্টিভ ওয়াটারফল ট্রেস সহ সম্পূর্ণ ট্র্যাফিক টেলিমেট্রি।",
      "subsections": [
        {
          "title": "লগ এন্ট্রি স্কিমা",
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
        "তিন ধরণের টোকেন অ্যাকাউন্টিং: প্রম্পট, কমপ্লিশন এবং রিজনিং টোকেন স্বাধীনভাবে ট্র্যাক করা হয়",
        "ওয়াটারফল ফেইলওভার ইন্সপেক্টর: প্রতিটি হপ, টাইমআউট এবং রিট্রাই চেষ্টার ধাপে ধাপে ভিজ্যুয়ালাইজেশন",
        "রিয়েল-টাইম ব্যয় গণনা: সরবরাহকারীদের মূল্যের ভিত্তিতে মার্কিন ডলারে আনুমানিক ব্যয়ের হিসাব",
        "অডিট ট্রেইল এক্সপোর্ট: স্ট্যাটাস কোড, চাবি বা মডেলের ভিত্তিতে লগ ফিল্টার এবং ডাউনলোড করুন"
      ]
    },
    {
      "id": "circuit-breaker",
      "title": "সার্কিট ব্রেকার এবং ত্রুটি বিচ্ছিন্নকরণ",
      "group": "system",
      "description": "নির্দিষ্ট স্টেট মেশিন যা ব্যর্থ বা অতিরিক্ত লোড হওয়া সরবরাহকারীদের ট্র্যাফিক বিচ্ছিন্ন করে গ্রাহক অ্যাপ্লিকেশনগুলিকে সুরক্ষিত রাখে।",
      "subsections": [
        {
          "title": "এফএসএম স্টেট লাইফসাইকেল",
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
        "৩টি অপারেশনাল অবস্থা: CLOSED (সুস্থ), OPEN (বিচ্ছিন্ন ও ডাইভার্ট করা), HALF-OPEN (পুনরুদ্ধার পরীক্ষা)",
        "ট্রিপ শর্ত: টানা ৫ বার 5xx ত্রুটি বা নেটওয়ার্ক টাইমআউটের পর সার্কিট স্বয়ংক্রিয়ভাবে বিচ্ছিন্ন হয়",
        "কুল ডাউন সময়কাল: একটি প্রোব রিকোয়েস্ট পাঠানোর আগে ৩০ সেকেন্ডের জন্য ট্র্যাফিক দূরে রাখে",
        "গ্রাহকদের জন্য নির্বিঘ্ন: প্রায়োরিটি ফলব্যাকের পরবর্তী প্রার্থী তাত্ক্ষণিকভাবে দায়িত্ব গ্রহণ করে"
      ]
    },
    {
      "id": "api-reference",
      "title": "সম্পূর্ণ এপিআই এন্ডপয়েন্ট রেফারেন্স",
      "group": "system",
      "description": "MyAIrouter সার্ভার দ্বারা প্রদত্ত সমস্ত পাবলিক ইনফারেন্স এবং প্রশাসনিক REST এন্ডপয়েন্টের সম্পূর্ণ বিবরণ।",
      "subsections": [
        {
          "title": "পাবলিক এবং অ্যাডমিন এন্ডপয়েন্ট তালিকা",
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
        "OpenAI ইনপুট: /v1/chat/completions, /v1/models (ড্রপ-ইন ক্লায়েন্ট সামঞ্জস্য)",
        "Jev System One ডিসিশন: /v1/systemone, /v1/decisions (ডিসক্রিট মূল্যায়ন ও সম্ভাব্যতা)",
        "Ollama প্রোটোকল: /api/tags, /api/show, /api/version, /api/chat",
        "কোর ম্যানেজমেন্ট: /api/v1/credentials, /api/v1/models, /api/v1/routes, /api/v1/fusion",
        "সিস্টেম ও হেলথ: /health, /api/v1/system/backup, /api/v1/system/restore"
      ]
    },
    {
      "id": "errors",
      "title": "HTTP ত্রুটি কোড এবং সমস্যা সমাধান",
      "group": "system",
      "description": "রাউটার দ্বারা ফেরত দেওয়া HTTP স্ট্যাটাস কোড, JSON ত্রুটি ফরম্যাট এবং সমস্যা সমাধানের স্পষ্ট নির্দেশিকা।",
      "subsections": [
        {
          "title": "HTTP স্ট্যাটাস কোড ক্যাটালগ",
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
        "স্ট্যান্ডার্ড OpenAI ত্রুটি স্কিমা: {\"error\": {\"message\": \"...\", \"type\": \"...\", \"code\": \"...\"}}",
        "স্পষ্ট পার্থক্য: ক্লায়েন্ট কনফিগারেশন ত্রুটি (4xx) এবং আপস্ট্রিম প্রদানকারীর ব্যর্থতার (502/504) সুস্পষ্ট বিভাজন",
        "বাস্তবধর্মী সমাধান: বার্তাগুলি স্পষ্টভাবে নির্দেশ করে যে ব্যর্থতা কোটা, কী নাকি মডেল না পাওয়ার কারণে হয়েছে",
        "রেট লিমিট হ্যান্ডলিং: ৪২৯ প্রতিক্রিয়ায় আরপিএম এবং টিপিএম সীমা অতিক্রমের তথ্য স্পষ্ট জানানো হয়"
      ]
    },
    {
      "id": "env-config",
      "title": "এনভায়রনমেন্ট ভেরিয়েবল এবং ডিপ্লয়মেন্ট",
      "group": "system",
      "description": "ডকার, পোস্টগ্রেসকিউএল, সিস্টেমডি এবং সুরক্ষা সেটিংস সহ উৎপাদনে MyAIrouter হোস্ট করার জন্য কনফিগারেশন বিকল্প।",
      "subsections": [
        {
          "title": "প্রধান পরিবেশ ভেরিয়েবল",
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
          "title": "প্রোডাকশন ডকার কম্পোজ উদাহরণ",
          "code": {
            "title": "docker-compose.prod.yml",
            "lang": "yaml",
            "content": "version: \"3.8\"\n\nservices:\n  myairouter:\n    image: myairouter:latest\n    restart: always\n    ports:\n      - \"8000:8000\"\n    environment:\n      - ROUTER_MASTER_KEY=<GENERATED_ROUTER_MASTER_KEY>\n      - DATABASE_URL=postgresql+asyncpg://router:<POSTGRES_PASSWORD>@postgres:5432/routerdb\n      - ROUTER_PORT=8000\n      - ROUTER_HOST=0.0.0.0\n      - LOG_LEVEL=INFO\n      - DEFAULT_TIMEOUT=45.0\n      - CORS_ORIGINS=https://ai.yourcompany.internal\n    depends_on:\n      - postgres\n\n  postgres:\n    image: postgres:16-alpine\n    restart: always\n    environment:\n      POSTGRES_USER: router\n      POSTGRES_PASSWORD: <POSTGRES_PASSWORD>\n      POSTGRES_DB: routerdb\n    volumes:\n      - pgdata:/var/lib/postgresql/data\n\nvolumes:\n  pgdata:"
          }
        }
      ],
      "badge": "Deployment",
      "highlights": [
        "ROUTER_MASTER_KEY: ডাটাবেসে সমস্ত শংসাপত্র এনক্রিপ্ট করার জন্য গুরুত্বপূর্ণ ৩২-বাইট মাস্টার চাবি",
        "DATABASE_URL: ডিফল্ট SQLite থেকে উচ্চ-কনকারেন্সি PostgreSQL এ স্থানান্তর করুন",
        "CORS_ORIGINS: সুরক্ষিত ওয়েব অ্যাক্সেসের জন্য অনুমোদিত ডোমেনের কমা-বিভক্ত তালিকা",
        "OLLAMA_BASE_URL: লোকাল ওলামা ডেমন সনাক্তকরণের বেস URL (ডিফল্ট: http://localhost:11434)"
      ]
    }
  ]
};
