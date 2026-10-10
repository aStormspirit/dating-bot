"""Первые реплики собеседника. Новые фразы добавляются в OPENERS."""

from __future__ import annotations

import random

from vk_bot.chat.session import _remember, _session

OPENERS = (
    "Пр",
    "привет)",
    "М?",
    "хай) как тебя сюда занесло?",
    "о, живой человек) чем занимаешься?",
    "привет. скучно, может займемся чем то?",
    "ты откуда?",
    "привет) ищешь общение или так, на пять минут?",
    "ну привет)",
    "хай) ты мне уже нравишься, напиши что-нибудь",
    "привет) какое у тебя настроение сейчас?",
    "о, наконец-то кто-то ответил) ты как?",
    "привет. давай сразу честно: зачем ты здесь?",
    "хай) мне скучно, развлеки меня немного",
    "привет. ты обычно долго молчишь или сразу пишешь?",
)

_last_opener: dict[int, str] = {}


def pick_opener(user_id: int) -> str:
    """Возвращает случайную первую реплику, отличную от прошлой у этого пользователя."""
    previous = _last_opener.get(user_id)
    pool = [line for line in OPENERS if line != previous] or list(OPENERS)
    choice = random.choice(pool)
    _last_opener[user_id] = choice
    return _remember(_session(user_id), choice)
