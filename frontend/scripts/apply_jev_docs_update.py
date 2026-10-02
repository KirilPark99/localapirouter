#!/usr/bin/env python3
"""
apply_jev_docs_update.py
Applies Jev System One documentation updates across all 13 languages to:
- frontend/scripts/sections_data_part1.py (overview, models, jev-systemone)
- frontend/scripts/sections_data_part2.py (api-reference)
"""

import sys
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

import sections_data_part1
import sections_data_part2

# 1. Update overview in SECTIONS_PART1
overview = None
for s in sections_data_part1.SECTIONS_PART1:
    if s["id"] == "overview":
        overview = s
        break

if overview:
    overview["descriptions"] = {
        "en": "Universal self-hosted LLM gateway with Direct, Priority Fallback, Model Fusion, and Jev System One decision engines, multi-provider key pooling, and Ollama compatibility.",
        "ru": "Универсальный self-hosted ИИ-шлюз с 4 движками маршрутизации (Direct, Priority Fallback, Fusion, Jev System One), пулом ключей и поддержкой протоколов OpenAI и Ollama.",
        "uk": "Універсальний self-hosted ШІ-шлюз із 4 механізмами маршрутизації (Direct, Priority Fallback, Fusion, Jev System One), пулом ключів та підтримкою протоколів OpenAI й Ollama.",
        "be": "Універсальны self-hosted ШІ-шлюз з 4 рухавікамі маршрутызацыі (Direct, Priority Fallback, Fusion, Jev System One), пулам ключоў і падтрымкай OpenAI і Ollama.",
        "zh": "自托管通用大模型网关，内置直连、优先级回退、模型融合与 Jev 快决策四大引擎，支持多提供商密钥池和 Ollama 协议兼容。",
        "es": "Pasarela LLM autohospedada universal con motores Direct, Priority Fallback, Model Fusion y decisiones Jev System One, agrupación de claves y compatibilidad con Ollama.",
        "fr": "Passerelle LLM auto-hébergée universelle avec moteurs Direct, Repli prioritaire, Fusion et décisions Jev System One, mutualisation de clés et compatibilité Ollama.",
        "de": "Universelles, selbst gehostetes LLM-Gateway mit Direct-, Priority-Fallback-, Fusion- und Jev System One Entscheidungs-Engines, Key-Pooling und Ollama-Kompatibilität.",
        "ja": "Direct、Priority Fallback、Model Fusion、Jev System Oneの4つのルーティングエンジンとOllama互換性を備えたセルフホスト型LLMゲートウェイ。",
        "pt": "Gateway LLM universal auto-hospedado com motores Direct, Priority Fallback, Model Fusion e decisões Jev System One, pool de chaves e compatibilidade com Ollama.",
        "ar": "بوابة نماذج لغوية ذاتية الاستضافة مع 4 محركات توجيه (المباشر، الاحتياطي، الدمج، وقرارات Jev System One)، وتجمع المفاتيح وتوافق Ollama.",
        "hi": "यूनिवर्सल सेल्फ-होस्टेड एलएलएम गेटवे: डायरेक्ट, प्रायोरिटी फॉलबैक, मॉडल फ्यूजन और जेव (Jev) सिस्टम वन डिसीजन इंजन, मल्टी-प्रोवाइडर की-पूलिंग और ओलामा कम्पैटिबिलिटी।",
        "bn": "ইউনিভার্সাল সেলফ-হোস্টেড এলএলএম গেটওয়ে: ডাইরেক্ট, প্রায়োরিটি ফলব্যাক, মডেল ফিউশন এবং জেভ (Jev) সিস্টেম ওয়ান ডিসিশন ইঞ্জিন, মাল্টি-প্রোভাইডার কি পুলিং এবং ওলামা সামঞ্জস্য।"
    }

    overview["highlights"] = {
        "en": [
            "4 Routing Engines: Direct, Priority Fallback (nested), Model Fusion (judge ensembles), and Jev System One Decisions",
            "OpenAI API (/v1/chat/completions) & Ollama (/api/tags, /api/show) drop-in compatibility",
            "Enterprise Key Security: AES-128-CBC Fernet encryption with ROUTER_MASTER_KEY",
            "Circuit Breaker fault isolation with automatic recovery & geo-proxy binding"
        ],
        "ru": [
            "4 движка маршрутизации: Прямой, Приоритетный Fallback (вложенный), Ансамбль Model Fusion и Решения Jev System One",
            "Совместимость с протоколами OpenAI (/v1/chat/completions) и Ollama (/api/tags, /api/show)",
            "Надежное шифрование ключей: AES-128-CBC Fernet под управлением ROUTER_MASTER_KEY",
            "Автоматический Circuit Breaker с самовосстановлением и привязкой гео-прокси"
        ],
        "uk": [
            "4 рушії маршрутизації: Прямий, Пріоритетний Fallback (вкладений), Ансамбль Model Fusion та Рішення Jev System One",
            "Повна сумісність з OpenAI API (/v1/chat/completions) та Ollama (/api/tags, /api/show)",
            "Надійне шифрування ключів: AES-128-CBC Fernet під контролем ROUTER_MASTER_KEY",
            "Автоматичний Circuit Breaker із самовідновленням та прив'язкою гео-проксі"
        ],
        "be": [
            "4 рухавікі маршрутызацыі: Прамы, Прыярытэтны Fallback (укладзены), Ансамбль Model Fusion і Рашэнні Jev System One",
            "Поўная сумяшчальнасць з OpenAI API (/v1/chat/completions) і Ollama (/api/tags, /api/show)",
            "Надзейнае шыфраванне ключоў: AES-128-CBC Fernet пад кіраваннем ROUTER_MASTER_KEY",
            "Аўтаматычны Circuit Breaker з самааднаўленнем і прывязкай геа-проксі"
        ],
        "zh": [
            "四大路由引擎：直连路由、优先级回退（支持嵌套）、模型融合评审团与 Jev 快决策 (System One)",
            "完美兼容 OpenAI API (/v1/chat/completions) 与 Ollama (/api/tags, /api/show)",
            "企业级安全：基于 ROUTER_MASTER_KEY 的 AES-128-CBC Fernet 密钥加密存储",
            "断路器自动隔离故障节点，支持健康检测自愈与独立代理绑定"
        ],
        "es": [
            "4 motores de enrutamiento: Directo, Fallback prioritario (anidado), Fusión de modelos y Decisiones Jev System One",
            "Compatibilidad total con API OpenAI (/v1/chat/completions) y Ollama (/api/tags, /api/show)",
            "Seguridad empresarial: cifrado AES-128-CBC Fernet mediante ROUTER_MASTER_KEY",
            "Aislamiento de fallos por Circuit Breaker con autorrecuperación y proxies geo"
        ],
        "fr": [
            "4 moteurs de routage : Direct, Repli prioritaire (imbriqué), Fusion de modèles et Décisions Jev System One",
            "Compatibilité directe avec l'API OpenAI (/v1/chat/completions) et Ollama (/api/tags)",
            "Sécurité renforcée : chiffrement AES-128-CBC Fernet via ROUTER_MASTER_KEY",
            "Disjoncteur automatique (Circuit Breaker) avec auto-guérison et liaison proxy"
        ],
        "de": [
            "4 Routing-Engines: Direkt, Prioritäts-Fallback (verschachtelt), Modell-Fusion und Jev System One Decisions",
            "Kompatibel mit OpenAI-API (/v1/chat/completions) und Ollama (/api/tags, /api/show)",
            "Sichere Schlüsselverwaltung: AES-128-CBC Fernet-Verschlüsselung mit ROUTER_MASTER_KEY",
            "Circuit Breaker zur automatischen Fehlerisolation mit Geo-Proxy-Unterstützung"
        ],
        "ja": [
            "4つのルーティングエンジン：ダイレクト、優先度フォールバック（入れ子対応）、モデル融合、およびJev System One意思決定",
            "OpenAI API (/v1/chat/completions) および Ollama (/api/tags) との完全互換",
            "強固なセキュリティ：ROUTER_MASTER_KEY による AES-128-CBC 暗号化",
            "サーキットブレーカーによる障害自動隔離とジオプロキシ連携"
        ],
        "pt": [
            "4 motores de roteamento: Direto, Fallback prioritário (aninhado), Fusão de modelos e Decisões Jev System One",
            "Compatibilidade total com OpenAI API (/v1/chat/completions) e Ollama (/api/tags)",
            "Segurança avançada: criptografia AES-128-CBC Fernet usando ROUTER_MASTER_KEY",
            "Isolamento automático de falhas com Circuit Breaker e suporte a proxies"
        ],
        "ar": [
            "4 محركات توجيه: المباشر، والاحتياطي ذو الأولوية (المتداخل)، ودمج النماذج، وقرارات Jev System One السريعة",
            "توافق فوري مع واجهات OpenAI (/v1/chat/completions) وOllama (/api/tags)",
            "تشفير عالي الأمان: AES-128-CBC Fernet محمي بمفتاح ROUTER_MASTER_KEY",
            "قاطع الدائرة الكهربائية (Circuit Breaker) لعزل الأعطال مع دعم البروكسي الجغرافي"
        ],
        "hi": [
            "4 रूटिंग इंजन: डायरेक्ट, प्रायोरिटी फॉलबैक (नेस्टेड), मॉडल फ्यूजन और जेव (Jev) सिस्टम वन डिसीजन",
            "ओपनएआई एपीआई (/v1/chat/completions) और ओलामा (/api/tags) के साथ पूर्ण कम्पैटिबिलिटी",
            "एंटरप्राइज सुरक्षा: ROUTER_MASTER_KEY द्वारा प्रबंधित AES-128-CBC फ़र्नेट एन्क्रिप्शन",
            "सर्किट ब्रेकर द्वारा स्वचालित विफलता अलगाव और प्रॉक्सी कनेक्टिविटी"
        ],
        "bn": [
            "৪টি রাউটিং ইঞ্জিন: ডাইরেক্ট, প্রায়োরিটি ফলব্যাক (নেস্টেড), মডেল ফিউশন এবং জেভ (Jev) সিস্টেম ওয়ান ডিসিশন",
            "OpenAI API (/v1/chat/completions) এবং Ollama (/api/tags) এর সাথে সম্পূর্ণ সামঞ্জস্য",
            "নিরাপদ কী স্টোরেজ: ROUTER_MASTER_KEY চালিত AES-128-CBC ফার্নেট এনক্রিপশন",
            "সার্কিট ব্রেকার স্বয়ংক্রিয় ত্রুটি বিচ্ছিন্নকরণ এবং প্রক্সি ইন্টিগ্রেশন"
        ]
    }

    # Add row to Routing Modes Comparison table
    if overview.get("subsections"):
        for sub in overview["subsections"]:
            if "table" in sub and "rows" in sub["table"]:
                jev_row = ["Jev System One", "direct, /v1/systemone, jev/*", "Discrete Decision Primitives", "Fast rubric & choice evaluation with calibrated probabilities", "Ultra-low / Instant"]
                if len(sub["table"]["rows"]) == 3:
                    sub["table"]["rows"].append(jev_row)


