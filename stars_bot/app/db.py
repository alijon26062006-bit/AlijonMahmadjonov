"""Слой доступа к данным (SQLite через aiosqlite).

Все денежные величины — целые числа в дирамах (1 сомони = 100 дирам).
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime, timezone
from typing import Any

import aiosqlite

from app.config import settings

# ---- статусы заказа ----
ORDER_DELIVERING = "delivering"
ORDER_DELIVERED = "delivered"
ORDER_FAILED = "failed"
ORDER_REFUNDED = "refunded"

ORDER_TITLES = {
    ORDER_DELIVERING: "🚚 Выдаётся",
    ORDER_DELIVERED: "✅ Выполнен",
    ORDER_FAILED: "⚠️ Ошибка",
    ORDER_REFUNDED: "↩️ Возвращён",
}

# ---- статусы пополнения ----
DEP_PENDING = "pending"
DEP_APPROVED = "approved"
DEP_REJECTED = "rejected"

DEP_TITLES = {
    DEP_PENDING: "🔍 На проверке",
    DEP_APPROVED: "✅ Зачислено",
    DEP_REJECTED: "❌ Отклонено",
}

# ---- статусы тикета ----
TICKET_OPEN = "open"
TICKET_CLOSED = "closed"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    username      TEXT,
    first_name    TEXT,
    balance       INTEGER NOT NULL DEFAULT 0,   -- дирамы
    total_deposit INTEGER NOT NULL DEFAULT 0,
    referrer_id   INTEGER,
    ref_earned    INTEGER NOT NULL DEFAULT 0,
    ref_count     INTEGER NOT NULL DEFAULT 0,
    is_banned     INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS deposits (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    amount          INTEGER NOT NULL,
    method          TEXT NOT NULL,
    receipt_file_id TEXT,
    status          TEXT NOT NULL,
    reviewed_by     INTEGER,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER NOT NULL,
    product_type      TEXT NOT NULL,        -- 'stars' | 'premium'
    quantity          INTEGER NOT NULL,     -- звёзд или месяцев
    recipient         TEXT NOT NULL,
    price             INTEGER NOT NULL,     -- дирамы
    status            TEXT NOT NULL,
    fragment_order_id TEXT,
    error             TEXT,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tickets (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    subject    TEXT NOT NULL,
    status     TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ticket_messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id  INTEGER NOT NULL REFERENCES tickets(id),
    sender_id  INTEGER NOT NULL,
    is_admin   INTEGER NOT NULL,
    text       TEXT,
    file_id    TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS promocodes (
    code       TEXT PRIMARY KEY,
    amount     INTEGER NOT NULL,
    max_uses   INTEGER NOT NULL,
    used_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS promo_uses (
    code       TEXT NOT NULL,
    user_id    INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (code, user_id)
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_orders_user    ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_deposits_user  ON deposits(user_id);
CREATE INDEX IF NOT EXISTS idx_deposits_stat  ON deposits(status);
CREATE INDEX IF NOT EXISTS idx_tickets_user   ON tickets(user_id);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tmsg_ticket    ON ticket_messages(ticket_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _from_row(cls, row: aiosqlite.Row):
    return cls(**{f.name: row[f.name] for f in fields(cls)})


@dataclass
class User:
    id: int
    username: str | None
    first_name: str | None
    balance: int
    total_deposit: int
    referrer_id: int | None
    ref_earned: int
    ref_count: int
    is_banned: int
    created_at: str


@dataclass
class Deposit:
    id: int
    user_id: int
    amount: int
    method: str
    receipt_file_id: str | None
    status: str
    reviewed_by: int | None
    created_at: str
    updated_at: str

    @property
    def status_title(self) -> str:
        return DEP_TITLES.get(self.status, self.status)


@dataclass
class Order:
    id: int
    user_id: int
    product_type: str
    quantity: int
    recipient: str
    price: int
    status: str
    fragment_order_id: str | None
    error: str | None
    created_at: str
    updated_at: str

    @property
    def title(self) -> str:
        if self.product_type == "stars":
            return f"⭐ {self.quantity} звёзд"
        return f"👑 Premium {self.quantity} мес."

    @property
    def status_title(self) -> str:
        return ORDER_TITLES.get(self.status, self.status)


@dataclass
class Ticket:
    id: int
    user_id: int
    subject: str
    status: str
    created_at: str
    updated_at: str


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


# ------------------------------------------------------------------ users


async def upsert_user(
    conn: aiosqlite.Connection,
    user_id: int,
    username: str | None,
    first_name: str | None,
    referrer_id: int | None = None,
) -> bool:
    """Создать или обновить пользователя. True — если пользователь новый."""
    async with conn.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)) as cur:
        exists = await cur.fetchone() is not None

    if exists:
        await conn.execute(
            "UPDATE users SET username = ?, first_name = ? WHERE id = ?",
            (username, first_name, user_id),
        )
        await conn.commit()
        return False

    # На себя рефералку не начисляем, и на несуществующего пригласителя тоже.
    if referrer_id == user_id:
        referrer_id = None
    if referrer_id is not None:
        async with conn.execute("SELECT 1 FROM users WHERE id = ?", (referrer_id,)) as cur:
            if await cur.fetchone() is None:
                referrer_id = None

    await conn.execute(
        """INSERT INTO users (id, username, first_name, referrer_id, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (user_id, username, first_name, referrer_id, _now()),
    )
    if referrer_id is not None:
        await conn.execute(
            "UPDATE users SET ref_count = ref_count + 1 WHERE id = ?", (referrer_id,)
        )
    await conn.commit()
    return True


