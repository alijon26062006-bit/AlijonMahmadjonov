"""Хранилище: SQLite. Ничего не удаляем насовсем — только помечаем.

Каждый чат считает отдельно: свои люди, свои смены, свои записи.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS chats (
    chat_id           INTEGER PRIMARY KEY,
    title             TEXT    NOT NULL DEFAULT '',
    active_worker_id  INTEGER,
    session_id        INTEGER,
    pending_kind      TEXT,
    pending_payload   TEXT,
    created_at        TEXT    NOT NULL,
    updated_at        TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id     INTEGER NOT NULL,
    title       TEXT    NOT NULL,
    started_at  TEXT    NOT NULL,
    closed_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_chat ON sessions(chat_id, id DESC);

CREATE TABLE IF NOT EXISTS workers (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id    INTEGER NOT NULL,
    name       TEXT    NOT NULL,
    name_key   TEXT    NOT NULL DEFAULT '',
    archived   INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL
);
-- Уникальный индекс по name_key создаётся в _migrate: у старых баз этой
-- колонки ещё нет, и здесь запрос бы упал.

CREATE TABLE IF NOT EXISTS entries (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id    INTEGER NOT NULL,
    session_id INTEGER NOT NULL,
    worker_id  INTEGER NOT NULL,
    amount     INTEGER NOT NULL,          -- в сотых
    raw_text   TEXT    NOT NULL DEFAULT '',
    source     TEXT    NOT NULL DEFAULT 'voice',
    author_id  INTEGER,
    deleted    INTEGER NOT NULL DEFAULT 0,
    edited     INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL,
    updated_at TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_entries_session ON entries(session_id, deleted, id);
CREATE INDEX IF NOT EXISTS idx_entries_worker  ON entries(worker_id, deleted, id);
CREATE INDEX IF NOT EXISTS idx_entries_chat    ON entries(chat_id, deleted, id DESC);
"""

