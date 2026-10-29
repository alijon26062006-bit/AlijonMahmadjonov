"""Хранилище: ученики и настройки (цена, реквизиты, канал...)."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

# Статусы ученика:
#   new             — просто открыл бота
#   waiting_receipt — нажал «Я оплатил», ждём фото чека
#   pending         — чек у админа на проверке
#   paid            — подписка активна (до paid_until), ученик в канале
#   renew_waiting   — подписка активна, нажал «Я оплатил» для продления, ждём чек
#   renew_pending   — подписка активна, чек о продлении у админа
#   rejected        — админ отклонил чек (можно прислать снова)
#   expired         — подписка закончилась, ученик убран из канала

# У этих статусов есть доступ к каналу.
ACTIVE = ("paid", "renew_waiting", "renew_pending")

DEFAULTS = {
    "price": "уточняйте у администратора",
    "pay": "",
    "schedule": "новый урок каждые 2 дня",
    "ready": "2",
    "contact": "",
    "demo": "",
    "channel_id": "",
}


def connect(path: Path | str) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS students (
            user_id      INTEGER PRIMARY KEY,
            username     TEXT,
            full_name    TEXT,
            status       TEXT NOT NULL DEFAULT 'new',
            created_at   REAL NOT NULL,
            paid_at      REAL,
            last_link_at REAL,
            paid_until   REAL,
            warned_at    REAL
        );
        """
    )
    # База от первой версии бота — без колонок подписки.
    columns = {r["name"] for r in conn.execute("PRAGMA table_info(students)")}
    for column in ("paid_until", "warned_at"):
        if column not in columns:
            conn.execute(f"ALTER TABLE students ADD COLUMN {column} REAL")
    conn.commit()
    return conn


def get_setting(conn: sqlite3.Connection, key: str) -> str:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else DEFAULTS.get(key, "")


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()


def ready_count(conn: sqlite3.Connection) -> int:
    try:
        return int(get_setting(conn, "ready"))
    except ValueError:
        return 0


def touch_student(conn: sqlite3.Connection, user_id: int, username: str | None, full_name: str) -> None:
    conn.execute(
        "INSERT INTO students (user_id, username, full_name, created_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET username = excluded.username, "
        "full_name = excluded.full_name",
        (user_id, username, full_name, time.time()),
    )
    conn.commit()


def get_student(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM students WHERE user_id = ?", (user_id,)).fetchone()


def status_of(conn: sqlite3.Connection, user_id: int) -> str:
    row = get_student(conn, user_id)
    return row["status"] if row else "new"


def set_status(conn: sqlite3.Connection, user_id: int, status: str) -> None:
    conn.execute("UPDATE students SET status = ? WHERE user_id = ?", (status, user_id))
    conn.commit()


def extend(conn: sqlite3.Connection, user_id: int, days: int, now: float | None = None) -> float:
    """Плюс days дней доступа. Продление до конца срока добавляется к оставшимся дням."""
    now = now or time.time()
    row = get_student(conn, user_id)
    active = row is not None and row["status"] in ACTIVE and (row["paid_until"] or 0) > now
    until = (row["paid_until"] if active else now) + days * 86400
    conn.execute(
        "UPDATE students SET status = 'paid', paid_at = ?, paid_until = ?, warned_at = NULL "
        "WHERE user_id = ?",
        (now, until, user_id),
    )
    conn.commit()
    return until


def ending_soon(conn: sqlite3.Connection, within: float, now: float) -> list[sqlite3.Row]:
    """Активные, кому ещё не напоминали, а до конца осталось меньше within секунд."""
    marks = ",".join("?" * len(ACTIVE))
    return conn.execute(
        f"SELECT * FROM students WHERE status IN ({marks}) AND warned_at IS NULL "
        "AND paid_until > ? AND paid_until <= ?",
        (*ACTIVE, now, now + within),
    ).fetchall()


def overdue(conn: sqlite3.Connection, now: float) -> list[sqlite3.Row]:
    """Срок вышел. Чек о продлении на проверке (renew_pending) не трогаем — ждём админа."""
    return conn.execute(
        "SELECT * FROM students WHERE status IN ('paid', 'renew_waiting') AND paid_until <= ?",
        (now,),
    ).fetchall()


def mark_warned(conn: sqlite3.Connection, user_id: int, now: float) -> None:
    conn.execute("UPDATE students SET warned_at = ? WHERE user_id = ?", (now, user_id))
    conn.commit()


def mark_link_issued(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute("UPDATE students SET last_link_at = ? WHERE user_id = ?", (time.time(), user_id))
    conn.commit()


def counts(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute("SELECT status, COUNT(*) AS n FROM students GROUP BY status").fetchall()
    return {r["status"]: r["n"] for r in rows}


def students_with(conn: sqlite3.Connection, *statuses: str, limit: int = 20) -> list[sqlite3.Row]:
    marks = ",".join("?" * len(statuses))
    return conn.execute(
        f"SELECT * FROM students WHERE status IN ({marks}) "
        "ORDER BY COALESCE(paid_at, created_at) DESC LIMIT ?",
        (*statuses, limit),
    ).fetchall()
