"""Хранилище дуэли: игроки, рейтинг, история матчей. SQLite без внешних зависимостей."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .rating import START_RATING

SCHEMA_VERSION = 1
LANGS = ("ru", "tg")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS players (
    id            INTEGER PRIMARY KEY,
    name          TEXT    NOT NULL,
    username      TEXT    NOT NULL DEFAULT '',
    photo_url     TEXT    NOT NULL DEFAULT '',
    lang          TEXT    NOT NULL DEFAULT 'ru',
    rating        INTEGER NOT NULL DEFAULT 1000,
    games         INTEGER NOT NULL DEFAULT 0,
    wins          INTEGER NOT NULL DEFAULT 0,
    losses        INTEGER NOT NULL DEFAULT 0,
    draws         INTEGER NOT NULL DEFAULT 0,
    correct       INTEGER NOT NULL DEFAULT 0,
    wrong         INTEGER NOT NULL DEFAULT 0,
    best_streak   INTEGER NOT NULL DEFAULT 0,
    best_rating   INTEGER NOT NULL DEFAULT 1000,
    created_at    TEXT    NOT NULL,
    last_seen_at  TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_players_rating ON players(rating DESC);
CREATE INDEX IF NOT EXISTS idx_players_seen ON players(last_seen_at DESC);

CREATE TABLE IF NOT EXISTS matches (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at   TEXT    NOT NULL,
    finished_at  TEXT    NOT NULL,
    duration     INTEGER NOT NULL,
    level        TEXT    NOT NULL,
    private      INTEGER NOT NULL DEFAULT 0,
    player_a     INTEGER NOT NULL,
    player_b     INTEGER NOT NULL,
    score_a      INTEGER NOT NULL,
    score_b      INTEGER NOT NULL,
    rope         INTEGER NOT NULL,
    winner       INTEGER,
    reason       TEXT    NOT NULL DEFAULT '',
    delta_a      INTEGER NOT NULL DEFAULT 0,
    delta_b      INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_matches_a ON matches(player_a, id DESC);
CREATE INDEX IF NOT EXISTS idx_matches_b ON matches(player_b, id DESC);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: str | Path) -> sqlite3.Connection:
    """Открывает базу и создаёт таблицы, если их ещё нет."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA)
    row = conn.execute("SELECT version FROM schema_version").fetchone()
    if row is None:
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
    conn.commit()
    return conn


def touch_player(
    conn: sqlite3.Connection,
    user_id: int,
    name: str,
    *,
    username: str = "",
    photo_url: str = "",
    lang: str | None = None,
) -> sqlite3.Row:
    """Заводит игрока при первом входе, дальше просто обновляет имя и время."""

    now = _now()
    conn.execute(
        """
        INSERT INTO players (id, name, username, photo_url, lang, rating,
                             best_rating, created_at, last_seen_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            username = excluded.username,
            photo_url = excluded.photo_url,
            last_seen_at = excluded.last_seen_at
        """,
        (
            user_id,
            name,
            username,
            photo_url,
            lang if lang in LANGS else "ru",
            START_RATING,
            START_RATING,
            now,
            now,
        ),
    )
    conn.commit()
    return get_player(conn, user_id)


