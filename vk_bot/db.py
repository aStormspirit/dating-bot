"""Сессии чата в Supabase Postgres."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from vk_bot.config import DATABASE_URL

_INIT_DIR = Path(__file__).resolve().parent.parent / "supabase" / "init"
_conn: psycopg.Connection | None = None


def _connection() -> psycopg.Connection:
    """Открывает соединение. На старте контейнера база может подняться не сразу."""
    global _conn
    if _conn is not None and not _conn.closed:
        return _conn
    if not DATABASE_URL:
        raise SystemExit(
            "Не задан DATABASE_URL. Укажите строку подключения к Supabase Postgres в .env "
            "или запустите проект через docker compose up --build."
        )

    last_error: Exception | None = None
    for _attempt in range(15):
        try:
            _conn = psycopg.connect(
                DATABASE_URL,
                autocommit=True,
                row_factory=dict_row,
                connect_timeout=5,
            )
            return _conn
        except psycopg.OperationalError as exc:
            last_error = exc
            time.sleep(1.5)
    raise SystemExit(f"Не удалось подключиться к Supabase Postgres.\n{last_error}") from last_error


def _execute(query: str, params: dict[str, Any] | tuple | None = None) -> psycopg.Cursor:
    """Выполняет запрос и один раз переподключается, если соединение оборвалось."""
    global _conn
    try:
        return _connection().execute(query, params)
    except psycopg.OperationalError:
        if _conn is not None and not _conn.closed:
            _conn.close()
        _conn = None
        return _connection().execute(query, params)


def _sql_statements(script: str) -> list[str]:
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


def ensure_schema() -> None:
    """Создаёт таблицы сессий и профилей и добавляет новые колонки профиля."""
    for path in sorted(_INIT_DIR.glob("*.sql")):
        for statement in _sql_statements(path.read_text(encoding="utf-8")):
            _execute(statement)
    columns = _execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'bot_users'
        ORDER BY ordinal_position
        """
    ).fetchall()
    names = ", ".join(row["column_name"] for row in columns)
    print(f"Колонки bot_users: {names}")


def fetch_sessions() -> list[tuple[int, dict[str, Any]]]:
    """Возвращает все сохранённые сессии в том виде, в каком их ждёт чат."""
    rows = _execute(
        """
        SELECT user_id, phase, generation, persona, user_gender, user_age,
               user_name, user_city, last_reply, preferred_female, blocked, history,
               partner_id
        FROM chat_sessions
        """
    ).fetchall()
    loaded: list[tuple[int, dict[str, Any]]] = []
    for row in rows:
        payload: dict[str, Any] = {
            "phase": row["phase"],
            "generation": row["generation"],
            "persona": row["persona"],
            "user_gender": row["user_gender"],
            "user_age": row["user_age"],
            "user_name": row["user_name"],
            "user_city": row["user_city"],
            "last_reply": row["last_reply"],
            "blocked": row["blocked"],
            "history": row["history"] or [],
            "partner_id": row["partner_id"],
        }
        if row["preferred_female"] is not None:
            payload["preferred_female"] = row["preferred_female"]
        loaded.append((int(row["user_id"]), payload))
    return loaded


def save_session(user_id: int, payload: dict[str, Any]) -> None:
    """Пишет одну сессию. Повторный вызов обновляет тот же ряд."""
    persona = payload.get("persona")
    _execute(
        """
        INSERT INTO chat_sessions (
            user_id, phase, generation, persona, user_gender, user_age,
            user_name, user_city, last_reply, preferred_female, blocked, history,
            partner_id, updated_at
        ) VALUES (
            %(user_id)s, %(phase)s, %(generation)s, %(persona)s, %(user_gender)s, %(user_age)s,
            %(user_name)s, %(user_city)s, %(last_reply)s, %(preferred_female)s, %(blocked)s,
            %(history)s, %(partner_id)s, NOW()
        )
        ON CONFLICT (user_id) DO UPDATE SET
            phase = EXCLUDED.phase,
            generation = EXCLUDED.generation,
            persona = EXCLUDED.persona,
            user_gender = EXCLUDED.user_gender,
            user_age = EXCLUDED.user_age,
            user_name = EXCLUDED.user_name,
            user_city = EXCLUDED.user_city,
            last_reply = EXCLUDED.last_reply,
            preferred_female = EXCLUDED.preferred_female,
            blocked = EXCLUDED.blocked,
            history = EXCLUDED.history,
            partner_id = EXCLUDED.partner_id,
            updated_at = NOW()
        """,
        {
            "user_id": user_id,
            "phase": payload.get("phase") or "idle",
            "generation": int(payload.get("generation") or 0),
            "persona": Jsonb(persona) if persona is not None else None,
            "user_gender": payload.get("user_gender"),
            "user_age": payload.get("user_age"),
            "user_name": payload.get("user_name"),
            "user_city": payload.get("user_city"),
            "last_reply": payload.get("last_reply"),
            "preferred_female": payload.get("preferred_female"),
            "blocked": bool(payload.get("blocked")),
            "history": Jsonb(payload.get("history") or []),
            "partner_id": payload.get("partner_id"),
        },
    )


def delete_session(user_id: int) -> None:
    """Удаляет сессию, которую больше не нужно хранить."""
    _execute("DELETE FROM chat_sessions WHERE user_id = %s", (user_id,))


def touch_bot_user(user_id: int) -> None:
    """Запоминает id пользователя, который написал боту. Пол и возраст не затирает."""
    _execute(
        """
        INSERT INTO bot_users (user_id)
        VALUES (%s)
        ON CONFLICT (user_id) DO NOTHING
        """,
        (user_id,),
    )


def save_bot_user(
    user_id: int,
    *,
    gender: str | None = None,
    age: int | None = None,
    partner_gender: str | None = None,
) -> None:
    """Пишет id и известные пол и возраст. Пустые поля оставляют уже сохранённые значения."""
    _execute(
        """
        INSERT INTO bot_users (user_id, gender, age, partner_gender)
        VALUES (%(user_id)s, %(gender)s, %(age)s, %(partner_gender)s)
        ON CONFLICT (user_id) DO UPDATE SET
            gender = COALESCE(EXCLUDED.gender, bot_users.gender),
            age = COALESCE(EXCLUDED.age, bot_users.age),
            partner_gender = COALESCE(EXCLUDED.partner_gender, bot_users.partner_gender),
            updated_at = NOW()
        """,
        {
            "user_id": user_id,
            "gender": gender,
            "age": age,
            "partner_gender": partner_gender,
        },
    )


def record_search(user_id: int) -> None:
    """Увеличивает число запусков поиска собеседника."""
    _execute(
        """
        INSERT INTO bot_users (user_id, search_count)
        VALUES (%s, 1)
        ON CONFLICT (user_id) DO UPDATE SET
            search_count = bot_users.search_count + 1,
            updated_at = NOW()
        """,
        (user_id,),
    )


def fetch_bot_users() -> list[dict[str, Any]]:
    """Возвращает сохранённые id, пол, возраст, ссылку, премиум и число поисков."""
    rows = _execute(
        """
        SELECT user_id, gender, age, partner_gender, vk_url, is_premium, search_count
        FROM bot_users
        """
    ).fetchall()
    return [
        {
            "user_id": int(row["user_id"]),
            "gender": row["gender"],
            "age": row["age"],
            "partner_gender": row["partner_gender"],
            "vk_url": row["vk_url"],
            "is_premium": bool(row["is_premium"]),
            "search_count": int(row["search_count"] or 0),
        }
        for row in rows
    ]
