"""Настройки запуска: токен, версия API и подключение к базе."""

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
    """Токены сообществ ВК. Первый — исходное сообщество, к нему крепятся старые диалоги."""
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


# Диалог после опенера идёт через Abliteration. Ключ: https://docs.abliteration.ai/quickstart
ABLIT_API_KEY = (os.getenv("ABLIT_KEY") or "").strip()
ABLIT_BASE_URL = "https://api.abliteration.ai/v1"
ABLIT_MODEL = (os.getenv("ABLIT_MODEL") or "abliterated-model").strip()
ABLIT_TIMEOUT = float(os.getenv("ABLIT_TIMEOUT") or "30")

ROOT_DIR = Path(__file__).resolve().parent.parent
# Старый файл сессий. При первом запуске с базой строки из него переносятся в Postgres.
CHATS_PATH = ROOT_DIR / "data" / "chats.json"
DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip()

PREMIUM_URL = (os.getenv("PREMIUM_URL") or "https://vk.cc/d2HjY8").strip()
_ASSETS = Path(__file__).resolve().parent / "assets"
WELCOME_IMAGE = _ASSETS / "welcome.jpg"
PREMIUM_IMAGE = _ASSETS / "premium.jpg"
