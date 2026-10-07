"""Сценарии входящих сообщений: меню, поиск и диалог."""

from __future__ import annotations

import asyncio
import json
import random

from vkbottle.bot import Message

from vk_bot.chat import (
    SEARCHING_TEXT,
    begin_search,
    complete_search,
    format_partner,
    is_chatting,
    is_searching,
    opener_pending,
    partner_reply,
    pick_opener,
    remember_visitor,
    set_partner_gender,
    stop_chat,
)
from vk_bot.premium import send_gender_premium, send_premium
from vk_bot.ui import (
    CHAT_BTN_NEXT,
    CHAT_BTN_REPORT,
    CHAT_BTN_STOP,
    GENDER_BTN_ANY,
    GENDER_BTN_FEMALE,
    GENDER_BTN_MALE,
    MENU_BTN_PARTNER_GENDER,
    MENU_BTN_PREMIUM,
    MENU_BTN_SEARCH,
    WELCOME_TEXT,
    build_chat_keyboard,
    build_main_keyboard,
    menu_message,
    menu_text,
    new_random_id,
)


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


async def handle_start(message: Message, user_id: int) -> bool:
    """Сбрасывает текущий диалог и открывает меню."""
    if not is_start_message(message):
        return False
    stop_chat(user_id)
    await message.answer(
        f"{WELCOME_TEXT}\n\n{menu_text()}",
        keyboard=build_main_keyboard(),
        random_id=random.randint(1, 2_147_483_647),
    )
    return True


async def handle_stop(message: Message, user_id: int, text: str, chatting: bool, searching: bool) -> bool:
    """Заканчивает диалог или поиск и возвращает основное меню."""
    if text != CHAT_BTN_STOP or not (chatting or searching):
        return False
    stop_chat(user_id)
    await message.answer(
        menu_message("Диалог остановлен. Нажми «Поиск», чтобы найти нового собеседника."),
        keyboard=build_main_keyboard(),
        random_id=new_random_id(),
    )
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
    """Запускает поиск по кнопкам «Поиск» и «Следующий собеседник»."""
    if text not in {MENU_BTN_SEARCH, CHAT_BTN_NEXT}:
        return False
    if is_searching(user_id):
        return True
    await connect_with_partner(message, user_id)
    return True


async def handle_chat_line(message: Message, user_id: int, text: str, chatting: bool) -> bool:
    """Передаёт текст пользователя собеседнику и присылает его ответ."""
    if not chatting:
        return False
    if not text:
        await message.answer(
            format_partner("напиши текстом)"),
            keyboard=build_chat_keyboard(),
            random_id=new_random_id(),
        )
        return True
    await message.answer(
        format_partner(await partner_reply(user_id, text)),
        keyboard=build_chat_keyboard(),
        random_id=new_random_id(),
    )
    return True


async def handle_partner_gender(message: Message, user_id: int, text: str, busy: bool) -> bool:
    """Даёт выбрать, в какой роли выйдет следующий собеседник."""
    if busy:
        return False
    if text == MENU_BTN_PARTNER_GENDER:
        await send_gender_premium(message)
        return True

    choice = {
        GENDER_BTN_FEMALE: True,
        GENDER_BTN_MALE: False,
        GENDER_BTN_ANY: None,
    }
    if text not in choice:
        return False
    set_partner_gender(user_id, choice[text])
    if choice[text] is True:
        note = "В следующем поиске это будет девушка."
    elif choice[text] is False:
        note = "В следующем поиске это будет парень."
    else:
        note = "В следующем поиске пол снова случайный."
    await message.answer(
        menu_message(note),
        keyboard=build_main_keyboard(),
        random_id=new_random_id(),
    )
    return True


async def handle_premium(message: Message, text: str) -> bool:
    """По кнопке «Премиум доступ» присылает карточку акции и ссылку на оплату."""
    if text != MENU_BTN_PREMIUM:
        return False
    await send_premium(message)
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
    if await handle_partner_gender(message, user_id, text, busy=chatting or searching):
        return
    if await handle_premium(message, text):
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
    """Показывает поиск и соединяет пользователя с собеседником-ботом."""
    generation = begin_search(user_id)
    await message.answer(
        SEARCHING_TEXT,
        keyboard=build_chat_keyboard(),
        random_id=new_random_id(),
    )
    await asyncio.sleep(random.uniform(1.4, 2.2))

    found = complete_search(user_id, generation)
    if found is None:
        return

    await message.answer(
        found,
        keyboard=build_chat_keyboard(),
        random_id=new_random_id(),
    )
    await asyncio.sleep(random.uniform(0.8, 1.4))
    if not opener_pending(user_id, generation):
        return

    await message.answer(
        format_partner(pick_opener(user_id)),
        keyboard=build_chat_keyboard(),
        random_id=new_random_id(),
    )
