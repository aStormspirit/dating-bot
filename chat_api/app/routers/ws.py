"""WebSocket событий для гостя сайта."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status

from app.config import get_settings
from app.deps import decode_guest_token

router = APIRouter(tags=["site"])


@router.websocket("/me/events")
async def guest_events(websocket: WebSocket, token: str) -> None:
    """Браузер не умеет слать заголовки в WebSocket, поэтому токен идёт в query."""
    try:
        peer = decode_guest_token(token, get_settings())
    except HTTPException:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await websocket.accept()
    hub = websocket.app.state.hub
    hub.add(peer.user_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        hub.remove(peer.user_id, websocket)
