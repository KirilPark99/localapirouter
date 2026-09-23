# Part 2: Sections 11-20

SECTIONS_PART2 = [
    {
        "id": "providers",
        "group": "management",
        "badge": "Multi-Provider",
        "titles": {
            "en": "Supported Providers & Keyless Mode",
            "ru": "Поддерживаемые провайдеры и Keyless-режим",
            "uk": "Підтримувані провайдери та Keyless-режим",
            "be": "Падтрымліваемыя правайдэры і Keyless-рэжым",
            "zh": "支持的提供商与免密本地模式",
            "es": "Proveedores compatibles y modo sin clave",
            "fr": "Fournisseurs pris en charge et mode sans clé",
            "de": "Unterstützte Provider & Keyless-Modus",
            "ja": "対応プロバイダーとKeylessモード",
            "pt": "Provedores Suportados e Modo Keyless",
            "ar": "المزودون المدعومون والوضع بدون مفتاح",
            "hi": "समर्थित प्रदाता और की-लेस मोड",
            "bn": "সমর্থিত প্রদানকারী এবং কী-লেস মোড"
        },
        "descriptions": {
            "en": "Native integration with 12+ cloud LLM providers and local inference runtimes, featuring Keyless Mode for self-hosted Ollama instances.",
            "ru": "Нативная интеграция с 12+ облачными провайдерами и локальными средами исполнения, включая Keyless-режим для собственного инстанса Ollama.",
            "uk": "Нативна інтеграція з 12+ хмарними провайдерами та локальними середовищами виконання, включаючи Keyless-режим для власного інстансу Ollama.",
            "be": "Натыўная інтэграцыя з 12+ воблачнымі правайдэрамі і лакальнымі асяроддзямі, уключаючы Keyless-рэжым для ўласнага інстанса Ollama.",
            "zh": "原生支持 12+ 主流云端大模型服务商与本地推理引擎，特设免密模式无缝接入自建 Ollama 实例。",
            "es": "Integración nativa con más de 12 proveedores de LLM en la nube y entornos locales, con modo sin clave para instancias de Ollama.",
            "fr": "Intégration native avec plus de 12 fournisseurs de LLM cloud et moteurs locaux, avec mode sans clé pour les instances Ollama.",
            "de": "Native Integration von über 12 Cloud-LLM-Providern und lokalen Runtimes, inklusive Keyless-Modus für lokale Ollama-Instanzen.",
            "ja": "12以上のクラウドLLMプロバイダーとローカルランタイムにネイティブ対応。自前Ollamaインスタンス向けのKeylessモードも完備。",
            "pt": "Integração nativa com mais de 12 provedores de LLM na nuvem e runtimes locais, com modo Keyless para instâncias do Ollama.",
            "ar": "تكامل أصلي مع أكثر من 12 مزوداً سحابياً للنماذج اللغوية ومحركات التشغيل المحلية، مع دعم الوضع بدون مفتاح لمثيلات Ollama.",
            "hi": "12+ क्लाउड एलएलएम प्रदाताओं और स्थानीय रनटाइम के साथ मूल एकीकरण, ओलामा इंस्टेंस के लिए की-लेस मोड के साथ।",
            "bn": "১২টিরও বেশি ক্লাউড এলএলএম প্রদানকারী এবং লোকাল রানটাইমের সাথে নেটিভ ইন্টিগ্রেশন, ওলামা ইন্সট্যান্সের জন্য কী-লেস মোড সহ।"
        },
        "highlights": {
            "en": [
                "Full support for OpenAI, Anthropic, Gemini, Groq, DeepSeek, Cerebras, Mistral, xAI, OpenRouter",
                "Keyless Mode: Connect local Ollama (http://localhost:11434) without requiring mock API keys",
                "Custom Base URL support for vLLM, LM Studio, and OpenAI-compatible corporate gateways",
                "Dedicated HTTP/SOCKS5 proxy binding per provider credential"
            ],
            "ru": [
                "Поддержка OpenAI, Anthropic, Gemini, Groq, DeepSeek, Cerebras, Mistral, xAI, OpenRouter",
                "Keyless-режим: подключение локальной Ollama (http://localhost:11434) без фиктивных API-ключей",
                "Пользовательский Base URL для vLLM, LM Studio и корпоративных OpenAI-совместимых шлюзов",
                "Привязка выделенных HTTP/SOCKS5 прокси к учетным записям провайдеров"
            ],
            "uk": [
                "Підтримка OpenAI, Anthropic, Gemini, Groq, DeepSeek, Cerebras, Mistral, xAI, OpenRouter",
                "Keyless-режим: підключення локальної Ollama (http://localhost:11434) без фіктивних ключів",
                "Власний Base URL для vLLM, LM Studio та корпоративних OpenAI-сумісних шлюзів",
                "Прив'язка виділених HTTP/SOCKS5 проксі до облікових записів провайдерів"
            ],
            "be": [
                "Падтрымка OpenAI, Anthropic, Gemini, Groq, DeepSeek, Cerebras, Mistral, xAI, OpenRouter",
                "Keyless-рэжым: падключэнне лакальнай Ollama (http://localhost:11434) без фіктыўных ключоў",
                "Уласны Base URL для vLLM, LM Studio і карпаратыўных OpenAI-сумяшчальных шлюзаў",
                "Прывязка вылучаных HTTP/SOCKS5 проксі да ўліковых запісаў правайдэраў"
            ],
            "zh": [
                "全面支持 OpenAI, Anthropic, Gemini, Groq, DeepSeek, Cerebras, Mistral, xAI, OpenRouter 等主流平台",
                "免密模式 (Keyless)：连接本地 Ollama (http://localhost:11434) 无需填写伪造 API Key",
                "自定义 Base URL：支持自建 vLLM, LM Studio, LocalAI 以及各类企业内网兼容网关",
                "代理通道绑定：可为每个提供商凭证独立配置专用的 HTTP/SOCKS5 代理"
            ],
            "es": [
                "Soporte integral para OpenAI, Anthropic, Gemini, Groq, DeepSeek, Cerebras, Mistral, xAI, OpenRouter",
                "Modo sin clave: conecte Ollama local (http://localhost:11434) sin necesidad de claves falsas",
                "Soporte de Base URL personalizada para vLLM, LM Studio y pasarelas empresariales OpenAI",
                "Vinculación de proxy HTTP/SOCKS5 dedicada por credencial de proveedor"
            ],
            "fr": [
                "Prise en charge d'OpenAI, Anthropic, Gemini, Groq, DeepSeek, Cerebras, Mistral, xAI, OpenRouter",
                "Mode sans clé : connectez Ollama local (http://localhost:11434) sans fausses clés API",
                "URL de base personnalisée pour vLLM, LM Studio et passerelles d'entreprise compatibles OpenAI",
                "Liaison de proxy HTTP/SOCKS5 dédiée par identifiant de fournisseur"
            ],
            "de": [
                "Vollständige Unterstützung für OpenAI, Anthropic, Gemini, Groq, DeepSeek, Cerebras, Mistral, xAI, OpenRouter",
                "Keyless-Modus: Lokale Ollama (http://localhost:11434) ohne Schein-API-Schlüssel verbinden",
                "Benutzerdefinierte Base-URLs für vLLM, LM Studio und OpenAI-kompatible Gateways",
                "Dedizierte HTTP/SOCKS5-Proxy-Bindung pro Provider-Anmeldedaten"
            ],
            "ja": [
                "OpenAI、Anthropic、Gemini、Groq、DeepSeek、Cerebras、Mistral、xAI、OpenRouterに完全対応",
                "Keylessモード：ローカルOllama（http://localhost:11434）をダミーキー不要で直接連携",
                "vLLM、LM Studio、OpenAI互換の企業内エンドポイント向けのカスタムBase URL設定",
                "プロバイダー認証情報ごとに専用のHTTP/SOCKS5プロキシを設定可能"
            ],
            "pt": [
                "Suporte total a OpenAI, Anthropic, Gemini, Groq, DeepSeek, Cerebras, Mistral, xAI, OpenRouter",
                "Modo Keyless: conecte o Ollama local (http://localhost:11434) sem necessidade de chaves falsas",
                "Suporte a Base URL personalizada para vLLM, LM Studio e gateways corporativos",
                "Vinculação dedicada de proxy HTTP/SOCKS5 por credencial de provedor"
            ],
            "ar": [
                "دعم شامل لـ OpenAI وAnthropic وGemini وGroq وDeepSeek وCerebras وMistral وxAI وOpenRouter",
                "الوضع بدون مفتاح: ربط Ollama المحلي (http://localhost:11434) دون الحاجة لمفاتيح وهمية",
                "دعم العناوين الأساسية المخصصة (Base URL) لـ vLLM وLM Studio والبوابات المؤسسية المتوافقة",
                "ربط بروكسي HTTP/SOCKS5 مخصص لكل مزود ومفتاح اعتماد"
            ],
            "hi": [
                "OpenAI, Anthropic, Gemini, Groq, DeepSeek, Cerebras, Mistral, xAI, OpenRouter का पूर्ण समर्थन",
                "की-लेस मोड: फर्जी एपीआई की के बिना स्थानीय ओलामा (http://localhost:11434) को कनेक्ट करें",
                "vLLM, LM Studio और ओपनएआई-संगत कॉर्पोरेट गेटवे के लिए कस्टम बेस यूआरएल समर्थन",
                "प्रति प्रदाता क्रेडेंशियल के लिए समर्पित HTTP/SOCKS5 प्रॉक्सी बाइंडिंग"
            ],
            "bn": [
                "OpenAI, Anthropic, Gemini, Groq, DeepSeek, Cerebras, Mistral, xAI, OpenRouter এর সম্পূর্ণ সমর্থন",
                "কী-লেস মোড: ডামি চাবি ছাড়াই স্থানীয় ওলামা (http://localhost:11434) সংযুক্ত করুন",
                "vLLM, LM Studio এবং কর্পোরেট গেটওয়ের জন্য কাস্টম বেস URL সমর্থন",
                "প্রতিটি প্রদানকারীর জন্য পৃথক HTTP/SOCKS5 প্রক্সি সংযোগ"
            ]
        },
        "subsections": [
            {
                "titles": {
                    "en": "Provider Capabilities Matrix", "ru": "Матрица возможностей провайдеров", "uk": "Матриця можливостей провайдерів", "be": "Матрыца магчымасцей правайдэраў",
                    "zh": "服务商特性与协议矩阵", "es": "Matriz de capacidades de proveedores", "fr": "Matrice des capacités des fournisseurs", "de": "Provider-Leistungsmatrix",
                    "ja": "プロバイダー機能マトリクス", "pt": "Matriz de Recursos dos Provedores", "ar": "مصفوفة إمكانيات المزودين", "hi": "प्रदाता क्षमता मैट्रिक्स", "bn": "প্রদানকারী সক্ষমতা ম্যাট্রিক্স"
                },
                "table": {
                    "headers": ["Provider", "ID", "Default Base URL", "Keyless", "Streaming"],
                    "rows": [
                        ["OpenAI", "openai", "https://api.openai.com/v1", "No", "Yes (SSE)"],
                        ["Google Gemini", "gemini", "https://generativelanguage.googleapis.com", "No", "Yes (SSE)"],
                        ["Anthropic", "anthropic", "https://api.anthropic.com/v1", "No", "Yes (SSE)"],
                        ["Groq", "groq", "https://api.groq.com/openai/v1", "No", "Yes (SSE)"],
                        ["Ollama (Local)", "ollama", "http://localhost:11434", "Yes", "Yes (SSE/NDJSON)"],
                        ["DeepSeek", "deepseek", "https://api.deepseek.com", "No", "Yes (SSE)"],
                        ["Cerebras", "cerebras", "https://api.cerebras.ai/v1", "No", "Yes (SSE)"],
                        ["OpenRouter", "openrouter", "https://openrouter.ai/api/v1", "No", "Yes (SSE)"],
                        ["Mistral AI", "mistral", "https://api.mistral.ai/v1", "No", "Yes (SSE)"],
                        ["xAI (Grok)", "xai", "https://api.x.ai/v1", "No", "Yes (SSE)"]
                    ]
                }
            },
            {
                "titles": {
                    "en": "Configuring Local Ollama Keyless Mode", "ru": "Настройка Keyless-режима для Ollama", "uk": "Налаштування Keyless-режиму для Ollama", "be": "Налада Keyless-рэжыму для Ollama",
                    "zh": "配置本地 Ollama 免密直连", "es": "Configuración de Ollama local sin clave", "fr": "Configuration d'Ollama local sans clé", "de": "Lokalen Ollama Keyless-Modus konfigurieren",
                    "ja": "ローカルOllamaのKeylessモード設定", "pt": "Configurando Ollama Local em Modo Keyless", "ar": "إعداد الوضع بدون مفتاح لـ Ollama المحلي", "hi": "स्थानीय ओलामा की-लेस मोड को कॉन्फ़िगर करना", "bn": "স্থানীয় ওলামা কী-লেস মোড কনফিগারেশন"
                },
                "code": {
                    "title": "Add Ollama via API or UI",
                    "lang": "bash",
                    "content": """curl -X POST http://localhost:8000/api/v1/credentials \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer ADMIN_SESSION_TOKEN" \\
  -d '{
    "provider": "ollama",
    "name": "Local Workstation Ollama",
    "api_key": "keyless",
    "base_url": "http://127.0.0.1:11434",
    "is_active": true
  }'"""
                }
            }
        ]
    },
    {
        "id": "credentials",
        "group": "management",
        "badge": "Encrypted Vault",
        "titles": {
            "en": "Upstream Credentials & Key Vault",
            "ru": "Управление ключами провайдеров (Vault)",
            "uk": "Керування ключами провайдерів (Vault)",
            "be": "Кіраванне ключамі правайдэраў (Vault)",
            "zh": "上游服务凭证与加密保险库",
            "es": "Credenciales y bóveda de claves",
            "fr": "Identifiants amont et coffre-fort de clés",
            "de": "Upstream-Anmeldedaten & Key-Vault",
            "ja": "上流プロバイダー認証情報と暗号化保管庫",
            "pt": "Credenciais Upstream e Cofre de Chaves",
            "ar": "بيانات اعتماد المزودين وخزنة المفاتيح المشفرة",
            "hi": "अपस्ट्रीम क्रेडेंशियल और की-वॉल्ट",
            "bn": "আপস্ট্রিম শংসাপত্র এবং কী ভল্ট"
        },
        "descriptions": {
            "en": "Bank-grade encrypted storage for upstream LLM provider API keys, featuring health checks, auto-disable, and group tagging.",
            "ru": "Хранилище API-ключей с шифрованием банковского уровня, автоматической проверкой работоспособности и группировкой по папкам.",
            "uk": "Сховище API-ключів із банківським шифруванням, автоматичною перевіркою працездатності та групуванням за папками.",
            "be": "Сховішча API-ключаў з банкаўскім шыфраваннем, аўтаматычнай праверкай працаздольнасці і групаваннем па папках.",
            "zh": "银行级加密存储各类大模型上游 API Key，具备自动健康巡检、故障自动下线以及分组管理功能。",
            "es": "Almacenamiento cifrado de nivel bancario para claves API de proveedores, con comprobaciones de estado y grupos de etiquetas.",
            "fr": "Stockage chiffré de niveau bancaire pour les clés API des fournisseurs, avec vérification de santé et balisage par groupe.",
            "de": "Bankenkonforme, verschlüsselte Speicherung für Upstream-API-Schlüssel mit Health-Checks, Auto-Disable und Gruppenverwaltung.",
            "ja": "アップストリームAPIキーを銀行水準で暗号化保存。健全性チェック、障害自動切り離し、グループフォルダ管理に対応。",
            "pt": "Armazenamento criptografado de nível bancário para chaves API com verificações de integridade e organização em grupos.",
            "ar": "تخزين مشفر بمعايير بنكية لمفاتيح مزودي الخدمة مع فحوصات دورية للسلامة والتعطيل التلقائي وإدارة المجموعات.",
            "hi": "अपस्ट्रीम एपीआई कुंजियों के लिए बैंक-ग्रेड एन्क्रिप्टेड स्टोरेज, स्वचालित स्वास्थ्य जांच और ग्रुप वर्गीकरण के साथ।",
            "bn": "আপস্ট্রিম এপিআই কীগুলির জন্য ব্যাংক-গ্রেড এনক্রিপ্ট করা স্টোরেজ, অটো হেলথ চেক এবং গ্রুপ সংগঠনের সুবিধা সহ।"
        },
        "highlights": {
            "en": [
                "AES-128-CBC Fernet symmetric encryption: keys are encrypted before SQLite insertion",
                "Key Masking: Raw secrets are never exposed in UI or logs (displays e.g. sk-ant...7a9f)",
                "Proactive Health Checks: Automatic ping testing against provider validation endpoints",
                "Credential Groups: Organize keys into logical folders (Production, Staging, Backup, Team)"
            ],
            "ru": [
                "Симметричное шифрование AES-128-CBC Fernet: ключи шифруются перед записью в SQLite",
                "Маскирование ключей: исходные секреты никогда не передаются в интерфейс (например, sk-ant...7a9f)",
                "Автоматические Health-чеки: регулярная проверка валидности ключей и квот провайдера",
                "Группы учетных записей: разделение ключей по папкам (Production, Staging, Backup, Team)"
            ],
            "uk": [
                "Симетричне шифрування AES-128-CBC Fernet: ключі шифруються перед записом у SQLite",
                "Маскування ключів: секрети ніколи не потрапляють в інтерфейс чи логи (наприклад, sk-ant...7a9f)",
                "Автоматичні Health-чеки: регулярна перевірка валідності ключів та квот провайдера",
                "Групи облікових записів: розділення ключів по папках (Production, Staging, Backup, Team)"
            ],
            "be": [
                "Сіметрычнае шыфраванне AES-128-CBC Fernet: ключы шыфруюцца перад запісам у SQLite",
                "Маскіраванне ключоў: сакрэты ніколі не перадаюцца ў інтэрфейс (напрыклад, sk-ant...7a9f)",
                "Аўтаматычныя Health-чэкі: рэгулярная праверка валіднасці ключоў і квот правайдэра",
                "Групы ўліковых запісаў: падзел ключоў па папках (Production, Staging, Backup, Team)"
            ],
            "zh": [
                "AES-128-CBC Fernet 对称加密：入库前自动全密文存储，内存按需解密",
                "安全密钥脱敏：前端及日志永久脱敏展示（例如 sk-ant...7a9f），严防泄露",
                "主动健康巡检：一键与定时探活验证 API Key 有效性与可用配额",
                "凭证逻辑分组：支持自定义文件夹分组（生产组、预发组、备用池、各业务线）"
            ],
            "es": [
                "Cifrado simétrico AES-128-CBC Fernet: las claves se cifran antes de guardarse en SQLite",
                "Enmascaramiento de claves: los secretos nunca se exponen en UI o registros (ej. sk-ant...7a9f)",
                "Verificaciones proactivas de estado: sondeo de prueba contra los endpoints del proveedor",
                "Grupos de credenciales: organice claves en carpetas (Producción, Pruebas, Respaldo)"
            ],
            "fr": [
                "Chiffrement symétrique AES-128-CBC Fernet : clés chiffrées avant insertion SQLite",
                "Masquage des clés : les secrets ne sont jamais exposés dans l'interface (ex. sk-ant...7a9f)",
                "Contrôles de santé proactifs : tests de connectivité réguliers auprès des fournisseurs",
                "Groupes d'identifiants : organisez les clés en dossiers logiques (Prod, Staging, Backup)"
            ],
            "de": [
                "Symmetrische AES-128-CBC Fernet-Verschlüsselung vor dem Speichern in SQLite",
                "Schlüssel-Maskierung: Rohe Schlüssel werden niemals in UI oder Logs angezeigt (z. B. sk-ant...7a9f)",
                "Proaktive Health-Checks: Regelmäßige Überprüfung der Gültigkeit und Quoten bei Providern",
                "Anmeldedaten-Gruppen: Strukturierung in logische Ordner (Produktion, Staging, Backup)"
            ],
            "ja": [
                "AES-128-CBC Fernet 暗号化：SQLite 保存前に全キーを暗号化、メモリ内でのみ復号",
                "キーのマスキング表示：UIやログには生キーを出力せず末尾のみ表示（例: sk-ant...7a9f）",
                "プロアクティブな死活監視：プロバイダーのエンドポイントへ定期的にヘルスチェック",
                "認証情報グループ：本番環境、ステージング、バックアッププールなどのフォルダ分類"
            ],
            "pt": [
                "Criptografia simétrica AES-128-CBC Fernet: chaves criptografadas antes da gravação",
                "Mascaramento de chaves: os segredos nunca são exibidos na interface (ex: sk-ant...7a9f)",
                "Verificações ativas de integridade: testes automáticos de conectividade e cotas",
                "Grupos de credenciais: organize chaves em pastas (Produção, Staging, Backup)"
            ],
            "ar": [
                "تشفير متماثل AES-128-CBC Fernet: تشفير المفاتيح بالكامل قبل حفظها في قاعدة البيانات",
                "إخفاء الأسرار: عدم عرض المفاتيح الأصلية في الواجهة أو السجلات (مثل sk-ant...7a9f)",
                "فحوصات سلامة استباقية: اختبار آلي لصلاحية المفتاح ورصيد الحساب لدى المزود",
                "مجموعات الاعتماد: تنظيم المفاتيح في مجلدات منطقية (إنتاج، تجارب، احتياط)"
            ],
            "hi": [
                "AES-128-CBC फ़र्नेट एन्क्रिप्शन: SQLite में सहेजने से पहले कुंजियों को एन्क्रिप्ट किया जाता है",
                "की मास्किंग: मूल रहस्य कभी भी UI या लॉग में प्रदर्शित नहीं होते (उदा. sk-ant...7a9f)",
                "सक्रिय स्वास्थ्य जांच: प्रदाता सत्यापन एंडपॉइंट्स पर नियमित जांच",
                "क्रेडेंशियल समूह: कुंजियों को फ़ोल्डरों में व्यवस्थित करें (प्रोडक्शन, स्टेजिंग, बैकअप)"
            ],
            "bn": [
                "AES-128-CBC ফার্নেট এনক্রিপশন: ডাটাবেসে সেভ করার পূর্বে প্রতিটি কী এনক্রিপ্ট করা হয়",
                "কী মাস্কিং: গোপন কোড কখনই ইন্টারফেসে প্রকাশিত হয় না (যেমন sk-ant...7a9f)",
                "অটোমেটিক হেলথ চেক: প্রদানকারীর কাছে নিয়মিত পরীক্ষা ও কোটা যাচাইকরণ",
                "শংসাপত্র গ্রুপিং: চাবিগুলিকে ফোল্ডারে সংগঠিত করুন (প্রোডাকশন, স্টেজিং, ব্যাকআপ)"
            ]
        },
        "subsections": [
            {
                "titles": {
                    "en": "Triggering Health Verification", "ru": "Ручной запуск проверки ключа", "uk": "Ручний запуск перевірки ключа", "be": "Ручны запуск праверкі ключа",
                    "zh": "手动触发凭证健康检查", "es": "Verificación manual de credenciales", "fr": "Vérification manuelle des identifiants", "de": "Manuelle Health-Überprüfung anstoßen",
                    "ja": "認証情報のヘルスチェック実行", "pt": "Disparando Verificação de Integridade", "ar": "تشغيل فحص السلامة يدوياً", "hi": "स्वास्थ्य सत्यापन शुरू करना", "bn": "ম্যানুয়াল হেলথ ভেরিফিকেশন চালানো"
                },
                "code": {
                    "title": "Health Check Endpoint",
                    "lang": "bash",
                    "content": """curl -X POST http://localhost:8000/api/v1/credentials/cred_abc123/health-check \\
  -H "Authorization: Bearer ADMIN_SESSION_TOKEN"

# Response:
# {
#   "status": "healthy",
#   "latency_ms": 142.5,
#   "checked_at": "2026-09-13T14:15:00Z"
# }"""
                }
            }
        ]
    },
    {
        "id": "api-keys",
        "group": "management",
        "badge": "Access Governance",
        "titles": {
            "en": "Router API Keys & Permissions",
            "ru": "Клиентские API-ключи и права доступа",
            "uk": "Клієнтські API-ключі та права доступу",
            "be": "Кліенцкія API-ключы і правы доступу",
            "zh": "客户端 API 密钥与访问授权",
            "es": "Claves API del enrutador y permisos",
            "fr": "Clés API du routeur et autorisations",
            "de": "Router-API-Schlüssel & Berechtigungen",
            "ja": "クライアントAPIキーとアクセス権限",
            "pt": "Chaves API do Router e Permissões",
            "ar": "مفاتيح API للعملاء وصلاحيات الوصول",
            "hi": "राउटर एपीआई कुंजियाँ और अनुमतियाँ",
            "bn": "রাউটার এপিআই কী এবং অনুমতি"
        },
        "descriptions": {
            "en": "Issue, monitor, and revoke client access tokens (sk-router-...) with per-key rate limits (RPM/TPM) and model whitelisting.",
            "ru": "Выпуск, мониторинг и отзыв клиентских токенов доступа (sk-router-...) с индивидуальными лимитами RPM/TPM и белыми списками моделей.",
            "uk": "Випуск, моніторинг та відкликання клієнтських токенів доступу (sk-router-...) з індивідуальними лімітами RPM/TPM та білими списками моделей.",
            "be": "Выпуск, маніторынг і адкліканне кліенцкіх токенаў доступу (sk-router-...) з індывідуальнымі лімітамі RPM/TPM і белымі спісамі мадэляў.",
            "zh": "签发、监管并吊销客户端访问令牌 (sk-router-...)，精细配置单密钥速率配额 (RPM/TPM) 及允许调用的模型白名单。",
            "es": "Emita, supervise y revoque tokens de acceso de clientes (sk-router-...) con límites de tasa por clave y listas blancas de modelos.",
            "fr": "Émettez, surveillez et révoquez des jetons clients (sk-router-...) avec limites de débit par clé et listes blanches de modèles.",
            "de": "Erstellen, überwachen und widerrufen Sie Client-Token (sk-router-...) mit individuellen RPM/TPM-Limits und Modell-Whitelists.",
            "ja": "クライアント用アクセストークン（sk-router-...）の発行・監視・失効管理。キーごとのRPM/TPM制限やモデル許可リストを設定可能。",
            "pt": "Emita, monitore e revogue tokens de clientes (sk-router-...) com limites individuais de taxa e listas de modelos permitidos.",
            "ar": "إصدار ومراقبة وإلغاء رموز وصول العملاء (sk-router-...) مع تحديد حدود الطلبات وحصص النماذج المصرح بها.",
            "hi": "क्लाइंट एक्सेस टोकन (sk-router-...) जारी करें, दर सीमाएँ (RPM/TPM) और मॉडल श्वेतसूची कॉन्फ़िगर करें।",
            "bn": "ক্লায়েন্ট অ্যাক্সেস টোকেন (sk-router-...) ইস্যু এবং প্রত্যাহার করুন, প্রতি-কী রেট সীমা এবং মডেল হোয়াইটলিস্ট সহ।"
        },
        "highlights": {
            "en": [
                "SHA-256 One-Way Hash: Secret keys are never stored in plaintext and cannot be extracted from database",
                "Rate Limiting: Granular limits on Requests Per Minute (RPM) and Tokens Per Minute (TPM)",
                "Model Whitelisting: Restrict specific keys to defined models (e.g. ['gpt-4o', 'fusion/code-jury'])",
                "Automatic Expiry: Set expiration dates for contract teams, interns, or temporary demo deployments"
            ],
            "ru": [
                "Необратимое хеширование SHA-256: секретные ключи не хранятся в открытом виде в БД",
                "Квоты и лимиты: раздельный контроль запросов в минуту (RPM) и токенов в минуту (TPM)",
                "Белые списки моделей: ограничение доступа только к разрешенным моделям и профилям",
                "Срок действия (TTL): автоматическое отключение ключей по истечении заданной даты"
            ],
            "uk": [
                "Незворотне хешування SHA-256: секретні ключі не зберігаються у відкритому вигляді в БД",
                "Квоти та ліміти: окремий контроль запитів на хвилину (RPM) і токенів на хвилину (TPM)",
                "Білі списки моделей: обмеження доступу лише до дозволених моделей та профілів",
                "Термін дії (TTL): автоматичне відключення ключів після закінчення вказаної дати"
            ],
            "be": [
                "Незваротнае хэшаванне SHA-256: сакрэтныя ключы не захоўваюцца ў адкрытым выглядзе ў БД",
                "Квоты і ліміты: асобны кантроль запытаў у хвіліну (RPM) і токенаў у хвіліну (TPM)",
                "Белыя спісы мадэляў: абмежаванне доступу толькі да дазволеных мадэляў і профіляў",
                "Тэрмін дзеяння (TTL): аўтаматычнае адключэнне ключоў пасля заканчэння пазначанай даты"
            ],
            "zh": [
                "SHA-256 单向哈希：数据库仅持久化密钥散列值，明文仅在创建瞬间展示一次",
                "严格速率配额：精细限制每分钟请求数 (RPM) 与每分钟 Token 吞吐量 (TPM)",
                "模型访问白名单：限定该密钥仅能调用指定模型或路由画像，防止未授权消耗",
                "有效期自动过期：支持为外包团队、临时测试或演示环境设置自动过期时间戳"
            ],
            "es": [
                "Hash unidireccional SHA-256: las claves secretas nunca se guardan en texto claro en la base de datos",
                "Límites de tasa: control granular de solicitudes por minuto (RPM) y tokens por minuto (TPM)",
                "Lista blanca de modelos: restrinja claves a modelos o perfiles de enrutamiento autorizados",
                "Caducidad automática: configure fechas de expiración para accesos temporales o demostraciones"
            ],
            "fr": [
                "Hachage SHA-256 unidirectionnel : les clés secrètes ne sont jamais enregistrées en clair",
                "Limites de débit : contrôle précis des requêtes par minute (RPM) et tokens par minute (TPM)",
                "Liste blanche de modèles : restreignez l'accès à des modèles ou profils spécifiques",
                "Expiration automatique : définissez des dates de fin de validité pour les accès temporaires"
            ],
            "de": [
                "SHA-256 One-Way-Hash: Geheime Schlüssel werden niemals im Klartext in der Datenbank gespeichert",
                "Ratenbegrenzung: Granulare Limits für Anfragen pro Minute (RPM) und Tokens pro Minute (TPM)",
                "Modell-Whitelist: Beschränken Sie Schlüssel auf ausgewählte Modelle oder Routing-Profile",
                "Automatischer Ablauf: Festlegen von Ablaufdaten für temporäre Test- oder Team-Schlüssel"
            ],
            "ja": [
                "SHA-256 一方向ハッシュ：秘密キーは平文保存されず、データベース流出時も復元不可能",
                "レート制限：分あたりリクエスト数（RPM）と分あたりトークン数（TPM）を個別制御",
                "モデル許可リスト：指定したモデルやルートプロファイルのみ呼び出し可能に制限",
                "有効期限（TTL）：一時的な開発チームやデモ用に自動失効日時を設定可能"
            ],
            "pt": [
                "Hash unidirecional SHA-256: chaves secretas nunca são salvas em texto simples no banco",
                "Limitação de taxa: controle granular de requisições por minuto (RPM) e tokens por minuto (TPM)",
                "Whitelist de modelos: restrinja chaves a modelos ou perfis de roteamento específicos",
                "Expiração automática: defina prazos de validade para acessos temporários de equipe"
            ],
            "ar": [
                "تشفير أحادي الاتجاه SHA-256: لا يتم تخزين المفاتيح كنصوص صريحة نهائياً في قاعدة البيانات",
                "تحديد معدل الاستخدام: ضبط دقيق لعدد الطلبات في الدقيقة (RPM) والرموز في الدقيقة (TPM)",
                "القوائم البيضاء للنماذج: قصر صلاحية المفتاح على نماذج معينة دون غيرها لمنع الاستنزاف",
                "انتهاء الصلاحية التلقائي: تحديد تاريخ ووقت انتهاء الصلاحية للمفاتيح المؤقتة"
            ],
            "hi": [
                "SHA-256 वन-वे हैश: गुप्त कुंजियों को डेटाबेस में कभी भी सादे पाठ में संग्रहीत नहीं किया जाता",
                "दर सीमा: प्रति मिनट अनुरोध (RPM) और प्रति मिनट टोकन (TPM) पर बारीक नियंत्रण",
                "मॉडल श्वेतसूची: विशिष्ट मॉडलों तक सीमित पहुंच की अनुमति दें",
                "स्वचालित समाप्ति: अस्थायी एक्सेस के लिए समाप्ति तिथियां निर्धारित करें"
            ],
            "bn": [
                "SHA-256 ওয়ান-ওয়ে হ্যাশ: গোপন চাবি ডাটাবেসে প্লেইন টেক্সট হিসেবে সংরক্ষিত থাকে না",
                "রেট লিমিটিং: প্রতি মিনিটে রিকোয়েস্ট (RPM) এবং টোকেন (TPM) এর সুনির্দিষ্ট নিয়ন্ত্রণ",
                "মডেল হোয়াইটলিস্ট: নির্দিষ্ট মডেল বা রুটে অ্যাক্সেস সীমাবদ্ধ করুন",
                "স্বয়ংক্রিয় মেয়াদোত্তীর্ণ: অস্থায়ী অ্যাক্সেসের জন্য এক্সপায়ারি তারিখ নির্ধারণ করুন"
            ]
        },
        "subsections": [
            {
                "titles": {
                    "en": "Client Key Parameters Reference", "ru": "Параметры клиентского ключа", "uk": "Параметри клієнтського ключа", "be": "Параметры кліенцкага ключа",
                    "zh": "客户端密钥参数规范", "es": "Referencia de parámetros de claves", "fr": "Paramètres des clés clientes", "de": "Client-Schlüssel Parameter",
                    "ja": "クライアントキー パラメータ仕様", "pt": "Parâmetros da Chave do Cliente", "ar": "مرجع معلمات مفتاح العميل", "hi": "क्लाइंट कुंजी पैरामीटर संदर्भ", "bn": "ক্লায়েন্ট কী প্যারামিটার রেফারেন্স"
                },
                "table": {
                    "headers": ["Field", "Type", "Default", "Description"],
                    "rows": [
                        ["name", "string", "Required", "Human-readable label for the client or application"],
                        ["rate_limit_rpm", "integer", "null (unlimited)", "Maximum allowed HTTP requests per 60-second window"],
                        ["rate_limit_tpm", "integer", "null (unlimited)", "Maximum total tokens allowed per 60-second window"],
                        ["allowed_models", "string[]", "null (all models)", "Array of model slugs permitted for inference"],
                        ["expires_at", "ISO string", "null (never)", "UTC timestamp after which requests return HTTP 401"]
                    ]
                }
            }
        ]
    },
    {
        "id": "proxies",
        "group": "management",
        "badge": "Egress & Geo",
        "titles": {
            "en": "Proxy Management & Geo-Tagging",
            "ru": "Прокси-серверы и гео-маршрутизация",
            "uk": "Проксі-сервери та гео-маршрутизація",
            "be": "Проксі-серверы і геа-маршрутызацыя",
            "zh": "代理池管理与地域标签路由",
            "es": "Gestión de proxies y etiquetado geográfico",
            "fr": "Gestion des proxys et étiquetage géographique",
            "de": "Proxy-Verwaltung & Geo-Tagging",
            "ja": "プロキシ管理と地域タグルーティング",
            "pt": "Gerenciamento de Proxies e Geo-Tagging",
            "ar": "إدارة البروكسي والتوجيه الجغرافي",
            "hi": "प्रॉक्सी प्रबंधन और भू-टैगिंग",
            "bn": "প্রক্সি পরিচালনা এবং জিও-ট্যাগিং"
        },
        "descriptions": {
            "en": "Route upstream traffic through authenticated HTTP and SOCKS5 proxies with automatic latency benchmarking and regional country tags.",
            "ru": "Маршрутизация запросов к провайдерам через HTTP и SOCKS5 прокси с измерением задержки и обходом региональных блокировок.",
            "uk": "Маршрутизація запитів до провайдерів через HTTP та SOCKS5 проксі з вимірюванням затримки та обходом блокувань.",
            "be": "Маршрутызацыя запытаў да правайдэраў праз HTTP і SOCKS5 проксі з вымярэннем затрымкі і абыходам блакаванняў.",
            "zh": "通过支持身份认证的 HTTP/SOCKS5 代理调度上游流量，内置实时延迟探测与国家区域标签，轻松突破地域限制。",
            "es": "Enrute el tráfico ascendente mediante proxies HTTP y SOCKS5 autenticados con medición de latencia y etiquetas regionales.",
            "fr": "Acheminez le trafic amont via des proxys HTTP et SOCKS5 avec authentification, suivi de latence et drapeaux géographiques.",
            "de": "Leiten Sie Upstream-Traffic über authentifizierte HTTP- und SOCKS5-Proxies mit Latenz-Benchmarks und Geo-Länder-Tags.",
            "ja": "認証付きHTTP/SOCKS5プロキシを経由して上流通信をルーティング。遅延測定機能や国別タグによる地域制限回避に対応。",
            "pt": "Roteie o tráfego upstream através de proxies HTTP e SOCKS5 autenticados com medição de latência e tags regionais.",
            "ar": "توجيه حركة المرور عبر بروكسيات HTTP وSOCKS5 مصادق عليها مع قياس زمن الاستجابة وتصنيف الدول لتجاوز الحجب الجغرافي.",
            "hi": "प्रमाणीकृत HTTP और SOCKS5 प्रॉक्सी के माध्यम से अपस्ट्रीम ट्रैफ़िक को रूट करें, विलंबता बेंचमार्किंग और क्षेत्रीय टैग के साथ।",
            "bn": "প্রমাণীকৃত HTTP এবং SOCKS5 প্রক্সির মাধ্যমে ট্র্যাফিক রুট করুন, লেটেন্সি পরিমাপ এবং আঞ্চলিক ট্যাগিং সহ।"
        },
        "highlights": {
            "en": [
                "Full Protocol Support: HTTP, HTTPS, and SOCKS5 (socks5://user:pass@host:port)",
                "Country / Geo Flags: Assign ISO codes (US, DE, SG, JP) to match provider regional requirements",
                "Latency Benchmarking: Real-time round-trip time (RTT) test on every proxy save and health check",
                "Per-Credential Isolation: Assign dedicated proxies to individual API keys or entire providers"
            ],
            "ru": [
                "Поддержка протоколов: HTTP, HTTPS и SOCKS5 (socks5://user:pass@host:port)",
                "Гео-метки стран: привязка ISO-кодов (US, DE, SG, JP) для обхода ограничений провайдеров",
                "Замер пинга и задержки: автоматический тест RTT при добавлении и плановой проверке",
                "Изоляция на уровне ключа: привязка выделенного прокси к конкретному ключу или провайдеру"
            ],
            "uk": [
                "Підтримка протоколів: HTTP, HTTPS та SOCKS5 (socks5://user:pass@host:port)",
                "Гео-мітки країн: прив'язка ISO-кодів (US, DE, SG, JP) для обходу обмежень провайдерів",
                "Замір пінгу та затримки: автоматичний тест RTT при додаванні та плановій перевірці",
                "Ізоляція на рівні ключа: прив'язка виділеного проксі до конкретного ключа чи провайдера"
            ],
            "be": [
                "Падтрымка пратаколаў: HTTP, HTTPS і SOCKS5 (socks5://user:pass@host:port)",
                "Геа-меткі краін: прывязка ISO-кодаў (US, DE, SG, JP) для абыходу абмежаванняў правайдэраў",
                "Замер пінгу і затрымкі: аўтаматычны тэст RTT пры даданні і планавай праверцы",
                "Ізаляцыя на ўзроўні ключа: прывязка вылучанага проксі да канкрэтнага ключа ці правайдэра"
            ],
            "zh": [
                "全协议支持：完美兼容 HTTP, HTTPS 以及 SOCKS5 (socks5://user:pass@host:port)",
                "国家与地理标签：支持分配 ISO 国家代码（如 US, DE, SG, JP 等），满足合规与跨境访问",
                "实时延迟基准测试：添加与巡检时自动测试握手 RTT 往返耗时，直观标注优劣",
                "按凭证独立绑定：可为特定的 API Key 单独绑定代理，实现多账号多出口 IP 隔离"
            ],
            "es": [
                "Soporte completo de protocolos: HTTP, HTTPS y SOCKS5 (socks5://user:pass@host:port)",
                "Banderas de país: asigne códigos ISO (US, DE, SG, JP) para cumplir requisitos geográficos",
                "Pruebas de latencia: medición del tiempo de ida y vuelta (RTT) en tiempo real",
                "Aislamiento por credencial: asigne proxies dedicados a claves o proveedores individuales"
            ],
            "fr": [
                "Prise en charge complète : HTTP, HTTPS et SOCKS5 (socks5://user:pass@host:port)",
                "Drapeaux géographiques : associez des codes ISO (US, DE, SG, JP) pour contourner les blocages",
                "Mesure de latence : test du temps d'aller-retour (RTT) en temps réel à chaque vérification",
                "Isolation par identifiant : assignez un proxy dédié à une clé ou un fournisseur spécifique"
            ],
            "de": [
                "Vollständige Protokollunterstützung: HTTP, HTTPS und SOCKS5 (socks5://user:pass@host:port)",
                "Länder-Tags: ISO-Codes (US, DE, SG, JP) zuweisen, um regionale Anforderungen zu erfüllen",
                "Latenz-Messung: Echtzeit-RTT-Test beim Speichern und bei periodischen Health-Checks",
                "Isolierung pro Anmeldedaten: Dedizierte Proxies einzelnen Schlüsseln oder Providern zuweisen"
            ],
            "ja": [
                "全プロトコル対応：HTTP、HTTPS、SOCKS5（socks5://user:pass@host:port）を完全サポート",
                "国・地域タグ設定：ISO国コード（US, DE, SG, JP）を指定して各社の地域制限をスマートに回避",
                "リアルタイム遅延計測：プロキシ保存時およびヘルスチェック時にRTT往復遅延を測定",
                "認証情報ごとの独立割当：特定のAPIキーやプロバイダー専用のプロキシ経路をバインド可能"
            ],
            "pt": [
                "Suporte completo a protocolos: HTTP, HTTPS e SOCKS5 (socks5://user:pass@host:port)",
                "Tags de país: atribua códigos ISO (US, DE, SG, JP) para cumprir requisitos regionais",
                "Benchmarking de latência: teste de tempo de ida e volta (RTT) em tempo real",
                "Isolamento por credencial: associe proxies dedicados a chaves ou provedores específicos"
            ],
            "ar": [
                "دعم كامل للبروتوكولات: HTTP وHTTPS وSOCKS5 (بالمصادقة الكاملة)",
                "أعلام ورموز الدول: تعيين رموز ISO (مثل US وDE وSG وJP) لتخطي القيود الإقليمية للمزودين",
                "قياس زمن الاستجابة: فحص مباشر لزمن انتقال البيانات ذهاباً وإياباً (RTT) عند كل اختبار",
                "عزل لكل اعتماد: تخصيص بروكسي مستقل لكل مفتاح API أو لكل مزود خدمة"
            ],
            "hi": [
                "पूर्ण प्रोटोकॉल समर्थन: HTTP, HTTPS, और SOCKS5 (socks5://user:pass@host:port)",
                "देश / भू-टैग: क्षेत्रीय आवश्यकताओं को पूरा करने के लिए ISO कोड (US, DE, SG) निर्दिष्ट करें",
                "विलंबता बेंचमार्किंग: प्रत्येक प्रॉक्सी सहेजने पर रीयल-टाइम RTT राउंड-ट्रिप परीक्षण",
                "क्रेडेंशियल स्तर पर अलगाव: व्यक्तिगत एपीआई कुंजियों को समर्पित प्रॉक्सी असाइन करें"
            ],
            "bn": [
                "সম্পূর্ণ প্রোটোকল সমর্থন: HTTP, HTTPS এবং SOCKS5 (socks5://user:pass@host:port)",
                "দেশ ও জিও ট্যাগ: আঞ্চলিক বিধিনিষেধ অতিক্রম করতে ISO কোড (US, DE, SG, JP) নির্ধারণ করুন",
                "লেটেন্সি বেঞ্চমার্কিং: রিয়েল-টাইমে রাউন্ড-ট্রিপ সময় (RTT) পরীক্ষা",
                "চাবি অনুযায়ী পৃথক প্রক্সি: নির্দিষ্ট চাবি বা সরবরাহকারীর জন্য ডেডিকেটেড প্রক্সি বরাদ্দ করুন"
            ]
        },
        "subsections": [
            {
                "titles": {
                    "en": "Proxy Format Examples", "ru": "Форматы URI прокси-серверов", "uk": "Формати URI проксі-серверів", "be": "Фарматы URI проксі-сервераў",
                    "zh": "代理连接字符串格式示例", "es": "Ejemplos de formato de proxy", "fr": "Exemples de format de proxy", "de": "Proxy-Format-Beispiele",
                    "ja": "プロキシ接続文字列の形式例", "pt": "Exemplos de Formato de Proxy", "ar": "أمثلة على صيغ البروكسي", "hi": "प्रॉक्सी प्रारूप उदाहरण", "bn": "প্রক্সি ফরম্যাটের উদাহরণ"
                },
                "code": {
                    "title": "Supported Proxy URI Formats",
                    "lang": "bash",
                    "content": """# Standard HTTP proxy:
http://proxy.corporate.internal:8080

# Authenticated HTTP proxy:
http://username:<PROXY_PASSWORD>@us-east.proxy-vendor.com:3128

# Authenticated SOCKS5 proxy:
socks5://proxyuser:<PROXY_PASSWORD>@sg-node.vpn-provider.net:1080"""
                }
            }
        ]
    },
    {
        "id": "backup-restore",
        "group": "system",
        "badge": "Disaster Recovery",
        "titles": {
            "en": "Encrypted Backup & Disaster Recovery",
            "ru": "Резервное копирование и восстановление",
            "uk": "Резервне копіювання та відновлення",
            "be": "Рэзервовае капіраванне і аднаўленне",
            "zh": "加密备份与全量灾难恢复",
            "es": "Copia de seguridad cifrada y recuperación",
            "fr": "Sauvegarde chiffrée et reprise après sinistre",
            "de": "Verschlüsseltes Backup & Disaster Recovery",
            "ja": "暗号化バックアップとディザスタリカバリ",
            "pt": "Backup Criptografado e Recuperação",
            "ar": "النسخ الاحتياطي المشفر والتعافي من الكوارث",
            "hi": "एन्क्रिप्टेड बैकअप और डिसास्टर रिकवरी",
            "bn": "এনক্রিপ্ট করা ব্যাকআপ এবং দুর্যোগ পুনরুদ্ধার"
        },
        "descriptions": {
            "en": "Export and restore entire router configurations with passphrase-derived AES-GCM encryption, covering models, routes, credentials, and proxies.",
            "ru": "Экспорт и импорт полной конфигурации шлюза с шифрованием AES-GCM по мастер-паролю (модели, маршруты, ключи, прокси и клиенты).",
            "uk": "Експорт та імпорт повної конфігурації шлюзу з шифруванням AES-GCM за паролем (моделі, маршрути, ключі, проксі та клієнти).",
            "be": "Экспарт і імпарт поўнай канфігурацыі шлюза з шыфраваннем AES-GCM па паролі (мадэлі, маршруты, ключы, проксі і кліенты).",
            "zh": "通过密码学 PBKDF2 与 AES-GCM 算法全量导出并恢复网关配置，涵盖模型映射、路由规则、加密密钥池、代理池及客户端凭证。",
            "es": "Exporte y restaure configuraciones completas con cifrado AES-GCM derivado de contraseña, incluyendo modelos, rutas y credenciales.",
            "fr": "Exportez et restaurez des configurations complètes avec chiffrement AES-GCM basé sur mot de passe, couvrant modèles, routes et proxys.",
            "de": "Exportieren und Wiederherstellen vollständiger Router-Konfigurationen mit Passphrase-basiertem AES-GCM-Schutz.",
            "ja": "パスフレーズから導出したAES-GCM暗号化により、ルーター全設定（モデル、ルート、資格情報、プロキシ、クライアントキー）を安全にバックアップ・復元。",
            "pt": "Exporte e restaure configurações completas com criptografia AES-GCM derivada de senha, cobrindo modelos, rotas e proxies.",
            "ar": "تصدير واستعادة كامل إعدادات الراوتر المشفرة بكلمة مرور عبر خوارزمية AES-GCM، شاملة النماذج والمسارات والبروكسيات.",
            "hi": "पासफ्रेज-व्युत्पन्न AES-GCM एन्क्रिप्शन के साथ पूरे राउटर कॉन्फ़िगरेशन को निर्यात और पुनर्स्थापित करें।",
            "bn": "পাসফ্রেজ-চালিত AES-GCM এনক্রিপশনের মাধ্যমে সম্পূর্ণ রাউটার কনফিগারেশন ব্যাকআপ এবং পুনরুদ্ধার করুন।"
        },
        "highlights": {
            "en": [
                "PBKDF2 HMAC-SHA256 key derivation with random 16-byte salt and AES-256-GCM authentication tag",
                "Full System Snapshot: Models, provider credentials, route profiles, fusion juries, proxies, API keys",
                "Selective or Full Restore: Option to merge imported entities or perform a clean replacement",
                "Zero Vendor Lock-in: Easily migrate routers across VPS nodes, Docker containers, or cloud regions"
            ],
            "ru": [
                "Деривация ключа PBKDF2 HMAC-SHA256 со случайной солью 16 байт и аутентификацией AES-256-GCM",
                "Полный снимок системы: модели, ключи провайдеров, профили маршрутов, жюри Fusion, прокси и клиенты",
                "Гибкое восстановление: возможность объединения с существующими записями или полной перезаписи",
                "Отсутствие привязки к инфраструктуре: мгновенный перенос между серверами, VPS и Docker-контейнерами"
            ],
            "uk": [
                "Деривація ключа PBKDF2 HMAC-SHA256 з випадковою сіллю 16 байт та аутентифікацією AES-256-GCM",
                "Повний знімок системи: моделі, ключі провайдерів, профілі маршрутів, журі Fusion, проксі та клієнти",
                "Гнучке відновлення: можливість об'єднання з існуючими записами або повного перезапису",
                "Відсутність прив'язки: миттєвий перенос між серверами, VPS та Docker-контейнерами"
            ],
            "be": [
                "Дэрывацыя ключа PBKDF2 HMAC-SHA256 з выпадковай соллю 16 байт і аўтэнтыфікацыяй AES-256-GCM",
                "Поўны здымак сістэмы: мадэлі, ключы правайдэраў, профілі маршрутаў, журы Fusion, проксі і кліенты",
                "Гнуткае аднаўленне: магчымасць аб'яднання з існуючымі запісамі або поўнага перазапісу",
                "Адсутнасць прывязкі: імгненны перанос паміж серверамі, VPS і Docker-кантэйнерамі"
            ],
            "zh": [
                "高强度密钥派生：基于 PBKDF2 HMAC-SHA256 算法生成高防碰撞密码衍生密钥并结合 AES-256-GCM",
                "全量系统快照：一键打包模型映射、上游密钥库、路由链路、融合评审团、代理列表及客户端授权",
                "增量合并或全量覆盖：支持与目标环境现有数据并集导入，或选择彻底重置后覆盖恢复",
                "无云端依赖：纯自托管离线迁移，秒级实现跨机房、跨 VPS 或 Docker 容器的高可用平滑迁移"
            ],
            "es": [
                "Derivación de claves PBKDF2 HMAC-SHA256 con sal aleatoria de 16 bytes y autenticación AES-256-GCM",
                "Instantánea completa: modelos, credenciales, perfiles de ruta, jurados de fusión, proxies y claves",
                "Restauración selectiva o completa: opción de fusionar entidades existentes o sustituirlas",
                "Sin dependencia de proveedor: migración sencilla entre nodos VPS, Docker o regiones en la nube"
            ],
            "fr": [
                "Dérivation de clé PBKDF2 HMAC-SHA256 avec sel aléatoire de 16 octets et tag AES-256-GCM",
                "Instantané système complet : modèles, identifiants, routes, jurys de fusion, proxys et clés",
                "Restauration sélective ou totale : option pour fusionner avec l'existant ou remplacement complet",
                "Zéro dépendance : migration facile entre serveurs VPS, conteneurs Docker ou régions cloud"
            ],
            "de": [
                "PBKDF2 HMAC-SHA256-Schlüsselableitung mit 16-Byte-Salt und AES-256-GCM-Authentifizierung",
                "Vollständiger System-Snapshot: Modelle, Provider-Keys, Routen, Fusion-Juries, Proxies, API-Keys",
                "Selektive oder vollständige Wiederherstellung: Daten zusammenführen oder sauber ersetzen",
                "Kein Vendor-Lock-in: Nahtlose Migration zwischen VPS-Instanzen, Docker-Containern und Cloud-Zonen"
            ],
            "ja": [
                "PBKDF2 HMAC-SHA256 鍵導出関数とランダムソルト、AES-256-GCM による強力な暗号化",
                "完全システムスナップショット：モデル、プロバイダー鍵、ルート、審査設定、プロキシ、クライアント鍵",
                "柔軟なリストア：既存データとのマージ統合、または完全クリーンインストールを選択可能",
                "完全セルフホスト：VPS間、Dockerコンテナ間、クラウドリージョン間の移行が瞬時に完了"
            ],
            "pt": [
                "Derivação de chaves PBKDF2 HMAC-SHA256 com salt aleatório e autenticação AES-256-GCM",
                "Snapshot completo: modelos, credenciais, perfis de rota, júris de fusão, proxies e chaves API",
                "Restauração flexível: mesclar com registros existentes ou substituição completa",
                "Sem dependência de fornecedor: migre facilmente entre instâncias VPS e contêineres Docker"
            ],
            "ar": [
                "اشتقاق مفاتيح قوي عبر PBKDF2 HMAC-SHA256 مع ملح عشوائي وتشفير موثوق AES-256-GCM",
                "لقطة كاملة للنظام: النماذج، مفاتيح المزودين، ملفات المسارات، لجان الدمج، البروكسيات والمفاتيح",
                "استعادة مرنة أو كاملة: خيار الدمج مع الإعدادات الحالية أو الاستبدال الشامل بنقرة واحدة",
                "استقلالية تامة: نقل سلس بين خوادم VPS وحاويات Docker في ثوانٍ معدودة"
            ],
            "hi": [
                "यादृच्छिक 16-बाइट सॉल्ट और AES-256-GCM टैग के साथ PBKDF2 HMAC-SHA256 कुंजी व्युत्पत्ति",
                "पूर्ण सिस्टम स्नैपशॉट: मॉडल, क्रेडेंशियल, रूट प्रोफ़ाइल, फ़्यूज़न जूरी, प्रॉक्सी, एपीआई कुंजियाँ",
                "चयनात्मक या पूर्ण पुनर्स्थापना: मौजूदा संस्थाओं को मर्ज करने या बदलने का विकल्प",
                "आसान माइग्रेशन: VPS नोड्स, डॉकर कंटेनरों के बीच त्वरित स्थानांतरण"
            ],
            "bn": [
                "PBKDF2 HMAC-SHA256 কী ডেরিভেশন এবং AES-256-GCM প্রমাণীকরণ সহ শক্তিশালী সুরক্ষা",
                "সম্পূর্ণ সিস্টেম স্ন্যাপশট: মডেল, সরবরাহকারী চাবি, রুট প্রোফাইল, ফিউশন জুরি, প্রক্সি এবং ক্লায়েন্ট চাবি",
                "নির্বাচনমূলক বা সম্পূর্ণ পুনরুদ্ধার: বিদ্যমান রেকর্ডের সাথে মার্জ বা সম্পূর্ণ প্রতিস্থাপনের বিকল্প",
                "সহজ মাইগ্রেশন: VPS এবং ডকার কন্টেইনারের মধ্যে দ্রুত ও মসৃণভাবে স্থানান্তর করুন"
            ]
        },
        "subsections": [
            {
                "titles": {
                    "en": "Export Backup via CLI", "ru": "Экспорт резервной копии через API", "uk": "Експорт резервної копії через API", "be": "Экспарт рэзервовай копіі праз API",
                    "zh": "通过 API 导出加密备份包", "es": "Exportar copia de seguridad vía API", "fr": "Exporter la sauvegarde via API", "de": "Backup per API exportieren",
                    "ja": "API経由でのバックアップ暗号化エクスポート", "pt": "Exportando Backup via API", "ar": "تصدير النسخة الاحتياطية عبر واجهة API", "hi": "एपीआई के माध्यम से बैकअप निर्यात करें", "bn": "এপিআই এর মাধ্যমে ব্যাকআপ এক্সপোর্ট"
                },
                "code": {
                    "title": "Encrypted Backup Endpoint",
                    "lang": "bash",
                    "content": """curl -X POST http://localhost:8000/api/v1/system/backup \\
  -H "Authorization: Bearer ADMIN_SESSION_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"passphrase": "<BACKUP_PASSPHRASE>"}' \\
  -o router_backup_2026-09-13.enc"""
                }
            }
        ]
    },
    {
        "id": "analytics",
        "group": "system",
        "badge": "Observability",
        "titles": {
            "en": "Analytics, Logs & Trace Inspector",
            "ru": "Аналитика, логи и Waterfall-трассировка",
            "uk": "Аналітика, логи та Waterfall-трасування",
            "be": "Аналітыка, логі і Waterfall-трасіроўка",
            "zh": "实时指标、日志与链路追踪",
            "es": "Analítica, registros e inspector de trazas",
            "fr": "Analytique, journaux et inspecteur de traces",
            "de": "Analytik, Logs & Trace-Inspektor",
            "ja": "分析、リアルタイムログ、トレース検査",
            "pt": "Análise, Logs e Inspetor de Rastreamento",
            "ar": "التحليلات والسجلات ومفتش مسارات التتبع",
            "hi": "एनालिटिक्स, लॉग और ट्रेस इंस्पेक्टर",
            "bn": "অ্যানালিটিক্স, লগ এবং ট্রেস পরিদর্শক"
        },
        "descriptions": {
            "en": "End-to-end traffic telemetry with token accounting, live spend estimation, latency charts, and interactive Waterfall trace inspection.",
            "ru": "Сквозная телеметрия трафика с учетом токенов, расчетом затрат, графиками задержек и интерактивной Waterfall-трассировкой.",
            "uk": "Наскрізна телеметрія трафіку з обліком токенів, розрахунком витрат, графіками затримок та інтерактивним Waterfall-трасуванням.",
            "be": "Скразная тэлеметрыя трафіка з улікам токенаў, разлікам выдаткаў, графікамі затрымак і інтэрактыўнай Waterfall-трасіроўкай.",
            "zh": "端到端流量监控与遥测体系：实时 Token 精准核算、费用预估、各层延迟时序图，以及直观的瀑布流重试追踪。",
            "es": "Telemetría de tráfico integral con contabilidad de tokens, estimación de costos, gráficos de latencia e inspección Waterfall.",
            "fr": "Télémétrie complète du trafic avec comptabilisation des tokens, estimation des coûts, graphiques de latence et inspection Waterfall.",
            "de": "Vollständige Traffic-Telemetrie mit Token-Abrechnung, Kostenschätzung, Latenzdiagrammen und interaktiver Waterfall-Trace-Analyse.",
            "ja": "トークン消費集計、リアルタイム利用料金試算、レイテンシ推移、フォールバックの全試行履歴を可視化するウォーターフォールトレースを完備。",
            "pt": "Telemetria de tráfego de ponta a ponta com contabilidade de tokens, estimativa de custos, gráficos de latência e inspeção Waterfall.",
            "ar": "تتبع شامل للبيانات مع رصد دقيق للرموز، وتقدير فوري للتكلفة المالية، ورسوم بيانية لأزمنة الاستجابة ومسارات الفشل والتعافي.",
            "hi": "टोकन लेखांकन, लागत अनुमान, विलंबता चार्ट और इंटरैक्टिव वॉटरफॉल ट्रेस के साथ एंड-टू-एंड टेलीमेट्री।",
            "bn": "টোকেন অ্যাকাউন্টিং, ব্যয় অনুমান, লেটেন্সি চার্ট এবং ইন্টারেক্টিভ ওয়াটারফল ট্রেস সহ সম্পূর্ণ ট্র্যাফিক টেলিমেট্রি।"
        },
        "highlights": {
            "en": [
                "Three-Fold Token Accounting: Prompt tokens, completion tokens, and reasoning tokens tracked independently",
                "Waterfall Failover Inspector: Step-by-step visual breakdown of every hop, timeout, and retry attempt",
                "Financial Spend Meter: Real-time USD cost estimation based on provider input/output pricing",
                "Exportable Audit Trail: Filter and download request logs by status code, client key, model, or date range"
            ],
            "ru": [
                "Трехмерный учет токенов: раздельный подсчет prompt-, completion- и reasoning-токенов",
                "Waterfall-трассировка: пошаговая визуализация каждой попытки, таймаута и переключения на fallback",
                "Финансовый учет: расчет оценочной стоимости в USD на основе тарифов провайдеров",
                "Экспорт аудита: фильтрация и выгрузка логов по статусам ответов, клиентам, моделям и датам"
            ],
            "uk": [
                "Тривимірний облік токенів: окремий підрахунок prompt-, completion- та reasoning-токенів",
                "Waterfall-трасування: покрокова візуалізація кожної спроби, таймауту та перемикання на fallback",
                "Фінансовий облік: розрахунок оціночної вартості в USD на основі тарифів провайдерів",
                "Експорт аудиту: фільтрація та вивантаження логів за статусами відповідей, клієнтами, моделями та датами"
            ],
            "be": [
                "Трохмерны ўлік токенаў: асобны падлік prompt-, completion- і reasoning-токенаў",
                "Waterfall-трасіроўка: пакрокавая візуалізацыя кожнай спробы, таймаўта і пераключэння на fallback",
                "Фінансавы ўлік: разлік ацэначнага кошту ў USD на аснове тарыфаў правайдэраў",
                "Экспарт аўдыту: фільтрацыя і выгрузка логаў па статусах адказаў, кліентах, мадэлях і датах"
            ],
            "zh": [
                "三维 Token 精准记账：提示词 (Prompt)、补全词 (Completion) 与思考链 (Reasoning) 分离核算",
                "瀑布流链路追踪 (Waterfall)：毫秒级呈现每一次重试跳点、错误状态码及备选路由切换路径",
                "实时成本估算：基于模型最新官方定价矩阵，秒级折算美元财务消耗与账单分布",
                "合规审计日志导出：支持按 HTTP 状态码、客户端 Key、模型名称及起止时间筛选并下载"
            ],
            "es": [
                "Contabilidad de tokens triple: seguimiento independiente de tokens de prompt, completado y razonamiento",
                "Inspector Waterfall: desglose visual paso a paso de cada intento de conexión, tiempo de espera y reintento",
                "Estimación de costos: cálculo en tiempo real en dólares según las tarifas oficiales de cada proveedor",
                "Registro de auditoría exportable: filtre y descargue registros por código, clave de cliente o fecha"
            ],
            "fr": [
                "Comptabilisation triple des tokens : suivi indépendant des tokens de prompt, complétion et raisonnement",
                "Inspecteur Waterfall : décomposition visuelle étape par étape de chaque saut, délai et tentative",
                "Calcul des coûts : estimation financière en USD en temps réel selon les barèmes des fournisseurs",
                "Journaux d'audit exportables : filtrez et téléchargez les journaux par code d'état, clé ou modèle"
            ],
            "de": [
                "Dreifache Token-Abrechnung: Separate Erfassung von Prompt-, Completion- und Reasoning-Tokens",
                "Waterfall-Failover-Inspektor: Schrittweise visuelle Analyse jedes Hops, Timeouts und Wiederholungsversuchs",
                "Kostenschätzung: Echtzeit-Berechnung in USD basierend auf aktuellen Provider-Preisen",
                "Exportierbares Audit-Protokoll: Filtern und Herunterladen von Logs nach Statuscode, Client-Key oder Datum"
            ],
            "ja": [
                "3方向トークン計測：プロンプト、完了、および思考プロセス（Reasoning）の各トークンを完全独立集計",
                "ウォーターフォールトレース：フォールバック発生時の試行履歴、エラー原因、所要時間を可視化",
                "リアルタイム料金試算：プロバイダー公式価格に基づきリクエスト単位でUSDコストを自動計算",
                "監査ログエクスポート：ステータスコード、クライアントキー、モデル名、期間で絞り込み・CSV出力"
            ],
            "pt": [
                "Contabilidade tripla de tokens: rastreamento independente de prompt, completion e raciocínio",
                "Inspetor Waterfall: detalhamento visual passo a passo de cada salto, timeout e tentativa de fallback",
                "Medidor de gastos: estimativa de custo em USD em tempo real com base nos preços dos provedores",
                "Logs de auditoria exportáveis: filtre e baixe registros por código de status, cliente ou data"
            ],
            "ar": [
                "محاسبة ثلاثية للرموز: تتبع مستقل لرموز الإدخال (Prompt) والإكمال (Completion) والتفكير (Reasoning)",
                "مفتش المسار الشلالي (Waterfall): تفصيل مرئي خطوة بخطوة لكل محاولة فاشلة وزمن انتظار وإعادة توجيه",
                "حاسبة التكاليف المباشرة: تقدير التكلفة بالدولار الأمريكي وفق تسعيرة المزودين المعتمدة لكل رمز",
                "تصدير سجلات التدقيق: تصفية وتنزيل السجلات حسب رمز الحالة أو مفتاح العميل أو النموذج أو التاريخ"
            ],
            "hi": [
                "तीन-स्तरीय टोकन लेखांकन: प्रॉम्प्ट, पूर्णता और तर्क टोकन स्वतंत्र रूप से ट्रैक किए गए",
                "वॉटरफॉल फेलओवर इंस्पेक्टर: प्रत्येक हॉप, टाइमआउट और पुनः प्रयास का दृश्य विवरण",
                "लागत मीटर: प्रदाता मूल्य निर्धारण के आधार पर रीयल-टाइम अमरीकी डालर लागत अनुमान",
                "निर्यात योग्य ऑडिट ट्रेल: स्थिति कोड, क्लाइंट कुंजी या मॉडल द्वारा लॉग फ़िल्टर करें"
            ],
            "bn": [
                "তিন ধরণের টোকেন অ্যাকাউন্টিং: প্রম্পট, কমপ্লিশন এবং রিজনিং টোকেন স্বাধীনভাবে ট্র্যাক করা হয়",
                "ওয়াটারফল ফেইলওভার ইন্সপেক্টর: প্রতিটি হপ, টাইমআউট এবং রিট্রাই চেষ্টার ধাপে ধাপে ভিজ্যুয়ালাইজেশন",
                "রিয়েল-টাইম ব্যয় গণনা: সরবরাহকারীদের মূল্যের ভিত্তিতে মার্কিন ডলারে আনুমানিক ব্যয়ের হিসাব",
                "অডিট ট্রেইল এক্সপোর্ট: স্ট্যাটাস কোড, চাবি বা মডেলের ভিত্তিতে লগ ফিল্টার এবং ডাউনলোড করুন"
            ]
        },
        "subsections": [
            {
                "titles": {
                    "en": "Log Entry Schema", "ru": "Схема записи лога", "uk": "Схема запису лога", "be": "Схема запісу лога",
                    "zh": "请求日志字段规范", "es": "Esquema del registro de logs", "fr": "Schéma des entrées du journal", "de": "Log-Eintrags-Schema",
                    "ja": "リクエストログのデータ構造", "pt": "Esquema da Entrada de Log", "ar": "مخطط حقول سجل الطلبات", "hi": "लॉग प्रविष्टि स्कीमा", "bn": "লগ এন্ট্রি স্কিমা"
                },
                "table": {
                    "headers": ["Field", "Type", "Description"],
                    "rows": [
                        ["id", "string (UUID)", "Unique identifier for the inference request transaction"],
                        ["timestamp", "ISO 8601", "UTC start time when client request was received"],
                        ["client_key_id", "string", "ID of the authorizing client API key (or 'master' / 'anon')"],
                        ["model_requested", "string", "Raw model parameter received in the client payload"],
                        ["model_resolved", "string", "Canonical model slug and provider that fulfilled the request"],
                        ["status_code", "integer", "Final HTTP response status returned to client (e.g. 200, 429, 502)"],
                        ["latency_ms", "float", "Total end-to-end response duration in milliseconds"],
                        ["prompt_tokens", "integer", "Token count of input messages"],
                        ["completion_tokens", "integer", "Token count of generated response (including reasoning)"],
                        ["cost_usd", "float", "Calculated monetary cost based on upstream token tariffs"]
                    ]
                }
            }
        ]
    },
    {
        "id": "circuit-breaker",
        "group": "system",
        "badge": "Resilience Engine",
        "titles": {
            "en": "Circuit Breaker & Fault Isolation",
            "ru": "Circuit Breaker и изоляция сбоев",
            "uk": "Circuit Breaker та ізоляція збоїв",
            "be": "Circuit Breaker і ізаляцыя збояў",
            "zh": "断路器自愈与故障隔离机制",
            "es": "Disyuntor de circuito y aislamiento de fallos",
            "fr": "Disjoncteur et isolation des pannes",
            "de": "Circuit Breaker & Fehlerisolation",
            "ja": "サーキットブレーカーと障害自動隔離",
            "pt": "Circuit Breaker e Isolamento de Falhas",
            "ar": "قاطع الدائرة الكهربائية وعزل الأعطال",
            "hi": "सर्किट ब्रेकर और विफलता अलगाव",
            "bn": "সার্কিট ব্রেকার এবং ত্রুটি বিচ্ছিন্নকরণ"
        },
        "descriptions": {
            "en": "Finite-state machine that stops traffic to failing or overloaded upstream providers, protecting client applications and restoring service seamlessly.",
            "ru": "Автомат состояний, изолирующий сбоящих или перегруженных провайдеров, защищая клиентские приложения от каскадных таймаутов.",
            "uk": "Автомат станів, що ізолює нестабільних або перевантажених провайдерів, захищаючи клієнтські застосунки від каскадних таймаутів.",
            "be": "Аўтамат станаў, які ізалюе нестабільных або перагружаных правайдэраў, абараняючы кліенцкія праграмы ад каскадных таймаўтаў.",
            "zh": "基于有限状态机 (FSM) 的自动容灾熔断引擎，主动切断向异常或宕机上游的无效请求，杜绝级联超时并平滑自愈。",
            "es": "Máquina de estados finitos que detiene el tráfico a proveedores en fallo o sobrecargados, protegiendo a los clientes de tiempos de espera en cascada.",
            "fr": "Machine à états finis qui bloque le trafic vers les fournisseurs défaillants ou surchargés, évitant les expirations en cascade.",
            "de": "Finite-State-Machine, die Anfragen an fehlerhafte oder überlastete Provider stoppt und Clients vor Kaskaden-Timeouts schützt.",
            "ja": "ダウンまたは過負荷の上流プロバイダーへの通信を自動遮断する有限ステートマシン。連鎖タイムアウトを防ぎ、自動プローブで復旧。",
            "pt": "Máquina de estados finitos que bloqueia tráfego para provedores com falhas, protegendo clientes contra timeouts em cascata.",
            "ar": "آلية آلية ذات حالات محددة لعزل المزودين المتعطلين أو المرهقين، وحماية تطبيقات العملاء من التوقف التراكمي وتسهيل التعافي.",
            "hi": "परिमित-स्थिति मशीन जो विफल या ओवरलोड प्रदाताओं को ट्रैफ़िक रोकती है, जिससे कैस्केडिंग टाइमआउट को रोका जा सके।",
            "bn": "নির্দিষ্ট স্টেট মেশিন যা ব্যর্থ বা অতিরিক্ত লোড হওয়া সরবরাহকারীদের ট্র্যাফিক বিচ্ছিন্ন করে গ্রাহক অ্যাপ্লিকেশনগুলিকে সুরক্ষিত রাখে।"
        },
        "highlights": {
            "en": [
                "3 Operational States: CLOSED (healthy, traffic flows), OPEN (broken, traffic diverted), HALF-OPEN (testing recovery)",
                "Error Trip Condition: Triggers automatically after 5 consecutive 5xx errors or network timeouts",
                "Cooling Down Period: Holds traffic away from broken endpoints for 30 seconds before sending a single probe",
                "Transparent Client Experience: Next candidate in Priority Fallback takes over immediately with zero client error"
            ],
            "ru": [
                "3 рабочих состояния: CLOSED (норма, трафик идет), OPEN (изолирован, перенаправление), HALF-OPEN (проверка)",
                "Порог срабатывания: автоматическое размыкание цепи после 5 подряд ошибок 5xx или таймаутов",
                "Период охлаждения: 30 секунд удержания перед отправкой пробного запроса для проверки доступности",
                "Незаметно для клиентов: следующий кандидат в профиле Fallback мгновенно обрабатывает запрос без ошибок"
            ],
            "uk": [
                "3 робочих стани: CLOSED (норма, трафік іде), OPEN (ізольований, перенаправлення), HALF-OPEN (перевірка)",
                "Поріг спрацьовування: автоматичне розмикання ланцюга після 5 поспіль помилок 5xx або таймаутів",
                "Період охолодження: 30 секунд утримання перед відправкою пробного запиту для перевірки доступності",
                "Непомітно для клієнтів: наступний кандидат у профілі Fallback миттєво обробляє запит без помилок"
            ],
            "be": [
                "3 працоўныя станы: CLOSED (норма, трафік ідзе), OPEN (ізаляваны, перанакіраванне), HALF-OPEN (праверка)",
                "Парог спрацоўвання: аўтаматычнае размыканне пасля 5 запар памылак 5xx або таймаўтаў",
                "Перыяд астуджэння: 30 секунд утрымання перад адпраўкай спробнага запыту для праверкі даступнасці",
                "Незаўважна для кліентаў: наступны кандыдат у профілі Fallback імгненна апрацоўвае запыт без памылак"
            ],
            "zh": [
                "三态状态机：CLOSED（健康，全量放行）、OPEN（熔断，流量旁路切走）、HALF-OPEN（半开，发送探针探测自愈）",
                "熔断触发条件：连续检测到 5 次 5xx 服务端错误或网络超时即自动跳闸",
                "冷却等待周期：熔断后静默 30 秒，随后仅允许单笔微量流量进行健康探活",
                "对客户端完全透明：Fallback 链路中的备用模型立即接管，客户端无感知、零报错"
            ],
            "es": [
                "3 estados operativos: CLOSED (saludable), OPEN (aislado, tráfico desviado), HALF-OPEN (probando recuperación)",
                "Condición de activación: se activa automáticamente tras 5 errores 5xx consecutivos o tiempos de espera",
                "Período de enfriamiento: desvía el tráfico durante 30 segundos antes de enviar una prueba de sondeo",
                "Transparente para el cliente: el siguiente candidato en Fallback asume la solicitud sin errores"
            ],
            "fr": [
                "3 états opérationnels : CLOSED (sain), OPEN (isolé, trafic dévié), HALF-OPEN (test de reprise)",
                "Déclenchement automatique : bascule après 5 erreurs 5xx consécutives ou délais d'attente réseau",
                "Période de refroidissement : bloque le trafic pendant 30 secondes avant d'envoyer une sonde de test",
                "Transparence totale pour le client : le modèle suivant dans la chaîne de repli prend le relais sans erreur"
            ],
            "de": [
                "3 Betriebszustände: CLOSED (gesund), OPEN (isoliert, Traffic umgeleitet), HALF-OPEN (Erholungstest)",
                "Auslösebedingung: Aktivierung nach 5 aufeinanderfolgenden 5xx-Fehlern oder Timeouts",
                "Abkühlphase: Leitet Anfragen für 30 Sekunden um, bevor eine einzelne Probe-Anfrage gesendet wird",
                "Transparent für Clients: Nächster Kandidat in der Fallback-Kette übernimmt sofort ohne Client-Fehler"
            ],
            "ja": [
                "3つの運用状態：CLOSED（正常）、OPEN（遮断・代替経路へ迂回）、HALF-OPEN（テストプローブ送信中）",
                "トリガー条件：5回連続で5xxエラーまたはタイムアウトが発生した場合に自動跳開",
                "クールダウン期間：障害発生から30秒間遮断を維持し、その後少数の通信で復旧を確認",
                "クライアント完全透過：優先度フォールバックの次候補が即時リクエストを代行しエラーを防止"
            ],
            "pt": [
                "3 estados operacionais: CLOSED (saudável), OPEN (isolado, tráfego desviado), HALF-OPEN (testando recuperação)",
                "Condição de disparo: ativa-se após 5 erros 5xx consecutivos ou tempos limite de rede",
                "Período de resfriamento: mantém o tráfego afastado por 30 segundos antes de enviar um probe de teste",
                "Transparente para o cliente: o próximo candidato no Fallback assume sem erros visíveis"
            ],
            "ar": [
                "3 حالات تشغيلية: CLOSED (سليم وطبيعي)، OPEN (معطول ومحول)، HALF-OPEN (اختبار التعافي)",
                "شرط الفصل: ينفصل القاطع تلقائياً بعد 5 أخطاء متتالية من نوع 5xx أو انتهاء زمن الانتظار",
                "فترة التبريد: تحويل الحركة لمدة 30 ثانية قبل إرسال طلب تجريبي واحد للتحقق من العودة",
                "تجربة عميل سلسة: يتولى النموذج التالي في مسار Fallback تنفيذ الطلب دون أي خطأ ظاهر للعميل"
            ],
            "hi": [
                "3 परिचालन अवस्थाएँ: CLOSED (स्वस्थ), OPEN (विफल, ट्रैफ़िक डायवर्ट), HALF-OPEN (पुनर्प्राप्ति परीक्षण)",
                "ट्रिप शर्त: लगातार 5 बार 5xx त्रुटियों या नेटवर्क टाइमआउट के बाद स्वचालित रूप से ट्रिप होता है",
                "कूलिंग डाउन अवधि: एकल परीक्षण अनुरोध भेजने से पहले 30 सेकंड के लिए ट्रैफ़िक को अलग रखता है",
                "क्लाइंट के लिए पारदर्शी: प्रायोरिटी फॉलबैक में अगला उम्मीदवार बिना किसी रुकावट के कार्यभार संभालता है"
            ],
            "bn": [
                "৩টি অপারেশনাল অবস্থা: CLOSED (সুস্থ), OPEN (বিচ্ছিন্ন ও ডাইভার্ট করা), HALF-OPEN (পুনরুদ্ধার পরীক্ষা)",
                "ট্রিপ শর্ত: টানা ৫ বার 5xx ত্রুটি বা নেটওয়ার্ক টাইমআউটের পর সার্কিট স্বয়ংক্রিয়ভাবে বিচ্ছিন্ন হয়",
                "কুল ডাউন সময়কাল: একটি প্রোব রিকোয়েস্ট পাঠানোর আগে ৩০ সেকেন্ডের জন্য ট্র্যাফিক দূরে রাখে",
                "গ্রাহকদের জন্য নির্বিঘ্ন: প্রায়োরিটি ফলব্যাকের পরবর্তী প্রার্থী তাত্ক্ষণিকভাবে দায়িত্ব গ্রহণ করে"
            ]
        },
        "subsections": [
            {
                "titles": {
                    "en": "FSM State Lifecycle", "ru": "Жизненный цикл состояний автомата", "uk": "Життєвий цикл станів автомата", "be": "Жыццёвы цыкл станаў аўтамата",
                    "zh": "状态机跃迁逻辑", "es": "Ciclo de vida de estados FSM", "fr": "Cycle de vie des états FSM", "de": "FSM-Zustandslebenszyklus",
                    "ja": "状態遷移ライフサイクル", "pt": "Ciclo de Vida do FSM", "ar": "دورة حياة حالات الآلة", "hi": "FSM स्थिति जीवनचक्र", "bn": "এফএসএম স্টেট লাইফসাইকেল"
                },
                "table": {
                    "headers": ["Transition", "Condition", "Action Taken"],
                    "rows": [
                        ["CLOSED -> OPEN", "5 consecutive failures (5xx / Timeout)", "Trip circuit breaker; mark credential unavailable; start 30s timer"],
                        ["OPEN -> HALF-OPEN", "Cooldown timer (30s) expires", "Allow 1 probe request through to verify upstream availability"],
                        ["HALF-OPEN -> CLOSED", "Probe succeeds with HTTP 200", "Reset failure count to 0; restore credential to active rotation pool"],
                        ["HALF-OPEN -> OPEN", "Probe fails or times out", "Restart 30s cooldown timer; keep credential isolated"]
                    ]
                }
            }
        ]
    },
    {
        "id": "api-reference",
        "group": "system",
        "badge": "REST Reference",
        "titles": {
            "en": "Complete API Endpoint Reference",
            "ru": "Полный справочник REST API",
            "uk": "Повний довідник REST API",
            "be": "Поўны даведнік REST API",
            "zh": "完整 REST API 接口清单",
            "es": "Referencia completa de endpoints API",
            "fr": "Référence complète des points de terminaison",
            "de": "Vollständige API-Endpunkt-Referenz",
            "ja": "完全なREST APIエンドポイント一覧",
            "pt": "Referência Completa de Endpoints da API",
            "ar": "المرجع الكامل لواجهات برمجة التطبيقات (API)",
            "hi": "पूर्ण एपीआई एंडपॉइंट संदर्भ",
            "bn": "সম্পূর্ণ এপিআই এন্ডপয়েন্ট রেফারেন্স"
        },
        "descriptions": {
            "en": "Comprehensive index of all public inference and administrative REST endpoints provided by the MyAIrouter server.",
            "ru": "Полный каталог всех публичных эндпоинтов инференса и административных интерфейсов управления шлюзом MyAIrouter.",
            "uk": "Повний каталог усіх публічних ендпоінтів інференсу та адміністративних інтерфейсів керування шлюзом MyAIrouter.",
            "be": "Поўны каталог усіх публічных эндпоінтаў інферэнсу і адміністрацыйных інтэрфейсаў кіравання шлюзам MyAIrouter.",
            "zh": "汇总 MyAIrouter 提供的全部标准推理端点与管理员 REST 控制面接口规范。",
            "es": "Índice completo de todos los endpoints REST públicos de inferencia y administración provistos por el servidor MyAIrouter.",
            "fr": "Index exhaustif de tous les points de terminaison REST publics d'inférence et d'administration de MyAIrouter.",
            "de": "Vollständiger Index aller öffentlichen Inferenz- und Administrations-REST-Endpunkte des MyAIrouter-Servers.",
            "ja": "MyAIrouter が提供するすべての公開推論エンドポイントおよび管理者向け管理RESTエンドポイントの完全な一覧仕様。",
            "pt": "Índice abrangente de todos os endpoints REST públicos de inferência e administração do MyAIrouter.",
            "ar": "فهرس شامل لجميع نقاط النهاية العامة للاستدلال وإدارة النظام التي يوفرها خادم MyAIrouter.",
            "hi": "MyAIrouter सर्वर द्वारा प्रदान किए गए सभी सार्वजनिक अनुमान और प्रशासनिक REST एंडपॉइंट्स की विस्तृत सूची।",
            "bn": "MyAIrouter সার্ভার দ্বারা প্রদত্ত সমস্ত পাবলিক ইনফারেন্স এবং প্রশাসনিক REST এন্ডপয়েন্টের সম্পূর্ণ বিবরণ।"
        },
        "highlights": {
            "en": [
                "OpenAI Ingest: /v1/chat/completions, /v1/models (full drop-in client compatibility)",
                "Ollama Protocol: /api/tags, /api/show, /api/version, /api/chat",
                "Core Management: /api/v1/credentials, /api/v1/models, /api/v1/routes, /api/v1/fusion",
                "System & Health: /health, /api/v1/system/backup, /api/v1/system/restore, /api/v1/system/stats"
            ],
            "ru": [
                "Совместимость с OpenAI: /v1/chat/completions, /v1/models (прямая замена в любых SDK)",
                "Протокол Ollama: /api/tags, /api/show, /api/version, /api/chat",
                "Управление конфигурацией: /api/v1/credentials, /api/v1/models, /api/v1/routes, /api/v1/fusion",
                "Система и мониторинг: /health, /api/v1/system/backup, /api/v1/system/restore, /api/v1/system/stats"
            ],
            "uk": [
                "Сумісність з OpenAI: /v1/chat/completions, /v1/models (пряма заміна у будь-яких SDK)",
                "Протокол Ollama: /api/tags, /api/show, /api/version, /api/chat",
                "Керування конфігурацією: /api/v1/credentials, /api/v1/models, /api/v1/routes, /api/v1/fusion",
                "Система та моніторинг: /health, /api/v1/system/backup, /api/v1/system/restore, /api/v1/system/stats"
            ],
            "be": [
                "Сумяшчальнасць з OpenAI: /v1/chat/completions, /v1/models (прамая замена ў любых SDK)",
                "Пратакол Ollama: /api/tags, /api/show, /api/version, /api/chat",
                "Кіраванне канфігурацыяй: /api/v1/credentials, /api/v1/models, /api/v1/routes, /api/v1/fusion",
                "Сістэма і маніторынг: /health, /api/v1/system/backup, /api/v1/system/restore, /api/v1/system/stats"
            ],
            "zh": [
                "OpenAI 标准推理接口：/v1/chat/completions, /v1/models（主流客户端无缝无感替换）",
                "Ollama 原生协议接口：/api/tags, /api/show, /api/version, /api/chat（兼容各类本地工具）",
                "核心配置控制面：/api/v1/credentials, /api/v1/models, /api/v1/routes, /api/v1/fusion",
                "系统运维与探针：/health, /api/v1/system/backup, /api/v1/system/restore, /api/v1/system/stats"
            ],
            "es": [
                "Entrada OpenAI: /v1/chat/completions, /v1/models (compatibilidad inmediata con cualquier cliente)",
                "Protocolo Ollama: /api/tags, /api/show, /api/version, /api/chat",
                "Gestión principal: /api/v1/credentials, /api/v1/models, /api/v1/routes, /api/v1/fusion",
                "Sistema y salud: /health, /api/v1/system/backup, /api/v1/system/restore, /api/v1/system/stats"
            ],
            "fr": [
                "Ingestion OpenAI : /v1/chat/completions, /v1/models (remplacement direct pour tout client)",
                "Protocole Ollama : /api/tags, /api/show, /api/version, /api/chat",
                "Gestion principale : /api/v1/credentials, /api/v1/models, /api/v1/routes, /api/v1/fusion",
                "Système et santé : /health, /api/v1/system/backup, /api/v1/system/restore, /api/v1/system/stats"
            ],
            "de": [
                "OpenAI-Eingang: /v1/chat/completions, /v1/models (vollständig kompatibel mit allen OpenAI-Clients)",
                "Ollama-Protokoll: /api/tags, /api/show, /api/version, /api/chat",
                "Kernverwaltung: /api/v1/credentials, /api/v1/models, /api/v1/routes, /api/v1/fusion",
                "System & Gesundheit: /health, /api/v1/system/backup, /api/v1/system/restore, /api/v1/system/stats"
            ],
            "ja": [
                "OpenAI互換：/v1/chat/completions、/v1/models（各社SDKをそのまま差し替え可能）",
                "Ollamaプロトコル：/api/tags、/api/show、/api/version、/api/chat",
                "構成管理：/api/v1/credentials、/api/v1/models、/api/v1/routes、/api/v1/fusion",
                "システム＆死活監視：/health、/api/v1/system/backup、/api/v1/system/restore、/api/v1/system/stats"
            ],
            "pt": [
                "Entrada OpenAI: /v1/chat/completions, /v1/models (compatibilidade direta com qualquer SDK)",
                "Protocolo Ollama: /api/tags, /api/show, /api/version, /api/chat",
                "Gerenciamento principal: /api/v1/credentials, /api/v1/models, /api/v1/routes, /api/v1/fusion",
                "Sistema e integridade: /health, /api/v1/system/backup, /api/v1/system/restore, /api/v1/system/stats"
            ],
            "ar": [
                "واجهة OpenAI المتوافقة: /v1/chat/completions و/v1/models (إحلال مباشر لجميع التطبيقات)",
                "بروتوكول Ollama: /api/tags و/api/show و/api/version و/api/chat",
                "الإدارة المركزية: /api/v1/credentials و/api/v1/models و/api/v1/routes و/api/v1/fusion",
                "النظام والسلامة: /health و/api/v1/system/backup و/api/v1/system/restore و/api/v1/system/stats"
            ],
            "hi": [
                "OpenAI इनपुट: /v1/chat/completions, /v1/models (पूर्ण क्लाइंट संगतता)",
                "Ollama प्रोटोकॉल: /api/tags, /api/show, /api/version, /api/chat",
                "कोर प्रबंधन: /api/v1/credentials, /api/v1/models, /api/v1/routes, /api/v1/fusion",
                "सिस्टम और स्वास्थ्य: /health, /api/v1/system/backup, /api/v1/system/restore"
            ],
            "bn": [
                "OpenAI ইনপুট: /v1/chat/completions, /v1/models (ড্রপ-ইন ক্লায়েন্ট সামঞ্জস্য)",
                "Ollama প্রোটোকল: /api/tags, /api/show, /api/version, /api/chat",
                "কোর ম্যানেজমেন্ট: /api/v1/credentials, /api/v1/models, /api/v1/routes, /api/v1/fusion",
                "সিস্টেম ও হেলথ: /health, /api/v1/system/backup, /api/v1/system/restore"
            ]
        },
        "subsections": [
            {
                "titles": {
                    "en": "Public & Admin Endpoints Table", "ru": "Таблица публичных и административных эндпоинтов", "uk": "Таблиця публічних та адміністративних ендпоінтів", "be": "Табліца публічных і адміністрацыйных эндпоінтаў",
                    "zh": "端点路由与鉴权要求清单", "es": "Tabla de endpoints públicos y administrativos", "fr": "Tableau des points de terminaison publics et admin", "de": "Tabelle öffentlicher und administrativer Endpunkte",
                    "ja": "公開および管理者向けエンドポイント仕様表", "pt": "Tabela de Endpoints Públicos e Administrativos", "ar": "جدول نقاط النهاية العامة والإدارية", "hi": "सार्वजनिक और व्यवस्थापक एंडपॉइंट्स तालिका", "bn": "পাবলিক এবং অ্যাডমিন এন্ডপয়েন্ট তালিকা"
                },
                "table": {
                    "headers": ["Method", "Path", "Auth Scheme", "Purpose"],
                    "rows": [
                        ["POST", "/v1/chat/completions", "Bearer sk-router-...", "OpenAI-compatible text & vision chat completion (streaming supported)"],
                        ["GET", "/v1/models", "Bearer sk-router-...", "List all active models, aliases, fallback routes, and fusion juries"],
                        ["GET", "/api/tags", "Optional / None", "Ollama protocol: enumerate locally installed and routed models"],
                        ["POST", "/api/show", "Optional / None", "Ollama protocol: inspect model architecture, parameters, and license"],
                        ["GET", "/api/version", "None", "Ollama protocol: returns Ollama compatibility version tag"],
                        ["GET", "/api/v1/credentials", "Admin Session / Token", "List encrypted upstream provider credentials with health metrics"],
                        ["POST", "/api/v1/routes", "Admin Session / Token", "Create or update Priority Fallback route policies"],
                        ["POST", "/api/v1/fusion", "Admin Session / Token", "Create or update Model Fusion jury configurations"],
                        ["GET", "/api/v1/system/stats", "Admin Session / Token", "Retrieve real-time token volume, latency distributions, and costs"],
                        ["POST", "/api/v1/system/backup", "Admin Session / Token", "Generate encrypted passphrase-protected JSON backup archive"]
                    ]
                }
            }
        ]
    },
    {
        "id": "errors",
        "group": "system",
        "badge": "Troubleshooting",
        "titles": {
            "en": "HTTP Error Codes & Troubleshooting",
            "ru": "Коды ошибок HTTP и диагностика",
            "uk": "Коди помилок HTTP та діагностика",
            "be": "Коды памылак HTTP і дыягностыка",
            "zh": "HTTP 状态码规范与排障指南",
            "es": "Códigos de error HTTP y solución de problemas",
            "fr": "Codes d'erreur HTTP et dépannage",
            "de": "HTTP-Fehlercodes & Fehlerbehebung",
            "ja": "HTTPエラーコードとトラブルシューティング",
            "pt": "Códigos de Erro HTTP e Resolução de Problemas",
            "ar": "رموز أخطاء HTTP واستكشاف الأعطال وإصلاحها",
            "hi": "HTTP त्रुटि कोड और समस्या निवारण",
            "bn": "HTTP ত্রুটি কোড এবং সমস্যা সমাধান"
        },
        "descriptions": {
            "en": "Detailed breakdown of HTTP status codes returned by the router, JSON error envelope specifications, and actionable troubleshooting steps.",
            "ru": "Подробный разбор кодов состояния HTTP, возвращаемых шлюзом, спецификация формата ошибок JSON и инструкции по их устранению.",
            "uk": "Детальний розбір кодів стану HTTP, що повертаються шлюзом, специфікація формату помилок JSON та інструкції з їх усунення.",
            "be": "Падрабязны разбор кодаў стану HTTP, якія вяртаюцца шлюзам, спецыфікацыя фармату памылак JSON і інструкцыі па іх выпраўленні.",
            "zh": "全面解析网关返回的标准 HTTP 状态码规范、OpenAI 兼容的错误响应体 JSON 结构及常见故障排查诊断指南。",
            "es": "Desglose detallado de los códigos de estado HTTP devueltos por el enrutador, especificaciones de error JSON y solución de problemas.",
            "fr": "Détail des codes d'état HTTP retournés par le routeur, spécifications des erreurs JSON et étapes de dépannage.",
            "de": "Detaillierte Aufschlüsselung der vom Router zurückgegebenen HTTP-Statuscodes, JSON-Fehlerformate und Fehlerbehebungsschritte.",
            "ja": "ルーターが返却するHTTPステータスコードの詳細一覧、OpenAI互換のJSONエラーレスポンス構造、および実践的なトラブルシューティング手順。",
            "pt": "Detalhamento dos códigos de status HTTP retornados pelo router, especificações do JSON de erro e passos para solução de problemas.",
            "ar": "تحليل شامل لرموز استجابة HTTP التي يرجعها النظام، ومواصفات كائن الخطأ بصيغة JSON، وخطوات عملية لحل المشكلات.",
            "hi": "राउटर द्वारा लौटाए गए HTTP स्थिति कोड, JSON त्रुटि प्रारूप विनिर्देशों और समस्या निवारण चरणों का विस्तृत विवरण।",
            "bn": "রাউটার দ্বারা ফেরত দেওয়া HTTP স্ট্যাটাস কোড, JSON ত্রুটি ফরম্যাট এবং সমস্যা সমাধানের স্পষ্ট নির্দেশিকা।"
        },
        "highlights": {
            "en": [
                "Standard OpenAI Error Schema: {\"error\": {\"message\": \"...\", \"type\": \"...\", \"code\": \"...\"}}",
                "Clear Distinction: Differentiates client misconfigurations (4xx) from upstream provider failures (502/504)",
                "Actionable Diagnostics: Specific error messages indicate whether failure was caused by quota, auth, or model resolution",
                "Rate Limit Backoff: 429 responses provide clear retry hints for RPM and TPM rate limit windows"
            ],
            "ru": [
                "Стандартная схема ошибок OpenAI: {\"error\": {\"message\": \"...\", \"type\": \"...\", \"code\": \"...\"}}",
                "Четкое разделение: разграничение ошибок клиента (4xx) и сбоев вышестоящих провайдеров (502/504)",
                "Информативные описания: сообщения указывают конкретную причину (неверный ключ, исчерпан лимит или модель не найдена)",
                "Обработка Rate Limit: ответы 429 содержат информацию о превышении лимитов RPM или TPM"
            ],
            "uk": [
                "Стандартна схема помилок OpenAI: {\"error\": {\"message\": \"...\", \"type\": \"...\", \"code\": \"...\"}}",
                "Чіткий поділ: розмежування помилок клієнта (4xx) та збоїв вищих провайдерів (502/504)",
                "Інформативні описи: повідомлення вказують конкретну причину (невірний ключ, вичерпаний ліміт або модель не знайдено)",
                "Обробка Rate Limit: відповіді 429 містять інформацію про перевищення лімітів RPM або TPM"
            ],
            "be": [
                "Стандартная схема памылак OpenAI: {\"error\": {\"message\": \"...\", \"type\": \"...\", \"code\": \"...\"}}",
                "Выразнае раздзяленне: размежаванне памылак кліента (4xx) і збояў правайдэраў (502/504)",
                "Інфарматыўныя апісанні: паведамленні паказваюць канкрэтную прычыну (няслушны ключ, вычарпаны ліміт або мадэль не знойдзена)",
                "Апрацоўка Rate Limit: адказы 429 змяшчаюць інфармацыю аб перавышэнні лімітаў RPM або TPM"
            ],
            "zh": [
                "标准 OpenAI 错误协议：输出格式严格遵循 {\"error\": {\"message\": \"...\", \"type\": \"...\", \"code\": \"...\"}}",
                "责任边界清晰：严格区分客户端调用错误（4xx）与上游大模型服务商异常（502/504）",
                "精准诊断指引：明确标明报错是由于凭据无效、额度耗尽、超时还是路由无可用候选节点",
                "速率超限友好回退：返回 HTTP 429 时附带精准的原因说明（RPM 或 TPM 阈值超出）"
            ],
            "es": [
                "Esquema estándar OpenAI: {\"error\": {\"message\": \"...\", \"type\": \"...\", \"code\": \"...\"}}",
                "Distinción clara: separa errores de configuración del cliente (4xx) de fallos del proveedor (502/504)",
                "Diagnósticos prácticos: mensajes específicos indican si el fallo fue por cuota, autenticación o modelo",
                "Control de límites: las respuestas 429 ofrecen pistas claras sobre ventanas de tiempo para RPM y TPM"
            ],
            "fr": [
                "Schéma d'erreur standard OpenAI : {\"error\": {\"message\": \"...\", \"type\": \"...\", \"code\": \"...\"}}",
                "Distinction claire : sépare les erreurs client (4xx) des défaillances de fournisseurs amont (502/504)",
                "Diagnostics exploitables : messages précis indiquant si la panne est due au quota, à l'auth ou au modèle",
                "Gestion des limites : les réponses 429 fournissent des indications claires de temporisation"
            ],
            "de": [
                "Standardisiertes OpenAI-Fehlerschema: {\"error\": {\"message\": \"...\", \"type\": \"...\", \"code\": \"...\"}}",
                "Klare Unterscheidung: Trennt Client-Fehler (4xx) sauber von Upstream-Provider-Ausfällen (502/504)",
                "Handlungsorientierte Diagnose: Präzise Meldungen zeigen, ob Quote, Authentifizierung oder Modell fehlten",
                "Ratenlimit-Hinweise: 429-Antworten liefern klare Informationen zur Wiederholung nach RPM/TPM-Überschreitung"
            ],
            "ja": [
                "標準OpenAIエラー構造：{\"error\": {\"message\": \"...\", \"type\": \"...\", \"code\": \"...\"}} に完全準拠",
                "明確な責任区分：クライアント側のパラメータ不備（4xx）と上流プロバイダー障害（502/504）を明確に分離",
                "実践的な診断メッセージ：認証エラー、クォータ枯渇、タイムアウト、候補ゼロなどの原因を具体的に明示",
                "レート制限バックオフ：429応答時にRPMおよびTPMの超過要因を明快に通知"
            ],
            "pt": [
                "Esquema de erro padrão OpenAI: {\"error\": {\"message\": \"...\", \"type\": \"...\", \"code\": \"...\"}}",
                "Distinção clara: diferencia erros do cliente (4xx) de falhas nos provedores upstream (502/504)",
                "Diagnósticos acionáveis: mensagens específicas indicando se a falha foi cota, autenticação ou modelo",
                "Controle de taxa: respostas 429 fornecem orientações claras de espera para limites RPM e TPM"
            ],
            "ar": [
                "مخطط خطأ قياسي متوافق مع OpenAI: {\"error\": {\"message\": \"...\", \"type\": \"...\", \"code\": \"...\"}}",
                "تمييز دقيق للمسؤولية: تفريق واضح بين أخطاء العميل (4xx) وأعطال مزودي الخدمة الخارجيين (502/504)",
                "تشخيصات واضحة وقابلة للتنفيذ: توضيح دقيق لسبب العطل سواء كان نفاد الرصيد أو خطأ بالمفتاح أو عدم توفر النموذج",
                "إرشادات تجاوز معدل الاستخدام: استجابات 429 توفر إرشادات واضحة حول فترات الانتظار لتجاوز حدود RPM وTPM"
            ],
            "hi": [
                "मानक OpenAI त्रुटि स्कीमा: {\"error\": {\"message\": \"...\", \"type\": \"...\", \"code\": \"...\"}}",
                "स्पष्ट अंतर: क्लाइंट त्रुटियों (4xx) को अपस्ट्रीम प्रदाता विफलताओं (502/504) से अलग करता है",
                "सटीक निदान: विशिष्ट त्रुटि संदेश बताते हैं कि विफलता कोटा, प्रमाणीकरण या मॉडल के कारण हुई",
                "दर सीमा प्रबंधन: 429 प्रतिक्रियाएं RPM और TPM के लिए पुनः प्रयास के स्पष्ट संकेत देती हैं"
            ],
            "bn": [
                "স্ট্যান্ডার্ড OpenAI ত্রুটি স্কিমা: {\"error\": {\"message\": \"...\", \"type\": \"...\", \"code\": \"...\"}}",
                "স্পষ্ট পার্থক্য: ক্লায়েন্ট কনফিগারেশন ত্রুটি (4xx) এবং আপস্ট্রিম প্রদানকারীর ব্যর্থতার (502/504) সুস্পষ্ট বিভাজন",
                "বাস্তবধর্মী সমাধান: বার্তাগুলি স্পষ্টভাবে নির্দেশ করে যে ব্যর্থতা কোটা, কী নাকি মডেল না পাওয়ার কারণে হয়েছে",
                "রেট লিমিট হ্যান্ডলিং: ৪২৯ প্রতিক্রিয়ায় আরপিএম এবং টিপিএম সীমা অতিক্রমের তথ্য স্পষ্ট জানানো হয়"
            ]
        },
        "subsections": [
            {
                "titles": {
                    "en": "HTTP Status Codes Catalog", "ru": "Каталог кодов состояния HTTP", "uk": "Каталог кодів стану HTTP", "be": "Каталог кодаў стану HTTP",
                    "zh": "常见 HTTP 状态码速查表", "es": "Catálogo de códigos de estado HTTP", "fr": "Catalogue des codes d'état HTTP", "de": "Katalog der HTTP-Statuscodes",
                    "ja": "HTTPステータスコード一覧", "pt": "Catálogo de Códigos de Status HTTP", "ar": "دليل رموز استجابة HTTP", "hi": "HTTP स्थिति कोड कैटलॉग", "bn": "HTTP স্ট্যাটাস কোড ক্যাটালগ"
                },
                "table": {
                    "headers": ["Status", "Error Name", "Likely Cause", "Resolution"],
                    "rows": [
                        ["400", "Bad Request", "Malformed JSON body or invalid parameter type", "Verify JSON syntax and data types against API specification"],
                        ["401", "Unauthorized", "Missing or invalid Bearer sk-router-... API key", "Generate a valid client API key in Admin UI and pass in Authorization header"],
                        ["403", "Forbidden", "Client key exists but requested model is not whitelisted", "Add the requested model to allowed_models in client key settings"],
                        ["404", "Not Found", "Requested model slug does not exist in router database", "Check /v1/models or create a model mapping / fallback route in router"],
                        ["422", "Unprocessable Entity", "Pydantic validation failed on payload fields", "Inspect error response details to locate offending field and type mismatch"],
                        ["429", "Rate Limit Exceeded", "Client exceeded configured RPM or TPM quota, or upstream 429", "Reduce request concurrency or increase RPM/TPM thresholds in client key settings"],
                        ["502", "Bad Gateway", "All upstream provider candidates failed or returned errors", "Verify upstream API keys, network connectivity, and proxy settings in router"],
                        ["504", "Gateway Timeout", "Upstream provider took longer than timeout threshold", "Increase model timeout limit or configure fallback route to faster provider (Groq/Cerebras)"]
                    ]
                }
            }
        ]
    },
    {
        "id": "env-config",
        "group": "system",
        "badge": "Deployment",
        "titles": {
            "en": "Environment Variables & Deployment",
            "ru": "Переменные окружения и деплой",
            "uk": "Змінні оточення та деплой",
            "be": "Пераменныя асяроддзя і дэплой",
            "zh": "环境变量配置与生产部署",
            "es": "Variables de entorno y despliegue",
            "fr": "Variables d'environnement et déploiement",
            "de": "Umgebungsvariablen & Deployment",
            "ja": "環境変数と本番デプロイ",
            "pt": "Variáveis de Ambiente e Implantação",
            "ar": "متغيرات البيئة والنشر الإنتاجي",
            "hi": "पर्यावरण चर और परिनियोजन",
            "bn": "এনভায়রনমেন্ট ভেরিয়েবল এবং ডিপ্লয়মেন্ট"
        },
        "descriptions": {
            "en": "Configuration options for hosting MyAIrouter in production with Docker, PostgreSQL, systemd, and custom security settings.",
            "ru": "Полный перечень параметров конфигурации для промышленного развертывания MyAIrouter с Docker, PostgreSQL и systemd.",
            "uk": "Повний перелік параметрів конфігурації для промислового розгортання MyAIrouter з Docker, PostgreSQL та systemd.",
            "be": "Поўны пералік параметраў канфігурацыі для прамысловага разгортвання MyAIrouter з Docker, PostgreSQL і systemd.",
            "zh": "MyAIrouter 生产级部署核心环境变量参考，支持 Docker Compose、PostgreSQL 数据库及生产安全加固。",
            "es": "Opciones de configuración para alojar MyAIrouter en producción con Docker, PostgreSQL, systemd y seguridad avanzada.",
            "fr": "Options de configuration pour héberger MyAIrouter en production avec Docker, PostgreSQL, systemd et sécurité renforcée.",
            "de": "Konfigurationsoptionen für den produktiven Betrieb von MyAIrouter mit Docker, PostgreSQL, systemd und Sicherheitsrichtlinien.",
            "ja": "Docker、PostgreSQL、systemd、および高度なセキュリティ設定を用いて MyAIrouter を本番環境で運用するための環境変数リファレンス。",
            "pt": "Opções de configuração para hospedar o MyAIrouter em produção com Docker, PostgreSQL, systemd e configurações de segurança.",
            "ar": "خيارات التهيئة لاستضافة MyAIrouter في بيئة الإنتاج باستخدام Docker وPostgreSQL وإعدادات الأمان المتقدمة.",
            "hi": "Docker, PostgreSQL, systemd और कस्टम सुरक्षा सेटिंग्स के साथ MyAIrouter को उत्पादन में होस्ट करने के लिए कॉन्फ़िगरेशन विकल्प।",
            "bn": "ডকার, পোস্টগ্রেসকিউএল, সিস্টেমডি এবং সুরক্ষা সেটিংস সহ উৎপাদনে MyAIrouter হোস্ট করার জন্য কনফিগারেশন বিকল্প।"
        },
        "highlights": {
            "en": [
                "ROUTER_MASTER_KEY: Critical 32-byte base64 key used to encrypt all provider credentials at rest",
                "DATABASE_URL: Switch from default SQLite (sqlite+aiosqlite:///router.db) to high-concurrency PostgreSQL",
                "CORS_ORIGINS: Comma-separated list of allowed origins for secure frontend web client access",
                "OLLAMA_BASE_URL: Default discovery URL for local or remote Ollama daemon (defaults to http://localhost:11434)"
            ],
            "ru": [
                "ROUTER_MASTER_KEY: критически важный 32-байтный base64 ключ для шифрования всех секретов в БД",
                "DATABASE_URL: переключение со стандартной SQLite на высоконагруженную PostgreSQL",
                "CORS_ORIGINS: разделенный запятыми список разрешенных доменов для безопасного доступа веб-интерфейса",
                "OLLAMA_BASE_URL: базовый адрес демона Ollama для автоматического обнаружения моделей (по умолч. http://localhost:11434)"
            ],
            "uk": [
                "ROUTER_MASTER_KEY: критично важливий 32-байтний base64 ключ для шифрування всіх секретів у БД",
                "DATABASE_URL: перемикання зі стандартної SQLite на високонавантажену PostgreSQL",
                "CORS_ORIGINS: розділений комами список дозволених доменів для безпечного доступу веб-інтерфейсу",
                "OLLAMA_BASE_URL: базова адреса демона Ollama для автоматичного виявлення моделей (за замовч. http://localhost:11434)"
            ],
            "be": [
                "ROUTER_MASTER_KEY: крытычна важны 32-байтны base64 ключ для шыфравання ўсіх сакрэтаў у БД",
                "DATABASE_URL: пераключэнне са стандартнай SQLite на высоканагружаную PostgreSQL",
                "CORS_ORIGINS: падзелены коскамі спіс дазволеных даменаў для бяспечнага доступу вэб-інтэрфейсу",
                "OLLAMA_BASE_URL: базавы адрас дэмана Ollama для аўтаматычнага выяўлення мадэляў (па змаўч. http://localhost:11434)"
            ],
            "zh": [
                "ROUTER_MASTER_KEY：用于底层加密所有上游 API 凭证的 32 字节 Base64 主密钥，生产环境严禁泄露",
                "DATABASE_URL：数据库连接串，支持从默认 SQLite 瞬间无缝切换至高并发生产级 PostgreSQL",
                "CORS_ORIGINS：跨域允许来源白名单，以逗号分隔，保障生产 Web UI 的安全隔离调用",
                "OLLAMA_BASE_URL：本地或局域网 Ollama 守护进程探测基地址（默认 http://localhost:11434）"
            ],
            "es": [
                "ROUTER_MASTER_KEY: Clave base64 de 32 bytes crítica para cifrar credenciales en reposo",
                "DATABASE_URL: Cambie de SQLite por defecto a PostgreSQL de alta concurrencia",
                "CORS_ORIGINS: Lista de orígenes permitidos separados por comas para acceso web seguro",
                "OLLAMA_BASE_URL: Dirección por defecto para el servicio de Ollama (http://localhost:11434)"
            ],
            "fr": [
                "ROUTER_MASTER_KEY : Clé base64 critique de 32 octets pour chiffrer les identifiants au repos",
                "DATABASE_URL : Basculez du SQLite par défaut vers un PostgreSQL haute performance",
                "CORS_ORIGINS : Liste d'origines autorisées séparées par des virgules pour sécuriser le web",
                "OLLAMA_BASE_URL : URL de détection pour le démon Ollama (par défaut http://localhost:11434)"
            ],
            "de": [
                "ROUTER_MASTER_KEY: Kritischer 32-Byte-Base64-Schlüssel zur Verschlüsselung aller Anmeldedaten",
                "DATABASE_URL: Wechsel von Standard-SQLite zu hochverfügbarem PostgreSQL",
                "CORS_ORIGINS: Kommagetrennte Liste erlaubter Origins für sicheren Web-Frontend-Zugriff",
                "OLLAMA_BASE_URL: Standard-Erkennungs-URL für den Ollama-Dienst (Standard: http://localhost:11434)"
            ],
            "ja": [
                "ROUTER_MASTER_KEY：全上流APIキーを保管時に暗号化するための重要な32バイトBase64マスターキー",
                "DATABASE_URL：デフォルトのSQLiteから高並行処理対応のPostgreSQLへ簡単に切り替え可能",
                "CORS_ORIGINS：Webフロントエンドから安全に通信するためのオリジン許可リスト（カンマ区切り）",
                "OLLAMA_BASE_URL：Ollamaデーモンの検出先URL（デフォルト: http://localhost:11434）"
            ],
            "pt": [
                "ROUTER_MASTER_KEY: Chave base64 de 32 bytes crítica para criptografar credenciais em repouso",
                "DATABASE_URL: Mude do SQLite padrão para PostgreSQL para alta concorrência",
                "CORS_ORIGINS: Lista de origens permitidas separadas por vírgula para acesso seguro à web",
                "OLLAMA_BASE_URL: URL padrão para o serviço Ollama (padrão: http://localhost:11434)"
            ],
            "ar": [
                "ROUTER_MASTER_KEY: مفتاح رئيسي مشفر بحجم 32 بايت بصيغة base64 لتشفير كافة اعتمادات المزودين في قاعدة البيانات",
                "DATABASE_URL: التبديل من SQLite الافتراضية إلى خادم PostgreSQL المخصص للأحمال العالية",
                "CORS_ORIGINS: قائمة النطاقات المسموح بها للتواصل الآمن مع واجهة الويب الأمامية",
                "OLLAMA_BASE_URL: عنوان اكتشاف خدمة Ollama المحلية أو البعيدة (الافتراضي: http://localhost:11434)"
            ],
            "hi": [
                "ROUTER_MASTER_KEY: डेटाबेस में सभी क्रेडेंशियल को एन्क्रिप्ट करने के लिए महत्वपूर्ण 32-बाइट कुंजी",
                "DATABASE_URL: डिफ़ॉल्ट SQLite से उच्च-समवर्ती PostgreSQL पर स्विच करें",
                "CORS_ORIGINS: सुरक्षित वेब क्लाइंट एक्सेस के लिए अनुमत ऑरिजिन की सूची",
                "OLLAMA_BASE_URL: स्थानीय या दूरस्थ ओलामा डेमॉन के लिए डिफ़ॉल्ट खोज यूआरएल"
            ],
            "bn": [
                "ROUTER_MASTER_KEY: ডাটাবেসে সমস্ত শংসাপত্র এনক্রিপ্ট করার জন্য গুরুত্বপূর্ণ ৩২-বাইট মাস্টার চাবি",
                "DATABASE_URL: ডিফল্ট SQLite থেকে উচ্চ-কনকারেন্সি PostgreSQL এ স্থানান্তর করুন",
                "CORS_ORIGINS: সুরক্ষিত ওয়েব অ্যাক্সেসের জন্য অনুমোদিত ডোমেনের কমা-বিভক্ত তালিকা",
                "OLLAMA_BASE_URL: লোকাল ওলামা ডেমন সনাক্তকরণের বেস URL (ডিফল্ট: http://localhost:11434)"
            ]
        },
        "subsections": [
            {
                "titles": {
                    "en": "Key Environment Variables", "ru": "Основные переменные окружения", "uk": "Основні змінні оточення", "be": "Асноўныя пераменныя асяроддзя",
                    "zh": "核心环境变量参考表", "es": "Variables de entorno principales", "fr": "Variables d'environnement clés", "de": "Wichtige Umgebungsvariablen",
                    "ja": "主要な環境変数一覧", "pt": "Principais Variáveis de Ambiente", "ar": "متغيرات البيئة الأساسية", "hi": "मुख्य पर्यावरण चर", "bn": "প্রধান পরিবেশ ভেরিয়েবল"
                },
                "table": {
                    "headers": ["Variable", "Default", "Required", "Description"],
                    "rows": [
                        ["ROUTER_MASTER_KEY", "(generated on first run)", "Recommended", "32-byte Base64 key for Fernet symmetric encryption of all API secrets"],
                        ["DATABASE_URL", "sqlite+aiosqlite:///./router.db", "No", "Async SQLAlchemy connection string (e.g. postgresql+asyncpg://user:pass@host/db)"],
                        ["ROUTER_HOST", "0.0.0.0", "No", "Network interface IP to bind the HTTP server listener"],
                        ["ROUTER_PORT", "8000", "No", "TCP port on which the router receives inference and admin traffic"],
                        ["LOG_LEVEL", "INFO", "No", "Logging verbosity: DEBUG, INFO, WARNING, ERROR, CRITICAL"],
                        ["DEFAULT_TIMEOUT", "60.0", "No", "Default timeout in seconds for upstream provider requests before fallback"],
                        ["CORS_ORIGINS", "*", "No", "Allowed origins for Cross-Origin Resource Sharing headers"],
                        ["OLLAMA_BASE_URL", "http://localhost:11434", "No", "Target host URL for discovering and routing to local Ollama models"]
                    ]
                }
            },
            {
                "titles": {
                    "en": "Production Docker Compose Example", "ru": "Пример Docker Compose для продакшена", "uk": "Приклад Docker Compose для продакшену", "be": "Прыклад Docker Compose для продакшана",
                    "zh": "生产级 Docker Compose 编排范式", "es": "Ejemplo de Docker Compose para producción", "fr": "Exemple Docker Compose pour production", "de": "Produktions-Docker-Compose-Beispiel",
                    "ja": "本番環境向け Docker Compose 構成例", "pt": "Exemplo de Docker Compose para Produção", "ar": "مثال Docker Compose للإنتاج", "hi": "उत्पादन डॉकर कम्पोज़ उदाहरण", "bn": "প্রোডাকশন ডকার কম্পোজ উদাহরণ"
                },
                "code": {
                    "title": "docker-compose.prod.yml",
                    "lang": "yaml",
                    "content": """version: "3.8"

services:
  myairouter:
    image: myairouter:latest
    restart: always
    ports:
      - "8000:8000"
    environment:
      - ROUTER_MASTER_KEY=<GENERATED_ROUTER_MASTER_KEY>
      - DATABASE_URL=postgresql+asyncpg://router:<POSTGRES_PASSWORD>@postgres:5432/routerdb
      - ROUTER_PORT=8000
      - ROUTER_HOST=0.0.0.0
      - LOG_LEVEL=INFO
      - DEFAULT_TIMEOUT=45.0
      - CORS_ORIGINS=https://ai.yourcompany.internal
    depends_on:
      - postgres

  postgres:
    image: postgres:16-alpine
    restart: always
    environment:
      POSTGRES_USER: router
      POSTGRES_PASSWORD: <POSTGRES_PASSWORD>
      POSTGRES_DB: routerdb
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:"""
                }
            }
        ]
    }
]
