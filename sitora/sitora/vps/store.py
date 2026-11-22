"""Раздел VPS в Sitora: таблицы и общее состояние (база, Hetzner, бот, фоновые задачи).

Таблицы с префиксом vps_ — остальные таблицы Sitora не меняются.
Деньги — общий баланс Sitora в дирамах (shop.move), время — секунды UTC (int).
"""
from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from pathlib import Path

import httpx

from .. import db, shop
from .hetzner import Hetzner

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS vps_servers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  hetzner_id INTEGER,
  name TEXT NOT NULL,
  location TEXT NOT NULL, server_type TEXT NOT NULL, image TEXT NOT NULL,
  cores INTEGER NOT NULL DEFAULT 1, memory REAL NOT NULL DEFAULT 0, disk INTEGER NOT NULL DEFAULT 0,
  price INTEGER NOT NULL,                   -- дирамы за 30 дней, зафиксирована при заказе
  price_usd INTEGER NOT NULL DEFAULT 0,     -- центы USD (по формуле), для отчётов
  cost_hourly_e6 INTEGER NOT NULL DEFAULT 0, cost_monthly INTEGER NOT NULL DEFAULT 0,  -- наш расход у Hetzner, USD
  status TEXT NOT NULL DEFAULT 'initializing',
  state TEXT NOT NULL DEFAULT 'creating',   -- creating | active | suspended | deleted | failed
  ipv4 TEXT NOT NULL DEFAULT '', ipv6 TEXT NOT NULL DEFAULT '',
  agent_hash TEXT NOT NULL DEFAULT '',
  password_state TEXT NOT NULL DEFAULT 'pending',
  paid_until INTEGER NOT NULL, unpaid_since INTEGER,
  warned_low INTEGER NOT NULL DEFAULT 0, warned_delete INTEGER NOT NULL DEFAULT 0,
  last_error TEXT NOT NULL DEFAULT '',
  created_at INTEGER NOT NULL, deleted_at INTEGER
);
CREATE INDEX IF NOT EXISTS vps_servers_user ON vps_servers(user_id);
CREATE TABLE IF NOT EXISTS vps_metrics (
  server_id INTEGER NOT NULL, ts INTEGER NOT NULL,
  cpu REAL, ram REAL, disk REAL, rd REAL, wr REAL, rx REAL, tx REAL, load1 REAL,
  PRIMARY KEY (server_id, ts)
);
CREATE TABLE IF NOT EXISTS vps_approved (user_id INTEGER PRIMARY KEY, at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS vps_audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, action TEXT NOT NULL,
  target TEXT NOT NULL DEFAULT '', details TEXT NOT NULL DEFAULT '', created_at INTEGER NOT NULL
);
"""


def now() -> int:
    return int(time.time())


def audit(conn, user_id, action: str, target: str = "", details: str = "") -> None:
    conn.execute("INSERT INTO vps_audit (user_id, action, target, details, created_at) VALUES (?,?,?,?,?)",
                 (user_id, action, target, details[:300], now()))


def approved(conn, config, user_id: int) -> bool:
    if shop.is_admin(conn, config, user_id):
        return True
    return conn.execute("SELECT 1 FROM vps_approved WHERE user_id = ?", (user_id,)).fetchone() is not None


class Vps:
    def __init__(self, config, bot=None, *, hetzner_transport: httpx.AsyncBaseTransport | None = None,
                 http_transport: httpx.AsyncBaseTransport | None = None, ssh=None):
        self.config, self.bot = config, bot
        self.hetzner_transport, self.http_transport, self.ssh = hetzner_transport, http_transport, ssh
        self.data_dir = Path(config.db_path).parent
        self.key_path = self.data_dir / "vps_ssh_key"
        self.tasks: set[asyncio.Task] = set()
        self.fast = False
        self._hz: Hetzner | None = None
        db.init(config.db_path)
        conn = self.conn()
        conn.executescript(SCHEMA)
        conn.close()

    def conn(self) -> sqlite3.Connection:
        return db.connect(self.config.db_path)

    def hz(self) -> Hetzner:
        token = self.config.hetzner_token
        if self._hz is None or self._hz.token != token:
            self._hz = Hetzner(token, self.config.hetzner_url, self.hetzner_transport)
        return self._hz

    @property
    def agent_url(self) -> str:
        base = self.config.base_url.rstrip("/")
        return base.replace("https://", "wss://", 1).replace("http://", "ws://", 1) + "/agent"

    def enabled(self, conn) -> bool:
        return bool(self.config.hetzner_token) and db.get_setting(conn, "vps_enabled", "1") == "1"

    def spawn(self, coro) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self.tasks.add(task)

        def done(t: asyncio.Task) -> None:
            self.tasks.discard(t)
            if not t.cancelled() and t.exception():
                log.error("VPS: фоновая задача упала: %r", t.exception())
        task.add_done_callback(done)
        return task

    # ── уведомления через бота Sitora ──

    async def tell(self, chat_id: int, text: str) -> None:
        if self.bot is not None:
            await asyncio.to_thread(self.bot.safe, "sendMessage", chat_id=chat_id, text=text,
                                    disable_web_page_preview=True)

    async def tell_admins(self, text: str) -> None:
        conn = self.conn()
        admins = shop.admin_list(conn, self.config)
        conn.close()
        for a in admins:
            await self.tell(a, text)
