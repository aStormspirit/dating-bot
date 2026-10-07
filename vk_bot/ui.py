"""Тексты, подписи кнопок и клавиатуры сообщений."""

import random

from vkbottle import Keyboard, KeyboardButtonColor, OpenLink, Text

_MENU_HEAD = "😋 Вместе с вами общаются 🟢"
_MENU_TAIL = "👇 Выберите действие в меню: 👇"


def menu_text() -> str:
    """Текст меню с новым числом онлайн при каждом показе."""
    online = random.randint(3000, 3500)
    return f"{_MENU_HEAD}{online} человек\n{_MENU_TAIL}"
WELCOME_TEXT = "Привет! 👋 Это чат для анонимных знакомств, флирта и лёгкого общения."

MENU_BTN_SEARCH = "🔍 Поиск"
MENU_BTN_PARTNER_GENDER = "Выбрать пол партнера"
MENU_BTN_PREMIUM = "Премиум доступ"

GENDER_BTN_FEMALE = "👩 Девушка"
GENDER_BTN_MALE = "👨 Парень"
GENDER_BTN_ANY = "🎲 Любой"

CHAT_BTN_NEXT = "➡️ Следующий собеседник"
CHAT_BTN_REPORT = "🛑⚠️ Пожаловаться на спам"
CHAT_BTN_STOP = "🛑 Закончить диалог"


def new_random_id() -> int:
    """Случайный идентификатор messages.send, чтобы VK не склеивал ответы."""
    return random.randint(1, 2_147_483_647)


def menu_message(text: str = "") -> str:
    """Для уже знакомого пользователя ответ начинается с текста меню."""
    cleaned = text.strip()
    header = menu_text()
    if not cleaned or cleaned.startswith(_MENU_HEAD):
        return header if not cleaned else cleaned
    return f"{header}\n\n{cleaned}"


def build_main_keyboard() -> str:
    """Клавиатура у поля ввода: [Поиск] [Пол партнера] / [Премиум]."""
    keyboard = (
        Keyboard(one_time=False, inline=False)
        .add(Text(MENU_BTN_SEARCH), color=KeyboardButtonColor.POSITIVE)
        .add(Text(MENU_BTN_PARTNER_GENDER), color=KeyboardButtonColor.PRIMARY)
        .row()
        .add(Text(MENU_BTN_PREMIUM), color=KeyboardButtonColor.SECONDARY)
    )
    return keyboard.get_json()


def build_gender_keyboard() -> str:
    """Клавиатура выбора роли собеседника перед поиском."""
    keyboard = (
        Keyboard(one_time=False, inline=False)
        .add(Text(GENDER_BTN_FEMALE), color=KeyboardButtonColor.PRIMARY)
        .add(Text(GENDER_BTN_MALE), color=KeyboardButtonColor.PRIMARY)
        .row()
        .add(Text(GENDER_BTN_ANY), color=KeyboardButtonColor.SECONDARY)
        .row()
        .add(Text(MENU_BTN_SEARCH), color=KeyboardButtonColor.POSITIVE)
    )
    return keyboard.get_json()


def build_chat_keyboard() -> str:
    """Клавиатура активного диалога: три кнопки друг под другом."""
    keyboard = (
        Keyboard(one_time=False, inline=False)
        .add(Text(CHAT_BTN_NEXT), color=KeyboardButtonColor.SECONDARY)
        .row()
        .add(Text(CHAT_BTN_STOP), color=KeyboardButtonColor.SECONDARY)
        .row()
        .add(Text(CHAT_BTN_REPORT), color=KeyboardButtonColor.NEGATIVE)
    )
    return keyboard.get_json()


def premium_message(name: str, url: str) -> str:
    """Текст под карточкой акции. Имя подставляется из профиля ВК."""
    who = f"{name}, вы" if name else "Вы"
    return (
        f"{who} пытались оплатить Премиум, но что-то пошло не так...\n\n"
        "Попробуйте еще раз 👇\n\n"
        "⚡ Временная акция:\n"
        f"{url}\n\n"
        "Отписаться - /отписаться"
    )


def build_premium_keyboard(url: str) -> str:
    """Кнопка под сообщением открывает сайт оплаты."""
    keyboard = Keyboard(inline=True).add(OpenLink(url, "👑 3 дня VIP за 1 ₽"))
    return keyboard.get_json()
