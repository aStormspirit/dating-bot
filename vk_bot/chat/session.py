"""Сессия анонимного чата: поиск собеседника и запись активных диалогов."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field

from vk_bot.config import CHATS_PATH
from vk_bot.db import (
    delete_session,
    ensure_schema,
    fetch_bot_users,
    fetch_sessions,
    record_search,
    save_bot_user,
    save_session,
    touch_bot_user,
)

SEARCHING_TEXT = "🔎 Ищем собеседника..."
FOUND_TEXT = (
    "💬 Собеседник найден. Вы можете писать ему сюда 👇\n"
    "Реклама коммерческих услуг запрещена! Не забывайте нажимать кнопку жалобы если встречаете спам."
)

_FEMALE_NAMES = ("Аня", "Катя", "Лера", "Маша", "Вика", "Алина", "Соня")
_MALE_NAMES = ("Артём", "Макс", "Дима", "Никита", "Егор", "Саша")
_CITIES = ("Москвы", "Питера", "Казани", "Новосибирска", "Краснодара", "Екатеринбурга")


@dataclass
class _Persona:
    name: str
    age: int
    female: bool
    city: str

    @property
    def gender_word(self) -> str:
        """Как персона называет свой пол в реплике."""
        return "девушка" if self.female else "парень"


@dataclass
class _Session:
    phase: str = "idle"
    generation: int = 0
    persona: _Persona | None = None
    user_gender: str | None = None
    user_age: int | None = None
    user_name: str | None = None
    user_city: str | None = None
    last_reply: str | None = None
    partner_id: int | None = None
    preferred_female: bool | None = None
    partner_choice: str | None = None
    blocked: bool = False
    history: list[dict[str, str]] = field(default_factory=list)


_sessions: dict[int, _Session] = {}


def _session(user_id: int) -> _Session:
    """Возвращает сессию пользователя, создавая пустую при первом обращении."""
    if user_id not in _sessions:
        _sessions[user_id] = _Session()
    return _sessions[user_id]


def is_searching(user_id: int) -> bool:
    """Пользователь сейчас ждёт, пока поиск собеседника завершится."""
    return _session(user_id).phase == "searching"


def is_chatting(user_id: int) -> bool:
    """Пользователь уже в диалоге с собеседником."""
    return _session(user_id).phase == "chatting"


def remember_visitor(user_id: int) -> None:
    """Сохраняет id пользователя, как только он написал боту."""
    _session(user_id)
    touch_bot_user(user_id)


def _clear_dialog(state: _Session) -> None:
    """Сбрасывает диалог, не трогая выбор пола на будущее."""
    state.phase = "idle"
    state.generation += 1
    state.persona = None
    state.partner_id = None
    state.user_name = None
    state.user_city = None
    state.blocked = False
    state.history.clear()
    state.last_reply = None


def stop_chat(user_id: int) -> int | None:
    """Прерывает поиск или диалог. Возвращает id собеседника, если пара была."""
    state = _session(user_id)
    partner_id = state.partner_id
    _clear_dialog(state)
    _persist_user(user_id)
    if partner_id is None:
        return None
    partner = _session(partner_id)
    if partner.partner_id != user_id:
        return None
    _clear_dialog(partner)
    _persist_user(partner_id)
    return partner_id


def begin_search(user_id: int) -> int:
    """Начинает новый поиск и возвращает его номер, чтобы отмена не смешала ответы."""
    state = _session(user_id)
    state.generation += 1
    state.phase = "searching"
    state.persona = None
    state.partner_id = None
    state.user_name = None
    state.user_city = None
    state.last_reply = None
    state.blocked = False
    state.history.clear()
    _persist_user(user_id)
    record_search(user_id)
    return state.generation


def partner_of(user_id: int) -> int | None:
    """Id живого собеседника, если диалог ещё связан с двух сторон."""
    state = _session(user_id)
    partner_id = state.partner_id
    if state.phase != "chatting" or partner_id is None:
        return None
    partner = _sessions.get(partner_id)
    if partner is None or partner.phase != "chatting" or partner.partner_id != user_id:
        return None
    return partner_id


def pair_searcher(user_id: int, generation: int) -> tuple[int, bool] | None:
    """Соединяет ищущего с другим ищущим. Второй элемент — создана ли пара этим вызовом."""
    state = _session(user_id)
    if state.generation != generation:
        return None
    if state.phase == "chatting" and state.partner_id is not None:
        return state.partner_id, False
    if state.phase != "searching":
        return None
    for other_id, other in _sessions.items():
        if other_id == user_id or other.phase != "searching" or other.partner_id is not None:
            continue
        state.phase = "chatting"
        other.phase = "chatting"
        state.partner_id = other_id
        other.partner_id = user_id
        state.persona = None
        other.persona = None
        _persist_user(user_id)
        _persist_user(other_id)
        return other_id, True
    return None


def set_partner_gender(user_id: int, female: bool | None) -> None:
    """Запоминает, кого искать в следующий раз: девушку, парня или кого угодно."""
    state = _session(user_id)
    state.preferred_female = female
    if female is True:
        state.partner_choice = "female"
    elif female is False:
        state.partner_choice = "male"
    else:
        state.partner_choice = "any"
    _persist_user(user_id)


def _make_persona(preferred_female: bool | None) -> _Persona:
    """Собирает собеседника 18+. Пол берётся из выбора пользователя, иначе случайный."""
    female = random.choice((True, False)) if preferred_female is None else preferred_female
    age = random.randint(18, 35)
    names = _FEMALE_NAMES if female else _MALE_NAMES
    return _Persona(
        name=random.choice(names),
        age=age,
        female=female,
        city=random.choice(_CITIES),
    )


def complete_search(user_id: int, generation: int) -> str | None:
    """Завершает поиск, если его не отменили. Возвращает служебный текст без реплики собеседника."""
    state = _session(user_id)
    if state.phase != "searching" or state.generation != generation:
        return None
    state.phase = "chatting"
    state.persona = _make_persona(state.preferred_female)
    _persist_user(user_id)
    return FOUND_TEXT


def opener_pending(user_id: int, generation: int) -> bool:
    """Первая реплика ещё не ушла и этот поиск не отменили."""
    state = _session(user_id)
    return state.phase == "chatting" and state.generation == generation and state.last_reply is None


_HISTORY_LIMIT = 40


def _push_history(state: _Session, role: str, content: str) -> None:
    """Кладёт реплику в контекст модели. В базу само не пишет."""
    text = content.strip()
    if not text or role not in {"user", "assistant"}:
        return
    state.history.append({"role": role, "content": text})
    if len(state.history) > _HISTORY_LIMIT:
        del state.history[:-_HISTORY_LIMIT]


def _user_id(state: _Session) -> int:
    """Находит пользователя, которому принадлежит сессия в памяти."""
    for user_id, current in _sessions.items():
        if current is state:
            return user_id
    raise RuntimeError("Сессия не привязана к пользователю")


def _remember(state: _Session, reply: str) -> str:
    """Запоминает последнюю реплику собеседника и сохраняет активный диалог."""
    state.last_reply = reply
    _push_history(state, "assistant", reply)
    _persist_user(_user_id(state))
    return reply


def format_partner(text: str) -> str:
    """Оформляет реплику так, будто её прислал собеседник."""
    return f"👤 Собеседник:\n{text}"


def _session_to_dict(state: _Session) -> dict:
    """Готовит сессию к записи в Supabase Postgres."""
    persona = None
    if state.persona is not None:
        persona = {
            "name": state.persona.name,
            "age": state.persona.age,
            "female": state.persona.female,
            "city": state.persona.city,
        }
    payload = {
        "phase": state.phase,
        "generation": state.generation,
        "persona": persona,
        "user_gender": state.user_gender,
        "user_age": state.user_age,
        "user_name": state.user_name,
        "user_city": state.user_city,
        "last_reply": state.last_reply,
        "blocked": state.blocked,
        "partner_id": state.partner_id,
        "history": state.history,
    }
    if state.preferred_female is not None:
        payload["preferred_female"] = state.preferred_female
    return payload


def _session_from_dict(raw: dict) -> _Session:
    """Восстанавливает диалог. Незавершённый поиск после перезапуска не продолжается."""
    persona_raw = raw.get("persona")
    persona = None
    if isinstance(persona_raw, dict):
        persona = _Persona(
            name=str(persona_raw.get("name") or "Аня"),
            age=int(persona_raw.get("age") or 20),
            female=bool(persona_raw.get("female")),
            city=str(persona_raw.get("city") or "Москвы"),
        )
    preferred = raw.get("preferred_female") if "preferred_female" in raw else None
    return _Session(
        phase="chatting" if raw.get("phase") == "chatting" else "idle",
        generation=int(raw.get("generation") or 0),
        persona=persona,
        user_gender=raw.get("user_gender"),
        user_age=raw.get("user_age"),
        user_name=raw.get("user_name"),
        user_city=raw.get("user_city"),
        last_reply=raw.get("last_reply"),
        partner_id=int(raw["partner_id"]) if raw.get("partner_id") else None,
        preferred_female=None if preferred is None else bool(preferred),
        blocked=bool(raw.get("blocked")),
        history=_history_from_raw(raw),
    )


def _history_from_raw(raw: dict) -> list[dict[str, str]]:
    """Восстанавливает переписку. Если её не было, хватает последней реплики собеседника."""
    history: list[dict[str, str]] = []
    for item in raw.get("history") or []:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str) or not content.strip():
            continue
        history.append({"role": role, "content": content.strip()})
    if history:
        return history[-_HISTORY_LIMIT:]
    last_reply = raw.get("last_reply")
    if isinstance(last_reply, str) and last_reply.strip():
        return [{"role": "assistant", "content": last_reply.strip()}]
    return []


def _partner_gender_label(state: _Session) -> str | None:
    """Выбор пола партнёра: female, male, any или ещё ничего."""
    if state.partner_choice in {"female", "male", "any"}:
        return state.partner_choice
    if state.preferred_female is True:
        return "female"
    if state.preferred_female is False:
        return "male"
    return None


def _apply_saved_profile(state: _Session, profile: dict) -> None:
    """Подставляет в сессию пол и возраст, если в этом запуске их ещё нет."""
    if state.user_gender is None and profile.get("gender"):
        state.user_gender = profile["gender"]
    if state.user_age is None and profile.get("age") is not None:
        state.user_age = int(profile["age"])
    choice = profile.get("partner_gender")
    if state.partner_choice is None and choice in {"female", "male", "any"}:
        state.partner_choice = choice
        if state.preferred_female is None and choice == "female":
            state.preferred_female = True
        elif state.preferred_female is None and choice == "male":
            state.preferred_female = False


def _should_store(state: _Session) -> bool:
    """В базе остаётся диалог двух людей и выбранный пол следующего партнёра."""
    return (state.phase == "chatting" and state.partner_id is not None) or state.preferred_female is not None


def _persist_user(user_id: int) -> None:
    """Пишет профиль пользователя и активный диалог. Профиль остаётся после остановки чата."""
    state = _session(user_id)
    save_bot_user(
        user_id,
        gender=state.user_gender,
        age=state.user_age,
        partner_gender=_partner_gender_label(state),
    )
    if _should_store(state):
        save_session(user_id, _session_to_dict(state))
        return
    delete_session(user_id)


def _import_legacy_file() -> int:
    """Переносит chats.json в базу. Уже существующие пользователи не затираются."""
    if not CHATS_PATH.exists():
        return 0
    try:
        raw = json.loads(CHATS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    if not isinstance(raw, dict):
        return 0
    imported = 0
    for key, value in raw.items():
        if not isinstance(value, dict):
            continue
        try:
            user_id = int(key)
        except (TypeError, ValueError):
            continue
        if user_id in _sessions:
            continue
        _sessions[user_id] = _session_from_dict(value)
        _persist_user(user_id)
        imported += 1
    return imported


def _repair_pairs() -> None:
    """Снимает диалоги с ботом и пары, у которых вторая сторона уже не отвечает."""
    for user_id, state in list(_sessions.items()):
        if partner_of(user_id) is not None:
            continue
        if state.phase != "chatting" and state.partner_id is None:
            continue
        state.phase = "idle"
        state.partner_id = None
        state.persona = None
        _persist_user(user_id)


def load_chats() -> None:
    """Поднимает диалоги и профили из Supabase Postgres, затем добирает старый chats.json."""
    ensure_schema()
    for user_id, raw in fetch_sessions():
        _sessions[user_id] = _session_from_dict(raw)
    imported = _import_legacy_file()
    if imported:
        print(f"Перенесено диалогов из chats.json в Supabase: {imported}")
    for user_id, state in list(_sessions.items()):
        save_bot_user(
            user_id,
            gender=state.user_gender,
            age=state.user_age,
            partner_gender=_partner_gender_label(state),
        )
    for profile in fetch_bot_users():
        _apply_saved_profile(_session(profile["user_id"]), profile)
    _repair_pairs()


load_chats()
