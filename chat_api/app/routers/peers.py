"""Маршруты ботов ВК и Telegram. Доступ по сервисному токену."""

from __future__ import annotations

from fastapi import status

from app.deps import Chat, ServicePeer, service_peer
from app.routers.actions import build_actions_router

router = build_actions_router("/peers/{platform}/{bot_key}/{user_id}", "bots", service_peer)


@router.post("/delivery-failed", status_code=status.HTTP_204_NO_CONTENT)
async def delivery_failed(peer: ServicePeer, chat: Chat) -> None:
    """Бот не смог доставить событие этому пользователю."""
    await chat.delivery_failed(peer)