def get_player(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM players WHERE id = ?", (user_id,)).fetchone()


def set_lang(conn: sqlite3.Connection, user_id: int, lang: str) -> None:
    if lang not in LANGS:
        raise ValueError(f"неизвестный язык: {lang!r}")
    conn.execute("UPDATE players SET lang = ? WHERE id = ?", (lang, user_id))
    conn.commit()


def apply_result(
    conn: sqlite3.Connection,
    user_id: int,
    *,
    new_rating: int,
    outcome: str,
    correct: int,
    wrong: int,
    best_streak: int,
) -> None:
    """Записывает итог матча в профиль. outcome: 'win' | 'loss' | 'draw'."""

    if outcome not in {"win", "loss", "draw"}:
        raise ValueError(f"неизвестный итог: {outcome!r}")
    conn.execute(
        f"""
        UPDATE players SET
            rating = ?,
            best_rating = MAX(best_rating, ?),
            games = games + 1,
            {'wins = wins + 1' if outcome == 'win' else
             'losses = losses + 1' if outcome == 'loss' else 'draws = draws + 1'},
            correct = correct + ?,
            wrong = wrong + ?,
            best_streak = MAX(best_streak, ?),
            last_seen_at = ?
        WHERE id = ?
        """,
        (new_rating, new_rating, correct, wrong, best_streak, _now(), user_id),
    )
    conn.commit()


def save_match(conn: sqlite3.Connection, **fields: Any) -> int:
    """Кладёт матч в историю, возвращает его номер."""

    cur = conn.execute(
        """
        INSERT INTO matches (started_at, finished_at, duration, level, private,
                             player_a, player_b, score_a, score_b, rope,
                             winner, reason, delta_a, delta_b)
        VALUES (:started_at, :finished_at, :duration, :level, :private,
                :player_a, :player_b, :score_a, :score_b, :rope,
                :winner, :reason, :delta_a, :delta_b)
        """,
        {
            "started_at": fields.get("started_at") or _now(),
            "finished_at": fields.get("finished_at") or _now(),
            "duration": int(fields.get("duration", 0)),
            "level": str(fields.get("level", "auto")),
            "private": 1 if fields.get("private") else 0,
            "player_a": int(fields["player_a"]),
            "player_b": int(fields["player_b"]),
            "score_a": int(fields.get("score_a", 0)),
            "score_b": int(fields.get("score_b", 0)),
            "rope": int(fields.get("rope", 0)),
            "winner": fields.get("winner"),
            "reason": str(fields.get("reason", "")),
            "delta_a": int(fields.get("delta_a", 0)),
            "delta_b": int(fields.get("delta_b", 0)),
        },
    )
    conn.commit()
    return int(cur.lastrowid)


def top(conn: sqlite3.Connection, limit: int = 50) -> list[sqlite3.Row]:
    """Таблица лидеров: сначала сыгравшие по рейтингу, новички — в конце.

    Новичок не может стоять выше того, кто играл и проиграл: у всех стартовые
    тысяча очков, и без этого правила он обошёл бы половину таблицы, не сыграв
    ни разу.
    """

    return conn.execute(
        """
        SELECT id, name, username, rating, games, wins, losses, draws
        FROM players
        ORDER BY (games > 0) DESC, rating DESC, wins DESC, id ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def place_of(conn: sqlite3.Connection, user_id: int) -> int:
    """Какое место занимает игрок. 0 — ещё ни одного матча."""

    row = get_player(conn, user_id)
    if row is None or row["games"] == 0:
        return 0
    ahead = conn.execute(
        "SELECT COUNT(*) AS n FROM players WHERE games > 0 AND rating > ?",
        (row["rating"],),
    ).fetchone()
    return int(ahead["n"]) + 1


def by_last_seen(
    conn: sqlite3.Connection,
    *,
    exclude: int = 0,
    limit: int = 60,
    offset: int = 0,
) -> list[sqlite3.Row]:
    """Все игроки: кто заходил недавно — сверху, забытые — в самом низу."""

    return conn.execute(
        """
        SELECT id, name, rating, games, wins, last_seen_at
        FROM players
        WHERE id != ?
        ORDER BY last_seen_at DESC, id ASC
        LIMIT ? OFFSET ?
        """,
        (exclude, limit, offset),
    ).fetchall()


def count_players(conn: sqlite3.Connection, exclude: int = 0) -> int:
    row = conn.execute("SELECT COUNT(*) AS n FROM players WHERE id != ?", (exclude,)).fetchone()
    return int(row["n"])


def seconds_since(stamp: str, now: datetime | None = None) -> int:
    """Сколько секунд прошло с записанного момента. Мусор — считаем давним."""

    try:
        seen = datetime.fromisoformat(stamp)
    except (TypeError, ValueError):
        return 10 ** 9
    if seen.tzinfo is None:
        seen = seen.replace(tzinfo=timezone.utc)
    moment = now or datetime.now(timezone.utc)
    return max(0, int((moment - seen).total_seconds()))


def history(conn: sqlite3.Connection, user_id: int, limit: int = 10) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT * FROM matches
        WHERE player_a = ? OR player_b = ?
        ORDER BY id DESC LIMIT ?
        """,
        (user_id, user_id, limit),
    ).fetchall()


def totals(conn: sqlite3.Connection) -> dict[str, int]:
    players = conn.execute("SELECT COUNT(*) AS n FROM players").fetchone()["n"]
    matches = conn.execute("SELECT COUNT(*) AS n FROM matches").fetchone()["n"]
    return {"players": int(players), "matches": int(matches)}
