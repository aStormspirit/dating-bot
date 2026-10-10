"""Сценарии входящих сообщений: меню, поиск и диалог."""

from __future__ import annotations

import json
from pathlib import Path

from vkbottle.bot import Message

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
from vk_bot.config import WELCOME_IMAGE
from vk_bot.gateway import gateway
from vk_bot.peer import Peer
from vk_bot.photos import upload_photo
from vk_bot.ui import (
    CHAT_BTN_NEXT,
    CHAT_BTN_REPORT,
    CHAT_BTN_STOP,
    MENU_BTN_SEARCH,
    WELCOME_TEXT,
    build_chat_keyboard,
    build_main_keyboard,
    menu_message,
    menu_text,
    new_random_id,
)

_SEARCH_BUTTONS = {MENU_BTN_SEARCH, "🔍 Поиск", CHAT_BTN_NEXT}
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
        kwargs: dict = {"keyboard": _vk_keyboard(kind), "random_id": new_random_id()}
        if photo is not None:
            kwargs["attachment"] = await upload_photo(vk_message, photo)
        await vk_message.answer(text, **kwargs)
        return True
    return await gateway.send(peer, text, kind, photo=photo)


async def _notify_left(partner: Peer) -> None:
    """Сообщает второй стороне, что диалог закончился."""
    await gateway.send(partner, menu_message(_PARTNER_LEFT), "main")


async def handle_start(peer: Peer, text: str, payload: dict, vk_message: Message | None) -> bool:
    """Сбрасывает текущий диалог и открывает меню."""
    if not _is_start(text, payload):
        return False
    partner = stop_chat(peer)
    await _reply(peer, f"{WELCOME_TEXT}\n\n{menu_text()}", "main", vk_message, photo=WELCOME_IMAGE)
    if partner is not None:
        await _notify_left(partner)
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
    if searching:
        return

    await _reply(peer, menu_message(), "main", vk_message)


async def handle_incoming(
    peer: Peer,
    text: str,
    payload: dict,
    vk_message: Message | None = None,
) -> None:
    """Маршрутизирует сообщение из ВК или Telegram: старт, затем меню или диалог."""
    remember_visitor(peer)
    if await handle_start(peer, text, payload, vk_message):
        return
    await handle_menu_or_dialog(peer, text, vk_message)


def vk_handler(bot_key: str):
    """Обработчик одного сообщества ВК. Ключ нужен, чтобы ответ ушёл тем же токеном."""

    async def _handle(message: Message) -> None:
        await handle_incoming(
            Peer("vk", bot_key, message.from_id),
            (message.text or "").strip(),
            parse_payload(message),
            message,
        )

    return _handle


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
