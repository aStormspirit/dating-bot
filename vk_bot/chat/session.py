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
    rekey_legacy_vk,
    save_bot_user,
    save_session,
    touch_bot_user,
)
from vk_bot.peer import Peer

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
    partner: Peer | None = None
    preferred_female: bool | None = None
    partner_choice: str | None = None
    blocked: bool = False
    history: list[dict[str, str]] = field(default_factory=list)


_sessions: dict[Peer, _Session] = {}


def _session(peer: Peer) -> _Session:
    """Возвращает сессию пользователя, создавая пустую при первом обращении."""
    if peer not in _sessions:
        _sessions[peer] = _Session()
    return _sessions[peer]


def is_searching(peer: Peer) -> bool:
    """Пользователь сейчас ждёт, пока поиск собеседника завершится."""
    return _session(peer).phase == "searching"


def is_chatting(peer: Peer) -> bool:
    """Пользователь уже в диалоге с собеседником."""
    return _session(peer).phase == "chatting"


def remember_visitor(peer: Peer) -> None:
    """Сохраняет пользователя, как только он написал боту."""
    _session(peer)
    touch_bot_user(peer)


def _clear_dialog(state: _Session) -> None:
    """Сбрасывает диалог, не трогая выбор пола на будущее."""
    state.phase = "idle"
    state.generation += 1
    state.persona = None
    state.partner = None
    state.user_name = None
    state.user_city = None
    state.blocked = False
    state.history.clear()
    state.last_reply = None


def stop_chat(peer: Peer) -> Peer | None:
    """Прерывает поиск или диалог. Возвращает собеседника, если пара была."""
    state = _session(peer)
    partner = state.partner
    _clear_dialog(state)
    _persist_user(peer)
    if partner is None:
        return None
    other = _session(partner)
    if other.partner != peer:
        return None
    _clear_dialog(other)
    _persist_user(partner)
    return partner


def begin_search(peer: Peer) -> int:
    """Начинает новый поиск и возвращает его номер, чтобы отмена не смешала ответы."""
    state = _session(peer)
    state.generation += 1
    state.phase = "searching"
    state.persona = None
    state.partner = None
    state.user_name = None
    state.user_city = None
    state.last_reply = None
    state.blocked = False
    state.history.clear()
    _persist_user(peer)
    record_search(peer)
    return state.generation


def partner_of(peer: Peer) -> Peer | None:
    """Живой собеседник, если диалог ещё связан с двух сторон."""
    state = _session(peer)
    partner = state.partner
    if state.phase != "chatting" or partner is None:
        return None
    other = _sessions.get(partner)
    if other is None or other.phase != "chatting" or other.partner != peer:
        return None
    return partner


def pair_searcher(peer: Peer, generation: int) -> tuple[Peer, bool] | None:
    """Соединяет ищущего с другим ищущим. Второй элемент — создана ли пара этим вызовом."""
    state = _session(peer)
    if state.generation != generation:
        return None
    if state.phase == "chatting" and state.partner is not None:
        return state.partner, False
    if state.phase != "searching":
        return None
    for other_peer, other in _sessions.items():
        if other_peer == peer or other.phase != "searching" or other.partner is not None:
            continue
        state.phase = "chatting"
        other.phase = "chatting"
        state.partner = other_peer
        other.partner = peer
        state.persona = None
        other.persona = None
        _persist_user(peer)
        _persist_user(other_peer)
        return other_peer, True
    return None


def set_partner_gender(peer: Peer, female: bool | None) -> None:
    """Запоминает, кого искать в следующий раз: девушку, парня или кого угодно."""
    state = _session(peer)
    state.preferred_female = female
    if female is True:
        state.partner_choice = "female"
    elif female is False:
        state.partner_choice = "male"
    else:
        state.partner_choice = "any"
    _persist_user(peer)


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


def complete_search(peer: Peer, generation: int) -> str | None:
    """Завершает поиск, если его не отменили. Возвращает служебный текст без реплики собеседника."""
    state = _session(peer)
    if state.phase != "searching" or state.generation != generation:
        return None
    state.phase = "chatting"
    state.persona = _make_persona(state.preferred_female)
    _persist_user(peer)
    return FOUND_TEXT


