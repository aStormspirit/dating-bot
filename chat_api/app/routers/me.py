"""Маршруты сайта: выдача гостевого токена и действия гостя."""

from __future__ import annotations

from fastapi import APIRouter, Request, status

from app.deps import AppSettings, guest_peer, issue_guest_token
from app.repositories import sessions as repo
from app.routers.actions import build_actions_router
from app.schemas import GuestOut

router = APIRouter()
router.include_router(build_actions_router("/me", "site", guest_peer))


@router.post("/guests", status_code=status.HTTP_201_CREATED, tags=["site"])
async def create_guest(request: Request, settings: AppSettings) -> GuestOut:
    """Новый анонимный гость. Сайт хранит токен и шлёт его в Authorization."""
    async with request.app.state.pool.connection() as conn:
        guest_id = await repo.next_guest_id(conn)
    return GuestOut(token=issue_guest_token(guest_id, settings), guest_id=guest_id)
