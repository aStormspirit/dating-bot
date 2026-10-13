"""Зависимости маршрутов: сервис чата, клиент API и адресат запроса."""

from __future__ import annotations

import hmac
from typing import Annotated, Literal

from fastapi import Depends, HTTPException, Path, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings
from app.peer import Peer
from app.services.chat import ChatService

Client = Literal["bot", "app"]
# Бот ВК и Telegram не может действовать от имени пользователей сайта и наоборот.
CLIENT_PLATFORMS: dict[Client, frozenset[str]] = {
    "bot": frozenset({"vk", "tg"}),
    "app": frozenset({"web"}),
}

_bearer = HTTPBearer(auto_error=False)


def get_chat(request: Request) -> ChatService:
    return request.app.state.chat


Chat = Annotated[ChatService, Depends(get_chat)]
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def _matches(token: str, expected: str) -> bool:
    return hmac.compare_digest(token.encode(), expected.encode())


def identify_client(token: str | None, settings: Settings) -> Client | None:
    """Определяет клиента по токену. None, если токен не подходит."""
    if not token:
        return None
    if _matches(token, settings.chat_api_service_token):
        return "bot"
    if _matches(token, settings.chat_api_app_token):
        return "app"
    return None


def current_client(credentials: Credentials, settings: AppSettings) -> Client:
    client = identify_client(credentials.credentials if credentials else None, settings)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Нужен действующий токен",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return client


CurrentClient = Annotated[Client, Depends(current_client)]


def service_peer(
    platform: Annotated[Literal["vk", "tg", "web"], Path(description="Платформа пользователя")],
    bot_key: Annotated[str, Path(min_length=1, max_length=64, description="Бот или сайт, через который пишет пользователь")],
    user_id: Annotated[int, Path(gt=0, description="ID пользователя на платформе")],
    client: CurrentClient,
) -> Peer:
    """Клиент действует от имени пользователя только своей платформы."""
    if platform not in CLIENT_PLATFORMS[client]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Токену недоступна платформа {platform}")
    return Peer(platform, bot_key, user_id)


ServicePeer = Annotated[Peer, Depends(service_peer)]
