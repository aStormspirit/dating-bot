"""Чтение событий Chat API для аккаунтов chat-engine из Redis Streams."""

from __future__ import annotations

import asyncio
import json
import logging

from redis.asyncio import Redis
from redis.exceptions import ResponseError

from app.bridge import Bridge

logger = logging.getLogger(__name__)

_GROUP = "bots"
_STREAM = "chat:events:engine"
_PENDING = "0"
_NEW = ">"
_BLOCK_MS = 5000


async def _ensure_group(redis: Redis) -> None:
    try:
        await redis.xgroup_create(_STREAM, _GROUP, id="$", mkstream=True)
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def _handle(bridge: Bridge, fields: dict) -> None:
    try:
        await bridge.handle_chat_event(json.loads(fields["data"]))
    except Exception:  # битое событие не должно стопорить очередь
        logger.exception("Не обработал событие %r", fields)


async def consume_events(bridge: Bridge, redis_url: str, consumer: str) -> None:
    """Сначала дочитывает события, не подтверждённые до перезапуска, потом ждёт новые."""
    # Таймаут сокета длиннее блокирующего XREADGROUP, иначе чтение обрывается.
    redis = Redis.from_url(
        redis_url,
        decode_responses=True,
        socket_timeout=_BLOCK_MS / 1000 + 10,
        socket_connect_timeout=5,
    )
    try:
        await _ensure_group(redis)
        cursors = {_STREAM: _PENDING}
        logger.info("Читаю события Chat API: %s", _STREAM)
        while True:
            try:
                batches = await redis.xreadgroup(_GROUP, consumer, cursors, count=50, block=_BLOCK_MS)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 — Redis может перезапускаться
                logger.warning("Не прочитал события: %s: %s", type(exc).__name__, exc)
                await asyncio.sleep(1)
                continue
            for stream, entries in batches or []:
                if not entries and cursors[stream] == _PENDING:
                    cursors[stream] = _NEW
                for entry_id, fields in entries:
                    await _handle(bridge, fields)
                    await redis.xack(stream, _GROUP, entry_id)
                    if cursors[stream] != _NEW:
                        cursors[stream] = entry_id
    finally:
        await redis.aclose()
