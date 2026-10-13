# Анонимный чат: боты ВК и Telegram + Chat API

Боты соединяют двух случайных людей из сообществ ВК и Telegram в анонимный диалог: очередь общая.
Боты и Chat API — отдельные сервисы. Логика поиска и пар живёт в Chat API.
Бот ВК принимает сообщения, вызывает REST Chat API и читает события из Redis Streams.
Бот Telegram работает на сервере chat-engine: ходит в Chat API по HTTPS
(`https://api.chatwithyou.site`) через Cloudflare Access и получает события по WebSocket
`/api/v1/events/tg`. Сайт (`landing`, отдельный репозиторий) ходит в тот же Chat API
через Cloudflare Worker.

## Собеседники из chat-engine

Если человек в очереди один, ему подбирается собеседник через chat-engine (bots.chatwithyou.site):
Chat API публикует событие `demand` в `chat:events:engine`, `engine_bridge` сразу запускает
поиск на свободном аккаунте chat-engine и, когда тот нашёл собеседника, вызывает
`POST /api/v1/engine/{account}/attach`. Живые люди в приоритете: аккаунты chat-engine в общую
очередь не попадают, а если человек за время поиска нашёл живого, `attach` отказывает и мост
закрывает разговор в chat-engine. Задержку перед подбором задаёт `ENGINE_FALLBACK_AFTER_SECONDS`
(по умолчанию 0), бот снимает человека с поиска через 30 секунд.

## Статистика для сайта

`GET /api/v1/stats` с любым токеном Chat API, кеш 5 секунд:

```json
{"online": 12, "searching": 2, "chatting": 8,
 "humans": {"online": 10, "searching": 2, "chatting": 4},
 "bots": {"online": 2, "searching": 0, "chatting": 4}}
```

Онлайн — кто в поиске или в диалоге, плюс кто писал за последние 5 минут
(`STATS_ONLINE_WINDOW_SECONDS`). Общие числа включают аккаунты chat-engine.

## Структура

```
.
├── vk_bot/                     # Сервис: бот ВК (контейнер vk-bot)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py             # Точка входа: Long Poll каждого сообщества и чтение событий
│       ├── config.py           # Переменные окружения: токены ВК, Chat API, Redis
│       ├── startup.py          # Проверка токена и включение Long Poll / кнопок сообщества
│       ├── longpoll.py         # BotPolling с обязательным параметром version
│       ├── handlers.py         # Сценарии: «Начать», поиск, следующий, стоп, пересылка реплик
│       ├── gateway.py          # Отправка ответа в нужное сообщество + клавиатуры
│       ├── events.py           # События Chat API из Redis Stream chat:events:vk → сообщения
│       ├── api_client.py       # HTTP-клиент Chat API (сервисный токен)
│       ├── peer.py             # Адресат: сообщество и пользователь
│       └── ui.py               # Тексты и клавиатуры
├── tg_bot/                     # Бот Telegram на aiogram. На проде — сервер chat-engine
│   ├── docker-compose.yml      # Один контейнер dating-tg-bot, без Redis и Postgres
│   └── app/                    # Тот же сценарий, что у ВК; события по WebSocket /events/tg
├── engine_bridge/              # Сервис: мост к chat-engine (контейнер vk-engine-bridge, профиль engine)
│   └── app/
│       ├── bridge.py           # demand → hunt → поиск в chat-engine → attach, пересылка реплик
│       ├── engine.py           # REST и WebSocket chat-engine
│       ├── chat_api.py         # Клиент Chat API от имени аккаунтов (токен CHAT_API_ENGINE_TOKEN)
│       └── events.py           # События Chat API из chat:events:engine
├── chat_api/                   # Сервис: Chat API на FastAPI (контейнер vk-chat-api)
│   ├── Dockerfile              # Собирается из корня: нужен каталог supabase/init
│   ├── requirements.txt
│   └── app/
│       ├── main.py             # Приложение, lifespan, /health
│       ├── config.py           # Настройки
│       ├── db.py               # Пул Postgres и прогон схемы при старте
│       ├── deps.py             # Авторизация по токену: бот ВК, бот Telegram, сайт, engine_bridge
│       ├── events.py           # Redis Streams и WebSocket-выдача событий ботам на других серверах
│       ├── peer.py
│       ├── schemas.py
│       ├── repositories/sessions.py  # SQL: очередь, пары, пользователи
│       ├── services/chat.py    # Логика поиска и диалога
│       └── routers/            # peers.py — REST действий, engine.py — подбор из chat-engine,
│                               # stats.py — /stats, ws.py — /events/web и /events/{vk|tg}
├── supabase/
│   ├── init/001_schema.sql     # Схема базы (идемпотентная)
│   └── studio/                 # Папки Supabase Studio
├── deploy/
│   ├── update.sh               # Сервер ВК: .env, pull образов, перезапуск
│   └── tg_update.sh            # Сервер chat-engine: контейнер бота Telegram
├── .github/workflows/
│   ├── deploy.yml              # Push в master → образы → сервер ВК, затем бот Telegram
│   └── server-logs.yml         # Ручной просмотр логов на сервере
├── docker-compose.yml          # db, redis, chat-api, bot, engine-bridge, studio, meta, cloudflared
└── .env.example
```

## Запуск

Всё вместе в Docker:

```sh
cp .env.example .env   # заполнить VK_TOKEN
docker compose up --build
```

- Chat API: http://127.0.0.1:8000/docs
- Studio: http://127.0.0.1:54323

Локально бот Telegram (нужны `TELEGRAM_BOT_TOKEN` и `CHAT_API_TG_TOKEN`):

```sh
COMPOSE_PROFILES=telegram docker compose up --build
```

На проде бот Telegram деплоится на сервер chat-engine отдельным job `telegram` в `deploy.yml`.
Секреты GitHub репозитория `aStormspirit/dating-bot`:

- `TELEGRAM_BOT_TOKEN` — токен @BotFather
- `CHAT_API_TG_TOKEN` — токен Chat API только для пользователей tg; один и тот же на обоих серверах
- `CF_ACCESS_CLIENT_ID` / `CF_ACCESS_CLIENT_SECRET` — сервисный токен Cloudflare Access к api.chatwithyou.site
- `TG_DEPLOY_HOST`, `TG_DEPLOY_USER`, `TG_DEPLOY_SSH_KEY` — SSH на сервер chat-engine (82.26.86.99)
- `CHAT_ENGINE_TOKEN` — `API_TOKEN` chat-engine, для `engine_bridge` на сервере ВК

`CHAT_API_ENGINE_TOKEN` генерируется на сервере ВК. Мост к chat-engine запускается, если задан `CHAT_ENGINE_TOKEN`.

Бот без Docker (Chat API и Redis уже запущены):

```sh
cd vk_bot
pip install -r requirements.txt
python -m app.main
```
