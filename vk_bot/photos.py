"""Загрузка картинок в сообщения ВК. Вложение кэшируется на процесс."""

from pathlib import Path

from vkbottle import PhotoMessageUploader
from vkbottle.bot import Message

_attachments: dict[str, str] = {}


async def upload_photo(message: Message, path: Path) -> str | None:
    """Возвращает photo{owner}_{id}. Повторно файл в ВК не загружается."""
    cached = _attachments.get(str(path))
    if cached:
        return cached
    if not path.is_file():
        print(f"Нет картинки: {path}")
        return None
    try:
        uploaded = await PhotoMessageUploader(message.ctx_api).upload(
            str(path),
            peer_id=message.peer_id,
        )
    except Exception as exc:
        print(f"Не удалось загрузить картинку {path.name}: {exc}")
        return None
    _attachments[str(path)] = uploaded
    return uploaded
