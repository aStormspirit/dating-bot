"""Адресат: мессенджер или сайт, конкретный бот и пользователь."""

from __future__ import annotations

from dataclasses import dataclass

PLATFORMS = ("vk", "tg", "web")


@dataclass(frozen=True)
class Peer:
    """Один и тот же человек в двух ботах — два разных адреса."""

    platform: str
    bot_key: str
    user_id: int

    def __post_init__(self) -> None:
        if self.platform not in PLATFORMS:
            raise ValueError(f"Неизвестная платформа: {self.platform}")

    def as_dict(self) -> dict[str, str | int]:
        return {"platform": self.platform, "bot_key": self.bot_key, "user_id": self.user_id}
