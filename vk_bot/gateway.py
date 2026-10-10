"""Доставка текста в тот бот ВК или Telegram, которому пишет человек."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from vk_bot.peer import Peer
from vk_bot.ui import (
    CHAT_BTN_NEXT,
    CHAT_BTN_REPORT,
    CHAT_BTN_STOP,
    START_BTN,
    build_chat_keyboard,
    build_main_keyboard,
    new_random_id,
)


def _vk_keyboard(kind: str) -> str:
    """Клавиатура ВК: меню или кнопки диалога."""
    if kind == "chat":
        return build_chat_keyboard()
    return build_main_keyboard()


def _tg_keyboard(kind: str):
    """Обычная клавиатура Telegram с теми же подписями, что и во ВК."""
    from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

    if kind == "chat":
        rows = [
            [KeyboardButton(text=CHAT_BTN_NEXT)],
            [KeyboardButton(text=CHAT_BTN_STOP)],
            [KeyboardButton(text=CHAT_BTN_REPORT)],
        ]
    else:
        rows = [[KeyboardButton(text=START_BTN)]]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


class Gateway:
    """Знает API каждого подключённого бота и шлёт ответ через него."""

    def __init__(self) -> None:
        self._vk: dict[str, Any] = {}
        self._tg: dict[str, Any] = {}

    def add_vk(self, bot_key: str, api: Any) -> None:
        """Регистрирует API сообщества ВК. Ключ — id сообщества."""
        self._vk[bot_key] = api

    def add_tg(self, bot_key: str, bot: Any) -> None:
        """Регистрирует бота Telegram. Ключ — числовой id бота."""
        self._tg[bot_key] = bot

    async def send(self, peer: Peer, text: str, kind: str, *, photo: Path | None = None) -> bool:
        """Отправляет текст и клавиатуру. False, если мессенджер не принял сообщение."""
        try:
            if peer.platform == "vk":
                await self._send_vk(peer, text, kind)
                return True
            await self._send_tg(peer, text, kind, photo)
            return True
        except Exception as exc:  # noqa: BLE001 — сбой доставки не должен ронять общий обработчик
            print(
                f"Не удалось написать {peer.platform}:{peer.bot_key}:{peer.user_id}: "
                f"{type(exc).__name__}: {exc}"
            )
            return False

    async def _send_vk(self, peer: Peer, text: str, kind: str) -> None:
        api = self._vk.get(peer.bot_key)
        if api is None:
            raise RuntimeError(f"Нет сообщества ВК {peer.bot_key}")
        await api.messages.send(
            peer_id=peer.user_id,
            message=text,
            keyboard=_vk_keyboard(kind),
            random_id=new_random_id(),
        )

    async def _send_tg(self, peer: Peer, text: str, kind: str, photo: Path | None) -> None:
        bot = self._tg.get(peer.bot_key)
        if bot is None:
            raise RuntimeError(f"Нет бота Telegram {peer.bot_key}")
        markup = _tg_keyboard(kind)
        if photo is not None and photo.is_file():
            from aiogram.types import FSInputFile

            await bot.send_photo(
                peer.user_id,
                FSInputFile(photo),
                caption=text,
                reply_markup=markup,
            )
            return
        await bot.send_message(peer.user_id, text, reply_markup=markup)


gateway = Gateway()
