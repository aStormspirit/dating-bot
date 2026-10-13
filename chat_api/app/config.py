"""Настройки сервиса из переменных окружения."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    chat_api_service_token: str = Field(min_length=16)
    chat_api_app_token: str = Field(min_length=16)
    # Токен engine_bridge. Без него собеседники из chat-engine не подключаются.
    chat_api_engine_token: str | None = Field(None, min_length=16)
    # Сколько человек ждёт живого собеседника, прежде чем ему подберут бота из chat-engine.
    engine_fallback_after_seconds: float = Field(0, ge=0)
    # Кто писал за это время, считается онлайн в /stats.
    stats_online_window_seconds: float = Field(300, gt=0)
    events_maxlen: int = 10_000

    @field_validator("chat_api_engine_token", mode="before")
    @classmethod
    def _empty_as_unset(cls, value: object) -> object:
        """Compose передаёт незаданную переменную пустой строкой."""
        return None if isinstance(value, str) and not value.strip() else value

    @property
    def engine_enabled(self) -> bool:
        return bool(self.chat_api_engine_token)

    @model_validator(mode="after")
    def _distinct_tokens(self) -> Settings:
        tokens = [self.chat_api_service_token, self.chat_api_app_token]
        if self.chat_api_engine_token:
            tokens.append(self.chat_api_engine_token)
        if len(set(tokens)) != len(tokens):
            raise ValueError("CHAT_API_SERVICE_TOKEN, CHAT_API_APP_TOKEN и CHAT_API_ENGINE_TOKEN должны различаться")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
