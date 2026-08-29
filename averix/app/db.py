"""Подключение к SQLite и миграции."""
import sqlite3
from pathlib import Path

from .config import DB_PATH, ensure_dirs

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def connect() -> sqlite3.Connection:
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    # Внешние ключи в SQLite по умолчанию выключены
    conn.execute("PRAGMA foreign_keys = ON")
    # WAL: чтение не блокируется записью
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def migrate() -> list[str]:
    """Применяет неприменённые миграции по порядку. Возвращает их имена."""
    applied: list[str] = []
    with connect() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " name TEXT PRIMARY KEY,"
            " applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )
        done = {r["name"] for r in conn.execute("SELECT name FROM schema_migrations")}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in done:
                continue
            conn.executescript(path.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO schema_migrations (name) VALUES (?)", (path.name,))
            applied.append(path.name)
    return applied
