"""Сценарии входящих сообщений: меню, поиск и диалог."""

from __future__ import annotations

import json
import time
from pathlib import Path

from vkbottle.bot import Message, MessageEvent

from vk_bot.chat import (
    FOUND_TEXT,
    SEARCHING_TEXT,
    begin_search,
    format_partner,
    is_chatting,
    is_searching,
    pair_searcher,
    partner_of,
    remember_visitor,
    stop_chat,
)
from vk_bot.gateway import gateway
from vk_bot.peer import Peer
from vk_bot.photos import upload_photo
from vk_bot.ui import (
    CHAT_BTN_NEXT,
    CHAT_BTN_REPORT,
    CHAT_BTN_STOP,
    COMMUNITY_GREETING,
    MENU_BTN_SEARCH,
    build_chat_keyboard,
    build_main_keyboard,
    menu_message,
    new_random_id,
)

_SEARCH_BUTTONS = {MENU_BTN_SEARCH, "🔍 Поиск", CHAT_BTN_NEXT, "Начать"}
_PARTNER_LEFT = "Собеседник завершил диалог. Нажми «Найти собеседника», чтобы найти нового."


def parse_payload(message: Message) -> dict:
    """Достаёт JSON из payload кнопки. Пустой словарь, если его нет или он битый."""
    if not message.payload:
        return {}
    try:
        data = json.loads(message.payload)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _is_start(text: str, payload: dict) -> bool:
    """Сообщение «Начать», /start или команда start из payload."""
    lowered = text.strip().lower()
    command = lowered.split()[0].split("@", 1)[0] if lowered else ""
    if command in {"начать", "/start", "start"}:
        return True
    return payload.get("command") == "start"


def _vk_keyboard(kind: str) -> str:
    """JSON клавиатуры ВК для ответа в том же сообщении."""
    if kind == "chat":
        return build_chat_keyboard()
    return build_main_keyboard()


async def _answer_vk(message: Message, text: str, kind: str, *, attachment: str | None = None) -> None:
    """Пишет в тот же диалог. Если клавиатуру отклонили, отправляет тот же текст без неё."""
    kwargs: dict = {"keyboard": _vk_keyboard(kind), "random_id": new_random_id()}
    if attachment:
        kwargs["attachment"] = attachment
    try:
        await message.answer(text, **kwargs)
    except Exception as exc:
        print(f"Клавиатура не принята, шлю текст: {type(exc).__name__}: {exc}", flush=True)
        plain: dict = {"random_id": new_random_id()}
        if attachment:
            plain["attachment"] = attachment
        await message.answer(text, **plain)


async def _reply(
    peer: Peer,
    text: str,
    kind: str,
    vk_message: Message | None,
    *,
    photo: Path | None = None,
) -> bool:
    """Отвечает тому, кто только что написал. Во ВК можно приложить картинку."""
    if vk_message is not None:
        attachment = await upload_photo(vk_message, photo) if photo is not None else None
        await _answer_vk(vk_message, text, kind, attachment=attachment)
        return True
    return await gateway.send(peer, text, kind, photo=photo)


async def _notify_left(partner: Peer) -> None:
    """Сообщает второй стороне, что диалог закончился."""
    await gateway.send(partner, menu_message(_PARTNER_LEFT), "main")


async def handle_start(peer: Peer, text: str, payload: dict, vk_message: Message | None) -> bool:
    """Кнопка «Начать» ставит человека в поиск собеседника."""
    if not _is_start(text, payload):
        return False
    await connect_with_partner(peer, vk_message)
    return True


async def handle_stop(
    peer: Peer,
    text: str,
    chatting: bool,
    searching: bool,
    vk_message: Message | None,
) -> bool:
    """Заканчивает диалог или поиск и возвращает основное меню."""
    if text != CHAT_BTN_STOP or not (chatting or searching):
        return False
    partner = stop_chat(peer)
    await _reply(
        peer,
        menu_message("Диалог остановлен. Нажми «Найти собеседника», чтобы начать снова."),
        "main",
        vk_message,
    )
    if partner is not None:
        await _notify_left(partner)
    return True


async def handle_report(peer: Peer, text: str, chatting: bool, vk_message: Message | None) -> bool:
    """Принимает жалобу в активном диалоге и сразу ищет другого собеседника."""
    if text != CHAT_BTN_REPORT or not chatting:
        return False
    await _reply(peer, menu_message("Жалоба отправлена. Ищем другого собеседника."), "chat", vk_message)
    await connect_with_partner(peer, vk_message)
    return True


async def handle_search(peer: Peer, text: str, vk_message: Message | None) -> bool:
    """Запускает поиск по кнопке «Найти собеседника» или «Следующий собеседник»."""
    if text not in _SEARCH_BUTTONS:
        return False
    if is_searching(peer):
        await _reply(peer, SEARCHING_TEXT, "chat", vk_message)
        return True
    await connect_with_partner(peer, vk_message)
    return True


async def handle_chat_line(
    peer: Peer,
    text: str,
    chatting: bool,
    vk_message: Message | None,
) -> bool:
    """Пересылает текст живому собеседнику."""
    if not chatting:
        return False
    if not text:
        await _reply(peer, "Напиши текстом.", "chat", vk_message)
        return True
    partner = partner_of(peer)
    if partner is None:
        stop_chat(peer)
        await _reply(peer, menu_message(_PARTNER_LEFT), "main", vk_message)
        return True
    delivered = await gateway.send(partner, format_partner(text), "chat")
    if delivered:
        return True
    stop_chat(peer)
    await _reply(peer, menu_message("Не удалось доставить сообщение. Диалог остановлен."), "main", vk_message)
    return True


