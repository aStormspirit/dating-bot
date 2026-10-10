"""Сценарии входящих сообщений: меню, поиск и диалог."""

from __future__ import annotations

import json

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


def is_start_message(message: Message) -> bool:
    """Сообщение «Начать», /start или команда start из payload."""
    text = (message.text or "").strip().lower()
    if text in ("начать", "/start", "start"):
        return True
    return parse_payload(message).get("command") == "start"


async def _tell(message: Message, user_id: int, text: str, keyboard: str) -> bool:
    """Отправляет текст другому пользователю. False, если ВК не принял сообщение."""
    try:
        await message.ctx_api.messages.send(
            peer_id=user_id,
            message=text,
            keyboard=keyboard,
            random_id=new_random_id(),
        )
    except Exception as exc:  # noqa: BLE001 — сбой доставки не должен ронять общий обработчик
        print(f"Не удалось написать {user_id}: {type(exc).__name__}: {exc}")
        return False
    return True


async def _notify_left(message: Message, partner_id: int) -> None:
    """Сообщает второй стороне, что диалог закончился."""
    await _tell(message, partner_id, menu_message(_PARTNER_LEFT), build_main_keyboard())


async def handle_start(message: Message, user_id: int) -> bool:
    """Сбрасывает текущий диалог и открывает меню."""
    if not is_start_message(message):
        return False
    partner_id = stop_chat(user_id)
    await message.answer(
        f"{WELCOME_TEXT}\n\n{menu_text()}",
        attachment=await upload_photo(message, WELCOME_IMAGE),
        keyboard=build_main_keyboard(),
        random_id=new_random_id(),
    )
    if partner_id is not None:
        await _notify_left(message, partner_id)
    return True


async def handle_stop(message: Message, user_id: int, text: str, chatting: bool, searching: bool) -> bool:
    """Заканчивает диалог или поиск и возвращает основное меню."""
    if text != CHAT_BTN_STOP or not (chatting or searching):
        return False
    partner_id = stop_chat(user_id)
    await message.answer(
        menu_message("Диалог остановлен. Нажми «Найти собеседника», чтобы начать снова."),
        keyboard=build_main_keyboard(),
        random_id=new_random_id(),
    )
    if partner_id is not None:
        await _notify_left(message, partner_id)
    return True


async def handle_report(message: Message, user_id: int, text: str, chatting: bool) -> bool:
    """Принимает жалобу в активном диалоге и сразу ищет другого собеседника."""
    if text != CHAT_BTN_REPORT or not chatting:
        return False
    stop_chat(user_id)
    await message.answer(
        menu_message("Жалоба отправлена. Ищем другого собеседника."),
        keyboard=build_chat_keyboard(),
        random_id=new_random_id(),
    )
    await connect_with_partner(message, user_id)
    return True


async def handle_search(message: Message, user_id: int, text: str) -> bool:
    """Запускает поиск по кнопке «Найти собеседника» или «Следующий собеседник»."""
    if text not in _SEARCH_BUTTONS:
        return False
    if is_searching(user_id):
        return True
    await connect_with_partner(message, user_id)
    return True


async def handle_chat_line(message: Message, user_id: int, text: str, chatting: bool) -> bool:
    """Пересылает текст живому собеседнику."""
    if not chatting:
        return False
    if not text:
        await message.answer(
            "Напиши текстом.",
            keyboard=build_chat_keyboard(),
            random_id=new_random_id(),
        )
        return True
    partner_id = partner_of(user_id)
    if partner_id is None:
        stop_chat(user_id)
        await message.answer(
            menu_message(_PARTNER_LEFT),
            keyboard=build_main_keyboard(),
            random_id=new_random_id(),
        )
        return True
    delivered = await _tell(message, partner_id, format_partner(text), build_chat_keyboard())
    if delivered:
        return True
    stop_chat(user_id)
    await message.answer(
        menu_message("Не удалось доставить сообщение. Диалог остановлен."),
        keyboard=build_main_keyboard(),
        random_id=new_random_id(),
    )
    return True


async def handle_menu_or_dialog(message: Message, user_id: int) -> None:
    """Разбирает меню и реплики диалога."""
    text = (message.text or "").strip()
    chatting = is_chatting(user_id)
    searching = is_searching(user_id)

    if await handle_stop(message, user_id, text, chatting, searching):
        return
    if await handle_report(message, user_id, text, chatting):
        return
    if await handle_search(message, user_id, text):
        return
    if await handle_chat_line(message, user_id, text, chatting):
        return
    if searching:
        return

    await message.answer(
        menu_message(),
        keyboard=build_main_keyboard(),
        random_id=new_random_id(),
    )


async def handle_message(message: Message) -> None:
    """Маршрутизирует сообщение: старт, затем меню или диалог."""
    user_id = message.from_id
    remember_visitor(user_id)
    if await handle_start(message, user_id):
        return
    await handle_menu_or_dialog(message, user_id)


async def connect_with_partner(message: Message, user_id: int) -> None:
    """Ставит пользователя в поиск и соединяет с другим живым человеком, если он уже ждёт."""
    previous = stop_chat(user_id)
    generation = begin_search(user_id)
    await message.answer(
        SEARCHING_TEXT,
        keyboard=build_chat_keyboard(),
        random_id=new_random_id(),
    )
    if previous is not None:
        await _notify_left(message, previous)
    paired = pair_searcher(user_id, generation)
    if paired is None:
        return
    partner_id, created = paired
    if not created:
        return
    await message.answer(
        FOUND_TEXT,
        keyboard=build_chat_keyboard(),
        random_id=new_random_id(),
    )
    await _tell(message, partner_id, FOUND_TEXT, build_chat_keyboard())