async def get_user(conn: aiosqlite.Connection, user_id: int) -> User | None:
    async with conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)) as cur:
        row = await cur.fetchone()
    return _from_row(User, row) if row else None


async def set_banned(conn: aiosqlite.Connection, user_id: int, banned: bool) -> None:
    await conn.execute("UPDATE users SET is_banned = ? WHERE id = ?", (int(banned), user_id))
    await conn.commit()


async def all_user_ids(conn: aiosqlite.Connection) -> list[int]:
    async with conn.execute("SELECT id FROM users WHERE is_banned = 0") as cur:
        return [row["id"] for row in await cur.fetchall()]


async def top_clients(conn: aiosqlite.Connection, limit: int = 10) -> list[User]:
    async with conn.execute(
        "SELECT * FROM users WHERE total_deposit > 0 ORDER BY total_deposit DESC LIMIT ?",
        (limit,),
    ) as cur:
        return [_from_row(User, row) for row in await cur.fetchall()]


# ---------------------------------------------------------------- деньги


async def charge(conn: aiosqlite.Connection, user_id: int, amount: int) -> bool:
    """Списать amount с баланса. False — если денег не хватило.

    Условие `balance >= ?` внутри UPDATE делает проверку и списание одной
    операцией, поэтому два одновременных заказа не уведут баланс в минус.
    """
    cur = await conn.execute(
        "UPDATE users SET balance = balance - ? WHERE id = ? AND balance >= ?",
        (amount, user_id, amount),
    )
    await conn.commit()
    return cur.rowcount > 0


async def credit(
    conn: aiosqlite.Connection, user_id: int, amount: int, *, as_deposit: bool = False
) -> None:
    """Начислить amount на баланс. as_deposit — учесть в общем депозите."""
    if as_deposit:
        await conn.execute(
            "UPDATE users SET balance = balance + ?, total_deposit = total_deposit + ? WHERE id = ?",
            (amount, amount, user_id),
        )
    else:
        await conn.execute(
            "UPDATE users SET balance = balance + ? WHERE id = ?", (amount, user_id)
        )
    await conn.commit()


async def add_ref_earning(conn: aiosqlite.Connection, user_id: int, amount: int) -> None:
    await conn.execute(
        """UPDATE users SET balance = balance + ?, ref_earned = ref_earned + ?
           WHERE id = ?""",
        (amount, amount, user_id),
    )
    await conn.commit()


# ------------------------------------------------------------- пополнения


async def create_deposit(
    conn: aiosqlite.Connection, *, user_id: int, amount: int, method: str, receipt_file_id: str
) -> Deposit:
    now = _now()
    cur = await conn.execute(
        """INSERT INTO deposits (user_id, amount, method, receipt_file_id, status,
                                 created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (user_id, amount, method, receipt_file_id, DEP_PENDING, now, now),
    )
    await conn.commit()
    deposit = await get_deposit(conn, cur.lastrowid)
    assert deposit is not None
    return deposit


async def get_deposit(conn: aiosqlite.Connection, deposit_id: int) -> Deposit | None:
    async with conn.execute("SELECT * FROM deposits WHERE id = ?", (deposit_id,)) as cur:
        row = await cur.fetchone()
    return _from_row(Deposit, row) if row else None


async def list_deposits(
    conn: aiosqlite.Connection, *, user_id: int | None = None, status: str | None = None,
    limit: int = 15,
) -> list[Deposit]:
    sql = "SELECT * FROM deposits WHERE 1 = 1"
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
        return [_from_row(Deposit, row) for row in await cur.fetchall()]


async def resolve_deposit(
    conn: aiosqlite.Connection, deposit_id: int, *, approved: bool, admin_id: int
) -> bool:
    """Перевести пополнение из pending в approved/rejected.

    False — если кто-то уже обработал заявку (защита от двойного зачисления).
    """
    cur = await conn.execute(
        """UPDATE deposits SET status = ?, reviewed_by = ?, updated_at = ?
           WHERE id = ? AND status = ?""",
        (DEP_APPROVED if approved else DEP_REJECTED, admin_id, _now(), deposit_id, DEP_PENDING),
    )
    await conn.commit()
    return cur.rowcount > 0


# ----------------------------------------------------------------- заказы


async def create_order(
    conn: aiosqlite.Connection, *, user_id: int, product_type: str, quantity: int,
    recipient: str, price: int,
) -> Order:
    now = _now()
    cur = await conn.execute(
        """INSERT INTO orders (user_id, product_type, quantity, recipient, price,
                               status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, product_type, quantity, recipient, price, ORDER_DELIVERING, now, now),
    )
    await conn.commit()
    order = await get_order(conn, cur.lastrowid)
    assert order is not None
    return order


