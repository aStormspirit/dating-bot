"""Логика анонимного чата: очередь поиска, пары и пересылка реплик."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from app.events import EventBus
from app.peer import Peer
from app.repositories import sessions as repo
from app.schemas import ChatEvent, LeftReason, MessageOut, Phase, StateOut, StopOut

Outbox = list[tuple[Peer, ChatEvent]]


class NotChattingError(Exception):
    """Действие доступно только в активном диалоге."""


class ChatService:
    """Все изменения пар идут под одной блокировкой, события уходят после коммита."""

    def __init__(self, pool: AsyncConnectionPool, events: EventBus) -> None:
        self._pool = pool
        self._events = events

    @asynccontextmanager
    async def _locked(self) -> AsyncIterator[AsyncConnection]:
        async with self._pool.connection() as conn, conn.transaction():
            await repo.lock_matchmaking(conn)
            yield conn

    async def _flush(self, outbox: Outbox) -> None:
        for recipient, event in outbox:
            await self._events.publish(recipient, event)

    @staticmethod
    async def _linked_partner(conn: AsyncConnection, peer: Peer, session: repo.SessionRow | None) -> Peer | None:
        """Собеседник, если диалог связан с двух сторон."""
        if session is None or session.phase != "chatting" or session.partner is None:
            return None
        other = await repo.get_session(conn, session.partner)
        if other is None or other.phase != "chatting" or other.partner != peer:
            return None
        return session.partner

    async def _detach(self, conn: AsyncConnection, peer: Peer, reason: LeftReason, outbox: Outbox) -> bool:
        """Снимает пользователя с поиска или диалога. True, если было что снимать."""
        session = await repo.get_session(conn, peer)
        if session is None or session.phase == "idle":
            return False
        partner = await self._linked_partner(conn, peer, session)
        await repo.set_idle(conn, peer)
        if partner is not None:
            await repo.set_idle(conn, partner)
            outbox.append((partner, ChatEvent(type="partner_left", reason=reason)))
        return True

    async def _search(self, peer: Peer, left_reason: LeftReason) -> StateOut:
        outbox: Outbox = []
        async with self._locked() as conn:
            await self._detach(conn, peer, left_reason, outbox)
            await repo.set_searching(conn, peer)
            await repo.record_search(conn, peer)
            phase: Phase = "searching"
            other = await repo.find_searcher(conn, peer)
            if other is not None:
                await repo.set_chatting(conn, peer, other)
                await repo.set_chatting(conn, other, peer)
                outbox.append((other, ChatEvent(type="partner_found")))
                phase = "chatting"
        await self._flush(outbox)
        return StateOut(phase=phase)

    async def visit(self, peer: Peer) -> None:
        async with self._pool.connection() as conn:
            await repo.touch_user(conn, peer)

    async def state(self, peer: Peer) -> StateOut:
        async with self._pool.connection() as conn:
            session = await repo.get_session(conn, peer)
        return StateOut(phase=session.phase if session else "idle")

    async def search(self, peer: Peer) -> StateOut:
        """Встаёт в очередь. Прежний собеседник узнаёт, что диалог закончен."""
        return await self._search(peer, "stopped")

    async def report(self, peer: Peer) -> StateOut:
        """Жалоба закрывает диалог и сразу ставит в поиск."""
        async with self._pool.connection() as conn:
            session = await repo.get_session(conn, peer)
        if session is None or session.phase != "chatting":
            raise NotChattingError
        return await self._search(peer, "reported")

    async def stop(self, peer: Peer) -> StopOut:
        outbox: Outbox = []
        async with self._locked() as conn:
            was_active = await self._detach(conn, peer, "stopped", outbox)
        await self._flush(outbox)
        return StopOut(was_active=was_active)

    async def send_message(self, peer: Peer, text: str) -> MessageOut:
        """Пересылает реплику. Если пара уже распалась, закрывает диалог."""
        async with self._pool.connection() as conn:
            session = await repo.get_session(conn, peer)
            if session is None or session.phase != "chatting":
                raise NotChattingError
            partner = await self._linked_partner(conn, peer, session)
        if partner is not None:
            await self._events.publish(partner, ChatEvent(type="message", text=text))
            return MessageOut(delivered=True, phase="chatting")
        outbox: Outbox = []
        async with self._locked() as conn:
            await self._detach(conn, peer, "stopped", outbox)
        await self._flush(outbox)
        return MessageOut(delivered=False, phase="idle")

    async def delivery_failed(self, peer: Peer) -> None:
        """Клиент не смог доставить событие этому пользователю: его диалог закрывается."""
        outbox: Outbox = []
        async with self._locked() as conn:
            await self._detach(conn, peer, "undeliverable", outbox)
        await self._flush(outbox)
