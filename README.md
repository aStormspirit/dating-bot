# Анонимный чат: боты ВК и Telegram + Chat API

Боты соединяют двух случайных людей из сообществ ВК и Telegram в анонимный диалог: очередь общая.
Боты и Chat API — отдельные сервисы в отдельных контейнерах: логика поиска и пар живёт в Chat API,
бот принимает сообщения, вызывает REST Chat API и доставляет события из Redis Streams.
Сайт (`landing`, отдельный репозиторий) ходит в тот же Chat API через Cloudflare Worker.

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
├── tg_bot/                     # Сервис: бот Telegram на aiogram (контейнер vk-tg-bot, профиль telegram)
│   └── app/                    # Тот же сценарий, что у ВК; события из chat:events:tg
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
│       ├── deps.py             # Авторизация по токену: бот или сайт (web)
│       ├── events.py           # Публикация событий в Redis Streams, WebSocket для сайта
│       ├── peer.py
│       ├── schemas.py
│       ├── repositories/sessions.py  # SQL: очередь, пары, пользователи
│       ├── services/chat.py    # Логика поиска и диалога
│       └── routers/            # peers.py — REST действий, engine.py — подбор из chat-engine,
│                               # stats.py — /stats, ws.py — /events/web
├── supabase/
│   ├── init/001_schema.sql     # Схема базы (идемпотентная)
│   └── studio/                 # Папки Supabase Studio
├── deploy/update.sh            # Обновление сервера: .env, pull образов, перезапуск
├── .github/workflows/
│   ├── deploy.yml              # Push в master → сборка образов → деплой
│   └── server-logs.yml         # Ручной просмотр логов на сервере
├── docker-compose.yml          # db, redis, chat-api, bot, tg-bot, engine-bridge, studio, meta, cloudflared
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

Бот Telegram и мост к chat-engine (нужны `TELEGRAM_BOT_TOKEN`, `CHAT_API_ENGINE_TOKEN`, `CHAT_ENGINE_TOKEN`):

```sh
COMPOSE_PROFILES=telegram,engine docker compose up --build
```

На сервере `deploy/update.sh` включает их сам, если в секретах GitHub есть `TELEGRAM_BOT_TOKEN`
и `CHAT_ENGINE_TOKEN` (это `API_TOKEN` chat-engine). `CHAT_API_ENGINE_TOKEN` генерируется на сервере.

Бот без Docker (Chat API и Redis уже запущены):

```sh
cd vk_bot
pip install -r requirements.txt
python -m app.main
```
