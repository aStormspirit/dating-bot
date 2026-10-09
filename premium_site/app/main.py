"""Отдельный сайт оплаты премиума. Бот только отдаёт на него ссылку."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

APP_DIR = Path(__file__).resolve().parent
DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip()
# id тарифа → название, дни, цена. Совпадает с кнопками в vk_bot/ui.py.
PLANS = {
    "trial": ("3 дня VIP", 3, 1),
    "start": ("Старт", 3, 399),
    "optimal": ("Оптимальный", 30, 990),
    "year": ("365 дней", 365, 2026),
}

app = FastAPI(title="Премиум")
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")


def _connect() -> psycopg.Connection:
    if not DATABASE_URL:
        raise HTTPException(status_code=503, detail="База оплаты не настроена")
    return psycopg.connect(DATABASE_URL, autocommit=True)


def _ensure_orders() -> None:
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS premium_orders (
                id UUID PRIMARY KEY,
                vk_user_id BIGINT,
                amount_rub INTEGER NOT NULL,
                period_hours INTEGER NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('pending', 'paid', 'failed')),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )


def _vk_user_id(raw: str) -> int | None:
    text = (raw or "").strip()
    if not text.isdigit():
        return None
    return int(text)


@app.on_event("startup")
def prepare_database() -> None:
    if DATABASE_URL:
        _ensure_orders()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _plan(plan_id: str) -> tuple[str, str, int, int]:
    """Возвращает известный тариф. Неизвестный id заменяется акцией за 1 ₽."""
    key = plan_id if plan_id in PLANS else "trial"
    title, days, price = PLANS[key]
    return key, title, days, price


@app.get("/", response_class=HTMLResponse)
def offer_page(request: Request, plan: str = "") -> HTMLResponse:
    selected = plan if plan in PLANS else ""
    keys = [selected] if selected else list(PLANS)
    plans = []
    for key in keys:
        title, days, price = PLANS[key]
        plans.append({"id": key, "title": title, "days": days, "price": price})
    return templates.TemplateResponse(request, "index.html", {"plans": plans})


@app.post("/checkout")
def checkout(plan: str = Form(default="trial"), vk_id: str = Form(default="")) -> RedirectResponse:
    _plan_id, _title, days, price = _plan(plan)
    user_id = _vk_user_id(vk_id)
    order_id = uuid4()
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO premium_orders (id, vk_user_id, amount_rub, period_hours, status)
            VALUES (%s, %s, %s, %s, 'pending')
            """,
            (order_id, user_id, price, days * 24),
        )
    return RedirectResponse(url=f"/orders/{order_id}", status_code=303)


@app.get("/orders/{order_id}", response_class=HTMLResponse)
def order_page(request: Request, order_id: UUID) -> HTMLResponse:
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT id, vk_user_id, amount_rub, period_hours, status
            FROM premium_orders
            WHERE id = %s
            """,
            (order_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Счёт не найден")
    return templates.TemplateResponse(
        request,
        "order.html",
        {
            "order_id": row[0],
            "vk_user_id": row[1],
            "amount": row[2],
            "hours": row[3],
            "days": max(1, int(row[3]) // 24),
            "status": row[4],
        },
    )
