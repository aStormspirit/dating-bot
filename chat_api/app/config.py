"""Настройки сервиса из переменных окружения."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    chat_api_service_token: str = Field(min_length=16)
    guest_jwt_secret: str = Field(min_length=32)
    guest_token_days: int = 30
    cors_origins: str = ""
    events_maxlen: int = 10_000

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
