"""Сообщение премиума: карточка акции, текст и кнопка оплаты."""

from vkbottle.bot import Message

from vk_bot.config import PREMIUM_IMAGE, PREMIUM_URL
from vk_bot.photos import upload_photo
from vk_bot.ui import (
    build_premium_keyboard,
    gender_premium_message,
    new_random_id,
    premium_message,
)


async def _first_name(message: Message) -> str:
    """Имя пользователя из профиля ВК. Пустая строка, если профиль недоступен."""
    try:
        users = await message.ctx_api.users.get(user_ids=[message.from_id])
    except Exception:
        return ""
    if not users:
        return ""
    return (users[0].first_name or "").strip()


async def send_premium(message: Message) -> None:
    """Отправляет текст премиума, карточку и кнопку со ссылкой на оплату."""
    name = await _first_name(message)
    await message.answer(
        premium_message(name),
        attachment=await upload_photo(message, PREMIUM_IMAGE),
        keyboard=build_premium_keyboard(PREMIUM_URL),
        random_id=new_random_id(),
    )


async def send_gender_premium(message: Message) -> None:
    """Объясняет, что фильтр по полу открывается после оплаты."""
    await message.answer(
        gender_premium_message(await _first_name(message)),
        attachment=await upload_photo(message, PREMIUM_IMAGE),
        keyboard=build_premium_keyboard(PREMIUM_URL),
        random_id=new_random_id(),
    )
