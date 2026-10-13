"""Запросы к chat_sessions и bot_users. Транзакцией управляет сервис."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from psycopg import AsyncConnection

from app.peer import ENGINE_PLATFORM, Peer

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
        INSERT INTO chat_sessions (platform, bot_key, user_id, phase, searching_since)
        VALUES (%(platform)s, %(bot_key)s, %(user_id)s, 'searching', NOW())
        ON CONFLICT (platform, bot_key, user_id) DO UPDATE SET
            phase = 'searching',
            partner_id = NULL,
            partner_platform = NULL,
            partner_bot_key = NULL,
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


def _peer(row: dict[str, Any]) -> Peer:
    return Peer(row["platform"], row["bot_key"] or "", int(row["user_id"]))


async def find_searcher(conn: AsyncConnection, exclude: Peer) -> Peer | None:
    """Живой человек, который дольше всех ждёт в очереди, кроме самого ищущего.

    Аккаунты chat-engine в очереди не участвуют: их к человеку привязывает `engine_attach`.
    """
    cursor = await conn.execute(
        """
        SELECT platform, bot_key, user_id
        FROM chat_sessions
        WHERE phase = 'searching' AND searching_since IS NOT NULL
          AND platform <> %(engine)s
          AND NOT (platform = %(platform)s AND bot_key = %(bot_key)s AND user_id = %(user_id)s)
        ORDER BY searching_since
        LIMIT 1
        """,
        {**_key(exclude), "engine": ENGINE_PLATFORM},
    )
    row = await cursor.fetchone()
    return _peer(row) if row else None


async def find_human_with_engine(conn: AsyncConnection) -> tuple[Peer, Peer] | None:
    """Человек в диалоге с chat-engine, который дольше всех говорит с ботом.

    Живой ищущий забирает его из пары с ботом: люди важнее аккаунтов chat-engine.
    """
    cursor = await conn.execute(
        """
        SELECT platform, bot_key, user_id, partner_platform, partner_bot_key, partner_id
        FROM chat_sessions
        WHERE phase = 'chatting'
          AND platform <> %(engine)s
          AND partner_platform = %(engine)s
          AND partner_id IS NOT NULL
        ORDER BY updated_at
        LIMIT 1
        """,
        {"engine": ENGINE_PLATFORM},
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    human = _peer(row)
    engine = Peer(row["partner_platform"], row["partner_bot_key"] or "", int(row["partner_id"]))
    return human, engine


async def oldest_waiting_human(conn: AsyncConnection, min_wait_seconds: float) -> Peer | None:
    """Человек, который ждёт в очереди дольше всех и не меньше min_wait_seconds."""
    cursor = await conn.execute(
        """
        SELECT platform, bot_key, user_id
        FROM chat_sessions
        WHERE phase = 'searching' AND searching_since IS NOT NULL
          AND platform <> %(engine)s
          AND searching_since <= NOW() - make_interval(secs => %(min_wait)s)
        ORDER BY searching_since
        LIMIT 1
        """,
        {"engine": ENGINE_PLATFORM, "min_wait": min_wait_seconds},
    )
    row = await cursor.fetchone()
    return _peer(row) if row else None


async def engine_demand(conn: AsyncConnection, min_wait_seconds: float) -> tuple[int, int]:
    """Сколько людей ждут не меньше min_wait_seconds и сколько аккаунтов chat-engine уже ищут."""
    cursor = await conn.execute(
        """
        SELECT
            count(*) FILTER (
                WHERE platform <> %(engine)s
                  AND searching_since <= NOW() - make_interval(secs => %(min_wait)s)
            ) AS waiting,
            count(*) FILTER (WHERE platform = %(engine)s) AS hunting
        FROM chat_sessions
        WHERE phase = 'searching' AND searching_since IS NOT NULL
        """,
        {"engine": ENGINE_PLATFORM, "min_wait": min_wait_seconds},
    )
    row = await cursor.fetchone()
    return int(row["waiting"]), int(row["hunting"])


async def presence_stats(conn: AsyncConnection, online_window_seconds: float) -> dict[str, int]:
    """Онлайн, в поиске и в диалоге — отдельно для людей и аккаунтов chat-engine.

    Онлайн: кто сейчас ищет или в диалоге, плюс кто писал за последние online_window_seconds.
    """
    cursor = await conn.execute(
        """
        WITH online AS (
            SELECT platform, bot_key, user_id FROM bot_users
            WHERE last_seen_at >= NOW() - make_interval(secs => %(window)s)
            UNION
            SELECT platform, bot_key, user_id FROM chat_sessions WHERE phase <> 'idle'
        )
        SELECT
            (SELECT count(*) FROM online WHERE platform <> %(engine)s) AS humans_online,
            (SELECT count(*) FROM online WHERE platform = %(engine)s) AS bots_online,
            count(*) FILTER (WHERE platform <> %(engine)s AND phase = 'searching') AS humans_searching,
            count(*) FILTER (WHERE platform <> %(engine)s AND phase = 'chatting') AS humans_chatting,
            count(*) FILTER (WHERE platform = %(engine)s AND phase = 'searching') AS bots_searching,
            count(*) FILTER (WHERE platform = %(engine)s AND phase = 'chatting') AS bots_chatting
        FROM chat_sessions
        """,
        {"engine": ENGINE_PLATFORM, "window": online_window_seconds},
    )
    row = await cursor.fetchone()
    return {key: int(value) for key, value in row.items()}


async def touch_user(conn: AsyncConnection, peer: Peer) -> None:
    """Запоминает пользователя при первом обращении и отмечает время последней активности."""
    await conn.execute(
        """
        INSERT INTO bot_users (platform, bot_key, user_id)
        VALUES (%(platform)s, %(bot_key)s, %(user_id)s)
        ON CONFLICT (platform, bot_key, user_id) DO UPDATE SET last_seen_at = NOW()
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
            updated_at = NOW(),
            last_seen_at = NOW()
        """,
        _key(peer),
    )
