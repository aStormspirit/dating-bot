"""Действия пользователя в чате. Один набор маршрутов для ботов и для сайта.

Без `from __future__ import annotations`: FastAPI не разрешит локальный `CurrentPeer` из строки.
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.deps import Chat
from app.peer import Peer
from app.schemas import MessageIn, MessageOut, StateOut, StopOut
from app.services.chat import NotChattingError

_NOT_CHATTING = "Нет активного диалога"


def build_actions_router(prefix: str, tag: str, peer_dependency: Callable[..., Peer]) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[tag])
    CurrentPeer = Annotated[Peer, Depends(peer_dependency)]

    @router.post("/visit", status_code=status.HTTP_204_NO_CONTENT)
    async def visit(peer: CurrentPeer, chat: Chat) -> None:
        await chat.visit(peer)

    @router.get("/state")
    async def state(peer: CurrentPeer, chat: Chat) -> StateOut:
        return await chat.state(peer)

    @router.post("/search")
    async def search(peer: CurrentPeer, chat: Chat) -> StateOut:
        return await chat.search(peer)

    @router.post("/stop")
    async def stop(peer: CurrentPeer, chat: Chat) -> StopOut:
        return await chat.stop(peer)

    @router.post("/report", responses={409: {"description": _NOT_CHATTING}})
    async def report(peer: CurrentPeer, chat: Chat) -> StateOut:
        try:
            return await chat.report(peer)
        except NotChattingError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, _NOT_CHATTING) from exc

    @router.post("/messages", responses={409: {"description": _NOT_CHATTING}})
    async def send_message(body: MessageIn, peer: CurrentPeer, chat: Chat) -> MessageOut:
        try:
            return await chat.send_message(peer, body.text)
        except NotChattingError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, _NOT_CHATTING) from exc

    return router
