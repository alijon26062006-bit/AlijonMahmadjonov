"""База ревизии: сотрудники, ревизии и записи (сканы и минусы). Фото не хранятся."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    tg_id      INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    username   TEXT,
    role       TEXT NOT NULL DEFAULT 'staff'   CHECK (role IN ('admin', 'staff')),
    status     TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'active', 'blocked')),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS revisions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    started_at TEXT NOT NULL,
    closed_at  TEXT
);
CREATE TABLE IF NOT EXISTS entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    revision_id INTEGER NOT NULL REFERENCES revisions(id),
    tg_id       INTEGER NOT NULL REFERENCES users(tg_id),
    amt         INTEGER NOT NULL,          -- плюс: скан ценника, минус: вычет вручную
    sec         REAL,                      -- сколько секунд Claude читал ценник
    voided      INTEGER NOT NULL DEFAULT 0,
    voided_by   INTEGER,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS entries_rev_user ON entries (revision_id, tg_id, id DESC);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: Path | str) -> sqlite3.Connection:
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None)  # каждая запись сохраняется сразу
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    return conn


# ── сотрудники ─────────────────────────────────────────────────────────────

def get_user(conn: sqlite3.Connection, tg_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,)).fetchone()
    return dict(row) if row else None


def upsert_user(conn, tg_id: int, name: str, username: str | None, admin_ids=frozenset()) -> tuple[dict, bool]:
    """Заводит сотрудника при первом входе. Возвращает (сотрудник, новый ли он).

    Самый первый человек становится админом: это владелец, он ставит систему.
    Все следующие ждут, пока админ их допустит.
    """
    user = get_user(conn, tg_id)
    if user:
        if user["name"] != name or user["username"] != username:
            conn.execute("UPDATE users SET name = ?, username = ? WHERE tg_id = ?", (name, username, tg_id))
            user.update(name=name, username=username)
        return user, False
    first = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    is_admin = first or tg_id in admin_ids
    conn.execute(
        "INSERT INTO users (tg_id, name, username, role, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (tg_id, name, username, "admin" if is_admin else "staff", "active" if is_admin else "pending", _now()),
    )
    return get_user(conn, tg_id), True


def set_user(conn, tg_id: int, *, status: str | None = None, role: str | None = None) -> dict | None:
    if status is not None:
        conn.execute("UPDATE users SET status = ? WHERE tg_id = ?", (status, tg_id))
    if role is not None:
        conn.execute("UPDATE users SET role = ? WHERE tg_id = ?", (role, tg_id))
    return get_user(conn, tg_id)


def admin_ids(conn) -> list[int]:
    return [r[0] for r in conn.execute("SELECT tg_id FROM users WHERE role = 'admin' AND status = 'active'")]


# ── ревизии ────────────────────────────────────────────────────────────────

def current_revision(conn) -> dict:
    row = conn.execute("SELECT * FROM revisions WHERE closed_at IS NULL ORDER BY id DESC LIMIT 1").fetchone()
    if row:
        return dict(row)
    return new_revision(conn)


def new_revision(conn, title: str | None = None) -> dict:
    """Закрывает текущую ревизию и начинает новую с нуля. Старые записи остаются в базе."""
    now = _now()
    conn.execute("UPDATE revisions SET closed_at = ? WHERE closed_at IS NULL", (now,))
    title = (title or "").strip() or "Ревизия " + datetime.now().strftime("%d.%m.%Y")
    cur = conn.execute("INSERT INTO revisions (title, started_at) VALUES (?, ?)", (title[:80], now))
    return dict(conn.execute("SELECT * FROM revisions WHERE id = ?", (cur.lastrowid,)).fetchone())


# ── записи ─────────────────────────────────────────────────────────────────

def _entry(row) -> dict:
    return {"id": row["id"], "amt": row["amt"], "sec": row["sec"], "voided": bool(row["voided"]), "at": row["created_at"]}


def add_entry(conn, tg_id: int, amt: int, sec: float | None = None) -> dict:
    rev = current_revision(conn)
    cur = conn.execute(
        "INSERT INTO entries (revision_id, tg_id, amt, sec, created_at) VALUES (?, ?, ?, ?, ?)",
        (rev["id"], tg_id, int(amt), round(sec, 1) if sec else None, _now()),
    )
    return _entry(conn.execute("SELECT * FROM entries WHERE id = ?", (cur.lastrowid,)).fetchone())


def void_entry(conn, entry_id: int, by: dict) -> bool:
    """Отменяет запись. Сотрудник отменяет только свои, админ любые. Только в текущей ревизии."""
    rev = current_revision(conn)
    row = conn.execute(
        "SELECT * FROM entries WHERE id = ? AND revision_id = ? AND voided = 0", (entry_id, rev["id"])
    ).fetchone()
    if not row or (row["tg_id"] != by["tg_id"] and by["role"] != "admin"):
        return False
    conn.execute("UPDATE entries SET voided = 1, voided_by = ? WHERE id = ?", (by["tg_id"], entry_id))
    return True


def recent(conn, tg_id: int, limit: int = 80) -> list[dict]:
    rev = current_revision(conn)
    rows = conn.execute(
        "SELECT * FROM entries WHERE revision_id = ? AND tg_id = ? ORDER BY id DESC LIMIT ?",
        (rev["id"], tg_id, limit),
    )
    return [_entry(r) for r in rows]


_TOTALS = """
    COALESCE(SUM(CASE WHEN e.voided = 0 THEN e.amt END), 0)                       AS sum,
    COALESCE(SUM(CASE WHEN e.voided = 0 AND e.amt > 0 THEN 1 END), 0)             AS scans,
    COALESCE(SUM(CASE WHEN e.voided = 0 AND e.amt < 0 THEN 1 END), 0)             AS minuses,
    COALESCE(SUM(CASE WHEN e.voided = 0 AND e.amt < 0 THEN -e.amt END), 0)        AS minus_sum,
    COALESCE(SUM(e.voided), 0)                                                    AS voids,
    AVG(CASE WHEN e.amt > 0 THEN e.sec END)                                       AS avg,
    MAX(e.created_at)                                                             AS last_at
