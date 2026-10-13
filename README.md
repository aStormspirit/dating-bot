# Анонимный чат: бот ВК + Chat API

Бот соединяет двух случайных людей из сообществ ВК в анонимный диалог.
Бот и Chat API — отдельные сервисы в отдельных контейнерах: логика поиска и пар живёт в Chat API,
бот принимает сообщения ВК, вызывает REST Chat API и доставляет события из Redis Streams.
Сайт (`landing`, отдельный репозиторий) ходит в тот же Chat API через Cloudflare Worker.

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
│       └── routers/            # peers.py — REST действий, ws.py — /events/web
├── supabase/
│   ├── init/001_schema.sql     # Схема базы (идемпотентная)
│   └── studio/                 # Папки Supabase Studio
├── deploy/update.sh            # Обновление сервера: .env, pull образов, перезапуск
├── .github/workflows/
│   ├── deploy.yml              # Push в master → сборка образов → деплой
│   └── server-logs.yml         # Ручной просмотр логов на сервере
├── docker-compose.yml          # db, redis, chat-api, bot, studio, meta, cloudflared (профиль proxy)
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

Бот без Docker (Chat API и Redis уже запущены):

```sh
cd vk_bot
pip install -r requirements.txt
python -m app.main
```
