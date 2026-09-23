# Part 1: Sections 1-10

SECTIONS_PART1 = [
    {
        "id": "overview",
        "group": "intro",
        "badge": "Core Architecture",
        "titles": {
            "en": "System Overview", "ru": "Обзор системы", "uk": "Огляд системи", "be": "Агляд сістэмы",
            "zh": "系统架构概述", "es": "Descripción general", "fr": "Présentation du système", "de": "Systemübersicht",
            "ja": "システム概要", "pt": "Visão Geral do Sistema", "ar": "نظرة عامة على النظام", "hi": "सिस्टम अवलोकन", "bn": "সিস্টেম ওভারভিউ"
        },
        "descriptions": {
            "en": "Universal self-hosted LLM gateway with Direct, Priority Fallback, and Model Fusion engines, multi-provider key pooling, and Ollama compatibility.",
            "ru": "Универсальный self-hosted ИИ-шлюз с 3 движками маршрутизации (Direct, Priority Fallback, Fusion), пулом ключей и поддержкой протоколов OpenAI и Ollama.",
            "uk": "Універсальний self-hosted ШІ-шлюз із 3 механізмами маршрутизації (Direct, Priority Fallback, Fusion), пулом ключів та підтримкою протоколів OpenAI й Ollama.",
            "be": "Універсальны self-hosted ШІ-шлюз з 3 рухавікамі маршрутызацыі (Direct, Priority Fallback, Fusion), пулам ключоў і падтрымкай OpenAI і Ollama.",
            "zh": "自托管通用大模型网关，内置直连、优先级回退与模型融合三大引擎，支持多提供商密钥池和 Ollama 协议兼容。",
            "es": "Pasarela LLM autohospedada universal con motores Direct, Priority Fallback y Model Fusion, agrupación de claves y compatibilidad con Ollama.",
            "fr": "Passerelle LLM auto-hébergée universelle avec moteurs Direct, Repli prioritaire et Fusion, mutualisation de clés et compatibilité Ollama.",
            "de": "Universelles, selbst gehostetes LLM-Gateway mit Direct-, Priority-Fallback- und Fusion-Engines, Key-Pooling und Ollama-Kompatibilität.",
            "ja": "Direct、Priority Fallback、Model Fusionの3つのルーティングエンジンとOllama互換性を備えたセルフホスト型LLMゲートウェイ。",
            "pt": "Gateway LLM universal auto-hospedado com motores Direct, Priority Fallback e Model Fusion, pool de chaves e compatibilidade com Ollama.",
            "ar": "بوابة نماذج لغوية ذاتية الاستضافة مع محركات التوجيه المباشر والاحتياطي والدمج، وتجمع المفاتيح وتوافق Ollama.",
            "hi": "यूनिवर्सल सेल्फ-होस्टेड एलएलएम गेटवे: डायरेक्ट, प्रायोरिटी फॉलबैक और मॉडल फ्यूजन इंजन, मल्टी-प्रोवाइडर की-पूलिंग और ओलामा कम्पैटिबिलिटी।",
            "bn": "ইউনিভার্সাল সেলফ-হোস্টেড এলএলএম গেটওয়ে: ডাইরেক্ট, প্রায়োরিটি ফলব্যাক এবং মডেল ফিউশন ইঞ্জিন, মাল্টি-প্রোভাইডার কি পুলিং এবং ওলামা সামঞ্জস্য।"
        },
        "highlights": {
            "en": [
                "3 Routing Engines: Direct, Priority Fallback (nested), Model Fusion (judge ensembles)",
                "OpenAI API (/v1/chat/completions) & Ollama (/api/tags, /api/show) drop-in compatibility",
                "Enterprise Key Security: AES-128-CBC Fernet encryption with ROUTER_MASTER_KEY",
                "Circuit Breaker fault isolation with automatic recovery & geo-proxy binding"
            ],
            "ru": [
                "3 движка маршрутизации: Прямой, Приоритетный Fallback (вложенный), Ансамбль Model Fusion",
                "Совместимость с протоколами OpenAI (/v1/chat/completions) и Ollama (/api/tags, /api/show)",
                "Надежное шифрование ключей: AES-128-CBC Fernet под управлением ROUTER_MASTER_KEY",
                "Автоматический Circuit Breaker с самовосстановлением и привязкой гео-прокси"
            ],
            "uk": [
                "3 рушії маршрутизації: Прямий, Пріоритетний Fallback (вкладений), Ансамбль Model Fusion",
                "Повна сумісність з OpenAI API (/v1/chat/completions) та Ollama (/api/tags, /api/show)",
                "Надійне шифрування ключів: AES-128-CBC Fernet під контролем ROUTER_MASTER_KEY",
                "Автоматичний Circuit Breaker із самовідновленням та прив'язкою гео-проксі"
            ],
            "be": [
                "3 рухавікі маршрутызацыі: Прамы, Прыярытэтны Fallback (укладзены), Ансамбль Model Fusion",
                "Поўная сумяшчальнасць з OpenAI API (/v1/chat/completions) і Ollama (/api/tags, /api/show)",
                "Надзейнае шыфраванне ключоў: AES-128-CBC Fernet пад кіраваннем ROUTER_MASTER_KEY",
                "Аўтаматычны Circuit Breaker з самааднаўленнем і прывязкай геа-проксі"
            ],
            "zh": [
                "三大路由引擎：直连路由、优先级回退（支持嵌套）、模型融合评审团",
                "完美兼容 OpenAI API (/v1/chat/completions) 与 Ollama (/api/tags, /api/show)",
                "企业级安全：基于 ROUTER_MASTER_KEY 的 AES-128-CBC Fernet 密钥加密存储",
                "断路器自动隔离故障节点，支持健康检测自愈与独立代理绑定"
            ],
            "es": [
                "3 motores de enrutamiento: Directo, Fallback prioritario (anidado) y Fusión de modelos",
                "Compatibilidad total con API OpenAI (/v1/chat/completions) y Ollama (/api/tags, /api/show)",
                "Seguridad empresarial: cifrado AES-128-CBC Fernet mediante ROUTER_MASTER_KEY",
                "Aislamiento de fallos por Circuit Breaker con autorrecuperación y proxies geo"
            ],
            "fr": [
                "3 moteurs de routage : Direct, Repli prioritaire (imbriqué) et Fusion de modèles",
                "Compatibilité directe avec l'API OpenAI (/v1/chat/completions) et Ollama (/api/tags)",
                "Sécurité renforcée : chiffrement AES-128-CBC Fernet via ROUTER_MASTER_KEY",
                "Disjoncteur automatique (Circuit Breaker) avec auto-guérison et liaison proxy"
            ],
            "de": [
                "3 Routing-Engines: Direkt, Prioritäts-Fallback (verschachtelt) und Modell-Fusion",
                "Kompatibel mit OpenAI-API (/v1/chat/completions) und Ollama (/api/tags, /api/show)",
                "Sichere Schlüsselverwaltung: AES-128-CBC Fernet-Verschlüsselung mit ROUTER_MASTER_KEY",
                "Circuit Breaker zur automatischen Fehlerisolation mit Geo-Proxy-Unterstützung"
            ],
            "ja": [
                "3つのルーティングエンジン：ダイレクト、優先度フォールバック（入れ子対応）、モデル融合",
                "OpenAI API (/v1/chat/completions) および Ollama (/api/tags) との完全互換",
                "強固なセキュリティ：ROUTER_MASTER_KEY による AES-128-CBC 暗号化",
                "サーキットブレーカーによる障害自動隔離とジオプロキシ連携"
            ],
            "pt": [
                "3 motores de roteamento: Direto, Fallback prioritário (aninhado) e Fusão de modelos",
                "Compatibilidade total com OpenAI API (/v1/chat/completions) e Ollama (/api/tags)",
                "Segurança avançada: criptografia AES-128-CBC Fernet usando ROUTER_MASTER_KEY",
                "Isolamento automático de falhas com Circuit Breaker e suporte a proxies"
            ],
            "ar": [
                "3 محركات توجيه: المباشر، والاحتياطي ذو الأولوية (المتداخل)، ودمج النماذج",
                "توافق فوري مع واجهات OpenAI (/v1/chat/completions) وOllama (/api/tags)",
                "تشفير عالي الأمان: AES-128-CBC Fernet محمي بمفتاح ROUTER_MASTER_KEY",
                "قاطع الدائرة الكهربائية (Circuit Breaker) لعزل الأعطال مع دعم البروكسي الجغرافي"
            ],
            "hi": [
                "3 रूटिंग इंजन: डायरेक्ट, प्रायोरिटी फॉलबैक (नेस्टेड), और मॉडल फ्यूजन",
                "ओपनएआई एपीआई (/v1/chat/completions) और ओलामा (/api/tags) के साथ पूर्ण कम्पैटिबिलिटी",
                "एंटरप्राइज सुरक्षा: ROUTER_MASTER_KEY द्वारा प्रबंधित AES-128-CBC फ़र्नेट एन्क्रिप्शन",
                "सर्किट ब्रेकर द्वारा स्वचालित विफलता अलगाव और प्रॉक्सी कनेक्टिविटी"
            ],
            "bn": [
                "৩টি রাউটিং ইঞ্জিন: ডাইরেক্ট, প্রায়োরিটি ফলব্যাক (নেস্টেড), এবং মডেল ফিউশন",
                "OpenAI API (/v1/chat/completions) এবং Ollama (/api/tags) এর সাথে সম্পূর্ণ সামঞ্জস্য",
                "নিরাপদ কী স্টোরেজ: ROUTER_MASTER_KEY চালিত AES-128-CBC ফার্নেট এনক্রিপশন",
                "সার্কিট ব্রেকার স্বয়ংক্রিয় ত্রুটি বিচ্ছিন্নকরণ এবং প্রক্সি ইন্টিগ্রেশন"
            ]
        },
        "subsections": [
            {
                "titles": {
                    "en": "Routing Modes Comparison", "ru": "Сравнение движков маршрутизации", "uk": "Порівняння рушіїв маршрутизації", "be": "Параўнанне рухавікоў маршрутызацыі",
                    "zh": "路由模式特性对比", "es": "Comparación de modos de enrutamiento", "fr": "Comparaison des modes de routage", "de": "Vergleich der Routing-Modi",
                    "ja": "ルーティングモードの比較", "pt": "Comparação dos Modos de Roteamento", "ar": "مقارنة أوضاع التوجيه", "hi": "रूटिंग मोड की तुलना", "bn": "রাউটিং মোডের তুলনা"
                },
                "table": {
                    "headers": ["Mode / Мод", "Slug Prefix", "Target / Цель", "Strategy / Стратегия", "Latency / Задержка"],
                    "rows": [
                        ["Direct Routing", "none or provider/", "Single Provider Model", "Round-robin across healthy credentials", "Lowest (single hop)"],
                        ["Priority Fallback", "route/*", "Ordered Chain of Models/Profiles", "Sequential try-next on 429 / 5xx error", "Fast on 1st, robust on failure"],
                        ["Model Fusion", "fusion/*", "Multi-Model Ensemble + Judge", "Parallel execution with consensus synthesis", "Higher (multi-model + judge deliberation)"]
                    ]
                }
            }
        ]
    },
    {
        "id": "quickstart",
        "group": "intro",
        "badge": "2-Minute Setup",
        "titles": {
            "en": "Quickstart Guide", "ru": "Быстрый старт", "uk": "Швидкий старт", "be": "Хуткі старт",
            "zh": "快速上手指南", "es": "Guía de inicio rápido", "fr": "Démarrage rapide", "de": "Schnellstart-Anleitung",
            "ja": "クイックスタート", "pt": "Início Rápido", "ar": "دليل البدء السريع", "hi": "क्विकस्टार्ट गाइड", "bn": "কুইকস্টার্ট গাইড"
        },
        "descriptions": {
            "en": "Connect any OpenAI-compatible library, cURL, or local Ollama client to MyAIrouter gateway in seconds.",
            "ru": "Подключение любой библиотеки OpenAI SDK, cURL или Ollama-клиента к шлюзу MyAIrouter за считанные секунды.",
            "uk": "Підключення будь-якої бібліотеки OpenAI SDK, cURL або Ollama-клієнта до шлюзу MyAIrouter за лічені секунди.",
            "be": "Падключэнне любой бібліятэкі OpenAI SDK, cURL або Ollama-кліента да шлюза MyAIrouter за лічаныя секунды.",
            "zh": "秒级将任何 OpenAI SDK、cURL 脚本或本地 Ollama 客户端连接至 MyAIrouter 智能网关。",
            "es": "Conecte cualquier librería OpenAI, cURL o cliente Ollama a la pasarela MyAIrouter en segundos.",
            "fr": "Connectez n'importe quelle bibliothèque OpenAI, cURL ou client Ollama à MyAIrouter en quelques secondes.",
            "de": "Verbinden Sie jedes OpenAI-SDK, cURL oder lokale Ollama-Clients in Sekundenschnelle mit MyAIrouter.",
            "ja": "OpenAI SDK、cURL、またはOllamaクライアントをわずか数秒でMyAIrouterに接続。",
            "pt": "Conecte qualquer biblioteca OpenAI, cURL ou cliente Ollama ao gateway MyAIrouter em segundos.",
            "ar": "اربط أي مكتبة متوافقة مع OpenAI أو cURL أو عميل Ollama ببوابة MyAIrouter في ثوانٍ.",
            "hi": "कुछ ही सेकंड में किसी भी ओपनएआई लाइब्रेरी, cURL, या ओलामा क्लाइंट को MyAIrouter से कनेक्ट करें।",
            "bn": "কয়েক সেকেন্ডের মধ্যে যেকোনো ওপেনএআই লাইব্রেরি, cURL, বা ওলামা ক্লায়েন্টকে MyAIrouter এর সাথে যুক্ত করুন।"
        },
        "subsections": [
            {
                "titles": {
                    "en": "1. cURL Quickstart", "ru": "1. Быстрый вызов через cURL", "uk": "1. Швидкий виклик через cURL", "be": "1. Хуткі выклік праз cURL",
                    "zh": "1. cURL 命令行调用", "es": "1. Inicio rápido con cURL", "fr": "1. Appel rapide avec cURL", "de": "1. cURL Schnellstart",
                    "ja": "1. cURL クイックスタート", "pt": "1. Início rápido com cURL", "ar": "1. البدء السريع عبر cURL", "hi": "1. cURL क्विकस्टार्ट", "bn": "1. cURL কুইকস্টার্ট"
                },
                "code": {
                    "title": "cURL Chat Completion",
                    "lang": "bash",
                    "content": """curl http://localhost:8000/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer sk-router-YOUR_KEY" \\
  -d '{
    "model": "gemini-2.5-flash",
    "messages": [{"role": "user", "content": "Explain quantum computing in one sentence."}],
    "temperature": 0.7
  }'"""
                }
            },
            {
                "titles": {
                    "en": "2. Python OpenAI SDK", "ru": "2. Python SDK (OpenAI)", "uk": "2. Python SDK (OpenAI)", "be": "2. Python SDK (OpenAI)",
                    "zh": "2. Python OpenAI 官方库", "es": "2. Python OpenAI SDK", "fr": "2. SDK Python OpenAI", "de": "2. Python OpenAI SDK",
                    "ja": "2. Python OpenAI SDK", "pt": "2. Python OpenAI SDK", "ar": "2. مكتبة Python OpenAI", "hi": "2. पायथन ओपनएआई एसडीके", "bn": "2. পাইথন ওপেনএআই এসডিকে"
                },
                "code": {
                    "title": "Python Client (Streaming)",
                    "lang": "python",
                    "content": """from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="sk-router-YOUR_KEY"
)

response = client.chat.completions.create(
    model="route/coding-fallback",
    messages=[
        {"role": "system", "content": "You are an expert engineer."},
        {"role": "user", "content": "Write an async Python client for SSE."}
    ],
    temperature=0.2,
    stream=True
)

for chunk in response:
    if chunk.choices and chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)"""
                }
            },
            {
                "titles": {
                    "en": "3. Node.js / TypeScript", "ru": "3. Node.js / TypeScript", "uk": "3. Node.js / TypeScript", "be": "3. Node.js / TypeScript",
                    "zh": "3. Node.js / TypeScript", "es": "3. Node.js / TypeScript", "fr": "3. Node.js / TypeScript", "de": "3. Node.js / TypeScript",
                    "ja": "3. Node.js / TypeScript", "pt": "3. Node.js / TypeScript", "ar": "3. Node.js / TypeScript", "hi": "3. Node.js / TypeScript", "bn": "3. Node.js / TypeScript"
                },
                "code": {
                    "title": "TypeScript OpenAI Client",
                    "lang": "typescript",
                    "content": """import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "http://localhost:8000/v1",
  apiKey: "sk-router-YOUR_KEY",
});

async function main() {
  const completion = await client.chat.completions.create({
    model: "fusion/code-jury",
    messages: [{ role: "user", content: "Compare Rust and Go for API gateways." }],
  });
  console.log(completion.choices[0].message.content);
}

main();"""
                }
            }
        ]
    },
    {
        "id": "models",
        "group": "models",
        "badge": "Addressing",
        "titles": {
            "en": "Model Addressing & Resolution", "ru": "Адресация и выбор моделей", "uk": "Адресація та вибір моделей", "be": "Адрасацыя і выбар мадэляў",
            "zh": "模型寻址与解析机制", "es": "Direccionamiento de modelos", "fr": "Adressage et résolution des modèles", "de": "Modell-Adressierung & Auflösung",
            "ja": "モデルのアドレッシングと解決", "pt": "Endereçamento e Resolução de Modelos", "ar": "عنونة النماذج والتحليل", "hi": "मॉडल एड्रेसिंग और रेजोल्यूशन", "bn": "মডেল অ্যাড্রেসিং ও রেজোলিউশন"
        },
        "descriptions": {
            "en": "Flexible multi-mode model addressing: canonical slugs, provider-qualified identifiers, priority fallback routes, and fusion juries.",
            "ru": "Гибкая многоуровневая адресация моделей: канонические slug-имена, прямые провайдерные пути, цепочки fallback и ансамбли fusion.",
            "uk": "Гнучка багаторівнева адресація моделей: канонічні slug-імена, прямі провайдерні шляхи, ланцюжки fallback та ансамблі fusion.",
            "be": "Гнуткая шматузроўневая адрасацыя мадэляў: кананічныя slug-імёны, прамыя шляхі правайдэраў, ланцужкі fallback і ансамблі fusion.",
            "zh": "多层次模型寻址方案：标准规范名、指定提供商前缀、回退路由别名与融合评审团标识。",
            "es": "Direccionamiento flexible multinivel: slugs canónicos, identificadores calificados por proveedor, rutas de fallback y jurados de fusión.",
            "fr": "Adressage flexible à plusieurs niveaux : slugs canoniques, identifiants qualifiés par fournisseur, routes de repli et jurys de fusion.",
            "de": "Flexibles mehrstufiges Modell-Adressierungssystem: kanonische Slugs, Provider-Präfixe, Fallback-Routen und Fusion-Jurys.",
            "ja": "柔軟なマルチモードアドレッシング：正規スラッグ、プロバイダー修飾子、フォールバックルート、フュージョン審査団。",
            "pt": "Endereçamento flexível em vários modos: slugs canônicos, identificadores por provedor, rotas de fallback e júris de fusão.",
            "ar": "عنونة مرنة متعددة الأنماط: المعرفات القياسية، وتحديد المزود، ومسارات الاحتياط، ولجان التحكيم المندمجة.",
            "hi": "मल्टी-मोड मॉडल एड्रेसिंग: कैनोनिकल स्लग, प्रोवाइडर-क्वालिफाइड पाथ, फॉलबैक रूट्स और फ्यूजन ज्यूरी।",
            "bn": "মাল্টি-মোড মডেল অ্যাড্রেসিং: ক্যানোনিকাল স্ল্যাগ, প্রোভাইডার-কোয়ালিফাইড পাথ, ফলব্যাক রুট এবং ফিউশন জুরি।"
        },
        "subsections": [
            {
                "titles": {
                    "en": "Addressing Hierarchy", "ru": "Иерархия адресации моделей", "uk": "Ієрархія адресації моделей", "be": "Іерархія адрасацыі мадэляў",
                    "zh": "寻址层级规范", "es": "Jerarquía de direccionamiento", "fr": "Hiérarchie d'adressage", "de": "Adressierungshierarchie",
                    "ja": "アドレッシングの階層", "pt": "Hierarquia de Endereçamento", "ar": "تسلسل العنونة", "hi": "एड्रेसिंग पदानुक्रम", "bn": "অ্যাড্রেসিং হায়ারার্কি"
                },
                "table": {
                    "headers": ["Addressing Type / Тип", "Example Request / Пример", "Routing Behavior / Поведение"],
                    "rows": [
                        ["Canonical Slug", "gemini-2.5-flash", "Resolves to highest priority provider with healthy credentials"],
                        ["Provider-Qualified", "openrouter/meta-llama/llama-3.3-70b", "Forces execution strictly via specified upstream provider"],
                        ["Route Profile", "route/coding-fallback", "Executes multi-tier priority fallback chain on 429/5xx errors"],
                        ["Fusion Profile", "fusion/code-jury", "Parallel multi-model execution synthesized by a Judge LLM"]
                    ]
                }
            }
        ]
    },
    {
        "id": "ollama",
        "group": "models",
        "badge": "Drop-in Ollama",
        "titles": {
            "en": "Ollama Compatibility API", "ru": "Совместимость с Ollama API", "uk": "Сумісність з Ollama API", "be": "Сумяшчальнасць з Ollama API",
            "zh": "Ollama 协议兼容接口", "es": "Compatibilidad con Ollama API", "fr": "Compatibilité API Ollama", "de": "Ollama API-Kompatibilität",
            "ja": "Ollama API 互換性", "pt": "Compatibilidade com Ollama API", "ar": "توافق واجهة برمجة تطبيقات Ollama", "hi": "ओलामा एपीआई कम्पैटिबिलिटी", "bn": "ওলামা এপিআই সামঞ্জস্য"
        },
        "descriptions": {
            "en": "Native drop-in support for Ollama CLI, Continue.dev, Open WebUI, and Obsidian Copilot without modifying client code.",
            "ru": "Нативная совместимость с утилитой Ollama CLI, плагинами Continue.dev, Open WebUI и Obsidian Copilot без изменения клиентского кода.",
            "uk": "Нативна сумісність з утилітою Ollama CLI, плагінами Continue.dev, Open WebUI та Obsidian Copilot без змін у клієнтському коді.",
            "be": "Натыўная сумяшчальнасць з утылітай Ollama CLI, плагінамі Continue.dev, Open WebUI і Obsidian Copilot без змен у кліенцкім кодзе.",
            "zh": "原生兼容 Ollama CLI 命令行工具、Continue.dev、Open WebUI 和 Obsidian Copilot，无需修改现有客户端代码。",
            "es": "Compatibilidad nativa con Ollama CLI, Continue.dev, Open WebUI y Obsidian Copilot sin modificar código cliente.",
            "fr": "Prise en charge native directe d'Ollama CLI, Continue.dev, Open WebUI et Obsidian Copilot sans modifier le code client.",
            "de": "Native Unterstützung für Ollama CLI, Continue.dev, Open WebUI und Obsidian Copilot ohne Anpassung des Client-Codes.",
            "ja": "クライアントコードを変更することなく、Ollama CLI、Continue.dev、Open WebUI、Obsidian Copilotをそのまま利用可能。",
            "pt": "Suporte nativo a Ollama CLI, Continue.dev, Open WebUI e Obsidian Copilot sem alterar código cliente.",
            "ar": "دعم أصلي مباشر لـ Ollama CLI وContinue.dev وOpen WebUI وObsidian Copilot دون تعديل كود العميل.",
            "hi": "क्लाइंट कोड बदले बिना ओलामा सीएलआई, Continue.dev, Open WebUI, और Obsidian Copilot के लिए नेटिव कम्पैटिबिलिटी।",
            "bn": "ক্লায়েন্ট কোড পরিবর্তন না করেই ওলামা সিএলআই, Continue.dev, Open WebUI, এবং Obsidian Copilot এর জন্য নেটিভ সমর্থন।"
        },
        "subsections": [
            {
                "titles": {
                    "en": "Ollama CLI Integration", "ru": "Использование через Ollama CLI", "uk": "Використання через Ollama CLI", "be": "Выкарыстанне праз Ollama CLI",
                    "zh": "使用 Ollama CLI 访问网关", "es": "Integración con Ollama CLI", "fr": "Intégration Ollama CLI", "de": "Ollama CLI Integration",
                    "ja": "Ollama CLI との統合", "pt": "Integração com Ollama CLI", "ar": "التكامل مع أداة سطر أوامر Ollama", "hi": "ओलामा सीएलआई इंटीग्रेशन", "bn": "ওলামা সিএলআই ইন্টিগ্রেশন"
                },
                "code": {
                    "title": "Bash / Terminal",
                    "lang": "bash",
                    "content": """# Point your local Ollama client or IDE extension to MyAIrouter
export OLLAMA_HOST=http://localhost:8000

# View all registered models, route profiles, and fusion profiles
ollama list

# Execute queries directly through the OpenAI-compatible gateway
ollama run gemini-2.5-flash "Write a Fibonacci function in Go" """
                }
            },
            {
                "titles": {
                    "en": "Supported Ollama Endpoints", "ru": "Поддерживаемые эндпоинты Ollama", "uk": "Підтримувані ендпоінти Ollama", "be": "Падтрымліваемыя эндпоінты Ollama",
                    "zh": "支持的 Ollama 接口列表", "es": "Puntos finales compatibles de Ollama", "fr": "Points de terminaison Ollama pris en charge", "de": "Unterstützte Ollama-Endpunkte",
                    "ja": "サポートされる Ollama エンドポイント", "pt": "Endpoints Ollama Suportados", "ar": "نقاط نهاية Ollama المدعومة", "hi": "समर्थित ओलामा एंडपॉइंट्स", "bn": "সমর্থিত ওলামা এন্ডপয়েন্ট"
                },
                "table": {
                    "headers": ["Endpoint / Эндпоинт", "Method / Метод", "Description / Описание"],
                    "rows": [
                        ["/api/tags", "GET", "Returns list of all active models and route profiles formatted as Ollama tags"],
                        ["/api/show", "POST", "Returns detailed model parameters, template info, and context length"],
                        ["/api/version", "GET", "Returns gateway compatibility version info"]
                    ]
                }
            }
        ]
    },
    {
        "id": "intelligence-ratings",
        "group": "models",
        "badge": "Benchmarks",
        "titles": {
            "en": "Ratings & Benchmarks", "ru": "Рейтинги и бенчмарки", "uk": "Рейтинги та бенчмарки", "be": "Рэйтынгі і бенчмаркі",
            "zh": "模型评测与基准数据", "es": "Calificaciones y Benchmarks", "fr": "Notes et bancs d'essai", "de": "Bewertungen & Benchmarks",
            "ja": "レーティングとベンチマーク", "pt": "Classificações e Benchmarks", "ar": "التقييمات والمعايير القياسية", "hi": "रेटिंग्स और बेंचमार्क्स", "bn": "রেটিং এবং বেঞ্চমার্ক"
        },
        "descriptions": {
            "en": "Automated Artificial Analysis metrics: Quality Index (0-100), generation speed (tok/s), token pricing, and context limits.",
            "ru": "Автоматическая интеграция бенчмарков Artificial Analysis: индекс качества (0-100), скорость генерации (ток/с), стоимость и контекст.",
            "uk": "Автоматична інтеграція бенчмарків Artificial Analysis: індекс якості (0-100), швидкість генерації (ток/с), вартість та контекст.",
            "be": "Аўтаматычная інтэграцыя бенчмаркаў Artificial Analysis: індэкс якасці (0-100), хуткасць генерацыі (ток/с), кошт і кантэкст.",
            "zh": "自动集成 Artificial Analysis 基准数据：综合质量评分 (0-100)、生成速度 (token/s)、百万 Token 价格与上下文窗口。",
            "es": "Métricas automáticas de Artificial Analysis: Índice de calidad (0-100), velocidad de generación, precios y ventana de contexto.",
            "fr": "Métriques intégrées d'Artificial Analysis : Indice de qualité (0-100), vitesse de génération, tarification et contexte.",
            "de": "Automatische Artificial Analysis-Metriken: Qualitätsindex (0-100), Generierungsgeschwindigkeit, Preise und Kontextfenster.",
            "ja": "Artificial Analysisの自動ベンチマーク連携：品質スコア（0-100）、生成速度（tok/s）、料金、コンテキスト長。",
            "pt": "Métricas automáticas de Artificial Analysis: Índice de qualidade (0-100), velocidade de geração, preços e limite de contexto.",
            "ar": "مقاييس Artificial Analysis الآلية: مؤشر الجودة (0-100)، سرعة التوليد (رمز/ثانية)، التسعير، وحدود السياق.",
            "hi": "आर्टिफिशियल एनालिसिस बेंचमार्क इंटीग्रेशन: क्वालिटी इंडेक्स (0-100), जेनरेशन स्पीड (टोकन/सेकंड), मूल्य और संदर्भ विंडो।",
            "bn": "আর্টিফিশিয়াল অ্যানালাইসিস বেঞ্চমার্ক ইন্টিগ্রেশন: গুণমান সূচক (0-100), উৎপাদন গতি (টোকেন/সেকেন্ড), মূল্য এবং কনটেক্সট উইন্ডো।"
        },
        "subsections": [
            {
                "titles": {
                    "en": "Benchmark Metrics", "ru": "Ключевые показатели моделей", "uk": "Ключові показники моделей", "be": "Ключавыя паказчыкі мадэляў",
                    "zh": "评测指标解析", "es": "Métricas de Benchmark", "fr": "Indicateurs d'évaluation", "de": "Benchmark-Metriken",
                    "ja": "ベンチマーク指標", "pt": "Métricas de Benchmark", "ar": "معايير القياس", "hi": "बेंचमार्क मेट्रिक्स", "bn": "বেঞ্চমার্ক মেট্রিক্স"
                },
                "table": {
                    "headers": ["Metric / Показатель", "Range / Диапазон", "Description / Значение"],
                    "rows": [
                        ["Quality Index", "0 — 100", "Composite intelligence index based on coding, math, reasoning, and instruction following"],
                        ["Output Speed", "10 — 300+ tok/s", "Median streaming completion velocity measured on real workloads"],
                        ["Context Window", "4K — 2M+ tokens", "Maximum active input context supported by the model architecture"],
                        ["Pricing (1M tokens)", "$0.05 — $60.00", "Estimated blended cost per million prompt and completion tokens"]
                    ]
                }
            }
        ]
    },
    {
        "id": "model-limits",
        "group": "models",
        "badge": "Quotas & RPM",
        "titles": {
            "en": "API Limits & Quotas", "ru": "Лимиты API и квоты", "uk": "Ліміти API та квоти", "be": "Ліміты API і квоты",
            "zh": "API 速率限制与配额", "es": "Límites y cuotas de API", "fr": "Limites et quotas d'API", "de": "API-Limits & Kontingente",
            "ja": "API 制限とクォータ", "pt": "Limites e Cotas de API", "ar": "حدود واجهة برمجة التطبيقات والحصص", "hi": "एपीआई सीमाएं और कोटा", "bn": "এপিআই সীমা এবং কোটা"
        },
        "descriptions": {
            "en": "Two-tier rate limiting: protect upstream accounts with per-credential RPM/TPM bounds while regulating client API key usage.",
            "ru": "Двухуровневое ограничение скорости: защита upstream-аккаунтов (RPM/TPM по ключам) и управление квотами клиентов шлюза.",
            "uk": "Дворівневе обмеження швидкості: захист upstream-акаунтів (RPM/TPM за ключами) та контроль квот клієнтів шлюзу.",
            "be": "Двухузроўневае абмежаванне хуткасці: абарона upstream-акаўнтаў (RPM/TPM па ключах) і кантроль квот кліентаў шлюза.",
            "zh": "双层速率控制机制：为每个上游凭据设置独立 RPM/TPM 保护账号，同时对下游客户端密钥进行配额与并发监管。",
            "es": "Control de tasa en dos niveles: proteja cuentas upstream con límites RPM/TPM por credencial y controle el uso de clientes.",
            "fr": "Limitation de débit à deux niveaux : protégez les comptes amont via des limites RPM/TPM par clé et gérez les quotas clients.",
            "de": "Zweistufige Ratenbegrenzung: Schützen Sie Upstream-Konten mit RPM/TPM-Grenzen und steuern Sie Client-Kontingente.",
            "ja": "2層構造のレート制限：認証情報ごとのRPM/TPM制限で上流アカウントを保護し、クライアント利用を細かく制御。",
            "pt": "Controle de taxa em dois níveis: proteja contas upstream com limites de RPM/TPM por credencial e regule clientes.",
            "ar": "تحديد المعدل على مستويين: حماية حسابات المزودين بحدود RPM/TPM لكل مفتاح، مع تنظيم استخدام عملاء البوابة.",
            "hi": "टू-टियर रेट लिमिटिंग: प्रति-क्रेडेंशियल RPM/TPM सीमाओं के साथ अपस्ट्रीम खातों को सुरक्षित रखें और क्लाइंट कोटा प्रबंधित करें।",
            "bn": "দ্বি-স্তরীয় রেট লিমিটিং: আপস্ট্রিম অ্যাকাউন্ট রক্ষা করতে আরপিএম/টিপিএম সীমাবদ্ধতা এবং ক্লায়েন্ট কোটা নিয়ন্ত্রণ।"
        },
        "subsections": [
            {
                "titles": {
                    "en": "Dual-Layer Enforcement", "ru": "Двухуровневый контроль лимитов", "uk": "Дворівневий контроль лімітів", "be": "Двухузроўневы кантроль лімітаў",
                    "zh": "双层限流控制逻辑", "es": "Control de límites en dos capas", "fr": "Contrôle des limites à double niveau", "de": "Zweistufige Limitüberwachung",
                    "ja": "2層制限の仕組み", "pt": "Controle de Limites em Duas Camadas", "ar": "آلية تطبيق الحدود المزدوجة", "hi": "डुअल-लेयर लिमिट एनफोर्समेंट", "bn": "দ্বৈত-স্তর লিমিট প্রয়োগ"
                },
                "table": {
                    "headers": ["Layer / Уровень", "Target / Объект", "Configurable Parameters", "Behavior on Limit"],
                    "rows": [
                        ["Upstream Layer", "Provider Credential", "RPM limit, TPM limit, max concurrency", "Skips busy key, routes to next available healthy key"],
                        ["Client Router Layer", "Router API Key", "RPM, TPM, total requests quota, expiration", "Returns HTTP 429 Too Many Requests to client app"]
                    ]
                }
            }
        ]
    },
    {
        "id": "thinking-cot",
        "group": "routing",
        "badge": "Reasoning Effort",
        "titles": {
            "en": "Reasoning Levels (CoT)", "ru": "Уровни рассуждений (CoT)", "uk": "Рівні міркувань (CoT)", "be": "Узроўні разваг (CoT)",
            "zh": "思维链推理强度 (CoT)", "es": "Niveles de razonamiento (CoT)", "fr": "Niveaux de raisonnement (CoT)", "de": "Denkstufen & CoT",
            "ja": "思考レベル (CoT)", "pt": "Níveis de Raciocínio (CoT)", "ar": "مستويات التفكير والمنطق (CoT)", "hi": "रीजनिंग लेवल्स (CoT)", "bn": "রিজনিং লেভেলস (CoT)"
        },
        "descriptions": {
            "en": "Universal reasoning_effort parameter with automatic cross-provider translation for OpenAI, Anthropic, Google Gemini, and Groq.",
            "ru": "Универсальный параметр reasoning_effort с двусторонней трансляцией форматов между OpenAI, Anthropic, Google Gemini и Groq.",
            "uk": "Універсальний параметр reasoning_effort із двосторонньою трансляцією форматів між OpenAI, Anthropic, Google Gemini та Groq.",
            "be": "Універсальны параметр reasoning_effort з двухбаковай трансляцыяй фарматаў паміж OpenAI, Anthropic, Google Gemini і Groq.",
            "zh": "通用的 reasoning_effort 推理参数，自动在 OpenAI、Anthropic Claude、Google Gemini 和 Groq 间进行双向协议翻译。",
            "es": "Parámetro universal reasoning_effort con traducción automática entre OpenAI, Anthropic, Google Gemini y Groq.",
            "fr": "Paramètre universel reasoning_effort avec conversion transparente entre OpenAI, Anthropic, Google Gemini et Groq.",
            "de": "Universeller Parameter reasoning_effort mit automatischer Übersetzung zwischen OpenAI, Anthropic, Google Gemini und Groq.",
            "ja": "OpenAI、Anthropic、Google Gemini、Groqの間で自動相互変換されるユニバーサルな reasoning_effort パラメータ。",
            "pt": "Parâmetro universal reasoning_effort com tradução bidirecional entre OpenAI, Anthropic, Google Gemini e Groq.",
            "ar": "معلمة reasoning_effort الموحدة مع ترجمة تلقائية متوافقة عبر OpenAI وAnthropic وGoogle Gemini وGroq.",
            "hi": "ओपनएआई, एंथ्रोपिक, गूगल जेमिनी और ग्रोक के लिए स्वचालित अनुवाद के साथ यूनिवर्सल reasoning_effort पैरामीटर।",
            "bn": "OpenAI, Anthropic, Google Gemini এবং Groq এর জন্য স্বয়ংক্রিয় অনুবাদ সহ ইউনিভার্সাল reasoning_effort প্যারামিটার।"
        },
        "subsections": [
            {
                "titles": {
                    "en": "Universal Reasoning Example", "ru": "Пример запроса с reasoning_effort", "uk": "Приклад запиту з reasoning_effort", "be": "Прыклад запыту з reasoning_effort",
                    "zh": "推理参数请求示例", "es": "Ejemplo de parámetro de razonamiento", "fr": "Exemple de paramètre de raisonnement", "de": "Beispiel für Denkparameter",
                    "ja": "思考パラメータのリクエスト例", "pt": "Exemplo de Parâmetro de Raciocínio", "ar": "مثال على معلمة التفكير", "hi": "रीजनिंग पैरामीटर का उदाहरण", "bn": "রিজনিং প্যারামিটারের উদাহরণ"
                },
                "code": {
                    "title": "cURL Reasoning Request",
                    "lang": "bash",
                    "content": """# Send standard reasoning_effort to any provider
curl http://localhost:8000/v1/chat/completions \\
  -H "Authorization: Bearer sk-router-YOUR_KEY" \\
  -d '{
    "model": "gemini-2.5-flash",
    "messages": [{"role": "user", "content": "Prove that the square root of 2 is irrational."}],
    "reasoning_effort": "high"
  }'"""
                }
            },
            {
                "titles": {
                    "en": "Provider Translation Matrix", "ru": "Матрица трансляции параметров", "uk": "Матриця трансляції параметрів", "be": "Матрыца трансляцыі параметраў",
                    "zh": "各厂商参数映射矩阵", "es": "Matriz de traducción entre proveedores", "fr": "Matrice de conversion des fournisseurs", "de": "Provider-Übersetzungsmatrix",
                    "ja": "プロバイダー変換マトリクス", "pt": "Matriz de Tradução entre Provedores", "ar": "مصفوفة ترجمة بروتوكولات المزودين", "hi": "प्रोवाइडर ट्रांसलेशन मैट्रिक्स", "bn": "প্রোভাইডার ট্রান্সলেশন ম্যাট্রিক্স"
                },
                "table": {
                    "headers": ["Standard Parameter", "Anthropic Claude", "Google Gemini", "Groq / DeepSeek"],
                    "rows": [
                        ["low", "thinking: { budget_tokens: 1024 }", "thinkingBudget: 1024", "reasoning_effort: low"],
                        ["medium", "thinking: { budget_tokens: 4096 }", "thinkingBudget: 4096", "reasoning_effort: medium"],
                        ["high", "thinking: { budget_tokens: 8192 }", "thinkingBudget: 8192", "reasoning_effort: high"],
                        ["none", "thinking: disabled", "thinkingBudget: 0", "reasoning_format: none"]
                    ]
                }
            }
        ]
    },
    {
        "id": "direct-routing",
        "group": "routing",
        "badge": "Low Latency",
        "titles": {
            "en": "Direct Routing Engine", "ru": "Прямая маршрутизация (Direct)", "uk": "Пряма маршрутизація (Direct)", "be": "Прамая маршрутызацыя (Direct)",
            "zh": "直连路由引擎 (Direct)", "es": "Enrutamiento directo (Direct)", "fr": "Moteur de routage direct", "de": "Direct-Routing-Engine",
            "ja": "ダイレクトルーティング", "pt": "Roteamento Direto (Direct)", "ar": "محرك التوجيه المباشر (Direct)", "hi": "डायरेक्ट रूटिंग इंजन", "bn": "ডাইরেক্ট রাউটিং ইঞ্জিন"
        },
        "descriptions": {
            "en": "Ultra-fast direct routing targeting a specific upstream model with round-robin key balancing and intra-provider failover.",
            "ru": "Высокоскоростная прямая отправка запроса в конкретную модель с балансировкой Round-robin и мгновенным переключением ключей.",
            "uk": "Високошвидкісна пряма відправка запиту в конкретну модель із балансуванням Round-robin та миттєвим перемиканням ключів.",
            "be": "Высокахуткасная прамая адпраўка запыту ў канкрэтную мадэль з балансаваннем Round-robin і імгненным пераключэннем ключоў.",
            "zh": "高性能直连调用指定模型，支持多密钥轮询负载均衡以及上游遭遇 429 时的同提供商内自动重试切换。",
            "es": "Enrutamiento directo ultrarrápido al modelo especificado con balanceo round-robin y conmutación automática entre claves.",
            "fr": "Routage direct ultra-rapide vers un modèle spécifique avec équilibrage round-robin et basculement automatique de clé.",
            "de": "Ultraschnelles Direct-Routing zu einem bestimmten Modell mit Round-Robin-Key-Balancing und automatischem Schlüssel-Failover.",
            "ja": "ラウンドロビン方式のキー分散と障害時の自動フェイルオーバーを備えた超高速ダイレクトルーティング。",
            "pt": "Roteamento direto ultrarrápido para um modelo específico com balanceamento round-robin e failover automático de chaves.",
            "ar": "توجيه فائق السرعة نحو نموذج محدد مباشرة مع موازنة المفاتيح بنظام Round-robin والتبديل التلقائي عند الخطأ.",
            "hi": "अल्ट्रा-फास्ट डायरेक्ट रूटिंग: राउंड-रॉबिन लोड बैलेंसिंग और की-फॉलबैक के साथ विशिष्ट मॉडल तक सीधी पहुंच।",
            "bn": "নির্দিষ্ট মডেলে সরাসরি উচ্চ-গতির রাউটিং, রাউন্ড-রবিন লোড ব্যালেন্সিং এবং স্বয়ংক্রিয় কী ফেইলওভার।"
        },
        "subsections": [
            {
                "titles": {
                    "en": "Addressing Code Sample", "ru": "Примеры прямого обращения", "uk": "Приклади прямого звернення", "be": "Прыклады прамога звароту",
                    "zh": "直连模式调用示例", "es": "Ejemplo de enrutamiento directo", "fr": "Exemple d'appel direct", "de": "Direct-Routing Codebeispiel",
                    "ja": "ダイレクト指定のコード例", "pt": "Exemplo de Roteamento Direto", "ar": "أمثلة الاستدعاء المباشر", "hi": "डायरेक्ट रूटिंग कोड उदाहरण", "bn": "ডাইরেক্ট রাউটিং কোড উদাহরণ"
                },
                "code": {
                    "title": "Direct Routing Requests",
                    "lang": "bash",
                    "content": """# 1. Canonical slug (auto-resolves primary provider)
curl http://localhost:8000/v1/chat/completions \\
  -H "Authorization: Bearer sk-router-YOUR_KEY" \\
  -d '{"model": "gemini-2.5-flash", "messages": [{"role":"user","content":"Hello!"}]}'

# 2. Provider-qualified addressing (forces specific provider)
curl http://localhost:8000/v1/chat/completions \\
  -H "Authorization: Bearer sk-router-YOUR_KEY" \\
  -d '{"model": "openrouter/meta-llama/llama-3.3-70b-instruct", "messages": [{"role":"user","content":"Hello!"}]}'"""
                }
            }
        ]
    },
    {
        "id": "priority-fallback",
        "group": "routing",
        "badge": "Nested Chains",
        "titles": {
            "en": "Priority & Fallback Chains", "ru": "Приоритеты и Fallback", "uk": "Пріоритети та Fallback", "be": "Прыярытэты і Fallback",
            "zh": "优先级与回退链路 (Fallback)", "es": "Cadenas de Fallback prioritario", "fr": "Chaînes de repli prioritaire", "de": "Prioritäts- & Fallback-Ketten",
            "ja": "優先度とフォールバックチェーン", "pt": "Cadeias de Fallback e Prioridade", "ar": "سلاسل الأولوية والاحتياط (Fallback)", "hi": "प्रायोरिटी और फॉलबैक चेन्स", "bn": "প্রায়োরিটি এবং ফলব্যাক চেইন"
        },
        "descriptions": {
            "en": "Multi-tier fallback queues across models and providers on 429 quota exhaustion or 5xx server outages, with nested profiles and key groups.",
            "ru": "Многоуровневые очереди переключения при 429 лимитах или 5xx ошибках, поддержка вложенных профилей и групп ключей.",
            "uk": "Багаторівневі черги перемикання при 429 лімітах або 5xx помилках, підтримка вкладених профілів та груп ключів.",
            "be": "Шматузроўневыя чэргі пераключэння пры 429 лімітах або 5xx памылках, падтрымка ўкладзеных профіляў і груп ключоў.",
            "zh": "当遇到上游 429 限流或 5xx 故障时自动切换的多级回退队列，支持嵌套路由配置、密钥分组与参数覆盖。",
            "es": "Colas de conmutación multinivel en caso de cuotas 429 o fallos 5xx, con perfiles anidados y grupos de claves.",
            "fr": "Files d'attente multi-niveaux en cas de quota 429 ou d'erreur 5xx, avec profils imbriqués et groupes de clés.",
            "de": "Mehrstufige Ausfallwarteschlangen bei 429-Quotenüberschreitungen oder 5xx-Fehlern, mit verschachtelten Profilen und Schlüsselgruppen.",
            "ja": "429 レート制限や 5xx 障害発生時に自動切り替えを行う多層フォールバックキュー。入れ子プロファイルやキーグループに対応。",
            "pt": "Filas de alternância em vários níveis em erros 429 ou 5xx, com suporte a perfis aninhados e grupos de chaves.",
            "ar": "قوائم تبديل متعددة المستويات عند استنفاد الحصص 429 أو أخطاء الخوادم 5xx، مع دعم المسارات المتداخلة ومجموعات المفاتيح.",
            "hi": "429 कोटा समाप्ति या 5xx सर्वर त्रुटियों पर ऑटोमैटिक मल्टी-टियर फॉलबैक कतारें, नेस्टेड प्रोफाइल और की-ग्रुप सपोर्ट।",
            "bn": "429 কোটা বা 5xx ত্রুটিতে স্বয়ংক্রিয় মাল্টি-লেভেল ফলব্যাক সারি, নেস্টেড প্রোফাইল এবং কী-গ্রুপ সমর্থন।"
        },
        "subsections": [
            {
                "titles": {
                    "en": "Fallback Mechanics", "ru": "Принцип работы цепочки", "uk": "Принцип роботи ланцюжка", "be": "Прынцып працы ланцужка",
                    "zh": "回退链路工作机制", "es": "Mecánica de Fallback", "fr": "Mécanisme de basculement", "de": "Fallback-Funktionsweise",
                    "ja": "フォールバックの動作原理", "pt": "Mecânica do Fallback", "ar": "آلية عمل السلسلة الاحتياطية", "hi": "फॉलबैक कार्यप्रणाली", "bn": "ফলব্যাক কাজের পদ্ধতি"
                },
                "table": {
                    "headers": ["Feature / Возможность", "Configuration / Настройка", "Benefit / Преимущество"],
                    "rows": [
                        ["Candidate Sequence", "Ordered list (Candidate 1 -> 2 -> 3)", "Ensures primary low-cost models are tried first before expensive fallbacks"],
                        ["Nested Profiles", "candidate_type: 'profile'", "Allows sharing base queues (e.g. embed route/standard inside route/premium)"],
                        ["Credential Groups", "credential_group: 'folder_name' or 'all'", "Restricts fallback candidate to team keys or enables full provider pool"],
                        ["Overrides", "temperature, context_length, reasoning", "Fine-tunes behavior per fallback step independently of request"]
                    ]
                }
            }
        ]
    },
    {
        "id": "fusion",
        "group": "routing",
        "badge": "AI Ensembles",
        "titles": {
            "en": "Model Fusion (Ensembles)", "ru": "Model Fusion (Ансамбли ИИ)", "uk": "Model Fusion (Ансамблі ШІ)", "be": "Model Fusion (Ансамблі ШІ)",
            "zh": "模型融合机制 (Model Fusion)", "es": "Fusión de modelos (Ensembles)", "fr": "Fusion de modèles (Ensembles IA)", "de": "Modell-Fusion (KI-Ensembles)",
            "ja": "モデル融合 (Model Fusion)", "pt": "Fusão de Modelos (Ensembles)", "ar": "دمج النماذج (Model Fusion)", "hi": "मॉडल फ्यूजन (AI एन्सेम्बल)", "bn": "মডেল ফিউশন (AI সমাহার)"
        },
        "descriptions": {
            "en": "Execute multiple LLMs in parallel and synthesize the definitive response using a Judge model with real-time reasoning streaming.",
            "ru": "Параллельное выполнение нескольких моделей и синтез эталонного ответа моделью-судьей с потоковой передачей хода рассуждений.",
            "uk": "Паралельне виконання кількох моделей та синтез еталонної відповіді моделлю-суддею з потоковою передачею ходу міркувань.",
            "be": "Паралельнае выкананне некалькіх мадэляў і сінтэз эталоннага адказу мадэллю-суддзёй з струменевай перадачай ходу разваг.",
            "zh": "多模型并发并行执行，由指定的评审模型 (Judge) 对候选草稿进行评优、共识提炼或批判重写，并实时流式传输评审思考链。",
            "es": "Ejecute varios LLM en paralelo y sintetice la respuesta definitiva mediante un modelo Juez con transmisión de razonamiento en tiempo real.",
            "fr": "Exécutez plusieurs LLM en parallèle et synthétisez la réponse optimale grâce à un modèle Juge avec streaming des réflexions.",
            "de": "Führen Sie mehrere LLMs parallel aus und synthetisieren Sie die beste Antwort mit einem Judge-Modell inklusive Echtzeit-Deliberations-Streaming.",
            "ja": "複数のLLMを並行実行し、Judgeモデルが最適な回答を統合・生成。審査過程の思考ストリーミングにも完全対応。",
            "pt": "Execute múltiplos LLMs em paralelo e sintetize a resposta ideal usando um modelo Juiz com streaming de raciocínio em tempo real.",
            "ar": "تشغيل نماذج لغوية متعددة بالتوازي وتوليف إجابة موحدة عبر نموذج الحكم مع بث خطوات التفكير المباشرة.",
            "hi": "समानांतर में कई एलएलएम निष्पादित करें और रीयल-टाइम रीजनिंग स्ट्रीमिंग के साथ एक जज मॉडल द्वारा अंतिम उत्तर तैयार करें।",
            "bn": "একসাথে একাধিক এলএলএম পরিচালনা করুন এবং রিয়েল-টাইম রিজনিং স্ট্রিমিং সহ জাজ মডেল দ্বারা চূড়ান্ত প্রতিক্রিয়া তৈরি করুন।"
        },
        "subsections": [
            {
                "titles": {
                    "en": "Streaming Deliberation Example", "ru": "Потоковый вывод хода обсуждения", "uk": "Потокове виведення обговорення", "be": "Струменевы вывад ходу абмеркавання",
                    "zh": "流式评审过程示例", "es": "Ejemplo de deliberación en streaming", "fr": "Exemple de délibération en streaming", "de": "Streaming-Deliberation Beispiel",
                    "ja": "審査思考ストリーミングの例", "pt": "Exemplo de Deliberação em Streaming", "ar": "مثال على بث خطوات التفكير", "hi": "स्ट्रीमिंग डेलिबरेशन का उदाहरण", "bn": "স্ট্রিমিং ডিলিবারেশন উদাহরণ"
                },
                "code": {
                    "title": "SSE Fusion Stream",
                    "lang": "bash",
                    "content": """curl http://localhost:8000/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer sk-router-YOUR_KEY" \\
  -d '{
    "model": "fusion/code-jury",
    "messages": [{"role": "user", "content": "Analyze time complexity of quicksort"}],
    "stream": true
  }'

# Streamed SSE chunks contain real-time deliberation in reasoning_content:
# data: {"choices":[{"delta":{"reasoning_content":"### 🧬 Fusion Ensemble Deliberation\\n..."}}]}
# ...
# data: {"choices":[{"delta":{"content":"Final evaluated answer..."}}]}"""
                }
            },
            {
                "titles": {
                    "en": "Judge Strategies", "ru": "Стратегии работы судьи", "uk": "Стратегії роботи судді", "be": "Стратэгіі працы суддзі",
                    "zh": "评审团工作策略", "es": "Estrategias de arbitraje del Juez", "fr": "Stratégies d'arbitrage du Juge", "de": "Judge-Strategien",
                    "ja": "Judge 戦略の比較", "pt": "Estratégias de Avaliação do Juiz", "ar": "استراتيجيات التحكيم", "hi": "जज कार्य रणनीतियाँ", "bn": "জাজ কার্যকৌশল"
                },
                "table": {
                    "headers": ["Strategy / Стратегия", "ID", "Operation / Принцип работы"],
                    "rows": [
                        ["Best-of-N", "best_of_n", "Compares all candidate drafts and selects the highest scoring complete response"],
                        ["Consensus", "consensus", "Synthesizes a unified response combining best points and resolving discrepancies"],
                        ["Critique & Rewrite", "critique_and_rewrite", "Critiques weaknesses in each draft and writes a superior comprehensive answer"]
                    ]
                }
            }
        ]
    }
]
