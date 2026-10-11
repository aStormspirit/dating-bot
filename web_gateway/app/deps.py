"""Зависимости маршрутов gateway."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth import decode_guest_id
from app.chat_client import ChatApiClient
from app.config import Settings, get_settings

_bearer = HTTPBearer(auto_error=False)

Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def get_chat_client(request: Request) -> ChatApiClient:
    return request.app.state.chat


ChatClient = Annotated[ChatApiClient, Depends(get_chat_client)]


def current_guest_id(credentials: Credentials, settings: AppSettings) -> int:
    token = credentials.credentials if credentials else ""
    return decode_guest_id(token, settings)


GuestId = Annotated[int, Depends(current_guest_id)]
