"""Зависимости маршрутов: сервис чата и адресат запроса."""

from __future__ import annotations

import hmac
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

import jwt
from fastapi import Depends, HTTPException, Path, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings
from app.peer import WEB_BOT_KEY, Peer
from app.services.chat import ChatService

_bearer = HTTPBearer(auto_error=False)
_GUEST_AUDIENCE = "chat-guest"


def get_chat(request: Request) -> ChatService:
    return request.app.state.chat


Chat = Annotated[ChatService, Depends(get_chat)]
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Нужен действующий токен",
        headers={"WWW-Authenticate": "Bearer"},
    )


def service_peer(
    platform: Annotated[Literal["vk", "tg"], Path()],
    bot_key: Annotated[str, Path(min_length=1, max_length=64)],
    user_id: Annotated[int, Path(gt=0)],
    credentials: Credentials,
    settings: AppSettings,
) -> Peer:
    """Бот действует от имени любого своего пользователя по сервисному токену."""
    if credentials is None or not hmac.compare_digest(
        credentials.credentials.encode(), settings.chat_api_service_token.encode()
    ):
        raise _unauthorized()
    return Peer(platform, bot_key, user_id)


def issue_guest_token(guest_id: int, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(guest_id),
        "aud": _GUEST_AUDIENCE,
        "iat": now,
        "exp": now + timedelta(days=settings.guest_token_days),
    }
    return jwt.encode(payload, settings.guest_jwt_secret, algorithm="HS256")


def decode_guest_token(token: str, settings: Settings) -> Peer:
    try:
        payload = jwt.decode(
            token,
            settings.guest_jwt_secret,
            algorithms=["HS256"],
            audience=_GUEST_AUDIENCE,
        )
        guest_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise _unauthorized() from exc
    return Peer("web", WEB_BOT_KEY, guest_id)


def guest_peer(credentials: Credentials, settings: AppSettings) -> Peer:
    if credentials is None:
        raise _unauthorized()
    return decode_guest_token(credentials.credentials, settings)


ServicePeer = Annotated[Peer, Depends(service_peer)]
GuestPeer = Annotated[Peer, Depends(guest_peer)]
