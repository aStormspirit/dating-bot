"""WebSocket событий платформы web для серверного приложения сайта."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.config import get_settings
from app.deps import identify_client

router = APIRouter(tags=["events"])


def _bearer_token(websocket: WebSocket) -> str | None:
    scheme, _, token = (websocket.headers.get("authorization") or "").partition(" ")
    return token.strip() if scheme.lower() == "bearer" else None


@router.websocket("/events/web")
async def web_events(websocket: WebSocket) -> None:
    """Все события пользователей сайта. Приложение само раздаёт их по своим пользователям.

    Требует заголовок `Authorization: Bearer <токен приложения>`, иначе
    соединение закрывается с кодом 1008. Сервер только отправляет JSON
    `{"to": {"platform", "bot_key", "user_id"}, "type", "text"?, "reason"?}`,
    входящие сообщения клиента игнорируются.
    """
    if identify_client(_bearer_token(websocket), get_settings()) != "app":
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await websocket.accept()
    hub = websocket.app.state.hub
    hub.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        hub.remove(websocket)