async def get_order(conn: aiosqlite.Connection, order_id: int) -> Order | None:
    async with conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)) as cur:
        row = await cur.fetchone()
    return _from_row(Order, row) if row else None


async def list_orders(
    conn: aiosqlite.Connection, *, user_id: int | None = None, status: str | None = None,
    limit: int = 15,
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
        return [_from_row(Order, row) for row in await cur.fetchall()]


async def update_order(conn: aiosqlite.Connection, order_id: int, **fields_: Any) -> None:
    if not fields_:
        return
    fields_["updated_at"] = _now()
    assignments = ", ".join(f"{key} = ?" for key in fields_)
    await conn.execute(
        f"UPDATE orders SET {assignments} WHERE id = ?", (*fields_.values(), order_id)
    )
    await conn.commit()


async def transition_order(
    conn: aiosqlite.Connection, order_id: int, *, expected: str, new: str, **fields_: Any
) -> bool:
    fields_["status"] = new
    fields_["updated_at"] = _now()
    assignments = ", ".join(f"{key} = ?" for key in fields_)
    cur = await conn.execute(
        f"UPDATE orders SET {assignments} WHERE id = ? AND status = ?",
        (*fields_.values(), order_id, expected),
    )
    await conn.commit()
    return cur.rowcount > 0


async def user_order_stats(conn: aiosqlite.Connection, user_id: int) -> dict[str, int]:
    async with conn.execute(
        """SELECT
             COUNT(*)                                                        AS total,
             SUM(status = ?)                                                 AS done,
             SUM(status = ?)                                                 AS active,
             COALESCE(SUM(CASE WHEN product_type = 'stars' AND status = ?
                               THEN quantity END), 0)                        AS stars,
             COALESCE(SUM(CASE WHEN product_type = 'stars' AND status = ?
                               THEN price END), 0)                           AS stars_spent,
             COALESCE(SUM(CASE WHEN product_type = 'premium' AND status = ?
                               THEN 1 END), 0)                               AS premium,
             COALESCE(SUM(CASE WHEN product_type = 'premium' AND status = ?
                               THEN price END), 0)                           AS premium_spent
           FROM orders WHERE user_id = ?""",
        (ORDER_DELIVERED, ORDER_DELIVERING, ORDER_DELIVERED, ORDER_DELIVERED,
         ORDER_DELIVERED, ORDER_DELIVERED, user_id),
    ) as cur:
        row = await cur.fetchone()
    return {key: (row[key] or 0) for key in row.keys()}


# ----------------------------------------------------------------- тикеты


async def create_ticket(conn: aiosqlite.Connection, user_id: int, subject: str) -> Ticket:
    now = _now()
    cur = await conn.execute(
        "INSERT INTO tickets (user_id, subject, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, subject, TICKET_OPEN, now, now),
    )
    await conn.commit()
    ticket = await get_ticket(conn, cur.lastrowid)
    assert ticket is not None
    return ticket


async def get_ticket(conn: aiosqlite.Connection, ticket_id: int) -> Ticket | None:
    async with conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)) as cur:
        row = await cur.fetchone()
    return _from_row(Ticket, row) if row else None


async def list_tickets(
    conn: aiosqlite.Connection, *, user_id: int | None = None, status: str | None = None,
    limit: int = 15,
) -> list[Ticket]:
    sql = "SELECT * FROM tickets WHERE 1 = 1"
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
        return [_from_row(Ticket, row) for row in await cur.fetchall()]


