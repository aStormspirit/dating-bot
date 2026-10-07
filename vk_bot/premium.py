"""Сообщение премиума: карточка акции, текст и кнопка оплаты."""

from vkbottle import PhotoMessageUploader
from vkbottle.bot import Message

from vk_bot.config import PREMIUM_IMAGE, PREMIUM_URL
from vk_bot.ui import (
    build_premium_keyboard,
    gender_premium_message,
    new_random_id,
    premium_message,
)

_attachment: str | None = None


async def _first_name(message: Message) -> str:
    """Имя пользователя из профиля ВК. Пустая строка, если профиль недоступен."""
    try:
        users = await message.ctx_api.users.get(user_ids=[message.from_id])
    except Exception:
        return ""
    if not users:
        return ""
    return (users[0].first_name or "").strip()


async def _premium_photo(message: Message) -> str | None:
    """Загружает карточку в сообщения ВК один раз и переиспользует вложение."""
    global _attachment
    if _attachment:
        return _attachment
    if not PREMIUM_IMAGE.is_file():
        print(f"Нет картинки премиума: {PREMIUM_IMAGE}")
        return None
    try:
        uploaded = await PhotoMessageUploader(message.ctx_api).upload(
            str(PREMIUM_IMAGE),
            peer_id=message.peer_id,
        )
    except Exception as exc:
        print(f"Не удалось загрузить картинку премиума: {exc}")
        return None
    _attachment = uploaded
    return uploaded


async def send_premium(message: Message) -> None:
    """Отправляет текст премиума, карточку и кнопку со ссылкой на оплату."""
    name = await _first_name(message)
    await message.answer(
        premium_message(name),
        attachment=await _premium_photo(message),
        keyboard=build_premium_keyboard(PREMIUM_URL),
        random_id=new_random_id(),
    )


async def send_gender_premium(message: Message) -> None:
    """Объясняет, что фильтр по полу открывается после оплаты."""
    await message.answer(
        gender_premium_message(await _first_name(message)),
        keyboard=build_premium_keyboard(PREMIUM_URL),
        random_id=new_random_id(),
    )
