"""Слой доступа к данным (SQLite через aiosqlite).

Все денежные величины — целые числа в дирамах (1 сомони = 100 дирам).
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, fields
from datetime import datetime, timezone
from typing import Any

import logging

import aiosqlite

from app.config import settings

log = logging.getLogger(__name__)

# ---- статусы заказа ----
ORDER_DELIVERING = "delivering"
ORDER_DELIVERED = "delivered"
ORDER_FAILED = "failed"
ORDER_REFUNDED = "refunded"

ORDER_TITLES = {
    ORDER_DELIVERING: "Выдаётся",
    ORDER_DELIVERED: "Выполнен",
    ORDER_FAILED: "Проверяется",
    ORDER_REFUNDED: "Деньги возвращены",
}

#: Ключ значка для каждого статуса — сами значки настраиваются в панели.
ORDER_ICONS = {
    ORDER_DELIVERING: "wait",
    ORDER_DELIVERED: "ok",
    ORDER_FAILED: "search",
    ORDER_REFUNDED: "refund",
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
    source        TEXT,                          -- код Deep Link, приведшей клиента
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS deposits (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    amount          INTEGER NOT NULL,
    method          TEXT NOT NULL,
    receipt_file_id TEXT,
    reference       TEXT,
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
    price             INTEGER NOT NULL,     -- дирамы, сколько заплатил клиент
    cost              INTEGER NOT NULL DEFAULT 0,  -- дирамы, во сколько обошлось нам
    status            TEXT NOT NULL,
    promo             TEXT,                        -- применённый промокод
    discount          INTEGER NOT NULL DEFAULT 0,  -- дирамы, размер скидки
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
    kind       TEXT NOT NULL DEFAULT 'bonus',  -- 'bonus' на баланс | 'discount' скидка
    amount     INTEGER NOT NULL,               -- дирамы, для bonus
    percent    INTEGER NOT NULL DEFAULT 0,     -- проценты, для discount
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

CREATE TABLE IF NOT EXISTS adjustments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    admin_id   INTEGER NOT NULL,
    amount     INTEGER NOT NULL,        -- дирамы, со знаком: минус = списание
    reason     TEXT,
    created_at TEXT NOT NULL
);

-- Отзывы: один завершённый заказ = один отзыв (UNIQUE на order_id).
-- Проверять это в коде мало: две кнопки, нажатые подряд, успели бы
-- проскочить обе.
CREATE TABLE IF NOT EXISTS reviews (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    INTEGER NOT NULL UNIQUE,
    user_id     INTEGER NOT NULL,
    rating      INTEGER NOT NULL,          -- 1..5
    text        TEXT,
    status      TEXT NOT NULL,             -- pending | published | deleted
    channel_msg INTEGER,                   -- id сообщения в канале
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- Кому уже предлагали оставить отзыв. Без этой отметки повторное нажатие
-- кнопки в панели дёргало бы одних и тех же людей снова и снова.
CREATE TABLE IF NOT EXISTS review_asks (
    order_id   INTEGER PRIMARY KEY,
    user_id    INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS links (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    code       TEXT NOT NULL UNIQUE,     -- то, что стоит после ?start=
    created_at TEXT NOT NULL
);

-- Один запуск бота по ссылке. Отсюда все три числа: переходы (все строки),
-- уникальные (разные user_id), новые (is_new = 1).
CREATE TABLE IF NOT EXISTS link_hits (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    link_id    INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    is_new     INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_orders_user    ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_deposits_created ON deposits(created_at);
CREATE INDEX IF NOT EXISTS idx_deposits_user  ON deposits(user_id);
CREATE INDEX IF NOT EXISTS idx_deposits_stat  ON deposits(status);
CREATE INDEX IF NOT EXISTS idx_tickets_user   ON tickets(user_id);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tmsg_ticket    ON ticket_messages(ticket_id);
CREATE INDEX IF NOT EXISTS idx_adj_user      ON adjustments(user_id);
CREATE INDEX IF NOT EXISTS idx_adj_created   ON adjustments(created_at);
CREATE INDEX IF NOT EXISTS idx_rev_status    ON reviews(status);
CREATE INDEX IF NOT EXISTS idx_rev_user      ON reviews(user_id);
CREATE INDEX IF NOT EXISTS idx_hits_link     ON link_hits(link_id);
CREATE INDEX IF NOT EXISTS idx_hits_user     ON link_hits(user_id);
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
    source: str | None = None      # код Deep Link, по которой пришёл


REVIEW_PENDING = "pending"
REVIEW_PUBLISHED = "published"
REVIEW_DELETED = "deleted"


@dataclass
class Review:
    id: int
    order_id: int
    user_id: int
    rating: int
    text: str | None
    status: str
    channel_msg: int | None
    created_at: str
    updated_at: str

    @property
    def stars(self) -> str:
        return "⭐️" * self.rating


@dataclass
class Link:
    id: int
    code: str
    created_at: str


@dataclass
class Deposit:
    id: int
    user_id: int
    amount: int
    method: str
    receipt_file_id: str | None
    reference: str | None
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
    cost: int
    status: str
    fragment_order_id: str | None
    error: str | None
    created_at: str
    updated_at: str
    promo: str | None = None       # применённый промокод
    discount: int = 0              # дирамы, на сколько сбили цену

    @property
    def title(self) -> str:
        if self.product_type == "stars":
            return f"⭐ {self.quantity} звёзд"
        if self.product_type == "steam":
            from app import runtime

            return f"🎮 Steam {self.quantity} {runtime.steam_currency()}"
        return f"👑 Premium {self.quantity} мес."

    @property
    def status_title(self) -> str:
        from app.emoji import em

        icon = em(ORDER_ICONS.get(self.status, "receipt"))
        return f"{icon} {ORDER_TITLES.get(self.status, self.status)}"

    @property
    def is_refunded(self) -> bool:
        return self.status == ORDER_REFUNDED

    @property
    def profit(self) -> int:
        """Прибыль по заказу. 0, если себестоимость не была известна."""
        return self.price - self.cost if self.cost else 0


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


#: Колонки, добавленные после первого выпуска. Ключ — таблица.
MIGRATIONS: dict[str, dict[str, str]] = {
    "orders": {
        "cost": "INTEGER NOT NULL DEFAULT 0",
        "promo": "TEXT",
        "discount": "INTEGER NOT NULL DEFAULT 0",
    },
    "promocodes": {
        "kind": "TEXT NOT NULL DEFAULT 'bonus'",
        "percent": "INTEGER NOT NULL DEFAULT 0",
    },
    "deposits": {"reference": "TEXT"},
    "users": {"source": "TEXT"},
}


async def init(conn: aiosqlite.Connection) -> None:
    await conn.executescript(SCHEMA)
    await _migrate(conn)
    await conn.commit()


async def _migrate(conn: aiosqlite.Connection) -> None:
    """Дописать недостающие колонки в уже существующую базу.

    Без этого обновление бота на работающем сервере падало бы: таблица
    создана по старой схеме, а код ждёт новых полей.
    """
    for table, columns in MIGRATIONS.items():
        async with conn.execute(f"PRAGMA table_info({table})") as cur:
            existing = {row["name"] for row in await cur.fetchall()}
        for name, definition in columns.items():
            if name not in existing:
                await conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
                log.info("База: в таблицу %s добавлена колонка %s", table, name)


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


async def find_user(conn: aiosqlite.Connection, query: str) -> User | None:
    """Найти клиента по ID или юзернейму — под рукой бывает любое из двух."""
    query = query.strip().lstrip("@")
    if query.isdigit():
        found = await get_user(conn, int(query))
        if found:
            return found
    async with conn.execute(
        "SELECT * FROM users WHERE lower(username) = lower(?) LIMIT 1", (query,)
    ) as cur:
        row = await cur.fetchone()
    return _from_row(User, row) if row else None


@dataclass
class Adjustment:
    id: int
    user_id: int
    admin_id: int
    amount: int
    reason: str | None
    created_at: str


async def add_adjustment(
    conn: aiosqlite.Connection, *, user_id: int, admin_id: int,
    amount: int, reason: str = "",
) -> None:
    """Записать ручную правку баланса.

    Без записи такие деньги появлялись бы из ниоткуда, и сойти отчёты
    уже не могли бы.
    """
    await conn.execute(
        """INSERT INTO adjustments (user_id, admin_id, amount, reason, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (user_id, admin_id, amount, reason or None, _now()),
    )
    await conn.commit()


