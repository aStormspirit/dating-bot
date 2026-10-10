"""Точка входа: у каждого сообщества свой Bot и своя задача Long Poll."""

import asyncio
import sys

from dotenv import load_dotenv

load_dotenv()

from vkbottle.bot import Bot
from vkbottle.http.aiohttp import AiohttpClient

from vk_bot.chat import adopt_legacy_vk
from vk_bot.config import tg_tokens, vk_tokens
from vk_bot.gateway import gateway
from vk_bot.handlers import answer_waiting, vk_handler
from vk_bot.longpoll import VersionedBotPolling
from vk_bot.startup import preflight_check, rebuild_vkbottle_response_models


def community_bot(token: str) -> Bot:
    """Отдельный Bot со своим токеном и своим HTTP-клиентом.

    Общий клиент vkbottle один на процесс. Три Long Poll на нём не отдают события.
    """
    bot = Bot(token)
    bot.api.http_client = AiohttpClient()
    bot._polling = VersionedBotPolling(  # noqa: SLF001 — своего конструктора для polling нет
        bot.api,
        error_handler=bot.error_handler,
        skip_old_events=bot.skip_old_events,
    )
    return bot


def _log_task_end(task: asyncio.Task) -> None:
    """Печатает падение задачи. Исключения vkbottle иначе остаются в loguru."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        print(f"Задача {task.get_name()} упала: {type(exc).__name__}: {exc}", flush=True)


async def _listen(bot: Bot, group_id: str) -> None:
    """Одна задача: сначала закрывает ожидающие диалоги, потом слушает Long Poll."""
    print(f"Слушаю сообщения group_id={group_id}", flush=True)
    try:
        await answer_waiting(bot.api, group_id)
    except Exception as exc:  # noqa: BLE001 — сбой догонки не должен останавливать приём
        print(
            f"Не ответил на ожидающие group_id={group_id}: {type(exc).__name__}: {exc}",
            flush=True,
        )
    await bot.run_polling()


async def _run() -> None:
    """Проверяет токены и поднимает отдельную задачу на каждое сообщество и Telegram."""
    tokens = vk_tokens()
    telegram = tg_tokens()
    if not tokens and not telegram:
        raise SystemExit(
            "Нужен хотя бы один токен. Укажите VK_TOKEN или VK_TOKENS и, если нужно, TG_TOKENS."
        )

    rebuild_vkbottle_response_models()
    tasks: list[asyncio.Task] = []
    first_group: str | None = None
    print(f"Токенов ВК: {len(tokens)}. Токенов Telegram: {len(telegram)}.")
    for token in tokens:
        try:
            group_id = preflight_check(token)
        except SystemExit as exc:
            print(f"Токен сообщества ВК пропущен: {exc}", file=sys.stderr)
            continue
        bot_key = str(group_id)
        if first_group is None:
            first_group = bot_key
        bot = community_bot(token)
        gateway.add_vk(bot_key, bot.api)
        bot.on.message()(vk_handler(bot_key))
        task = asyncio.create_task(_listen(bot, bot_key), name=f"vk-{bot_key}")
        task.add_done_callback(_log_task_end)
        tasks.append(task)
        print(f"VK: доступ к Long Poll есть (group_id={group_id})")
    if tokens and not tasks:
        raise SystemExit("Ни одно сообщество ВК не прошло проверку Long Poll.")

    if first_group is not None:
        adopt_legacy_vk(first_group)
    if telegram:
        try:
            from vk_bot.telegram_bot import telegram_runners

            for runner in await telegram_runners(telegram, gateway):
                task = asyncio.create_task(runner, name="telegram")
                task.add_done_callback(_log_task_end)
                tasks.append(task)
        except Exception as exc:  # noqa: BLE001 — ВК должен работать, даже если Telegram недоступен
            print(f"Telegram не запущен: {type(exc).__name__}: {exc}", file=sys.stderr)

    if not tasks:
        raise SystemExit("Нет запущенных ботов.")

    print("Сессии диалогов хранятся в Supabase Postgres.")
    print("Анонимный чат: сообщения пересылаются живому собеседнику.")
    print("Бот запущен. Ожидание сообщений...")
    results = await asyncio.gather(*tasks, return_exceptions=True)
    errors = [result for result in results if isinstance(result, BaseException)]
    if errors and len(errors) == len(results):
        raise errors[0]


def main() -> None:
    """Запускает общий цикл всех ботов."""
    try:
        asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001
        print(f"Ошибка запуска: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
