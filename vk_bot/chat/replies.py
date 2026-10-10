"""Реплики собеседника: факты о пользователе и ответ модели."""

from __future__ import annotations

import random
import re

from vk_bot.chat.session import _Persona, _Session, _push_history, _remember, _session

_MALE_TOKENS = {"парень", "мужчина", "мужской", "male", "хлопец"}
_FEMALE_TOKENS = {"девушка", "женщина", "женский", "female", "девчонка", "девочка"}
_TOKEN_RE = re.compile(r"[a-zа-яё0-9]+", re.IGNORECASE)
_AGE_RE = re.compile(r"(?<!\d)(1[8-9]|[2-9]\d)(?!\d)")
_NAME_RE = re.compile(r"меня зовут\s+([a-zа-яё-]{2,})", re.IGNORECASE)
_CITY_RE = re.compile(r"(?:я из|живу в)\s+([a-zа-яё-]{3,})", re.IGNORECASE)
_FALLBACKS = (
    "хах) и что дальше?",
    "интересно. расскажи ещё",
    "а ты обычно так сразу пишешь незнакомцам?)",
    "мне с тобой нормально общаться) продолжай",
    "звучит заманчиво) а если серьёзно?",
    "ок, я это запомню)",
    "и как тебе такой формат, анонимно?",
    "давай без рекламы только, ок?)",
    "мм, понял(а))",
)


def _tokens(text: str) -> set[str]:
    """Режет текст на слова без знаков препинания."""
    return {token.lower() for token in _TOKEN_RE.findall(text)}


def _detect_gender(text: str) -> str | None:
    """Ищет в реплике пол пользователя: male, female или ничего."""
    tokens = _tokens(text)
    if tokens & _FEMALE_TOKENS:
        return "female"
    if tokens & _MALE_TOKENS:
        return "male"
    # «м» / «ж» — ответ на вопрос опенера, даже если в той же реплике есть имя и возраст.
    if "ж" in tokens and "м" not in tokens:
        return "female"
    if "м" in tokens and "ж" not in tokens:
        return "male"
    return None


def _detect_age(text: str) -> int | None:
    """Достаёт возраст 18–99, если он написан отдельным числом."""
    match = _AGE_RE.search(text)
    if match is None:
        return None
    return int(match.group(1))


def _about_partner(text: str, persona: _Persona) -> str | None:
    """Отвечает на вопрос о собеседнике. None, если вопрос не про него."""
    if not re.search(r"\b(ты|тебя|тебе|твой|твоя|твоё|твое)\b", text):
        return None
    if "зовут" in text or "имя" in text or "кто ты" in text:
        return f"я {persona.name}) а тебя как зовут?"
    if "лет" in text or "возраст" in text or "года" in text:
        return f"мне {persona.age}) а ты чего хочешь?"
    if any(word in text for word in ("парень", "девуш", "пол", "м или", "женщин", "мужчин")):
        return f"я {persona.gender_word}) а ты?"
    if any(word in text for word in ("откуда", "город", "живешь", "живёшь", "где ты")):
        return f"я из {persona.city}) а ты откуда?"
    if any(word in text for word in ("делаешь", "занимаешь", "работа", "учишь", "кем ты")):
        if persona.female:
            return "учусь и иногда подрабатываю) а ты чем занимаешься?"
        return "работаю, по вечерам обычно свободен) а ты чем занимаешься?"
    return None


def _pick_fallback(state: _Session, persona: _Persona) -> str:
    """Выбирает запасную реплику и подставляет уже известные имя и город."""
    pool = [line for line in _FALLBACKS if line != state.last_reply]
    if state.user_name and state.last_reply != f"{state.user_name}, ты интересный человек)":
        pool.append(f"{state.user_name}, ты интересный человек)")
    if state.user_city:
        pool.append(f"в {state.user_city} никогда не был(а), как там?")
    if persona.female:
        pool = [line.replace("понял(а)", "поняла").replace("был(а)", "была") for line in pool]
    else:
        pool = [line.replace("понял(а)", "понял").replace("был(а)", "был") for line in pool]
    return random.choice(pool)


def _note_facts(state: _Session, text: str) -> set[str]:
    """Записывает новые пол, возраст, имя и город. Возвращает, что узнали из этой реплики."""
    learned: set[str] = set()
    low = text.lower()

    name_match = _NAME_RE.search(low)
    if name_match is not None:
        state.user_name = name_match.group(1).capitalize()
        learned.add("name")

    city_match = _CITY_RE.search(low)
    if city_match is not None and state.user_city is None:
        state.user_city = city_match.group(1).capitalize()
        learned.add("city")

    gender = _detect_gender(low)
    if gender is not None and state.user_gender is None:
        state.user_gender = gender
        learned.add("gender")

    age = _detect_age(low)
    if age is not None and state.user_age is None:
        state.user_age = age
        learned.add("age")
    return learned


def _scripted_reply(state: _Session, cleaned: str, learned: set[str]) -> str:
    """Запасной ответ, если модели нет или она не ответила."""
    persona = state.persona
    assert persona is not None
    low = cleaned.lower()

    about = _about_partner(low, persona)
    if about is not None:
        return _remember(state, about)

    if "name" in learned and state.user_name:
        return _remember(state, f"приятно, {state.user_name}) чем занимаешься?")

    if "city" in learned and state.user_city:
        return _remember(state, f"{state.user_city}) далеко от меня. и чего хочешь от этого чата?")

    if "gender" in learned and state.user_gender:
        who = "парень" if state.user_gender == "male" else "девушка"
        reply = f"о, {who}) мне нравится. и чего хочешь?"
        return _remember(state, reply)

    if "age" in learned and state.user_age:
        reply = f"{state.user_age}) поняла. из какого ты города?" if persona.female else f"{state.user_age}) понял. из какого ты города?"
        return _remember(state, reply)

    if _tokens(low) & {"пока", "бб", "спокойной", "свидания", "прощай"}:
        return _remember(state, "ладно, тогда спишемся) если что, я ещё тут")

    return _remember(state, _pick_fallback(state, persona))


async def partner_reply(user_id: int, text: str) -> str:
    """После опенера ведёт диалог моделью. Без ключа или при сбое — заготовкой."""
    state = _session(user_id)
    persona = state.persona
    if state.phase != "chatting" or persona is None:
        return "напиши ещё раз, я на секунду отвлёкся)"

    cleaned = (text or "").strip()
    _push_history(state, "user", cleaned)

    learned = _note_facts(state, cleaned)
    # Импорт здесь, а не сверху: пакет агента сам тянет сессию чата.
    from vk_bot.agent import generate_reply

    generated = await generate_reply(state)
    if generated:
        return _remember(state, generated)
    return _scripted_reply(state, cleaned, learned)