async def list_adjustments(
    conn: aiosqlite.Connection, *, user_id: int | None = None, limit: int = 10
) -> list[Adjustment]:
    sql = "SELECT * FROM adjustments"
    params: list[Any] = []
    if user_id is not None:
        sql += " WHERE user_id = ?"
        params.append(user_id)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    async with conn.execute(sql, params) as cur:
        return [_from_row(Adjustment, row) for row in await cur.fetchall()]


async def adjustments_total(
    conn: aiosqlite.Connection, since: str, until: str
) -> tuple[int, int]:
    """Сколько начислено и списано вручную за период."""
    async with conn.execute(
        """SELECT COALESCE(SUM(CASE WHEN amount > 0 THEN amount END), 0) AS added,
                  COALESCE(SUM(CASE WHEN amount < 0 THEN -amount END), 0) AS taken
           FROM adjustments WHERE created_at >= ? AND created_at < ?""",
        (since, until),
    ) as cur:
        row = await cur.fetchone()
    return row["added"], row["taken"]


async def all_user_ids(conn: aiosqlite.Connection) -> list[int]:
    async with conn.execute("SELECT id FROM users WHERE is_banned = 0") as cur:
        return [row["id"] for row in await cur.fetchall()]


async def top_clients(
    conn: aiosqlite.Connection, limit: int = 10, by: str = "purchases",
) -> list[tuple[User, int]]:
    """Топ клиентов: пары (клиент, сумма) по убыванию суммы.

    by="purchases" — сумма выданных заказов: отменённые и возвращённые
    в неё не попадают, поэтому рейтинг показывает реальных покупателей.
    by="deposits"  — сумма пополнений за всё время.
    """
    if by == "deposits":
        query = """SELECT *, total_deposit AS amount FROM users
                   WHERE total_deposit > 0
                   ORDER BY amount DESC, id LIMIT ?"""
        params: tuple = (limit,)
    else:
        query = """SELECT u.*, SUM(o.price) AS amount
                   FROM users u JOIN orders o ON o.user_id = u.id
                   WHERE o.status = ?
                   GROUP BY u.id
                   ORDER BY amount DESC, u.id LIMIT ?"""
        params = (ORDER_DELIVERED, limit)
    async with conn.execute(query, params) as cur:
        return [(_from_row(User, row), row["amount"]) for row in await cur.fetchall()]


