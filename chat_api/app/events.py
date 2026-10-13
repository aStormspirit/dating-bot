"""События для второй стороны диалога через Redis Streams.

Поток на платформу: `chat:events:vk`, `chat:events:tg`, `chat:events:web`, `chat:events:engine`.
Боты и engine_bridge читают свои потоки группой потребителей, поток сайта читает
сам API и отдаёт серверному приложению по WebSocket.
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import WebSocket
from redis.asyncio import Redis

from app.peer import ENGINE_PLATFORM, Peer
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
        await self._add(stream_name(recipient.platform), body, f"{event.type} для {recipient}")

    async def request_engine(self) -> None:
        """Человек остался в очереди один: engine_bridge сразу запускает поиск в chat-engine."""
        await self._add(stream_name(ENGINE_PLATFORM), {"type": "demand"}, "demand")

    async def _add(self, stream: str, body: dict, label: str) -> None:
        try:
            await self._redis.xadd(
                stream,
                {"data": json.dumps(body, ensure_ascii=False)},
                maxlen=self._maxlen,
                approximate=True,
            )
        except Exception:
            logger.exception("Не опубликовал событие %s", label)


class WebSocketHub:
    """Держит WebSocket-соединения приложения сайта с этой копией API и отдаёт им события web."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        self._sockets: set[WebSocket] = set()

    def add(self, socket: WebSocket) -> None:
        self._sockets.add(socket)

    def remove(self, socket: WebSocket) -> None:
        self._sockets.discard(socket)

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
        except ValueError:
            logger.warning("Битое событие в потоке сайта: %r", raw)
            return
        for socket in list(self._sockets):
            try:
                await socket.send_json(body)
            except Exception:  # noqa: BLE001 — закрытое соединение снимется в обработчике WebSocket
                self.remove(socket)
