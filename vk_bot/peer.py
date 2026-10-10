"""Адресат сообщения: мессенджер, конкретный бот и пользователь."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Peer:
    """Куда слать ответ. Один и тот же человек в двух ботах — два разных адреса."""

    platform: str
    bot_key: str
    user_id: int

    def __post_init__(self) -> None:
        if self.platform not in {"vk", "tg"}:
            raise ValueError(f"Неизвестный мессенджер: {self.platform}")
