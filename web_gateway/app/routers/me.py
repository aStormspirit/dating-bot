"""Браузерные маршруты гостя: проксируют peer-действия Chat API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status

from app.auth import decode_guest_id, issue_guest_token, new_guest_id
from app.chat_client import ChatApiError
from app.config import get_settings
from app.deps import ChatClient, GuestId
from app.schemas import GuestOut, MessageIn, MessageOut, StateOut, StopOut

router = APIRouter(tags=["site"])


def _raise_from_api(exc: ChatApiError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/guests", status_code=status.HTTP_201_CREATED)
async def create_guest(chat: ChatClient) -> GuestOut:
    """Новый анонимный гость. Сайт хранит token и шлёт его в Authorization."""
    settings = get_settings()
    guest_id = new_guest_id()
    try:
        await chat.visit(guest_id)
    except ChatApiError as exc:
        _raise_from_api(exc)
    return GuestOut(token=issue_guest_token(guest_id, settings), guest_id=guest_id)


@router.post("/me/visit", status_code=status.HTTP_204_NO_CONTENT)
async def visit(guest_id: GuestId, chat: ChatClient) -> None:
    try:
        await chat.visit(guest_id)
    except ChatApiError as exc:
        _raise_from_api(exc)


@router.get("/me/state")
async def state(guest_id: GuestId, chat: ChatClient) -> StateOut:
    try:
        return StateOut.model_validate(await chat.state(guest_id))
    except ChatApiError as exc:
        _raise_from_api(exc)


@router.post("/me/search")
async def search(guest_id: GuestId, chat: ChatClient) -> StateOut:
    try:
        return StateOut.model_validate(await chat.search(guest_id))
    except ChatApiError as exc:
        _raise_from_api(exc)


@router.post("/me/stop")
async def stop(guest_id: GuestId, chat: ChatClient) -> StopOut:
    try:
        return StopOut.model_validate(await chat.stop(guest_id))
    except ChatApiError as exc:
        _raise_from_api(exc)


@router.post("/me/report", responses={409: {"description": "Нет активного диалога"}})
async def report(guest_id: GuestId, chat: ChatClient) -> StateOut:
    try:
        return StateOut.model_validate(await chat.report(guest_id))
    except ChatApiError as exc:
        _raise_from_api(exc)


@router.post("/me/messages", responses={409: {"description": "Нет активного диалога"}})
async def send_message(body: MessageIn, guest_id: GuestId, chat: ChatClient) -> MessageOut:
    try:
        return MessageOut.model_validate(await chat.send_message(guest_id, body.text))
    except ChatApiError as exc:
        _raise_from_api(exc)


@router.websocket("/me/events")
async def guest_events(websocket: WebSocket, token: str) -> None:
    """Браузер не умеет слать Authorization в WS — токен в query, как раньше."""
    settings = get_settings()
    try:
        guest_id = decode_guest_id(token, settings)
    except HTTPException:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await websocket.accept()
    hub = websocket.app.state.hub
    hub.add(guest_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        hub.remove(guest_id, websocket)