# ---------------------------------------------------------------- отзывы


async def create_review(
    conn: aiosqlite.Connection, *, order_id: int, user_id: int, rating: int,
) -> Review | None:
    """Завести отзыв на заказ. None — если отзыв на него уже есть."""
    now = _now()
    try:
        cur = await conn.execute(
            """INSERT INTO reviews (order_id, user_id, rating, status,
                                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (order_id, user_id, rating, REVIEW_PENDING, now, now),
        )
    except sqlite3.IntegrityError:
        return None
    await conn.commit()
    return await get_review(conn, cur.lastrowid)


async def get_review(conn: aiosqlite.Connection, review_id: int) -> Review | None:
    async with conn.execute("SELECT * FROM reviews WHERE id = ?", (review_id,)) as cur:
        row = await cur.fetchone()
    return _from_row(Review, row) if row else None


async def review_of_order(conn: aiosqlite.Connection, order_id: int) -> Review | None:
    async with conn.execute(
        "SELECT * FROM reviews WHERE order_id = ?", (order_id,)
    ) as cur:
        row = await cur.fetchone()
    return _from_row(Review, row) if row else None


async def set_review_text(conn: aiosqlite.Connection, review_id: int, text: str) -> None:
    await conn.execute(
        "UPDATE reviews SET text = ?, updated_at = ? WHERE id = ?",
        (text, _now(), review_id),
    )
    await conn.commit()


async def moderate_review(
    conn: aiosqlite.Connection, review_id: int, new: str, channel_msg: int | None = None,
) -> bool:
    """Опубликовать или удалить отзыв. False — если его уже разобрали.

    Условие `status = pending` не даёт двум нажатиям подряд опубликовать
    отзыв дважды.
    """
    cur = await conn.execute(
        """UPDATE reviews SET status = ?, channel_msg = ?, updated_at = ?
           WHERE id = ? AND status = ?""",
        (new, channel_msg, _now(), review_id, REVIEW_PENDING),
    )
    await conn.commit()
    return cur.rowcount > 0


async def list_reviews(
    conn: aiosqlite.Connection, status: str | None = None, limit: int = 20,
) -> list[Review]:
    sql = "SELECT * FROM reviews"
    params: list = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    async with conn.execute(sql, params) as cur:
        return [_from_row(Review, row) for row in await cur.fetchall()]


async def review_targets(
    conn: aiosqlite.Connection, limit: int = 500,
) -> list[Order]:
    """Кого ещё можно попросить об отзыве.

    По одному заказу на человека — самому свежему выданному. Пропускаем тех,
    кто уже оставил отзыв, кого уже спрашивали и кто в бане: рассылка не
    должна выглядеть навязчивой.
    """
    async with conn.execute(
        """SELECT o.* FROM orders o
           JOIN users u ON u.id = o.user_id
           WHERE o.status = ?
             AND u.is_banned = 0
             AND o.id NOT IN (SELECT order_id FROM reviews)
             AND o.id NOT IN (SELECT order_id FROM review_asks)
             AND o.id = (SELECT MAX(id) FROM orders x
                         WHERE x.user_id = o.user_id AND x.status = ?)
           ORDER BY o.id DESC LIMIT ?""",
        (ORDER_DELIVERED, ORDER_DELIVERED, limit),
    ) as cur:
        return [_from_row(Order, row) for row in await cur.fetchall()]


async def mark_review_asked(
    conn: aiosqlite.Connection, order_id: int, user_id: int,
) -> None:
    await conn.execute(
        """INSERT OR IGNORE INTO review_asks (order_id, user_id, created_at)
           VALUES (?, ?, ?)""",
        (order_id, user_id, _now()),
    )
    await conn.commit()


async def review_stats(conn: aiosqlite.Connection) -> dict[str, int]:
    async with conn.execute(
        """SELECT COUNT(*)                        AS total,
                  SUM(status = ?)                 AS pending,
                  SUM(status = ?)                 AS published,
                  COALESCE(SUM(rating), 0)        AS rating_sum
           FROM reviews WHERE status != ?""",
        (REVIEW_PENDING, REVIEW_PUBLISHED, REVIEW_DELETED),
    ) as cur:
        row = await cur.fetchone()
    return {key: (row[key] or 0) for key in row.keys()}


# ------------------------------------------------------------ Deep Links


async def create_link(conn: aiosqlite.Connection, code: str) -> Link | None:
    """Завести рекламную ссылку. None — если такая уже есть."""
    try:
        cur = await conn.execute(
            "INSERT INTO links (code, created_at) VALUES (?, ?)", (code, _now()),
        )
    except sqlite3.IntegrityError:
        return None
    await conn.commit()
    return await get_link(conn, cur.lastrowid)


async def get_link(conn: aiosqlite.Connection, link_id: int) -> Link | None:
    async with conn.execute("SELECT * FROM links WHERE id = ?", (link_id,)) as cur:
        row = await cur.fetchone()
    return _from_row(Link, row) if row else None


async def get_link_by_code(conn: aiosqlite.Connection, code: str) -> Link | None:
    async with conn.execute("SELECT * FROM links WHERE code = ?", (code,)) as cur:
        row = await cur.fetchone()
    return _from_row(Link, row) if row else None


async def delete_link(conn: aiosqlite.Connection, link_id: int) -> bool:
    """Убрать ссылку вместе с её переходами. Метка source у клиентов остаётся."""
    cur = await conn.execute("DELETE FROM links WHERE id = ?", (link_id,))
    await conn.execute("DELETE FROM link_hits WHERE link_id = ?", (link_id,))
    await conn.commit()
    return cur.rowcount > 0


async def record_link_hit(
    conn: aiosqlite.Connection, code: str, user_id: int, is_new: bool,
) -> bool:
    """Отметить запуск бота по ссылке.

    Считаем только заведённые в панели коды: чужой ?start=что-угодно не должен
    плодить ссылки. Метку source ставим один раз — засчитываем первый источник,
    иначе последняя реклама воровала бы себе чужого клиента.
    """
    link = await get_link_by_code(conn, code)
    if link is None:
        return False
    await conn.execute(
        "INSERT INTO link_hits (link_id, user_id, is_new, created_at) VALUES (?, ?, ?, ?)",
        (link.id, user_id, int(is_new), _now()),
    )
    await conn.execute(
        "UPDATE users SET source = ? WHERE id = ? AND (source IS NULL OR source = '')",
        (code, user_id),
    )
    await conn.commit()
    return True


async def link_stats(conn: aiosqlite.Connection, link_id: int) -> dict[str, int]:
    """Переходы, уникальные, новые, а также покупатели и выручка с этой ссылки."""
    async with conn.execute(
        """SELECT COUNT(*)                 AS hits,
                  COUNT(DISTINCT user_id)  AS people,
                  COALESCE(SUM(is_new), 0) AS fresh
           FROM link_hits WHERE link_id = ?""",
        (link_id,),
    ) as cur:
        row = await cur.fetchone()
    stats = {key: (row[key] or 0) for key in row.keys()}

    async with conn.execute(
        """SELECT COUNT(DISTINCT o.user_id)   AS buyers,
                  COALESCE(SUM(o.price), 0)   AS revenue
           FROM orders o
           JOIN users u ON u.id = o.user_id
           JOIN links l ON l.code = u.source
           WHERE l.id = ? AND o.status = ?""",
        (link_id, ORDER_DELIVERED),
    ) as cur:
        row = await cur.fetchone()
    stats.update({key: (row[key] or 0) for key in row.keys()})
    return stats


async def list_links(conn: aiosqlite.Connection) -> list[tuple[Link, dict[str, int]]]:
    """Все ссылки, свежие сверху, каждая со своей статистикой."""
    async with conn.execute("SELECT * FROM links ORDER BY id DESC") as cur:
        links = [_from_row(Link, row) for row in await cur.fetchall()]
    return [(link, await link_stats(conn, link.id)) for link in links]


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
    conn: aiosqlite.Connection, *, user_id: int, amount: int, method: str,
    receipt_file_id: str, reference: str | None = None,
) -> Deposit:
    now = _now()
    cur = await conn.execute(
        """INSERT INTO deposits (user_id, amount, method, receipt_file_id,
                                 reference, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, amount, method, receipt_file_id, reference, DEP_PENDING, now, now),
    )
    await conn.commit()
    deposit = await get_deposit(conn, cur.lastrowid)
    assert deposit is not None
    return deposit


