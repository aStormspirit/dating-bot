"""Приём личных сообщений нескольких ботов Telegram в общую очередь поиска."""

from __future__ import annotations

from collections.abc import Awaitable

from aiogram import Bot, Dispatcher
from aiogram.types import Message

from vk_bot.gateway import Gateway
from vk_bot.handlers import handle_incoming
from vk_bot.peer import Peer


async def telegram_runners(tokens: list[str], gateway: Gateway) -> list[Awaitable[None]]:
    """Поднимает long polling для каждого токена. Групповые чаты не принимает."""
    runners: list[Awaitable[None]] = []
    for token in tokens:
        bot = Bot(token=token)
        me = await bot.get_me()
        bot_key = str(me.id)
        gateway.add_tg(bot_key, bot)
        dispatcher = Dispatcher()

        async def on_message(message: Message, current_key: str = bot_key) -> None:
            if message.from_user is None or message.chat.type != "private":
                return
            text = (message.text or message.caption or "").strip()
            await handle_incoming(Peer("tg", current_key, message.from_user.id), text, {})

        dispatcher.message.register(on_message)
        runners.append(dispatcher.start_polling(bot))
        print(f"Telegram: @{me.username} (id={bot_key})")
    return runners