def opener_pending(peer: Peer, generation: int) -> bool:
    """Первая реплика ещё не ушла и этот поиск не отменили."""
    state = _session(peer)
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


def _owner(state: _Session) -> Peer:
    """Находит пользователя, которому принадлежит сессия в памяти."""
    for peer, current in _sessions.items():
        if current is state:
            return peer
    raise RuntimeError("Сессия не привязана к пользователю")


def _remember(state: _Session, reply: str) -> str:
    """Запоминает последнюю реплику собеседника и сохраняет активный диалог."""
    state.last_reply = reply
    _push_history(state, "assistant", reply)
    _persist_user(_owner(state))
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
        "partner_id": state.partner.user_id if state.partner else None,
        "partner_platform": state.partner.platform if state.partner else None,
        "partner_bot_key": state.partner.bot_key if state.partner else None,
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
    partner = None
    if raw.get("partner_id"):
        partner = Peer(
            str(raw.get("partner_platform") or "vk"),
            str(raw.get("partner_bot_key") or ""),
            int(raw["partner_id"]),
        )
    return _Session(
        phase="chatting" if raw.get("phase") == "chatting" else "idle",
        generation=int(raw.get("generation") or 0),
        persona=persona,
        user_gender=raw.get("user_gender"),
        user_age=raw.get("user_age"),
        user_name=raw.get("user_name"),
        user_city=raw.get("user_city"),
        last_reply=raw.get("last_reply"),
        partner=partner,
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
    return (state.phase == "chatting" and state.partner is not None) or state.preferred_female is not None


def _persist_user(peer: Peer) -> None:
    """Пишет профиль пользователя и активный диалог. Профиль остаётся после остановки чата."""
    state = _session(peer)
    save_bot_user(
        peer,
        gender=state.user_gender,
        age=state.user_age,
        partner_gender=_partner_gender_label(state),
    )
    if _should_store(state):
        save_session(peer, _session_to_dict(state))
        return
    delete_session(peer)


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
        peer = Peer("vk", "", user_id)
        if peer in _sessions:
            continue
        _sessions[peer] = _session_from_dict(value)
        _persist_user(peer)
        imported += 1
    return imported


def _repair_pairs() -> None:
    """Снимает диалоги с ботом и пары, у которых вторая сторона уже не отвечает."""
    for peer, state in list(_sessions.items()):
        if partner_of(peer) is not None:
            continue
        if state.phase != "chatting" and state.partner is None:
            continue
        state.phase = "idle"
        state.partner = None
        state.persona = None
        _persist_user(peer)


def adopt_legacy_vk(bot_key: str) -> None:
    """Крепит старые диалоги без имени бота к первому сообществу ВК."""
    rekey_legacy_vk(bot_key)
    moved: list[tuple[Peer, _Session]] = []
    for peer, state in list(_sessions.items()):
        if state.partner is not None and state.partner.platform == "vk" and state.partner.bot_key == "":
            state.partner = Peer("vk", bot_key, state.partner.user_id)
        if peer.platform == "vk" and peer.bot_key == "":
            moved.append((peer, state))
            del _sessions[peer]
    for peer, state in moved:
        adopted = Peer("vk", bot_key, peer.user_id)
        if adopted not in _sessions:
            _sessions[adopted] = state


def load_chats() -> None:
    """Поднимает диалоги и профили из Supabase Postgres, затем добирает старый chats.json."""
    ensure_schema()
    for peer, raw in fetch_sessions():
        _sessions[peer] = _session_from_dict(raw)
    imported = _import_legacy_file()
    if imported:
        print(f"Перенесено диалогов из chats.json в Supabase: {imported}")
    for peer, state in list(_sessions.items()):
        save_bot_user(
            peer,
            gender=state.user_gender,
            age=state.user_age,
            partner_gender=_partner_gender_label(state),
        )
    for profile in fetch_bot_users():
        profile_peer = Peer(profile["platform"], profile["bot_key"], profile["user_id"])
        _apply_saved_profile(_session(profile_peer), profile)
    _repair_pairs()


load_chats()
