"""Настройки сервиса из переменных окружения."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    chat_api_service_token: str = Field(min_length=16)
    chat_api_app_token: str = Field(min_length=16)
    events_maxlen: int = 10_000

    @model_validator(mode="after")
    def _distinct_tokens(self) -> Settings:
        if self.chat_api_service_token == self.chat_api_app_token:
            raise ValueError("CHAT_API_SERVICE_TOKEN и CHAT_API_APP_TOKEN должны различаться")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
