"""Сообщение покупателю в Telegram о КАЖДОМ решении — где бы он ни купил (сайт, бот, мини-приложение).

Пополнение зачислено / отклонено, заказ выполнен / не выполнен (деньги вернулись) — всем, у кого
аккаунт связан с Telegram (shop_users). Пишет бот-магазин (или бот мини-приложения, если магазина нет).

Бот-магазин и мини-приложение сами пишут о том, за чем следят, — сразу. Этот обход (воркер, каждые
~20 с) подбирает всё остальное: заказ на сайте, автоплатёж, решение кассира, возврат позже. Одно
событие — одно сообщение: кто отправил, тот отмечает его в buyer_notified, остальные пропускают.
Старое (до первого запуска) не рассылаем.
"""

from __future__ import annotations

import logging
import sqlite3

import httpx

from . import accounts, db
from .config import Config

log = logging.getLogger("donatix.buyernotify")

SINCE_KEY = "buyer_notify.since"
GRACE = 10      # секунд: сначала свой бот-магазин/мини-приложение (они пишут сразу и красивее)
BATCH = 50


def ensure(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS buyer_notified (kind TEXT NOT NULL, obj_id INTEGER NOT NULL, "
                 "at TEXT NOT NULL, PRIMARY KEY (kind, obj_id))")


def mark(conn: sqlite3.Connection, kind: str, obj_id: int) -> bool:
    """Отметить «сообщили». False — уже сообщил кто-то другой."""
    ensure(conn)
    return bool(conn.execute("INSERT OR IGNORE INTO buyer_notified (kind, obj_id, at) VALUES (?, ?, ?)",
                             (kind, int(obj_id), db.now())).rowcount)


def _token(config: Config) -> str:
    return config.shop_bot_token or config.gift_bot_token


def _send(config: Config, chat_id: int, text: str) -> bool:
    try:
        r = httpx.post(f"https://api.telegram.org/bot{_token(config)}/sendMessage", timeout=10,
                       json={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True})
        return r.status_code == 200
    except httpx.HTTPError as exc:
        log.warning("уведомление покупателю %s: %s", chat_id, exc.__class__.__name__)
        return False


def order_text(conn: sqlite3.Connection, config: Config, lang: str, o: sqlite3.Row) -> str:
    from .shopbot import _e, delivery_text, money, tjs_rate, tr
    if o["status"] == "completed":
        return tr(lang, "done", id=o["public_id"], product=_e(o["product_name"])) + delivery_text(o)
    return tr(lang, "failed", id=o["public_id"], product=_e(o["product_name"]), reason=_e(o["error"] or ""),
              total=money(o["total_micro"], tjs_rate(conn, config)))


def payment_text(conn: sqlite3.Connection, config: Config, lang: str, p: sqlite3.Row) -> str:
    from .shopbot import _e, money, tjs_rate, tr
    if p["status"] != "paid":
        return tr(lang, "rejected", id=p["id"], reason=_e(p["admin_note"] or ""))
    rate = tjs_rate(conn, config)
    user = accounts.get_user(conn, p["user_id"])
    return tr(lang, "paid", amount=money(p["amount_micro"], rate), balance=money(user["balance_micro"], rate))


def tick(conn: sqlite3.Connection, config: Config) -> int:
    """Из воркера: всем, у кого с прошлого раза что-то решилось, — сообщение в Telegram."""
    if not _token(config):
        return 0
    ensure(conn)
    since = db.get_setting(conn, SINCE_KEY)
    if not since:   # первый запуск — старые заказы и заявки не рассылаем
        db.set_setting(conn, SINCE_KEY, db.now())
        return 0
    from .shopbot import _ago
    until = _ago(GRACE)
    tg_of: dict[int, list[sqlite3.Row]] = {}

    def chats(user_id: int) -> list[sqlite3.Row]:
        if user_id not in tg_of:
            tg_of[user_id] = conn.execute("SELECT tg_id, lang FROM shop_users WHERE user_id = ?",
                                          (user_id,)).fetchall()
        return tg_of[user_id]

    watched = _with_intent(conn)
    sent = 0
    jobs = [("order", r, order_text) for r in conn.execute(
                "SELECT * FROM orders WHERE status IN ('completed', 'failed') "
                "AND COALESCE(completed_at, updated_at) >= ? AND COALESCE(completed_at, updated_at) < ? "
                "AND user_id IN (SELECT user_id FROM shop_users) "
                "AND id NOT IN (SELECT obj_id FROM buyer_notified WHERE kind = 'order') ORDER BY id LIMIT ?",
                (since, until, BATCH))]
    jobs += [("pay", r, payment_text) for r in conn.execute(
                "SELECT * FROM payments WHERE status IN ('paid', 'rejected') AND resolved_at >= ? AND resolved_at < ? "
                "AND user_id IN (SELECT user_id FROM shop_users) "
                "AND id NOT IN (SELECT obj_id FROM buyer_notified WHERE kind = 'pay') ORDER BY id LIMIT ?",
                (since, until, BATCH))]
    for kind, row, make in jobs:
        if (kind, row["id"]) in watched:   # «пополнить и купить» — бот-магазин сам оформит заказ и напишет
            continue
        if not mark(conn, kind, row["id"]):
            continue
        for chat in chats(row["user_id"]):
            if _send(config, chat["tg_id"], make(conn, config, chat["lang"] or "", row)):
                sent += 1
    return sent


def _with_intent(conn: sqlite3.Connection) -> set[tuple[str, int]]:
    try:
        return {(r[0], int(r[1])) for r in conn.execute("SELECT kind, obj_id FROM shop_watch WHERE intent IS NOT NULL")}
    except sqlite3.OperationalError:   # таблицы ещё нет
        return set()


def push_payment(conn: sqlite3.Connection, config: Config, payment_id: int) -> int:
    """Заявку только что решили (админ, кассир, автоплатёж) — написать сразу, не дожидаясь воркера."""
    if not _token(config):
        return 0
    p = conn.execute("SELECT * FROM payments WHERE id = ? AND status IN ('paid', 'rejected')",
                     (payment_id,)).fetchone()
    if p is None or ("pay", payment_id) in _with_intent(conn):
        return 0
    rows = conn.execute("SELECT tg_id, lang FROM shop_users WHERE user_id = ?", (p["user_id"],)).fetchall()
    if not rows or not mark(conn, "pay", payment_id):
        return 0
    return sum(_send(config, r["tg_id"], payment_text(conn, config, r["lang"] or "", p)) for r in rows)
