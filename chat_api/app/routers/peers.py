"""Действия пользователя в чате. Бот ходит за vk и tg, приложение сайта — за web."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.deps import Chat, ServicePeer
from app.schemas import MessageIn, MessageOut, StateOut, StopOut
from app.services.chat import NotChattingError

_NOT_CHATTING = "Нет активного диалога"

router = APIRouter(prefix="/peers/{platform}/{bot_key}/{user_id}", tags=["peers"])


@router.post("/visit", status_code=status.HTTP_204_NO_CONTENT)
async def visit(peer: ServicePeer, chat: Chat) -> None:
    await chat.visit(peer)


@router.get("/state")
async def state(peer: ServicePeer, chat: Chat) -> StateOut:
    return await chat.state(peer)


@router.post("/search")
async def search(peer: ServicePeer, chat: Chat) -> StateOut:
    return await chat.search(peer)


@router.post("/stop")
async def stop(peer: ServicePeer, chat: Chat) -> StopOut:
    return await chat.stop(peer)


@router.post("/report", responses={409: {"description": _NOT_CHATTING}})
async def report(peer: ServicePeer, chat: Chat) -> StateOut:
    try:
        return await chat.report(peer)
    except NotChattingError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, _NOT_CHATTING) from exc


@router.post("/messages", responses={409: {"description": _NOT_CHATTING}})
async def send_message(body: MessageIn, peer: ServicePeer, chat: Chat) -> MessageOut:
    try:
        return await chat.send_message(peer, body.text)
    except NotChattingError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, _NOT_CHATTING) from exc


@router.post("/delivery-failed", status_code=status.HTTP_204_NO_CONTENT)
async def delivery_failed(peer: ServicePeer, chat: Chat) -> None:
    """Клиент не смог доставить событие этому пользователю."""
    await chat.delivery_failed(peer)
