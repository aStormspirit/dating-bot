"""Счётчики онлайна для сайта и ботов."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.deps import Chat, CurrentClient
from app.schemas import StatsOut

router = APIRouter(
    tags=["stats"],
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "Нет токена или он не подходит"}},
)


@router.get("/stats", summary="Сколько людей онлайн, в поиске и в диалоге")
async def stats(_client: CurrentClient, chat: Chat) -> StatsOut:
    """Общие числа включают аккаунты chat-engine, разбивка — в `humans` и `bots`.

    Ответ кешируется на 5 секунд.
    """
    return await chat.stats()
