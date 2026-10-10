"""Тексты, подписи кнопок и клавиатуры сообщений."""

import random

from vkbottle import Keyboard, KeyboardButtonColor, OpenLink, Text

MENU_TEXT = "Найди собеседника прямо сейчас"
COMMUNITY_GREETING = (
    "👋 Привет! Это чат для анонимных знакомств, флирта и легкого общения\n"
    "Найди собеседника прямо сейчас. Нажми кнопку начать"
)
START_BTN = "Начать"


def menu_text() -> str:
    """Короткий текст меню без счётчика людей онлайн."""
    return MENU_TEXT
WELCOME_TEXT = "Привет! 👋 Это чат для анонимных знакомств, флирта и лёгкого общения."

MENU_BTN_SEARCH = "🔍 Найти собеседника"

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
    if not cleaned or cleaned.startswith(header):
        return header if not cleaned else cleaned
    return f"{header}\n\n{cleaned}"


def build_main_keyboard() -> str:
    """Клавиатура чата сообщества: кнопка «Начать»."""
    keyboard = Keyboard(one_time=False, inline=False).add(
        Text(START_BTN),
        color=KeyboardButtonColor.POSITIVE,
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


_PREMIUM_PERKS = (
    "🍓 Девушки твоего возраста — с первого собеседника\n"
    "💋 Комнаты флирта и знакомств\n"
    "📹 Фото, видео, голосовые без лимитов\n"
    "🔝 Ты — первый в поиске"
)


def premium_message(name: str) -> str:
    """Текст кнопки «Премиум доступ». Имя берётся из профиля ВК."""
    waiting = random.randint(500, 1500)
    who = name.strip()
    if who:
        lead = f"{who}, {waiting} девушек уже ждут тебя. Успеешь к ним😏"
    else:
        lead = f"{waiting} девушек уже ждут тебя. Успеешь к ним😏"
    return (
        f"{lead}\n\n"
        f"{_PREMIUM_PERKS}\n"
        "⚡ Полный доступ включается за 10 секунд.\n"
        "💳 Карты всех банков, кроме Т-банка, Озон банка и Альфа-банка."
    )


def gender_premium_message(name: str) -> str:
    """Текст кнопки «Выбрать пол партнера». Фильтр закрыт премиумом."""
    who = name.strip()
    if who:
        pitch = (
            f"{who}, выбирай сам с кем общаться и на какие темы. "
            "Выбор пола собеседника доступен только с премиумом 😏"
        )
    else:
        pitch = (
            "Выбирай сам с кем общаться и на какие темы. "
            "Выбор пола собеседника доступен только с премиумом 😏"
        )
    return (
        "👑 Для использования фильтра по полу нужен Премиум\n\n"
        f"{pitch}\n\n"
        f"{_PREMIUM_PERKS}\n\n"
        "⚡ Полный доступ включается за 10 секунд."
    )


def _tariff_url(base: str, plan_id: str) -> str:
    """Добавляет к ссылке оплаты идентификатор тарифа."""
    separator = "&" if "?" in base else "?"
    return f"{base}{separator}plan={plan_id}"


# plan_id, подпись кнопки, дни, цена. Сайт оплаты читает plan и берёт цену у себя.
_TARIFFS = (
    ("trial", "👑 3 дня VIP за 1 ₽", 3, 1),
    ("start", "Старт · 3 дня · 399 ₽", 3, 399),
    ("optimal", "Оптимальный · 30 дней · 990 ₽", 30, 990),
    ("year", "365 дней · 2026 ₽", 365, 2026),
)


def build_premium_keyboard(url: str) -> str:
    """Кнопки тарифов под сообщением. Каждая открывает оплату своего плана."""
    keyboard = Keyboard(inline=True)
    for index, (plan_id, label, *_rest) in enumerate(_TARIFFS):
        if index:
            keyboard.row()
        keyboard.add(OpenLink(_tariff_url(url, plan_id), label))
    return keyboard.get_json()
