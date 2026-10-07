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
        attachment = await _upload(message, path)
    except Exception as exc:
        print(f"Не удалось загрузить картинку {path.name}: {type(exc).__name__}: {exc}")
        return None
    _attachments[str(path)] = attachment
    return attachment


def _save_payload(uploaded: dict) -> dict:
    """Старый upload.php отдаёт photo, новый bulk_upload — sha и secret."""
    photo = uploaded.get("photo")
    if photo:
        return {
            "photo": photo,
            "server": uploaded.get("server"),
            "hash": uploaded.get("hash"),
        }
    files = uploaded.get("files") or {}
    info = files.get("file1")
    if not isinstance(info, dict):
        info = next((item for item in files.values() if isinstance(item, dict)), None)
    if isinstance(info, dict) and info.get("sha") and info.get("secret") is not None:
        return {
            "photo": f"{info['sha']}_{info['secret']}",
            "server": uploaded.get("server"),
            "hash": uploaded.get("hash"),
        }
    raise RuntimeError(f"Сервер ВК не принял фото: {uploaded}")


async def _upload(message: Message, path: Path) -> str:
    api = message.ctx_api
    server = (
        await api.request(
            "photos.getMessagesUploadServer",
            {"peer_id": message.peer_id},
        )
    )["response"]
    upload_url = server["upload_url"]
    helper = PhotoMessageUploader(api)
    data = path.read_bytes()
    fields = ("file1", "photo") if "bulk_upload" in upload_url else ("photo", "file1")
    uploaded = None
    for field in fields:
        uploaded = await helper.upload_files(
            upload_url,
            {field: helper.get_bytes_io(data, name=path.name)},
        )
        if isinstance(uploaded, dict) and not uploaded.get("error_code") and not uploaded.get("error"):
            break
    if not isinstance(uploaded, dict):
        raise RuntimeError("Пустой ответ сервера загрузки фото")
    saved = (
        await api.request("photos.saveMessagesPhoto", _save_payload(uploaded))
    )["response"][0]
    return PhotoMessageUploader.generate_attachment_string(
        "photo",
        saved["owner_id"],
        saved["id"],
        saved.get("access_key"),
    )
