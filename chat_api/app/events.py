"""События для второй стороны диалога через Redis Streams.

Поток на платформу: `chat:events:vk`, `chat:events:tg`, `chat:events:web`.
Боты читают свои потоки группой потребителей, поток сайта читает сам API и раздаёт по WebSocket.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict

from fastapi import WebSocket
from redis.asyncio import Redis

from app.peer import WEB_BOT_KEY, Peer
from app.schemas import ChatEvent

logger = logging.getLogger(__name__)

STREAM_PREFIX = "chat:events:"
_BLOCK_MS = 5000
# Таймаут сокета должен быть длиннее блокирующего XREAD, иначе чтение обрывается.
REDIS_SOCKET_TIMEOUT = _BLOCK_MS / 1000 + 10


def stream_name(platform: str) -> str:
    return f"{STREAM_PREFIX}{platform}"


class EventBus:
    """Публикует события в поток платформы получателя."""

    def __init__(self, redis: Redis, maxlen: int) -> None:
        self._redis = redis
        self._maxlen = maxlen

    async def publish(self, recipient: Peer, event: ChatEvent) -> None:
        body = {"to": recipient.as_dict(), **event.model_dump(exclude_none=True)}
        try:
            await self._redis.xadd(
                stream_name(recipient.platform),
                {"data": json.dumps(body, ensure_ascii=False)},
                maxlen=self._maxlen,
                approximate=True,
            )
        except Exception:
            logger.exception("Не опубликовал событие %s для %s", event.type, recipient)


class WebSocketHub:
    """Держит WebSocket-соединения гостей этой копии API и отдаёт им события из потока сайта."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        self._sockets: dict[int, set[WebSocket]] = defaultdict(set)

    def add(self, guest_id: int, socket: WebSocket) -> None:
        self._sockets[guest_id].add(socket)

    def remove(self, guest_id: int, socket: WebSocket) -> None:
        sockets = self._sockets.get(guest_id)
        if not sockets:
            return
        sockets.discard(socket)
        if not sockets:
            del self._sockets[guest_id]

    async def run(self) -> None:
        """Читает поток сайта с текущего конца. Каждая копия API видит все события."""
        last_id = "$"
        stream = stream_name("web")
        while True:
            try:
                batches = await self._redis.xread({stream: last_id}, block=_BLOCK_MS, count=100)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Не прочитал поток сайта, повтор через секунду")
                await asyncio.sleep(1)
                continue
            for _stream, entries in batches or []:
                for entry_id, fields in entries:
                    last_id = entry_id
                    await self._dispatch(fields)

    async def _dispatch(self, fields: dict) -> None:
        raw = fields.get("data")
        if raw is None:
            return
        try:
            body = json.loads(raw)
            to = body.pop("to")
            if to.get("bot_key") != WEB_BOT_KEY:
                return
            guest_id = int(to["user_id"])
        except (ValueError, KeyError, TypeError, AttributeError):
            logger.warning("Битое событие в потоке сайта: %r", raw)
            return
        for socket in list(self._sockets.get(guest_id, ())):
            try:
                await socket.send_json(body)
            except Exception:  # noqa: BLE001 — закрытое соединение снимется в обработчике WebSocket
                self.remove(guest_id, socket)