async def set_deposit_reference(
    conn: aiosqlite.Connection, deposit_id: int, reference: str,
) -> None:
    await conn.execute(
        "UPDATE deposits SET reference = ?, updated_at = ? WHERE id = ?",
        (reference, _now(), deposit_id),
    )
    await conn.commit()


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
    recipient: str, price: int, cost: int = 0,
    promo: str | None = None, discount: int = 0,
) -> Order:
    now = _now()
    cur = await conn.execute(
        """INSERT INTO orders (user_id, product_type, quantity, recipient, price,
                               cost, status, promo, discount, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, product_type, quantity, recipient, price, cost,
         ORDER_DELIVERING, promo, discount, now, now),
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
    if cur.rowcount == 0:
        return False

    # Активацию промокода списываем здесь, а не при вводе кода: заказ мог
    # сорваться и деньги вернуться — тогда активация не потрачена. Условие
    # `status = expected` выше пропускает только один переход, поэтому
    # дважды один и тот же заказ активацию не съест.
    if new == ORDER_DELIVERED:
        order = await get_order(conn, order_id)
        if order and order.promo:
            await use_promo(conn, order.promo, order.user_id)
    return True


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
    conn: aiosqlite.Connection, code: str, amount: int, max_uses: int,
    kind: str = "bonus", percent: int = 0,
) -> bool:
    """Завести промокод. kind='bonus' — деньги на баланс, 'discount' — скидка."""
    try:
        await conn.execute(
            """INSERT INTO promocodes (code, kind, amount, percent, max_uses, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (code.upper(), kind, amount, percent, max_uses, _now()),
        )
    except aiosqlite.IntegrityError:
        return False
    await conn.commit()
    return True


async def get_promo(conn: aiosqlite.Connection, code: str) -> aiosqlite.Row | None:
    async with conn.execute(
        "SELECT * FROM promocodes WHERE code = ?", (code.upper().strip(),)
    ) as cur:
        return await cur.fetchone()


async def promo_reserved(conn: aiosqlite.Connection, code: str) -> int:
    """Сколько активаций держат незавершённые заказы с этим кодом.

    Активация списывается только после выдачи, поэтому без такого резерва
    сотню заказов можно было бы оформить одновременно на код со лимитом 10.
    """
    async with conn.execute(
        "SELECT COUNT(*) AS n FROM orders WHERE promo = ? AND status IN (?, ?)",
        (code.upper().strip(), ORDER_DELIVERING, ORDER_FAILED),
    ) as cur:
        row = await cur.fetchone()
    return row["n"] or 0


async def check_discount(
    conn: aiosqlite.Connection, code: str, user_id: int
) -> aiosqlite.Row | str:
    """Можно ли применить код к заказу. Строка — причина отказа."""
    promo = await get_promo(conn, code)
    if promo is None:
        return "not_found"
    if promo["kind"] != "discount" or promo["percent"] <= 0:
        return "not_for_order"

    async with conn.execute(
        "SELECT 1 FROM promo_uses WHERE code = ? AND user_id = ?",
        (promo["code"], user_id),
    ) as cur:
        if await cur.fetchone():
            return "already_used"

    left = promo["max_uses"] - promo["used_count"] - await promo_reserved(conn, promo["code"])
    if left <= 0:
        return "exhausted"
    return promo


async def use_promo(conn: aiosqlite.Connection, code: str, user_id: int) -> bool:
    """Списать одну активацию. False — если этот клиент код уже отмечал."""
    code = code.upper().strip()
    cur = await conn.execute(
        "INSERT OR IGNORE INTO promo_uses (code, user_id, created_at) VALUES (?, ?, ?)",
        (code, user_id, _now()),
    )
    if cur.rowcount == 0:
        await conn.commit()
        return False
    # Счётчик не должен перевалить за лимит, даже если заказы шли внахлёст.
    await conn.execute(
        "UPDATE promocodes SET used_count = used_count + 1 "
        "WHERE code = ? AND used_count < max_uses",
        (code,),
    )
    await conn.commit()
    return True


async def delete_promo(conn: aiosqlite.Connection, code: str) -> bool:
    cur = await conn.execute("DELETE FROM promocodes WHERE code = ?", (code.upper(),))
    await conn.commit()
    return cur.rowcount > 0


async def redeem_promo(conn: aiosqlite.Connection, code: str, user_id: int) -> int | str:
    """Активировать промокод. Возвращает сумму в дирамах или строку с причиной отказа."""
    code = code.upper().strip()
    async with conn.execute("SELECT * FROM promocodes WHERE code = ?", (code,)) as cur:
        promo = await cur.fetchone()
    if promo is None:
        return "not_found"
    if promo["kind"] == "discount":
        # Код на скидку вводят при покупке, на баланс он ничего не кладёт.
        return "not_for_balance"

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


# ══════════════════════════════════════════════════════════════ отчёты


async def report(
    conn: aiosqlite.Connection, since: str, until: str
) -> dict[str, Any]:
    """Сводка за период [since, until) по времени UTC в ISO-формате.

    Границы сравниваются строками: ISO-даты сортируются так же, как время,
    поэтому индекс по created_at работает и без разбора дат.
    """
    async with conn.execute(
        """SELECT
             COUNT(*)                                              AS orders,
             COALESCE(SUM(status = ?), 0)                          AS done,
             COALESCE(SUM(status = ?), 0)                          AS refunded,
             COALESCE(SUM(status = ?), 0)                          AS failed,
             COALESCE(SUM(CASE WHEN status = ? THEN price END), 0) AS revenue,
             COALESCE(SUM(CASE WHEN status = ? THEN cost  END), 0) AS cost,
             COALESCE(SUM(CASE WHEN status = ? AND product_type = 'stars'
                               THEN quantity END), 0)              AS stars,
             COALESCE(SUM(CASE WHEN status = ? AND product_type = 'premium'
                               THEN quantity END), 0)              AS premium_months,
             COALESCE(SUM(CASE WHEN status = ? THEN price END), 0) AS refunded_sum
           FROM orders WHERE created_at >= ? AND created_at < ?""",
        (ORDER_DELIVERED, ORDER_REFUNDED, ORDER_FAILED, ORDER_DELIVERED,
         ORDER_DELIVERED, ORDER_DELIVERED, ORDER_DELIVERED, ORDER_REFUNDED,
         since, until),
    ) as cur:
        row = await cur.fetchone()
    data = {key: (row[key] or 0) for key in row.keys()}

    async with conn.execute(
        """SELECT COUNT(*) AS cnt, COALESCE(SUM(amount), 0) AS total
           FROM deposits
           WHERE status = ? AND created_at >= ? AND created_at < ?""",
        (DEP_APPROVED, since, until),
    ) as cur:
        dep = await cur.fetchone()
    data["deposits"] = dep["cnt"]
    data["deposits_sum"] = dep["total"]

    async with conn.execute(
        "SELECT COUNT(*) AS cnt FROM users WHERE created_at >= ? AND created_at < ?",
        (since, until),
    ) as cur:
        data["new_users"] = (await cur.fetchone())["cnt"]

    async with conn.execute(
        """SELECT COUNT(DISTINCT user_id) AS cnt FROM orders
           WHERE status = ? AND created_at >= ? AND created_at < ?""",
        (ORDER_DELIVERED, since, until),
    ) as cur:
        data["buyers"] = (await cur.fetchone())["cnt"]

    added, taken = await adjustments_total(conn, since, until)
    data["adjust_added"] = added
    data["adjust_taken"] = taken

    data["profit"] = data["revenue"] - data["cost"]
    return data


async def daily_series(
    conn: aiosqlite.Connection, since: str, until: str, tz_hours: int
) -> list[tuple[str, int, int, int]]:
    """По дням: дата, выполнено, выручка, прибыль.

    Дата берётся с поправкой на часовой пояс владельца, иначе вечерние
    заказы попадали бы во «вчера».
    """
    shift = f"{tz_hours:+d} hours"
    async with conn.execute(
        f"""SELECT date(created_at, '{shift}') AS day,
                   COUNT(*) AS done,
                   COALESCE(SUM(price), 0) AS revenue,
                   COALESCE(SUM(price - cost), 0) AS profit
            FROM orders
            WHERE status = ? AND created_at >= ? AND created_at < ?
            GROUP BY day ORDER BY day""",
        (ORDER_DELIVERED, since, until),
    ) as cur:
        return [
            (row["day"], row["done"], row["revenue"], row["profit"])
            for row in await cur.fetchall()
        ]


async def find_order_by_external(
    conn: aiosqlite.Connection, external_id: str
) -> Order | None:
    """Найти заказ по номеру на стороне сервиса выдачи."""
    async with conn.execute(
        "SELECT * FROM orders WHERE fragment_order_id = ? ORDER BY id DESC LIMIT 1",
        (str(external_id),),
    ) as cur:
        row = await cur.fetchone()
    return _from_row(Order, row) if row else None