async def handle_menu_or_dialog(peer: Peer, text: str, vk_message: Message | None) -> None:
    """Разбирает меню и реплики диалога."""
    chatting = is_chatting(peer)
    searching = is_searching(peer)

    if await handle_stop(peer, text, chatting, searching, vk_message):
        return
    if await handle_report(peer, text, chatting, vk_message):
        return
    if await handle_search(peer, text, vk_message):
        return
    if await handle_chat_line(peer, text, chatting, vk_message):
        return

    await _reply(peer, COMMUNITY_GREETING, "main", vk_message)


async def handle_incoming(
    peer: Peer,
    text: str,
    payload: dict,
    vk_message: Message | None = None,
) -> None:
    """Маршрутизирует сообщение из ВК или Telegram: старт, затем меню или диалог."""
    try:
        remember_visitor(peer)
    except Exception as exc:  # noqa: BLE001 — сбой базы не должен оставлять человека без ответа
        print(f"Не записал визит {peer.user_id}: {type(exc).__name__}: {exc}", flush=True)
    if await handle_start(peer, text, payload, vk_message):
        return
    await handle_menu_or_dialog(peer, text, vk_message)


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
            payload = parse_payload(message)
            peer = Peer("vk", bot_key, message.from_id)
            if message.peer_id != message.from_id:
                await _answer_vk(message, COMMUNITY_GREETING, "main")
                if _is_start(text, payload):
                    await connect_with_partner(peer, None)
                return
            await handle_incoming(peer, text, payload, message)
        except Exception as exc:  # noqa: BLE001 — иначе ошибка остаётся только в loguru и в docker её нет
            print(
                f"Ошибка ответа group={bot_key} from={message.from_id}: "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )

    return _handle


def _event_payload(event: MessageEvent) -> dict:
    """Достаёт payload нажатой кнопки. VK отдаёт и словарь, и строку JSON."""
    raw = event.payload
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}
    return {}


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
        if _event_payload(event).get("command") != "start":
            return
        if event.user_id is None or event.user_id <= 0:
            return
        try:
            await connect_with_partner(Peer("vk", bot_key, event.user_id), None)
        except Exception as exc:  # noqa: BLE001
            print(
                f"Ошибка кнопки Начать group={bot_key} from={event.user_id}: "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )

    return _handle


async def answer_waiting(api: object, bot_key: str) -> None:
    """Отвечает на чужие сообщения за последний час, которые бот ещё не закрыл своим ответом."""
    response = await api.request("messages.getConversations", {"count": 20})  # type: ignore[attr-defined]
    payload = response
    if isinstance(payload, dict) and "items" not in payload and isinstance(payload.get("response"), dict):
        payload = payload["response"]
    items = payload.get("items") if isinstance(payload, dict) else None
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
        try:
            await api.messages.send(  # type: ignore[attr-defined]
                peer_id=peer_id,
                message=COMMUNITY_GREETING,
                keyboard=build_main_keyboard(),
                random_id=new_random_id(),
            )
        except Exception as exc:
            print(
                f"Клавиатура не принята для peer={peer_id}, шлю текст: {type(exc).__name__}: {exc}",
                flush=True,
            )
            await api.messages.send(  # type: ignore[attr-defined]
                peer_id=peer_id,
                message=COMMUNITY_GREETING,
                random_id=new_random_id(),
            )
        try:
            await api.request("messages.markAsRead", {"peer_id": peer_id})  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            print(f"Не отметил прочитанным peer={peer_id}: {type(exc).__name__}: {exc}", flush=True)
        print(f"Ответил на ожидающее group={bot_key} peer={peer_id}", flush=True)


async def attach_start_buttons(api: object, bot_key: str) -> None:
    """Дописывает кнопку «Начать» к свежим приветствиям, которые ушли без неё."""
    response = await api.request("messages.getConversations", {"count": 20})  # type: ignore[attr-defined]
    payload = response
    if isinstance(payload, dict) and "items" not in payload and isinstance(payload.get("response"), dict):
        payload = payload["response"]
    items = payload.get("items") if isinstance(payload, dict) else None
    if not items:
        return
    cutoff = int(time.time()) - 3600
    for item in items:
        conversation = item.get("conversation") or {}
        last = item.get("last_message") or {}
        peer_id = (conversation.get("peer") or {}).get("id")
        text = last.get("text") or ""
        if not peer_id or int(last.get("out") or 0) != 1 or "Нажми кнопку начать" not in text:
            continue
        if int(last.get("date") or 0) < cutoff:
            continue
        edit: dict = {
            "peer_id": peer_id,
            "message": text,
            "keyboard": build_main_keyboard(),
        }
        if last.get("conversation_message_id"):
            edit["conversation_message_id"] = last["conversation_message_id"]
        elif last.get("id"):
            edit["message_id"] = last["id"]
        else:
            continue
        try:
            await api.messages.edit(**edit)  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            print(
                f"Не добавил кнопку group={bot_key} peer={peer_id}: {type(exc).__name__}: {exc}",
                flush=True,
            )
            continue
        print(f"Добавил кнопку Начать group={bot_key} peer={peer_id}", flush=True)


async def connect_with_partner(peer: Peer, vk_message: Message | None) -> None:
    """Ставит пользователя в поиск и соединяет с другим живым человеком, если он уже ждёт."""
    previous = stop_chat(peer)
    generation = begin_search(peer)
    await _reply(peer, SEARCHING_TEXT, "chat", vk_message)
    if previous is not None:
        await _notify_left(previous)
    paired = pair_searcher(peer, generation)
    if paired is None:
        return
    partner, created = paired
    if not created:
        return
    await _reply(peer, FOUND_TEXT, "chat", vk_message)
    await gateway.send(partner, FOUND_TEXT, "chat")
