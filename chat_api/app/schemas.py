"""Pydantic-модели запросов, ответов и событий."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Phase = Literal["idle", "searching", "chatting"]
LeftReason = Literal["stopped", "reported", "undeliverable"]


class StateOut(BaseModel):
    phase: Phase = Field(description="`idle` — вне чата, `searching` — в очереди, `chatting` — в диалоге")


class StopOut(BaseModel):
    phase: Phase = "idle"
    was_active: bool = Field(description="Был ли поиск или диалог до остановки")


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=4096)


class MessageOut(BaseModel):
    delivered: bool = Field(description="Сообщение передано собеседнику")
    phase: Phase


class ChatEvent(BaseModel):
    """Событие для второй стороны. Инициатор узнаёт итог из HTTP-ответа."""

    type: Literal["partner_found", "message", "partner_left"]
    text: str | None = Field(None, description="Текст для `message`")
    reason: LeftReason | None = Field(None, description="Причина для `partner_left`")


class EngineDemandOut(BaseModel):
    waiting: int = Field(description="Людей в очереди дольше порога подбора бота")
    hunting: int = Field(description="Аккаунтов chat-engine, которые уже ищут собеседника")


class EngineAttachOut(BaseModel):
    attached: bool = Field(description="Аккаунт chat-engine связан с ждущим человеком")
    phase: Phase = Field(description="Фаза аккаунта chat-engine после вызова")


class PresenceOut(BaseModel):
    online: int = Field(description="В поиске, в диалоге или писали за последние минуты")
    searching: int
    chatting: int


class StatsOut(BaseModel):
    """Счётчики для сайта. Общие числа включают аккаунты chat-engine."""

    online: int
    searching: int
    chatting: int
    humans: PresenceOut
    bots: PresenceOut
