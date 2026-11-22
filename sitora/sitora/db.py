"""База SQLite: пользователи, заказы, пополнения, движения баланса, карты, настройки."""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,                 -- Telegram ID
  username TEXT NOT NULL DEFAULT '',
  first_name TEXT NOT NULL DEFAULT '',
  lang TEXT NOT NULL DEFAULT 'tj',
  balance INTEGER NOT NULL DEFAULT 0,     -- дирамы
  banned INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  seen_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS users_username ON users(lower(username));
CREATE TABLE IF NOT EXISTS ledger (
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, delta INTEGER NOT NULL, balance_after INTEGER NOT NULL,
  reason TEXT NOT NULL, ref TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL,
  kind TEXT NOT NULL,                    -- stars | premium | gift
  title TEXT NOT NULL, qty INTEGER NOT NULL DEFAULT 1, months INTEGER NOT NULL DEFAULT 0,
  gift_id TEXT NOT NULL DEFAULT '', gift_stars INTEGER NOT NULL DEFAULT 0, gift_text TEXT NOT NULL DEFAULT '',
  recipient TEXT NOT NULL DEFAULT '', recipient_id INTEGER, gift_token TEXT,
  price INTEGER NOT NULL, cost_usd TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL,                  -- new | processing | attention | completed | failed | awaiting_recipient | paid | sending | sent
  supplier_order_id TEXT, tries INTEGER NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS orders_user ON orders(user_id, id);
CREATE INDEX IF NOT EXISTS orders_status ON orders(status);
CREATE UNIQUE INDEX IF NOT EXISTS orders_gift_token ON orders(gift_token);
CREATE TABLE IF NOT EXISTS topups (
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, method TEXT NOT NULL, card_id INTEGER,
  amount INTEGER NOT NULL, status TEXT NOT NULL,   -- waiting | pending | paid | rejected | cancelled
  receipt_file TEXT, receipt_hash TEXT, ai_note TEXT NOT NULL DEFAULT '', intent TEXT NOT NULL DEFAULT '',
  admin_msgs TEXT NOT NULL DEFAULT '', decided_by TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL, resolved_at TEXT
);
CREATE INDEX IF NOT EXISTS topups_status ON topups(status);
CREATE TABLE IF NOT EXISTS cards (
  id INTEGER PRIMARY KEY, method TEXT NOT NULL, details TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS chat_state (user_id INTEGER PRIMARY KEY, state TEXT NOT NULL, data TEXT NOT NULL DEFAULT '{}');
"""

_local = threading.local()
_lock = threading.Lock()


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(path: str) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=15000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init(path: str) -> None:
    conn = connect(path)
    conn.executescript(SCHEMA)
    conn.close()


def conn_for(path: str) -> sqlite3.Connection:
    """Одно соединение на поток."""
    c = getattr(_local, "conns", {}).get(path)
    if c is None:
        c = connect(path)
        _local.conns = {**getattr(_local, "conns", {}), path: c}
    return c


@contextmanager
def tx(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Транзакция с блокировкой на запись: деньги не уйдут дважды."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def get_setting(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row[0] if row else default


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                 (key, str(value)))
