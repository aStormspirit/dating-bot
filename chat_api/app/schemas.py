"""Pydantic-модели запросов, ответов и событий."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Phase = Literal["idle", "searching", "chatting"]
LeftReason = Literal["stopped", "reported", "undeliverable"]


class StateOut(BaseModel):
    phase: Phase


class StopOut(BaseModel):
    phase: Phase = "idle"
    was_active: bool


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=4096)


class MessageOut(BaseModel):
    delivered: bool
    phase: Phase


class ChatEvent(BaseModel):
    """Событие для второй стороны. Инициатор узнаёт итог из HTTP-ответа."""

    type: Literal["partner_found", "message", "partner_left"]
    text: str | None = None
    reason: LeftReason | None = None
