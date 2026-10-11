"""Гостевые JWT для браузера. APP token в браузер не попадает."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException, status

from app.config import Settings

_GUEST_AUDIENCE = "chat-guest"


def new_guest_id() -> int:
    """Положительный уникальный id без общей последовательности в Chat API."""
    return secrets.randbelow(2**48 - 1) + 1


def issue_guest_token(guest_id: int, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(guest_id),
        "aud": _GUEST_AUDIENCE,
        "iat": now,
        "exp": now + timedelta(days=settings.guest_token_days),
    }
    return jwt.encode(payload, settings.guest_jwt_secret, algorithm="HS256")


def decode_guest_id(token: str, settings: Settings) -> int:
    try:
        payload = jwt.decode(
            token,
            settings.guest_jwt_secret,
            algorithms=["HS256"],
            audience=_GUEST_AUDIENCE,
        )
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Нужен действующий токен",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
