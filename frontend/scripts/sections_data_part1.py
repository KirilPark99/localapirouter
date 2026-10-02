# Part 1: Sections 1-11

SECTIONS_PART1 = [   {   'id': 'overview',
        'group': 'intro',
        'badge': 'Core Architecture',
        'titles': {   'en': 'System Overview',
                      'ru': 'Обзор системы',
                      'uk': 'Огляд системи',
                      'be': 'Агляд сістэмы',
                      'zh': '系统架构概述',
                      'es': 'Descripción general',
                      'fr': 'Présentation du système',
                      'de': 'Systemübersicht',
                      'ja': 'システム概要',
                      'pt': 'Visão Geral do Sistema',
                      'ar': 'نظرة عامة على النظام',
                      'hi': 'सिस्टम अवलोकन',
                      'bn': 'সিস্টেম ওভারভিউ'},
        'descriptions': {   'en': 'Universal self-hosted LLM gateway with Direct, Priority Fallback, Model Fusion, and '
                                  'Jev System One decision engines, multi-provider key pooling, and Ollama '
                                  'compatibility.',
                            'ru': 'Универсальный self-hosted ИИ-шлюз с 4 движками маршрутизации (Direct, Priority '
                                  'Fallback, Fusion, Jev System One), пулом ключей и поддержкой протоколов OpenAI и '
                                  'Ollama.',
                            'uk': 'Універсальний self-hosted ШІ-шлюз із 4 механізмами маршрутизації (Direct, Priority '
                                  'Fallback, Fusion, Jev System One), пулом ключів та підтримкою протоколів OpenAI й '
                                  'Ollama.',
                            'be': 'Універсальны self-hosted ШІ-шлюз з 4 рухавікамі маршрутызацыі (Direct, Priority '
                                  'Fallback, Fusion, Jev System One), пулам ключоў і падтрымкай OpenAI і Ollama.',
                            'zh': '自托管通用大模型网关，内置直连、优先级回退、模型融合与 Jev 快决策四大引擎，支持多提供商密钥池和 Ollama 协议兼容。',
                            'es': 'Pasarela LLM autohospedada universal con motores Direct, Priority Fallback, Model '
                                  'Fusion y decisiones Jev System One, agrupación de claves y compatibilidad con '
                                  'Ollama.',
                            'fr': 'Passerelle LLM auto-hébergée universelle avec moteurs Direct, Repli prioritaire, '
                                  'Fusion et décisions Jev System One, mutualisation de clés et compatibilité Ollama.',
                            'de': 'Universelles, selbst gehostetes LLM-Gateway mit Direct-, Priority-Fallback-, '
                                  'Fusion- und Jev System One Entscheidungs-Engines, Key-Pooling und '
                                  'Ollama-Kompatibilität.',
                            'ja': 'Direct、Priority Fallback、Model Fusion、Jev System '
                                  'Oneの4つのルーティングエンジンとOllama互換性を備えたセルフホスト型LLMゲートウェイ。',
                            'pt': 'Gateway LLM universal auto-hospedado com motores Direct, Priority Fallback, Model '
                                  'Fusion e decisões Jev System One, pool de chaves e compatibilidade com Ollama.',
                            'ar': 'بوابة نماذج لغوية ذاتية الاستضافة مع 4 محركات توجيه (المباشر، الاحتياطي، الدمج، '
                                  'وقرارات Jev System One)، وتجمع المفاتيح وتوافق Ollama.',
                            'hi': 'यूनिवर्सल सेल्फ-होस्टेड एलएलएम गेटवे: डायरेक्ट, प्रायोरिटी फॉलबैक, मॉडल फ्यूजन और '
                                  'जेव (Jev) सिस्टम वन डिसीजन इंजन, मल्टी-प्रोवाइडर की-पूलिंग और ओलामा कम्पैटिबिलिटी।',
                            'bn': 'ইউনিভার্সাল সেলফ-হোস্টেড এলএলএম গেটওয়ে: ডাইরেক্ট, প্রায়োরিটি ফলব্যাক, মডেল ফিউশন '
                                  'এবং জেভ (Jev) সিস্টেম ওয়ান ডিসিশন ইঞ্জিন, মাল্টি-প্রোভাইডার কি পুলিং এবং ওলামা '
                                  'সামঞ্জস্য।'},
        'highlights': {   'en': [   '4 Routing Engines: Direct, Priority Fallback (nested), Model Fusion (judge '
                                    'ensembles), and Jev System One Decisions',
                                    'OpenAI API (/v1/chat/completions) & Ollama (/api/tags, /api/show) drop-in '
                                    'compatibility',
                                    'Enterprise Key Security: AES-128-CBC Fernet encryption with ROUTER_MASTER_KEY',
                                    'Circuit Breaker fault isolation with automatic recovery & geo-proxy binding'],
                          'ru': [   '4 движка маршрутизации: Прямой, Приоритетный Fallback (вложенный), Ансамбль Model '
                                    'Fusion и Решения Jev System One',
                                    'Совместимость с протоколами OpenAI (/v1/chat/completions) и Ollama (/api/tags, '
                                    '/api/show)',
                                    'Надежное шифрование ключей: AES-128-CBC Fernet под управлением ROUTER_MASTER_KEY',
                                    'Автоматический Circuit Breaker с самовосстановлением и привязкой гео-прокси'],
                          'uk': [   '4 рушії маршрутизації: Прямий, Пріоритетний Fallback (вкладений), Ансамбль Model '
                                    'Fusion та Рішення Jev System One',
                                    'Повна сумісність з OpenAI API (/v1/chat/completions) та Ollama (/api/tags, '
                                    '/api/show)',
                                    'Надійне шифрування ключів: AES-128-CBC Fernet під контролем ROUTER_MASTER_KEY',
                                    "Автоматичний Circuit Breaker із самовідновленням та прив'язкою гео-проксі"],
                          'be': [   '4 рухавікі маршрутызацыі: Прамы, Прыярытэтны Fallback (укладзены), Ансамбль Model '
                                    'Fusion і Рашэнні Jev System One',
                                    'Поўная сумяшчальнасць з OpenAI API (/v1/chat/completions) і Ollama (/api/tags, '
                                    '/api/show)',
                                    'Надзейнае шыфраванне ключоў: AES-128-CBC Fernet пад кіраваннем ROUTER_MASTER_KEY',
                                    'Аўтаматычны Circuit Breaker з самааднаўленнем і прывязкай геа-проксі'],
                          'zh': [   '四大路由引擎：直连路由、优先级回退（支持嵌套）、模型融合评审团与 Jev 快决策 (System One)',
                                    '完美兼容 OpenAI API (/v1/chat/completions) 与 Ollama (/api/tags, /api/show)',
                                    '企业级安全：基于 ROUTER_MASTER_KEY 的 AES-128-CBC Fernet 密钥加密存储',
                                    '断路器自动隔离故障节点，支持健康检测自愈与独立代理绑定'],
                          'es': [   '4 motores de enrutamiento: Directo, Fallback prioritario (anidado), Fusión de '
                                    'modelos y Decisiones Jev System One',
                                    'Compatibilidad total con API OpenAI (/v1/chat/completions) y Ollama (/api/tags, '
                                    '/api/show)',
                                    'Seguridad empresarial: cifrado AES-128-CBC Fernet mediante ROUTER_MASTER_KEY',
                                    'Aislamiento de fallos por Circuit Breaker con autorrecuperación y proxies geo'],
                          'fr': [   '4 moteurs de routage : Direct, Repli prioritaire (imbriqué), Fusion de modèles et '
                                    'Décisions Jev System One',
                                    "Compatibilité directe avec l'API OpenAI (/v1/chat/completions) et Ollama "
                                    '(/api/tags)',
                                    'Sécurité renforcée : chiffrement AES-128-CBC Fernet via ROUTER_MASTER_KEY',
                                    'Disjoncteur automatique (Circuit Breaker) avec auto-guérison et liaison proxy'],
                          'de': [   '4 Routing-Engines: Direkt, Prioritäts-Fallback (verschachtelt), Modell-Fusion und '
                                    'Jev System One Decisions',
                                    'Kompatibel mit OpenAI-API (/v1/chat/completions) und Ollama (/api/tags, '
                                    '/api/show)',
                                    'Sichere Schlüsselverwaltung: AES-128-CBC Fernet-Verschlüsselung mit '
                                    'ROUTER_MASTER_KEY',
                                    'Circuit Breaker zur automatischen Fehlerisolation mit Geo-Proxy-Unterstützung'],
                          'ja': [   '4つのルーティングエンジン：ダイレクト、優先度フォールバック（入れ子対応）、モデル融合、およびJev System One意思決定',
                                    'OpenAI API (/v1/chat/completions) および Ollama (/api/tags) との完全互換',
                                    '強固なセキュリティ：ROUTER_MASTER_KEY による AES-128-CBC 暗号化',
                                    'サーキットブレーカーによる障害自動隔離とジオプロキシ連携'],
                          'pt': [   '4 motores de roteamento: Direto, Fallback prioritário (aninhado), Fusão de '
                                    'modelos e Decisões Jev System One',
                                    'Compatibilidade total com OpenAI API (/v1/chat/completions) e Ollama (/api/tags)',
                                    'Segurança avançada: criptografia AES-128-CBC Fernet usando ROUTER_MASTER_KEY',
                                    'Isolamento automático de falhas com Circuit Breaker e suporte a proxies'],
                          'ar': [   '4 محركات توجيه: المباشر، والاحتياطي ذو الأولوية (المتداخل)، ودمج النماذج، وقرارات '
                                    'Jev System One السريعة',
                                    'توافق فوري مع واجهات OpenAI (/v1/chat/completions) وOllama (/api/tags)',
                                    'تشفير عالي الأمان: AES-128-CBC Fernet محمي بمفتاح ROUTER_MASTER_KEY',
                                    'قاطع الدائرة الكهربائية (Circuit Breaker) لعزل الأعطال مع دعم البروكسي الجغرافي'],
                          'hi': [   '4 रूटिंग इंजन: डायरेक्ट, प्रायोरिटी फॉलबैक (नेस्टेड), मॉडल फ्यूजन और जेव (Jev) '
                                    'सिस्टम वन डिसीजन',
                                    'ओपनएआई एपीआई (/v1/chat/completions) और ओलामा (/api/tags) के साथ पूर्ण '
                                    'कम्पैटिबिलिटी',
                                    'एंटरप्राइज सुरक्षा: ROUTER_MASTER_KEY द्वारा प्रबंधित AES-128-CBC फ़र्नेट '
                                    'एन्क्रिप्शन',
                                    'सर्किट ब्रेकर द्वारा स्वचालित विफलता अलगाव और प्रॉक्सी कनेक्टिविटी'],
                          'bn': [   '৪টি রাউটিং ইঞ্জিন: ডাইরেক্ট, প্রায়োরিটি ফলব্যাক (নেস্টেড), মডেল ফিউশন এবং জেভ '
                                    '(Jev) সিস্টেম ওয়ান ডিসিশন',
                                    'OpenAI API (/v1/chat/completions) এবং Ollama (/api/tags) এর সাথে সম্পূর্ণ '
                                    'সামঞ্জস্য',
                                    'নিরাপদ কী স্টোরেজ: ROUTER_MASTER_KEY চালিত AES-128-CBC ফার্নেট এনক্রিপশন',
                                    'সার্কিট ব্রেকার স্বয়ংক্রিয় ত্রুটি বিচ্ছিন্নকরণ এবং প্রক্সি ইন্টিগ্রেশন']},
        'subsections': [   {   'titles': {   'en': 'Routing Modes Comparison',
                                             'ru': 'Сравнение движков маршрутизации',
                                             'uk': 'Порівняння рушіїв маршрутизації',
                                             'be': 'Параўнанне рухавікоў маршрутызацыі',
                                             'zh': '路由模式特性对比',
                                             'es': 'Comparación de modos de enrutamiento',
                                             'fr': 'Comparaison des modes de routage',
                                             'de': 'Vergleich der Routing-Modi',
                                             'ja': 'ルーティングモードの比較',
                                             'pt': 'Comparação dos Modos de Roteamento',
                                             'ar': 'مقارنة أوضاع التوجيه',
                                             'hi': 'रूटिंग मोड की तुलना',
                                             'bn': 'রাউটিং মোডের তুলনা'},
                               'table': {   'headers': [   'Mode / Мод',
                                                           'Slug Prefix',
                                                           'Target / Цель',
                                                           'Strategy / Стратегия',
                                                           'Latency / Задержка'],
                                            'rows': [   [   'Direct Routing',
                                                            'none or provider/',
                                                            'Single Provider Model',
                                                            'Round-robin across healthy credentials',
                                                            'Lowest (single hop)'],
                                                        [   'Priority Fallback',
                                                            'route/*',
                                                            'Ordered Chain of Models/Profiles',
                                                            'Sequential try-next on 429 / 5xx error',
                                                            'Fast on 1st, robust on failure'],
                                                        [   'Model Fusion',
                                                            'fusion/*',
                                                            'Multi-Model Ensemble + Judge',
                                                            'Parallel execution with consensus synthesis',
                                                            'Higher (multi-model + judge deliberation)'],
                                                        [   'Jev System One',
                                                            'direct, /v1/systemone, jev/*',
                                                            'Discrete Decision Primitives',
                                                            'Fast rubric & choice evaluation with calibrated '
                                                            'probabilities',
                                                            'Ultra-low / Instant']]}}]},
    {   'id': 'quickstart',
        'group': 'intro',
        'badge': '2-Minute Setup',
        'titles': {   'en': 'Quickstart Guide',
                      'ru': 'Быстрый старт',
                      'uk': 'Швидкий старт',
                      'be': 'Хуткі старт',
                      'zh': '快速上手指南',
                      'es': 'Guía de inicio rápido',
                      'fr': 'Démarrage rapide',
                      'de': 'Schnellstart-Anleitung',
                      'ja': 'クイックスタート',
                      'pt': 'Início Rápido',
                      'ar': 'دليل البدء السريع',
                      'hi': 'क्विकस्टार्ट गाइड',
                      'bn': 'কুইকস্টার্ট গাইড'},
        'descriptions': {   'en': 'Connect any OpenAI-compatible library, cURL, or local Ollama client to MyAIrouter '
                                  'gateway in seconds.',
                            'ru': 'Подключение любой библиотеки OpenAI SDK, cURL или Ollama-клиента к шлюзу MyAIrouter '
                                  'за считанные секунды.',
                            'uk': 'Підключення будь-якої бібліотеки OpenAI SDK, cURL або Ollama-клієнта до шлюзу '
                                  'MyAIrouter за лічені секунди.',
                            'be': 'Падключэнне любой бібліятэкі OpenAI SDK, cURL або Ollama-кліента да шлюза '
                                  'MyAIrouter за лічаныя секунды.',
                            'zh': '秒级将任何 OpenAI SDK、cURL 脚本或本地 Ollama 客户端连接至 MyAIrouter 智能网关。',
                            'es': 'Conecte cualquier librería OpenAI, cURL o cliente Ollama a la pasarela MyAIrouter '
                                  'en segundos.',
                            'fr': "Connectez n'importe quelle bibliothèque OpenAI, cURL ou client Ollama à MyAIrouter "
                                  'en quelques secondes.',
                            'de': 'Verbinden Sie jedes OpenAI-SDK, cURL oder lokale Ollama-Clients in Sekundenschnelle '
                                  'mit MyAIrouter.',
                            'ja': 'OpenAI SDK、cURL、またはOllamaクライアントをわずか数秒でMyAIrouterに接続。',
                            'pt': 'Conecte qualquer biblioteca OpenAI, cURL ou cliente Ollama ao gateway MyAIrouter em '
                                  'segundos.',
                            'ar': 'اربط أي مكتبة متوافقة مع OpenAI أو cURL أو عميل Ollama ببوابة MyAIrouter في ثوانٍ.',
                            'hi': 'कुछ ही सेकंड में किसी भी ओपनएआई लाइब्रेरी, cURL, या ओलामा क्लाइंट को MyAIrouter से '
                                  'कनेक्ट करें।',
                            'bn': 'কয়েক সেকেন্ডের মধ্যে যেকোনো ওপেনএআই লাইব্রেরি, cURL, বা ওলামা ক্লায়েন্টকে '
                                  'MyAIrouter এর সাথে যুক্ত করুন।'},
        'subsections': [   {   'titles': {   'en': '1. cURL Quickstart',
                                             'ru': '1. Быстрый вызов через cURL',
                                             'uk': '1. Швидкий виклик через cURL',
                                             'be': '1. Хуткі выклік праз cURL',
                                             'zh': '1. cURL 命令行调用',
                                             'es': '1. Inicio rápido con cURL',
                                             'fr': '1. Appel rapide avec cURL',
                                             'de': '1. cURL Schnellstart',
                                             'ja': '1. cURL クイックスタート',
                                             'pt': '1. Início rápido com cURL',
                                             'ar': '1. البدء السريع عبر cURL',
                                             'hi': '1. cURL क्विकस्टार्ट',
                                             'bn': '1. cURL কুইকস্টার্ট'},
                               'code': {   'title': 'cURL Chat Completion',
                                           'lang': 'bash',
                                           'content': 'curl http://localhost:8000/v1/chat/completions \\\n'
                                                      '  -H "Content-Type: application/json" \\\n'
                                                      '  -H "Authorization: Bearer sk-router-YOUR_KEY" \\\n'
                                                      "  -d '{\n"
                                                      '    "model": "gemini-2.5-flash",\n'
                                                      '    "messages": [{"role": "user", "content": "Explain quantum '
                                                      'computing in one sentence."}],\n'
                                                      '    "temperature": 0.7\n'
                                                      "  }'"}},
                           {   'titles': {   'en': '2. Python OpenAI SDK',
                                             'ru': '2. Python SDK (OpenAI)',
                                             'uk': '2. Python SDK (OpenAI)',
                                             'be': '2. Python SDK (OpenAI)',
                                             'zh': '2. Python OpenAI 官方库',
                                             'es': '2. Python OpenAI SDK',
                                             'fr': '2. SDK Python OpenAI',
                                             'de': '2. Python OpenAI SDK',
                                             'ja': '2. Python OpenAI SDK',
                                             'pt': '2. Python OpenAI SDK',
                                             'ar': '2. مكتبة Python OpenAI',
                                             'hi': '2. पायथन ओपनएआई एसडीके',
                                             'bn': '2. পাইথন ওপেনএআই এসডিকে'},
                               'code': {   'title': 'Python Client (Streaming)',
                                           'lang': 'python',
                                           'content': 'from openai import OpenAI\n'
                                                      '\n'
                                                      'client = OpenAI(\n'
                                                      '    base_url="http://localhost:8000/v1",\n'
                                                      '    api_key="sk-router-YOUR_KEY"\n'
                                                      ')\n'
                                                      '\n'
                                                      'response = client.chat.completions.create(\n'
                                                      '    model="route/coding-fallback",\n'
                                                      '    messages=[\n'
                                                      '        {"role": "system", "content": "You are an expert '
                                                      'engineer."},\n'
                                                      '        {"role": "user", "content": "Write an async Python '
                                                      'client for SSE."}\n'
                                                      '    ],\n'
                                                      '    temperature=0.2,\n'
                                                      '    stream=True\n'
                                                      ')\n'
                                                      '\n'
                                                      'for chunk in response:\n'
                                                      '    if chunk.choices and chunk.choices[0].delta.content:\n'
                                                      '        print(chunk.choices[0].delta.content, end="", '
                                                      'flush=True)'}},
                           {   'titles': {   'en': '3. Node.js / TypeScript',
                                             'ru': '3. Node.js / TypeScript',
                                             'uk': '3. Node.js / TypeScript',
                                             'be': '3. Node.js / TypeScript',
                                             'zh': '3. Node.js / TypeScript',
                                             'es': '3. Node.js / TypeScript',
                                             'fr': '3. Node.js / TypeScript',
                                             'de': '3. Node.js / TypeScript',
                                             'ja': '3. Node.js / TypeScript',
                                             'pt': '3. Node.js / TypeScript',
                                             'ar': '3. Node.js / TypeScript',
                                             'hi': '3. Node.js / TypeScript',
                                             'bn': '3. Node.js / TypeScript'},
                               'code': {   'title': 'TypeScript OpenAI Client',
                                           'lang': 'typescript',
                                           'content': 'import OpenAI from "openai";\n'
                                                      '\n'
                                                      'const client = new OpenAI({\n'
                                                      '  baseURL: "http://localhost:8000/v1",\n'
                                                      '  apiKey: "sk-router-YOUR_KEY",\n'
                                                      '});\n'
                                                      '\n'
                                                      'async function main() {\n'
                                                      '  const completion = await client.chat.completions.create({\n'
                                                      '    model: "fusion/code-jury",\n'
                                                      '    messages: [{ role: "user", content: "Compare Rust and Go '
                                                      'for API gateways." }],\n'
                                                      '  });\n'
                                                      '  console.log(completion.choices[0].message.content);\n'
                                                      '}\n'
                                                      '\n'
                                                      'main();'}}]},
    {   'id': 'models',
        'group': 'models',
        'badge': 'Addressing',
        'titles': {   'en': 'Model Addressing & Resolution',
                      'ru': 'Адресация и выбор моделей',
                      'uk': 'Адресація та вибір моделей',
                      'be': 'Адрасацыя і выбар мадэляў',
                      'zh': '模型寻址与解析机制',
                      'es': 'Direccionamiento de modelos',
                      'fr': 'Adressage et résolution des modèles',
                      'de': 'Modell-Adressierung & Auflösung',
                      'ja': 'モデルのアドレッシングと解決',
                      'pt': 'Endereçamento e Resolução de Modelos',
                      'ar': 'عنونة النماذج والتحليل',
                      'hi': 'मॉडल एड्रेसिंग और रेजोल्यूशन',
                      'bn': 'মডেল অ্যাড্রেসিং ও রেজোলিউশন'},
        'descriptions': {   'en': 'Flexible multi-mode model addressing: canonical slugs, provider-qualified '
                                  'identifiers, priority fallback routes, and fusion juries.',
                            'ru': 'Гибкая многоуровневая адресация моделей: канонические slug-имена, прямые '
                                  'провайдерные пути, цепочки fallback и ансамбли fusion.',
                            'uk': 'Гнучка багаторівнева адресація моделей: канонічні slug-імена, прямі провайдерні '
                                  'шляхи, ланцюжки fallback та ансамблі fusion.',
                            'be': 'Гнуткая шматузроўневая адрасацыя мадэляў: кананічныя slug-імёны, прамыя шляхі '
                                  'правайдэраў, ланцужкі fallback і ансамблі fusion.',
                            'zh': '多层次模型寻址方案：标准规范名、指定提供商前缀、回退路由别名与融合评审团标识。',
                            'es': 'Direccionamiento flexible multinivel: slugs canónicos, identificadores calificados '
                                  'por proveedor, rutas de fallback y jurados de fusión.',
                            'fr': 'Adressage flexible à plusieurs niveaux : slugs canoniques, identifiants qualifiés '
                                  'par fournisseur, routes de repli et jurys de fusion.',
                            'de': 'Flexibles mehrstufiges Modell-Adressierungssystem: kanonische Slugs, '
                                  'Provider-Präfixe, Fallback-Routen und Fusion-Jurys.',
                            'ja': '柔軟なマルチモードアドレッシング：正規スラッグ、プロバイダー修飾子、フォールバックルート、フュージョン審査団。',
                            'pt': 'Endereçamento flexível em vários modos: slugs canônicos, identificadores por '
                                  'provedor, rotas de fallback e júris de fusão.',
                            'ar': 'عنونة مرنة متعددة الأنماط: المعرفات القياسية، وتحديد المزود، ومسارات الاحتياط، '
                                  'ولجان التحكيم المندمجة.',
                            'hi': 'मल्टी-मोड मॉडल एड्रेसिंग: कैनोनिकल स्लग, प्रोवाइडर-क्वालिफाइड पाथ, फॉलबैक रूट्स और '
                                  'फ्यूजन ज्यूरी।',
                            'bn': 'মাল্টি-মোড মডেল অ্যাড্রেসিং: ক্যানোনিকাল স্ল্যাগ, প্রোভাইডার-কোয়ালিফাইড পাথ, '
                                  'ফলব্যাক রুট এবং ফিউশন জুরি।'},
        'subsections': [   {   'titles': {   'en': 'Addressing Hierarchy',
                                             'ru': 'Иерархия адресации моделей',
                                             'uk': 'Ієрархія адресації моделей',
                                             'be': 'Іерархія адрасацыі мадэляў',
                                             'zh': '寻址层级规范',
                                             'es': 'Jerarquía de direccionamiento',
                                             'fr': "Hiérarchie d'adressage",
                                             'de': 'Adressierungshierarchie',
                                             'ja': 'アドレッシングの階層',
                                             'pt': 'Hierarquia de Endereçamento',
                                             'ar': 'تسلسل العنونة',
                                             'hi': 'एड्रेसिंग पदानुक्रम',
                                             'bn': 'অ্যাড্রেসিং হায়ারার্কি'},
                               'table': {   'headers': [   'Addressing Type / Тип',
                                                           'Example Request / Пример',
                                                           'Routing Behavior / Поведение'],
                                            'rows': [   [   'Canonical Slug',
                                                            'gemini-2.5-flash',
                                                            'Resolves to highest priority provider with healthy '
                                                            'credentials'],
                                                        [   'Provider-Qualified',
                                                            'openrouter/meta-llama/llama-3.3-70b',
                                                            'Forces execution strictly via specified upstream '
                                                            'provider'],
                                                        [   'Route Profile',
                                                            'route/coding-fallback',
                                                            'Executes multi-tier priority fallback chain on 429/5xx '
                                                            'errors'],
                                                        [   'Fusion Profile',
                                                            'fusion/code-jury',
                                                            'Parallel multi-model execution synthesized by a Judge '
                                                            'LLM']]}},
                           {   'titles': {   'en': 'Model Types: OpenAI Compatible vs ⚡ Jev (System One)',
                                             'ru': 'Типы моделей: OpenAI-совместимые vs ⚡ Jev (System One)',
                                             'uk': 'Типи моделей: OpenAI-сумісні vs ⚡ Jev (System One)',
                                             'be': 'Тыпы мадэляў: OpenAI-сумяшчальныя vs ⚡ Jev (System One)',
                                             'zh': '模型执行类型：OpenAI 兼容模式 vs ⚡ Jev 快决策',
                                             'es': 'Tipos de modelos: Compatible con OpenAI vs ⚡ Jev (System One)',
                                             'fr': 'Types de modèles : Compatible OpenAI vs ⚡ Jev (System One)',
                                             'de': 'Modelltypen: OpenAI-kompatibel vs. ⚡ Jev (System One)',
                                             'ja': 'モデルタイプ：OpenAI互換 vs ⚡ Jev（System One意思決定）',
                                             'pt': 'Tipos de Modelos: Compatível com OpenAI vs ⚡ Jev (System One)',
                                             'ar': 'أنواع النماذج: متوافقة مع OpenAI مقابل ⚡ Jev (System One)',
                                             'hi': 'मॉडल प्रकार: ओपनएआई (OpenAI) संगत बनाम ⚡ जेव (Jev System One)',
                                             'bn': 'মডেলের প্রকারভেদ: ওপেনএআই সামঞ্জস্যপূর্ণ বনাম ⚡ জেভ (Jev System '
                                                   'One)'},
                               'descriptions': {   'en': 'MyAIrouter allows configuring the execution mode for every '
                                                         'model in the catalog: default OpenAI compatible or '
                                                         'high-speed Jev System One decision engine.',
                                                   'ru': 'MyAIrouter позволяет настраивать режим работы для каждой '
                                                         'модели в каталоге: стандартный OpenAI-совместимый по '
                                                         'умолчанию или высокоскоростной движок решений Jev System '
                                                         'One.',
                                                   'uk': 'MyAIrouter дозволяє налаштовувати режим роботи для кожної '
                                                         'моделі в каталозі: стандартний OpenAI-сумісний за '
                                                         'замовчуванням або високошвидкісний рушій рішень Jev System '
                                                         'One.',
                                                   'be': 'MyAIrouter дазваляе наладжваць рэжым працы для кожнай мадэлі '
                                                         'ў каталогу: стандартны OpenAI-сумяшчальны па змаўчанні або '
                                                         'высакахуткасны рухавік рашэнняў Jev System One.',
                                                   'zh': 'MyAIrouter 支持为模型目录中的每一款模型独立配置执行模式：默认的 OpenAI 兼容模式或高并发 Jev '
                                                         'System One 快速决策引擎。',
                                                   'es': 'MyAIrouter permite configurar el modo de ejecución para cada '
                                                         'modelo del catálogo: compatible con OpenAI por defecto o '
                                                         'motor de decisiones rápido Jev System One.',
                                                   'fr': "MyAIrouter permet de configurer le mode d'exécution de "
                                                         'chaque modèle du catalogue : compatible OpenAI par défaut ou '
                                                         'moteur de décision rapide Jev System One.',
                                                   'de': 'MyAIrouter ermöglicht die Konfiguration des Ausführungsmodus '
                                                         'für jedes Modell im Katalog: standardmäßig OpenAI-kompatibel '
                                                         'oder als schnelle Jev System One Entscheidungs-Engine.',
                                                   'ja': 'MyAIrouter ではカタログ内の各モデルに対して、デフォルトのOpenAI互換モードまたは高速なJev '
                                                         'System One意思決定エンジンモードを設定できます。',
                                                   'pt': 'O MyAIrouter permite configurar o modo de execução de cada '
                                                         'modelo no catálogo: padrão compatível com OpenAI ou motor de '
                                                         'decisões rápidas Jev System One.',
                                                   'ar': 'يتيح MyAIrouter تحديد وضع التشغيل لكل نموذج في الدليل: الوضع '
                                                         'الافتراضي المتوافق مع OpenAI أو محرك اتخاذ القرارات السريع '
                                                         'Jev System One.',
                                                   'hi': 'MyAIrouter कैटलॉग में प्रत्येक मॉडल के लिए निष्पादन मोड '
                                                         'कॉन्फ़िगर करने की अनुमति देता है: डिफ़ॉल्ट ओपनएआई कम्पैटिबल '
                                                         'या हाई-स्पीड जेव (Jev) सिस्टम वन डिसीजन इंजन।',
                                                   'bn': 'MyAIrouter ক্যাটালগের প্রতিটি মডেলের জন্য এক্সিকিউশন মোড '
                                                         'কনফিগার করতে দেয়: ডিফল্ট ওপেনএআই সামঞ্জস্যপূর্ণ বা '
                                                         'উচ্চ-গতির জেভ (Jev) সিস্টেম ওয়ান ডিসিশন ইঞ্জিন।'},
                               'bullets': {   'en': [   "Default Model Type ('openai'): Standard conversational "
                                                        'generation, reasoning tokens, and streaming across OpenAI, '
                                                        'Gemini, Anthropic, Ollama, etc.',
                                                        "Jev Mode ('jev'): Fast System One decision evaluation against "
                                                        'discrete criteria (choice, score, noul) with calibrated '
                                                        'probabilities.',
                                                        'Native Execution vs Emulation: Native providers (drex.nace, '
                                                        'experientiallabs) receive zero-overhead direct payloads; '
                                                        'general LLMs (GPT, Claude, Gemini, Groq) run via automatic '
                                                        'structured JSON emulation.',
                                                        "Catalog Management: Filter models with quick chips ('All "
                                                        "Types', 'OpenAI', '⚡ Jev'), edit single models, or use the "
                                                        "batch modal ('Set Model Type') in the UI.",
                                                        "API Exposure: The model_type field ('openai' | 'jev') is "
                                                        'exposed in GET /v1/models and GET /v1/models/{id}.'],
                                              'ru': [   "Тип модели по умолчанию ('openai'): Стандартная генерация "
                                                        'текста, CoT-рассуждения и стриминг (OpenAI, Gemini, '
                                                        'Anthropic, Ollama и др.).',
                                                        "Режим Jev ('jev'): Быстрые решения System One по дискретным "
                                                        'рубрикам (choice, score, noul) с калиброванными '
                                                        'вероятностями.',
                                                        'Нативный запуск vs Эмуляция: Нативные провайдеры (drex.nace, '
                                                        'experientiallabs) получают прямой запрос без задержек; '
                                                        'универсальные LLM (GPT, Claude, Gemini, Groq) эмулируются '
                                                        'через структурированный JSON.',
                                                        "Управление каталогом: Быстрые фильтры ('Все типы', 'OpenAI', "
                                                        "'⚡ Jev'), одиночное редактирование и массовое обновление "
                                                        "('Set Model Type') в интерфейсе.",
                                                        "Поддержка API: Поле model_type ('openai' | 'jev') "
                                                        'возвращается в GET /v1/models и GET /v1/models/{id}.'],
                                              'uk': [   "Тип моделі за замовчуванням ('openai'): Стандартна генерація "
                                                        'тексту, міркування CoT та стрімінг (OpenAI, Gemini, '
                                                        'Anthropic, Ollama тощо).',
                                                        "Режим Jev ('jev'): Швидкі рішення System One за дискретними "
                                                        'критеріями (choice, score, noul) із каліброваними '
                                                        'ймовірностями.',
                                                        'Нативний запуск vs Емуляція: Нативні провайдери (drex.nace, '
                                                        'experientiallabs) отримують прямий запит без затримок; '
                                                        'універсальні LLM (GPT, Claude, Gemini, Groq) емулюються через '
                                                        'структурований JSON.',
                                                        "Керування каталогом: Швидкі фільтри ('Всі типи', 'OpenAI', '⚡ "
                                                        "Jev'), редагування моделі та масове оновлення ('Set Model "
                                                        "Type') в інтерфейсі.",
                                                        "Підтримка API: Поле model_type ('openai' | 'jev') "
                                                        'повертається в GET /v1/models та GET /v1/models/{id}.'],
                                              'be': [   "Тып мадэлі па змаўчанні ('openai'): Стандартная генерацыя "
                                                        'тэксту, развагі CoT і стрымінг (OpenAI, Gemini, Anthropic, '
                                                        'Ollama і інш.).',
                                                        "Рэжым Jev ('jev'): Хуткія рашэнні System One па дыскрэтных "
                                                        'крытэрыях (choice, score, noul) з калібраванымі '
                                                        'верагоднасцямі.',
                                                        'Натыўны запуск vs Эмуляцыя: Натыўныя правайдэры (drex.nace, '
                                                        'experientiallabs) атрымліваюць прамы запыт без затрымак; '
                                                        'універсальныя LLM (GPT, Claude, Gemini, Groq) эмулююцца праз '
                                                        'структураваны JSON.',
                                                        "Кіраванне каталогам: Хуткія фільтры ('Усе тыпы', 'OpenAI', '⚡ "
                                                        "Jev'), рэдагаванне мадэлі і масавае абнаўленне ('Set Model "
                                                        "Type') у інтэрфейсе.",
                                                        "Падтрымка API: Поле model_type ('openai' | 'jev') вяртаецца ў "
                                                        'GET /v1/models і GET /v1/models/{id}.'],
                                              'zh': [   "默认模型类型 ('openai')：支持标准的多轮对话、思维链推理与流式响应（涵盖 "
                                                        'OpenAI、Gemini、Anthropic、Ollama 等）。',
                                                        "Jev 决策模式 ('jev')：专用于 System One 快速离散评估（choice 选项、score "
                                                        '评分、noul 判定）并输出校准概率分布。',
                                                        '原生执行与智能模拟：原生 Jev '
                                                        '服务商（drex.nace、experientiallabs）享受零延迟直传；通用大模型（GPT、Claude、Gemini、Groq）自动通过结构化 '
                                                        'JSON 提示词无缝模拟。',
                                                        "目录快捷管理：支持筛选标签（'All Types'、'OpenAI'、'⚡ "
                                                        "Jev'）、单模型弹窗编辑与批量批量切换（'Set Model Type'）。",
                                                        'API 字段支持：GET /v1/models 与 GET /v1/models/{id} 接口均完整返回 '
                                                        'model_type 属性。'],
                                              'es': [   "Tipo predeterminado ('openai'): Generación de texto "
                                                        'conversacional estándar, tokens de razonamiento y streaming '
                                                        '(OpenAI, Gemini, Anthropic, Ollama, etc.).',
                                                        "Modo Jev ('jev'): Evaluación rápida de decisiones System One "
                                                        'frente a criterios discretos (choice, score, noul) con '
                                                        'probabilidades calibradas.',
                                                        'Ejecución nativa vs Emulación: Los proveedores nativos '
                                                        '(drex.nace, experientiallabs) reciben solicitudes directas '
                                                        'sin retardo; los LLM generales (GPT, Claude, Gemini, Groq) se '
                                                        'emulan mediante JSON estructurado.',
                                                        "Gestión del catálogo: Filtros rápidos ('All Types', 'OpenAI', "
                                                        "'⚡ Jev'), edición individual y actualización masiva ('Set "
                                                        "Model Type') en la interfaz.",
                                                        "Soporte API: El campo model_type ('openai' | 'jev') se "
                                                        'incluye en GET /v1/models y GET /v1/models/{id}.'],
                                              'fr': [   "Type par défaut ('openai') : Génération de texte standard, "
                                                        'jetons de raisonnement et streaming (OpenAI, Gemini, '
                                                        'Anthropic, Ollama, etc.).',
                                                        "Mode Jev ('jev') : Évaluation rapide de décisions System One "
                                                        'selon des rubriques discrètes (choice, score, noul) avec '
                                                        'probabilités calibrées.',
                                                        'Exécution native vs Émulation : Les fournisseurs natifs '
                                                        '(drex.nace, experientiallabs) reçoivent des requêtes directes '
                                                        'sans surcoût ; les LLM généraux (GPT, Claude, Gemini, Groq) '
                                                        'sont émulés via JSON structuré.',
                                                        "Gestion du catalogue : Filtres rapides ('All Types', "
                                                        "'OpenAI', '⚡ Jev'), édition unitaire et mise à jour groupée "
                                                        "('Set Model Type') dans l'interface.",
                                                        "Support API : Le champ model_type ('openai' | 'jev') est "
                                                        'retourné par GET /v1/models et GET /v1/models/{id}.'],
                                              'de': [   "Standard-Modelltyp ('openai'): Konventionelle "
                                                        'Textgenerierung, Reasoning-Tokens und Streaming für OpenAI, '
                                                        'Gemini, Anthropic, Ollama usw.',
                                                        "Jev-Modus ('jev'): Schnelle System One Entscheidungsbewertung "
                                                        'anhand diskreter Kriterien (choice, score, noul) mit '
                                                        'kalibrierten Wahrscheinlichkeiten.',
                                                        'Native Ausführung vs. Emulation: Native Provider (drex.nace, '
                                                        'experientiallabs) erhalten direkte Payloads ohne Latenz; '
                                                        'Standard-LLMs (GPT, Claude, Gemini, Groq) werden über '
                                                        'strukturiertes JSON emuliert.',
                                                        "Katalogverwaltung: Filter-Chips ('All Types', 'OpenAI', '⚡ "
                                                        "Jev'), Einzelbearbeitung und Stapelaktualisierung ('Set Model "
                                                        "Type') im Webinterface.",
                                                        "API-Unterstützung: Das Feld model_type ('openai' | 'jev') "
                                                        'wird in GET /v1/models und GET /v1/models/{id} '
                                                        'zurückgegeben.'],
                                              'ja': [   "デフォルトモデルタイプ（'openai'）：通常のテキスト対話生成、推論トークン、ストリーミングに対応（OpenAI、Gemini、Anthropic、Ollama等）。",
                                                        "Jevモード（'jev'）：離散ルーブリック（choice、score、noul）に対する校正済み確率を算出する高速System "
                                                        'One意思決定エンジン。',
                                                        'ネイティブ実行 vs '
                                                        'エミュレーション：ネイティブ事業者（drex.nace、experientiallabs）には遅延ゼロで直結。汎用LLM（GPT、Claude、Gemini、Groq）は構造化JSONプロンプトで自動エミュレート。',
                                                        "カタログ管理機能：クイックフィルター（'All Types'、'OpenAI'、'⚡ "
                                                        "Jev'）、個別編集ダイアログ、一括変更モーダル（'Set Model Type'）を搭載。",
                                                        'APIレスポンス：GET /v1/models および GET /v1/models/{id} で '
                                                        "model_type（'openai' | 'jev'）を返却。"],
                                              'pt': [   "Tipo padrão ('openai'): Geração de texto conversacional "
                                                        'padrão, tokens de raciocínio e streaming (OpenAI, Gemini, '
                                                        'Anthropic, Ollama, etc.).',
                                                        "Modo Jev ('jev'): Avaliação rápida de decisões System One "
                                                        'contra critérios discretos (choice, score, noul) com '
                                                        'probabilidades calibradas.',
                                                        'Execução nativa vs Emulação: Provedores nativos (drex.nace, '
                                                        'experientiallabs) recebem requisições diretas sem overhead; '
                                                        'LLMs gerais (GPT, Claude, Gemini, Groq) são emulados via JSON '
                                                        'estruturado.',
                                                        "Gerenciamento do catálogo: Filtros rápidos ('All Types', "
                                                        "'OpenAI', '⚡ Jev'), edição individual e atualização em lote "
                                                        "('Set Model Type') na interface.",
                                                        "Suporte na API: O campo model_type ('openai' | 'jev') é "
                                                        'retornado em GET /v1/models e GET /v1/models/{id}.'],
                                              'ar': [   "نوع النموذج الافتراضي ('openai'): التوليد النصي التحاوري "
                                                        'القياسي، وتفكير CoT، والبث المباشر (OpenAI, Gemini, '
                                                        'Anthropic, Ollama وغيرها).',
                                                        "وضع Jev ('jev'): تقييم سريع للقرارات (System One) بناءً على "
                                                        'معايير محددة (choice, score, noul) مع احتمالات معايرة دقيقة.',
                                                        'التنفيذ الأصلي مقابل المحاكاة: المزودون الأصليون (drex.nace, '
                                                        'experientiallabs) يتلقون الحمولات مباشرة دون تأخير؛ النماذج '
                                                        'العامة (GPT, Claude, Gemini, Groq) تُحاكى تلقائياً عبر JSON '
                                                        'المنظم.',
                                                        "إدارة الدليل: تصفية سريعة بالوسوم ('All Types', 'OpenAI', '⚡ "
                                                        "Jev')، وتعديل فردي، وتحديث جماعي ('Set Model Type') في واجهة "
                                                        'الويب.',
                                                        "واجهة API: يُرجع حقل model_type ('openai' | 'jev') في طلبات "
                                                        'GET /v1/models وGET /v1/models/{id}.'],
                                              'hi': [   "डिफ़ॉल्ट मॉडल प्रकार ('openai'): मानक टेक्स्ट जनरेशन, "
                                                        'रीज़निंग टोकन और स्ट्रीमिंग (OpenAI, Gemini, Anthropic, '
                                                        'Ollama आदि)।',
                                                        "जेव मोड ('jev'): कैलिब्रेटेड प्रायिकताओं के साथ असतत मानदंडों "
                                                        '(choice, score, noul) पर त्वरित सिस्टम वन निर्णय मूल्यांकन।',
                                                        'नेटिव बनाम एमुलेशन: नेटिव प्रदाताओं (drex.nace, '
                                                        'experientiallabs) को शून्य विलंबता के साथ सीधे पेलोड मिलते '
                                                        'हैं; सामान्य LLM (GPT, Claude, Gemini, Groq) स्वचालित संरचित '
                                                        'JSON द्वारा एमुलेट होते हैं।',
                                                        "कैटलॉग प्रबंधन: क्विक फिल्टर ('All Types', 'OpenAI', '⚡ "
                                                        "Jev'), एकल मॉडल संपादन, और वेब यूआई में बैच अपडेट ('Set Model "
                                                        "Type')।",
                                                        "एपीआई समर्थन: model_type फ़ील्ड ('openai' | 'jev') GET "
                                                        '/v1/models और GET /v1/models/{id} में लौटाया जाता है।'],
                                              'bn': [   "ডিফল্ট মডেলের ধরন ('openai'): স্ট্যান্ডার্ড টেক্সট জেনারেশন, "
                                                        'রিজনিং টোকেন এবং স্ট্রিমিং (OpenAI, Gemini, Anthropic, Ollama '
                                                        'ইত্যাদি)।',
                                                        "জেভ মোড ('jev'): ক্যালিব্রেটেড সম্ভাব্যতা সহ ডিসক্রিট "
                                                        'মানদণ্ডের (choice, score, noul) উপর ভিত্তি করে দ্রুত সিস্টেম '
                                                        'ওয়ান সিদ্ধান্ত মূল্যায়ন।',
                                                        'নেটিভ বনাম এমুলেশন: নেটিভ প্রোভাইডার (drex.nace, '
                                                        'experientiallabs) সরাসরি জিরো-লেটেন্সি পেলোড পায়; সাধারণ '
                                                        'এলএলএম (GPT, Claude, Gemini, Groq) স্বয়ংক্রিয় কাঠামোগত JSON '
                                                        'এমুলেশনের মাধ্যমে চালিত হয়।',
                                                        "ক্যাটালগ পরিচালনা: দ্রুত ফিল্টার চিপস ('All Types', 'OpenAI', "
                                                        "'⚡ Jev'), একক মডেল সম্পাদনা এবং ওয়েব ইউআই-তে ব্যাচ আপডেট "
                                                        "('Set Model Type')।",
                                                        "এপিআই সমর্থন: model_type ফিল্ড ('openai' | 'jev') GET "
                                                        '/v1/models এবং GET /v1/models/{id}-এ ফেরত দেওয়া হয়।']}}]},
    {   'id': 'ollama',
        'group': 'models',
        'badge': 'Drop-in Ollama',
        'titles': {   'en': 'Ollama Compatibility API',
                      'ru': 'Совместимость с Ollama API',
                      'uk': 'Сумісність з Ollama API',
                      'be': 'Сумяшчальнасць з Ollama API',
                      'zh': 'Ollama 协议兼容接口',
                      'es': 'Compatibilidad con Ollama API',
                      'fr': 'Compatibilité API Ollama',
                      'de': 'Ollama API-Kompatibilität',
                      'ja': 'Ollama API 互換性',
                      'pt': 'Compatibilidade com Ollama API',
                      'ar': 'توافق واجهة برمجة تطبيقات Ollama',
                      'hi': 'ओलामा एपीआई कम्पैटिबिलिटी',
                      'bn': 'ওলামা এপিআই সামঞ্জস্য'},
        'descriptions': {   'en': 'Native drop-in support for Ollama CLI, Continue.dev, Open WebUI, and Obsidian '
                                  'Copilot without modifying client code.',
                            'ru': 'Нативная совместимость с утилитой Ollama CLI, плагинами Continue.dev, Open WebUI и '
                                  'Obsidian Copilot без изменения клиентского кода.',
                            'uk': 'Нативна сумісність з утилітою Ollama CLI, плагінами Continue.dev, Open WebUI та '
                                  'Obsidian Copilot без змін у клієнтському коді.',
                            'be': 'Натыўная сумяшчальнасць з утылітай Ollama CLI, плагінамі Continue.dev, Open WebUI і '
                                  'Obsidian Copilot без змен у кліенцкім кодзе.',
                            'zh': '原生兼容 Ollama CLI 命令行工具、Continue.dev、Open WebUI 和 Obsidian Copilot，无需修改现有客户端代码。',
                            'es': 'Compatibilidad nativa con Ollama CLI, Continue.dev, Open WebUI y Obsidian Copilot '
                                  'sin modificar código cliente.',
                            'fr': "Prise en charge native directe d'Ollama CLI, Continue.dev, Open WebUI et Obsidian "
                                  'Copilot sans modifier le code client.',
                            'de': 'Native Unterstützung für Ollama CLI, Continue.dev, Open WebUI und Obsidian Copilot '
                                  'ohne Anpassung des Client-Codes.',
                            'ja': 'クライアントコードを変更することなく、Ollama CLI、Continue.dev、Open WebUI、Obsidian Copilotをそのまま利用可能。',
                            'pt': 'Suporte nativo a Ollama CLI, Continue.dev, Open WebUI e Obsidian Copilot sem '
                                  'alterar código cliente.',
                            'ar': 'دعم أصلي مباشر لـ Ollama CLI وContinue.dev وOpen WebUI وObsidian Copilot دون تعديل '
                                  'كود العميل.',
                            'hi': 'क्लाइंट कोड बदले बिना ओलामा सीएलआई, Continue.dev, Open WebUI, और Obsidian Copilot '
                                  'के लिए नेटिव कम्पैटिबिलिटी।',
                            'bn': 'ক্লায়েন্ট কোড পরিবর্তন না করেই ওলামা সিএলআই, Continue.dev, Open WebUI, এবং '
                                  'Obsidian Copilot এর জন্য নেটিভ সমর্থন।'},
        'subsections': [   {   'titles': {   'en': 'Ollama CLI Integration',
                                             'ru': 'Использование через Ollama CLI',
                                             'uk': 'Використання через Ollama CLI',
                                             'be': 'Выкарыстанне праз Ollama CLI',
                                             'zh': '使用 Ollama CLI 访问网关',
                                             'es': 'Integración con Ollama CLI',
                                             'fr': 'Intégration Ollama CLI',
                                             'de': 'Ollama CLI Integration',
                                             'ja': 'Ollama CLI との統合',
                                             'pt': 'Integração com Ollama CLI',
                                             'ar': 'التكامل مع أداة سطر أوامر Ollama',
                                             'hi': 'ओलामा सीएलआई इंटीग्रेशन',
                                             'bn': 'ওলামা সিএলআই ইন্টিগ্রেশন'},
                               'code': {   'title': 'Bash / Terminal',
                                           'lang': 'bash',
                                           'content': '# Point your local Ollama client or IDE extension to '
                                                      'MyAIrouter\n'
                                                      'export OLLAMA_HOST=http://localhost:8000\n'
                                                      '\n'
                                                      '# View all registered models, route profiles, and fusion '
                                                      'profiles\n'
                                                      'ollama list\n'
                                                      '\n'
                                                      '# Execute queries directly through the OpenAI-compatible '
                                                      'gateway\n'
                                                      'ollama run gemini-2.5-flash "Write a Fibonacci function in '
                                                      'Go" '}},
                           {   'titles': {   'en': 'Supported Ollama Endpoints',
                                             'ru': 'Поддерживаемые эндпоинты Ollama',
                                             'uk': 'Підтримувані ендпоінти Ollama',
                                             'be': 'Падтрымліваемыя эндпоінты Ollama',
                                             'zh': '支持的 Ollama 接口列表',
                                             'es': 'Puntos finales compatibles de Ollama',
                                             'fr': 'Points de terminaison Ollama pris en charge',
                                             'de': 'Unterstützte Ollama-Endpunkte',
                                             'ja': 'サポートされる Ollama エンドポイント',
                                             'pt': 'Endpoints Ollama Suportados',
                                             'ar': 'نقاط نهاية Ollama المدعومة',
                                             'hi': 'समर्थित ओलामा एंडपॉइंट्स',
                                             'bn': 'সমর্থিত ওলামা এন্ডপয়েন্ট'},
                               'table': {   'headers': [   'Endpoint / Эндпоинт',
                                                           'Method / Метод',
                                                           'Description / Описание'],
                                            'rows': [   [   '/api/tags',
                                                            'GET',
                                                            'Returns list of all active models and route profiles '
                                                            'formatted as Ollama tags'],
                                                        [   '/api/show',
                                                            'POST',
                                                            'Returns detailed model parameters, template info, and '
                                                            'context length'],
                                                        [   '/api/version',
                                                            'GET',
                                                            'Returns gateway compatibility version info']]}}]},
    {   'id': 'intelligence-ratings',
        'group': 'models',
        'badge': 'Benchmarks',
        'titles': {   'en': 'Ratings & Benchmarks',
                      'ru': 'Рейтинги и бенчмарки',
                      'uk': 'Рейтинги та бенчмарки',
                      'be': 'Рэйтынгі і бенчмаркі',
                      'zh': '模型评测与基准数据',
                      'es': 'Calificaciones y Benchmarks',
                      'fr': "Notes et bancs d'essai",
                      'de': 'Bewertungen & Benchmarks',
                      'ja': 'レーティングとベンチマーク',
                      'pt': 'Classificações e Benchmarks',
                      'ar': 'التقييمات والمعايير القياسية',
                      'hi': 'रेटिंग्स और बेंचमार्क्स',
                      'bn': 'রেটিং এবং বেঞ্চমার্ক'},
        'descriptions': {   'en': 'Automated Artificial Analysis metrics: Quality Index (0-100), generation speed '
                                  '(tok/s), token pricing, and context limits.',
                            'ru': 'Автоматическая интеграция бенчмарков Artificial Analysis: индекс качества (0-100), '
                                  'скорость генерации (ток/с), стоимость и контекст.',
                            'uk': 'Автоматична інтеграція бенчмарків Artificial Analysis: індекс якості (0-100), '
                                  'швидкість генерації (ток/с), вартість та контекст.',
                            'be': 'Аўтаматычная інтэграцыя бенчмаркаў Artificial Analysis: індэкс якасці (0-100), '
                                  'хуткасць генерацыі (ток/с), кошт і кантэкст.',
                            'zh': '自动集成 Artificial Analysis 基准数据：综合质量评分 (0-100)、生成速度 (token/s)、百万 Token 价格与上下文窗口。',
                            'es': 'Métricas automáticas de Artificial Analysis: Índice de calidad (0-100), velocidad '
                                  'de generación, precios y ventana de contexto.',
                            'fr': "Métriques intégrées d'Artificial Analysis : Indice de qualité (0-100), vitesse de "
                                  'génération, tarification et contexte.',
                            'de': 'Automatische Artificial Analysis-Metriken: Qualitätsindex (0-100), '
                                  'Generierungsgeschwindigkeit, Preise und Kontextfenster.',
                            'ja': 'Artificial Analysisの自動ベンチマーク連携：品質スコア（0-100）、生成速度（tok/s）、料金、コンテキスト長。',
                            'pt': 'Métricas automáticas de Artificial Analysis: Índice de qualidade (0-100), '
                                  'velocidade de geração, preços e limite de contexto.',
                            'ar': 'مقاييس Artificial Analysis الآلية: مؤشر الجودة (0-100)، سرعة التوليد (رمز/ثانية)، '
                                  'التسعير، وحدود السياق.',
                            'hi': 'आर्टिफिशियल एनालिसिस बेंचमार्क इंटीग्रेशन: क्वालिटी इंडेक्स (0-100), जेनरेशन स्पीड '
                                  '(टोकन/सेकंड), मूल्य और संदर्भ विंडो।',
                            'bn': 'আর্টিফিশিয়াল অ্যানালাইসিস বেঞ্চমার্ক ইন্টিগ্রেশন: গুণমান সূচক (0-100), উৎপাদন গতি '
                                  '(টোকেন/সেকেন্ড), মূল্য এবং কনটেক্সট উইন্ডো।'},
        'subsections': [   {   'titles': {   'en': 'Benchmark Metrics',
                                             'ru': 'Ключевые показатели моделей',
                                             'uk': 'Ключові показники моделей',
                                             'be': 'Ключавыя паказчыкі мадэляў',
                                             'zh': '评测指标解析',
                                             'es': 'Métricas de Benchmark',
                                             'fr': "Indicateurs d'évaluation",
                                             'de': 'Benchmark-Metriken',
                                             'ja': 'ベンチマーク指標',
                                             'pt': 'Métricas de Benchmark',
                                             'ar': 'معايير القياس',
                                             'hi': 'बेंचमार्क मेट्रिक्स',
                                             'bn': 'বেঞ্চমার্ক মেট্রিক্স'},
                               'table': {   'headers': [   'Metric / Показатель',
                                                           'Range / Диапазон',
                                                           'Description / Значение'],
                                            'rows': [   [   'Quality Index',
                                                            '0 — 100',
                                                            'Composite intelligence index based on coding, math, '
                                                            'reasoning, and instruction following'],
                                                        [   'Output Speed',
                                                            '10 — 300+ tok/s',
                                                            'Median streaming completion velocity measured on real '
                                                            'workloads'],
                                                        [   'Context Window',
                                                            '4K — 2M+ tokens',
                                                            'Maximum active input context supported by the model '
                                                            'architecture'],
                                                        [   'Pricing (1M tokens)',
                                                            '$0.05 — $60.00',
                                                            'Estimated blended cost per million prompt and completion '
                                                            'tokens']]}}]},
    {   'id': 'model-limits',
        'group': 'models',
        'badge': 'Quotas & RPM',
        'titles': {   'en': 'API Limits & Quotas',
                      'ru': 'Лимиты API и квоты',
                      'uk': 'Ліміти API та квоти',
                      'be': 'Ліміты API і квоты',
                      'zh': 'API 速率限制与配额',
                      'es': 'Límites y cuotas de API',
                      'fr': "Limites et quotas d'API",
                      'de': 'API-Limits & Kontingente',
                      'ja': 'API 制限とクォータ',
                      'pt': 'Limites e Cotas de API',
                      'ar': 'حدود واجهة برمجة التطبيقات والحصص',
                      'hi': 'एपीआई सीमाएं और कोटा',
                      'bn': 'এপিআই সীমা এবং কোটা'},
        'descriptions': {   'en': 'Two-tier rate limiting: protect upstream accounts with per-credential RPM/TPM '
                                  'bounds while regulating client API key usage.',
                            'ru': 'Двухуровневое ограничение скорости: защита upstream-аккаунтов (RPM/TPM по ключам) и '
                                  'управление квотами клиентов шлюза.',
                            'uk': 'Дворівневе обмеження швидкості: захист upstream-акаунтів (RPM/TPM за ключами) та '
                                  'контроль квот клієнтів шлюзу.',
                            'be': 'Двухузроўневае абмежаванне хуткасці: абарона upstream-акаўнтаў (RPM/TPM па ключах) '
                                  'і кантроль квот кліентаў шлюза.',
                            'zh': '双层速率控制机制：为每个上游凭据设置独立 RPM/TPM 保护账号，同时对下游客户端密钥进行配额与并发监管。',
                            'es': 'Control de tasa en dos niveles: proteja cuentas upstream con límites RPM/TPM por '
                                  'credencial y controle el uso de clientes.',
                            'fr': 'Limitation de débit à deux niveaux : protégez les comptes amont via des limites '
                                  'RPM/TPM par clé et gérez les quotas clients.',
                            'de': 'Zweistufige Ratenbegrenzung: Schützen Sie Upstream-Konten mit RPM/TPM-Grenzen und '
                                  'steuern Sie Client-Kontingente.',
                            'ja': '2層構造のレート制限：認証情報ごとのRPM/TPM制限で上流アカウントを保護し、クライアント利用を細かく制御。',
                            'pt': 'Controle de taxa em dois níveis: proteja contas upstream com limites de RPM/TPM por '
                                  'credencial e regule clientes.',
                            'ar': 'تحديد المعدل على مستويين: حماية حسابات المزودين بحدود RPM/TPM لكل مفتاح، مع تنظيم '
                                  'استخدام عملاء البوابة.',
                            'hi': 'टू-टियर रेट लिमिटिंग: प्रति-क्रेडेंशियल RPM/TPM सीमाओं के साथ अपस्ट्रीम खातों को '
                                  'सुरक्षित रखें और क्लाइंट कोटा प्रबंधित करें।',
                            'bn': 'দ্বি-স্তরীয় রেট লিমিটিং: আপস্ট্রিম অ্যাকাউন্ট রক্ষা করতে আরপিএম/টিপিএম সীমাবদ্ধতা '
                                  'এবং ক্লায়েন্ট কোটা নিয়ন্ত্রণ।'},
        'subsections': [   {   'titles': {   'en': 'Dual-Layer Enforcement',
                                             'ru': 'Двухуровневый контроль лимитов',
                                             'uk': 'Дворівневий контроль лімітів',
                                             'be': 'Двухузроўневы кантроль лімітаў',
                                             'zh': '双层限流控制逻辑',
                                             'es': 'Control de límites en dos capas',
                                             'fr': 'Contrôle des limites à double niveau',
                                             'de': 'Zweistufige Limitüberwachung',
                                             'ja': '2層制限の仕組み',
                                             'pt': 'Controle de Limites em Duas Camadas',
                                             'ar': 'آلية تطبيق الحدود المزدوجة',
                                             'hi': 'डुअल-लेयर लिमिट एनफोर्समेंट',
                                             'bn': 'দ্বৈত-স্তর লিমিট প্রয়োগ'},
                               'table': {   'headers': [   'Layer / Уровень',
                                                           'Target / Объект',
                                                           'Configurable Parameters',
                                                           'Behavior on Limit'],
                                            'rows': [   [   'Upstream Layer',
                                                            'Provider Credential',
                                                            'RPM limit, TPM limit, max concurrency',
                                                            'Skips busy key, routes to next available healthy key'],
                                                        [   'Client Router Layer',
                                                            'Router API Key',
                                                            'RPM, TPM, total requests quota, expiration',
                                                            'Returns HTTP 429 Too Many Requests to client app']]}}]},
    {   'id': 'thinking-cot',
        'group': 'routing',
        'badge': 'Reasoning Effort',
        'titles': {   'en': 'Reasoning Levels (CoT)',
                      'ru': 'Уровни рассуждений (CoT)',
                      'uk': 'Рівні міркувань (CoT)',
                      'be': 'Узроўні разваг (CoT)',
                      'zh': '思维链推理强度 (CoT)',
                      'es': 'Niveles de razonamiento (CoT)',
                      'fr': 'Niveaux de raisonnement (CoT)',
                      'de': 'Denkstufen & CoT',
                      'ja': '思考レベル (CoT)',
                      'pt': 'Níveis de Raciocínio (CoT)',
                      'ar': 'مستويات التفكير والمنطق (CoT)',
                      'hi': 'रीजनिंग लेवल्स (CoT)',
                      'bn': 'রিজনিং লেভেলস (CoT)'},
        'descriptions': {   'en': 'Universal reasoning_effort parameter with automatic cross-provider translation for '
                                  'OpenAI, Anthropic, Google Gemini, and Groq.',
                            'ru': 'Универсальный параметр reasoning_effort с двусторонней трансляцией форматов между '
                                  'OpenAI, Anthropic, Google Gemini и Groq.',
                            'uk': 'Універсальний параметр reasoning_effort із двосторонньою трансляцією форматів між '
                                  'OpenAI, Anthropic, Google Gemini та Groq.',
                            'be': 'Універсальны параметр reasoning_effort з двухбаковай трансляцыяй фарматаў паміж '
                                  'OpenAI, Anthropic, Google Gemini і Groq.',
                            'zh': '通用的 reasoning_effort 推理参数，自动在 OpenAI、Anthropic Claude、Google Gemini 和 Groq '
                                  '间进行双向协议翻译。',
                            'es': 'Parámetro universal reasoning_effort con traducción automática entre OpenAI, '
                                  'Anthropic, Google Gemini y Groq.',
                            'fr': 'Paramètre universel reasoning_effort avec conversion transparente entre OpenAI, '
                                  'Anthropic, Google Gemini et Groq.',
                            'de': 'Universeller Parameter reasoning_effort mit automatischer Übersetzung zwischen '
                                  'OpenAI, Anthropic, Google Gemini und Groq.',
                            'ja': 'OpenAI、Anthropic、Google Gemini、Groqの間で自動相互変換されるユニバーサルな reasoning_effort パラメータ。',
                            'pt': 'Parâmetro universal reasoning_effort com tradução bidirecional entre OpenAI, '
                                  'Anthropic, Google Gemini e Groq.',
                            'ar': 'معلمة reasoning_effort الموحدة مع ترجمة تلقائية متوافقة عبر OpenAI وAnthropic '
                                  'وGoogle Gemini وGroq.',
                            'hi': 'ओपनएआई, एंथ्रोपिक, गूगल जेमिनी और ग्रोक के लिए स्वचालित अनुवाद के साथ यूनिवर्सल '
                                  'reasoning_effort पैरामीटर।',
                            'bn': 'OpenAI, Anthropic, Google Gemini এবং Groq এর জন্য স্বয়ংক্রিয় অনুবাদ সহ '
                                  'ইউনিভার্সাল reasoning_effort প্যারামিটার।'},
        'subsections': [   {   'titles': {   'en': 'Universal Reasoning Example',
                                             'ru': 'Пример запроса с reasoning_effort',
                                             'uk': 'Приклад запиту з reasoning_effort',
                                             'be': 'Прыклад запыту з reasoning_effort',
                                             'zh': '推理参数请求示例',
                                             'es': 'Ejemplo de parámetro de razonamiento',
                                             'fr': 'Exemple de paramètre de raisonnement',
                                             'de': 'Beispiel für Denkparameter',
                                             'ja': '思考パラメータのリクエスト例',
                                             'pt': 'Exemplo de Parâmetro de Raciocínio',
                                             'ar': 'مثال على معلمة التفكير',
                                             'hi': 'रीजनिंग पैरामीटर का उदाहरण',
                                             'bn': 'রিজনিং প্যারামিটারের উদাহরণ'},
                               'code': {   'title': 'cURL Reasoning Request',
                                           'lang': 'bash',
                                           'content': '# Send standard reasoning_effort to any provider\n'
                                                      'curl http://localhost:8000/v1/chat/completions \\\n'
                                                      '  -H "Authorization: Bearer sk-router-YOUR_KEY" \\\n'
                                                      "  -d '{\n"
                                                      '    "model": "gemini-2.5-flash",\n'
                                                      '    "messages": [{"role": "user", "content": "Prove that the '
                                                      'square root of 2 is irrational."}],\n'
                                                      '    "reasoning_effort": "high"\n'
                                                      "  }'"}},
                           {   'titles': {   'en': 'Provider Translation Matrix',
                                             'ru': 'Матрица трансляции параметров',
                                             'uk': 'Матриця трансляції параметрів',
                                             'be': 'Матрыца трансляцыі параметраў',
                                             'zh': '各厂商参数映射矩阵',
                                             'es': 'Matriz de traducción entre proveedores',
                                             'fr': 'Matrice de conversion des fournisseurs',
                                             'de': 'Provider-Übersetzungsmatrix',
                                             'ja': 'プロバイダー変換マトリクス',
                                             'pt': 'Matriz de Tradução entre Provedores',
                                             'ar': 'مصفوفة ترجمة بروتوكولات المزودين',
                                             'hi': 'प्रोवाइडर ट्रांसलेशन मैट्रिक्स',
                                             'bn': 'প্রোভাইডার ট্রান্সলেশন ম্যাট্রিক্স'},
                               'table': {   'headers': [   'Standard Parameter',
                                                           'Anthropic Claude',
                                                           'Google Gemini',
                                                           'Groq / DeepSeek'],
                                            'rows': [   [   'low',
                                                            'thinking: { budget_tokens: 1024 }',
                                                            'thinkingBudget: 1024',
                                                            'reasoning_effort: low'],
                                                        [   'medium',
                                                            'thinking: { budget_tokens: 4096 }',
                                                            'thinkingBudget: 4096',
                                                            'reasoning_effort: medium'],
                                                        [   'high',
                                                            'thinking: { budget_tokens: 8192 }',
                                                            'thinkingBudget: 8192',
                                                            'reasoning_effort: high'],
                                                        [   'none',
                                                            'thinking: disabled',
                                                            'thinkingBudget: 0',
                                                            'reasoning_format: none']]}}]},
    {   'id': 'direct-routing',
        'group': 'routing',
        'badge': 'Low Latency',
        'titles': {   'en': 'Direct Routing Engine',
                      'ru': 'Прямая маршрутизация (Direct)',
                      'uk': 'Пряма маршрутизація (Direct)',
                      'be': 'Прамая маршрутызацыя (Direct)',
                      'zh': '直连路由引擎 (Direct)',
                      'es': 'Enrutamiento directo (Direct)',
                      'fr': 'Moteur de routage direct',
                      'de': 'Direct-Routing-Engine',
                      'ja': 'ダイレクトルーティング',
                      'pt': 'Roteamento Direto (Direct)',
                      'ar': 'محرك التوجيه المباشر (Direct)',
                      'hi': 'डायरेक्ट रूटिंग इंजन',
                      'bn': 'ডাইরেক্ট রাউটিং ইঞ্জিন'},
        'descriptions': {   'en': 'Ultra-fast direct routing targeting a specific upstream model with round-robin key '
                                  'balancing and intra-provider failover.',
                            'ru': 'Высокоскоростная прямая отправка запроса в конкретную модель с балансировкой '
                                  'Round-robin и мгновенным переключением ключей.',
                            'uk': 'Високошвидкісна пряма відправка запиту в конкретну модель із балансуванням '
                                  'Round-robin та миттєвим перемиканням ключів.',
                            'be': 'Высокахуткасная прамая адпраўка запыту ў канкрэтную мадэль з балансаваннем '
                                  'Round-robin і імгненным пераключэннем ключоў.',
                            'zh': '高性能直连调用指定模型，支持多密钥轮询负载均衡以及上游遭遇 429 时的同提供商内自动重试切换。',
                            'es': 'Enrutamiento directo ultrarrápido al modelo especificado con balanceo round-robin y '
                                  'conmutación automática entre claves.',
                            'fr': 'Routage direct ultra-rapide vers un modèle spécifique avec équilibrage round-robin '
                                  'et basculement automatique de clé.',
                            'de': 'Ultraschnelles Direct-Routing zu einem bestimmten Modell mit '
                                  'Round-Robin-Key-Balancing und automatischem Schlüssel-Failover.',
                            'ja': 'ラウンドロビン方式のキー分散と障害時の自動フェイルオーバーを備えた超高速ダイレクトルーティング。',
                            'pt': 'Roteamento direto ultrarrápido para um modelo específico com balanceamento '
                                  'round-robin e failover automático de chaves.',
                            'ar': 'توجيه فائق السرعة نحو نموذج محدد مباشرة مع موازنة المفاتيح بنظام Round-robin '
                                  'والتبديل التلقائي عند الخطأ.',
                            'hi': 'अल्ट्रा-फास्ट डायरेक्ट रूटिंग: राउंड-रॉबिन लोड बैलेंसिंग और की-फॉलबैक के साथ '
                                  'विशिष्ट मॉडल तक सीधी पहुंच।',
                            'bn': 'নির্দিষ্ট মডেলে সরাসরি উচ্চ-গতির রাউটিং, রাউন্ড-রবিন লোড ব্যালেন্সিং এবং '
                                  'স্বয়ংক্রিয় কী ফেইলওভার।'},
        'subsections': [   {   'titles': {   'en': 'Addressing Code Sample',
                                             'ru': 'Примеры прямого обращения',
                                             'uk': 'Приклади прямого звернення',
                                             'be': 'Прыклады прамога звароту',
                                             'zh': '直连模式调用示例',
                                             'es': 'Ejemplo de enrutamiento directo',
                                             'fr': "Exemple d'appel direct",
                                             'de': 'Direct-Routing Codebeispiel',
                                             'ja': 'ダイレクト指定のコード例',
                                             'pt': 'Exemplo de Roteamento Direto',
                                             'ar': 'أمثلة الاستدعاء المباشر',
                                             'hi': 'डायरेक्ट रूटिंग कोड उदाहरण',
                                             'bn': 'ডাইরেক্ট রাউটিং কোড উদাহরণ'},
                               'code': {   'title': 'Direct Routing Requests',
                                           'lang': 'bash',
                                           'content': '# 1. Canonical slug (auto-resolves primary provider)\n'
                                                      'curl http://localhost:8000/v1/chat/completions \\\n'
                                                      '  -H "Authorization: Bearer sk-router-YOUR_KEY" \\\n'
                                                      '  -d \'{"model": "gemini-2.5-flash", "messages": '
                                                      '[{"role":"user","content":"Hello!"}]}\'\n'
                                                      '\n'
                                                      '# 2. Provider-qualified addressing (forces specific provider)\n'
                                                      'curl http://localhost:8000/v1/chat/completions \\\n'
                                                      '  -H "Authorization: Bearer sk-router-YOUR_KEY" \\\n'
                                                      '  -d \'{"model": '
                                                      '"openrouter/meta-llama/llama-3.3-70b-instruct", "messages": '
                                                      '[{"role":"user","content":"Hello!"}]}\''}}]},
    {   'id': 'priority-fallback',
        'group': 'routing',
        'badge': 'Nested Chains',
        'titles': {   'en': 'Priority & Fallback Chains',
                      'ru': 'Приоритеты и Fallback',
                      'uk': 'Пріоритети та Fallback',
                      'be': 'Прыярытэты і Fallback',
                      'zh': '优先级与回退链路 (Fallback)',
                      'es': 'Cadenas de Fallback prioritario',
                      'fr': 'Chaînes de repli prioritaire',
                      'de': 'Prioritäts- & Fallback-Ketten',
                      'ja': '優先度とフォールバックチェーン',
                      'pt': 'Cadeias de Fallback e Prioridade',
                      'ar': 'سلاسل الأولوية والاحتياط (Fallback)',
                      'hi': 'प्रायोरिटी और फॉलबैक चेन्स',
                      'bn': 'প্রায়োরিটি এবং ফলব্যাক চেইন'},
        'descriptions': {   'en': 'Multi-tier fallback queues across models and providers on 429 quota exhaustion or '
                                  '5xx server outages, with nested profiles and key groups.',
                            'ru': 'Многоуровневые очереди переключения при 429 лимитах или 5xx ошибках, поддержка '
                                  'вложенных профилей и групп ключей.',
                            'uk': 'Багаторівневі черги перемикання при 429 лімітах або 5xx помилках, підтримка '
                                  'вкладених профілів та груп ключів.',
                            'be': 'Шматузроўневыя чэргі пераключэння пры 429 лімітах або 5xx памылках, падтрымка '
                                  'ўкладзеных профіляў і груп ключоў.',
                            'zh': '当遇到上游 429 限流或 5xx 故障时自动切换的多级回退队列，支持嵌套路由配置、密钥分组与参数覆盖。',
                            'es': 'Colas de conmutación multinivel en caso de cuotas 429 o fallos 5xx, con perfiles '
                                  'anidados y grupos de claves.',
                            'fr': "Files d'attente multi-niveaux en cas de quota 429 ou d'erreur 5xx, avec profils "
                                  'imbriqués et groupes de clés.',
                            'de': 'Mehrstufige Ausfallwarteschlangen bei 429-Quotenüberschreitungen oder 5xx-Fehlern, '
                                  'mit verschachtelten Profilen und Schlüsselgruppen.',
                            'ja': '429 レート制限や 5xx 障害発生時に自動切り替えを行う多層フォールバックキュー。入れ子プロファイルやキーグループに対応。',
                            'pt': 'Filas de alternância em vários níveis em erros 429 ou 5xx, com suporte a perfis '
                                  'aninhados e grupos de chaves.',
                            'ar': 'قوائم تبديل متعددة المستويات عند استنفاد الحصص 429 أو أخطاء الخوادم 5xx، مع دعم '
                                  'المسارات المتداخلة ومجموعات المفاتيح.',
                            'hi': '429 कोटा समाप्ति या 5xx सर्वर त्रुटियों पर ऑटोमैटिक मल्टी-टियर फॉलबैक कतारें, '
                                  'नेस्टेड प्रोफाइल और की-ग्रुप सपोर्ट।',
                            'bn': '429 কোটা বা 5xx ত্রুটিতে স্বয়ংক্রিয় মাল্টি-লেভেল ফলব্যাক সারি, নেস্টেড প্রোফাইল '
                                  'এবং কী-গ্রুপ সমর্থন।'},
        'subsections': [   {   'titles': {   'en': 'Fallback Mechanics',
                                             'ru': 'Принцип работы цепочки',
                                             'uk': 'Принцип роботи ланцюжка',
                                             'be': 'Прынцып працы ланцужка',
                                             'zh': '回退链路工作机制',
                                             'es': 'Mecánica de Fallback',
                                             'fr': 'Mécanisme de basculement',
                                             'de': 'Fallback-Funktionsweise',
                                             'ja': 'フォールバックの動作原理',
                                             'pt': 'Mecânica do Fallback',
                                             'ar': 'آلية عمل السلسلة الاحتياطية',
                                             'hi': 'फॉलबैक कार्यप्रणाली',
                                             'bn': 'ফলব্যাক কাজের পদ্ধতি'},
                               'table': {   'headers': [   'Feature / Возможность',
                                                           'Configuration / Настройка',
                                                           'Benefit / Преимущество'],
                                            'rows': [   [   'Candidate Sequence',
                                                            'Ordered list (Candidate 1 -> 2 -> 3)',
                                                            'Ensures primary low-cost models are tried first before '
                                                            'expensive fallbacks'],
                                                        [   'Nested Profiles',
                                                            "candidate_type: 'profile'",
                                                            'Allows sharing base queues (e.g. embed route/standard '
                                                            'inside route/premium)'],
                                                        [   'Credential Groups',
                                                            "credential_group: 'folder_name' or 'all'",
                                                            'Restricts fallback candidate to team keys or enables full '
                                                            'provider pool'],
                                                        [   'Overrides',
                                                            'temperature, context_length, reasoning',
                                                            'Fine-tunes behavior per fallback step independently of '
                                                            'request']]}}]},
    {   'id': 'fusion',
        'group': 'routing',
        'badge': 'AI Ensembles',
        'titles': {   'en': 'Model Fusion (Ensembles)',
                      'ru': 'Model Fusion (Ансамбли ИИ)',
                      'uk': 'Model Fusion (Ансамблі ШІ)',
                      'be': 'Model Fusion (Ансамблі ШІ)',
                      'zh': '模型融合机制 (Model Fusion)',
                      'es': 'Fusión de modelos (Ensembles)',
                      'fr': 'Fusion de modèles (Ensembles IA)',
                      'de': 'Modell-Fusion (KI-Ensembles)',
                      'ja': 'モデル融合 (Model Fusion)',
                      'pt': 'Fusão de Modelos (Ensembles)',
                      'ar': 'دمج النماذج (Model Fusion)',
                      'hi': 'मॉडल फ्यूजन (AI एन्सेम्बल)',
                      'bn': 'মডেল ফিউশন (AI সমাহার)'},
        'descriptions': {   'en': 'Execute multiple LLMs in parallel and synthesize the definitive response using a '
                                  'Judge model with real-time reasoning streaming.',
                            'ru': 'Параллельное выполнение нескольких моделей и синтез эталонного ответа '
                                  'моделью-судьей с потоковой передачей хода рассуждений.',
                            'uk': 'Паралельне виконання кількох моделей та синтез еталонної відповіді моделлю-суддею з '
                                  'потоковою передачею ходу міркувань.',
                            'be': 'Паралельнае выкананне некалькіх мадэляў і сінтэз эталоннага адказу мадэллю-суддзёй '
                                  'з струменевай перадачай ходу разваг.',
                            'zh': '多模型并发并行执行，由指定的评审模型 (Judge) 对候选草稿进行评优、共识提炼或批判重写，并实时流式传输评审思考链。',
                            'es': 'Ejecute varios LLM en paralelo y sintetice la respuesta definitiva mediante un '
                                  'modelo Juez con transmisión de razonamiento en tiempo real.',
                            'fr': 'Exécutez plusieurs LLM en parallèle et synthétisez la réponse optimale grâce à un '
                                  'modèle Juge avec streaming des réflexions.',
                            'de': 'Führen Sie mehrere LLMs parallel aus und synthetisieren Sie die beste Antwort mit '
                                  'einem Judge-Modell inklusive Echtzeit-Deliberations-Streaming.',
                            'ja': '複数のLLMを並行実行し、Judgeモデルが最適な回答を統合・生成。審査過程の思考ストリーミングにも完全対応。',
                            'pt': 'Execute múltiplos LLMs em paralelo e sintetize a resposta ideal usando um modelo '
                                  'Juiz com streaming de raciocínio em tempo real.',
                            'ar': 'تشغيل نماذج لغوية متعددة بالتوازي وتوليف إجابة موحدة عبر نموذج الحكم مع بث خطوات '
                                  'التفكير المباشرة.',
                            'hi': 'समानांतर में कई एलएलएम निष्पादित करें और रीयल-टाइम रीजनिंग स्ट्रीमिंग के साथ एक जज '
                                  'मॉडल द्वारा अंतिम उत्तर तैयार करें।',
                            'bn': 'একসাথে একাধিক এলএলএম পরিচালনা করুন এবং রিয়েল-টাইম রিজনিং স্ট্রিমিং সহ জাজ মডেল '
                                  'দ্বারা চূড়ান্ত প্রতিক্রিয়া তৈরি করুন।'},
        'subsections': [   {   'titles': {   'en': 'Streaming Deliberation Example',
                                             'ru': 'Потоковый вывод хода обсуждения',
                                             'uk': 'Потокове виведення обговорення',
                                             'be': 'Струменевы вывад ходу абмеркавання',
                                             'zh': '流式评审过程示例',
                                             'es': 'Ejemplo de deliberación en streaming',
                                             'fr': 'Exemple de délibération en streaming',
                                             'de': 'Streaming-Deliberation Beispiel',
                                             'ja': '審査思考ストリーミングの例',
                                             'pt': 'Exemplo de Deliberação em Streaming',
                                             'ar': 'مثال على بث خطوات التفكير',
                                             'hi': 'स्ट्रीमिंग डेलिबरेशन का उदाहरण',
                                             'bn': 'স্ট্রিমিং ডিলিবারেশন উদাহরণ'},
                               'code': {   'title': 'SSE Fusion Stream',
                                           'lang': 'bash',
                                           'content': 'curl http://localhost:8000/v1/chat/completions \\\n'
                                                      '  -H "Content-Type: application/json" \\\n'
                                                      '  -H "Authorization: Bearer sk-router-YOUR_KEY" \\\n'
                                                      "  -d '{\n"
                                                      '    "model": "fusion/code-jury",\n'
                                                      '    "messages": [{"role": "user", "content": "Analyze time '
                                                      'complexity of quicksort"}],\n'
                                                      '    "stream": true\n'
                                                      "  }'\n"
                                                      '\n'
                                                      '# Streamed SSE chunks contain real-time deliberation in '
                                                      'reasoning_content:\n'
                                                      '# data: {"choices":[{"delta":{"reasoning_content":"### 🧬 Fusion '
                                                      'Ensemble Deliberation\\n..."}}]}\n'
                                                      '# ...\n'
                                                      '# data: {"choices":[{"delta":{"content":"Final evaluated '
                                                      'answer..."}}]}'}},
                           {   'titles': {   'en': 'Judge Strategies',
                                             'ru': 'Стратегии работы судьи',
                                             'uk': 'Стратегії роботи судді',
                                             'be': 'Стратэгіі працы суддзі',
                                             'zh': '评审团工作策略',
                                             'es': 'Estrategias de arbitraje del Juez',
                                             'fr': "Stratégies d'arbitrage du Juge",
                                             'de': 'Judge-Strategien',
                                             'ja': 'Judge 戦略の比較',
                                             'pt': 'Estratégias de Avaliação do Juiz',
                                             'ar': 'استراتيجيات التحكيم',
                                             'hi': 'जज कार्य रणनीतियाँ',
                                             'bn': 'জাজ কার্যকৌশল'},
                               'table': {   'headers': ['Strategy / Стратегия', 'ID', 'Operation / Принцип работы'],
                                            'rows': [   [   'Best-of-N',
                                                            'best_of_n',
                                                            'Compares all candidate drafts and selects the highest '
                                                            'scoring complete response'],
                                                        [   'Consensus',
                                                            'consensus',
                                                            'Synthesizes a unified response combining best points and '
                                                            'resolving discrepancies'],
                                                        [   'Critique & Rewrite',
                                                            'critique_and_rewrite',
                                                            'Critiques weaknesses in each draft and writes a superior '
                                                            'comprehensive answer']]}}]},
    {   'id': 'jev-systemone',
        'group': 'routing',
        'badge': '⚡ System One Decisions',
        'titles': {   'en': 'Jev (System One) Decision Engine',
                      'ru': 'Движок быстрых решений Jev (System One)',
                      'uk': 'Рушій швидких рішень Jev (System One)',
                      'be': 'Рухавік хуткіх рашэнняў Jev (System One)',
                      'zh': 'Jev 快决策 (System One) 引擎',
                      'es': 'Motor de decisiones Jev (System One)',
                      'fr': 'Moteur de décisions Jev (System One)',
                      'de': 'Jev (System One) Entscheidungs-Engine',
                      'ja': 'Jev（System One）意思決定エンジン',
                      'pt': 'Motor de Decisões Jev (System One)',
                      'ar': 'محرك اتخاذ القرار السريع Jev (System One)',
                      'hi': 'जेव (Jev) सिस्टम वन डिसीजन इंजन',
                      'bn': 'জেভ (Jev) সিস্টেম ওয়ান ডিসিশন ইঞ্জিন'},
        'descriptions': {   'en': 'Ultra-fast System One decision engine for autonomous agents, classification, '
                                  'guardrails, and structured scoring against discrete rubrics with calibrated '
                                  'probability distributions.',
                            'ru': 'Сверхбыстрый движок решений System One для автономных агентов, классификации, '
                                  'гардрайлов и оценки по дискретным рубрикам с калиброванным распределением '
                                  'вероятностей.',
                            'uk': 'Надшвидкий рушій рішень System One для автономних агентів, класифікації, гардрейлів '
                                  'та оцінювання за дискретними рубриками з каліброваним розподілом ймовірностей.',
                            'be': 'Звышхуткі рухавік рашэнняў System One для аўтаномных агентаў, класіфікацыі, '
                                  'гардрэйлаў і ацэнкі па дыскрэтных рубрыках з калібраваным размеркаваннем '
                                  'верагоднасцяў.',
                            'zh': '超高速 System One 快速决策引擎，面向自主智能体、意图分类、安全护栏与结构化规则评分，输出精确校准的概率分布。',
                            'es': 'Motor de decisiones System One ultrarrápido para agentes autónomos, clasificación, '
                                  'guardarraíles y puntuación con distribuciones de probabilidad calibradas.',
                            'fr': 'Moteur de décisions System One ultra-rapide pour agents autonomes, classification, '
                                  'garde-fous et évaluation structurée avec probabilités calibrées.',
                            'de': 'Ultraschnelle System One Entscheidungs-Engine für autonome Agenten, '
                                  'Klassifizierung, Guardrails und strukturierte Kriterienbewertung mit kalibrierten '
                                  'Wahrscheinlichkeiten.',
                            'ja': '自律型エージェント、分類、ガードレール、離散ルーブリック評価向けの高精度確率分布を出力する超高速System One意思決定エンジン。',
                            'pt': 'Motor ultrarrápido de decisões System One para agentes autônomos, classificação, '
                                  'guardrails e avaliação estruturada com distribuições de probabilidade calibradas.',
                            'ar': 'محرك قرارات فائق السرعة (System One) للوكلاء المستقلين والتصنيف وحواجز الأمان '
                                  'والتقييم المعياري مع توزيعات احتمالية معايرة.',
                            'hi': 'स्वायत्त एजेंटों, वर्गीकरण, सुरक्षा गार्डरेल्स और कैलिब्रेटेड प्रायिकता वितरण के '
                                  'साथ त्वरित सिस्टम वन डिसीजन इंजन।',
                            'bn': 'স্বায়ত্তশাসিত এজেন্ট, ক্লাসিফিকেশন, সুরক্ষা গার্ডরেল এবং ক্যালিব্রেটেড সম্ভাব্যতা '
                                  'বিতরণের জন্য অতি-দ্রুত সিস্টেম ওয়ান ডিসিশন ইঞ্জিন।'},
        'highlights': {   'en': [   'System One Decision Engine: Sub-second rubric & classification evaluation with '
                                    'calibrated probabilities',
                                    '3 Decision Primitives: Choice (categorical distribution), Score (quantitative '
                                    'metric), and Noul (binary assertion)',
                                    'Dedicated Endpoints: POST /v1/systemone, POST /v1/decisions, and transparent POST '
                                    '/v1/chat/completions support',
                                    'Native Zero-Delay Routing for Jev providers + intelligent structured JSON '
                                    'emulation fallback for any LLM',
                                    'Interactive Playground Studio: State Context, Visual Builder, 4 Presets, '
                                    'probability charts, and multi-language code export'],
                          'ru': [   'Движок решений System One: Мгновенная классификация и оценка по рубрикам с '
                                    'калиброванными вероятностями',
                                    '3 примитива решений: Choice (категориальный выбор), Score (числовой балл) и Noul '
                                    '(булево утверждение)',
                                    'Выделенные эндпоинты: POST /v1/systemone, POST /v1/decisions и прозрачная '
                                    'поддержка POST /v1/chat/completions',
                                    'Нативный роутинг без задержек для Jev-провайдеров + структурированная '
                                    'JSON-эмуляция для любых LLM',
                                    'Интерактивная студия в Playground: контекст State, Visual Builder, 4 пресета, '
                                    'графики вероятностей и экспорт кода'],
                          'uk': [   'Рушій рішень System One: Миттєва класифікація та оцінювання за рубриками з '
                                    'каліброваними ймовірностями',
                                    '3 примітиви рішень: Choice (категоріальний вибір), Score (числовий бал) та Noul '
                                    '(булеве твердження)',
                                    'Виділені ендпоінти: POST /v1/systemone, POST /v1/decisions та прозора підтримка '
                                    'POST /v1/chat/completions',
                                    'Нативний роутинг без затримок для Jev-провайдерів + структурована JSON-емуляція '
                                    'для будь-яких LLM',
                                    'Інтерактивна студія в Playground: контекст State, Visual Builder, 4 пресети, '
                                    'графіки ймовірностей та експорт коду'],
                          'be': [   'Рухавік рашэнняў System One: Імгненная класіфікацыя і ацэнка па рубрыках з '
                                    'калібраванымі верагоднасцямі',
                                    '3 прымітывы рашэнняў: Choice (катэгарыяльны выбар), Score (лікавы бал) і Noul '
                                    '(булева сцвярджэнне)',
                                    'Вылучаныя эндпоінты: POST /v1/systemone, POST /v1/decisions і празрыстая '
                                    'падтрымка POST /v1/chat/completions',
                                    'Натыўны роўтынг без затрымак для Jev-правайдэраў + структураваная JSON-эмуляцыя '
                                    'для любых LLM',
                                    'Інтэрактыўная студыя ў Playground: кантэкст State, Visual Builder, 4 прэсеты, '
                                    'графікі верагоднасцяў і экспарт коду'],
                          'zh': [   'System One 极速决策引擎：面向分类、安全与合规审计的高并发评估，输出高精度校准概率',
                                    '三大决策原语：Choice（多选类别概率分布）、Score（量化规则评分）与 Noul（布尔断言决策）',
                                    '专用 REST 接口：POST /v1/systemone、POST /v1/decisions，并无缝兼容标准 POST '
                                    '/v1/chat/completions',
                                    '原生直连零延迟：原生 Jev 平台直通透传，通用 LLM 自动激活高质量结构化 JSON 提示词模拟回退',
                                    'Playground 可视化决策工作室：支持 State 上下文编辑、可视化问题构建器、4大场景预设及多语言代码导出'],
                          'es': [   'Motor de decisiones System One: Clasificación instantánea y evaluación por '
                                    'rúbricas con probabilidades calibradas',
                                    '3 primitivas de decisión: Choice (distribución categórica), Score (métrica '
                                    'cuantitativa) y Noul (afirmación binaria)',
                                    'Endpoints dedicados: POST /v1/systemone, POST /v1/decisions y compatibilidad '
                                    'transparente con POST /v1/chat/completions',
                                    'Enrutamiento nativo sin retardo para proveedores Jev + emulación JSON '
                                    'estructurada inteligente para cualquier LLM',
                                    'Estudio interactivo en Playground: contexto State, Visual Builder, 4 ajustes '
                                    'preestablecidos, gráficos de probabilidad y exportación de código'],
                          'fr': [   'Moteur de décisions System One : Classification instantanée et évaluation selon '
                                    'des grilles avec probabilités calibrées',
                                    '3 primitives de décision : Choice (distribution catégorielle), Score (note '
                                    'quantitative) et Noul (assertion binaire)',
                                    'Points de terminaison dédiés : POST /v1/systemone, POST /v1/decisions et '
                                    'compatibilité transparente avec POST /v1/chat/completions',
                                    'Routage natif sans délai pour les fournisseurs Jev + émulation JSON structurée '
                                    'intelligente pour tout LLM',
                                    'Studio interactif dans Playground : contexte State, Visual Builder, 4 '
                                    'préréglages, graphiques de probabilité et export de code'],
                          'de': [   'System One Entscheidungs-Engine: Sekundenschnelle Rubriken- und '
                                    'Klassifizierungsbewertung mit kalibrierten Wahrscheinlichkeiten',
                                    '3 Entscheidungsprimitive: Choice (kategoriale Verteilung), Score (quantitative '
                                    'Metrik) und Noul (binäre Aussage)',
                                    'Dedizierte Endpunkte: POST /v1/systemone, POST /v1/decisions und transparente '
                                    'Unterstützung von POST /v1/chat/completions',
                                    'Natives Routing ohne Latenz für Jev-Provider + intelligente strukturierte '
                                    'JSON-Emulation für jedes LLM',
                                    'Interaktives Playground-Studio: State-Kontext, Visual Builder, 4 Presets, '
                                    'Wahrscheinlichkeitsdiagramme und Code-Export'],
                          'ja': [   'System One意思決定エンジン：校正済み確率を出力するミリ秒級のルーブリック評価および分類機能',
                                    '3つの意思決定プリミティブ：Choice（カテゴリカル確率分布）、Score（定量的評価点）、Noul（ブール判定）',
                                    '専用RESTエンドポイント：POST /v1/systemone、POST /v1/decisions、および透過的なPOST '
                                    '/v1/chat/completions対応',
                                    'Jev事業者向けのネイティブゼロ遅延転送＋汎用LLM向けの高度な構造化JSONエミュレーションフォールバック',
                                    'Playground判定スタジオ：Stateコンテキスト入力、ビジュアルビルダー、4つの実用プリセット、確率グラフ、コード生成'],
                          'pt': [   'Motor de decisões System One: Classificação instantânea e avaliação por rubricas '
                                    'com probabilidades calibradas',
                                    '3 primitivas de decisão: Choice (distribuição categórica), Score (métrica '
                                    'quantitativa) e Noul (afirmação binária)',
                                    'Endpoints dedicados: POST /v1/systemone, POST /v1/decisions e compatibilidade '
                                    'transparente com POST /v1/chat/completions',
                                    'Roteamento nativo sem latência para provedores Jev + emulação JSON estruturada '
                                    'inteligente para qualquer LLM',
                                    'Estúdio interativo no Playground: contexto State, Visual Builder, 4 '
                                    'predefinições, gráficos de probabilidade e exportação de código'],
                          'ar': [   'محرك قرارات System One: تقييم فائق السرعة للمعايير والتصنيف مع توزيعات احتمالية '
                                    'معايرة بدقة',
                                    '3 أوليات للقرار: الاختيار Choice (توزيع فئوي)، والدرجة Score (مقياس كمي)، '
                                    'والإثبات Noul (قرار ثنائي/منطقي)',
                                    'نقاط نهاية مخصصة: POST /v1/systemone وPOST /v1/decisions، مع توافق شفاف مع POST '
                                    '/v1/chat/completions',
                                    'توجيه أصلي بدون تأخير لمزودي Jev + محاكاة ذكية بـ JSON المنظم لأي نموذج LLM عام',
                                    'استوديو Playground التفاعلي: سياق الحالة State، ومنشئ بصري، و4 قوالب جاهزة، ورسوم '
                                    'بيانية للاحتمالات، وتصدير الأكواد'],
                          'hi': [   'सिस्टम वन डिसीजन इंजन: कैलिब्रेटेड प्रायिकताओं के साथ त्वरित वर्गीकरण और मानक '
                                    'मूल्यांकन',
                                    '3 निर्णय प्रिमिटिव: Choice (श्रेणीबद्ध वितरण), Score (मात्रात्मक स्कोर) और Noul '
                                    '(बूलियन निर्णय)',
                                    'समर्पित एंडपॉइंट्स: POST /v1/systemone, POST /v1/decisions और POST '
                                    '/v1/chat/completions के साथ पारदर्शी कम्पैटिबिलिटी',
                                    'जेव प्रदाताओं के लिए नेटिव जीरो-डिले रूटिंग + किसी भी एलएलएम के लिए इंटेलिजेंट '
                                    'स्ट्रक्चर्ड JSON एमुलेशन फॉलबैक',
                                    'इंटरएक्टिव प्लेग्राउंड स्टूडियो: State संदर्भ संपादक, विज़ुअल बिल्डर, 4 प्रीसेट, '
                                    'प्रायिकता चार्ट और कोड निर्यात'],
                          'bn': [   'সিস্টেম ওয়ান ডিসিশন ইঞ্জিন: ক্যালিব্রেটেড সম্ভাব্যতা সহ সাব-সেকেন্ড ক্লাসিফিকেশন '
                                    'এবং রুব্রিক মূল্যায়ন',
                                    '৩টি ডিসিশন প্রিমিটিভ: Choice (ক্যাটেগরিক্যাল সম্ভাবনা বণ্টন), Score (সংখ্যাসূচক '
                                    'স্কোর) এবং Noul (বুলিয়ান সিদ্ধান্ত)',
                                    'ডেডিকেটেড এন্ডপয়েন্ট: POST /v1/systemone, POST /v1/decisions এবং সম্পূর্ণ স্বচ্ছ '
                                    'POST /v1/chat/completions সামঞ্জস্য',
                                    'জেভ প্রোভাইডারদের জন্য নেটিভ জিরো-ডিলে রাউটিং + যেকোনো এলএলএম-এর জন্য বুদ্ধিমান '
                                    'স্ট্রাকচার্ড JSON এমুলেশন',
                                    'ইন্টারেক্টিভ প্লেগ্রাউন্ড স্টুডিও: State কনটেক্সট এডিটর, ভিজ্যুয়াল বিল্ডার, ৪টি '
                                    'প্রিসেট, সম্ভাব্যতা চার্ট এবং কোড এক্সপোর্ট']},
        'subsections': [   {   'titles': {   'en': 'Decision Primitives & Rubrics',
                                             'ru': 'Примитивы решений и рубрики',
                                             'uk': 'Примітиви рішень та рубрики',
                                             'be': 'Прымітывы рашэнняў і рубрыкі',
                                             'zh': '决策原语与评估规则',
                                             'es': 'Primitivas de decisión y rúbricas',
                                             'fr': 'Primitives de décision et grilles',
                                             'de': 'Entscheidungsprimitive & Bewertungsrubriken',
                                             'ja': '意思決定プリミティブと評価ルーブリック',
                                             'pt': 'Primitivas de Decisão e Rubricas',
                                             'ar': 'أوليات القرار والمعايير',
                                             'hi': 'निर्णय प्रिमिटिव और मूल्यांकन रूब्रिक्स',
                                             'bn': 'ডিসিশন প্রিমিটিভ ও মূল্যায়ন রুব্রিক্স'},
                               'table': {   'headers': [   'Primitive / Примитив',
                                                           'Type / Тип',
                                                           'Output Structure',
                                                           'Description & Usage / Назначение'],
                                            'rows': [   [   'choice',
                                                            'Categorical / Категориальный',
                                                            'probabilities: {option: float}, choice: string',
                                                            'Calculates calibrated probability distribution across '
                                                            'discrete options (e.g. intent routing, priority triage, '
                                                            'sentiment).'],
                                                        [   'score',
                                                            'Quantitative / Числовой',
                                                            'score: float, confidence: float',
                                                            'Computes a numerical score within a defined rubric range '
                                                            '(e.g. risk score 0.0-1.0, quality rating 1-5).'],
                                                        [   'noul',
                                                            'Binary / Булево',
                                                            'value: bool, confidence: float',
                                                            'Evaluates a strict boolean assertion or safety guardrail '
                                                            'condition with associated confidence.']]}},
                           {   'titles': {   'en': 'REST API Specification (POST /v1/systemone)',
                                             'ru': 'Спецификация REST API (POST /v1/systemone)',
                                             'uk': 'Специфікація REST API (POST /v1/systemone)',
                                             'be': 'Спецыфікацыя REST API (POST /v1/systemone)',
                                             'zh': 'REST 接口规范 (POST /v1/systemone)',
                                             'es': 'Especificación REST API (POST /v1/systemone)',
                                             'fr': "Spécification de l'API REST (POST /v1/systemone)",
                                             'de': 'REST-API-Spezifikation (POST /v1/systemone)',
                                             'ja': 'REST API 仕様 (POST /v1/systemone)',
                                             'pt': 'Especificação da API REST (POST /v1/systemone)',
                                             'ar': 'مواصفات واجهة REST API (POST /v1/systemone)',
                                             'hi': 'REST एपीआई विशिष्टता (POST /v1/systemone)',
                                             'bn': 'REST এপিআই স্পেসিফিকেশন (POST /v1/systemone)'},
                               'code': {   'title': 'System One Decision Request',
                                           'lang': 'bash',
                                           'content': 'curl http://localhost:8000/v1/systemone \\\n'
                                                      '  -H "Content-Type: application/json" \\\n'
                                                      '  -H "Authorization: Bearer sk-router-YOUR_KEY" \\\n'
                                                      "  -d '{\n"
                                                      '    "model": "experientiallabs/jev-latest",\n'
                                                      '    "state": "User transaction: $4,990 from IP 198.51.100.4 '
                                                      '(New Device, Location: Kyiv, Previous: New York 10m ago).",\n'
                                                      '    "questions": [\n'
                                                      '      {\n'
                                                      '        "id": "fraud_risk",\n'
                                                      '        "text": "What is the fraud probability category?",\n'
                                                      '        "type": "choice",\n'
                                                      '        "options": ["low", "suspicious", "critical_fraud"]\n'
                                                      '      },\n'
                                                      '      {\n'
                                                      '        "id": "require_2fa",\n'
                                                      '        "text": "Should step-up 2FA verification be enforced '
                                                      'immediately?",\n'
                                                      '        "type": "noul"\n'
                                                      '      }\n'
                                                      '    ]\n'
                                                      "  }'\n"
                                                      '\n'
                                                      '# Response format:\n'
                                                      '# {\n'
                                                      '#   "id": "jev-9b2f4c1e",\n'
                                                      '#   "model": "experientiallabs/jev-latest",\n'
                                                      '#   "decisions": {\n'
                                                      '#     "fraud_risk": {\n'
                                                      '#       "choice": "critical_fraud",\n'
                                                      '#       "probabilities": {"low": 0.02, "suspicious": 0.11, '
                                                      '"critical_fraud": 0.87},\n'
                                                      '#       "confidence": 0.87\n'
                                                      '#     },\n'
                                                      '#     "require_2fa": {\n'
                                                      '#       "value": true,\n'
                                                      '#       "confidence": 0.96\n'
                                                      '#     }\n'
                                                      '#   }\n'
                                                      '# }'}},
                           {   'titles': {   'en': 'Native Execution vs Intelligent Emulation',
                                             'ru': 'Нативное исполнение vs Умная эмуляция',
                                             'uk': 'Нативне виконання vs Розумна емуляція',
                                             'be': 'Натыўнае выкананне vs Разумная эмуляцыя',
                                             'zh': '原生执行与智能模拟回退机制',
                                             'es': 'Ejecución nativa vs Emulación inteligente',
                                             'fr': 'Exécution native vs Émulation intelligente',
                                             'de': 'Native Ausführung vs. Intelligente Emulation',
                                             'ja': 'ネイティブ実行 vs インテリジェントエミュレーション',
                                             'pt': 'Execução Nativa vs Emulação Inteligente',
                                             'ar': 'التنفيذ الأصلي مقابل المحاكاة الذكية',
                                             'hi': 'नेटिव निष्पादन बनाम इंटेलिजेंट एमुलेशन',
                                             'bn': 'নেটিভ এক্সিকিউশন বনাম ইন্টেলিজেন্ট এমুলেশন'},
                               'bullets': {   'en': [   'Native Zero-Delay Routing: Providers specializing in System '
                                                        'One decisions (such as drex.nace, experientiallabs, '
                                                        'typesafe.ai) receive pass-through requests with minimal '
                                                        'latency overhead.',
                                                        'Universal LLM Structured Emulation: If a general '
                                                        'conversational model (e.g. gemini-2.5-flash, gpt-4o-mini, '
                                                        "claude-3-5-haiku, or local ollama) has model_type='jev', "
                                                        'MyAIrouter automatically converts the state and questions '
                                                        'into a strict structured JSON schema prompt, validates '
                                                        'probability constraints, and normalizes output into the '
                                                        'compliant Jev envelope.',
                                                        'Transparent Chat Compatibility: Standard POST '
                                                        '/v1/chat/completions accepts Jev-style requests and '
                                                        'automatically returns decision payloads, enabling drop-in '
                                                        'integration with existing SDKs.',
                                                        'Alias Support: Both POST /v1/systemone and POST /v1/decisions '
                                                        'are public and serve identical functionality.'],
                                              'ru': [   'Нативный роутинг без задержек: Специализированные провайдеры '
                                                        '(drex.nace, experientiallabs, typesafe.ai) получают прямой '
                                                        'запрос к System One с минимальным временем отклика.',
                                                        'Универсальная структурированная JSON-эмуляция: Если у обычной '
                                                        'модели (например, gemini-2.5-flash, gpt-4o-mini, '
                                                        'claude-3-5-haiku или локальной ollama) установлен '
                                                        "model_type='jev', шлюз автоматически генерирует строгий "
                                                        'JSON-промпт, валидирует вероятности и нормализует ответ в '
                                                        'формат Jev.',
                                                        'Прозрачная совместимость с Chat API: Эндпоинт POST '
                                                        '/v1/chat/completions прозрачно обрабатывает запросы решений, '
                                                        'позволяя работать через стандартные OpenAI SDK.',
                                                        'Поддержка алиасов: Эндпоинты POST /v1/systemone и POST '
                                                        '/v1/decisions взаимозаменяемы и обладают идентичной '
                                                        'функциональностью.'],
                                              'uk': [   'Нативний роутинг без затримок: Спеціалізовані провайдери '
                                                        '(drex.nace, experientiallabs, typesafe.ai) отримують прямий '
                                                        'запит до System One із мінімальним часом відгуку.',
                                                        'Універсальна структурована JSON-емуляція: Якщо у звичайної '
                                                        'моделі (наприклад, gemini-2.5-flash, gpt-4o-mini, '
                                                        'claude-3-5-haiku або локальної ollama) встановлено '
                                                        "model_type='jev', шлюз автоматично генерує суворий "
                                                        'JSON-промпт, валідує ймовірності та нормалізує відповідь у '
                                                        'формат Jev.',
                                                        'Прозора сумісність із Chat API: Ендпоінт POST '
                                                        '/v1/chat/completions прозоро обробляє запити рішень, '
                                                        'дозволяючи працювати через стандартні OpenAI SDK.',
                                                        'Підтримка аліасів: Ендпоінти POST /v1/systemone та POST '
                                                        '/v1/decisions взаємозамінні та мають ідентичну '
                                                        'функціональність.'],
                                              'be': [   'Натыўны роўтынг без затрымак: Спецыялізаваныя правайдэры '
                                                        '(drex.nace, experientiallabs, typesafe.ai) атрымліваюць прамы '
                                                        'запыт да System One з мінімальным часам водгуку.',
                                                        'Універсальная структураваная JSON-эмуляцыя: Калі ў звычайнай '
                                                        'мадэлі (напрыклад, gemini-2.5-flash, gpt-4o-mini, '
                                                        'claude-3-5-haiku або лакальнай ollama) усталяваны '
                                                        "model_type='jev', шлюз аўтаматычна генеруе строгі "
                                                        'JSON-промпт, валідуе верагоднасці і нармалізуе адказ у фармат '
                                                        'Jev.',
                                                        'Празрыстая сумяшчальнасць з Chat API: Эндпоінт POST '
                                                        '/v1/chat/completions празрыста апрацоўвае запыты рашэнняў, '
                                                        'дазваляючы працаваць праз стандартныя OpenAI SDK.',
                                                        'Падтрымка аліясаў: Эндпоінты POST /v1/systemone і POST '
                                                        '/v1/decisions узаемазаменныя і маюць ідэнтычную '
                                                        'функцыянальнасць.'],
                                              'zh': [   '原生零延迟直通：针对原生支持 System One 决策架构的服务商（如 '
                                                        'drex.nace、experientiallabs、typesafe.ai），网关直接透传专属协议，确保极致响应速度。',
                                                        '通用大模型结构化模拟：当将普通模型（如 '
                                                        'gemini-2.5-flash、gpt-4o-mini、claude-3-5-haiku 或本地 ollama）标记为 '
                                                        "model_type='jev' 时，网关自动注入严密的结构化 JSON Prompt，校准概率分布并封装为标准决策对象。",
                                                        '兼容 OpenAI Chat 端点：标准 POST /v1/chat/completions 接口可无缝接收 Jev '
                                                        '负载并自动按决策格式返回，现有 SDK 无需任何修改即可平滑接入。',
                                                        '双路由别名支持：POST /v1/systemone 与 POST /v1/decisions '
                                                        '完全等价，均可作为决策接口的主入口。'],
                                              'es': [   'Enrutamiento nativo sin latencia: Los proveedores '
                                                        'especializados (drex.nace, experientiallabs, typesafe.ai) '
                                                        'reciben solicitudes directas a System One con la menor '
                                                        'latencia posible.',
                                                        'Emulación estructurada para cualquier LLM: Si un modelo '
                                                        'conversacional general (ej. gemini-2.5-flash, gpt-4o-mini, '
                                                        "claude-3-5-haiku, ollama) tiene model_type='jev', MyAIrouter "
                                                        'construye automáticamente un prompt JSON estructurado '
                                                        'estricto y normaliza la respuesta.',
                                                        'Compatibilidad transparente con Chat API: El endpoint POST '
                                                        '/v1/chat/completions acepta solicitudes Jev y responde con el '
                                                        'esquema de decisiones estándar.',
                                                        'Soporte de alias: Tanto POST /v1/systemone como POST '
                                                        '/v1/decisions son idénticos y totalmente operativos.'],
                                              'fr': [   'Routage natif sans délai : Les fournisseurs spécialisés '
                                                        '(drex.nace, experientiallabs, typesafe.ai) reçoivent les '
                                                        'requêtes directes System One sans surcoût de latence.',
                                                        'Émulation JSON structurée universelle : Si un modèle '
                                                        'généraliste (ex. gemini-2.5-flash, gpt-4o-mini, '
                                                        'claude-3-5-haiku, ollama) est configuré avec '
                                                        "model_type='jev', MyAIrouter génère un prompt JSON strict et "
                                                        'normalise la réponse.',
                                                        'Compatibilité transparente avec Chat API : Le point de '
                                                        'terminaison POST /v1/chat/completions accepte les charges '
                                                        'utiles Jev et renvoie la structure de décision standard.',
                                                        "Prise en charge d'alias : POST /v1/systemone et POST "
                                                        '/v1/decisions sont totalement interchangeables.'],
                                              'de': [   'Natives Routing ohne Verzögerung: Spezialisierte Anbieter '
                                                        '(drex.nace, experientiallabs, typesafe.ai) erhalten direkte '
                                                        'Durchleitungen mit minimaler Latenz.',
                                                        'Universelle strukturierte JSON-Emulation: Wenn ein '
                                                        'Standard-LLM (z. B. gemini-2.5-flash, gpt-4o-mini, '
                                                        "claude-3-5-haiku, ollama) auf model_type='jev' gesetzt ist, "
                                                        'erzeugt MyAIrouter automatisch einen strengen JSON-Prompt und '
                                                        'normalisiert die Antwort.',
                                                        'Transparente Chat-API-Kompatibilität: Der Endpunkt POST '
                                                        '/v1/chat/completions verarbeitet Jev-Anfragen transparent und '
                                                        'liefert konforme Entscheidungsobjekte.',
                                                        'Alias-Unterstützung: Sowohl POST /v1/systemone als auch POST '
                                                        '/v1/decisions sind öffentlich verfügbar und funktional '
                                                        'identisch.'],
                                              'ja': [   'ネイティブゼロ遅延転送：System '
                                                        'One意思決定に対応した事業者（drex.nace、experientiallabs、typesafe.ai等）へのリクエストは変換なしで高速直結されます。',
                                                        '汎用LLM向け構造化JSON自動エミュレーション：通常モデル（gemini-2.5-flash、gpt-4o-mini、claude-3-5-haiku、ローカルollama等）に '
                                                        "model_type='jev' を指定した場合、厳格なJSONスキーマプロンプトを自動生成し出力を正規化します。",
                                                        'Chat APIとの透過的互換性：標準の POST /v1/chat/completions '
                                                        'でもJevペイロードを受け付け、意思決定レスポンスを返却可能です。',
                                                        'エイリアス対応：POST /v1/systemone と POST /v1/decisions '
                                                        'は完全に等価であり、同一の機能を提供します。'],
                                              'pt': [   'Roteamento nativo sem latência: Provedores especializados '
                                                        '(drex.nace, experientiallabs, typesafe.ai) recebem '
                                                        'requisições diretas com o menor tempo de resposta.',
                                                        'Emulação estruturada universal: Quando um modelo convencional '
                                                        '(ex: gemini-2.5-flash, gpt-4o-mini, claude-3-5-haiku, ollama) '
                                                        "tem model_type='jev', o MyAIrouter gera automaticamente "
                                                        'prompts JSON estruturados e valida as probabilidades.',
                                                        'Compatibilidade transparente com Chat API: O endpoint POST '
                                                        '/v1/chat/completions aceita cargas úteis Jev e retorna os '
                                                        'dados de decisão correspondentes.',
                                                        'Suporte a alias: POST /v1/systemone e POST /v1/decisions são '
                                                        'intercambiáveis e oferecem a mesma funcionalidade.'],
                                              'ar': [   'توجيه أصلي بدون تأخير: يتلقى المزودون المتخصصون (مثل '
                                                        'drex.nace وexperientiallabs وtypesafe.ai) الطلبات مباشرة إلى '
                                                        'محرك System One بأدنى زمن استجابة ممكن.',
                                                        "محاكاة JSON المنظمة لجميع النماذج: عند ضبط model_type='jev' "
                                                        'لأي نموذج محادثة عام (مثل gemini-2.5-flash أو gpt-4o-mini أو '
                                                        'claude-3-5-haiku أو ollama)، يقوم النظام تلقائياً بإنشاء موجه '
                                                        'JSON صارم ومعايرة الاحتمالات.',
                                                        'توافق شفاف مع Chat API: تقبل نقطة النهاية القياسية POST '
                                                        '/v1/chat/completions حمولات Jev وتعيد استجابة القرارات '
                                                        'المعتمدة.',
                                                        'دعم الأسماء المستعارة: كل من POST /v1/systemone وPOST '
                                                        '/v1/decisions يقدمان نفس الوظيفة تماماً.'],
                                              'hi': [   'नेटिव जीरो-डिले रूटिंग: सिस्टम वन में विशेषज्ञता रखने वाले '
                                                        'प्रदाता (drex.nace, experientiallabs, typesafe.ai) बिना किसी '
                                                        'विलंबता के सीधे अनुरोध प्राप्त करते हैं।',
                                                        'सार्वभौमिक एलएलएम स्ट्रक्चर्ड एमुलेशन: यदि किसी सामान्य मॉडल '
                                                        '(उदा. gemini-2.5-flash, gpt-4o-mini, claude-3-5-haiku, '
                                                        "ollama) में model_type='jev' सेट है, तो MyAIrouter स्वचालित "
                                                        'रूप से एक सख्त JSON प्रॉम्प्ट बनाकर आउटपुट को सामान्य करता '
                                                        'है।',
                                                        'पारदर्शी चैट कम्पैटिबिलिटी: मानक POST /v1/chat/completions '
                                                        'जेव पेलोड को पारदर्शी रूप से स्वीकार करता है और निर्णय परिणाम '
                                                        'देता है।',
                                                        'उपनाम (Alias) समर्थन: POST /v1/systemone और POST '
                                                        '/v1/decisions दोनों समान कार्यक्षमता प्रदान करते हैं।'],
                                              'bn': [   'নেটিভ জিরো-ডিলে রাউটিং: সিস্টেম ওয়ান ডিসিশনে বিশেষজ্ঞ '
                                                        'প্রদানকারীরা (যেমন drex.nace, experientiallabs, typesafe.ai) '
                                                        'ন্যূনতম লেটেন্সিতে সরাসরি অনুরোধ গ্রহণ করে।',
                                                        'ইউনিভার্সাল এলএলএম স্ট্রাকচার্ড এমুলেশন: যদি কোনো সাধারণ মডেল '
                                                        '(যেমন gemini-2.5-flash, gpt-4o-mini, claude-3-5-haiku, '
                                                        "ollama)-এ model_type='jev' থাকে, তবে MyAIrouter "
                                                        'স্বয়ংক্রিয়ভাবে একটি কঠোর JSON প্রম্পটের মাধ্যমে আউটপুট '
                                                        'প্রক্রিয়া করে।',
                                                        'স্বচ্ছ চ্যাট সামঞ্জস্য: স্ট্যান্ডার্ড POST '
                                                        '/v1/chat/completions জেভ পেলোড গ্রহণ করে স্বয়ংক্রিয়ভাবে '
                                                        'ডিসিশন রেসপন্স ফেরত দেয়।',
                                                        'উপনাম সমর্থন: POST /v1/systemone এবং POST /v1/decisions দুটি '
                                                        'এন্ডপয়েন্টই সম্পূর্ণ সমতুল্য।']}},
                           {   'titles': {   'en': 'Playground Studio & Visual Presets',
                                             'ru': 'Студия в Playground и готовые пресеты',
                                             'uk': 'Студія в Playground та готові пресети',
                                             'be': 'Студыя ў Playground і гатовыя прэсеты',
                                             'zh': 'Playground 可视化决策工作室与场景预设',
                                             'es': 'Estudio Playground y preajustes visuales',
                                             'fr': 'Studio Playground et préréglages visuels',
                                             'de': 'Playground-Studio & Visuelle Presets',
                                             'ja': 'Playground スタジオとプリセット機能',
                                             'pt': 'Estúdio no Playground e Predefinições Visuais',
                                             'ar': 'استوديو Playground والقوالب المرئية الجاهزة',
                                             'hi': 'प्लेग्राउंड स्टूडियो और विज़ुअल प्रीसेट',
                                             'bn': 'প্লেগ্রাউন্ড স্টুডিও এবং ভিজ্যুয়াল প্রিসেট'},
                               'bullets': {   'en': [   "Dedicated Studio Mode: Access the '⚡ Jev (System One)' tab in "
                                                        'the web console (/playground) to test discrete decision '
                                                        'models interactively.',
                                                        'State Context Editor: Provide rich context (user profiles, '
                                                        'audit logs, code diffs, financial transactions, or policy '
                                                        'documents) for the decision engine.',
                                                        'Visual Question Builder: Add questions, configure primitive '
                                                        'types (choice, score, noul), and specify discrete options '
                                                        'with live validation or toggle to raw JSON.',
                                                        '4 Built-in Presets: Instant one-click templates for Customer '
                                                        'Support Escalation, Content Moderation Guardrails, PR Code '
                                                        'Review, and Financial Fraud Risk.',
                                                        'Live Analytics & Export: Real-time calibrated probability '
                                                        'distribution bar charts, confidence gauges, and instant code '
                                                        'export for cURL, Python SDK, and Node.js.'],
                                              'ru': [   "Выделенный режим студии: Вкладка '⚡ Jev (System One)' в "
                                                        'веб-консоли (/playground) для интерактивного тестирования '
                                                        'моделей быстрых решений.',
                                                        'Редактор контекста State: Удобный ввод контекста (профиль '
                                                        'пользователя, лог аудита, диффы кода, транзакции или текст '
                                                        'политик).',
                                                        'Визуальный конструктор вопросов: Добавление вопросов, выбор '
                                                        'примитивов (choice, score, noul) и настройка опций с '
                                                        'мгновенной валидацией или переключением в JSON.',
                                                        '4 встроенных пресета: Готовые сценарии для эскалации '
                                                        'поддержки, модерации контента, ревью кода в PR и оценки '
                                                        'финансовых рисков.',
                                                        'Аналитика и экспорт: Наглядные гистограммы распределения '
                                                        'вероятностей, датчики уверенности и экспорт готового кода для '
                                                        'cURL, Python и Node.js.'],
                                              'uk': [   "Виділений режим студії: Вкладка '⚡ Jev (System One)' у "
                                                        'веб-консолі (/playground) для інтерактивного тестування '
                                                        'моделей швидких рішень.',
                                                        'Редактор контексту State: Зручне введення контексту (профіль '
                                                        'користувача, лог аудиту, дифи коду, транзакції або текст '
                                                        'політик).',
                                                        'Візуальний конструктор питань: Додавання питань, вибір '
                                                        'примітивів (choice, score, noul) та налаштування опцій із '
                                                        'миттєвою валідацією або перемиканням у JSON.',
                                                        '4 вбудовані пресети: Готові сценарії для ескалації підтримки, '
                                                        "модерації контенту, рев'ю коду в PR та оцінки фінансових "
                                                        'ризиків.',
                                                        'Аналітика та експорт: Наочні гістограми розподілу '
                                                        'ймовірностей, датчики впевненості та експорт готового коду '
                                                        'для cURL, Python і Node.js.'],
                                              'be': [   "Вылучаны рэжым студыі: Укладка '⚡ Jev (System One)' у "
                                                        'вэб-кансолі (/playground) для інтэрактыўнага тэсціравання '
                                                        'мадэляў хуткіх рашэнняў.',
                                                        'Рэдактар кантэксту State: Зручны ўвод кантэксту (профіль '
                                                        'карыстальніка, лог аўдыту, дыфы коду, транзакцыі або тэкст '
                                                        'палітык).',
                                                        'Візуальны канструктар пытанняў: Даданне пытанняў, выбар '
                                                        'прымітываў (choice, score, noul) і налада опцый з імгненнай '
                                                        'валідацыяй або пераключэннем у JSON.',
                                                        '4 убудаваныя прэсеты: Гатовыя сцэнарыі для эскалацыі '
                                                        'падтрымкі, мадэрацыі кантэнту, рэвю коду ў PR і ацэнкі '
                                                        'фінансавых рызык.',
                                                        'Аналітыка і экспарт: Наглядныя гістаграмы размеркавання '
                                                        'верагоднасцяў, датчыкі ўпэўненасці і экспарт гатовага коду '
                                                        'для cURL, Python і Node.js.'],
                                              'zh': [   "专属工作室模式：在 Web 控制台的 /playground 页面直接切换至 '⚡ Jev (System One)' "
                                                        '模式进行离散决策交互调试。',
                                                        'State 上下文编辑器：输入待评估的完整上下文信息（如客户会话、审计日志、代码审查 Diff、支付交易详情或合规准则）。',
                                                        '可视化原语构建器：轻松增删评估项，一键切换 choice、score、noul 原语类型并配置离散标签，支持无缝切换至底层 '
                                                        'Raw JSON 编辑。',
                                                        '内置4大场景预设：提供客服工单流转、内容安全审核、PR 代码合规审查、金融交易欺诈拦截等开箱即用的工业级预设。',
                                                        '实时概率图表与多语言代码导出：提供校准概率条形图、置信度指标盘与 cURL、Python、Node.js '
                                                        '快速接入代码生成。'],
                                              'es': [   "Modo de estudio dedicado: Pestaña '⚡ Jev (System One)' en la "
                                                        'consola web (/playground) para probar modelos de decisión de '
                                                        'forma interactiva.',
                                                        'Editor de contexto State: Inserte contextos completos '
                                                        '(perfiles de usuario, registros de auditoría, diffs de '
                                                        'código, transacciones o políticas).',
                                                        'Constructor visual de preguntas: Agregue preguntas, '
                                                        'seleccione primitivas (choice, score, noul) y especifique '
                                                        'opciones con validación en vivo o cambie a JSON puro.',
                                                        '4 preajustes integrados: Plantillas inmediatas para '
                                                        'derivación de soporte, moderación de contenido, revisión de '
                                                        'código PR y riesgo financiero.',
                                                        'Gráficos y exportación de código: Visualización de '
                                                        'distribuciones de probabilidad, medidores de confianza y '
                                                        'exportación de código a cURL, Python y Node.js.'],
                                              'fr': [   "Mode studio dédié : Onglet '⚡ Jev (System One)' dans la "
                                                        'console (/playground) pour tester interactivement les modèles '
                                                        'de décision.',
                                                        'Éditeur de contexte State : Renseignez le contexte à évaluer '
                                                        "(profil client, logs d'audit, diffs de code, transactions "
                                                        'bancaires, politiques de sécurité).',
                                                        'Générateur visuel de questions : Ajoutez des questions, '
                                                        'sélectionnez les types (choice, score, noul) et définissez '
                                                        'les options avec bascule en JSON brut.',
                                                        "4 préréglages prêts à l'emploi : Modèles pour l'escalade du "
                                                        'support, la modération de contenu, la revue de code PR et le '
                                                        'risque de fraude financière.',
                                                        'Graphiques et export de code : Diagrammes de probabilité '
                                                        'calibrés, jauges de confiance et export de code pour cURL, '
                                                        'Python et Node.js.'],
                                              'de': [   "Dedizierter Studio-Modus: Eigener Tab '⚡ Jev (System One)' im "
                                                        'Playground (/playground) zur interaktiven Evaluierung '
                                                        'diskreter Entscheidungen.',
                                                        'State-Kontext-Editor: Bereitstellung von Kontextdaten '
                                                        '(Benutzerprofile, Audit-Logs, Code-Diffs, Finanztransaktionen '
                                                        'oder Richtlinientexte).',
                                                        'Visueller Fragen-Builder: Fragen hinzufügen, Primitive '
                                                        '(choice, score, noul) auswählen und Optionen konfigurieren '
                                                        'oder direkt im Raw JSON editieren.',
                                                        '4 integrierte Vorlagen: Vordefinierte Szenarien für '
                                                        'Support-Eskalation, Content-Moderation, PR-Code-Review und '
                                                        'Betrugserkennung.',
                                                        'Live-Visualisierung & Code-Export: Wahrscheinlichkeitsbalken, '
                                                        'Konfidenzanzeigen und Ein-Klick-Code-Generierung für cURL, '
                                                        'Python und Node.js.'],
                                              'ja': [   '専用スタジオモード：Webコンソールの /playground 内にある「⚡ Jev（System '
                                                        'One）」タブから対話形式で意思決定テストが可能。',
                                                        'Stateコンテキスト入力：ユーザー履歴、監査ログ、コード差分、金融取引情報、セキュリティ規約などの文脈を柔軟に入力。',
                                                        'ビジュアル質問ビルダー：質問項目の追加、プリミティブ型（choice、score、noul）の選択、選択肢の設定をGUIで行え、Raw '
                                                        'JSONの直接編集も可能。',
                                                        '4つの実用プリセット：カスタマーサポート対応、コンテンツ審査、PRコードレビュー、金融不正検知のテンプレートを即座に呼び出し可能。',
                                                        'リアルタイム確率可視化とコード出力：確率分布バーグラフ、信頼度メーター、cURL・Python・Node.js '
                                                        '向けの接続コード自動生成。'],
                                              'pt': [   "Modo de estúdio dedicado: Aba '⚡ Jev (System One)' no console "
                                                        'web (/playground) para testar modelos de decisão '
                                                        'interativamente.',
                                                        'Editor de contexto State: Forneça contextos completos (perfis '
                                                        'de usuário, logs de auditoria, diffs de código, transações ou '
                                                        'políticas).',
                                                        'Construtor visual de perguntas: Adicione perguntas, selecione '
                                                        'tipos de primitivas (choice, score, noul) e defina opções com '
                                                        'validação em tempo real.',
                                                        '4 predefinições integradas: Cenários prontos para '
                                                        'escalonamento de suporte, moderação de conteúdo, revisão de '
                                                        'código e risco de fraude.',
                                                        'Gráficos e exportação de código: Gráficos de barras de '
                                                        'probabilidade calibrada, medidores de confiança e exportação '
                                                        'de código cURL, Python e Node.js.'],
                                              'ar': [   "وضع استوديو مخصص: تبويب '⚡ Jev (System One)' في واجهة الويب "
                                                        '(/playground) لاختبار نماذج اتخاذ القرارات السريعة بشكل '
                                                        'تفاعلي.',
                                                        'محرر سياق الحالة State: إدخال السياق المطلوب تقييمه (سجلات '
                                                        'الأمان، محادثات العملاء، الفروقات البرمجية، أو المعاملات '
                                                        'المالية).',
                                                        'منشئ الأسئلة المرئي: إضافة الأسئلة واختيار نوع الأولية '
                                                        '(choice, score, noul) وضبط الخيارات مع إمكانية التبديل إلى '
                                                        'JSON الخام.',
                                                        '4 قوالب مدمجة: سيناريوهات جاهزة لتصعيد دعم العملاء، وإشراف '
                                                        'المحتوى، ومراجعة الأكواد البرمجية، ومخاطر الاحتيال المالي.',
                                                        'مخططات احتمالية وتصدير الكود: رسوم بيانية للتوزيع الاحتمالي '
                                                        'ومؤشرات الثقة مع تصدير الأكواد بضغطة زر لـ cURL وPython '
                                                        'وNode.js.'],
                                              'hi': [   'समर्पित स्टूडियो मोड: त्वरित निर्णय मॉडल का परीक्षण करने के '
                                                        "लिए वेब कंसोल (/playground) में '⚡ Jev (System One)' टैब।",
                                                        'State संदर्भ संपादक: मूल्यांकन के लिए समृद्ध संदर्भ '
                                                        '(उपयोगकर्ता प्रोफ़ाइल, ऑडिट लॉग, कोड डिफ, वित्तीय लेनदेन) '
                                                        'दर्ज करें।',
                                                        'विज़ुअल प्रश्न निर्माता: प्रश्न जोड़ें, प्रिमिटिव प्रकार '
                                                        '(choice, score, noul) चुनें और सीधे JSON में टॉगल करें।',
                                                        '4 अंतर्निहित प्रीसेट: ग्राहक सहायता एस्केलेशन, सामग्री '
                                                        'मॉडरेशन, पीआर कोड समीक्षा, और वित्तीय धोखाधड़ी जोखिम के लिए '
                                                        'रेडीमेड टेम्पलेट।',
                                                        'लाइव एनालिटिक्स और कोड निर्यात: वास्तविक समय प्रायिकता बार '
                                                        'चार्ट, विश्वास गेज और cURL, Python, Node.js के लिए त्वरित कोड '
                                                        'जनरेशन।'],
                                              'bn': [   "ডেডিকেটেড স্টুডিও মোড: ওয়েব কনসোলে (/playground) '⚡ Jev "
                                                        "(System One)' ট্যাবের মাধ্যমে ডিসিশন মডেল ইন্টারঅ্যাক্টিভভাবে "
                                                        'পরীক্ষা করুন।',
                                                        'State কনটেক্সট এডিটর: মূল্যায়নের জন্য সম্পূর্ণ বিবরণ (ইউজার '
                                                        'প্রোফাইল, অডিট লগ, কোড ডিফস, লেনদেন বা পলিসি ডকুমেন্ট) প্রদান '
                                                        'করুন।',
                                                        'ভিজ্যুয়াল প্রশ্ন নির্মাতা: প্রশ্ন যোগ করুন, প্রিমিটিভের ধরন '
                                                        "(choice, score, noul) নির্বাচন করুন এবং সরাসরি র' JSON-এ "
                                                        'স্যুইচ করুন।',
                                                        '৪টি প্রস্তুত প্রিসেট: কাস্টমার সাপোর্ট এস্কেলেশন, কনটেন্ট '
                                                        'মডারেশন, পিআর কোড রিভিউ এবং আর্থিক জালিয়াতি ঝুঁকির জন্য '
                                                        'রেডিমেড টেমপ্লেট।',
                                                        'লাইভ চার্ট ও কোড এক্সপোর্ট: ক্যালিব্রেটেড সম্ভাব্যতা বার '
                                                        'চার্ট, কনফিডেন্স গজ এবং cURL, Python, Node.js-এর জন্য '
                                                        'তাৎক্ষণিক কোড রপ্তানি।']}}]}]
