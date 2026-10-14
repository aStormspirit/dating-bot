"""Адресат: мессенджер или сайт, конкретный бот и пользователь."""

from __future__ import annotations

from dataclasses import dataclass

PLATFORMS = ("vk", "tg", "web", "engine")
# Аккаунты chat-engine (bots.chatwithyou.site): подменяют живого собеседника, когда очередь пуста.
ENGINE_PLATFORM = "engine"
# У аккаунта chat-engine один «пользователь»: сам аккаунт.
ENGINE_USER_ID = 1


@dataclass(frozen=True)
class Peer:
    """Куда доставить ответ: платформа, бот и id человека на ней."""

    platform: str
    bot_key: str
    user_id: int

    def __post_init__(self) -> None:
        if self.platform not in PLATFORMS:
            raise ValueError(f"Неизвестная платформа: {self.platform}")

    @property
    def is_engine(self) -> bool:
        return self.platform == ENGINE_PLATFORM

    def as_dict(self) -> dict[str, str | int]:
        return {"platform": self.platform, "bot_key": self.bot_key, "user_id": self.user_id}