# 2. Update models section in SECTIONS_PART1: add Model Types subsection
models_sec = None
for s in sections_data_part1.SECTIONS_PART1:
    if s["id"] == "models":
        models_sec = s
        break

if models_sec:
    model_type_sub = {
        "titles": {
            "en": "Model Types: OpenAI Compatible vs ⚡ Jev (System One)",
            "ru": "Типы моделей: OpenAI-совместимые vs ⚡ Jev (System One)",
            "uk": "Типи моделей: OpenAI-сумісні vs ⚡ Jev (System One)",
            "be": "Тыпы мадэляў: OpenAI-сумяшчальныя vs ⚡ Jev (System One)",
            "zh": "模型执行类型：OpenAI 兼容模式 vs ⚡ Jev 快决策",
            "es": "Tipos de modelos: Compatible con OpenAI vs ⚡ Jev (System One)",
            "fr": "Types de modèles : Compatible OpenAI vs ⚡ Jev (System One)",
            "de": "Modelltypen: OpenAI-kompatibel vs. ⚡ Jev (System One)",
            "ja": "モデルタイプ：OpenAI互換 vs ⚡ Jev（System One意思決定）",
            "pt": "Tipos de Modelos: Compatível com OpenAI vs ⚡ Jev (System One)",
            "ar": "أنواع النماذج: متوافقة مع OpenAI مقابل ⚡ Jev (System One)",
            "hi": "मॉडल प्रकार: ओपनएआई (OpenAI) संगत बनाम ⚡ जेव (Jev System One)",
            "bn": "মডেলের প্রকারভেদ: ওপেনএআই সামঞ্জস্যপূর্ণ বনাম ⚡ জেভ (Jev System One)"
        },
        "descriptions": {
            "en": "MyAIrouter allows configuring the execution mode for every model in the catalog: default OpenAI compatible or high-speed Jev System One decision engine.",
            "ru": "MyAIrouter позволяет настраивать режим работы для каждой модели в каталоге: стандартный OpenAI-совместимый по умолчанию или высокоскоростной движок решений Jev System One.",
            "uk": "MyAIrouter дозволяє налаштовувати режим роботи для кожної моделі в каталозі: стандартний OpenAI-сумісний за замовчуванням або високошвидкісний рушій рішень Jev System One.",
            "be": "MyAIrouter дазваляе наладжваць рэжым працы для кожнай мадэлі ў каталогу: стандартны OpenAI-сумяшчальны па змаўчанні або высакахуткасны рухавік рашэнняў Jev System One.",
            "zh": "MyAIrouter 支持为模型目录中的每一款模型独立配置执行模式：默认的 OpenAI 兼容模式或高并发 Jev System One 快速决策引擎。",
            "es": "MyAIrouter permite configurar el modo de ejecución para cada modelo del catálogo: compatible con OpenAI por defecto o motor de decisiones rápido Jev System One.",
            "fr": "MyAIrouter permet de configurer le mode d'exécution de chaque modèle du catalogue : compatible OpenAI par défaut ou moteur de décision rapide Jev System One.",
            "de": "MyAIrouter ermöglicht die Konfiguration des Ausführungsmodus für jedes Modell im Katalog: standardmäßig OpenAI-kompatibel oder als schnelle Jev System One Entscheidungs-Engine.",
            "ja": "MyAIrouter ではカタログ内の各モデルに対して、デフォルトのOpenAI互換モードまたは高速なJev System One意思決定エンジンモードを設定できます。",
            "pt": "O MyAIrouter permite configurar o modo de execução de cada modelo no catálogo: padrão compatível com OpenAI ou motor de decisões rápidas Jev System One.",
            "ar": "يتيح MyAIrouter تحديد وضع التشغيل لكل نموذج في الدليل: الوضع الافتراضي المتوافق مع OpenAI أو محرك اتخاذ القرارات السريع Jev System One.",
            "hi": "MyAIrouter कैटलॉग में प्रत्येक मॉडल के लिए निष्पादन मोड कॉन्फ़िगर करने की अनुमति देता है: डिफ़ॉल्ट ओपनएआई कम्पैटिबल या हाई-स्पीड जेव (Jev) सिस्टम वन डिसीजन इंजन।",
            "bn": "MyAIrouter ক্যাটালগের প্রতিটি মডেলের জন্য এক্সিকিউশন মোড কনফিগার করতে দেয়: ডিফল্ট ওপেনএআই সামঞ্জস্যপূর্ণ বা উচ্চ-গতির জেভ (Jev) সিস্টেম ওয়ান ডিসিশন ইঞ্জিন।"
        },
        "bullets": {
            "en": [
                "Default Model Type ('openai'): Standard conversational generation, reasoning tokens, and streaming across OpenAI, Gemini, Anthropic, Ollama, etc.",
                "Jev Mode ('jev'): Fast System One decision evaluation against discrete criteria (choice, score, noul) with calibrated probabilities.",
                "Native Execution vs Emulation: Native providers (drex.nace, experientiallabs) receive zero-overhead direct payloads; general LLMs (GPT, Claude, Gemini, Groq) run via automatic structured JSON emulation.",
                "Catalog Management: Filter models with quick chips ('All Types', 'OpenAI', '⚡ Jev'), edit single models, or use the batch modal ('Set Model Type') in the UI.",
                "API Exposure: The model_type field ('openai' | 'jev') is exposed in GET /v1/models and GET /v1/models/{id}."
            ],
            "ru": [
                "Тип модели по умолчанию ('openai'): Стандартная генерация текста, CoT-рассуждения и стриминг (OpenAI, Gemini, Anthropic, Ollama и др.).",
                "Режим Jev ('jev'): Быстрые решения System One по дискретным рубрикам (choice, score, noul) с калиброванными вероятностями.",
                "Нативный запуск vs Эмуляция: Нативные провайдеры (drex.nace, experientiallabs) получают прямой запрос без задержек; универсальные LLM (GPT, Claude, Gemini, Groq) эмулируются через структурированный JSON.",
                "Управление каталогом: Быстрые фильтры ('Все типы', 'OpenAI', '⚡ Jev'), одиночное редактирование и массовое обновление ('Set Model Type') в интерфейсе.",
                "Поддержка API: Поле model_type ('openai' | 'jev') возвращается в GET /v1/models и GET /v1/models/{id}."
            ],
            "uk": [
                "Тип моделі за замовчуванням ('openai'): Стандартна генерація тексту, міркування CoT та стрімінг (OpenAI, Gemini, Anthropic, Ollama тощо).",
                "Режим Jev ('jev'): Швидкі рішення System One за дискретними критеріями (choice, score, noul) із каліброваними ймовірностями.",
                "Нативний запуск vs Емуляція: Нативні провайдери (drex.nace, experientiallabs) отримують прямий запит без затримок; універсальні LLM (GPT, Claude, Gemini, Groq) емулюються через структурований JSON.",
                "Керування каталогом: Швидкі фільтри ('Всі типи', 'OpenAI', '⚡ Jev'), редагування моделі та масове оновлення ('Set Model Type') в інтерфейсі.",
                "Підтримка API: Поле model_type ('openai' | 'jev') повертається в GET /v1/models та GET /v1/models/{id}."
            ],
            "be": [
                "Тып мадэлі па змаўчанні ('openai'): Стандартная генерацыя тэксту, развагі CoT і стрымінг (OpenAI, Gemini, Anthropic, Ollama і інш.).",
                "Рэжым Jev ('jev'): Хуткія рашэнні System One па дыскрэтных крытэрыях (choice, score, noul) з калібраванымі верагоднасцямі.",
                "Натыўны запуск vs Эмуляцыя: Натыўныя правайдэры (drex.nace, experientiallabs) атрымліваюць прамы запыт без затрымак; універсальныя LLM (GPT, Claude, Gemini, Groq) эмулююцца праз структураваны JSON.",
                "Кіраванне каталогам: Хуткія фільтры ('Усе тыпы', 'OpenAI', '⚡ Jev'), рэдагаванне мадэлі і масавае абнаўленне ('Set Model Type') у інтэрфейсе.",
                "Падтрымка API: Поле model_type ('openai' | 'jev') вяртаецца ў GET /v1/models і GET /v1/models/{id}."
            ],
            "zh": [
                "默认模型类型 ('openai')：支持标准的多轮对话、思维链推理与流式响应（涵盖 OpenAI、Gemini、Anthropic、Ollama 等）。",
                "Jev 决策模式 ('jev')：专用于 System One 快速离散评估（choice 选项、score 评分、noul 判定）并输出校准概率分布。",
                "原生执行与智能模拟：原生 Jev 服务商（drex.nace、experientiallabs）享受零延迟直传；通用大模型（GPT、Claude、Gemini、Groq）自动通过结构化 JSON 提示词无缝模拟。",
                "目录快捷管理：支持筛选标签（'All Types'、'OpenAI'、'⚡ Jev'）、单模型弹窗编辑与批量批量切换（'Set Model Type'）。",
                "API 字段支持：GET /v1/models 与 GET /v1/models/{id} 接口均完整返回 model_type 属性。"
            ],
            "es": [
                "Tipo predeterminado ('openai'): Generación de texto conversacional estándar, tokens de razonamiento y streaming (OpenAI, Gemini, Anthropic, Ollama, etc.).",
                "Modo Jev ('jev'): Evaluación rápida de decisiones System One frente a criterios discretos (choice, score, noul) con probabilidades calibradas.",
                "Ejecución nativa vs Emulación: Los proveedores nativos (drex.nace, experientiallabs) reciben solicitudes directas sin retardo; los LLM generales (GPT, Claude, Gemini, Groq) se emulan mediante JSON estructurado.",
                "Gestión del catálogo: Filtros rápidos ('All Types', 'OpenAI', '⚡ Jev'), edición individual y actualización masiva ('Set Model Type') en la interfaz.",
                "Soporte API: El campo model_type ('openai' | 'jev') se incluye en GET /v1/models y GET /v1/models/{id}."
            ],
            "fr": [
                "Type par défaut ('openai') : Génération de texte standard, jetons de raisonnement et streaming (OpenAI, Gemini, Anthropic, Ollama, etc.).",
                "Mode Jev ('jev') : Évaluation rapide de décisions System One selon des rubriques discrètes (choice, score, noul) avec probabilités calibrées.",
                "Exécution native vs Émulation : Les fournisseurs natifs (drex.nace, experientiallabs) reçoivent des requêtes directes sans surcoût ; les LLM généraux (GPT, Claude, Gemini, Groq) sont émulés via JSON structuré.",
                "Gestion du catalogue : Filtres rapides ('All Types', 'OpenAI', '⚡ Jev'), édition unitaire et mise à jour groupée ('Set Model Type') dans l'interface.",
                "Support API : Le champ model_type ('openai' | 'jev') est retourné par GET /v1/models et GET /v1/models/{id}."
            ],
            "de": [
                "Standard-Modelltyp ('openai'): Konventionelle Textgenerierung, Reasoning-Tokens und Streaming für OpenAI, Gemini, Anthropic, Ollama usw.",
                "Jev-Modus ('jev'): Schnelle System One Entscheidungsbewertung anhand diskreter Kriterien (choice, score, noul) mit kalibrierten Wahrscheinlichkeiten.",
                "Native Ausführung vs. Emulation: Native Provider (drex.nace, experientiallabs) erhalten direkte Payloads ohne Latenz; Standard-LLMs (GPT, Claude, Gemini, Groq) werden über strukturiertes JSON emuliert.",
                "Katalogverwaltung: Filter-Chips ('All Types', 'OpenAI', '⚡ Jev'), Einzelbearbeitung und Stapelaktualisierung ('Set Model Type') im Webinterface.",
                "API-Unterstützung: Das Feld model_type ('openai' | 'jev') wird in GET /v1/models und GET /v1/models/{id} zurückgegeben."
            ],
            "ja": [
                "デフォルトモデルタイプ（'openai'）：通常のテキスト対話生成、推論トークン、ストリーミングに対応（OpenAI、Gemini、Anthropic、Ollama等）。",
                "Jevモード（'jev'）：離散ルーブリック（choice、score、noul）に対する校正済み確率を算出する高速System One意思決定エンジン。",
                "ネイティブ実行 vs エミュレーション：ネイティブ事業者（drex.nace、experientiallabs）には遅延ゼロで直結。汎用LLM（GPT、Claude、Gemini、Groq）は構造化JSONプロンプトで自動エミュレート。",
                "カタログ管理機能：クイックフィルター（'All Types'、'OpenAI'、'⚡ Jev'）、個別編集ダイアログ、一括変更モーダル（'Set Model Type'）を搭載。",
                "APIレスポンス：GET /v1/models および GET /v1/models/{id} で model_type（'openai' | 'jev'）を返却。"
            ],
            "pt": [
                "Tipo padrão ('openai'): Geração de texto conversacional padrão, tokens de raciocínio e streaming (OpenAI, Gemini, Anthropic, Ollama, etc.).",
                "Modo Jev ('jev'): Avaliação rápida de decisões System One contra critérios discretos (choice, score, noul) com probabilidades calibradas.",
                "Execução nativa vs Emulação: Provedores nativos (drex.nace, experientiallabs) recebem requisições diretas sem overhead; LLMs gerais (GPT, Claude, Gemini, Groq) são emulados via JSON estruturado.",
                "Gerenciamento do catálogo: Filtros rápidos ('All Types', 'OpenAI', '⚡ Jev'), edição individual e atualização em lote ('Set Model Type') na interface.",
                "Suporte na API: O campo model_type ('openai' | 'jev') é retornado em GET /v1/models e GET /v1/models/{id}."
            ],
            "ar": [
                "نوع النموذج الافتراضي ('openai'): التوليد النصي التحاوري القياسي، وتفكير CoT، والبث المباشر (OpenAI, Gemini, Anthropic, Ollama وغيرها).",
                "وضع Jev ('jev'): تقييم سريع للقرارات (System One) بناءً على معايير محددة (choice, score, noul) مع احتمالات معايرة دقيقة.",
                "التنفيذ الأصلي مقابل المحاكاة: المزودون الأصليون (drex.nace, experientiallabs) يتلقون الحمولات مباشرة دون تأخير؛ النماذج العامة (GPT, Claude, Gemini, Groq) تُحاكى تلقائياً عبر JSON المنظم.",
                "إدارة الدليل: تصفية سريعة بالوسوم ('All Types', 'OpenAI', '⚡ Jev')، وتعديل فردي، وتحديث جماعي ('Set Model Type') في واجهة الويب.",
                "واجهة API: يُرجع حقل model_type ('openai' | 'jev') في طلبات GET /v1/models وGET /v1/models/{id}."
            ],
            "hi": [
                "डिफ़ॉल्ट मॉडल प्रकार ('openai'): मानक टेक्स्ट जनरेशन, रीज़निंग टोकन और स्ट्रीमिंग (OpenAI, Gemini, Anthropic, Ollama आदि)।",
                "जेव मोड ('jev'): कैलिब्रेटेड प्रायिकताओं के साथ असतत मानदंडों (choice, score, noul) पर त्वरित सिस्टम वन निर्णय मूल्यांकन।",
                "नेटिव बनाम एमुलेशन: नेटिव प्रदाताओं (drex.nace, experientiallabs) को शून्य विलंबता के साथ सीधे पेलोड मिलते हैं; सामान्य LLM (GPT, Claude, Gemini, Groq) स्वचालित संरचित JSON द्वारा एमुलेट होते हैं।",
                "कैटलॉग प्रबंधन: क्विक फिल्टर ('All Types', 'OpenAI', '⚡ Jev'), एकल मॉडल संपादन, और वेब यूआई में बैच अपडेट ('Set Model Type')।",
                "एपीआई समर्थन: model_type फ़ील्ड ('openai' | 'jev') GET /v1/models और GET /v1/models/{id} में लौटाया जाता है।"
            ],
            "bn": [
                "ডিফল্ট মডেলের ধরন ('openai'): স্ট্যান্ডার্ড টেক্সট জেনারেশন, রিজনিং টোকেন এবং স্ট্রিমিং (OpenAI, Gemini, Anthropic, Ollama ইত্যাদি)।",
                "জেভ মোড ('jev'): ক্যালিব্রেটেড সম্ভাব্যতা সহ ডিসক্রিট মানদণ্ডের (choice, score, noul) উপর ভিত্তি করে দ্রুত সিস্টেম ওয়ান সিদ্ধান্ত মূল্যায়ন।",
                "নেটিভ বনাম এমুলেশন: নেটিভ প্রোভাইডার (drex.nace, experientiallabs) সরাসরি জিরো-লেটেন্সি পেলোড পায়; সাধারণ এলএলএম (GPT, Claude, Gemini, Groq) স্বয়ংক্রিয় কাঠামোগত JSON এমুলেশনের মাধ্যমে চালিত হয়।",
                "ক্যাটালগ পরিচালনা: দ্রুত ফিল্টার চিপস ('All Types', 'OpenAI', '⚡ Jev'), একক মডেল সম্পাদনা এবং ওয়েব ইউআই-তে ব্যাচ আপডেট ('Set Model Type')।",
                "এপিআই সমর্থন: model_type ফিল্ড ('openai' | 'jev') GET /v1/models এবং GET /v1/models/{id}-এ ফেরত দেওয়া হয়।"
            ]
        }
    }
    
    # Check if already added
    has_sub = any("Model Types" in s.get("titles", {}).get("en", "") for s in models_sec.get("subsections", []))
    if not has_sub:
        models_sec.setdefault("subsections", []).append(model_type_sub)


