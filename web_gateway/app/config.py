"""Настройки web gateway из переменных окружения."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    chat_api_url: str = "http://localhost:8000"
    chat_api_app_token: str = Field(min_length=16)
    guest_jwt_secret: str = Field(min_length=32)
    guest_token_days: int = 30
    web_bot_key: str = "site"
    cors_origins: str = "http://localhost:3000"

    @field_validator("chat_api_url")
    @classmethod
    def _strip_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
