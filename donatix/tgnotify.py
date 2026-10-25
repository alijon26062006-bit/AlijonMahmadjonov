"""Уведомления покупателям мини-приложения /tg — пишет бот мини-приложения (DONATIX_GIFT_BOT_TOKEN).

Мини-приложение ставит «слежку» за пополнением, заказом Stars/Premium или подарком. Воркер (каждые
~20 секунд) смотрит статусы: решилось — пишет человеку в бот и снимает слежку. Запись удаляется ДО
отправки: два процесса одно и то же сообщение не пришлют.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any

from . import accounts, db
from .config import Config
from .refs import ref

log = logging.getLogger("donatix.tgnotify")

SCHEMA = """
CREATE TABLE IF NOT EXISTS tgapp_watch (
    id          INTEGER PRIMARY KEY,
    kind        TEXT NOT NULL,          -- pay | order | gift
    obj_id      INTEGER NOT NULL,
    tg_id       INTEGER NOT NULL,
    lang        TEXT NOT NULL DEFAULT 'tj',
    created_at  TEXT NOT NULL,
    UNIQUE (kind, obj_id, tg_id)
)
"""
MAX_AGE = 3 * 86400        # не решилось за 3 дня — больше не ждём
PAY_FINAL = ("paid", "rejected", "cancelled", "fake")
ORDER_FINAL = ("completed", "failed", "refunded", "cancelled")
GIFT_FINAL = ("sent", "failed", "refunded")

T = {
    "tj": {
        "paid": "✅ Пардохт қабул шуд!\n\nЗаявка #{id}: +{amount}\nБаланс: {balance}",
        "rejected": "❌ Заявка #{id} рад карда шуд.{reason}\n\nАгар хато бошад — ба дастгирӣ нависед.",
        "cancelled": "⌛ Заявка #{id} бекор шуд (вақт гузашт ё пардохт наомад).",
        "order_ok": "✅ Фармоиш № {id} иҷро шуд!\n{product}",
        "order_fail": "❌ Фармоиш № {id} иҷро нашуд: {product}\nПул ба баланс баргардонида шуд.",
        "gift_ok": "🎁 Тӯҳфа № {ref} (⭐{stars}) ба {to} фиристода шуд!",
        "gift_fail": "❌ Тӯҳфа № {ref} (⭐{stars}) фиристода нашуд. Пул ба баланс баргардонида шуд.",
        "open": "🛍 Кушодани мағоза",
    },
    "ru": {
        "paid": "✅ Оплата принята!\n\nЗаявка #{id}: +{amount}\nБаланс: {balance}",
        "rejected": "❌ Заявка #{id} отклонена.{reason}\n\nЕсли это ошибка — напишите в поддержку.",
        "cancelled": "⌛ Заявка #{id} отменена (время вышло или оплата не пришла).",
        "order_ok": "✅ Заказ № {id} выполнен!\n{product}",
        "order_fail": "❌ Заказ № {id} не выполнен: {product}\nДеньги вернулись на баланс.",
        "gift_ok": "🎁 Подарок № {ref} (⭐{stars}) отправлен: {to}!",
        "gift_fail": "❌ Подарок № {ref} (⭐{stars}) не отправлен. Деньги вернулись на баланс.",
        "open": "🛍 Открыть магазин",
    },
}


def ensure(conn: sqlite3.Connection) -> None:
    # Один execute, не executescript: тот делает COMMIT — а нас зовут и изнутри чужих транзакций
    conn.execute(SCHEMA)


def lang_of(tg: dict[str, Any]) -> str:
    return "ru" if (tg.get("language_code") or "").startswith("ru") else "tj"


def add(conn: sqlite3.Connection, kind: str, obj_id: int, tg: dict[str, Any]) -> None:
    ensure(conn)
    conn.execute("INSERT OR IGNORE INTO tgapp_watch (kind, obj_id, tg_id, lang, created_at) VALUES (?, ?, ?, ?, ?)",
                 (kind, int(obj_id), int(tg["id"]), lang_of(tg), db.now()))


def _money(conn: sqlite3.Connection, config: Config, micro: int) -> str:
    from .shopbot import money, tjs_rate
    return f"{money(micro, tjs_rate(conn, config))} (${micro / 10_000:.2f})"


def _text(conn: sqlite3.Connection, config: Config, w: sqlite3.Row) -> str | None:
    """Готовый текст, если статус окончательный; None — ещё ждём."""
    t = T.get(w["lang"], T["tj"])
    if w["kind"] == "pay":
        p = conn.execute("SELECT * FROM payments WHERE id = ?", (w["obj_id"],)).fetchone()
        if p is None:
            return ""
        if p["status"] not in PAY_FINAL:
            return None
        if p["status"] == "paid":
            user = accounts.get_user(conn, p["user_id"])
            return t["paid"].format(id=p["id"], amount=_money(conn, config, p["amount_micro"]),
                                    balance=_money(conn, config, user["balance_micro"]))
        if p["status"] == "cancelled":
            return t["cancelled"].format(id=p["id"])
        reason = (p["admin_note"] or "").strip()
        return t["rejected"].format(id=p["id"], reason=f"\n{reason}" if reason else "")
    if w["kind"] == "order":
        o = conn.execute("SELECT * FROM orders WHERE id = ?", (w["obj_id"],)).fetchone()
        if o is None:
            return ""
        if o["status"] not in ORDER_FINAL:
            return None
        key = "order_ok" if o["status"] == "completed" else "order_fail"
        text = t[key].format(id=o["public_id"], product=o["product_name"])
        if o["status"] == "completed" and o["delivery_json"]:
            from .orders import delivery_items
            try:
                items = delivery_items(json.loads(o["delivery_json"]))
            except ValueError:
                items = []
            text += "".join(f"\n{'🔗' if i['link'] else '🔑'} {i['label']}: {i['value']}" for i in items)
        return text
    g = conn.execute("SELECT * FROM gift_orders WHERE id = ?", (w["obj_id"],)).fetchone()
    if g is None:
        return ""
    if g["status"] not in GIFT_FINAL:
        return None
    if g["status"] == "sent":
        return t["gift_ok"].format(ref=ref("gift", g["id"]), stars=g["star_count"], to=g["recipient"] or "")
    return t["gift_fail"].format(ref=ref("gift", g["id"]), stars=g["star_count"])


def push(conn: sqlite3.Connection, config: Config, kind: str, obj_id: int) -> int:
    """Сразу после решения (админ, кассир, автоплатёж) — не дожидаясь воркера."""
    return tick(conn, config, kind=kind, obj_id=obj_id)


def tick(conn: sqlite3.Connection, config: Config, *, kind: str = "", obj_id: int = 0) -> int:
    """Из воркера: всем, у кого что-то решилось, — сообщение в бот."""
    if not config.gift_bot_token:
        return 0
    ensure(conn)
    from . import tggifts
    from .giftbot import app_url
    from .shopbot import _ago
    old = _ago(MAX_AGE)
    sent = 0
    sql, args = "SELECT * FROM tgapp_watch", ()
    if kind:
        sql, args = sql + " WHERE kind = ? AND obj_id = ?", (kind, obj_id)
    for w in conn.execute(sql + " ORDER BY id LIMIT 200", args).fetchall():
        text = _text(conn, config, w)
        if text is None:
            if w["created_at"] < old:
                conn.execute("DELETE FROM tgapp_watch WHERE id = ?", (w["id"],))
            continue
        # Забираем запись первой — второй процесс то же сообщение не пришлёт
        if not conn.execute("DELETE FROM tgapp_watch WHERE id = ?", (w["id"],)).rowcount or not text:
            continue
        if w["kind"] in ("order", "pay"):
            from .buyernotify import mark
            if not mark(conn, w["kind"], w["obj_id"]):   # уже написали (одно событие — одно сообщение)
                continue
        t = T.get(w["lang"], T["tj"])
        try:
            tggifts.call(config, "sendMessage", chat_id=w["tg_id"], text=text,
                         reply_markup={"inline_keyboard": [[{"text": t["open"], "web_app": {"url": app_url(config)}}]]})
            sent += 1
        except Exception as exc:  # noqa: BLE001 — человек заблокировал бот и т.п.
            log.warning("уведомление в бот мини-приложения не ушло (%s #%s): %s", w["kind"], w["obj_id"], exc)
    return sent
