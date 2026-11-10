"""Розыгрыш по промокодам: админ генерирует N случайных кодов и задаёт призы — бот сам раскладывает
призы по случайным кодам, остальные пустые. Коды админ раздаёт (канал, сторис). Клиент вводит код
в Telegram-боте (кнопка на главном экране): 3 попытки (кода) в день на человека, каждый код — один раз.
В канале публикуются только выигрыши («код … активировал @user — выиграл …»).
В админке видны все коды, призы и аккаунт, который активировал каждый код. Приз выдаётся вручную:
админ получает уведомление и отмечает «Выдано».
"""

from __future__ import annotations

import html
import logging
import re
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from . import db

log = logging.getLogger(__name__)

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"   # без 0/O, 1/I/L — чтобы не путали при вводе
MAX_CODES = 1000
PER_DAY = 3                                     # сколько кодов человек может активировать за день
MAX_WRONG_PER_DAY = 15                          # неверных попыток в день — дальше ждать (перебор кодов)
CHANNEL_KEY = "giveaway.channel"
DEFAULT_CHANNEL = "@donatixtj"

SCHEMA = """
CREATE TABLE IF NOT EXISTS giveaway_batches (     -- розыгрыш: пачка кодов с призами
    id          INTEGER PRIMARY KEY,
    title       TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    active      INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS giveaway_codes (
    id          INTEGER PRIMARY KEY,
    batch_id    INTEGER NOT NULL,
    code        TEXT NOT NULL UNIQUE,
    prize       TEXT,                             -- NULL — пустой код
    user_id     INTEGER,                          -- кто активировал
    used_at     TEXT,
    source      TEXT,                             -- site · bot
    given_at    TEXT                              -- админ отметил «приз выдан»
);
CREATE INDEX IF NOT EXISTS giveaway_codes_user ON giveaway_codes(user_id, used_at);
CREATE TABLE IF NOT EXISTS giveaway_wrong (       -- неверные попытки — защита от перебора
    user_id     INTEGER NOT NULL,
    day         TEXT NOT NULL,
    n           INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, day)
);
"""


class GiveawayError(Exception):
    pass


