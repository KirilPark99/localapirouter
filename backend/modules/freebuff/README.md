# Freebuff — freebuff2api-wokers

Модуль `freebuff` использует `/home/kiril/PythonProjects/freebuff2api-wokers/worker.js`
как движок. Исходный проект не переписан: discovery, выбор аккаунта, session/run lifecycle,
параметры и преобразования tools остаются в нём. `server.js` и его отдельная admin-панель
не запускаются; аккаунтами, маршрутизацией и клиентскими ключами управляет MyAIrouter.

## Настройка

1. Установить зависимости в checkout: `npm ci --ignore-scripts`.
2. Нужен Node >=22.19. Bun больше не нужен.
3. В **Модули → Freebuff** сохранить профиль. `project_path` указывает на новый checkout;
   сохранённый прежний default `/home/kiril/PythonProjects/freebuff-proxy` автоматически
   разрешается в новый движок, без изменения encrypted profile или удаления аккаунтов.
4. Можно указать `auth_token` либо войти по ссылке. Браузер автоматически не открывается.
   Использовать браузер с тем же выходным IP, что у профиля.
5. `api_base` — origin upstream (по умолчанию `https://www.codebuff.com`). Произвольные
   пути, credentials в URL и query запрещены. Локальный origin применяется в тестах.
6. Выполнить синхронизацию моделей. Идентификаторы нового движка отличаются от старых
   display-name моделей: выбирать новую модель из discovery, не менять цены старых строк.

Каждый профиль сохраняет свой приватный каталог
`$XDG_STATE_HOME/MyAIrouter/freebuff/<id>-<hash-даты-создания>/` и старые
`data/credentials/*.json`. Новый runtime читает только этот пул; чужие credentials,
глобальный HOME и данные checkout не импортируются. Новый numeric ID с другой датой
создания не наследует прежний аккаунт. `auth_token` хранится существующим encrypted store;
локальный runtime и login credentials имеют приватные права.

Выход — выбранный HTTP(S)-прокси профиля либо explicit direct. Все fetch, включая
публичные источники моделей, используют этот маршрут без env/direct fallback.
SOCKS из самостоятельного server.js этим модулем не объявлен поддерживаемым.
При существующем аккаунте или pending login изменение egress отклоняется. Привязка
маршрута не гарантирует неизменный внешний IP у прокси с ротацией.

## Контракт и ограничения

- Chat Completions: JSON и SSE через общий строгий collector MyAIrouter.
- Function tools исполняются только клиентом. Необъявленный tool не принимается;
  модуль не выполняет команды, код или функции модели на сервере.
- Неизвестные параметры отвергаются до запуска runtime/response cache. Параметры,
  поддерживаемые worker.js, передаются его штатной реализации.
- Обрыв/ошибка после отправки запроса не допускают автоматический replay/fallback.
- Терминальные upstream `403 banned/country_blocked/region_locked` передаются как
  явный отказ доступа, а не общий `502`. После такого ответа runtime прекращает
  admission/генерацию/повторы; адаптер запрещает fallback. Региональную или аккаунтную
  блокировку Freebuff модуль не снимает и IP автоматически не меняет.
  Если circuit breaker уже помнит такой отказ всего профиля, смена модели не
  сбрасывает защиту: direct и profile/group routing сразу возвращают сохранённую
  безопасную причину, без общего `No available healthy credentials` и ожидания таймаута.
  Другие рабочие профили и модельные rate-limit cooldown остаются доступны.
- Discovery — текущий `FREEBUFF_MODELS` picker, а не вся таблица agent mappings
  (она включает legacy/God-mode модели). Поддерживаемые worker.js строки не подтверждают
  доступ аккаунта, тариф или успешную генерацию. Лимиты без upstream данных неизвестны.
  `display_name` берётся из актуального каталога; wire ID может оставаться прежним:
  `mimo/mimo-v2.5` отображается как **MiMo 2.6 Flash**, это не повод переименовывать ID.
  Обновление установленного официального CLI само по себе не обновляет отдельный worker.
- Native Responses/Anthropic маршруты исходника не являются автоматически новыми
  маршрутам MyAIrouter: этот модуль подключён к существующему Chat Completions контракту.
- Browser login сохраняет прежний admin-only/no-store/profile-owned API и безопасные
  URL Freebuff/Codebuff. Late polling после cancel/expiry не сохраняет аккаунт.

Это сторонний клиент. README исходного проекта предупреждает о нарушении его трактовки
Freebuff ToS и риске необратимой блокировки аккаунта. Ни локальные тесты, ни обновление
модуля не гарантируют снятие upstream `freebuff_update_required` или другого отказа.
Модуль не дописывает поверх проекта новые fingerprint/version/TTY обходы.

## Проверка

```bash
backend/.venv/bin/python -I backend/modules/freebuff/verify.py --runtime
node backend/modules/freebuff/check_runtime.mjs
```

Проверки используют synthetic settings/DB/accounts и loopback upstream/proxy. Изменение
исходников не означает активацию в уже работающем backend; runtime/UI activation и
проверка реальным аккаунтом выполняются отдельно с сохранением настроек и egress.
