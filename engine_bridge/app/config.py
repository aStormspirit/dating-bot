"""Настройки моста между Chat API и chat-engine."""

from __future__ import annotations

import os


def _required(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise SystemExit(f"Не задан {name}.")
    return value


def _float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    return float(raw) if raw else default


CHAT_API_URL = (os.getenv("CHAT_API_URL") or "http://chat-api:8000").strip()
CHAT_API_ENGINE_TOKEN = _required("CHAT_API_ENGINE_TOKEN")
CHAT_ENGINE_URL = (os.getenv("CHAT_ENGINE_URL") or "https://bots.chatwithyou.site").strip().rstrip("/")
CHAT_ENGINE_TOKEN = _required("CHAT_ENGINE_TOKEN")
REDIS_URL = (os.getenv("REDIS_URL") or "redis://redis:6379/0").strip()
EVENTS_CONSUMER = (os.getenv("EVENTS_CONSUMER") or "engine-bridge").strip()

# Как часто сверять очередь с ищущими аккаунтами, даже если события demand не было.
RECONCILE_INTERVAL_SECONDS = _float("RECONCILE_INTERVAL_SECONDS", 3)
# Как часто перечитывать список аккаунтов chat-engine.
ACCOUNTS_REFRESH_SECONDS = _float("ACCOUNTS_REFRESH_SECONDS", 60)
# Визит аккаунта в Chat API: по нему /stats считает ботов онлайн.
HEARTBEAT_SECONDS = _float("HEARTBEAT_SECONDS", 60)
