"""Тексты, подписи кнопок и клавиатуры сообщений."""

import json
import random

from vkbottle import Callback, Keyboard, KeyboardButtonColor, Text

MENU_TEXT = "Найди собеседника прямо сейчас"
COMMUNITY_GREETING = (
    "👋 Привет! Это чат для анонимных знакомств, флирта и легкого общения\n"
    "Найди собеседника прямо сейчас. Нажми кнопку начать"
)
START_BTN = "Начать"

CHAT_BTN_NEXT = "➡️ Следующий собеседник"
CHAT_BTN_STOP = "🛑 Закончить диалог"

SEARCHING_TEXT = "🔎 Ищем собеседника..."
NO_PARTNERS_TEXT = "Сейчас собеседников нет, приходите чуть позже 😔"
FOUND_TEXT = "💬 Собеседник найден. Вы можете писать ему сюда 👇"
STOPPED_TEXT = f"{MENU_TEXT}\n\nДиалог остановлен. Нажми «Начать», чтобы начать снова."
PARTNER_LEFT_TEXT = "Собеседник завершил диалог. Нажми «Найти собеседника», чтобы найти нового."
UNDELIVERED_TEXT = "❌ Собеседник недоступен, диалог закончен.\nНажми «Начать», чтобы найти нового собеседника."
SERVICE_DOWN_TEXT = "Сервис временно недоступен. Попробуй через минуту."


def format_partner(text: str) -> str:
    """Оформляет реплику так, будто её прислал собеседник."""
    return f"👤 Собеседник:\n{text}"


def new_random_id() -> int:
    """Случайный идентификатор messages.send, чтобы VK не склеивал ответы."""
    return random.randint(1, 2_147_483_647)


def build_main_keyboard() -> str:
    """Кнопка «Начать» под текстом. В беседе обычная клавиатура не показывается."""
    keyboard = Keyboard(inline=True).add(
        Callback(START_BTN, payload=json.dumps({"command": "start"})),
        color=KeyboardButtonColor.POSITIVE,
    )
    return keyboard.get_json()


def build_idle_keyboard() -> str:
    """Постоянная клавиатура лички вне диалога: заменяет кнопки диалога одной «Начать»."""
    keyboard = Keyboard(one_time=False, inline=False).add(
        Text(START_BTN, payload={"command": "start"}),
        color=KeyboardButtonColor.POSITIVE,
    )
    return keyboard.get_json()


def build_chat_keyboard() -> str:
    """Клавиатура активного диалога: две кнопки друг под другом."""
    keyboard = (
        Keyboard(one_time=False, inline=False)
        .add(Text(CHAT_BTN_NEXT), color=KeyboardButtonColor.SECONDARY)
        .row()
        .add(Text(CHAT_BTN_STOP), color=KeyboardButtonColor.SECONDARY)
    )
    return keyboard.get_json()
