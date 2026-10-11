"""FastAPI-приложение Chat API."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from app.config import get_settings
from app.db import create_pool, ensure_schema
from app.events import REDIS_SOCKET_TIMEOUT, EventBus, WebSocketHub
from app.routers import me, peers, ws
from app.services.chat import ChatService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    pool = create_pool(settings.database_url)
    await pool.open(wait=True, timeout=60)
    await ensure_schema(pool)
    redis = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_timeout=REDIS_SOCKET_TIMEOUT,
        socket_connect_timeout=5,
    )
    hub = WebSocketHub(redis)
    hub_task = asyncio.create_task(hub.run(), name="web-events")

    app.state.chat = ChatService(pool, EventBus(redis, settings.events_maxlen))
    app.state.hub = hub
    app.state.pool = pool
    app.state.redis = redis
    try:
        yield
    finally:
        hub_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await hub_task
        await redis.aclose()
        await pool.close()


app = FastAPI(title="Chat API", version="1.0.0", lifespan=lifespan)

_origins = get_settings().cors_origin_list
if _origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

app.include_router(peers.router, prefix="/api/v1")
app.include_router(me.router, prefix="/api/v1")
app.include_router(ws.router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict[str, str]:
    """Проверяет базу и Redis: бот ждёт этот ответ перед запуском."""
    async with app.state.pool.connection() as conn:
        await conn.execute("SELECT 1")
    await app.state.redis.ping()
    return {"status": "ok"}
