"""Подписка на Chat API /events/web и раздача событий гостям браузера."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict

import websockets
from fastapi import WebSocket
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)


class GuestHub:
    """Держит браузерные сокеты по guest_id и фильтрует fan-out с /events/web."""

    def __init__(self, chat_api_url: str, app_token: str, bot_key: str) -> None:
        self._ws_url = self._to_ws(chat_api_url.rstrip("/")) + "/api/v1/events/web"
        self._token = app_token
        self._bot_key = bot_key
        self._sockets: dict[int, set[WebSocket]] = defaultdict(set)
        self._stop = asyncio.Event()

    @staticmethod
    def _to_ws(http_url: str) -> str:
        if http_url.startswith("https://"):
            return "wss://" + http_url.removeprefix("https://")
        if http_url.startswith("http://"):
            return "ws://" + http_url.removeprefix("http://")
        return http_url

    def add(self, guest_id: int, socket: WebSocket) -> None:
        self._sockets[guest_id].add(socket)

    def remove(self, guest_id: int, socket: WebSocket) -> None:
        sockets = self._sockets.get(guest_id)
        if not sockets:
            return
        sockets.discard(socket)
        if not sockets:
            del self._sockets[guest_id]

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        """Держит upstream WebSocket к Chat API. При обрыве переподключается."""
        backoff = 1.0
        while not self._stop.is_set():
            try:
                async with websockets.connect(
                    self._ws_url,
                    additional_headers={"Authorization": f"Bearer {self._token}"},
                    ping_interval=20,
                    ping_timeout=20,
                    max_queue=256,
                ) as upstream:
                    logger.info("Подключено к Chat API /events/web")
                    backoff = 1.0
                    stop_wait = asyncio.create_task(self._stop.wait())
                    try:
                        while not self._stop.is_set():
                            recv = asyncio.create_task(upstream.recv())
                            done, pending = await asyncio.wait(
                                {recv, stop_wait},
                                return_when=asyncio.FIRST_COMPLETED,
                            )
                            if stop_wait in done:
                                for task in pending:
                                    task.cancel()
                                return
                            message = recv.result()
                            if isinstance(message, bytes):
                                message = message.decode()
                            await self._dispatch(message)
                    finally:
                        if not stop_wait.done():
                            stop_wait.cancel()
            except asyncio.CancelledError:
                raise
            except ConnectionClosed:
                logger.warning("Upstream /events/web закрыт, переподключение через %.0fs", backoff)
            except Exception:
                logger.exception("Ошибка upstream /events/web, повтор через %.0fs", backoff)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=backoff)
                return
            except TimeoutError:
                backoff = min(backoff * 2, 30.0)

    async def _dispatch(self, raw: str) -> None:
        try:
            body = json.loads(raw)
            to = body.get("to") or {}
            if to.get("bot_key") != self._bot_key:
                return
            guest_id = int(to["user_id"])
            event = {key: value for key, value in body.items() if key != "to"}
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            logger.warning("Битое событие от Chat API: %r", raw)
            return
        for socket in list(self._sockets.get(guest_id, ())):
            try:
                await socket.send_json(event)
            except Exception:  # noqa: BLE001 — закрытое соединение снимет обработчик WS
                self.remove(guest_id, socket)
