"""Публичный вызов графа: чистая реплика или тишина, если Abliteration недоступен."""

from __future__ import annotations

import re
import sys

from vk_bot.agent.graph import breaks_role, get_graph, history_messages
from vk_bot.chat.session import _Persona, _Session
from vk_bot.config import ABLIT_API_KEY


def _clean_reply(text: str, persona: _Persona) -> str | None:
    """Снимает служебную обвязку и укладывает ответ в размер сообщения ВК."""
    cleaned = text.strip().strip('"').strip("«»").strip()
    cleaned = re.sub(
        rf"^(?:{re.escape(persona.name)}|собеседник)\s*:\s*",
        "",
        cleaned,
        count=1,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    if not cleaned:
        return None
    if len(cleaned) > 900:
        shortened = cleaned[:900].rsplit(" ", 1)[0].rstrip(".,; ")
        cleaned = f"{shortened}..."
    return cleaned


def _accept(state: _Session, text: str | None) -> str | None:
    """Оставляет ответ, только если модель осталась в роли персонажа."""
    if not text or state.persona is None or breaks_role(text):
        return None
    return _clean_reply(text, state.persona)


async def generate_reply(state: _Session) -> str | None:
    """Просит граф продолжить диалог. None — ключа нет или Abliteration не ответила."""
    if not ABLIT_API_KEY or state.persona is None or not state.history:
        return None
    try:
        result = await get_graph().ainvoke(
            {
                "messages": history_messages(state),
                "reply": None,
                "attempt": 0,
                "broke_role": False,
            }
        )
    except Exception as exc:  # noqa: BLE001 — сбой сети не должен ронять диалог ВК
        print(f"Abliteration не ответила: {type(exc).__name__}: {exc}", file=sys.stderr)
        return None
    reply = result.get("reply") if isinstance(result, dict) else None
    return _accept(state, reply if isinstance(reply, str) else None)
