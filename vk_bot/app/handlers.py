"""Сценарии входящих сообщений: меню, поиск и диалог."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from vkbottle.bot import Message, MessageEvent

from app.api_client import ChatApiError, NotChattingError, chat_api
from app.gateway import gateway, send_vk, vk_keyboard
from app.peer import Peer
from app.ui import (
    CHAT_BTN_NEXT,
    CHAT_BTN_STOP,
    COMMUNITY_GREETING,
    FOUND_TEXT,
    NO_PARTNERS_TEXT,
    PARTNER_LEFT_TEXT,
    SEARCHING_TEXT,
    SERVICE_DOWN_TEXT,
    STOPPED_TEXT,
    build_main_keyboard,
)

SEARCH_TIMEOUT_SECONDS = 30
_search_timeouts: dict[Peer, asyncio.Task[None]] = {}


def parse_payload(raw: Any) -> dict:
    """Payload кнопки как словарь. VK отдаёт и словарь, и строку JSON; битый payload — пустой словарь."""
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _is_start(text: str, payload: dict) -> bool:
    """Сообщение «Начать», /start или команда start из payload."""
    lowered = text.strip().lower()
    command = lowered.split()[0].split("@", 1)[0] if lowered else ""
    if command in {"начать", "/start", "start"}:
        return True
    return payload.get("command") == "start"


async def handle_stop(peer: Peer, text: str, active: bool) -> bool:
    """Заканчивает диалог или поиск и возвращает основное меню."""
    if text != CHAT_BTN_STOP or not active:
        return False
    await chat_api.stop(peer)
    await gateway.send(peer, STOPPED_TEXT, "main")
    return True


async def handle_next(peer: Peer, text: str, searching: bool) -> bool:
    """Кнопка «Следующий собеседник» запускает новый поиск."""
    if text != CHAT_BTN_NEXT:
        return False
    if searching:
        await gateway.send(peer, SEARCHING_TEXT, "chat")
        return True
    await connect_with_partner(peer)
    return True


async def handle_chat_line(peer: Peer, text: str, chatting: bool) -> bool:
    """Пересылает текст живому собеседнику."""
    if not chatting:
        return False
    if not text:
        await gateway.send(peer, "Напиши текстом.", "chat")
        return True
    try:
        delivered = (await chat_api.send_message(peer, text)).delivered
    except NotChattingError:
        delivered = False
    if not delivered:
        await gateway.send(peer, PARTNER_LEFT_TEXT, "main")
    return True


async def handle_menu_or_dialog(peer: Peer, text: str) -> None:
    """Разбирает меню и реплики диалога."""
    phase = await chat_api.phase(peer)
    chatting = phase == "chatting"
    searching = phase == "searching"

    if await handle_stop(peer, text, chatting or searching):
        return
    if await handle_next(peer, text, searching):
        return
    if await handle_chat_line(peer, text, chatting):
        return

    await gateway.send(peer, COMMUNITY_GREETING, "main")


async def handle_incoming(peer: Peer, text: str, payload: dict) -> None:
    """Маршрутизирует сообщение из лички: старт, затем меню или диалог."""
    try:
        await chat_api.visit(peer)
    except ChatApiError as exc:
        print(f"Не записал визит {peer.user_id}: {exc}", flush=True)
    try:
        if _is_start(text, payload):
            await connect_with_partner(peer)
            return
        await handle_menu_or_dialog(peer, text)
    except ChatApiError as exc:
        print(f"Chat API недоступен для {peer}: {exc}", flush=True)
        await gateway.send(peer, SERVICE_DOWN_TEXT, "main")


def vk_handler(bot_key: str):
    """Обработчик одного сообщества ВК. Ключ нужен, чтобы ответ ушёл тем же токеном."""

    async def _handle(message: Message) -> None:
        print(
            f"VK входящее group={bot_key} from={message.from_id} peer={message.peer_id}",
            flush=True,
        )
        try:
            if message.from_id is None or message.from_id <= 0:
                return
            text = (message.text or "").strip()
            payload = parse_payload(message.payload)
            peer = Peer(bot_key, message.from_id)
            if message.peer_id != message.from_id:
                await send_vk(message.ctx_api, message.peer_id, COMMUNITY_GREETING, vk_keyboard("greeting"))
                if _is_start(text, payload):
                    await connect_with_partner(peer)
                return
            await handle_incoming(peer, text, payload)
        except Exception as exc:  # noqa: BLE001 — иначе ошибка остаётся только в loguru и в docker её нет
            print(
                f"Ошибка ответа group={bot_key} from={message.from_id}: "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )

    return _handle


def vk_start_handler(bot_key: str):
    """Нажатие inline-кнопки «Начать» в личке или в беседе сообщества."""

    async def _handle(event: MessageEvent) -> None:
        print(
            f"VK кнопка group={bot_key} from={event.user_id} peer={event.peer_id}",
            flush=True,
        )
        try:
            await event.send_empty_answer()
        except Exception as exc:  # noqa: BLE001 — ответ на нажатие не должен срывать поиск
            print(f"Не подтвердил нажатие: {type(exc).__name__}: {exc}", flush=True)
        if parse_payload(event.payload).get("command") != "start":
            return
        if event.user_id is None or event.user_id <= 0:
            return
        peer = Peer(bot_key, event.user_id)
        try:
            await connect_with_partner(peer)
        except ChatApiError as exc:
            print(f"Chat API недоступен для {peer}: {exc}", flush=True)
            await gateway.send(peer, SERVICE_DOWN_TEXT, "main")
        except Exception as exc:  # noqa: BLE001
            print(
                f"Ошибка кнопки Начать group={bot_key} from={event.user_id}: "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )

    return _handle


def _vk_body(response: object) -> dict:
    """Достаёт словарь ответа VK и из обёртки response, и из уже распакованного тела."""
    if not isinstance(response, dict):
        return {}
    nested = response.get("response")
    if "items" not in response and isinstance(nested, dict):
        return nested
    return response


async def answer_waiting(api: Any, bot_key: str) -> None:
    """Отвечает на чужие сообщения за последний час, которые бот ещё не закрыл своим ответом."""
    response = await api.request("messages.getConversations", {"count": 20})
    items = _vk_body(response).get("items")
    if not items:
        print(f"Непрочитанных диалогов нет (group_id={bot_key}).", flush=True)
        return
    cutoff = int(time.time()) - 3600
    for item in items:
        conversation = item.get("conversation") or {}
        last = item.get("last_message") or {}
        peer_id = (conversation.get("peer") or {}).get("id")
        from_id = int(last.get("from_id") or 0)
        if not peer_id or from_id <= 0 or int(last.get("out") or 0) == 1:
            continue
        if int(last.get("date") or 0) < cutoff:
            continue
        await send_vk(api, peer_id, COMMUNITY_GREETING, build_main_keyboard())
        try:
            await api.request("messages.markAsRead", {"peer_id": peer_id})
        except Exception as exc:  # noqa: BLE001
            print(f"Не отметил прочитанным peer={peer_id}: {type(exc).__name__}: {exc}", flush=True)
        print(f"Ответил на ожидающее group={bot_key} peer={peer_id}", flush=True)


async def attach_start_buttons(api: Any, bot_key: str) -> None:
    """Дописывает кнопку «Начать» к свежим приветствиям, которые ушли без неё."""
    response = await api.request("messages.getConversations", {"count": 30})
    items = _vk_body(response).get("items") or []
    for item in items:
        peer_id = ((item.get("conversation") or {}).get("peer") or {}).get("id")
        if not peer_id:
            continue
        history = await api.request("messages.getHistory", {"peer_id": peer_id, "count": 8})
        for message in _vk_body(history).get("items") or []:
            text = message.get("text") or ""
            if int(message.get("out") or 0) != 1 or "Нажми кнопку начать" not in text:
                continue
            edit: dict = {
                "peer_id": peer_id,
                "message": text,
                "keyboard": build_main_keyboard(),
            }
            if message.get("conversation_message_id"):
                edit["conversation_message_id"] = message["conversation_message_id"]
            elif message.get("id"):
                edit["message_id"] = message["id"]
            else:
                break
            try:
                await api.messages.edit(**edit)
            except Exception as exc:  # noqa: BLE001
                print(
                    f"Не добавил кнопку group={bot_key} peer={peer_id}: "
                    f"{type(exc).__name__}: {exc}",
                    flush=True,
                )
            else:
                print(f"Добавил кнопку Начать group={bot_key} peer={peer_id}", flush=True)
            break


def cancel_search_timeout(peer: Peer) -> None:
    """С поиска уже сняли: найден собеседник или диалог закончен."""
    previous = _search_timeouts.pop(peer, None)
    if previous is not None:
        previous.cancel()


async def _leave_queue_later(peer: Peer) -> None:
    """Через SEARCH_TIMEOUT_SECONDS снимает с поиска, если пара так и не нашлась."""
    try:
        await asyncio.sleep(SEARCH_TIMEOUT_SECONDS)
        if await chat_api.phase(peer) != "searching":
            return
        await chat_api.stop(peer)
        await gateway.send(peer, NO_PARTNERS_TEXT, "main")
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001 — фоновая задача, иначе ошибка потеряется
        print(f"Не снял с поиска {peer}: {type(exc).__name__}: {exc}", flush=True)
    finally:
        if _search_timeouts.get(peer) is asyncio.current_task():
            del _search_timeouts[peer]


async def connect_with_partner(peer: Peer) -> None:
    """Ставит в поиск. Второй стороне о паре и прежнему собеседнику об уходе пишет Chat API."""
    phase = await chat_api.search(peer)
    await gateway.send(peer, SEARCHING_TEXT, "chat")
    cancel_search_timeout(peer)
    if phase == "chatting":
        await gateway.send(peer, FOUND_TEXT, "chat")
        return
    _search_timeouts[peer] = asyncio.create_task(_leave_queue_later(peer))
