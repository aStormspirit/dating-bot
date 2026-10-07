"""Точка входа: загрузка окружения, проверка Long Poll и запуск бота."""

import sys

from dotenv import load_dotenv

load_dotenv()

from vkbottle.bot import Bot

from vk_bot.config import ABLIT_API_KEY, TOKEN
from vk_bot.handlers import handle_message
from vk_bot.startup import preflight_check, rebuild_vkbottle_response_models


def main() -> None:
    """Проверяет токен и доступ к Long Poll, затем принимает сообщения."""
    if not TOKEN:
        raise SystemExit(
            "Не задан VK_TOKEN. Скопируйте .env.example в .env и укажите токен группы."
        )

    group_id = preflight_check(TOKEN)
    rebuild_vkbottle_response_models()
    bot = Bot(token=TOKEN)
    bot.on.message()(handle_message)

    print(f"OK: доступ к Long Poll есть (group_id={group_id})")
    print("Сессии диалогов хранятся в Supabase Postgres.")
    if ABLIT_API_KEY:
        print("ИИ-собеседник включён: после опенера отвечает Abliteration.")
    else:
        print("ABLIT_KEY не задан: после опенера бот ответит заготовками, без ИИ.")
    print("Бот запущен. Ожидание сообщений...")
    try:
        bot.run()
    except Exception as exc:  # noqa: BLE001
        print(f"Ошибка запуска: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
