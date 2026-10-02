import { DocContent } from "./types";

export const hi: DocContent = {
  "ui": {
    "searchPlaceholder": "दस्तावेज़ खोजें (उदा. Ollama, Fallback, Fusion, API key)...",
    "noSectionsFound": "कोई मेल खाता अनुभाग नहीं मिला।",
    "prevSection": "पिछला अनुभाग",
    "nextSection": "अगला अनुभाग",
    "copied": "कॉपी किया गया!",
    "copy": "कोड कॉपी करें",
    "endpoints": "एंडपॉइंट्स",
    "tocTitle": "दस्तावेज़ सूची"
  },
  "sections": [
    {
      "id": "overview",
      "title": "सिस्टम अवलोकन",
      "group": "intro",
      "description": "यूनिवर्सल सेल्फ-होस्टेड एलएलएम गेटवे: डायरेक्ट, प्रायोरिटी फॉलबैक, मॉडल फ्यूजन और जेव (Jev) सिस्टम वन डिसीजन इंजन, मल्टी-प्रोवाइडर की-पूलिंग और ओलामा कम्पैटिबिलिटी।",
      "subsections": [
        {
          "title": "रूटिंग मोड की तुलना",
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
        "4 रूटिंग इंजन: डायरेक्ट, प्रायोरिटी फॉलबैक (नेस्टेड), मॉडल फ्यूजन और जेव (Jev) सिस्टम वन डिसीजन",
        "ओपनएआई एपीआई (/v1/chat/completions) और ओलामा (/api/tags) के साथ पूर्ण कम्पैटिबिलिटी",
        "एंटरप्राइज सुरक्षा: ROUTER_MASTER_KEY द्वारा प्रबंधित AES-128-CBC फ़र्नेट एन्क्रिप्शन",
        "सर्किट ब्रेकर द्वारा स्वचालित विफलता अलगाव और प्रॉक्सी कनेक्टिविटी"
      ]
    },
    {
      "id": "quickstart",
      "title": "क्विकस्टार्ट गाइड",
      "group": "intro",
      "description": "कुछ ही सेकंड में किसी भी ओपनएआई लाइब्रेरी, cURL, या ओलामा क्लाइंट को MyAIrouter से कनेक्ट करें।",
      "subsections": [
        {
          "title": "1. cURL क्विकस्टार्ट",
          "code": {
            "title": "cURL Chat Completion",
            "lang": "bash",
            "content": "curl http://localhost:8000/v1/chat/completions \\\n  -H \"Content-Type: application/json\" \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\n    \"model\": \"gemini-2.5-flash\",\n    \"messages\": [{\"role\": \"user\", \"content\": \"Explain quantum computing in one sentence.\"}],\n    \"temperature\": 0.7\n  }'"
          }
        },
        {
          "title": "2. पायथन ओपनएआई एसडीके",
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
      "title": "मॉडल एड्रेसिंग और रेजोल्यूशन",
      "group": "models",
      "description": "मल्टी-मोड मॉडल एड्रेसिंग: कैनोनिकल स्लग, प्रोवाइडर-क्वालिफाइड पाथ, फॉलबैक रूट्स और फ्यूजन ज्यूरी।",
      "subsections": [
        {
          "title": "एड्रेसिंग पदानुक्रम",
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
          "title": "मॉडल प्रकार: ओपनएआई (OpenAI) संगत बनाम ⚡ जेव (Jev System One)",
          "description": "MyAIrouter कैटलॉग में प्रत्येक मॉडल के लिए निष्पादन मोड कॉन्फ़िगर करने की अनुमति देता है: डिफ़ॉल्ट ओपनएआई कम्पैटिबल या हाई-स्पीड जेव (Jev) सिस्टम वन डिसीजन इंजन।",
          "bullets": [
            "डिफ़ॉल्ट मॉडल प्रकार ('openai'): मानक टेक्स्ट जनरेशन, रीज़निंग टोकन और स्ट्रीमिंग (OpenAI, Gemini, Anthropic, Ollama आदि)।",
            "जेव मोड ('jev'): कैलिब्रेटेड प्रायिकताओं के साथ असतत मानदंडों (choice, score, noul) पर त्वरित सिस्टम वन निर्णय मूल्यांकन।",
            "नेटिव बनाम एमुलेशन: नेटिव प्रदाताओं (drex.nace, experientiallabs) को शून्य विलंबता के साथ सीधे पेलोड मिलते हैं; सामान्य LLM (GPT, Claude, Gemini, Groq) स्वचालित संरचित JSON द्वारा एमुलेट होते हैं।",
            "कैटलॉग प्रबंधन: क्विक फिल्टर ('All Types', 'OpenAI', '⚡ Jev'), एकल मॉडल संपादन, और वेब यूआई में बैच अपडेट ('Set Model Type')।",
            "एपीआई समर्थन: model_type फ़ील्ड ('openai' | 'jev') GET /v1/models और GET /v1/models/{id} में लौटाया जाता है।"
          ]
        }
      ],
      "badge": "Addressing"
    },
    {
      "id": "ollama",
      "title": "ओलामा एपीआई कम्पैटिबिलिटी",
      "group": "models",
      "description": "क्लाइंट कोड बदले बिना ओलामा सीएलआई, Continue.dev, Open WebUI, और Obsidian Copilot के लिए नेटिव कम्पैटिबिलिटी।",
      "subsections": [
        {
          "title": "ओलामा सीएलआई इंटीग्रेशन",
          "code": {
            "title": "Bash / Terminal",
            "lang": "bash",
            "content": "# Point your local Ollama client or IDE extension to MyAIrouter\nexport OLLAMA_HOST=http://localhost:8000\n\n# View all registered models, route profiles, and fusion profiles\nollama list\n\n# Execute queries directly through the OpenAI-compatible gateway\nollama run gemini-2.5-flash \"Write a Fibonacci function in Go\" "
          }
        },
        {
          "title": "समर्थित ओलामा एंडपॉइंट्स",
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
      "title": "रेटिंग्स और बेंचमार्क्स",
      "group": "models",
      "description": "आर्टिफिशियल एनालिसिस बेंचमार्क इंटीग्रेशन: क्वालिटी इंडेक्स (0-100), जेनरेशन स्पीड (टोकन/सेकंड), मूल्य और संदर्भ विंडो।",
      "subsections": [
        {
          "title": "बेंचमार्क मेट्रिक्स",
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
      "title": "एपीआई सीमाएं और कोटा",
      "group": "models",
      "description": "टू-टियर रेट लिमिटिंग: प्रति-क्रेडेंशियल RPM/TPM सीमाओं के साथ अपस्ट्रीम खातों को सुरक्षित रखें और क्लाइंट कोटा प्रबंधित करें।",
      "subsections": [
        {
          "title": "डुअल-लेयर लिमिट एनफोर्समेंट",
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
      "title": "रीजनिंग लेवल्स (CoT)",
      "group": "routing",
      "description": "ओपनएआई, एंथ्रोपिक, गूगल जेमिनी और ग्रोक के लिए स्वचालित अनुवाद के साथ यूनिवर्सल reasoning_effort पैरामीटर।",
      "subsections": [
        {
          "title": "रीजनिंग पैरामीटर का उदाहरण",
          "code": {
            "title": "cURL Reasoning Request",
            "lang": "bash",
            "content": "# Send standard reasoning_effort to any provider\ncurl http://localhost:8000/v1/chat/completions \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\n    \"model\": \"gemini-2.5-flash\",\n    \"messages\": [{\"role\": \"user\", \"content\": \"Prove that the square root of 2 is irrational.\"}],\n    \"reasoning_effort\": \"high\"\n  }'"
          }
        },
        {
          "title": "प्रोवाइडर ट्रांसलेशन मैट्रिक्स",
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
      "title": "डायरेक्ट रूटिंग इंजन",
      "group": "routing",
      "description": "अल्ट्रा-फास्ट डायरेक्ट रूटिंग: राउंड-रॉबिन लोड बैलेंसिंग और की-फॉलबैक के साथ विशिष्ट मॉडल तक सीधी पहुंच।",
      "subsections": [
        {
          "title": "डायरेक्ट रूटिंग कोड उदाहरण",
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
      "title": "प्रायोरिटी और फॉलबैक चेन्स",
      "group": "routing",
      "description": "429 कोटा समाप्ति या 5xx सर्वर त्रुटियों पर ऑटोमैटिक मल्टी-टियर फॉलबैक कतारें, नेस्टेड प्रोफाइल और की-ग्रुप सपोर्ट।",
      "subsections": [
        {
          "title": "फॉलबैक कार्यप्रणाली",
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
      "title": "मॉडल फ्यूजन (AI एन्सेम्बल)",
      "group": "routing",
      "description": "समानांतर में कई एलएलएम निष्पादित करें और रीयल-टाइम रीजनिंग स्ट्रीमिंग के साथ एक जज मॉडल द्वारा अंतिम उत्तर तैयार करें।",
      "subsections": [
        {
          "title": "स्ट्रीमिंग डेलिबरेशन का उदाहरण",
          "code": {
            "title": "SSE Fusion Stream",
            "lang": "bash",
            "content": "curl http://localhost:8000/v1/chat/completions \\\n  -H \"Content-Type: application/json\" \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\n    \"model\": \"fusion/code-jury\",\n    \"messages\": [{\"role\": \"user\", \"content\": \"Analyze time complexity of quicksort\"}],\n    \"stream\": true\n  }'\n\n# Streamed SSE chunks contain real-time deliberation in reasoning_content:\n# data: {\"choices\":[{\"delta\":{\"reasoning_content\":\"### 🧬 Fusion Ensemble Deliberation\\n...\"}}]}\n# ...\n# data: {\"choices\":[{\"delta\":{\"content\":\"Final evaluated answer...\"}}]}"
          }
        },
        {
          "title": "जज कार्य रणनीतियाँ",
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
      "title": "जेव (Jev) सिस्टम वन डिसीजन इंजन",
      "group": "routing",
      "description": "स्वायत्त एजेंटों, वर्गीकरण, सुरक्षा गार्डरेल्स और कैलिब्रेटेड प्रायिकता वितरण के साथ त्वरित सिस्टम वन डिसीजन इंजन।",
      "subsections": [
        {
          "title": "निर्णय प्रिमिटिव और मूल्यांकन रूब्रिक्स",
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
          "title": "REST एपीआई विशिष्टता (POST /v1/systemone)",
          "code": {
            "title": "System One Decision Request",
            "lang": "bash",
            "content": "curl http://localhost:8000/v1/systemone \\\n  -H \"Content-Type: application/json\" \\\n  -H \"Authorization: Bearer sk-router-YOUR_KEY\" \\\n  -d '{\n    \"model\": \"experientiallabs/jev-latest\",\n    \"state\": \"User transaction: $4,990 from IP 198.51.100.4 (New Device, Location: Kyiv, Previous: New York 10m ago).\",\n    \"questions\": [\n      {\n        \"id\": \"fraud_risk\",\n        \"text\": \"What is the fraud probability category?\",\n        \"type\": \"choice\",\n        \"options\": [\"low\", \"suspicious\", \"critical_fraud\"]\n      },\n      {\n        \"id\": \"require_2fa\",\n        \"text\": \"Should step-up 2FA verification be enforced immediately?\",\n        \"type\": \"noul\"\n      }\n    ]\n  }'\n\n# Response format:\n# {\n#   \"id\": \"jev-9b2f4c1e\",\n#   \"model\": \"experientiallabs/jev-latest\",\n#   \"decisions\": {\n#     \"fraud_risk\": {\n#       \"choice\": \"critical_fraud\",\n#       \"probabilities\": {\"low\": 0.02, \"suspicious\": 0.11, \"critical_fraud\": 0.87},\n#       \"confidence\": 0.87\n#     },\n#     \"require_2fa\": {\n#       \"value\": true,\n#       \"confidence\": 0.96\n#     }\n#   }\n# }"
          }
        },
        {
          "title": "नेटिव निष्पादन बनाम इंटेलिजेंट एमुलेशन",
          "bullets": [
            "नेटिव जीरो-डिले रूटिंग: सिस्टम वन में विशेषज्ञता रखने वाले प्रदाता (drex.nace, experientiallabs, typesafe.ai) बिना किसी विलंबता के सीधे अनुरोध प्राप्त करते हैं।",
            "सार्वभौमिक एलएलएम स्ट्रक्चर्ड एमुलेशन: यदि किसी सामान्य मॉडल (उदा. gemini-2.5-flash, gpt-4o-mini, claude-3-5-haiku, ollama) में model_type='jev' सेट है, तो MyAIrouter स्वचालित रूप से एक सख्त JSON प्रॉम्प्ट बनाकर आउटपुट को सामान्य करता है।",
            "पारदर्शी चैट कम्पैटिबिलिटी: मानक POST /v1/chat/completions जेव पेलोड को पारदर्शी रूप से स्वीकार करता है और निर्णय परिणाम देता है।",
            "उपनाम (Alias) समर्थन: POST /v1/systemone और POST /v1/decisions दोनों समान कार्यक्षमता प्रदान करते हैं।"
          ]
        },
        {
          "title": "प्लेग्राउंड स्टूडियो और विज़ुअल प्रीसेट",
          "bullets": [
            "समर्पित स्टूडियो मोड: त्वरित निर्णय मॉडल का परीक्षण करने के लिए वेब कंसोल (/playground) में '⚡ Jev (System One)' टैब।",
            "State संदर्भ संपादक: मूल्यांकन के लिए समृद्ध संदर्भ (उपयोगकर्ता प्रोफ़ाइल, ऑडिट लॉग, कोड डिफ, वित्तीय लेनदेन) दर्ज करें।",
            "विज़ुअल प्रश्न निर्माता: प्रश्न जोड़ें, प्रिमिटिव प्रकार (choice, score, noul) चुनें और सीधे JSON में टॉगल करें।",
            "4 अंतर्निहित प्रीसेट: ग्राहक सहायता एस्केलेशन, सामग्री मॉडरेशन, पीआर कोड समीक्षा, और वित्तीय धोखाधड़ी जोखिम के लिए रेडीमेड टेम्पलेट।",
            "लाइव एनालिटिक्स और कोड निर्यात: वास्तविक समय प्रायिकता बार चार्ट, विश्वास गेज और cURL, Python, Node.js के लिए त्वरित कोड जनरेशन।"
          ]
        }
      ],
      "badge": "⚡ System One Decisions",
      "highlights": [
        "सिस्टम वन डिसीजन इंजन: कैलिब्रेटेड प्रायिकताओं के साथ त्वरित वर्गीकरण और मानक मूल्यांकन",
        "3 निर्णय प्रिमिटिव: Choice (श्रेणीबद्ध वितरण), Score (मात्रात्मक स्कोर) और Noul (बूलियन निर्णय)",
        "समर्पित एंडपॉइंट्स: POST /v1/systemone, POST /v1/decisions और POST /v1/chat/completions के साथ पारदर्शी कम्पैटिबिलिटी",
        "जेव प्रदाताओं के लिए नेटिव जीरो-डिले रूटिंग + किसी भी एलएलएम के लिए इंटेलिजेंट स्ट्रक्चर्ड JSON एमुलेशन फॉलबैक",
        "इंटरएक्टिव प्लेग्राउंड स्टूडियो: State संदर्भ संपादक, विज़ुअल बिल्डर, 4 प्रीसेट, प्रायिकता चार्ट और कोड निर्यात"
      ]
    },
    {
      "id": "providers",
      "title": "समर्थित प्रदाता और की-लेस मोड",
      "group": "management",
      "description": "12+ क्लाउड एलएलएम प्रदाताओं और स्थानीय रनटाइम के साथ मूल एकीकरण, ओलामा इंस्टेंस के लिए की-लेस मोड के साथ।",
      "subsections": [
        {
          "title": "प्रदाता क्षमता मैट्रिक्स",
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
          "title": "स्थानीय ओलामा की-लेस मोड को कॉन्फ़िगर करना",
          "code": {
            "title": "Add Ollama via API or UI",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/credentials \\\n  -H \"Content-Type: application/json\" \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\" \\\n  -d '{\n    \"provider\": \"ollama\",\n    \"name\": \"Local Workstation Ollama\",\n    \"api_key\": \"keyless\",\n    \"base_url\": \"http://127.0.0.1:11434\",\n    \"is_active\": true\n  }'"
          }
        }
      ],
      "badge": "Multi-Provider",
      "highlights": [
        "OpenAI, Anthropic, Gemini, Groq, DeepSeek, Cerebras, Mistral, xAI, OpenRouter का पूर्ण समर्थन",
        "की-लेस मोड: फर्जी एपीआई की के बिना स्थानीय ओलामा (http://localhost:11434) को कनेक्ट करें",
        "vLLM, LM Studio और ओपनएआई-संगत कॉर्पोरेट गेटवे के लिए कस्टम बेस यूआरएल समर्थन",
        "प्रति प्रदाता क्रेडेंशियल के लिए समर्पित HTTP/SOCKS5 प्रॉक्सी बाइंडिंग"
      ]
    },
    {
      "id": "credentials",
      "title": "अपस्ट्रीम क्रेडेंशियल और की-वॉल्ट",
      "group": "management",
      "description": "अपस्ट्रीम एपीआई कुंजियों के लिए बैंक-ग्रेड एन्क्रिप्टेड स्टोरेज, स्वचालित स्वास्थ्य जांच और ग्रुप वर्गीकरण के साथ।",
      "subsections": [
        {
          "title": "स्वास्थ्य सत्यापन शुरू करना",
          "code": {
            "title": "Health Check Endpoint",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/credentials/cred_abc123/health-check \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\"\n\n# Response:\n# {\n#   \"status\": \"healthy\",\n#   \"latency_ms\": 142.5,\n#   \"checked_at\": \"2026-09-13T14:15:00Z\"\n# }"
          }
        }
      ],
      "badge": "Encrypted Vault",
      "highlights": [
        "AES-128-CBC फ़र्नेट एन्क्रिप्शन: SQLite में सहेजने से पहले कुंजियों को एन्क्रिप्ट किया जाता है",
        "की मास्किंग: मूल रहस्य कभी भी UI या लॉग में प्रदर्शित नहीं होते (उदा. sk-ant...7a9f)",
        "सक्रिय स्वास्थ्य जांच: प्रदाता सत्यापन एंडपॉइंट्स पर नियमित जांच",
        "क्रेडेंशियल समूह: कुंजियों को फ़ोल्डरों में व्यवस्थित करें (प्रोडक्शन, स्टेजिंग, बैकअप)"
      ]
    },
    {
      "id": "api-keys",
      "title": "राउटर एपीआई कुंजियाँ और अनुमतियाँ",
      "group": "management",
      "description": "क्लाइंट एक्सेस टोकन (sk-router-...) जारी करें, दर सीमाएँ (RPM/TPM) और मॉडल श्वेतसूची कॉन्फ़िगर करें।",
      "subsections": [
        {
          "title": "क्लाइंट कुंजी पैरामीटर संदर्भ",
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
        "SHA-256 वन-वे हैश: गुप्त कुंजियों को डेटाबेस में कभी भी सादे पाठ में संग्रहीत नहीं किया जाता",
        "दर सीमा: प्रति मिनट अनुरोध (RPM) और प्रति मिनट टोकन (TPM) पर बारीक नियंत्रण",
        "मॉडल श्वेतसूची: विशिष्ट मॉडलों तक सीमित पहुंच की अनुमति दें",
        "स्वचालित समाप्ति: अस्थायी एक्सेस के लिए समाप्ति तिथियां निर्धारित करें"
      ]
    },
    {
      "id": "proxies",
      "title": "प्रॉक्सी प्रबंधन और भू-टैगिंग",
      "group": "management",
      "description": "प्रमाणीकृत HTTP और SOCKS5 प्रॉक्सी के माध्यम से अपस्ट्रीम ट्रैफ़िक को रूट करें, विलंबता बेंचमार्किंग और क्षेत्रीय टैग के साथ।",
      "subsections": [
        {
          "title": "प्रॉक्सी प्रारूप उदाहरण",
          "code": {
            "title": "Supported Proxy URI Formats",
            "lang": "bash",
            "content": "# Standard HTTP proxy:\nhttp://proxy.corporate.internal:8080\n\n# Authenticated HTTP proxy:\nhttp://username:<PROXY_PASSWORD>@us-east.proxy-vendor.com:3128\n\n# Authenticated SOCKS5 proxy:\nsocks5://proxyuser:<PROXY_PASSWORD>@sg-node.vpn-provider.net:1080"
          }
        }
      ],
      "badge": "Egress & Geo",
      "highlights": [
        "पूर्ण प्रोटोकॉल समर्थन: HTTP, HTTPS, और SOCKS5 (socks5://user:pass@host:port)",
        "देश / भू-टैग: क्षेत्रीय आवश्यकताओं को पूरा करने के लिए ISO कोड (US, DE, SG) निर्दिष्ट करें",
        "विलंबता बेंचमार्किंग: प्रत्येक प्रॉक्सी सहेजने पर रीयल-टाइम RTT राउंड-ट्रिप परीक्षण",
        "क्रेडेंशियल स्तर पर अलगाव: व्यक्तिगत एपीआई कुंजियों को समर्पित प्रॉक्सी असाइन करें"
      ]
    },
    {
      "id": "backup-restore",
      "title": "एन्क्रिप्टेड बैकअप और डिसास्टर रिकवरी",
      "group": "system",
      "description": "पासफ्रेज-व्युत्पन्न AES-GCM एन्क्रिप्शन के साथ पूरे राउटर कॉन्फ़िगरेशन को निर्यात और पुनर्स्थापित करें।",
      "subsections": [
        {
          "title": "एपीआई के माध्यम से बैकअप निर्यात करें",
          "code": {
            "title": "Encrypted Backup Endpoint",
            "lang": "bash",
            "content": "curl -X POST http://localhost:8000/api/v1/system/backup \\\n  -H \"Authorization: Bearer ADMIN_SESSION_TOKEN\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{\"passphrase\": \"<BACKUP_PASSPHRASE>\"}' \\\n  -o router_backup_2026-09-13.enc"
          }
        }
      ],
      "badge": "Disaster Recovery",
      "highlights": [
        "यादृच्छिक 16-बाइट सॉल्ट और AES-256-GCM टैग के साथ PBKDF2 HMAC-SHA256 कुंजी व्युत्पत्ति",
        "पूर्ण सिस्टम स्नैपशॉट: मॉडल, क्रेडेंशियल, रूट प्रोफ़ाइल, फ़्यूज़न जूरी, प्रॉक्सी, एपीआई कुंजियाँ",
        "चयनात्मक या पूर्ण पुनर्स्थापना: मौजूदा संस्थाओं को मर्ज करने या बदलने का विकल्प",
        "आसान माइग्रेशन: VPS नोड्स, डॉकर कंटेनरों के बीच त्वरित स्थानांतरण"
      ]
    },
    {
      "id": "analytics",
      "title": "एनालिटिक्स, लॉग और ट्रेस इंस्पेक्टर",
      "group": "system",
      "description": "टोकन लेखांकन, लागत अनुमान, विलंबता चार्ट और इंटरैक्टिव वॉटरफॉल ट्रेस के साथ एंड-टू-एंड टेलीमेट्री।",
      "subsections": [
        {
          "title": "लॉग प्रविष्टि स्कीमा",
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
        "तीन-स्तरीय टोकन लेखांकन: प्रॉम्प्ट, पूर्णता और तर्क टोकन स्वतंत्र रूप से ट्रैक किए गए",
        "वॉटरफॉल फेलओवर इंस्पेक्टर: प्रत्येक हॉप, टाइमआउट और पुनः प्रयास का दृश्य विवरण",
        "लागत मीटर: प्रदाता मूल्य निर्धारण के आधार पर रीयल-टाइम अमरीकी डालर लागत अनुमान",
        "निर्यात योग्य ऑडिट ट्रेल: स्थिति कोड, क्लाइंट कुंजी या मॉडल द्वारा लॉग फ़िल्टर करें"
      ]
    },
    {
      "id": "circuit-breaker",
      "title": "सर्किट ब्रेकर और विफलता अलगाव",
      "group": "system",
      "description": "परिमित-स्थिति मशीन जो विफल या ओवरलोड प्रदाताओं को ट्रैफ़िक रोकती है, जिससे कैस्केडिंग टाइमआउट को रोका जा सके।",
      "subsections": [
        {
          "title": "FSM स्थिति जीवनचक्र",
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
        "3 परिचालन अवस्थाएँ: CLOSED (स्वस्थ), OPEN (विफल, ट्रैफ़िक डायवर्ट), HALF-OPEN (पुनर्प्राप्ति परीक्षण)",
        "ट्रिप शर्त: लगातार 5 बार 5xx त्रुटियों या नेटवर्क टाइमआउट के बाद स्वचालित रूप से ट्रिप होता है",
        "कूलिंग डाउन अवधि: एकल परीक्षण अनुरोध भेजने से पहले 30 सेकंड के लिए ट्रैफ़िक को अलग रखता है",
        "क्लाइंट के लिए पारदर्शी: प्रायोरिटी फॉलबैक में अगला उम्मीदवार बिना किसी रुकावट के कार्यभार संभालता है"
      ]
    },
    {
      "id": "api-reference",
      "title": "पूर्ण एपीआई एंडपॉइंट संदर्भ",
      "group": "system",
      "description": "MyAIrouter सर्वर द्वारा प्रदान किए गए सभी सार्वजनिक अनुमान और प्रशासनिक REST एंडपॉइंट्स की विस्तृत सूची।",
      "subsections": [
        {
          "title": "सार्वजनिक और व्यवस्थापक एंडपॉइंट्स तालिका",
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
        "OpenAI इनपुट: /v1/chat/completions, /v1/models (पूर्ण क्लाइंट संगतता)",
        "Jev System One डिसीजन: /v1/systemone, /v1/decisions (असतत निर्णय मूल्यांकन)",
        "Ollama प्रोटोकॉल: /api/tags, /api/show, /api/version, /api/chat",
        "कोर प्रबंधन: /api/v1/credentials, /api/v1/models, /api/v1/routes, /api/v1/fusion",
        "सिस्टम और स्वास्थ्य: /health, /api/v1/system/backup, /api/v1/system/restore"
      ]
    },
    {
      "id": "errors",
      "title": "HTTP त्रुटि कोड और समस्या निवारण",
      "group": "system",
      "description": "राउटर द्वारा लौटाए गए HTTP स्थिति कोड, JSON त्रुटि प्रारूप विनिर्देशों और समस्या निवारण चरणों का विस्तृत विवरण।",
      "subsections": [
        {
          "title": "HTTP स्थिति कोड कैटलॉग",
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
        "मानक OpenAI त्रुटि स्कीमा: {\"error\": {\"message\": \"...\", \"type\": \"...\", \"code\": \"...\"}}",
        "स्पष्ट अंतर: क्लाइंट त्रुटियों (4xx) को अपस्ट्रीम प्रदाता विफलताओं (502/504) से अलग करता है",
        "सटीक निदान: विशिष्ट त्रुटि संदेश बताते हैं कि विफलता कोटा, प्रमाणीकरण या मॉडल के कारण हुई",
        "दर सीमा प्रबंधन: 429 प्रतिक्रियाएं RPM और TPM के लिए पुनः प्रयास के स्पष्ट संकेत देती हैं"
      ]
    },
    {
      "id": "env-config",
      "title": "पर्यावरण चर और परिनियोजन",
      "group": "system",
      "description": "Docker, PostgreSQL, systemd और कस्टम सुरक्षा सेटिंग्स के साथ MyAIrouter को उत्पादन में होस्ट करने के लिए कॉन्फ़िगरेशन विकल्प।",
      "subsections": [
        {
          "title": "मुख्य पर्यावरण चर",
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
          "title": "उत्पादन डॉकर कम्पोज़ उदाहरण",
          "code": {
            "title": "docker-compose.prod.yml",
            "lang": "yaml",
            "content": "version: \"3.8\"\n\nservices:\n  myairouter:\n    image: myairouter:latest\n    restart: always\n    ports:\n      - \"8000:8000\"\n    environment:\n      - ROUTER_MASTER_KEY=<GENERATED_ROUTER_MASTER_KEY>\n      - DATABASE_URL=postgresql+asyncpg://router:<POSTGRES_PASSWORD>@postgres:5432/routerdb\n      - ROUTER_PORT=8000\n      - ROUTER_HOST=0.0.0.0\n      - LOG_LEVEL=INFO\n      - DEFAULT_TIMEOUT=45.0\n      - CORS_ORIGINS=https://ai.yourcompany.internal\n    depends_on:\n      - postgres\n\n  postgres:\n    image: postgres:16-alpine\n    restart: always\n    environment:\n      POSTGRES_USER: router\n      POSTGRES_PASSWORD: <POSTGRES_PASSWORD>\n      POSTGRES_DB: routerdb\n    volumes:\n      - pgdata:/var/lib/postgresql/data\n\nvolumes:\n  pgdata:"
          }
        }
      ],
      "badge": "Deployment",
      "highlights": [
        "ROUTER_MASTER_KEY: डेटाबेस में सभी क्रेडेंशियल को एन्क्रिप्ट करने के लिए महत्वपूर्ण 32-बाइट कुंजी",
        "DATABASE_URL: डिफ़ॉल्ट SQLite से उच्च-समवर्ती PostgreSQL पर स्विच करें",
        "CORS_ORIGINS: सुरक्षित वेब क्लाइंट एक्सेस के लिए अनुमत ऑरिजिन की सूची",
        "OLLAMA_BASE_URL: स्थानीय या दूरस्थ ओलामा डेमॉन के लिए डिफ़ॉल्ट खोज यूआरएल"
      ]
    }
  ]
};
