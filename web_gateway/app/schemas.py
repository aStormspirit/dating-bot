"""Модели ответов gateway (зеркало Chat API + гость)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Phase = Literal["idle", "searching", "chatting"]


class GuestOut(BaseModel):
    token: str
    guest_id: int


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
