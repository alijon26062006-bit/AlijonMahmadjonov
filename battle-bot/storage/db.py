"""SQLite: подключение и схема."""
from __future__ import annotations

import sqlite3
from pathlib import Path

MIGRATIONS = (
    # добавляем колонку отдельно: у уже работающих ботов таблица создана раньше
    "ALTER TABLE users ADD COLUMN is_blocked INTEGER NOT NULL DEFAULT 0",
)

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
-- под нагрузкой запись может ждать: лучше подождать, чем упасть с «database is locked»
PRAGMA busy_timeout = 5000;
PRAGMA synchronous = NORMAL;

CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    username    TEXT,
    first_name  TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    vote_balance INTEGER NOT NULL DEFAULT 0,
    is_banned   INTEGER NOT NULL DEFAULT 0,
    is_blocked  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS battles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    status      TEXT NOT NULL,
    round_no    INTEGER NOT NULL DEFAULT 1,
    deadline    TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS participants (
    battle_id   INTEGER NOT NULL REFERENCES battles(id) ON DELETE CASCADE,
    user_id     INTEGER NOT NULL REFERENCES users(user_id),
    nickname    TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'alive',
    place       INTEGER,
    joined_at   TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (battle_id, user_id)
);

CREATE TABLE IF NOT EXISTS matches (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    battle_id   INTEGER NOT NULL REFERENCES battles(id) ON DELETE CASCADE,
    round_no    INTEGER NOT NULL,
    number      INTEGER NOT NULL,
    status      TEXT NOT NULL DEFAULT 'voting',
    is_final    INTEGER NOT NULL DEFAULT 0,
    advance     INTEGER NOT NULL DEFAULT 1,
    message_id  INTEGER,
    deadline    TEXT,
    closed_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_matches_battle ON matches(battle_id, round_no);

CREATE TABLE IF NOT EXISTS match_slots (
    match_id    INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    user_id     INTEGER NOT NULL REFERENCES users(user_id),
    nickname    TEXT NOT NULL,
    votes       INTEGER NOT NULL DEFAULT 0,
    position    INTEGER,
    slot_no     INTEGER NOT NULL,
    PRIMARY KEY (match_id, user_id)
);

-- UNIQUE(match_id, voter_id) — защита от повторного голоса на уровне БД,
-- переживает перезапуск бота.
CREATE TABLE IF NOT EXISTS votes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id    INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    voter_id    INTEGER NOT NULL,
    target_id   INTEGER NOT NULL,
    source      TEXT NOT NULL DEFAULT 'free',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_free_vote
    ON votes(match_id, voter_id) WHERE source = 'free';
CREATE INDEX IF NOT EXISTS idx_votes_target ON votes(match_id, target_id);

CREATE TABLE IF NOT EXISTS payments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(user_id),
    charge_id   TEXT UNIQUE,
    stars       INTEGER NOT NULL,
    votes       INTEGER NOT NULL,
    status      TEXT NOT NULL DEFAULT 'paid',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Что автопилот уже отправил. Ключ первичный, поэтому одно и то же
-- напоминание не уйдёт дважды даже после перезапуска бота.
CREATE TABLE IF NOT EXISTS auto_log (
    kind    TEXT NOT NULL,
    key     TEXT NOT NULL,
    sent_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (kind, key)
);

-- Рекламные посты автопилота: крутятся по кругу с заданным интервалом.
CREATE TABLE IF NOT EXISTS promos (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    text         TEXT NOT NULL,
    button_label TEXT,
    button_url   TEXT,
    enabled      INTEGER NOT NULL DEFAULT 1,
    sent_count   INTEGER NOT NULL DEFAULT 0,
    last_sent    TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Приглашения. invited_id первичный ключ: один приглашённый приносит награду
-- ровно один раз, сколько бы ссылок он ни открывал.
CREATE TABLE IF NOT EXISTS referrals (
    invited_id  INTEGER PRIMARY KEY,
    inviter_id  INTEGER NOT NULL,
    rewarded    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    rewarded_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_referrals_inviter ON referrals(inviter_id);

-- Всё, что бот опубликовал в каналах: нужно, чтобы панель могла
-- удалить посты батла, включая анонсы, а не только пары.
CREATE TABLE IF NOT EXISTS channel_posts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    battle_id   INTEGER,
    chat_id     INTEGER NOT NULL,
    message_id  INTEGER NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'match',
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (chat_id, message_id)
);
CREATE INDEX IF NOT EXISTS idx_posts_battle ON channel_posts(battle_id);

-- Всё, что админ меняет из панели. .env даёт только начальные значения:
-- при первом запуске они переносятся сюда, дальше правит панель.
CREATE TABLE IF NOT EXISTS settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS stats (
    user_id     INTEGER PRIMARY KEY REFERENCES users(user_id),
    battles     INTEGER NOT NULL DEFAULT 0,
    wins        INTEGER NOT NULL DEFAULT 0,
    titles      INTEGER NOT NULL DEFAULT 0,
    best_place  INTEGER
);
"""


def connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Досоздать то, чего нет в старых базах. Уже существующее молча пропускаем."""
    for statement in MIGRATIONS:
        try:
            conn.execute(statement)
        except sqlite3.OperationalError:
            pass  # колонка уже есть — обычное дело при обновлении
    conn.commit()
