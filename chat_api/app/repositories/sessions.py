"""Запросы к chat_sessions и bot_users. Транзакцией управляет сервис."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from psycopg import AsyncConnection

from app.peer import Peer

_MATCHMAKING_LOCK = 7_310_002


@dataclass(frozen=True)
class SessionRow:
    phase: str
    partner: Peer | None


def _key(peer: Peer) -> dict[str, Any]:
    return peer.as_dict()


async def lock_matchmaking(conn: AsyncConnection) -> None:
    """Одна блокировка на все изменения пар до конца транзакции."""
    await conn.execute("SELECT pg_advisory_xact_lock(%s)", (_MATCHMAKING_LOCK,))


async def get_session(conn: AsyncConnection, peer: Peer) -> SessionRow | None:
    cursor = await conn.execute(
        """
        SELECT phase, partner_id, partner_platform, partner_bot_key
        FROM chat_sessions
        WHERE platform = %(platform)s AND bot_key = %(bot_key)s AND user_id = %(user_id)s
        """,
        _key(peer),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    partner = None
    if row["partner_id"]:
        partner = Peer(
            row["partner_platform"] or "vk",
            row["partner_bot_key"] or "",
            int(row["partner_id"]),
        )
    return SessionRow(phase=row["phase"], partner=partner)


async def set_idle(conn: AsyncConnection, peer: Peer) -> None:
    await conn.execute(
        """
        UPDATE chat_sessions
        SET phase = 'idle', partner_id = NULL, partner_platform = NULL, partner_bot_key = NULL,
            searching_since = NULL, updated_at = NOW()
        WHERE platform = %(platform)s AND bot_key = %(bot_key)s AND user_id = %(user_id)s
        """,
        _key(peer),
    )


async def set_searching(conn: AsyncConnection, peer: Peer) -> None:
    await conn.execute(
        """
        INSERT INTO chat_sessions (platform, bot_key, user_id, phase, generation, searching_since)
        VALUES (%(platform)s, %(bot_key)s, %(user_id)s, 'searching', 1, NOW())
        ON CONFLICT (platform, bot_key, user_id) DO UPDATE SET
            phase = 'searching',
            generation = chat_sessions.generation + 1,
            partner_id = NULL,
            partner_platform = NULL,
            partner_bot_key = NULL,
            persona = NULL,
            history = '[]'::jsonb,
            searching_since = NOW(),
            updated_at = NOW()
        """,
        _key(peer),
    )


async def set_chatting(conn: AsyncConnection, peer: Peer, partner: Peer) -> None:
    await conn.execute(
        """
        UPDATE chat_sessions
        SET phase = 'chatting', partner_id = %(partner_id)s,
            partner_platform = %(partner_platform)s, partner_bot_key = %(partner_bot_key)s,
            searching_since = NULL, updated_at = NOW()
        WHERE platform = %(platform)s AND bot_key = %(bot_key)s AND user_id = %(user_id)s
        """,
        {
            **_key(peer),
            "partner_id": partner.user_id,
            "partner_platform": partner.platform,
            "partner_bot_key": partner.bot_key,
        },
    )


async def find_searcher(conn: AsyncConnection, exclude: Peer) -> Peer | None:
    """Тот, кто дольше всех ждёт в очереди, кроме самого ищущего."""
    cursor = await conn.execute(
        """
        SELECT platform, bot_key, user_id
        FROM chat_sessions
        WHERE phase = 'searching' AND searching_since IS NOT NULL
          AND NOT (platform = %(platform)s AND bot_key = %(bot_key)s AND user_id = %(user_id)s)
        ORDER BY searching_since
        LIMIT 1
        """,
        _key(exclude),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return Peer(row["platform"], row["bot_key"] or "", int(row["user_id"]))


async def touch_user(conn: AsyncConnection, peer: Peer) -> None:
    """Запоминает пользователя. Пол и возраст не затирает."""
    await conn.execute(
        """
        INSERT INTO bot_users (platform, bot_key, user_id)
        VALUES (%(platform)s, %(bot_key)s, %(user_id)s)
        ON CONFLICT (platform, bot_key, user_id) DO NOTHING
        """,
        _key(peer),
    )


async def record_search(conn: AsyncConnection, peer: Peer) -> None:
    await conn.execute(
        """
        INSERT INTO bot_users (platform, bot_key, user_id, search_count)
        VALUES (%(platform)s, %(bot_key)s, %(user_id)s, 1)
        ON CONFLICT (platform, bot_key, user_id) DO UPDATE SET
            search_count = bot_users.search_count + 1,
            updated_at = NOW()
        """,
        _key(peer),
    )
