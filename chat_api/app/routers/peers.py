"""Действия пользователя в чате.

Бот ходит за vk и tg, приложение сайта — за web, engine_bridge — за аккаунты chat-engine
(кроме поиска и жалобы: их аккаунту заменяют `/engine/{account}/hunt` и `/attach`).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.deps import Chat, HumanPeer, ServicePeer
from app.schemas import MessageIn, MessageOut, StateOut, StopOut
from app.services.chat import NotChattingError

_NOT_CHATTING = "Нет активного диалога"

router = APIRouter(
    prefix="/peers/{platform}/{bot_key}/{user_id}",
    tags=["peers"],
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Нет токена или он не подходит"},
        status.HTTP_403_FORBIDDEN: {"description": "Токену недоступна эта платформа"},
    },
)


@router.post("/visit", status_code=status.HTTP_204_NO_CONTENT, summary="Отметить визит")
async def visit(peer: ServicePeer, chat: Chat) -> None:
    """Запоминает пользователя при первом обращении. Повторные вызовы ничего не меняют."""
    await chat.visit(peer)


@router.get("/state", summary="Текущее состояние")
async def state(peer: ServicePeer, chat: Chat) -> StateOut:
    """Фаза пользователя: `idle`, `searching` или `chatting`. Незнакомый пользователь — `idle`."""
    return await chat.state(peer)


@router.post("/search", summary="Искать собеседника")
async def search(peer: HumanPeer, chat: Chat) -> StateOut:
    """Ставит пользователя в очередь поиска.

    Если в очереди уже кто-то есть, пара создаётся сразу: ответ `chatting`,
    собеседник получает событие `partner_found`. Иначе ответ `searching`,
    а `partner_found` придёт пользователю событием, когда найдётся пара.
    Текущий диалог при этом закрывается, бывший собеседник получает
    `partner_left` с причиной `stopped`.
    """
    return await chat.search(peer)


@router.post("/stop", summary="Закончить диалог или поиск")
async def stop(peer: ServicePeer, chat: Chat) -> StopOut:
    """Переводит пользователя в `idle`.

    `was_active` показывает, был ли активный поиск или диалог. Собеседник
    получает `partner_left` с причиной `stopped`.
    """
    return await chat.stop(peer)


@router.post(
    "/report",
    summary="Пожаловаться на собеседника",
    responses={status.HTTP_409_CONFLICT: {"description": _NOT_CHATTING}},
)
async def report(peer: HumanPeer, chat: Chat) -> StateOut:
    """Закрывает диалог и сразу ставит пользователя в поиск, как `/search`.

    Собеседник получает `partner_left` с причиной `reported`.
    """
    try:
        return await chat.report(peer)
    except NotChattingError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, _NOT_CHATTING) from exc


@router.post(
    "/messages",
    summary="Отправить сообщение",
    responses={status.HTTP_409_CONFLICT: {"description": _NOT_CHATTING}},
)
async def send_message(body: MessageIn, peer: ServicePeer, chat: Chat) -> MessageOut:
    """Пересылает текст собеседнику событием `message`.

    Если собеседник уже вышел из пары, сообщение не доставляется: диалог
    закрывается, ответ `delivered=false` и `phase=idle`.
    """
    try:
        return await chat.send_message(peer, body.text)
    except NotChattingError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, _NOT_CHATTING) from exc


@router.post("/delivery-failed", status_code=status.HTTP_204_NO_CONTENT, summary="Сообщить о недоставке")
async def delivery_failed(peer: ServicePeer, chat: Chat) -> None:
    """Клиент не смог доставить событие этому пользователю, например он заблокировал бота.

    Поиск или диалог пользователя закрывается, собеседник получает
    `partner_left` с причиной `undeliverable`.
    """
    await chat.delivery_failed(peer)