def init(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def _new_code() -> str:
    return "DX-" + "".join(secrets.choice(ALPHABET) for _ in range(6))


def clean(raw: str) -> str:
    """«dx 7k3p-9a» → «DX-7K3P9A»."""
    s = re.sub(r"[^A-Za-z0-9]", "", raw or "").upper()
    if s.startswith("DX"):
        s = s[2:]
    return "DX-" + s if s else ""


def generate(conn: sqlite3.Connection, count: int, prizes: list[str], title: str = "") -> int:
    """Новый розыгрыш: count кодов, призы — на случайные коды (по одному на приз). Вернёт id розыгрыша."""
    init(conn)
    prizes = [p.strip()[:120] for p in prizes if p.strip()]
    if not 1 <= count <= MAX_CODES:
        raise GiveawayError(f"Кодов — от 1 до {MAX_CODES}.")
    if len(prizes) > count:
        raise GiveawayError("Призов больше, чем кодов.")
    with db.tx(conn):
        bid = conn.execute("INSERT INTO giveaway_batches (title, created_at) VALUES (?, ?)",
                           (title.strip()[:80], db.now())).lastrowid
        codes: set[str] = set()
        while len(codes) < count:
            c = _new_code()
            if c not in codes and conn.execute("SELECT 1 FROM giveaway_codes WHERE code = ?", (c,)).fetchone() is None:
                codes.add(c)
        order = list(codes)
        secrets.SystemRandom().shuffle(order)
        winners = dict(zip(order, prizes))   # первые len(prizes) случайных кодов — с призами
        conn.executemany("INSERT INTO giveaway_codes (batch_id, code, prize) VALUES (?, ?, ?)",
                         [(bid, c, winners.get(c)) for c in sorted(codes)])
    return bid


def live(conn: sqlite3.Connection) -> bool:
    """Есть ли что активировать — тогда показываем кнопку «Проверить промокод»."""
    init(conn)
    return conn.execute("SELECT 1 FROM giveaway_codes c JOIN giveaway_batches b ON b.id = c.batch_id "
                        "WHERE b.active = 1 AND c.user_id IS NULL LIMIT 1").fetchone() is not None


def _day(tz_offset: int, now: datetime | None = None) -> tuple[str, str]:
    """Сегодня по местному времени: (дата, начало дня в UTC для сравнения с used_at)."""
    now = now or datetime.now(timezone.utc)
    local = now + timedelta(hours=tz_offset)
    start_local = local.replace(hour=0, minute=0, second=0, microsecond=0)
    start_utc = start_local - timedelta(hours=tz_offset)
    return local.strftime("%Y-%m-%d"), start_utc.strftime("%Y-%m-%dT%H:%M:%S")


def used_today(conn: sqlite3.Connection, user_id: int, tz_offset: int = 5) -> sqlite3.Row | None:
    init(conn)
    _, since = _day(tz_offset)
    return conn.execute("SELECT * FROM giveaway_codes WHERE user_id = ? AND used_at >= ? ORDER BY used_at DESC LIMIT 1",
                        (user_id, since)).fetchone()


def activate(conn: sqlite3.Connection, user_id: int, raw: str, *, tz_offset: int = 5, source: str = "site") -> dict:
    """Активировать код. Вернёт {"code", "prize"} или бросит GiveawayError с понятной причиной."""
    init(conn)
    code = clean(raw)
    day, since = _day(tz_offset)
    with db.tx(conn):
        wrong = conn.execute("SELECT n FROM giveaway_wrong WHERE user_id = ? AND day = ?", (user_id, day)).fetchone()
        if wrong and wrong["n"] >= MAX_WRONG_PER_DAY:
            raise GiveawayError("Слишком много неверных кодов. Попробуйте завтра. · Имрӯз кӯшишҳо тамом шуд.")
        done = conn.execute("SELECT COUNT(*) FROM giveaway_codes WHERE user_id = ? AND used_at >= ?",
                            (user_id, since)).fetchone()[0]
        if done >= PER_DAY:   # код не проверяем и не тратим — о нём ничего не узнать
            raise GiveawayError(f"Сегодня вы уже использовали {PER_DAY} попытки. Новые — завтра. "
                                f"· Имрӯз {PER_DAY} кӯшиш тамом шуд, фардо боз.")
        row = conn.execute("SELECT c.*, b.active FROM giveaway_codes c JOIN giveaway_batches b ON b.id = c.batch_id "
                           "WHERE c.code = ?", (code,)).fetchone()
        if row is None or not row["active"]:
            # счётчик записываем и при отказе: откат транзакции его бы стёр
            conn.execute("INSERT INTO giveaway_wrong (user_id, day, n) VALUES (?, ?, 1) "
                         "ON CONFLICT(user_id, day) DO UPDATE SET n = n + 1", (user_id, day))
            missing = True
        elif row["user_id"] is not None:
            raise GiveawayError("Этот промокод уже активировали. · Ин рамзро аллакай фаъол кардаанд.")
        else:
            missing = False
            conn.execute("UPDATE giveaway_codes SET user_id = ?, used_at = ?, source = ? WHERE id = ? AND user_id IS NULL",
                         (user_id, db.now(), source, row["id"]))
    if missing:
        raise GiveawayError("Такого промокода нет. Проверьте буквы и цифры. · Чунин рамз нест.")
    return {"code": code, "prize": row["prize"], "left": PER_DAY - done - 1}


def who(conn: sqlite3.Connection, user_id: int) -> str:
    """Как подписать в канале: @username из бота, иначе логин (без почты)."""
    r = conn.execute("SELECT username FROM shop_users WHERE user_id = ? AND username IS NOT NULL LIMIT 1",
                     (user_id,)).fetchone()
    if r and r["username"]:
        return "@" + r["username"]
    u = conn.execute("SELECT login FROM users WHERE id = ?", (user_id,)).fetchone()
    login = (u["login"] if u else "") or "клиент"
    if login.startswith("tg") and login[2:].isdigit():
        return "клиент из бота"
    return login[:2] + "***" if len(login) > 3 else login


def channel(conn: sqlite3.Connection) -> str:
    return (db.get_setting(conn, CHANNEL_KEY) or DEFAULT_CHANNEL).strip()


def post_text(code: str, name: str, prize: str | None) -> str:
    if prize:
        return (f"🎉 Промокод <code>{html.escape(code)}</code> активировал {html.escape(name)} — "
                f"выиграл: <b>{html.escape(prize)}</b>!\n\nТабрик! Рамзи бурднок 🎁")
    return (f"🎟 Промокод <code>{html.escape(code)}</code> активировал {html.escape(name)} — пусто.\n"
            "Холӣ — дафъаи дигар бахт ёр шавад!")


def announce(config: Any, conn: sqlite3.Connection, user_id: int, result: dict, api: Any = None) -> None:
    """Пост в канал и уведомление админу о выигрыше — в фоне, клиент не ждёт Telegram."""
    name = who(conn, user_id)
    chat = channel(conn)
    text = post_text(result["code"], name, result["prize"])
    login = (conn.execute("SELECT login FROM users WHERE id = ?", (user_id,)).fetchone() or {"login": "?"})["login"]

    def run() -> None:
        # В канал — только победители: пустые коды не публикуем
        if result["prize"] and config.shop_bot_token and chat and chat != "-":
            try:
                from .tgbot import TelegramApi
                (api or TelegramApi(config.shop_bot_token))("sendMessage", chat_id=chat, text=text, parse_mode="HTML",
                                                           disable_web_page_preview=True)
            except Exception as exc:  # noqa: BLE001
                log.warning("розыгрыш: пост в канал %s не ушёл: %s", chat, exc)
        if result["prize"]:
            from .worker import notify_admin
            notify_admin(config, f"🎁 Розыгрыш: код {result['code']} — приз «{result['prize']}». "
                                 f"Победитель: {login} (id {user_id}, {name}). Выдайте приз и отметьте "
                                 f"«Выдано» в админке → Розыгрыш.")
    if api is not None:
        run()
    else:
        threading.Thread(target=run, daemon=True).start()


def batches(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    init(conn)
    out = []
    for b in conn.execute("SELECT * FROM giveaway_batches ORDER BY id DESC LIMIT 20").fetchall():
        st = conn.execute("SELECT COUNT(*) AS n, SUM(user_id IS NOT NULL) AS used, SUM(prize IS NOT NULL) AS prizes, "
                          "SUM(prize IS NOT NULL AND user_id IS NOT NULL) AS won FROM giveaway_codes WHERE batch_id = ?",
                          (b["id"],)).fetchone()
        codes = conn.execute("SELECT c.*, u.login FROM giveaway_codes c LEFT JOIN users u ON u.id = c.user_id "
                             "WHERE c.batch_id = ? ORDER BY c.prize IS NULL, c.user_id IS NULL, c.used_at DESC, c.code",
                             (b["id"],)).fetchall()   # сверху призы, потом активированные
        out.append({**dict(b), "n": st["n"] or 0, "used": st["used"] or 0, "prizes": st["prizes"] or 0,
                    "won": st["won"] or 0,
                    "codes": [{**dict(c), "who": who(conn, c["user_id"]) if c["user_id"] else ""} for c in codes]})
    return out


def mark_given(conn: sqlite3.Connection, code_id: int) -> bool:
    init(conn)
    return conn.execute("UPDATE giveaway_codes SET given_at = ? WHERE id = ? AND prize IS NOT NULL "
                        "AND user_id IS NOT NULL AND given_at IS NULL", (db.now(), code_id)).rowcount == 1


def set_active(conn: sqlite3.Connection, batch_id: int, on: bool) -> None:
    init(conn)
    conn.execute("UPDATE giveaway_batches SET active = ? WHERE id = ?", (1 if on else 0, batch_id))
