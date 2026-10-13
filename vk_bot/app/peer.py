"""Адресат сообщения: сообщество ВК и пользователь."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Peer:
    """Куда слать ответ. Один и тот же человек в двух сообществах — два разных адреса."""

    bot_key: str
    user_id: int
    platform: str = "vk"
