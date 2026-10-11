"""Пул соединений с Supabase Postgres и создание схемы при старте."""

from __future__ import annotations

import logging
from pathlib import Path

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger(__name__)

_APP_DIR = Path(__file__).resolve().parent
# В контейнере supabase/ лежит рядом с app/, в репозитории — на уровень выше chat_api/.
_INIT_DIRS = (_APP_DIR.parent / "supabase" / "init", _APP_DIR.parent.parent / "supabase" / "init")
_SCHEMA_LOCK = 7_310_001


def create_pool(database_url: str) -> AsyncConnectionPool:
    return AsyncConnectionPool(
        database_url,
        min_size=1,
        max_size=10,
        kwargs={"row_factory": dict_row, "autocommit": True},
        open=False,
    )


def _init_dir() -> Path:
    for path in _INIT_DIRS:
        if path.is_dir():
            return path
    raise RuntimeError(f"Не найден каталог SQL-схемы: {', '.join(map(str, _INIT_DIRS))}")


def sql_statements(script: str) -> list[str]:
    """Делит SQL-файл на запросы. Точки с запятой внутри $$ не режут запрос."""
    statements: list[str] = []
    chunk: list[str] = []
    in_dollar = False
    for line in script.splitlines():
        if not in_dollar and line.strip().startswith("--"):
            continue
        chunk.append(line)
        if line.count("$$") % 2:
            in_dollar = not in_dollar
        if not in_dollar and line.strip().endswith(";"):
            statement = "\n".join(chunk).strip()
            if statement:
                statements.append(statement)
            chunk = []
    tail = "\n".join(chunk).strip()
    if tail:
        statements.append(tail)
    return statements


async def ensure_schema(pool: AsyncConnectionPool) -> None:
    """Прогоняет идемпотентные SQL-файлы. Блокировка не даёт двум копиям API делать это разом."""
    async with pool.connection() as conn:
        await conn.execute("SELECT pg_advisory_lock(%s)", (_SCHEMA_LOCK,))
        try:
            for path in sorted(_init_dir().glob("*.sql")):
                for statement in sql_statements(path.read_text(encoding="utf-8")):
                    await conn.execute(statement)
        finally:
            await conn.execute("SELECT pg_advisory_unlock(%s)", (_SCHEMA_LOCK,))
    logger.info("Схема базы проверена")