"""


def totals(conn, tg_id: int) -> dict:
    rev = current_revision(conn)
    row = conn.execute(
        f"SELECT {_TOTALS} FROM entries e WHERE e.revision_id = ? AND e.tg_id = ?", (rev["id"], tg_id)
    ).fetchone()
    return dict(row)


def admin_summary(conn) -> dict:
    rev = current_revision(conn)
    rows = conn.execute(
        f"""SELECT u.tg_id AS id, u.name, u.username, u.role, u.status, {_TOTALS}
            FROM users u LEFT JOIN entries e ON e.tg_id = u.tg_id AND e.revision_id = ?
            GROUP BY u.tg_id ORDER BY sum DESC, u.name""",
        (rev["id"],),
    ).fetchall()
    people = [dict(r) for r in rows]
    staff = [p for p in people if p["status"] != "pending"]
    return {
        "revision": {"id": rev["id"], "title": rev["title"], "started_at": rev["started_at"]},
        "sum": sum(p["sum"] for p in staff),
        "scans": sum(p["scans"] for p in staff),
        "minus_sum": sum(p["minus_sum"] for p in staff),
        "users": staff,
        "pending": [{"id": p["id"], "name": p["name"], "username": p["username"]} for p in people if p["status"] == "pending"],
    }


def all_entries(conn, revision_id: int) -> list[dict]:
    rows = conn.execute(
        """SELECT e.id, e.created_at, u.name, e.amt, e.sec, e.voided
           FROM entries e JOIN users u ON u.tg_id = e.tg_id
           WHERE e.revision_id = ? ORDER BY e.id""",
        (revision_id,),
    )
    return [dict(r) for r in rows]
