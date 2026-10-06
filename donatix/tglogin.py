"""Вход и регистрация через Telegram (бот-магазин): без пароля и без ввода номера.

1. Сайт создаёт одноразовый токен (10 минут), привязанный к этому браузеру (сессии), и даёт ссылку
   t.me/<бот>?start=login_<токен>.
2. Человек жмёт Start. Первый раз бот просит «Поделиться номером» (номер подтверждает сам Telegram),
   дальше — одна кнопка «Войти». Аккаунт — тот же, что у покупок в боте (общий баланс).
3. Страница входа сама спрашивает сервер «подтвердили?» и входит. Войти может только тот браузер,
   который начал вход (токен в его сессии). Перед входом бот всегда показывает, с какого устройства
   и IP входят, и просит нажать «Войти» — если ссылку подсунули чужие, человек видит чужое устройство.

Привязка: залогиненный на сайте человек может привязать свой Telegram к текущему аккаунту.
"""

from __future__ import annotations

import re
import secrets
import sqlite3
import time
from typing import Any

from . import db

TTL = 600


def bot_username(conn: sqlite3.Connection) -> str:
    return db.get_setting(conn, "shop.bot_username") or ""


def device(ua: str) -> str:
    """«Android · Chrome», «iPhone · Safari», «Windows · Chrome» — чтобы человек узнал своё устройство."""
    ua = ua or ""
    os_ = next((n for k, n in (("Android", "Android"), ("iPhone", "iPhone"), ("iPad", "iPad"),
                               ("Windows", "Windows"), ("Mac OS", "Mac"), ("Linux", "Linux")) if k in ua), "устройство")
    app = "приложение Donatix" if "DonatixApp" in ua else next(
        (n for k, n in (("YaBrowser", "Яндекс"), ("Edg/", "Edge"), ("OPR/", "Opera"), ("Chrome", "Chrome"),
                        ("Firefox", "Firefox"), ("Safari", "Safari")) if k in ua), "браузер")
    return f"{os_} · {app}"


def create(conn: sqlite3.Connection, ua: str, ip: str, link_user_id: int | None = None) -> str:
    conn.execute("DELETE FROM tg_logins WHERE expires_at < ?", (time.time() - 3600,))
    token = secrets.token_urlsafe(18).replace("-", "x").replace("_", "y")   # для ?start= — только буквы и цифры
    conn.execute("INSERT INTO tg_logins (token, created_at, expires_at, status, ua, ip, link_user_id) "
                 "VALUES (?, ?, ?, 'new', ?, ?, ?)",
                 (token, db.now(), time.time() + TTL, ua[:300], ip[:64], link_user_id))
    return token


def get(conn: sqlite3.Connection, token: str) -> sqlite3.Row | None:
    if not re.fullmatch(r"[A-Za-z0-9]{10,40}", token or ""):
        return None
    row = conn.execute("SELECT * FROM tg_logins WHERE token = ?", (token,)).fetchone()
    return row if row is not None and row["expires_at"] >= time.time() else None


def approve(conn: sqlite3.Connection, token: str, tg_id: int) -> tuple[bool, str]:
    """Человек в Telegram подтвердил вход. (успех, текст ответа в боте)."""
    row = get(conn, token)
    if row is None or row["status"] != "new":
        return False, "expired"
    su = conn.execute("SELECT user_id FROM shop_users WHERE tg_id = ?", (tg_id,)).fetchone()
    if row["link_user_id"]:   # привязка Telegram к аккаунту, в который уже вошли на сайте
        target = int(row["link_user_id"])
        if su is not None and su["user_id"] != target:
            if not _empty(conn, su["user_id"]):
                conn.execute("UPDATE tg_logins SET status = 'denied' WHERE token = ?", (token,))
                return False, "busy"
            conn.execute("UPDATE shop_users SET user_id = ? WHERE tg_id = ?", (target, tg_id))
        elif su is None:
            conn.execute("INSERT INTO shop_users (tg_id, user_id, name, lang, created_at, last_seen) "
                         "VALUES (?, ?, '', '', ?, ?)", (tg_id, target, db.now(), db.now()))
        user_id = target
    else:
        if su is None:
            return False, "expired"
        user_id = su["user_id"]
    u = conn.execute("SELECT status FROM users WHERE id = ?", (user_id,)).fetchone()
    if u is None or u["status"] == "blocked":
        conn.execute("UPDATE tg_logins SET status = 'denied' WHERE token = ?", (token,))
        return False, "blocked"
    conn.execute("UPDATE tg_logins SET status = 'ok', user_id = ?, tg_id = ? WHERE token = ?", (user_id, tg_id, token))
    return True, "ok"


def deny(conn: sqlite3.Connection, token: str) -> None:
    conn.execute("UPDATE tg_logins SET status = 'denied' WHERE token = ? AND status = 'new'", (token,))


def consume(conn: sqlite3.Connection, token: str) -> int | None:
    """Браузер, начавший вход, забирает результат — один раз."""
    row = get(conn, token)
    if row is None or row["status"] != "ok":
        return None
    done = conn.execute("UPDATE tg_logins SET status = 'used' WHERE token = ? AND status = 'ok'", (token,)).rowcount
    return int(row["user_id"]) if done else None


def _empty(conn: sqlite3.Connection, user_id: int) -> bool:
    """Аккаунт, созданный ботом и ещё ни разу не использованный, — его можно заменить привязкой."""
    u = conn.execute("SELECT balance_micro, role FROM users WHERE id = ?", (user_id,)).fetchone()
    if u is None:
        return True
    orders = conn.execute("SELECT COUNT(*) FROM orders WHERE user_id = ?", (user_id,)).fetchone()[0]
    pays = conn.execute("SELECT COUNT(*) FROM payments WHERE user_id = ?", (user_id,)).fetchone()[0]
    return u["role"] == "client" and not u["balance_micro"] and not orders and not pays


def save_phone(conn: sqlite3.Connection, user_id: int, phone: str) -> None:
    phone = re.sub(r"[^\d+]", "", phone or "")
    if phone and not phone.startswith("+"):
        phone = "+" + phone
    conn.execute("UPDATE users SET phone = ? WHERE id = ?", (phone[:20] or None, user_id))


def status(conn: sqlite3.Connection, token: str) -> dict[str, Any]:
    row = get(conn, token)
    if row is None:
        return {"state": "expired"}
    return {"state": row["status"]}
