"""Настройки запуска: токен, версия API и подключение к базе."""

import os
from pathlib import Path

TOKEN = (os.getenv("VK_TOKEN") or "").strip()
API_VERSION = "5.199"

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
