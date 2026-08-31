"""Хранилище: SQLite + полнотекстовый поиск FTS5 по русскому тексту."""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 1

DIRECTIONS = ("out", "in")
KINDS = ("transfer", "payment", "debt", "income")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS transactions (
    id                INTEGER PRIMARY KEY,
    chat_id           INTEGER NOT NULL,
    created_at        TEXT    NOT NULL,
    happened_on       TEXT,
    direction         TEXT,
    kind              TEXT,
    counterparty      TEXT,
    counterparty_norm TEXT,
    amount            REAL,
    currency          TEXT,
    item              TEXT,
    quantity          REAL,
    unit              TEXT,
    due_date          TEXT,
    note              TEXT,
    raw_text          TEXT,
    source            TEXT,
    deleted_at        TEXT
);
CREATE INDEX IF NOT EXISTS ix_tx_chat_date ON transactions(chat_id, happened_on);
CREATE INDEX IF NOT EXISTS ix_tx_counterparty ON transactions(chat_id, counterparty_norm);

CREATE TABLE IF NOT EXISTS documents (
    id             INTEGER PRIMARY KEY,
    chat_id        INTEGER NOT NULL,
    created_at     TEXT    NOT NULL,
    tg_file_id     TEXT    NOT NULL,
    file_path      TEXT    NOT NULL,
    doc_kind       TEXT,
    description    TEXT,
    transaction_id INTEGER REFERENCES transactions(id),
    deleted_at     TEXT
);
CREATE INDEX IF NOT EXISTS ix_doc_chat ON documents(chat_id, created_at);

CREATE TABLE IF NOT EXISTS messages (
    id      INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL,
    ts      TEXT    NOT NULL,
    role    TEXT    NOT NULL,
    text    TEXT
);
CREATE INDEX IF NOT EXISTS ix_msg_chat ON messages(chat_id, id);

CREATE VIRTUAL TABLE IF NOT EXISTS tx_fts USING fts5(
    counterparty, item, note, raw_text,
    content='transactions', content_rowid='id', tokenize='unicode61'
);
CREATE VIRTUAL TABLE IF NOT EXISTS doc_fts USING fts5(
    description, doc_kind,
    content='documents', content_rowid='id', tokenize='unicode61'
);
"""

# Триггеры держат FTS в синхроне с таблицами — иначе после правки поиск начнёт врать.
_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS tx_ai AFTER INSERT ON transactions BEGIN
    INSERT INTO tx_fts(rowid, counterparty, item, note, raw_text)
    VALUES (new.id, new.counterparty, new.item, new.note, new.raw_text);
END;
CREATE TRIGGER IF NOT EXISTS tx_ad AFTER DELETE ON transactions BEGIN
    INSERT INTO tx_fts(tx_fts, rowid, counterparty, item, note, raw_text)
    VALUES ('delete', old.id, old.counterparty, old.item, old.note, old.raw_text);
END;
CREATE TRIGGER IF NOT EXISTS tx_au AFTER UPDATE ON transactions BEGIN
    INSERT INTO tx_fts(tx_fts, rowid, counterparty, item, note, raw_text)
    VALUES ('delete', old.id, old.counterparty, old.item, old.note, old.raw_text);
    INSERT INTO tx_fts(rowid, counterparty, item, note, raw_text)
    VALUES (new.id, new.counterparty, new.item, new.note, new.raw_text);
END;

CREATE TRIGGER IF NOT EXISTS doc_ai AFTER INSERT ON documents BEGIN
    INSERT INTO doc_fts(rowid, description, doc_kind)
    VALUES (new.id, new.description, new.doc_kind);
END;
CREATE TRIGGER IF NOT EXISTS doc_ad AFTER DELETE ON documents BEGIN
    INSERT INTO doc_fts(doc_fts, rowid, description, doc_kind)
    VALUES ('delete', old.id, old.description, old.doc_kind);
END;
CREATE TRIGGER IF NOT EXISTS doc_au AFTER UPDATE ON documents BEGIN
    INSERT INTO doc_fts(doc_fts, rowid, description, doc_kind)
    VALUES ('delete', old.id, old.description, old.doc_kind);
    INSERT INTO doc_fts(rowid, description, doc_kind)
    VALUES (new.id, new.description, new.doc_kind);
END;
"""


