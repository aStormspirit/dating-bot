"""Тексты, подписи кнопок и клавиатуры Telegram."""

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

GREETING = (
    "👋 Привет! Это чат для анонимных знакомств, флирта и легкого общения\n"
    "Найди собеседника прямо сейчас. Нажми кнопку «Начать»"
)
START_BTN = "Начать"

CHAT_BTN_NEXT = "➡️ Следующий собеседник"
CHAT_BTN_STOP = "🛑 Закончить диалог"

SEARCHING_TEXT = "🔎 Ищем собеседника..."
NO_PARTNERS_TEXT = "Сейчас собеседников нет, приходите чуть позже 😔"
FOUND_TEXT = "💬 Собеседник найден. Вы можете писать ему сюда 👇"
STOPPED_TEXT = "Диалог остановлен. Нажми «Начать», чтобы начать снова."
PARTNER_LEFT_TEXT = "❌ Собеседник закончил диалог.\nНажми «Начать», чтобы найти нового собеседника."
UNDELIVERED_TEXT = "❌ Собеседник недоступен, диалог закончен.\nНажми «Начать», чтобы найти нового собеседника."
SERVICE_DOWN_TEXT = "Сервис временно недоступен. Попробуй через минуту."
TEXT_ONLY_TEXT = "Напиши текстом."

IDLE_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=START_BTN)]],
    resize_keyboard=True,
)
CHAT_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=CHAT_BTN_NEXT)], [KeyboardButton(text=CHAT_BTN_STOP)]],
    resize_keyboard=True,
)


def format_partner(text: str) -> str:
    """Оформляет реплику так, будто её прислал собеседник."""
    return f"👤 Собеседник:\n{text}"
