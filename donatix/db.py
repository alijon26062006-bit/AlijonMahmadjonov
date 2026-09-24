"""SQLite: схема и подключение. Каждый запрос/поток открывает своё соединение.

Деньги — целые числа в «микро» (см. money.py). Все изменения баланса идут
в одной транзакции с записью в журнал transactions."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY,
    email           TEXT NOT NULL UNIQUE,
    login           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'client',   -- client | admin
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending | active | blocked
    tier            TEXT NOT NULL DEFAULT 'bronze',   -- bronze | silver | gold
    markup_override TEXT,                             -- своя наценка в %, если задана
    balance_micro   INTEGER NOT NULL DEFAULT 0,
    webhook_url     TEXT,
    webhook_secret  TEXT,
    project         TEXT,             -- о проекте клиента, из заявки
    created_at      TEXT NOT NULL,
    last_active_at  TEXT
);

CREATE TABLE IF NOT EXISTS api_keys (
    id           INTEGER PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id),
    name         TEXT NOT NULL,
    prefix       TEXT NOT NULL,
    key_hash     TEXT NOT NULL UNIQUE,
    created_at   TEXT NOT NULL,
    last_used_at TEXT,
    revoked_at   TEXT
);

CREATE TABLE IF NOT EXISTS products (
    id                TEXT PRIMARY KEY,
    kind              TEXT NOT NULL,     -- telegram_stars | telegram_premium | topup | gift_card
    category_id       TEXT NOT NULL,
    category_name     TEXT NOT NULL,
    name              TEXT NOT NULL,
    base_price        TEXT NOT NULL,     -- закупка за единицу, Decimal строкой
    unit              TEXT NOT NULL DEFAULT 'item',
    min_qty           INTEGER NOT NULL DEFAULT 1,
    max_qty           INTEGER NOT NULL DEFAULT 1,
    stock             INTEGER,           -- NULL — без ограничения
    image_url         TEXT,              -- обложка из каталога поставщика
    fields_json       TEXT NOT NULL DEFAULT '[]',
    supplier_ref_json TEXT NOT NULL DEFAULT '{}',
    active            INTEGER NOT NULL DEFAULT 1,
    hidden            INTEGER NOT NULL DEFAULT 0,  -- скрыт админом
    updated_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS products_kind ON products(kind, active);

CREATE TABLE IF NOT EXISTS orders (
    id                INTEGER PRIMARY KEY,
    public_id         TEXT UNIQUE,
    user_id           INTEGER NOT NULL REFERENCES users(id),
    product_id        TEXT NOT NULL,
    kind              TEXT NOT NULL,
    product_name      TEXT NOT NULL,
    quantity          INTEGER NOT NULL,
    fields_json       TEXT NOT NULL DEFAULT '{}',
    unit_price        TEXT NOT NULL,
    total_micro       INTEGER NOT NULL,
    cost_micro        INTEGER NOT NULL,
    status            TEXT NOT NULL,     -- processing | completed | failed | attention
    supplier_idem_key TEXT NOT NULL UNIQUE,
    supplier_order_id TEXT,
    supplier_status   TEXT,
    supplier_attempts INTEGER NOT NULL DEFAULT 0,
    idempotent_supply INTEGER NOT NULL DEFAULT 1,
    delivery_json     TEXT,
    error             TEXT,
    client_idem_key   TEXT,
    source            TEXT NOT NULL DEFAULT 'api',   -- api | panel
    webhook_state     TEXT NOT NULL DEFAULT 'none',  -- none | pending | sent | failed
    webhook_attempts  INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    completed_at      TEXT,
    UNIQUE (user_id, client_idem_key)
);
CREATE INDEX IF NOT EXISTS orders_user ON orders(user_id, id DESC);
CREATE INDEX IF NOT EXISTS orders_status ON orders(status);

CREATE TABLE IF NOT EXISTS transactions (
    id                  INTEGER PRIMARY KEY,
    user_id             INTEGER NOT NULL REFERENCES users(id),
    type                TEXT NOT NULL,     -- credit | debit
    amount_micro        INTEGER NOT NULL,  -- со знаком
    balance_before      INTEGER NOT NULL,
    balance_after       INTEGER NOT NULL,
    note                TEXT NOT NULL,
    order_id            INTEGER REFERENCES orders(id),
    created_by          INTEGER REFERENCES users(id),
    created_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS tx_user ON transactions(user_id, id DESC);

CREATE TABLE IF NOT EXISTS steam_gift_games (
    appid   INTEGER PRIMARY KEY,
    name    TEXT NOT NULL,
    name_lc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS payments (
    id            INTEGER PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id),
    method        TEXT NOT NULL,
    amount_micro  INTEGER NOT NULL,             -- сколько зачислить, USD
    pay_amount    TEXT NOT NULL,                -- сколько перевести, в валюте способа
    pay_currency  TEXT NOT NULL,
    reference     TEXT,                         -- что указал клиент: номер чека, хэш и т.п.
    status        TEXT NOT NULL DEFAULT 'pending',  -- pending | paid | rejected | cancelled
    admin_note    TEXT,
    tx_id         INTEGER REFERENCES transactions(id),
    created_at    TEXT NOT NULL,
    resolved_at   TEXT,
    resolved_by   INTEGER REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS payments_status ON payments(status, id DESC);

CREATE TABLE IF NOT EXISTS notifications (
    id         INTEGER PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    text       TEXT NOT NULL,
    link       TEXT,
    created_at TEXT NOT NULL,
    read_at    TEXT
);
CREATE INDEX IF NOT EXISTS notifications_user ON notifications(user_id, id DESC);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def connect(path: Path | str) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Соединение живёт в пределах одного запроса, но FastAPI может открыть и закрыть
    # его в разных потоках — поэтому check_same_thread=False.
    conn = sqlite3.connect(path, timeout=15, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=15000")
    return conn


def init(path: Path | str) -> None:
    conn = connect(path)
    try:
        conn.executescript(_SCHEMA)
        row = conn.execute("SELECT version FROM schema_version").fetchone()
        if row is None:
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
        cols = {r[1] for r in conn.execute("PRAGMA table_info(products)")}
        if "image_url" not in cols:  # база, созданная до появления картинок
            conn.execute("ALTER TABLE products ADD COLUMN image_url TEXT")
    finally:
        conn.close()


@contextmanager
def tx(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Транзакция с немедленной блокировкой записи: два заказа одного клиента
    не прочитают один и тот же баланс."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def get_setting(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