# ── вспомогательное ────────────────────────────────────────────────────────

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize(text: str | None) -> str:
    """lower + ё→е + схлопнутые пробелы. Для поиска по именам и товарам."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.replace("ё", "е").replace("Ё", "Е").lower()).strip()


_WORD_RE = re.compile(r"[\wЀ-ӿ]+", re.UNICODE)


def fts_query(text: str) -> str:
    """Собрать FTS5-запрос с префиксами: «сумки» → «сумк*».

    Русской морфологии в FTS5 нет, поэтому длинные слова обрезаем до корня —
    так «сумки» находит «сумка», а «обуви» находит «обувь».
    """
    words = [w for w in _WORD_RE.findall(normalize(text)) if len(w) > 2]
    if not words:
        return ""
    parts = []
    for w in words:
        stem = w[:-2] if len(w) > 5 else (w[:-1] if len(w) > 4 else w)
        parts.append(f'"{stem}"*')
    return " OR ".join(parts)


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {k: row[k] for k in row.keys()}


# ── подключение ────────────────────────────────────────────────────────────

def connect(db_path: Path | str) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    init_schema(conn)
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    conn.executescript(_TRIGGERS)
    cur = conn.execute("SELECT version FROM schema_version LIMIT 1")
    if cur.fetchone() is None:
        conn.execute("INSERT INTO schema_version(version) VALUES (?)", (SCHEMA_VERSION,))
    conn.commit()


# ── журнал сообщений ───────────────────────────────────────────────────────

def log_message(conn: sqlite3.Connection, chat_id: int, role: str, text: str | None) -> int:
    cur = conn.execute(
        "INSERT INTO messages(chat_id, ts, role, text) VALUES (?,?,?,?)",
        (chat_id, now_iso(), role, text),
    )
    conn.commit()
    return int(cur.lastrowid)


# ── операции ───────────────────────────────────────────────────────────────

_TX_FIELDS = (
    "happened_on", "direction", "kind", "counterparty", "amount", "currency",
    "item", "quantity", "unit", "due_date", "note", "raw_text", "source",
)


def add_transaction(conn: sqlite3.Connection, chat_id: int, **fields: Any) -> int:
    data = {k: fields.get(k) for k in _TX_FIELDS}
    cur = conn.execute(
        f"""INSERT INTO transactions
            (chat_id, created_at, counterparty_norm, {', '.join(_TX_FIELDS)})
            VALUES (?,?,?,{','.join('?' * len(_TX_FIELDS))})""",
        (chat_id, now_iso(), normalize(data["counterparty"]), *[data[k] for k in _TX_FIELDS]),
    )
    conn.commit()
    return int(cur.lastrowid)


def get_transaction(conn: sqlite3.Connection, chat_id: int, tx_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM transactions WHERE id=? AND chat_id=? AND deleted_at IS NULL",
        (tx_id, chat_id),
    ).fetchone()
    return _row_to_dict(row) if row else None


def update_transaction(conn: sqlite3.Connection, chat_id: int, tx_id: int, **fields: Any) -> bool:
    changes = {k: v for k, v in fields.items() if k in _TX_FIELDS and v is not None}
    if not changes:
        return False
    if "counterparty" in changes:
        changes["counterparty_norm"] = normalize(changes["counterparty"])
    sets = ", ".join(f"{k}=?" for k in changes)
    cur = conn.execute(
        f"UPDATE transactions SET {sets} WHERE id=? AND chat_id=? AND deleted_at IS NULL",
        (*changes.values(), tx_id, chat_id),
    )
    conn.commit()
    return cur.rowcount > 0


def delete_transaction(conn: sqlite3.Connection, chat_id: int, tx_id: int) -> bool:
    cur = conn.execute(
        "UPDATE transactions SET deleted_at=? WHERE id=? AND chat_id=? AND deleted_at IS NULL",
        (now_iso(), tx_id, chat_id),
    )
    conn.commit()
    return cur.rowcount > 0


def search_transactions(
    conn: sqlite3.Connection,
    chat_id: int,
    *,
    text: str | None = None,
    counterparty: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    direction: str | None = None,
    kind: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Найти операции. Возвращает ВЕСЬ список — пользователю нужна история целиком."""
    where = ["t.chat_id = ?", "t.deleted_at IS NULL"]
    args: list[Any] = [chat_id]

    if counterparty:
        where.append("t.counterparty_norm LIKE ?")
        args.append(f"%{normalize(counterparty)}%")
    if date_from:
        where.append("COALESCE(t.happened_on, substr(t.created_at,1,10)) >= ?")
        args.append(date_from)
    if date_to:
        where.append("COALESCE(t.happened_on, substr(t.created_at,1,10)) <= ?")
        args.append(date_to)
    if direction in DIRECTIONS:
        where.append("t.direction = ?")
        args.append(direction)
    if kind in KINDS:
        where.append("t.kind = ?")
        args.append(kind)

    ids: list[int] | None = None
    if text:
        # Шаг 1: FTS5 с префиксами (морфология).
        query = fts_query(text)
        if query:
            try:
                ids = [
                    int(r["rowid"])
                    for r in conn.execute(
                        "SELECT rowid FROM tx_fts WHERE tx_fts MATCH ? ORDER BY rank", (query,)
                    )
                ]
            except sqlite3.OperationalError:
                ids = None
        # Шаг 2: если FTS пусто — запасной LIKE по нормализованному тексту.
        if not ids:
            like = f"%{normalize(text)}%"
            ids = [
                int(r["id"])
                for r in conn.execute(
                    """SELECT id FROM transactions
                       WHERE chat_id=? AND deleted_at IS NULL AND (
                             lower(COALESCE(item,'')) LIKE ?
                          OR lower(COALESCE(note,'')) LIKE ?
                          OR lower(COALESCE(raw_text,'')) LIKE ?
                          OR counterparty_norm LIKE ?)""",
                    (chat_id, like, like, like, like),
                )
            ]
        if not ids:
            return []
        where.append(f"t.id IN ({','.join('?' * len(ids))})")
        args.extend(ids)

    rows = conn.execute(
        f"""SELECT t.* FROM transactions t
            WHERE {' AND '.join(where)}
            ORDER BY COALESCE(t.happened_on, substr(t.created_at,1,10)) DESC, t.id DESC
            LIMIT ?""",
        (*args, limit),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def totals_by_currency(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Итоги отдельно по каждой валюте — конвертации нет по решению пользователя."""
    totals: dict[str, dict[str, float]] = {}
    for r in rows:
        if r.get("amount") is None:
            continue
        cur = (r.get("currency") or "?").upper()
        bucket = totals.setdefault(cur, {"out": 0.0, "in": 0.0, "count": 0})
        key = "in" if r.get("direction") == "in" else "out"
        bucket[key] += float(r["amount"])
        bucket["count"] += 1
    return totals


# ── документы (фото накладных) ─────────────────────────────────────────────

def add_document(
    conn: sqlite3.Connection,
    chat_id: int,
    *,
    tg_file_id: str,
    file_path: str,
    doc_kind: str | None = None,
    description: str | None = None,
    transaction_id: int | None = None,
) -> int:
    cur = conn.execute(
        """INSERT INTO documents
           (chat_id, created_at, tg_file_id, file_path, doc_kind, description, transaction_id)
           VALUES (?,?,?,?,?,?,?)""",
        (chat_id, now_iso(), tg_file_id, file_path, doc_kind, description, transaction_id),
    )
    conn.commit()
    return int(cur.lastrowid)


def describe_document(
    conn: sqlite3.Connection,
    chat_id: int,
    doc_id: int,
    *,
    description: str,
    doc_kind: str | None = None,
    transaction_id: int | None = None,
) -> bool:
    sets = ["description=?"]
    args: list[Any] = [description]
    if doc_kind:
        sets.append("doc_kind=?")
        args.append(doc_kind)
    if transaction_id:
        sets.append("transaction_id=?")
        args.append(transaction_id)
    cur = conn.execute(
        f"UPDATE documents SET {', '.join(sets)} WHERE id=? AND chat_id=? AND deleted_at IS NULL",
        (*args, doc_id, chat_id),
    )
    conn.commit()
    return cur.rowcount > 0


def get_document(conn: sqlite3.Connection, chat_id: int, doc_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM documents WHERE id=? AND chat_id=? AND deleted_at IS NULL",
        (doc_id, chat_id),
    ).fetchone()
    return _row_to_dict(row) if row else None


def pending_documents(conn: sqlite3.Connection, chat_id: int, limit: int = 3) -> list[dict[str, Any]]:
    """Фото без описания — их пользователь ещё не подписал."""
    rows = conn.execute(
        """SELECT * FROM documents
           WHERE chat_id=? AND deleted_at IS NULL
             AND (description IS NULL OR description='')
           ORDER BY id DESC LIMIT ?""",
        (chat_id, limit),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def search_documents(
    conn: sqlite3.Connection,
    chat_id: int,
    *,
    text: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    where = ["d.chat_id = ?", "d.deleted_at IS NULL"]
    args: list[Any] = [chat_id]

    if date_from:
        where.append("substr(d.created_at,1,10) >= ?")
        args.append(date_from)
    if date_to:
        where.append("substr(d.created_at,1,10) <= ?")
        args.append(date_to)

    if text:
        ids: list[int] = []
        query = fts_query(text)
        if query:
            try:
                ids = [
                    int(r["rowid"])
                    for r in conn.execute(
                        "SELECT rowid FROM doc_fts WHERE doc_fts MATCH ? ORDER BY rank", (query,)
                    )
                ]
            except sqlite3.OperationalError:
                ids = []
        if not ids:
            like = f"%{normalize(text)}%"
            ids = [
                int(r["id"])
                for r in conn.execute(
                    """SELECT id FROM documents
                       WHERE chat_id=? AND deleted_at IS NULL AND (
                             lower(COALESCE(description,'')) LIKE ?
                          OR lower(COALESCE(doc_kind,'')) LIKE ?)""",
                    (chat_id, like, like),
                )
            ]
        if not ids:
            return []
        where.append(f"d.id IN ({','.join('?' * len(ids))})")
        args.extend(ids)

    rows = conn.execute(
        f"SELECT d.* FROM documents d WHERE {' AND '.join(where)} ORDER BY d.id DESC LIMIT ?",
        (*args, limit),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]
