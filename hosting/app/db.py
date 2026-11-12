"""SQLite: схема и маленькие помощники. Деньги хранятся в центах (целые числа)."""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL DEFAULT '',
    pw_hash       TEXT NOT NULL,
    is_admin      INTEGER NOT NULL DEFAULT 0,
    balance_cents INTEGER NOT NULL DEFAULT 0,
    created_at    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    csrf       TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    ip         TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS servers (
    id               INTEGER PRIMARY KEY,
    user_id          INTEGER NOT NULL REFERENCES users(id),
    name             TEXT NOT NULL,
    plan             TEXT NOT NULL,
    location         TEXT NOT NULL,
    image            TEXT NOT NULL,
    provider         TEXT NOT NULL,
    provider_id      TEXT NOT NULL DEFAULT '',
    ipv4             TEXT NOT NULL DEFAULT '',
    ipv6             TEXT NOT NULL DEFAULT '',
    status           TEXT NOT NULL DEFAULT 'creating',
    price_cents      INTEGER NOT NULL,
    paid_until       INTEGER NOT NULL,
    suspended        INTEGER NOT NULL DEFAULT 0,
    agent_token_hash TEXT NOT NULL DEFAULT '',
    ssh_hostkey      TEXT NOT NULL DEFAULT '',
    password_state   TEXT NOT NULL DEFAULT '',
    created_at       INTEGER NOT NULL,
    deleted_at       INTEGER
);
CREATE INDEX IF NOT EXISTS servers_user ON servers(user_id);

CREATE TABLE IF NOT EXISTS domains (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    name        TEXT NOT NULL UNIQUE,
    kind        TEXT NOT NULL,            -- registered | external
    price_cents INTEGER NOT NULL DEFAULT 0,
    expires_at  INTEGER,
    auto_renew  INTEGER NOT NULL DEFAULT 1,
    status      TEXT NOT NULL DEFAULT 'active',
    created_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS dns_records (
    id         INTEGER PRIMARY KEY,
    domain_id  INTEGER NOT NULL REFERENCES domains(id) ON DELETE CASCADE,
    type       TEXT NOT NULL,
    name       TEXT NOT NULL,
    value      TEXT NOT NULL,
    ttl        INTEGER NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS dns_domain ON dns_records(domain_id);

CREATE TABLE IF NOT EXISTS transactions (
    id           INTEGER PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id),
    amount_cents INTEGER NOT NULL,
    kind         TEXT NOT NULL,           -- topup | charge | refund | admin
    description  TEXT NOT NULL,
    created_at   INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS tx_user ON transactions(user_id);

CREATE TABLE IF NOT EXISTS agent_metrics (
    server_id  INTEGER NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
    ts         INTEGER NOT NULL,
    mem_used   INTEGER NOT NULL,
    mem_total  INTEGER NOT NULL,
    disk_used  INTEGER NOT NULL,
    disk_total INTEGER NOT NULL,
    load1      REAL NOT NULL,
    procs      TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS agent_ts ON agent_metrics(server_id, ts);

CREATE TABLE IF NOT EXISTS audit (
    id         INTEGER PRIMARY KEY,
    user_id    INTEGER,
    action     TEXT NOT NULL,
    target     TEXT NOT NULL DEFAULT '',
    ip         TEXT NOT NULL DEFAULT '',
    created_at INTEGER NOT NULL
);
"""


def now() -> int:
    return int(time.time())


class Database:
    """Одно соединение на поток; SQLite в режиме WAL спокойно держит панель хостинга."""

    def __init__(self, path: str):
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._lock = threading.RLock()
        self._shared: sqlite3.Connection | None = None
        if path == ":memory:":
            # Для тестов: одна общая база в памяти.
            self._shared = self._connect()
        with self.conn() as c:
            c.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None, timeout=30)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        if self.path != ":memory:":
            c.execute("PRAGMA journal_mode = WAL")
        return c

    def conn(self) -> sqlite3.Connection:
        if self._shared is not None:
            return self._shared
        c = getattr(self._local, "c", None)
        if c is None:
            c = self._connect()
            self._local.c = c
        return c

    # ── помощники ──
    def one(self, sql: str, params: Iterable[Any] = ()) -> dict | None:
        with self._lock:
            row = self.conn().execute(sql, tuple(params)).fetchone()
        return dict(row) if row else None

    def all(self, sql: str, params: Iterable[Any] = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self.conn().execute(sql, tuple(params)).fetchall()]

    def run(self, sql: str, params: Iterable[Any] = ()) -> int:
        """Выполняет запрос и возвращает lastrowid."""
        with self._lock:
            cur = self.conn().execute(sql, tuple(params))
            return cur.lastrowid or 0

    def transaction(self):
        return _Tx(self)

    def audit(self, user_id: int | None, action: str, target: str = "", ip: str = "") -> None:
        self.run("INSERT INTO audit(user_id, action, target, ip, created_at) VALUES (?,?,?,?,?)",
                 (user_id, action, target, ip, now()))

    # ── деньги ──
    def charge(self, user_id: int, cents: int, description: str) -> bool:
        """Списывает сумму, если хватает баланса. Атомарно."""
        with self.transaction():
            cur = self.conn().execute(
                "UPDATE users SET balance_cents = balance_cents - ? WHERE id = ? AND balance_cents >= ?",
                (cents, user_id, cents))
            if cur.rowcount != 1:
                return False
            self.conn().execute(
                "INSERT INTO transactions(user_id, amount_cents, kind, description, created_at) VALUES (?,?,?,?,?)",
                (user_id, -cents, "charge", description, now()))
        return True

    def credit(self, user_id: int, cents: int, kind: str, description: str) -> None:
        with self.transaction():
            self.conn().execute("UPDATE users SET balance_cents = balance_cents + ? WHERE id = ?", (cents, user_id))
            self.conn().execute(
                "INSERT INTO transactions(user_id, amount_cents, kind, description, created_at) VALUES (?,?,?,?,?)",
                (user_id, cents, kind, description, now()))


class _Tx:
    def __init__(self, db: Database):
        self.db = db

    def __enter__(self):
        self.db._lock.acquire()
        self.db.conn().execute("BEGIN IMMEDIATE")
        return self.db

    def __exit__(self, exc_type, exc, tb):
        try:
            self.db.conn().execute("ROLLBACK" if exc_type else "COMMIT")
        finally:
            self.db._lock.release()
        return False
