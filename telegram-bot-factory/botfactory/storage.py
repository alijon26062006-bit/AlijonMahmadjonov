"""База данных фабрики (SQLite)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiosqlite

from .spec import BotSpec

STATUS_STOPPED = "stopped"
STATUS_RUNNING = "running"
STATUS_ERROR = "error"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY,
    username    TEXT,
    first_name  TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id      INTEGER NOT NULL,
    tg_bot_id     INTEGER,
    username      TEXT,
    token_enc     TEXT NOT NULL,
    token_hash    TEXT NOT NULL UNIQUE,
    prompt        TEXT NOT NULL DEFAULT '',
    spec_json     TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'stopped',
    last_error    TEXT,
    ai_calls      INTEGER NOT NULL DEFAULT 0,
    ai_period     TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bots_owner ON bots(owner_id);
CREATE INDEX IF NOT EXISTS idx_bots_status ON bots(status);

CREATE TABLE IF NOT EXISTS versions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id      INTEGER NOT NULL,
    spec_json   TEXT NOT NULL,
    note        TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_versions_bot ON versions(bot_id);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def period() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def token_fingerprint(token: str) -> str:
    """Отпечаток токена — чтобы ловить повторы, не храня сам токен в открытом виде."""
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass
class BotRecord:
    id: int
    owner_id: int
    tg_bot_id: Optional[int]
    username: Optional[str]
    token_enc: str
    prompt: str
    spec: BotSpec
    status: str
    last_error: Optional[str]
    ai_calls: int
    ai_period: str

    @property
    def link(self) -> str:
        return f"https://t.me/{self.username}" if self.username else ""

    @property
    def handle(self) -> str:
        return f"@{self.username}" if self.username else f"бот #{self.id}"


def _record(row: aiosqlite.Row) -> BotRecord:
    return BotRecord(
        id=row["id"],
        owner_id=row["owner_id"],
        tg_bot_id=row["tg_bot_id"],
        username=row["username"],
        token_enc=row["token_enc"],
        prompt=row["prompt"],
        spec=BotSpec.model_validate_json(row["spec_json"]),
        status=row["status"],
        last_error=row["last_error"],
        ai_calls=row["ai_calls"],
        ai_period=row["ai_period"],
    )


class Storage:
    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._db: aiosqlite.Connection | None = None

    async def open(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self._path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(_SCHEMA)
        await self._db.commit()

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("База не открыта — вызовите Storage.open()")
        return self._db

    # --- пользователи -------------------------------------------------

    async def remember_user(self, user_id: int, username: str | None, first_name: str | None) -> None:
        await self.db.execute(
            "INSERT INTO users (id, username, first_name, created_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET username=excluded.username, first_name=excluded.first_name",
            (user_id, username, first_name, now()),
        )
        await self.db.commit()

    # --- боты ---------------------------------------------------------

    async def count_bots(self, owner_id: int) -> int:
        async with self.db.execute(
            "SELECT COUNT(*) AS n FROM bots WHERE owner_id = ?", (owner_id,)
        ) as cur:
            row = await cur.fetchone()
        return int(row["n"]) if row else 0

    async def token_taken(self, token: str) -> bool:
        async with self.db.execute(
            "SELECT 1 FROM bots WHERE token_hash = ?", (token_fingerprint(token),)
        ) as cur:
            return await cur.fetchone() is not None

    async def create_bot(
        self,
        *,
        owner_id: int,
        token_enc: str,
        token_hash: str,
        tg_bot_id: int | None,
        username: str | None,
        prompt: str,
        spec: BotSpec,
    ) -> BotRecord:
        stamp = now()
        cursor = await self.db.execute(
            "INSERT INTO bots (owner_id, tg_bot_id, username, token_enc, token_hash, prompt, "
            "spec_json, status, ai_period, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                owner_id,
                tg_bot_id,
                username,
                token_enc,
                token_hash,
                prompt,
                spec.model_dump_json(),
                STATUS_STOPPED,
                period(),
                stamp,
                stamp,
            ),
        )
        await self.db.commit()
        bot_id = int(cursor.lastrowid)
        await self.save_version(bot_id, spec, "создан")
        record = await self.get_bot(bot_id)
        assert record is not None
        return record

    async def get_bot(self, bot_id: int) -> BotRecord | None:
        async with self.db.execute("SELECT * FROM bots WHERE id = ?", (bot_id,)) as cur:
            row = await cur.fetchone()
        return _record(row) if row else None

    async def list_bots(self, owner_id: int) -> list[BotRecord]:
        async with self.db.execute(
            "SELECT * FROM bots WHERE owner_id = ? ORDER BY id", (owner_id,)
        ) as cur:
            rows = await cur.fetchall()
        return [_record(row) for row in rows]

    async def list_by_status(self, status: str) -> list[BotRecord]:
        async with self.db.execute("SELECT * FROM bots WHERE status = ?", (status,)) as cur:
            rows = await cur.fetchall()
        return [_record(row) for row in rows]

    async def update_spec(self, bot_id: int, spec: BotSpec, note: str) -> None:
        await self.save_version(bot_id, spec, note)
        await self.db.execute(
            "UPDATE bots SET spec_json = ?, updated_at = ? WHERE id = ?",
            (spec.model_dump_json(), now(), bot_id),
        )
        await self.db.commit()

    async def set_status(self, bot_id: int, status: str, error: str | None = None) -> None:
        await self.db.execute(
            "UPDATE bots SET status = ?, last_error = ?, updated_at = ? WHERE id = ?",
            (status, error, now(), bot_id),
        )
        await self.db.commit()

    async def set_prompt(self, bot_id: int, prompt: str) -> None:
        await self.db.execute(
            "UPDATE bots SET prompt = ?, updated_at = ? WHERE id = ?", (prompt, now(), bot_id)
        )
        await self.db.commit()

    async def delete_bot(self, bot_id: int) -> None:
        await self.db.execute("DELETE FROM versions WHERE bot_id = ?", (bot_id,))
        await self.db.execute("DELETE FROM bots WHERE id = ?", (bot_id,))
        await self.db.commit()

    # --- версии -------------------------------------------------------

    async def save_version(self, bot_id: int, spec: BotSpec, note: str) -> None:
        await self.db.execute(
            "INSERT INTO versions (bot_id, spec_json, note, created_at) VALUES (?, ?, ?, ?)",
            (bot_id, spec.model_dump_json(), note, now()),
        )
        await self.db.commit()

    async def previous_version(self, bot_id: int) -> BotSpec | None:
        """Предпоследняя сохранённая версия — то, что было до последней правки."""
        async with self.db.execute(
            "SELECT spec_json FROM versions WHERE bot_id = ? ORDER BY id DESC LIMIT 2", (bot_id,)
        ) as cur:
            rows = await cur.fetchall()
        if len(rows) < 2:
            return None
        return BotSpec.model_validate_json(rows[1]["spec_json"])

    async def drop_last_version(self, bot_id: int) -> None:
        await self.db.execute(
            "DELETE FROM versions WHERE id = (SELECT id FROM versions WHERE bot_id = ? "
            "ORDER BY id DESC LIMIT 1)",
            (bot_id,),
        )
        await self.db.commit()

    # --- сводка -------------------------------------------------------

    async def stats(self) -> dict[str, int]:
        """Общие числа по всей фабрике — для администратора."""
        result: dict[str, int] = {}
        async with self.db.execute("SELECT COUNT(*) AS n FROM users") as cur:
            row = await cur.fetchone()
            result["users"] = int(row["n"]) if row else 0
        async with self.db.execute("SELECT COUNT(*) AS n FROM bots") as cur:
            row = await cur.fetchone()
            result["bots"] = int(row["n"]) if row else 0
        async with self.db.execute(
            "SELECT status, COUNT(*) AS n FROM bots GROUP BY status"
        ) as cur:
            for row in await cur.fetchall():
                result[str(row["status"])] = int(row["n"])
        async with self.db.execute(
            "SELECT COALESCE(SUM(ai_calls), 0) AS n FROM bots WHERE ai_period = ?", (period(),)
        ) as cur:
            row = await cur.fetchone()
            result["ai_calls"] = int(row["n"]) if row else 0
        return result

    # --- лимит ИИ -----------------------------------------------------

    async def take_ai_quota(self, bot_id: int, limit: int) -> bool:
        """Списать один ответ ИИ. False — месячный лимит исчерпан."""
        if limit <= 0:
            return True
        current = period()
        async with self.db.execute(
            "SELECT ai_calls, ai_period FROM bots WHERE id = ?", (bot_id,)
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return False
        used = 0 if row["ai_period"] != current else int(row["ai_calls"])
        if used >= limit:
            return False
        await self.db.execute(
            "UPDATE bots SET ai_calls = ?, ai_period = ? WHERE id = ?",
            (used + 1, current, bot_id),
        )
        await self.db.commit()
        return True

    async def ai_used(self, bot_id: int) -> int:
        async with self.db.execute(
            "SELECT ai_calls, ai_period FROM bots WHERE id = ?", (bot_id,)
        ) as cur:
            row = await cur.fetchone()
        if row is None or row["ai_period"] != period():
            return 0
        return int(row["ai_calls"])
