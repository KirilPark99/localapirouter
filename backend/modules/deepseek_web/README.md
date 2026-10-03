# DeepSeek Web Provider Module

Модуль для интеграции веб-версии DeepSeek ([chat.deepseek.com](https://chat.deepseek.com)) в качестве стандартного OpenAI-совместимого провайдера в MyAIrouter. Архитектура и сетевые протоколы портированы и адаптированы из OmniRoute (`open-sse/executors/deepseek-web.ts`).

---

## 🚀 Особенности

1. **Proof-of-Work (PoW) Solver (`DeepSeekHashV1`)**:
   - Высокопроизводительный расчёт хеш-коллизий Keccak на базе WebAssembly (`sha3_wasm_bg.wasm`) — нахождение nonce занимает **1–50 мс**.
   - Автоматический fallback на чистый JavaScript/Node.js при необходимости.
2. **Поддержка R1 Reasoning / Thinking**:
   - Полная потоковая передача процесса рассуждений через `reasoning_content` (совместимо со всеми OpenAI/OpenCode/Cline/Roo-Code клиентами).
3. **Web Search & Цитаты**:
   - Поддержка онлайн веб-поиска DeepSeek с автоматическим извлечением источников (`search_results`) и форматированием markdown-сносок `[1]: [Title](URL)`.
4. **Управление сессиями и контекстом**:
   - Автоматическое создание сессий на бэкенде DeepSeek.
   - Возможность включить `persist_session` для сохранения контекста на сервере DeepSeek.
   - Скользящее окно истории (`history_window`, по умолчанию 20 реплик) для сохранения контекста многошаговых диалогов и агентов.
5. **Tool Calling (Function Calling)**:
   - Автоматическая сериализация OpenAI инструментов (`tools`) в строгий формат контракта `<tool>...</tool>` с nonce-библиотекой и обратный парсинг ответов модели в стандартные `tool_calls`.
6. **Полная поддержка прокси**:
   - Работа через назначенные HTTP, HTTPS, SOCKS5 или SOCKS5H прокси для обхода геоблокировок и ограничений.

---

## 🔑 Как получить `userToken`

1. Откройте в браузере [chat.deepseek.com](https://chat.deepseek.com) и войдите в свой аккаунт.
2. Откройте инструменты разработчика (клавиша **F12** или **Ctrl+Shift+I**).
3. Перейдите на вкладку **Application** (или **Хранилище** в Firefox) → слева раскройте **Local Storage** → выберите `https://chat.deepseek.com`.
4. Найдите ключ **`userToken`**.
5. Скопируйте его значение (это может быть как строка токена, так и JSON вида `{"value":"..."}`) — модуль автоматически поддерживает оба формата.

---

## 📋 Поддерживаемые модели

- **`deepseek-chat`** — стандартная модель DeepSeek V3 (быстрый чат).
- **`deepseek-reasoner`** — модель DeepSeek R1 с генерацией цепочки рассуждений (`reasoning_content`).
- **`deepseek-search`** — модель DeepSeek V3 с включённым поиском в интернете.
- **`deepseek-reasoner-search`** — модель DeepSeek R1 с рассуждениями и онлайн-поиском.
