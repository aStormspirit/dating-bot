"""Точка входа: несколько ботов ВК и Telegram в одной очереди поиска."""

import asyncio
import sys

from dotenv import load_dotenv

load_dotenv()

from vkbottle.bot import Bot

from vk_bot.chat import adopt_legacy_vk
from vk_bot.config import tg_tokens, vk_tokens
from vk_bot.gateway import gateway
from vk_bot.handlers import vk_handler
from vk_bot.startup import preflight_check, rebuild_vkbottle_response_models


async def _run() -> None:
    """Проверяет токены и принимает сообщения всех подключённых ботов."""
    tokens = vk_tokens()
    telegram = tg_tokens()
    if not tokens and not telegram:
        raise SystemExit(
            "Нужен хотя бы один токен. Укажите VK_TOKEN или VK_TOKENS и, если нужно, TG_TOKENS."
        )

    rebuild_vkbottle_response_models()
    runners = []
    first_group: str | None = None
    for token in tokens:
        group_id = preflight_check(token)
        bot_key = str(group_id)
        if first_group is None:
            first_group = bot_key
        bot = Bot(token=token)
        gateway.add_vk(bot_key, bot.api)
        bot.on.message()(vk_handler(bot_key))
        runners.append(bot.run_polling())
        print(f"VK: доступ к Long Poll есть (group_id={group_id})")

    if first_group is not None:
        adopt_legacy_vk(first_group)
    if telegram:
        try:
            from vk_bot.telegram_bot import telegram_runners

            runners.extend(await telegram_runners(telegram, gateway))
        except Exception as exc:  # noqa: BLE001 — ВК должен работать, даже если Telegram недоступен
            print(f"Telegram не запущен: {type(exc).__name__}: {exc}", file=sys.stderr)

    print("Сессии диалогов хранятся в Supabase Postgres.")
    print("Анонимный чат: сообщения пересылаются живому собеседнику.")
    print("Бот запущен. Ожидание сообщений...")
    await asyncio.gather(*runners)


def main() -> None:
    """Запускает общий цикл всех ботов."""
    try:
        asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001
        print(f"Ошибка запуска: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