_LOCKS: dict[int, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


def _lock_for(conn: sqlite3.Connection) -> threading.RLock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(id(conn), threading.RLock())


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")   # выключат свет — записи не пропадут
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    _migrate(conn)
    conn.commit()
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Дотянуть базы, созданные прошлыми версиями."""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(workers)")}
    if "name_key" not in columns:
        conn.execute("ALTER TABLE workers ADD COLUMN name_key TEXT NOT NULL DEFAULT ''")
    for row in conn.execute("SELECT id, name FROM workers WHERE name_key=''").fetchall():
        conn.execute("UPDATE workers SET name_key=? WHERE id=?", (name_key(row["name"]), row["id"]))
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_workers_key ON workers(chat_id, name_key)"
    )


def _write(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
    with _lock_for(conn):
        cursor = conn.execute(sql, tuple(params))
        conn.commit()
        return cursor


# ── Чат ────────────────────────────────────────────────────────────────────
def ensure_chat(conn: sqlite3.Connection, chat_id: int, title: str = "") -> sqlite3.Row:
    row = conn.execute("SELECT * FROM chats WHERE chat_id=?", (chat_id,)).fetchone()
    if row is None:
        stamp = now()
        _write(
            conn,
            "INSERT INTO chats(chat_id, title, created_at, updated_at) VALUES(?,?,?,?)",
            (chat_id, title, stamp, stamp),
        )
        row = conn.execute("SELECT * FROM chats WHERE chat_id=?", (chat_id,)).fetchone()
    elif title and row["title"] != title:
        _write(conn, "UPDATE chats SET title=?, updated_at=? WHERE chat_id=?", (title, now(), chat_id))
        row = conn.execute("SELECT * FROM chats WHERE chat_id=?", (chat_id,)).fetchone()
    return row


def _set_chat(conn: sqlite3.Connection, chat_id: int, **fields: Any) -> None:
    if not fields:
        return
    ensure_chat(conn, chat_id)
    assignments = ", ".join(f"{key}=?" for key in fields)
    _write(
        conn,
        f"UPDATE chats SET {assignments}, updated_at=? WHERE chat_id=?",
        (*fields.values(), now(), chat_id),
    )


# ── Смены ──────────────────────────────────────────────────────────────────
def current_session(conn: sqlite3.Connection, chat_id: int, tz=timezone.utc) -> sqlite3.Row:
    chat = ensure_chat(conn, chat_id)
    if chat["session_id"]:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id=? AND closed_at IS NULL", (chat["session_id"],)
        ).fetchone()
        if row is not None:
            return row
    return start_session(conn, chat_id, tz=tz)


def default_session_title(tz=timezone.utc) -> str:
    return "Смена " + datetime.now(tz).strftime("%d.%m.%Y %H:%M")


def start_session(
    conn: sqlite3.Connection, chat_id: int, title: str | None = None, tz=timezone.utc
) -> sqlite3.Row:
    chat = ensure_chat(conn, chat_id)
    if chat["session_id"]:
        _write(
            conn,
            "UPDATE sessions SET closed_at=? WHERE id=? AND closed_at IS NULL",
            (now(), chat["session_id"]),
        )
    cursor = _write(
        conn,
        "INSERT INTO sessions(chat_id, title, started_at) VALUES(?,?,?)",
        (chat_id, title or default_session_title(tz), now()),
    )
    _set_chat(conn, chat_id, session_id=cursor.lastrowid)
    return conn.execute("SELECT * FROM sessions WHERE id=?", (cursor.lastrowid,)).fetchone()


def get_session(conn: sqlite3.Connection, session_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()


def list_sessions(conn: sqlite3.Connection, chat_id: int, limit: int = 20) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM sessions WHERE chat_id=? ORDER BY id DESC LIMIT ?", (chat_id, limit)
    ).fetchall()


# ── Люди ───────────────────────────────────────────────────────────────────
def clean_name(name: str) -> str:
    return " ".join((name or "").split())[:40]


def name_key(name: str) -> str:
    """Ключ для сравнения имён: «Иброхим», «иброхим» и «ИБРОХИМ» — один человек."""
    return clean_name(name).casefold()


def add_worker(conn: sqlite3.Connection, chat_id: int, name: str) -> tuple[sqlite3.Row | None, str]:
    """Вернуть (человек, статус). Статус: created | restored | exists | bad_name."""
    name = clean_name(name)
    if not name:
        return None, "bad_name"
    ensure_chat(conn, chat_id)
    row = conn.execute(
        "SELECT * FROM workers WHERE chat_id=? AND name_key=?", (chat_id, name_key(name))
    ).fetchone()
    if row is not None:
        if row["archived"]:
            _write(conn, "UPDATE workers SET archived=0 WHERE id=?", (row["id"],))
            return get_worker(conn, row["id"]), "restored"
        return row, "exists"
    cursor = _write(
        conn,
        "INSERT INTO workers(chat_id, name, name_key, created_at) VALUES(?,?,?,?)",
        (chat_id, name, name_key(name), now()),
    )
    return get_worker(conn, cursor.lastrowid), "created"


def get_worker(conn: sqlite3.Connection, worker_id: int | None) -> sqlite3.Row | None:
    if not worker_id:
        return None
    return conn.execute("SELECT * FROM workers WHERE id=?", (worker_id,)).fetchone()


def list_workers(
    conn: sqlite3.Connection, chat_id: int, include_archived: bool = False
) -> list[sqlite3.Row]:
    sql = "SELECT * FROM workers WHERE chat_id=?"
    if not include_archived:
        sql += " AND archived=0"
    sql += " ORDER BY archived, id"
    return conn.execute(sql, (chat_id,)).fetchall()


def rename_worker(conn: sqlite3.Connection, worker_id: int, name: str) -> str:
    name = clean_name(name)
    if not name:
        return "bad_name"
    worker = get_worker(conn, worker_id)
    if worker is None:
        return "missing"
    clash = conn.execute(
        "SELECT id FROM workers WHERE chat_id=? AND name_key=? AND id<>?",
        (worker["chat_id"], name_key(name), worker_id),
    ).fetchone()
    if clash is not None:
        return "exists"
    _write(
        conn,
        "UPDATE workers SET name=?, name_key=? WHERE id=?",
        (name, name_key(name), worker_id),
    )
    return "ok"


def archive_worker(conn: sqlite3.Connection, worker_id: int) -> None:
    worker = get_worker(conn, worker_id)
    if worker is None:
        return
    _write(conn, "UPDATE workers SET archived=1 WHERE id=?", (worker_id,))
    chat = ensure_chat(conn, worker["chat_id"])
    if chat["active_worker_id"] == worker_id:
        _set_chat(conn, worker["chat_id"], active_worker_id=None)


def set_active_worker(conn: sqlite3.Connection, chat_id: int, worker_id: int | None) -> None:
    _set_chat(conn, chat_id, active_worker_id=worker_id)


def active_worker(conn: sqlite3.Connection, chat_id: int) -> sqlite3.Row | None:
    chat = ensure_chat(conn, chat_id)
    worker = get_worker(conn, chat["active_worker_id"])
    if worker is None or worker["archived"]:
        return None
    return worker


# ── Что бот ждёт от пользователя ───────────────────────────────────────────
def set_pending(
    conn: sqlite3.Connection, chat_id: int, kind: str | None, payload: str | None = None
) -> None:
    _set_chat(conn, chat_id, pending_kind=kind, pending_payload=payload)


def get_pending(conn: sqlite3.Connection, chat_id: int) -> tuple[str | None, str | None]:
    chat = ensure_chat(conn, chat_id)
    return chat["pending_kind"], chat["pending_payload"]


# ── Записи ─────────────────────────────────────────────────────────────────
def add_entry(
    conn: sqlite3.Connection,
    *,
    chat_id: int,
    session_id: int,
    worker_id: int,
    amount: int,
    raw_text: str = "",
    source: str = "voice",
    author_id: int | None = None,
) -> sqlite3.Row:
    stamp = now()
    cursor = _write(
        conn,
        """INSERT INTO entries(chat_id, session_id, worker_id, amount, raw_text,
                               source, author_id, created_at, updated_at)
           VALUES(?,?,?,?,?,?,?,?,?)""",
        (chat_id, session_id, worker_id, amount, raw_text[:200], source, author_id, stamp, stamp),
    )
    return get_entry(conn, cursor.lastrowid)


def get_entry(conn: sqlite3.Connection, entry_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM entries WHERE id=?", (entry_id,)).fetchone()


def update_entry(conn: sqlite3.Connection, entry_id: int, amount: int, raw_text: str = "") -> None:
    _write(
        conn,
        "UPDATE entries SET amount=?, raw_text=?, edited=1, updated_at=? WHERE id=?",
        (amount, raw_text[:200], now(), entry_id),
    )


def set_deleted(conn: sqlite3.Connection, entry_id: int, deleted: bool) -> None:
    _write(
        conn,
        "UPDATE entries SET deleted=?, updated_at=? WHERE id=?",
        (1 if deleted else 0, now(), entry_id),
    )


def last_entry(conn: sqlite3.Connection, chat_id: int, session_id: int | None = None) -> sqlite3.Row | None:
    sql = "SELECT * FROM entries WHERE chat_id=? AND deleted=0"
    params: list[Any] = [chat_id]
    if session_id is not None:
        sql += " AND session_id=?"
        params.append(session_id)
    sql += " ORDER BY id DESC LIMIT 1"
    return conn.execute(sql, params).fetchone()


def recent_duplicate(
    conn: sqlite3.Connection, worker_id: int, amount: int, window_seconds: int
) -> sqlite3.Row | None:
    """Такое же число тому же человеку пару секунд назад — похоже на случайный повтор."""
    if window_seconds <= 0:
        return None
    border = (datetime.now(timezone.utc) - timedelta(seconds=window_seconds)).replace(microsecond=0)
    return conn.execute(
        """SELECT * FROM entries
           WHERE worker_id=? AND amount=? AND deleted=0 AND created_at>=?
           ORDER BY id DESC LIMIT 1""",
        (worker_id, amount, border.isoformat()),
    ).fetchone()


def worker_stats(conn: sqlite3.Connection, worker_id: int, session_id: int | None) -> tuple[int, int]:
    """(количество записей, сумма) по человеку."""
    sql = "SELECT COUNT(*) AS n, COALESCE(SUM(amount),0) AS total FROM entries WHERE worker_id=? AND deleted=0"
    params: list[Any] = [worker_id]
    if session_id is not None:
        sql += " AND session_id=?"
        params.append(session_id)
    row = conn.execute(sql, params).fetchone()
    return int(row["n"]), int(row["total"])


def summary(conn: sqlite3.Connection, chat_id: int, session_id: int | None) -> list[dict]:
    """Итог по каждому человеку: имя, сколько записей, сумма."""
    sql = """
        SELECT w.id AS worker_id, w.name AS name,
               COUNT(e.id) AS count, COALESCE(SUM(e.amount),0) AS total
        FROM workers w
        LEFT JOIN entries e
               ON e.worker_id = w.id AND e.deleted = 0
              {session_filter}
        WHERE w.chat_id = ?
        GROUP BY w.id
        ORDER BY w.id
    """
    params: list[Any] = []
    if session_id is not None:
        sql = sql.format(session_filter="AND e.session_id = ?")
        params.append(session_id)
    else:
        sql = sql.format(session_filter="")
    params.append(chat_id)
    rows = conn.execute(sql, params).fetchall()
    return [
        {
            "worker_id": row["worker_id"],
            "name": row["name"],
            "count": int(row["count"]),
            "total": int(row["total"]),
        }
        for row in rows
    ]


def entries(
    conn: sqlite3.Connection,
    chat_id: int,
    session_id: int | None,
    worker_id: int | None = None,
    include_deleted: bool = False,
    limit: int | None = None,
) -> list[sqlite3.Row]:
    sql = """SELECT e.*, w.name AS worker_name
             FROM entries e JOIN workers w ON w.id = e.worker_id
             WHERE e.chat_id=?"""
    params: list[Any] = [chat_id]
    if not include_deleted:
        sql += " AND e.deleted=0"
    if session_id is not None:
        sql += " AND e.session_id=?"
        params.append(session_id)
    if worker_id is not None:
        sql += " AND e.worker_id=?"
        params.append(worker_id)
    sql += " ORDER BY e.id"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    return conn.execute(sql, params).fetchall()


def grand_total(conn: sqlite3.Connection, chat_id: int, session_id: int | None) -> tuple[int, int]:
    sql = "SELECT COUNT(*) AS n, COALESCE(SUM(amount),0) AS total FROM entries WHERE chat_id=? AND deleted=0"
    params: list[Any] = [chat_id]
    if session_id is not None:
        sql += " AND session_id=?"
        params.append(session_id)
    row = conn.execute(sql, params).fetchone()
    return int(row["n"]), int(row["total"])
