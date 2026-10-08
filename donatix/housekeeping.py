"""Уборка раз в сутки: только служебный мусор, данные людей не трогаем.

НЕ удаляется никогда: аккаунты, балансы, транзакции, заказы, заявки на пополнение, ЧЕКИ (файлы и записи),
тикеты и их файлы, рефералы, D-коины, уведомления за последний год.

Удаляется: истёкшие коды входа и привязки, закрытые входы старше 90 дней (история входов за 90 дней остаётся),
служебные отметки сообщений админу по уже решённым заявкам, слежение бота за давно закрытыми заказами,
кэш ников игроков старше 60 дней, прочитанные уведомления старше года. Потом база «поджимается» (WAL, optimize).
"""

from __future__ import annotations

import logging
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from . import db

log = logging.getLogger(__name__)

HOUR_LOCAL = 4          # в 4 утра по Душанбе — меньше всего покупателей


def _ago(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")


def _table(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone() is not None


def run(conn: sqlite3.Connection) -> dict[str, int]:
    """Одна уборка. Вернёт, сколько строк удалено в каждой таблице."""
    done: dict[str, int] = {}

    def delete(table: str, where: str, args: tuple[Any, ...] = ()) -> None:
        if _table(conn, table):
            n = conn.execute(f"DELETE FROM {table} WHERE {where}", args).rowcount
            if n:
                done[table] = done.get(table, 0) + n

    now = time.time()
    delete("tg_logins", "expires_at < ?", (now - 3600,))
    delete("support_link_codes", "expires_at < ?", (now,))
    delete("support_codes", "expires_at < ?", (now - 86400,))
    delete("logins", "ended_at IS NOT NULL AND created_at < ?", (_ago(90),))   # открытые входы не трогаем
    delete("payment_msgs", "payment_id IN (SELECT id FROM payments WHERE status != 'pending' AND "
                           "COALESCE(resolved_at, created_at) < ?)", (_ago(7),))
    delete("shop_watch", "created_at < ?", (_ago(7),))
    delete("player_names", "checked_at < ?", (now - 60 * 86400,))
    delete("notifications", "read_at IS NOT NULL AND created_at < ?", (_ago(365),))
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.execute("PRAGMA optimize")
    except sqlite3.Error as exc:   # база занята — подожмём в следующий раз
        log.info("уборка: checkpoint отложен: %s", exc)
    return done


def maybe_run(conn: sqlite3.Connection, tz_offset: int = 5, now: datetime | None = None) -> dict[str, int] | None:
    """Раз в сутки, после 4:00 по местному времени. Вызывает воркер."""
    local = (now or datetime.now(timezone.utc)).astimezone(timezone(timedelta(hours=tz_offset)))
    today = local.strftime("%Y-%m-%d")
    if local.hour < HOUR_LOCAL or db.get_setting(conn, "hk.last_day") == today:
        return None
    db.set_setting(conn, "hk.last_day", today)
    try:
        done = run(conn)
    except sqlite3.Error:
        log.exception("уборка")
        return None
    if done:
        log.info("уборка: удалено %s", done)
    return done