# 3. Create the new section: jev-systemone
jev_section = {
    "id": "jev-systemone",
    "group": "routing",
    "badge": "⚡ System One Decisions",
    "titles": {
        "en": "Jev (System One) Decision Engine",
        "ru": "Движок быстрых решений Jev (System One)",
        "uk": "Рушій швидких рішень Jev (System One)",
        "be": "Рухавік хуткіх рашэнняў Jev (System One)",
        "zh": "Jev 快决策 (System One) 引擎",
        "es": "Motor de decisiones Jev (System One)",
        "fr": "Moteur de décisions Jev (System One)",
        "de": "Jev (System One) Entscheidungs-Engine",
        "ja": "Jev（System One）意思決定エンジン",
        "pt": "Motor de Decisões Jev (System One)",
        "ar": "محرك اتخاذ القرار السريع Jev (System One)",
        "hi": "जेव (Jev) सिस्टम वन डिसीजन इंजन",
        "bn": "জেভ (Jev) সিস্টেম ওয়ান ডিসিশন ইঞ্জিন"
    },
    "descriptions": {
        "en": "Ultra-fast System One decision engine for autonomous agents, classification, guardrails, and structured scoring against discrete rubrics with calibrated probability distributions.",
        "ru": "Сверхбыстрый движок решений System One для автономных агентов, классификации, гардрайлов и оценки по дискретным рубрикам с калиброванным распределением вероятностей.",
        "uk": "Надшвидкий рушій рішень System One для автономних агентів, класифікації, гардрейлів та оцінювання за дискретними рубриками з каліброваним розподілом ймовірностей.",
        "be": "Звышхуткі рухавік рашэнняў System One для аўтаномных агентаў, класіфікацыі, гардрэйлаў і ацэнкі па дыскрэтных рубрыках з калібраваным размеркаваннем верагоднасцяў.",
        "zh": "超高速 System One 快速决策引擎，面向自主智能体、意图分类、安全护栏与结构化规则评分，输出精确校准的概率分布。",
        "es": "Motor de decisiones System One ultrarrápido para agentes autónomos, clasificación, guardarraíles y puntuación con distribuciones de probabilidad calibradas.",
        "fr": "Moteur de décisions System One ultra-rapide pour agents autonomes, classification, garde-fous et évaluation structurée avec probabilités calibrées.",
        "de": "Ultraschnelle System One Entscheidungs-Engine für autonome Agenten, Klassifizierung, Guardrails und strukturierte Kriterienbewertung mit kalibrierten Wahrscheinlichkeiten.",
        "ja": "自律型エージェント、分類、ガードレール、離散ルーブリック評価向けの高精度確率分布を出力する超高速System One意思決定エンジン。",
        "pt": "Motor ultrarrápido de decisões System One para agentes autônomos, classificação, guardrails e avaliação estruturada com distribuições de probabilidade calibradas.",
        "ar": "محرك قرارات فائق السرعة (System One) للوكلاء المستقلين والتصنيف وحواجز الأمان والتقييم المعياري مع توزيعات احتمالية معايرة.",
        "hi": "स्वायत्त एजेंटों, वर्गीकरण, सुरक्षा गार्डरेल्स और कैलिब्रेटेड प्रायिकता वितरण के साथ त्वरित सिस्टम वन डिसीजन इंजन।",
        "bn": "স্বায়ত্তশাসিত এজেন্ট, ক্লাসিফিকেশন, সুরক্ষা গার্ডরেল এবং ক্যালিব্রেটেড সম্ভাব্যতা বিতরণের জন্য অতি-দ্রুত সিস্টেম ওয়ান ডিসিশন ইঞ্জিন।"
    },
    "highlights": {
        "en": [
            "System One Decision Engine: Sub-second rubric & classification evaluation with calibrated probabilities",
            "3 Decision Primitives: Choice (categorical distribution), Score (quantitative metric), and Noul (binary assertion)",
            "Dedicated Endpoints: POST /v1/systemone, POST /v1/decisions, and transparent POST /v1/chat/completions support",
            "Native Zero-Delay Routing for Jev providers + intelligent structured JSON emulation fallback for any LLM",
            "Interactive Playground Studio: State Context, Visual Builder, 4 Presets, probability charts, and multi-language code export"
        ],
        "ru": [
            "Движок решений System One: Мгновенная классификация и оценка по рубрикам с калиброванными вероятностями",
            "3 примитива решений: Choice (категориальный выбор), Score (числовой балл) и Noul (булево утверждение)",
            "Выделенные эндпоинты: POST /v1/systemone, POST /v1/decisions и прозрачная поддержка POST /v1/chat/completions",
            "Нативный роутинг без задержек для Jev-провайдеров + структурированная JSON-эмуляция для любых LLM",
            "Интерактивная студия в Playground: контекст State, Visual Builder, 4 пресета, графики вероятностей и экспорт кода"
        ],
        "uk": [
            "Рушій рішень System One: Миттєва класифікація та оцінювання за рубриками з каліброваними ймовірностями",
            "3 примітиви рішень: Choice (категоріальний вибір), Score (числовий бал) та Noul (булеве твердження)",
            "Виділені ендпоінти: POST /v1/systemone, POST /v1/decisions та прозора підтримка POST /v1/chat/completions",
            "Нативний роутинг без затримок для Jev-провайдерів + структурована JSON-емуляція для будь-яких LLM",
            "Інтерактивна студія в Playground: контекст State, Visual Builder, 4 пресети, графіки ймовірностей та експорт коду"
        ],
        "be": [
            "Рухавік рашэнняў System One: Імгненная класіфікацыя і ацэнка па рубрыках з калібраванымі верагоднасцямі",
            "3 прымітывы рашэнняў: Choice (катэгарыяльны выбар), Score (лікавы бал) і Noul (булева сцвярджэнне)",
            "Вылучаныя эндпоінты: POST /v1/systemone, POST /v1/decisions і празрыстая падтрымка POST /v1/chat/completions",
            "Натыўны роўтынг без затрымак для Jev-правайдэраў + структураваная JSON-эмуляцыя для любых LLM",
            "Інтэрактыўная студыя ў Playground: кантэкст State, Visual Builder, 4 прэсеты, графікі верагоднасцяў і экспарт коду"
        ],
        "zh": [
            "System One 极速决策引擎：面向分类、安全与合规审计的高并发评估，输出高精度校准概率",
            "三大决策原语：Choice（多选类别概率分布）、Score（量化规则评分）与 Noul（布尔断言决策）",
            "专用 REST 接口：POST /v1/systemone、POST /v1/decisions，并无缝兼容标准 POST /v1/chat/completions",
            "原生直连零延迟：原生 Jev 平台直通透传，通用 LLM 自动激活高质量结构化 JSON 提示词模拟回退",
            "Playground 可视化决策工作室：支持 State 上下文编辑、可视化问题构建器、4大场景预设及多语言代码导出"
        ],
        "es": [
            "Motor de decisiones System One: Clasificación instantánea y evaluación por rúbricas con probabilidades calibradas",
            "3 primitivas de decisión: Choice (distribución categórica), Score (métrica cuantitativa) y Noul (afirmación binaria)",
            "Endpoints dedicados: POST /v1/systemone, POST /v1/decisions y compatibilidad transparente con POST /v1/chat/completions",
            "Enrutamiento nativo sin retardo para proveedores Jev + emulación JSON estructurada inteligente para cualquier LLM",
            "Estudio interactivo en Playground: contexto State, Visual Builder, 4 ajustes preestablecidos, gráficos de probabilidad y exportación de código"
        ],
        "fr": [
            "Moteur de décisions System One : Classification instantanée et évaluation selon des grilles avec probabilités calibrées",
            "3 primitives de décision : Choice (distribution catégorielle), Score (note quantitative) et Noul (assertion binaire)",
            "Points de terminaison dédiés : POST /v1/systemone, POST /v1/decisions et compatibilité transparente avec POST /v1/chat/completions",
            "Routage natif sans délai pour les fournisseurs Jev + émulation JSON structurée intelligente pour tout LLM",
            "Studio interactif dans Playground : contexte State, Visual Builder, 4 préréglages, graphiques de probabilité et export de code"
        ],
        "de": [
            "System One Entscheidungs-Engine: Sekundenschnelle Rubriken- und Klassifizierungsbewertung mit kalibrierten Wahrscheinlichkeiten",
            "3 Entscheidungsprimitive: Choice (kategoriale Verteilung), Score (quantitative Metrik) und Noul (binäre Aussage)",
            "Dedizierte Endpunkte: POST /v1/systemone, POST /v1/decisions und transparente Unterstützung von POST /v1/chat/completions",
            "Natives Routing ohne Latenz für Jev-Provider + intelligente strukturierte JSON-Emulation für jedes LLM",
            "Interaktives Playground-Studio: State-Kontext, Visual Builder, 4 Presets, Wahrscheinlichkeitsdiagramme und Code-Export"
        ],
        "ja": [
            "System One意思決定エンジン：校正済み確率を出力するミリ秒級のルーブリック評価および分類機能",
            "3つの意思決定プリミティブ：Choice（カテゴリカル確率分布）、Score（定量的評価点）、Noul（ブール判定）",
            "専用RESTエンドポイント：POST /v1/systemone、POST /v1/decisions、および透過的なPOST /v1/chat/completions対応",
            "Jev事業者向けのネイティブゼロ遅延転送＋汎用LLM向けの高度な構造化JSONエミュレーションフォールバック",
            "Playground判定スタジオ：Stateコンテキスト入力、ビジュアルビルダー、4つの実用プリセット、確率グラフ、コード生成"
        ],
        "pt": [
            "Motor de decisões System One: Classificação instantânea e avaliação por rubricas com probabilidades calibradas",
            "3 primitivas de decisão: Choice (distribuição categórica), Score (métrica quantitativa) e Noul (afirmação binária)",
            "Endpoints dedicados: POST /v1/systemone, POST /v1/decisions e compatibilidade transparente com POST /v1/chat/completions",
            "Roteamento nativo sem latência para provedores Jev + emulação JSON estruturada inteligente para qualquer LLM",
            "Estúdio interativo no Playground: contexto State, Visual Builder, 4 predefinições, gráficos de probabilidade e exportação de código"
        ],
        "ar": [
            "محرك قرارات System One: تقييم فائق السرعة للمعايير والتصنيف مع توزيعات احتمالية معايرة بدقة",
            "3 أوليات للقرار: الاختيار Choice (توزيع فئوي)، والدرجة Score (مقياس كمي)، والإثبات Noul (قرار ثنائي/منطقي)",
            "نقاط نهاية مخصصة: POST /v1/systemone وPOST /v1/decisions، مع توافق شفاف مع POST /v1/chat/completions",
            "توجيه أصلي بدون تأخير لمزودي Jev + محاكاة ذكية بـ JSON المنظم لأي نموذج LLM عام",
            "استوديو Playground التفاعلي: سياق الحالة State، ومنشئ بصري، و4 قوالب جاهزة، ورسوم بيانية للاحتمالات، وتصدير الأكواد"
        ],
        "hi": [
            "सिस्टम वन डिसीजन इंजन: कैलिब्रेटेड प्रायिकताओं के साथ त्वरित वर्गीकरण और मानक मूल्यांकन",
            "3 निर्णय प्रिमिटिव: Choice (श्रेणीबद्ध वितरण), Score (मात्रात्मक स्कोर) और Noul (बूलियन निर्णय)",
            "समर्पित एंडपॉइंट्स: POST /v1/systemone, POST /v1/decisions और POST /v1/chat/completions के साथ पारदर्शी कम्पैटिबिलिटी",
            "जेव प्रदाताओं के लिए नेटिव जीरो-डिले रूटिंग + किसी भी एलएलएम के लिए इंटेलिजेंट स्ट्रक्चर्ड JSON एमुलेशन फॉलबैक",
            "इंटरएक्टिव प्लेग्राउंड स्टूडियो: State संदर्भ संपादक, विज़ुअल बिल्डर, 4 प्रीसेट, प्रायिकता चार्ट और कोड निर्यात"
        ],
        "bn": [
            "সিস্টেম ওয়ান ডিসিশন ইঞ্জিন: ক্যালিব্রেটেড সম্ভাব্যতা সহ সাব-সেকেন্ড ক্লাসিফিকেশন এবং রুব্রিক মূল্যায়ন",
            "৩টি ডিসিশন প্রিমিটিভ: Choice (ক্যাটেগরিক্যাল সম্ভাবনা বণ্টন), Score (সংখ্যাসূচক স্কোর) এবং Noul (বুলিয়ান সিদ্ধান্ত)",
            "ডেডিকেটেড এন্ডপয়েন্ট: POST /v1/systemone, POST /v1/decisions এবং সম্পূর্ণ স্বচ্ছ POST /v1/chat/completions সামঞ্জস্য",
            "জেভ প্রোভাইডারদের জন্য নেটিভ জিরো-ডিলে রাউটিং + যেকোনো এলএলএম-এর জন্য বুদ্ধিমান স্ট্রাকচার্ড JSON এমুলেশন",
            "ইন্টারেক্টিভ প্লেগ্রাউন্ড স্টুডিও: State কনটেক্সট এডিটর, ভিজ্যুয়াল বিল্ডার, ৪টি প্রিসেট, সম্ভাব্যতা চার্ট এবং কোড এক্সপোর্ট"
        ]
    },
    "subsections": [
        {
            "titles": {
                "en": "Decision Primitives & Rubrics",
                "ru": "Примитивы решений и рубрики",
                "uk": "Примітиви рішень та рубрики",
                "be": "Прымітывы рашэнняў і рубрыкі",
                "zh": "决策原语与评估规则",
                "es": "Primitivas de decisión y rúbricas",
                "fr": "Primitives de décision et grilles",
                "de": "Entscheidungsprimitive & Bewertungsrubriken",
                "ja": "意思決定プリミティブと評価ルーブリック",
                "pt": "Primitivas de Decisão e Rubricas",
                "ar": "أوليات القرار والمعايير",
                "hi": "निर्णय प्रिमिटिव और मूल्यांकन रूब्रिक्स",
                "bn": "ডিসিশন প্রিমিটিভ ও মূল্যায়ন রুব্রিক্স"
            },
            "table": {
                "headers": ["Primitive / Примитив", "Type / Тип", "Output Structure", "Description & Usage / Назначение"],
                "rows": [
                    ["choice", "Categorical / Категориальный", "probabilities: {option: float}, choice: string", "Calculates calibrated probability distribution across discrete options (e.g. intent routing, priority triage, sentiment)."],
                    ["score", "Quantitative / Числовой", "score: float, confidence: float", "Computes a numerical score within a defined rubric range (e.g. risk score 0.0-1.0, quality rating 1-5)."],
                    ["noul", "Binary / Булево", "value: bool, confidence: float", "Evaluates a strict boolean assertion or safety guardrail condition with associated confidence."]
                ]
            }
        },
        {
            "titles": {
                "en": "REST API Specification (POST /v1/systemone)",
                "ru": "Спецификация REST API (POST /v1/systemone)",
                "uk": "Специфікація REST API (POST /v1/systemone)",
                "be": "Спецыфікацыя REST API (POST /v1/systemone)",
                "zh": "REST 接口规范 (POST /v1/systemone)",
                "es": "Especificación REST API (POST /v1/systemone)",
                "fr": "Spécification de l'API REST (POST /v1/systemone)",
                "de": "REST-API-Spezifikation (POST /v1/systemone)",
                "ja": "REST API 仕様 (POST /v1/systemone)",
                "pt": "Especificação da API REST (POST /v1/systemone)",
                "ar": "مواصفات واجهة REST API (POST /v1/systemone)",
                "hi": "REST एपीआई विशिष्टता (POST /v1/systemone)",
                "bn": "REST এপিআই স্পেসিফিকেশন (POST /v1/systemone)"
            },
            "code": {
                "title": "System One Decision Request",
                "lang": "bash",
                "content": """curl http://localhost:8000/v1/systemone \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer sk-router-YOUR_KEY" \\
  -d '{
    "model": "experientiallabs/jev-latest",
    "state": "User transaction: $4,990 from IP 198.51.100.4 (New Device, Location: Kyiv, Previous: New York 10m ago).",
    "questions": [
      {
        "id": "fraud_risk",
        "text": "What is the fraud probability category?",
        "type": "choice",
        "options": ["low", "suspicious", "critical_fraud"]
      },
      {
        "id": "require_2fa",
        "text": "Should step-up 2FA verification be enforced immediately?",
        "type": "noul"
      }
    ]
  }'

# Response format:
# {
#   "id": "jev-9b2f4c1e",
#   "model": "experientiallabs/jev-latest",
#   "decisions": {
#     "fraud_risk": {
#       "choice": "critical_fraud",
#       "probabilities": {"low": 0.02, "suspicious": 0.11, "critical_fraud": 0.87},
#       "confidence": 0.87
#     },
#     "require_2fa": {
#       "value": true,
#       "confidence": 0.96
#     }
#   }
# }"""
            }
        },
        {
            "titles": {
                "en": "Native Execution vs Intelligent Emulation",
                "ru": "Нативное исполнение vs Умная эмуляция",
                "uk": "Нативне виконання vs Розумна емуляція",
                "be": "Натыўнае выкананне vs Разумная эмуляцыя",
                "zh": "原生执行与智能模拟回退机制",
                "es": "Ejecución nativa vs Emulación inteligente",
                "fr": "Exécution native vs Émulation intelligente",
                "de": "Native Ausführung vs. Intelligente Emulation",
                "ja": "ネイティブ実行 vs インテリジェントエミュレーション",
                "pt": "Execução Nativa vs Emulação Inteligente",
                "ar": "التنفيذ الأصلي مقابل المحاكاة الذكية",
                "hi": "नेटिव निष्पादन बनाम इंटेलिजेंट एमुलेशन",
                "bn": "নেটিভ এক্সিকিউশন বনাম ইন্টেলিজেন্ট এমুলেশন"
            },
            "bullets": {
                "en": [
                    "Native Zero-Delay Routing: Providers specializing in System One decisions (such as drex.nace, experientiallabs, typesafe.ai) receive pass-through requests with minimal latency overhead.",
                    "Universal LLM Structured Emulation: If a general conversational model (e.g. gemini-2.5-flash, gpt-4o-mini, claude-3-5-haiku, or local ollama) has model_type='jev', MyAIrouter automatically converts the state and questions into a strict structured JSON schema prompt, validates probability constraints, and normalizes output into the compliant Jev envelope.",
                    "Transparent Chat Compatibility: Standard POST /v1/chat/completions accepts Jev-style requests and automatically returns decision payloads, enabling drop-in integration with existing SDKs.",
                    "Alias Support: Both POST /v1/systemone and POST /v1/decisions are public and serve identical functionality."
                ],
                "ru": [
                    "Нативный роутинг без задержек: Специализированные провайдеры (drex.nace, experientiallabs, typesafe.ai) получают прямой запрос к System One с минимальным временем отклика.",
                    "Универсальная структурированная JSON-эмуляция: Если у обычной модели (например, gemini-2.5-flash, gpt-4o-mini, claude-3-5-haiku или локальной ollama) установлен model_type='jev', шлюз автоматически генерирует строгий JSON-промпт, валидирует вероятности и нормализует ответ в формат Jev.",
                    "Прозрачная совместимость с Chat API: Эндпоинт POST /v1/chat/completions прозрачно обрабатывает запросы решений, позволяя работать через стандартные OpenAI SDK.",
                    "Поддержка алиасов: Эндпоинты POST /v1/systemone и POST /v1/decisions взаимозаменяемы и обладают идентичной функциональностью."
                ],
                "uk": [
                    "Нативний роутинг без затримок: Спеціалізовані провайдери (drex.nace, experientiallabs, typesafe.ai) отримують прямий запит до System One із мінімальним часом відгуку.",
                    "Універсальна структурована JSON-емуляція: Якщо у звичайної моделі (наприклад, gemini-2.5-flash, gpt-4o-mini, claude-3-5-haiku або локальної ollama) встановлено model_type='jev', шлюз автоматично генерує суворий JSON-промпт, валідує ймовірності та нормалізує відповідь у формат Jev.",
                    "Прозора сумісність із Chat API: Ендпоінт POST /v1/chat/completions прозоро обробляє запити рішень, дозволяючи працювати через стандартні OpenAI SDK.",
                    "Підтримка аліасів: Ендпоінти POST /v1/systemone та POST /v1/decisions взаємозамінні та мають ідентичну функціональність."
                ],
                "be": [
                    "Натыўны роўтынг без затрымак: Спецыялізаваныя правайдэры (drex.nace, experientiallabs, typesafe.ai) атрымліваюць прамы запыт да System One з мінімальным часам водгуку.",
                    "Універсальная структураваная JSON-эмуляцыя: Калі ў звычайнай мадэлі (напрыклад, gemini-2.5-flash, gpt-4o-mini, claude-3-5-haiku або лакальнай ollama) усталяваны model_type='jev', шлюз аўтаматычна генеруе строгі JSON-промпт, валідуе верагоднасці і нармалізуе адказ у фармат Jev.",
                    "Празрыстая сумяшчальнасць з Chat API: Эндпоінт POST /v1/chat/completions празрыста апрацоўвае запыты рашэнняў, дазваляючы працаваць праз стандартныя OpenAI SDK.",
                    "Падтрымка аліясаў: Эндпоінты POST /v1/systemone і POST /v1/decisions узаемазаменныя і маюць ідэнтычную функцыянальнасць."
                ],
                "zh": [
                    "原生零延迟直通：针对原生支持 System One 决策架构的服务商（如 drex.nace、experientiallabs、typesafe.ai），网关直接透传专属协议，确保极致响应速度。",
                    "通用大模型结构化模拟：当将普通模型（如 gemini-2.5-flash、gpt-4o-mini、claude-3-5-haiku 或本地 ollama）标记为 model_type='jev' 时，网关自动注入严密的结构化 JSON Prompt，校准概率分布并封装为标准决策对象。",
                    "兼容 OpenAI Chat 端点：标准 POST /v1/chat/completions 接口可无缝接收 Jev 负载并自动按决策格式返回，现有 SDK 无需任何修改即可平滑接入。",
                    "双路由别名支持：POST /v1/systemone 与 POST /v1/decisions 完全等价，均可作为决策接口的主入口。"
                ],
                "es": [
                    "Enrutamiento nativo sin latencia: Los proveedores especializados (drex.nace, experientiallabs, typesafe.ai) reciben solicitudes directas a System One con la menor latencia posible.",
                    "Emulación estructurada para cualquier LLM: Si un modelo conversacional general (ej. gemini-2.5-flash, gpt-4o-mini, claude-3-5-haiku, ollama) tiene model_type='jev', MyAIrouter construye automáticamente un prompt JSON estructurado estricto y normaliza la respuesta.",
                    "Compatibilidad transparente con Chat API: El endpoint POST /v1/chat/completions acepta solicitudes Jev y responde con el esquema de decisiones estándar.",
                    "Soporte de alias: Tanto POST /v1/systemone como POST /v1/decisions son idénticos y totalmente operativos."
                ],
                "fr": [
                    "Routage natif sans délai : Les fournisseurs spécialisés (drex.nace, experientiallabs, typesafe.ai) reçoivent les requêtes directes System One sans surcoût de latence.",
                    "Émulation JSON structurée universelle : Si un modèle généraliste (ex. gemini-2.5-flash, gpt-4o-mini, claude-3-5-haiku, ollama) est configuré avec model_type='jev', MyAIrouter génère un prompt JSON strict et normalise la réponse.",
                    "Compatibilité transparente avec Chat API : Le point de terminaison POST /v1/chat/completions accepte les charges utiles Jev et renvoie la structure de décision standard.",
                    "Prise en charge d'alias : POST /v1/systemone et POST /v1/decisions sont totalement interchangeables."
                ],
                "de": [
                    "Natives Routing ohne Verzögerung: Spezialisierte Anbieter (drex.nace, experientiallabs, typesafe.ai) erhalten direkte Durchleitungen mit minimaler Latenz.",
                    "Universelle strukturierte JSON-Emulation: Wenn ein Standard-LLM (z. B. gemini-2.5-flash, gpt-4o-mini, claude-3-5-haiku, ollama) auf model_type='jev' gesetzt ist, erzeugt MyAIrouter automatisch einen strengen JSON-Prompt und normalisiert die Antwort.",
                    "Transparente Chat-API-Kompatibilität: Der Endpunkt POST /v1/chat/completions verarbeitet Jev-Anfragen transparent und liefert konforme Entscheidungsobjekte.",
                    "Alias-Unterstützung: Sowohl POST /v1/systemone als auch POST /v1/decisions sind öffentlich verfügbar und funktional identisch."
                ],
                "ja": [
                    "ネイティブゼロ遅延転送：System One意思決定に対応した事業者（drex.nace、experientiallabs、typesafe.ai等）へのリクエストは変換なしで高速直結されます。",
                    "汎用LLM向け構造化JSON自動エミュレーション：通常モデル（gemini-2.5-flash、gpt-4o-mini、claude-3-5-haiku、ローカルollama等）に model_type='jev' を指定した場合、厳格なJSONスキーマプロンプトを自動生成し出力を正規化します。",
                    "Chat APIとの透過的互換性：標準の POST /v1/chat/completions でもJevペイロードを受け付け、意思決定レスポンスを返却可能です。",
                    "エイリアス対応：POST /v1/systemone と POST /v1/decisions は完全に等価であり、同一の機能を提供します。"
                ],
                "pt": [
                    "Roteamento nativo sem latência: Provedores especializados (drex.nace, experientiallabs, typesafe.ai) recebem requisições diretas com o menor tempo de resposta.",
                    "Emulação estruturada universal: Quando um modelo convencional (ex: gemini-2.5-flash, gpt-4o-mini, claude-3-5-haiku, ollama) tem model_type='jev', o MyAIrouter gera automaticamente prompts JSON estruturados e valida as probabilidades.",
                    "Compatibilidade transparente com Chat API: O endpoint POST /v1/chat/completions aceita cargas úteis Jev e retorna os dados de decisão correspondentes.",
                    "Suporte a alias: POST /v1/systemone e POST /v1/decisions são intercambiáveis e oferecem a mesma funcionalidade."
                ],
                "ar": [
                    "توجيه أصلي بدون تأخير: يتلقى المزودون المتخصصون (مثل drex.nace وexperientiallabs وtypesafe.ai) الطلبات مباشرة إلى محرك System One بأدنى زمن استجابة ممكن.",
                    "محاكاة JSON المنظمة لجميع النماذج: عند ضبط model_type='jev' لأي نموذج محادثة عام (مثل gemini-2.5-flash أو gpt-4o-mini أو claude-3-5-haiku أو ollama)، يقوم النظام تلقائياً بإنشاء موجه JSON صارم ومعايرة الاحتمالات.",
                    "توافق شفاف مع Chat API: تقبل نقطة النهاية القياسية POST /v1/chat/completions حمولات Jev وتعيد استجابة القرارات المعتمدة.",
                    "دعم الأسماء المستعارة: كل من POST /v1/systemone وPOST /v1/decisions يقدمان نفس الوظيفة تماماً."
                ],
                "hi": [
                    "नेटिव जीरो-डिले रूटिंग: सिस्टम वन में विशेषज्ञता रखने वाले प्रदाता (drex.nace, experientiallabs, typesafe.ai) बिना किसी विलंबता के सीधे अनुरोध प्राप्त करते हैं।",
                    "सार्वभौमिक एलएलएम स्ट्रक्चर्ड एमुलेशन: यदि किसी सामान्य मॉडल (उदा. gemini-2.5-flash, gpt-4o-mini, claude-3-5-haiku, ollama) में model_type='jev' सेट है, तो MyAIrouter स्वचालित रूप से एक सख्त JSON प्रॉम्प्ट बनाकर आउटपुट को सामान्य करता है।",
                    "पारदर्शी चैट कम्पैटिबिलिटी: मानक POST /v1/chat/completions जेव पेलोड को पारदर्शी रूप से स्वीकार करता है और निर्णय परिणाम देता है।",
                    "उपनाम (Alias) समर्थन: POST /v1/systemone और POST /v1/decisions दोनों समान कार्यक्षमता प्रदान करते हैं।"
                ],
                "bn": [
                    "নেটিভ জিরো-ডিলে রাউটিং: সিস্টেম ওয়ান ডিসিশনে বিশেষজ্ঞ প্রদানকারীরা (যেমন drex.nace, experientiallabs, typesafe.ai) ন্যূনতম লেটেন্সিতে সরাসরি অনুরোধ গ্রহণ করে।",
                    "ইউনিভার্সাল এলএলএম স্ট্রাকচার্ড এমুলেশন: যদি কোনো সাধারণ মডেল (যেমন gemini-2.5-flash, gpt-4o-mini, claude-3-5-haiku, ollama)-এ model_type='jev' থাকে, তবে MyAIrouter স্বয়ংক্রিয়ভাবে একটি কঠোর JSON প্রম্পটের মাধ্যমে আউটপুট প্রক্রিয়া করে।",
                    "স্বচ্ছ চ্যাট সামঞ্জস্য: স্ট্যান্ডার্ড POST /v1/chat/completions জেভ পেলোড গ্রহণ করে স্বয়ংক্রিয়ভাবে ডিসিশন রেসপন্স ফেরত দেয়।",
                    "উপনাম সমর্থন: POST /v1/systemone এবং POST /v1/decisions দুটি এন্ডপয়েন্টই সম্পূর্ণ সমতুল্য।"
                ]
            }
        },
        {
            "titles": {
                "en": "Playground Studio & Visual Presets",
                "ru": "Студия в Playground и готовые пресеты",
                "uk": "Студія в Playground та готові пресети",
                "be": "Студыя ў Playground і гатовыя прэсеты",
                "zh": "Playground 可视化决策工作室与场景预设",
                "es": "Estudio Playground y preajustes visuales",
                "fr": "Studio Playground et préréglages visuels",
                "de": "Playground-Studio & Visuelle Presets",
                "ja": "Playground スタジオとプリセット機能",
                "pt": "Estúdio no Playground e Predefinições Visuais",
                "ar": "استوديو Playground والقوالب المرئية الجاهزة",
                "hi": "प्लेग्राउंड स्टूडियो और विज़ुअल प्रीसेट",
                "bn": "প্লেগ্রাউন্ড স্টুডিও এবং ভিজ্যুয়াল প্রিসেট"
            },
            "bullets": {
                "en": [
                    "Dedicated Studio Mode: Access the '⚡ Jev (System One)' tab in the web console (/playground) to test discrete decision models interactively.",
                    "State Context Editor: Provide rich context (user profiles, audit logs, code diffs, financial transactions, or policy documents) for the decision engine.",
                    "Visual Question Builder: Add questions, configure primitive types (choice, score, noul), and specify discrete options with live validation or toggle to raw JSON.",
                    "4 Built-in Presets: Instant one-click templates for Customer Support Escalation, Content Moderation Guardrails, PR Code Review, and Financial Fraud Risk.",
                    "Live Analytics & Export: Real-time calibrated probability distribution bar charts, confidence gauges, and instant code export for cURL, Python SDK, and Node.js."
                ],
                "ru": [
                    "Выделенный режим студии: Вкладка '⚡ Jev (System One)' в веб-консоли (/playground) для интерактивного тестирования моделей быстрых решений.",
                    "Редактор контекста State: Удобный ввод контекста (профиль пользователя, лог аудита, диффы кода, транзакции или текст политик).",
                    "Визуальный конструктор вопросов: Добавление вопросов, выбор примитивов (choice, score, noul) и настройка опций с мгновенной валидацией или переключением в JSON.",
                    "4 встроенных пресета: Готовые сценарии для эскалации поддержки, модерации контента, ревью кода в PR и оценки финансовых рисков.",
                    "Аналитика и экспорт: Наглядные гистограммы распределения вероятностей, датчики уверенности и экспорт готового кода для cURL, Python и Node.js."
                ],
                "uk": [
                    "Виділений режим студії: Вкладка '⚡ Jev (System One)' у веб-консолі (/playground) для інтерактивного тестування моделей швидких рішень.",
                    "Редактор контексту State: Зручне введення контексту (профіль користувача, лог аудиту, дифи коду, транзакції або текст політик).",
                    "Візуальний конструктор питань: Додавання питань, вибір примітивів (choice, score, noul) та налаштування опцій із миттєвою валідацією або перемиканням у JSON.",
                    "4 вбудовані пресети: Готові сценарії для ескалації підтримки, модерації контенту, рев'ю коду в PR та оцінки фінансових ризиків.",
                    "Аналітика та експорт: Наочні гістограми розподілу ймовірностей, датчики впевненості та експорт готового коду для cURL, Python і Node.js."
                ],
                "be": [
                    "Вылучаны рэжым студыі: Укладка '⚡ Jev (System One)' у вэб-кансолі (/playground) для інтэрактыўнага тэсціравання мадэляў хуткіх рашэнняў.",
                    "Рэдактар кантэксту State: Зручны ўвод кантэксту (профіль карыстальніка, лог аўдыту, дыфы коду, транзакцыі або тэкст палітык).",
                    "Візуальны канструктар пытанняў: Даданне пытанняў, выбар прымітываў (choice, score, noul) і налада опцый з імгненнай валідацыяй або пераключэннем у JSON.",
                    "4 убудаваныя прэсеты: Гатовыя сцэнарыі для эскалацыі падтрымкі, мадэрацыі кантэнту, рэвю коду ў PR і ацэнкі фінансавых рызык.",
                    "Аналітыка і экспарт: Наглядныя гістаграмы размеркавання верагоднасцяў, датчыкі ўпэўненасці і экспарт гатовага коду для cURL, Python і Node.js."
                ],
                "zh": [
                    "专属工作室模式：在 Web 控制台的 /playground 页面直接切换至 '⚡ Jev (System One)' 模式进行离散决策交互调试。",
                    "State 上下文编辑器：输入待评估的完整上下文信息（如客户会话、审计日志、代码审查 Diff、支付交易详情或合规准则）。",
                    "可视化原语构建器：轻松增删评估项，一键切换 choice、score、noul 原语类型并配置离散标签，支持无缝切换至底层 Raw JSON 编辑。",
                    "内置4大场景预设：提供客服工单流转、内容安全审核、PR 代码合规审查、金融交易欺诈拦截等开箱即用的工业级预设。",
                    "实时概率图表与多语言代码导出：提供校准概率条形图、置信度指标盘与 cURL、Python、Node.js 快速接入代码生成。"
                ],
                "es": [
                    "Modo de estudio dedicado: Pestaña '⚡ Jev (System One)' en la consola web (/playground) para probar modelos de decisión de forma interactiva.",
                    "Editor de contexto State: Inserte contextos completos (perfiles de usuario, registros de auditoría, diffs de código, transacciones o políticas).",
                    "Constructor visual de preguntas: Agregue preguntas, seleccione primitivas (choice, score, noul) y especifique opciones con validación en vivo o cambie a JSON puro.",
                    "4 preajustes integrados: Plantillas inmediatas para derivación de soporte, moderación de contenido, revisión de código PR y riesgo financiero.",
                    "Gráficos y exportación de código: Visualización de distribuciones de probabilidad, medidores de confianza y exportación de código a cURL, Python y Node.js."
                ],
                "fr": [
                    "Mode studio dédié : Onglet '⚡ Jev (System One)' dans la console (/playground) pour tester interactivement les modèles de décision.",
                    "Éditeur de contexte State : Renseignez le contexte à évaluer (profil client, logs d'audit, diffs de code, transactions bancaires, politiques de sécurité).",
                    "Générateur visuel de questions : Ajoutez des questions, sélectionnez les types (choice, score, noul) et définissez les options avec bascule en JSON brut.",
                    "4 préréglages prêts à l'emploi : Modèles pour l'escalade du support, la modération de contenu, la revue de code PR et le risque de fraude financière.",
                    "Graphiques et export de code : Diagrammes de probabilité calibrés, jauges de confiance et export de code pour cURL, Python et Node.js."
                ],
                "de": [
                    "Dedizierter Studio-Modus: Eigener Tab '⚡ Jev (System One)' im Playground (/playground) zur interaktiven Evaluierung diskreter Entscheidungen.",
                    "State-Kontext-Editor: Bereitstellung von Kontextdaten (Benutzerprofile, Audit-Logs, Code-Diffs, Finanztransaktionen oder Richtlinientexte).",
                    "Visueller Fragen-Builder: Fragen hinzufügen, Primitive (choice, score, noul) auswählen und Optionen konfigurieren oder direkt im Raw JSON editieren.",
                    "4 integrierte Vorlagen: Vordefinierte Szenarien für Support-Eskalation, Content-Moderation, PR-Code-Review und Betrugserkennung.",
                    "Live-Visualisierung & Code-Export: Wahrscheinlichkeitsbalken, Konfidenzanzeigen und Ein-Klick-Code-Generierung für cURL, Python und Node.js."
                ],
                "ja": [
                    "専用スタジオモード：Webコンソールの /playground 内にある「⚡ Jev（System One）」タブから対話形式で意思決定テストが可能。",
                    "Stateコンテキスト入力：ユーザー履歴、監査ログ、コード差分、金融取引情報、セキュリティ規約などの文脈を柔軟に入力。",
                    "ビジュアル質問ビルダー：質問項目の追加、プリミティブ型（choice、score、noul）の選択、選択肢の設定をGUIで行え、Raw JSONの直接編集も可能。",
                    "4つの実用プリセット：カスタマーサポート対応、コンテンツ審査、PRコードレビュー、金融不正検知のテンプレートを即座に呼び出し可能。",
                    "リアルタイム確率可視化とコード出力：確率分布バーグラフ、信頼度メーター、cURL・Python・Node.js 向けの接続コード自動生成。"
                ],
                "pt": [
                    "Modo de estúdio dedicado: Aba '⚡ Jev (System One)' no console web (/playground) para testar modelos de decisão interativamente.",
                    "Editor de contexto State: Forneça contextos completos (perfis de usuário, logs de auditoria, diffs de código, transações ou políticas).",
                    "Construtor visual de perguntas: Adicione perguntas, selecione tipos de primitivas (choice, score, noul) e defina opções com validação em tempo real.",
                    "4 predefinições integradas: Cenários prontos para escalonamento de suporte, moderação de conteúdo, revisão de código e risco de fraude.",
                    "Gráficos e exportação de código: Gráficos de barras de probabilidade calibrada, medidores de confiança e exportação de código cURL, Python e Node.js."
                ],
                "ar": [
                    "وضع استوديو مخصص: تبويب '⚡ Jev (System One)' في واجهة الويب (/playground) لاختبار نماذج اتخاذ القرارات السريعة بشكل تفاعلي.",
                    "محرر سياق الحالة State: إدخال السياق المطلوب تقييمه (سجلات الأمان، محادثات العملاء، الفروقات البرمجية، أو المعاملات المالية).",
                    "منشئ الأسئلة المرئي: إضافة الأسئلة واختيار نوع الأولية (choice, score, noul) وضبط الخيارات مع إمكانية التبديل إلى JSON الخام.",
                    "4 قوالب مدمجة: سيناريوهات جاهزة لتصعيد دعم العملاء، وإشراف المحتوى، ومراجعة الأكواد البرمجية، ومخاطر الاحتيال المالي.",
                    "مخططات احتمالية وتصدير الكود: رسوم بيانية للتوزيع الاحتمالي ومؤشرات الثقة مع تصدير الأكواد بضغطة زر لـ cURL وPython وNode.js."
                ],
                "hi": [
                    "समर्पित स्टूडियो मोड: त्वरित निर्णय मॉडल का परीक्षण करने के लिए वेब कंसोल (/playground) में '⚡ Jev (System One)' टैब।",
                    "State संदर्भ संपादक: मूल्यांकन के लिए समृद्ध संदर्भ (उपयोगकर्ता प्रोफ़ाइल, ऑडिट लॉग, कोड डिफ, वित्तीय लेनदेन) दर्ज करें।",
                    "विज़ुअल प्रश्न निर्माता: प्रश्न जोड़ें, प्रिमिटिव प्रकार (choice, score, noul) चुनें और सीधे JSON में टॉगल करें।",
                    "4 अंतर्निहित प्रीसेट: ग्राहक सहायता एस्केलेशन, सामग्री मॉडरेशन, पीआर कोड समीक्षा, और वित्तीय धोखाधड़ी जोखिम के लिए रेडीमेड टेम्पलेट।",
                    "लाइव एनालिटिक्स और कोड निर्यात: वास्तविक समय प्रायिकता बार चार्ट, विश्वास गेज और cURL, Python, Node.js के लिए त्वरित कोड जनरेशन।"
                ],
                "bn": [
                    "ডেডিকেটেড স্টুডিও মোড: ওয়েব কনসোলে (/playground) '⚡ Jev (System One)' ট্যাবের মাধ্যমে ডিসিশন মডেল ইন্টারঅ্যাক্টিভভাবে পরীক্ষা করুন।",
                    "State কনটেক্সট এডিটর: মূল্যায়নের জন্য সম্পূর্ণ বিবরণ (ইউজার প্রোফাইল, অডিট লগ, কোড ডিফস, লেনদেন বা পলিসি ডকুমেন্ট) প্রদান করুন।",
                    "ভিজ্যুয়াল প্রশ্ন নির্মাতা: প্রশ্ন যোগ করুন, প্রিমিটিভের ধরন (choice, score, noul) নির্বাচন করুন এবং সরাসরি র' JSON-এ স্যুইচ করুন।",
                    "৪টি প্রস্তুত প্রিসেট: কাস্টমার সাপোর্ট এস্কেলেশন, কনটেন্ট মডারেশন, পিআর কোড রিভিউ এবং আর্থিক জালিয়াতি ঝুঁকির জন্য রেডিমেড টেমপ্লেট।",
                    "লাইভ চার্ট ও কোড এক্সপোর্ট: ক্যালিব্রেটেড সম্ভাব্যতা বার চার্ট, কনফিডেন্স গজ এবং cURL, Python, Node.js-এর জন্য তাৎক্ষণিক কোড রপ্তানি।"
                ]
            }
        }
    ]
}

