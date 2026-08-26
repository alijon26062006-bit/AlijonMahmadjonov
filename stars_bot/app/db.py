"""Слой доступа к данным (SQLite через aiosqlite)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import aiosqlite

from app.config import settings

# Жизненный цикл заказа
STATUS_AWAITING_RECEIPT = "awaiting_receipt"  # ждём чек от покупателя
STATUS_PENDING_REVIEW = "pending_review"      # чек прислан, ждём решения админа
STATUS_DELIVERING = "delivering"              # админ подтвердил, идёт выдача
STATUS_DELIVERED = "delivered"                # успешно выдано
STATUS_REJECTED = "rejected"                  # админ отклонил
STATUS_FAILED = "failed"                      # оплата принята, но выдача упала
STATUS_CANCELLED = "cancelled"                # покупатель отменил сам

STATUS_TITLES = {
    STATUS_AWAITING_RECEIPT: "🕗 Ждёт чек",
    STATUS_PENDING_REVIEW: "🔍 На проверке",
    STATUS_DELIVERING: "🚚 Выдаётся",
    STATUS_DELIVERED: "✅ Выдан",
    STATUS_REJECTED: "❌ Отклонён",
    STATUS_FAILED: "⚠️ Ошибка выдачи",
    STATUS_CANCELLED: "🚫 Отменён",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY,
    username    TEXT,
    first_name  TEXT,
    is_banned   INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER NOT NULL,
    product_type      TEXT NOT NULL,          -- 'stars' | 'premium'
    quantity          INTEGER NOT NULL,       -- кол-во звёзд или месяцев
    recipient         TEXT NOT NULL,          -- @username получателя
    price             INTEGER NOT NULL,
    currency          TEXT NOT NULL,
    status            TEXT NOT NULL,
    receipt_file_id   TEXT,
    fragment_order_id TEXT,
    error             TEXT,
    reviewed_by       INTEGER,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_orders_user   ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
"""


@dataclass
class Order:
    id: int
    user_id: int
    product_type: str
    quantity: int
    recipient: str
    price: int
    currency: str
    status: str
    receipt_file_id: str | None
    fragment_order_id: str | None
    error: str | None
    reviewed_by: int | None
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: aiosqlite.Row) -> "Order":
        return cls(**{key: row[key] for key in cls.__annotations__})

    @property
    def title(self) -> str:
        if self.product_type == "stars":
            return f"⭐ {self.quantity} звёзд"
        return f"💎 Premium {self.quantity} мес."

    @property
    def status_title(self) -> str:
        return STATUS_TITLES.get(self.status, self.status)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def connect() -> aiosqlite.Connection:
    settings.db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(settings.db_file)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    return conn


async def init(conn: aiosqlite.Connection) -> None:
    await conn.executescript(SCHEMA)
    await conn.commit()


# ---------------------------------------------------------------- users


async def upsert_user(
    conn: aiosqlite.Connection, user_id: int, username: str | None, first_name: str | None
) -> None:
    await conn.execute(
        """
        INSERT INTO users (id, username, first_name, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET username = excluded.username,
                                      first_name = excluded.first_name
        """,
        (user_id, username, first_name, _now()),
    )
    await conn.commit()


async def is_banned(conn: aiosqlite.Connection, user_id: int) -> bool:
    async with conn.execute("SELECT is_banned FROM users WHERE id = ?", (user_id,)) as cur:
        row = await cur.fetchone()
    return bool(row and row["is_banned"])


async def set_banned(conn: aiosqlite.Connection, user_id: int, banned: bool) -> None:
    await conn.execute("UPDATE users SET is_banned = ? WHERE id = ?", (int(banned), user_id))
    await conn.commit()


# --------------------------------------------------------------- orders


async def create_order(
    conn: aiosqlite.Connection,
    *,
    user_id: int,
    product_type: str,
    quantity: int,
    recipient: str,
    price: int,
    currency: str,
) -> Order:
    now = _now()
    cur = await conn.execute(
        """
        INSERT INTO orders (user_id, product_type, quantity, recipient, price, currency,
                            status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, product_type, quantity, recipient, price, currency,
         STATUS_AWAITING_RECEIPT, now, now),
    )
    await conn.commit()
    order = await get_order(conn, cur.lastrowid)
    assert order is not None
    return order


async def get_order(conn: aiosqlite.Connection, order_id: int) -> Order | None:
    async with conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)) as cur:
        row = await cur.fetchone()
    return Order.from_row(row) if row else None


async def list_orders(
    conn: aiosqlite.Connection, *, user_id: int | None = None, status: str | None = None,
    limit: int = 20,
) -> list[Order]:
    sql = "SELECT * FROM orders WHERE 1 = 1"
    params: list[Any] = []
    if user_id is not None:
        sql += " AND user_id = ?"
        params.append(user_id)
    if status is not None:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    async with conn.execute(sql, params) as cur:
        rows = await cur.fetchall()
    return [Order.from_row(row) for row in rows]


async def update_order(conn: aiosqlite.Connection, order_id: int, **fields: Any) -> None:
    if not fields:
        return
    fields["updated_at"] = _now()
    assignments = ", ".join(f"{key} = ?" for key in fields)
    await conn.execute(
        f"UPDATE orders SET {assignments} WHERE id = ?", (*fields.values(), order_id)
    )
    await conn.commit()


async def transition(
    conn: aiosqlite.Connection, order_id: int, *, expected: str, new: str, **fields: Any
) -> bool:
    """Перевести заказ из статуса expected в new.

    Возвращает False, если заказ уже не в статусе expected — так двойной клик
    двух админов по «Подтвердить» не приведёт к двойной выдаче.
    """
    fields["status"] = new
    fields["updated_at"] = _now()
    assignments = ", ".join(f"{key} = ?" for key in fields)
    cur = await conn.execute(
        f"UPDATE orders SET {assignments} WHERE id = ? AND status = ?",
        (*fields.values(), order_id, expected),
    )
    await conn.commit()
    return cur.rowcount > 0


async def stats(conn: aiosqlite.Connection) -> dict[str, Any]:
    async with conn.execute(
        """
        SELECT status, COUNT(*) AS cnt, COALESCE(SUM(price), 0) AS total
        FROM orders GROUP BY status
        """
    ) as cur:
        rows = await cur.fetchall()
    async with conn.execute("SELECT COUNT(*) AS cnt FROM users") as cur:
        users_row = await cur.fetchone()
    by_status = {row["status"]: {"count": row["cnt"], "total": row["total"]} for row in rows}
    revenue = by_status.get(STATUS_DELIVERED, {}).get("total", 0)
    return {"by_status": by_status, "users": users_row["cnt"], "revenue": revenue}
