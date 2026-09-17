"""Хранилище: SQLite. Деньги и незаконченные игры переживают перезапуск.

Главное правило файла: любое изменение баланса идёт одной транзакцией и
одновременно пишет строку в ledger. По ledger всегда можно собрать баланс
заново и увидеть, откуда взялась каждая монета.
"""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id      INTEGER PRIMARY KEY,
    name         TEXT    NOT NULL DEFAULT '',
    balance      INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0),
    created_at   TEXT    NOT NULL,
    last_bonus   TEXT
);

CREATE TABLE IF NOT EXISTS ledger (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    delta      INTEGER NOT NULL,
    reason     TEXT    NOT NULL,
    ref        TEXT    NOT NULL DEFAULT '',
    created_at TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS ledger_user ON ledger(user_id, id);

CREATE TABLE IF NOT EXISTS games (
    game_id     TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    chat_id     INTEGER NOT NULL,
    message_id  INTEGER,
    bet         INTEGER NOT NULL,
    mines       INTEGER NOT NULL,
    mine_cells  TEXT    NOT NULL,
    opened      TEXT    NOT NULL DEFAULT '[]',
    status      TEXT    NOT NULL DEFAULT 'active',
    payout      INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL,
    finished_at TEXT
);
-- Одна активная игра на человека. Это не «договорённость в коде», а запрет
-- на уровне базы: вторую активную игру просто не дадут вставить.
CREATE UNIQUE INDEX IF NOT EXISTS games_one_active
    ON games(user_id) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS games_user ON games(user_id, created_at);
"""


class Insufficient(RuntimeError):
    """На балансе не хватает монет."""


class NoGame(RuntimeError):
    """Активной игры нет (или она уже закрыта другим обновлением)."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: str | os.PathLike[str]) -> sqlite3.Connection:
    """Открыть базу и привести её в рабочий вид."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        path,
        # Ждём блокировку до 30 с вместо мгновенного "database is locked".
        timeout=30,
        isolation_level=None,  # транзакциями управляем сами, явно
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")      # читатели не блокируют писателя
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    return conn


@contextmanager
def tx(conn: sqlite3.Connection):
    """Транзакция на запись.

    BEGIN IMMEDIATE берёт блокировку сразу, а не при первой записи. Без этого
    две одновременные «проверь баланс → спиши» могли бы прочитать один и тот же
    баланс и списать дважды.
    """

    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


# ── пользователи и деньги ──────────────────────────────────────────────────

def ensure_user(conn: sqlite3.Connection, user_id: int, name: str, start_balance: int) -> int:
    """Завести игрока, если его нет. Вернуть баланс."""

    with tx(conn):
        row = conn.execute(
            "SELECT balance FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO users(user_id, name, balance, created_at) VALUES (?,?,?,?)",
                (user_id, name[:64], start_balance, now()),
            )
            if start_balance:
                _ledger(conn, user_id, start_balance, "start")
            return start_balance
        if name:
            conn.execute("UPDATE users SET name = ? WHERE user_id = ?", (name[:64], user_id))
        return int(row["balance"])


def balance(conn: sqlite3.Connection, user_id: int) -> int:
    row = conn.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)).fetchone()
    return int(row["balance"]) if row else 0


def _ledger(conn: sqlite3.Connection, user_id: int, delta: int, reason: str, ref: str = "") -> None:
    conn.execute(
        "INSERT INTO ledger(user_id, delta, reason, ref, created_at) VALUES (?,?,?,?,?)",
        (user_id, delta, reason, ref, now()),
    )


def _add(conn: sqlite3.Connection, user_id: int, delta: int, reason: str, ref: str = "") -> int:
    """Изменить баланс ВНУТРИ уже открытой транзакции. Вернуть новый баланс."""

    row = conn.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        raise Insufficient("Игрок ещё не зарегистрирован.")
    new = int(row["balance"]) + delta
    if new < 0:
        raise Insufficient("Не хватает монет.")
    conn.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new, user_id))
    _ledger(conn, user_id, delta, reason, ref)
    return new


def deposit(conn: sqlite3.Connection, user_id: int, amount: int, reason: str, ref: str = "") -> int:
    with tx(conn):
        return _add(conn, user_id, amount, reason, ref)


def transfer(conn: sqlite3.Connection, sender: int, receiver: int, amount: int) -> tuple[int, int]:
    """Перевод между игроками — одной транзакцией.

    Либо у одного списалось И другому пришло, либо не случилось ничего.
    Монеты не могут «испариться» между двумя отдельными записями.
    """

    if amount <= 0:
        raise ValueError("Сумма перевода должна быть больше нуля.")
    if sender == receiver:
        raise ValueError("Себе переводить нельзя.")
    with tx(conn):
        left = _add(conn, sender, -amount, "send_out", str(receiver))
        got = _add(conn, receiver, amount, "send_in", str(sender))
        return left, got


def claim_bonus(conn: sqlite3.Connection, user_id: int, amount: int, hours: int) -> tuple[bool, int, int]:
    """Выдать бонус, если прошло `hours` часов.

    Возвращает (выдали?, баланс, сколько минут ждать).
    Проверка времени и начисление — в одной транзакции, поэтому два быстрых
    /bonus подряд не выдадут бонус дважды.
    """

    with tx(conn):
        row = conn.execute(
            "SELECT last_bonus FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row is None:
            raise Insufficient("Игрок ещё не зарегистрирован.")
        last = row["last_bonus"]
        if last:
            try:
                left = datetime.fromisoformat(last) + timedelta(hours=hours) - datetime.now(timezone.utc)
            except ValueError:
                left = timedelta(0)
            if left.total_seconds() > 0:
                bal = int(conn.execute(
                    "SELECT balance FROM users WHERE user_id = ?", (user_id,)
                ).fetchone()["balance"])
                return False, bal, int(left.total_seconds() // 60) + 1
        bal = _add(conn, user_id, amount, "bonus")
        conn.execute("UPDATE users SET last_bonus = ? WHERE user_id = ?", (now(), user_id))
        return True, bal, 0


def top(conn: sqlite3.Connection, limit: int = 10) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT user_id, name, balance FROM users ORDER BY balance DESC, user_id LIMIT ?",
        (limit,),
    ).fetchall()


# ── игры ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Game:
    game_id: str
    user_id: int
    chat_id: int
    message_id: int | None
    bet: int
    mines: int
    mine_cells: tuple[int, ...]
    opened: tuple[int, ...]
    status: str


def _game(row: sqlite3.Row) -> Game:
    return Game(
        game_id=row["game_id"],
        user_id=int(row["user_id"]),
        chat_id=int(row["chat_id"]),
        message_id=row["message_id"],
        bet=int(row["bet"]),
        mines=int(row["mines"]),
        mine_cells=tuple(json.loads(row["mine_cells"])),
        opened=tuple(json.loads(row["opened"])),
        status=row["status"],
    )


def start_game(
    conn: sqlite3.Connection,
    user_id: int,
    chat_id: int,
    bet: int,
    mines: int,
    mine_cells: tuple[int, ...],
) -> Game:
    """Списать ставку и создать игру — одной транзакцией.

    Ставка списывается СРАЗУ. Иначе при падении процесса посреди игры можно
    было бы сыграть бесплатно.
    """

    game_id = secrets.token_hex(4)  # короткий: он влезает в callback_data
    with tx(conn):
        if conn.execute(
            "SELECT 1 FROM games WHERE user_id = ? AND status = 'active'", (user_id,)
        ).fetchone():
            raise RuntimeError("active-game")
        _add(conn, user_id, -bet, "bet", game_id)
        conn.execute(
            "INSERT INTO games(game_id, user_id, chat_id, bet, mines, mine_cells, created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (game_id, user_id, chat_id, bet, mines, json.dumps(list(mine_cells)), now()),
        )
    return Game(game_id, user_id, chat_id, None, bet, mines, tuple(mine_cells), (), "active")


def active_game(conn: sqlite3.Connection, user_id: int) -> Game | None:
    row = conn.execute(
        "SELECT * FROM games WHERE user_id = ? AND status = 'active'", (user_id,)
    ).fetchone()
    return _game(row) if row else None


def bind_message(conn: sqlite3.Connection, game_id: str, message_id: int) -> None:
    conn.execute("UPDATE games SET message_id = ? WHERE game_id = ?", (message_id, game_id))


def open_cell(conn: sqlite3.Connection, game_id: str, index: int) -> Game:
    """Отметить клетку открытой.

    UPDATE ... WHERE status='active' AND opened NOT LIKE ... нам не подходит
    (JSON), поэтому читаем и пишем внутри одной IMMEDIATE-транзакции: два
    одновременных нажатия не смогут открыть одну клетку дважды.
    """

    with tx(conn):
        row = conn.execute(
            "SELECT * FROM games WHERE game_id = ? AND status = 'active'", (game_id,)
        ).fetchone()
        if row is None:
            raise NoGame(game_id)
        opened = json.loads(row["opened"])
        if index in opened:
            raise NoGame("cell-taken")
        opened.append(index)
        conn.execute("UPDATE games SET opened = ? WHERE game_id = ?", (json.dumps(opened), game_id))
        game = _game(row)
    return replace(game, opened=tuple(opened))


def finish_game(conn: sqlite3.Connection, game_id: str, status: str, payout_amount: int = 0) -> int:
    """Закрыть игру и (если выиграл) начислить выплату — одной транзакцией.

    Возвращает баланс после начисления. Если игру уже закрыло другое
    обновление — NoGame, и второй раз деньги не начислятся.
    """

    with tx(conn):
        row = conn.execute(
            "SELECT user_id FROM games WHERE game_id = ? AND status = 'active'", (game_id,)
        ).fetchone()
        if row is None:
            raise NoGame(game_id)
        user_id = int(row["user_id"])
        conn.execute(
            "UPDATE games SET status = ?, payout = ?, finished_at = ? WHERE game_id = ?",
            (status, payout_amount, now(), game_id),
        )
        if payout_amount:
            return _add(conn, user_id, payout_amount, "win", game_id)
        return balance(conn, user_id)


def stats(conn: sqlite3.Connection, user_id: int) -> dict[str, int]:
    row = conn.execute(
        "SELECT COUNT(*) AS games,"
        " SUM(CASE WHEN status = 'lost' THEN 1 ELSE 0 END) AS lost,"
        " SUM(CASE WHEN status IN ('cashout','cleared') THEN 1 ELSE 0 END) AS won,"
        " COALESCE(SUM(payout), 0) - COALESCE(SUM(bet), 0) AS net"
        " FROM games WHERE user_id = ? AND status != 'active'",
        (user_id,),
    ).fetchone()
    return {
        "games": int(row["games"] or 0),
        "won": int(row["won"] or 0),
        "lost": int(row["lost"] or 0),
        "net": int(row["net"] or 0),
    }