# Insert jev_section right after fusion (or at the end of SECTIONS_PART1)
jev_idx = None
for i, s in enumerate(sections_data_part1.SECTIONS_PART1):
    if s["id"] == "jev-systemone":
        jev_idx = i
        break

if jev_idx is not None:
    sections_data_part1.SECTIONS_PART1[jev_idx] = jev_section
else:
    # Insert after fusion
    fusion_idx = -1
    for i, s in enumerate(sections_data_part1.SECTIONS_PART1):
        if s["id"] == "fusion":
            fusion_idx = i
            break
    if fusion_idx >= 0:
        sections_data_part1.SECTIONS_PART1.insert(fusion_idx + 1, jev_section)
    else:
        sections_data_part1.SECTIONS_PART1.append(jev_section)


# 4. Update api-reference in SECTIONS_PART2
api_ref = None
for s in sections_data_part2.SECTIONS_PART2:
    if s["id"] == "api-reference":
        api_ref = s
        break

if api_ref:
    api_ref["highlights"] = {
        "en": [
            "OpenAI Ingest: /v1/chat/completions, /v1/models (full drop-in client compatibility)",
            "Jev System One Decisions: /v1/systemone, /v1/decisions (discrete decision intelligence)",
            "Ollama Protocol: /api/tags, /api/show, /api/version, /api/chat",
            "Core Management: /api/v1/credentials, /api/v1/models, /api/v1/routes, /api/v1/fusion",
            "System & Health: /health, /api/v1/system/backup, /api/v1/system/restore, /api/v1/system/stats"
        ],
        "ru": [
            "Совместимость с OpenAI: /v1/chat/completions, /v1/models (прямая замена в любых SDK)",
            "Решения Jev System One: /v1/systemone, /v1/decisions (быстрая дискретная классификация)",
            "Протокол Ollama: /api/tags, /api/show, /api/version, /api/chat",
            "Управление конфигурацией: /api/v1/credentials, /api/v1/models, /api/v1/routes, /api/v1/fusion",
            "Система и мониторинг: /health, /api/v1/system/backup, /api/v1/system/restore, /api/v1/system/stats"
        ],
        "uk": [
            "Сумісність з OpenAI: /v1/chat/completions, /v1/models (пряма заміна у будь-яких SDK)",
            "Рішення Jev System One: /v1/systemone, /v1/decisions (швидка дискретна класифікація)",
            "Протокол Ollama: /api/tags, /api/show, /api/version, /api/chat",
            "Керування конфігурацією: /api/v1/credentials, /api/v1/models, /api/v1/routes, /api/v1/fusion",
            "Система та моніторинг: /health, /api/v1/system/backup, /api/v1/system/restore, /api/v1/system/stats"
        ],
        "be": [
            "Сумяшчальнасць з OpenAI: /v1/chat/completions, /v1/models (прамая замена ў любых SDK)",
            "Рашэнні Jev System One: /v1/systemone, /v1/decisions (хуткая дыскрэтная класіфікацыя)",
            "Пратакол Ollama: /api/tags, /api/show, /api/version, /api/chat",
            "Кіраванне канфігурацыяй: /api/v1/credentials, /api/v1/models, /api/v1/routes, /api/v1/fusion",
            "Сістэма і маніторынг: /health, /api/v1/system/backup, /api/v1/system/restore, /api/v1/system/stats"
        ],
        "zh": [
            "OpenAI 标准推理接口：/v1/chat/completions, /v1/models（主流客户端无缝无感替换）",
            "Jev System One 决策端点：/v1/systemone, /v1/decisions（离散评估与校准概率）",
            "Ollama 原生协议接口：/api/tags, /api/show, /api/version, /api/chat（兼容各类本地工具）",
            "核心配置控制面：/api/v1/credentials, /api/v1/models, /api/v1/routes, /api/v1/fusion",
            "系统运维与探针：/health, /api/v1/system/backup, /api/v1/system/restore, /api/v1/system/stats"
        ],
        "es": [
            "Entrada OpenAI: /v1/chat/completions, /v1/models (compatibilidad inmediata con cualquier cliente)",
            "Decisiones Jev System One: /v1/systemone, /v1/decisions (evaluación discreta y probabilidades calibradas)",
            "Protocolo Ollama: /api/tags, /api/show, /api/version, /api/chat",
            "Gestión principal: /api/v1/credentials, /api/v1/models, /api/v1/routes, /api/v1/fusion",
            "Sistema y salud: /health, /api/v1/system/backup, /api/v1/system/restore, /api/v1/system/stats"
        ],
        "fr": [
            "Ingestion OpenAI : /v1/chat/completions, /v1/models (remplacement direct pour tout client)",
            "Décisions Jev System One : /v1/systemone, /v1/decisions (évaluation discrète et probabilités calibrées)",
            "Protocole Ollama : /api/tags, /api/show, /api/version, /api/chat",
            "Gestion principale : /api/v1/credentials, /api/v1/models, /api/v1/routes, /api/v1/fusion",
            "Système et santé : /health, /api/v1/system/backup, /api/v1/system/restore, /api/v1/system/stats"
        ],
        "de": [
            "OpenAI-Eingang: /v1/chat/completions, /v1/models (vollständig kompatibel mit allen OpenAI-Clients)",
            "Jev System One Decisions: /v1/systemone, /v1/decisions (diskrete Bewertung & kalibrierte Wahrscheinlichkeiten)",
            "Ollama-Protokoll: /api/tags, /api/show, /api/version, /api/chat",
            "Kernverwaltung: /api/v1/credentials, /api/v1/models, /api/v1/routes, /api/v1/fusion",
            "System & Gesundheit: /health, /api/v1/system/backup, /api/v1/system/restore, /api/v1/system/stats"
        ],
        "ja": [
            "OpenAI互換：/v1/chat/completions、/v1/models（各社SDKをそのまま差し替え可能）",
            "Jev System One意思決定：/v1/systemone、/v1/decisions（離散ルーブリック判定・校正済み確率）",
            "Ollamaプロトコル：/api/tags、/api/show、/api/version、/api/chat",
            "構成管理：/api/v1/credentials、/api/v1/models、/api/v1/routes、/api/v1/fusion",
            "システム＆死活監視：/health、/api/v1/system/backup、/api/v1/system/restore、/api/v1/system/stats"
        ],
        "pt": [
            "Entrada OpenAI: /v1/chat/completions, /v1/models (compatibilidade direta com qualquer SDK)",
            "Decisões Jev System One: /v1/systemone, /v1/decisions (avaliação discreta e probabilidades calibradas)",
            "Protocolo Ollama: /api/tags, /api/show, /api/version, /api/chat",
            "Gerenciamento principal: /api/v1/credentials, /api/v1/models, /api/v1/routes, /api/v1/fusion",
            "Sistema e integridade: /health, /api/v1/system/backup, /api/v1/system/restore, /api/v1/system/stats"
        ],
        "ar": [
            "واجهة OpenAI المتوافقة: /v1/chat/completions و/v1/models (إحلال مباشر لجميع التطبيقات)",
            "قرارات Jev System One: /v1/systemone و/v1/decisions (تقييم المعايير المنفصلة والاحتمالات المعايرة)",
            "بروتوكول Ollama: /api/tags و/api/show و/api/version و/api/chat",
            "الإدارة المركزية: /api/v1/credentials و/api/v1/models و/api/v1/routes و/api/v1/fusion",
            "النظام والسلامة: /health و/api/v1/system/backup و/api/v1/system/restore و/api/v1/system/stats"
        ],
        "hi": [
            "OpenAI इनपुट: /v1/chat/completions, /v1/models (पूर्ण क्लाइंट संगतता)",
            "Jev System One डिसीजन: /v1/systemone, /v1/decisions (असतत निर्णय मूल्यांकन)",
            "Ollama प्रोटोकॉल: /api/tags, /api/show, /api/version, /api/chat",
            "कोर प्रबंधन: /api/v1/credentials, /api/v1/models, /api/v1/routes, /api/v1/fusion",
            "सिस्टम और स्वास्थ्य: /health, /api/v1/system/backup, /api/v1/system/restore"
        ],
        "bn": [
            "OpenAI ইনপুট: /v1/chat/completions, /v1/models (ড্রপ-ইন ক্লায়েন্ট সামঞ্জস্য)",
            "Jev System One ডিসিশন: /v1/systemone, /v1/decisions (ডিসক্রিট মূল্যায়ন ও সম্ভাব্যতা)",
            "Ollama প্রোটোকল: /api/tags, /api/show, /api/version, /api/chat",
            "কোর ম্যানেজমেন্ট: /api/v1/credentials, /api/v1/models, /api/v1/routes, /api/v1/fusion",
            "সিস্টেম ও হেলথ: /health, /api/v1/system/backup, /api/v1/system/restore"
        ]
    }

    if api_ref.get("subsections"):
        for sub in api_ref["subsections"]:
            if "table" in sub and "rows" in sub["table"]:
                rows = sub["table"]["rows"]
                # Check if systemone already in rows
                has_sysone = any("/v1/systemone" in r[1] for r in rows)
                if not has_sysone:
                    # Insert after /v1/chat/completions (idx 1)
                    rows.insert(1, ["POST", "/v1/systemone", "Bearer sk-router-...", "Jev System One decision engine: evaluate state against discrete criteria (choice, score, noul)"])
                    rows.insert(2, ["POST", "/v1/decisions", "Bearer sk-router-...", "Alias for /v1/systemone decision evaluation endpoint"])


# Helper to format Python file
import pprint

def write_sections_file(filepath, var_name, data, header):
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(header + "\n\n")
        f.write(f"{var_name} = ")
        # Using json-like or formatted python dict
        formatted = pprint.pformat(data, indent=4, width=120, sort_dicts=False)
        f.write(formatted)
        f.write("\n")

# Write updated sections_data_part1.py and sections_data_part2.py
p1_path = os.path.join(script_dir, "sections_data_part1.py")
p2_path = os.path.join(script_dir, "sections_data_part2.py")

write_sections_file(p1_path, "SECTIONS_PART1", sections_data_part1.SECTIONS_PART1, "# Part 1: Sections 1-11")
print(f"Updated {p1_path} ({len(sections_data_part1.SECTIONS_PART1)} sections)")

write_sections_file(p2_path, "SECTIONS_PART2", sections_data_part2.SECTIONS_PART2, "# Part 2: Sections 12-21")
print(f"Updated {p2_path} ({len(sections_data_part2.SECTIONS_PART2)} sections)")

print("Docs source data update complete!")
