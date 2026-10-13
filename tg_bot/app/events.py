"""Доставка событий Chat API в Telegram. События идут по WebSocket `/api/v1/events/tg`."""

from __future__ import annotations

import asyncio
import json
import logging
from urllib.parse import quote

from websockets.asyncio.client import connect

from app.api_client import ChatApiError, chat_api
from app.config import CHAT_API_URL, EVENTS_CONSUMER, chat_api_headers
from app.gateway import gateway
from app.handlers import cancel_search_timeout
from app.peer import Peer
from app.ui import FOUND_TEXT, PARTNER_LEFT_TEXT, UNDELIVERED_TEXT, format_partner

logger = logging.getLogger(__name__)

_RECONNECT_DELAY_SECONDS = 3.0


async def _deliver(body: dict) -> None:
    """Шлёт событие адресату. Если Telegram не принял, API закрывает его диалог."""
    to = body["to"]
    peer = Peer(str(to["bot_key"]), int(to["user_id"]))
    kind = body.get("type")
    if kind == "partner_found":
        cancel_search_timeout(peer)
        delivered = await gateway.send(peer, FOUND_TEXT, "chat")
    elif kind == "message":
        delivered = await gateway.send(peer, format_partner(str(body.get("text") or "")), "chat")
    elif kind == "partner_left":
        cancel_search_timeout(peer)
        text = UNDELIVERED_TEXT if body.get("reason") == "undeliverable" else PARTNER_LEFT_TEXT
        await gateway.send(peer, text, "main")
        return
    else:
        logger.warning("Неизвестное событие Chat API: %s", kind)
        return
    if delivered:
        return
    try:
        await chat_api.delivery_failed(peer)
    except ChatApiError as exc:
        logger.warning("Не сообщил API о недоставке %s: %s", peer, exc)


async def _handle(event: dict) -> None:
    try:
        await _deliver(event)
    except Exception:  # битое событие не должно стопорить очередь
        logger.exception("Не обработал событие %r", event)


async def consume_events() -> None:
    """Держит WebSocket событий: каждое событие доставляется и подтверждается по порядку."""
    url = f"{CHAT_API_URL.replace('http', 'ws', 1)}/api/v1/events/tg?consumer={quote(EVENTS_CONSUMER)}"
    while True:
        try:
            async with connect(
                url,
                additional_headers=chat_api_headers(),
                open_timeout=15,
                ping_interval=20,
                ping_timeout=20,
            ) as socket:
                logger.info("Читаю события Chat API: %s", url)
                async for raw in socket:
                    message = json.loads(raw)
                    await _handle(message["event"])
                    await socket.send(json.dumps({"ack": message["id"]}))
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — обрыв или перезапуск Chat API
            logger.warning("WebSocket событий: %s: %s", type(exc).__name__, exc)
        await asyncio.sleep(_RECONNECT_DELAY_SECONDS)
