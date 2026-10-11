"""Публичный web gateway для Iskra: APP token остаётся на сервере."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.chat_client import ChatApiClient
from app.config import get_settings
from app.events import GuestHub
from app.routers import me

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    chat = ChatApiClient(settings.chat_api_url, settings.chat_api_app_token, settings.web_bot_key)
    hub = GuestHub(settings.chat_api_url, settings.chat_api_app_token, settings.web_bot_key)
    hub_task = asyncio.create_task(hub.run(), name="chat-api-events")
    app.state.chat = chat
    app.state.hub = hub
    try:
        yield
    finally:
        hub.stop()
        hub_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await hub_task
        await chat.aclose()


app = FastAPI(title="Iskra Web Gateway", version="1.0.0", lifespan=lifespan)

_origins = get_settings().cors_origin_list
if _origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

app.include_router(me.router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict[str, str]:
    chat: ChatApiClient = app.state.chat
    if not await chat.health():
        return {"status": "degraded", "chat_api": "down"}
    return {"status": "ok", "chat_api": "ok"}
