"""Настройки запуска: токены, версия API ВК и адреса Chat API."""

import os
import re
from pathlib import Path

TOKEN = (os.getenv("VK_TOKEN") or "").strip()
API_VERSION = "5.199"


def _token_list(*raw_values: str) -> list[str]:
    """Собирает токены из нескольких переменных. Повторы отбрасывает."""
    found: list[str] = []
    for raw in raw_values:
        for part in (raw or "").replace(";", ",").split(","):
            token = part.strip()
            if token and token not in found:
                found.append(token)
    return found


_TG_TOKEN = re.compile(r"^\d{6,}:[A-Za-z0-9_-]{20,}$")


def vk_tokens() -> list[str]:
    """Токены сообществ ВК."""
    raw = _token_list(os.getenv("VK_TOKEN") or "", os.getenv("VK_TOKENS") or "")
    return [token for token in raw if not _TG_TOKEN.match(token)]


def tg_tokens() -> list[str]:
    """Токены ботов Telegram. Пустой список — бот работает только во ВК."""
    raw = _token_list(
        os.getenv("TG_TOKEN") or "",
        os.getenv("TG_TOKENS") or "",
        os.getenv("VK_TOKEN") or "",
        os.getenv("VK_TOKENS") or "",
    )
    return [token for token in raw if _TG_TOKEN.match(token)]


# Логика чата живёт в Chat API. Бот вызывает его REST и читает события из Redis.
CHAT_API_URL = (os.getenv("CHAT_API_URL") or "http://localhost:8000").strip()
CHAT_API_SERVICE_TOKEN = (os.getenv("CHAT_API_SERVICE_TOKEN") or "").strip()
REDIS_URL = (os.getenv("REDIS_URL") or "redis://localhost:6379/0").strip()
# Имя потребителя в группе Redis. Постоянное, чтобы после перезапуска дочитать неподтверждённые события.
EVENTS_CONSUMER = (os.getenv("EVENTS_CONSUMER") or "bot").strip()

PREMIUM_URL = (os.getenv("PREMIUM_URL") or "https://vk.cc/d2HjY8").strip()
_ASSETS = Path(__file__).resolve().parent / "assets"
WELCOME_IMAGE = _ASSETS / "welcome.jpg"
PREMIUM_IMAGE = _ASSETS / "premium.jpg"