async def add_ticket_message(
    conn: aiosqlite.Connection, ticket_id: int, sender_id: int, *, is_admin: bool,
    text: str | None = None, file_id: str | None = None,
) -> None:
    now = _now()
    await conn.execute(
        """INSERT INTO ticket_messages (ticket_id, sender_id, is_admin, text, file_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (ticket_id, sender_id, int(is_admin), text, file_id, now),
    )
    await conn.execute("UPDATE tickets SET updated_at = ? WHERE id = ?", (now, ticket_id))
    await conn.commit()


async def close_ticket(conn: aiosqlite.Connection, ticket_id: int) -> bool:
    cur = await conn.execute(
        "UPDATE tickets SET status = ?, updated_at = ? WHERE id = ? AND status = ?",
        (TICKET_CLOSED, _now(), ticket_id, TICKET_OPEN),
    )
    await conn.commit()
    return cur.rowcount > 0


async def count_open_tickets(conn: aiosqlite.Connection, user_id: int) -> int:
    async with conn.execute(
        "SELECT COUNT(*) AS cnt FROM tickets WHERE user_id = ? AND status = ?",
        (user_id, TICKET_OPEN),
    ) as cur:
        return (await cur.fetchone())["cnt"]


# ------------------------------------------------------------- промокоды


async def create_promo(
    conn: aiosqlite.Connection, code: str, amount: int, max_uses: int
) -> bool:
    try:
        await conn.execute(
            "INSERT INTO promocodes (code, amount, max_uses, created_at) VALUES (?, ?, ?, ?)",
            (code.upper(), amount, max_uses, _now()),
        )
    except aiosqlite.IntegrityError:
        return False
    await conn.commit()
    return True


async def redeem_promo(conn: aiosqlite.Connection, code: str, user_id: int) -> int | str:
    """Активировать промокод. Возвращает сумму в дирамах или строку с причиной отказа."""
    code = code.upper().strip()
    async with conn.execute("SELECT * FROM promocodes WHERE code = ?", (code,)) as cur:
        promo = await cur.fetchone()
    if promo is None:
        return "not_found"

    async with conn.execute(
        "SELECT 1 FROM promo_uses WHERE code = ? AND user_id = ?", (code, user_id)
    ) as cur:
        if await cur.fetchone():
            return "already_used"

    # Счётчик увеличиваем условием used_count < max_uses — так последний
    # оставшийся код не достанется двоим сразу.
    cur = await conn.execute(
        "UPDATE promocodes SET used_count = used_count + 1 WHERE code = ? AND used_count < max_uses",
        (code,),
    )
    if cur.rowcount == 0:
        await conn.commit()
        return "exhausted"

    try:
        await conn.execute(
            "INSERT INTO promo_uses (code, user_id, created_at) VALUES (?, ?, ?)",
            (code, user_id, _now()),
        )
    except aiosqlite.IntegrityError:
        await conn.execute(
            "UPDATE promocodes SET used_count = used_count - 1 WHERE code = ?", (code,)
        )
        await conn.commit()
        return "already_used"

    await conn.execute(
        "UPDATE users SET balance = balance + ? WHERE id = ?", (promo["amount"], user_id)
    )
    await conn.commit()
    return int(promo["amount"])


async def list_promos(conn: aiosqlite.Connection, limit: int = 20) -> list[aiosqlite.Row]:
    async with conn.execute(
        "SELECT * FROM promocodes ORDER BY rowid DESC LIMIT ?", (limit,)
    ) as cur:
        return list(await cur.fetchall())


# --------------------------------------------------------------- сводка


async def global_stats(conn: aiosqlite.Connection) -> dict[str, Any]:
    async with conn.execute("SELECT COUNT(*) AS c FROM users") as cur:
        users = (await cur.fetchone())["c"]
    async with conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS s FROM deposits WHERE status = ?", (DEP_APPROVED,)
    ) as cur:
        deposits = (await cur.fetchone())["s"]
    async with conn.execute(
        """SELECT COUNT(*) AS c, COALESCE(SUM(price), 0) AS s
           FROM orders WHERE status = ?""", (ORDER_DELIVERED,)
    ) as cur:
        row = await cur.fetchone()
    async with conn.execute(
        "SELECT COUNT(*) AS c FROM deposits WHERE status = ?", (DEP_PENDING,)
    ) as cur:
        pending = (await cur.fetchone())["c"]
    async with conn.execute(
        "SELECT COUNT(*) AS c FROM tickets WHERE status = ?", (TICKET_OPEN,)
    ) as cur:
        open_tickets = (await cur.fetchone())["c"]
    async with conn.execute(
        "SELECT COUNT(*) AS c FROM orders WHERE status = ?", (ORDER_FAILED,)
    ) as cur:
        failed = (await cur.fetchone())["c"]
    async with conn.execute("SELECT COALESCE(SUM(balance), 0) AS s FROM users") as cur:
        held = (await cur.fetchone())["s"]
    return {
        "users": users, "deposits": deposits, "orders": row["c"], "revenue": row["s"],
        "pending_deposits": pending, "open_tickets": open_tickets,
        "failed_orders": failed, "held_balance": held,
    }
