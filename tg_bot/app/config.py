"""Настройки запуска: токен бота Telegram и адреса Chat API."""

import os

TELEGRAM_BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()

# Логика чата живёт в Chat API. Бот вызывает его REST и читает события из Redis.
CHAT_API_URL = (os.getenv("CHAT_API_URL") or "http://localhost:8000").strip()
CHAT_API_SERVICE_TOKEN = (os.getenv("CHAT_API_SERVICE_TOKEN") or "").strip()
REDIS_URL = (os.getenv("REDIS_URL") or "redis://localhost:6379/0").strip()
# Имя потребителя в группе Redis. Постоянное, чтобы после перезапуска дочитать неподтверждённые события.
EVENTS_CONSUMER = (os.getenv("EVENTS_CONSUMER") or "tg-bot").strip()
