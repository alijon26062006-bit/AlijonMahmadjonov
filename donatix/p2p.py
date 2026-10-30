"""P2P D-коинов: покупатели продают и покупают монеты друг у друга по своей цене, за баланс Donatix.

Как на P2P бирж, только гарантом сделки выступает сам сайт:
  • Объявление «Продаю D»: монеты сразу уходят из кошелька продавца в резерв объявления. Кто покупает —
    платит со своего баланса, деньги сразу у продавца, монеты сразу у покупателя.
  • Объявление «Покупаю D»: деньги сразу резервируются с баланса покупателя. Кто продаёт — отдаёт свои
    монеты и сразу получает деньги из резерва.
  • Отменил объявление — несделанный остаток (монеты или деньги) возвращается владельцу.
Обмануть нельзя: монеты и деньги лежат у сайта до сделки, сделка проходит целиком в одной транзакции.

Цену владелец ставит сам — в процентах от цены копилки (MIN_PCT…MAX_PCT), в объявлении она фиксируется.
Комиссии нет. Копилку и цену D-коина P2P не трогает: монеты только переходят от человека к человеку,
поэтому сайт не может уйти в минус — это деньги самих покупателей. Монеты за ещё не выполненные заказы
продавать нельзя (как и обменивать).
"""

from __future__ import annotations

import sqlite3
from typing import Any

from . import accounts, db, dcoin

PRICE_SCALE = 1_000_000          # цена в объявлении — микро-доллары за 1 000 000 D
MIN_PCT, MAX_PCT = 80, 150       # цена от 80% до 150% цены копилки
MAX_ADS = 5                      # открытых объявлений на одного
SIDES = ("sell", "buy")


class P2PError(Exception):
    pass


def ref_price_m(conn: sqlite3.Connection) -> int:
    """Цена копилки: микро-доллары за 1 000 000 D."""
    return int(round(dcoin.price(conn) * 10_000 * PRICE_SCALE))


def cost(units: int, price_m: int) -> int:
    """Сколько микро-долларов за units сотых долей монеты по цене price_m (в пользу покупателя — вниз)."""
    return units * price_m // (dcoin.UNIT * PRICE_SCALE)


def _cost_up(units: int, price_m: int) -> int:
    return -(-units * price_m // (dcoin.UNIT * PRICE_SCALE))


def free_coins(conn: sqlite3.Connection, user_id: int) -> int:
    return max(0, dcoin.balance(conn, user_id) - dcoin.waiting(conn, user_id))


def _coins(conn: sqlite3.Connection, user_id: int, units: int, reason: str) -> None:
    conn.execute("UPDATE users SET dcoin = dcoin + ? WHERE id = ?", (units, user_id))
    conn.execute("INSERT INTO dcoin_ledger (user_id, amount, pool_micro, reason, created_at) VALUES (?, ?, 0, ?, ?)",
                 (user_id, units, reason, db.now()))


def _money(conn: sqlite3.Connection, user_id: int, micro: int, note: str) -> None:
    try:
        accounts.post_ledger(conn, user_id, micro, note)
    except accounts.InsufficientBalance:
        raise P2PError("Не хватает денег на балансе — пополните баланс.") from None


def create_ad(conn: sqlite3.Connection, user_id: int, side: str, pct: int, units: int, min_units: int = 0) -> int:
    if not dcoin.enabled(conn):
        raise P2PError("D-коин сейчас выключен.")
    if not dcoin.exchange_open(conn):
        raise P2PError(f"P2P откроется вместе с обменом — {dcoin.exchange_opens(conn):%d.%m.%Y}.")
    if side not in SIDES:
        raise P2PError("Выберите: продаю или покупаю.")
    if not MIN_PCT <= pct <= MAX_PCT:
        raise P2PError(f"Цена — от {MIN_PCT}% до {MAX_PCT}% цены копилки.")
    if units <= 0:
        raise P2PError("Сколько D? Укажите количество.")
    price_m = ref_price_m(conn) * pct // 100
    if price_m <= 0:
        raise P2PError("У D-коина ещё нет цены — подождите первых покупок.")
    min_units = max(0, min(min_units, units))
    with db.tx(conn):
        n = conn.execute("SELECT COUNT(*) FROM p2p_ads WHERE user_id = ? AND status = 'open'", (user_id,)).fetchone()[0]
        if n >= MAX_ADS:
            raise P2PError(f"Открытых объявлений не больше {MAX_ADS} — закройте старое.")
        cur = conn.execute("INSERT INTO p2p_ads (user_id, side, price_m, pct, remaining, min_units, locked_micro, status, "
                           "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 0, 'open', ?, ?)",
                           (user_id, side, price_m, pct, units, min_units, db.now(), db.now()))
        ad_id = int(cur.lastrowid)
        if side == "sell":
            if units > free_coins(conn, user_id):
                raise P2PError("Столько свободных D-коинов у вас нет (монеты за невыполненные заказы продавать нельзя).")
            _coins(conn, user_id, -units, f"P2P: выставлено на продажу (объявление #{ad_id})")
        else:
            lock = _cost_up(units, price_m)
            if lock <= 0:
                raise P2PError("Слишком маленькая сумма — укажите больше D.")
            _money(conn, user_id, -lock, f"P2P: резерв на покупку {dcoin.fmt_d(units)} D (объявление #{ad_id})")
            conn.execute("UPDATE p2p_ads SET locked_micro = ? WHERE id = ?", (lock, ad_id))
    return ad_id


def take(conn: sqlite3.Connection, user_id: int, ad_id: int, units: int) -> dict[str, Any]:
    """Сделка по чужому объявлению: купить у продавца или продать покупателю. Вернёт итог сделки."""
    with db.tx(conn):
        ad = conn.execute("SELECT * FROM p2p_ads WHERE id = ?", (ad_id,)).fetchone()
        if ad is None or ad["status"] != "open":
            raise P2PError("Объявление уже закрыто.")
        if ad["user_id"] == user_id:
            raise P2PError("Это ваше объявление.")
        if units <= 0 or units > ad["remaining"]:
            raise P2PError(f"Доступно {dcoin.fmt_d(ad['remaining'])} D.")
        if units < ad["min_units"] and units != ad["remaining"]:
            raise P2PError(f"Минимум в этом объявлении — {dcoin.fmt_d(ad['min_units'])} D.")
        total = cost(units, ad["price_m"])
        if total <= 0:
            raise P2PError("Слишком маленькая сделка — возьмите больше D.")
        owner = ad["user_id"]
        if ad["side"] == "sell":   # я покупаю у продавца
            buyer, seller = user_id, owner
            _money(conn, buyer, -total, f"P2P: покупка {dcoin.fmt_d(units)} D (объявление #{ad_id})")
            _money(conn, seller, total, f"P2P: продажа {dcoin.fmt_d(units)} D (объявление #{ad_id})")
            _coins(conn, buyer, units, f"P2P: куплено (объявление #{ad_id})")
            locked = ad["locked_micro"]
        else:                      # я продаю покупателю
            buyer, seller = owner, user_id
            if units > free_coins(conn, seller):
                raise P2PError("Столько свободных D-коинов у вас нет (монеты за невыполненные заказы продавать нельзя).")
            _coins(conn, seller, -units, f"P2P: продано (объявление #{ad_id})")
            _money(conn, seller, total, f"P2P: продажа {dcoin.fmt_d(units)} D (объявление #{ad_id})")
            _coins(conn, buyer, units, f"P2P: куплено (объявление #{ad_id})")
            locked = ad["locked_micro"] - total
        left = ad["remaining"] - units
        status = "open" if left > 0 else "done"
        if ad["side"] == "buy" and left == 0 and locked > 0:   # копейки округления — обратно покупателю
            _money(conn, buyer, locked, f"P2P: возврат остатка резерва (объявление #{ad_id})")
            locked = 0
        conn.execute("UPDATE p2p_ads SET remaining = ?, locked_micro = ?, status = ?, updated_at = ? WHERE id = ?",
                     (left, locked, status, db.now(), ad_id))
        conn.execute("INSERT INTO p2p_trades (ad_id, buyer_id, seller_id, units, price_m, total_micro, created_at) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?)", (ad_id, buyer, seller, units, ad["price_m"], total, db.now()))
    return {"units": units, "total": total, "side": "buy" if ad["side"] == "sell" else "sell"}


def cancel(conn: sqlite3.Connection, user_id: int, ad_id: int) -> None:
    with db.tx(conn):
        ad = conn.execute("SELECT * FROM p2p_ads WHERE id = ? AND user_id = ?", (ad_id, user_id)).fetchone()
        if ad is None or ad["status"] != "open":
            raise P2PError("Объявление уже закрыто.")
        if ad["side"] == "sell" and ad["remaining"] > 0:
            _coins(conn, user_id, ad["remaining"], f"P2P: возврат с продажи (объявление #{ad_id})")
        if ad["side"] == "buy" and ad["locked_micro"] > 0:
            _money(conn, user_id, ad["locked_micro"], f"P2P: возврат резерва (объявление #{ad_id})")
        conn.execute("UPDATE p2p_ads SET status = 'cancelled', locked_micro = 0, updated_at = ? WHERE id = ?",
                     (db.now(), ad_id))


def _mask(login: str) -> str:
    login = login or "user"
    return login[:3] + "***" if len(login) > 3 else login[:1] + "***"


def _view(r: sqlite3.Row) -> dict[str, Any]:
    return {"id": r["id"], "side": r["side"], "pct": r["pct"], "price_usd": r["price_m"] / 10_000 / PRICE_SCALE,
            "remaining": r["remaining"], "remaining_text": dcoin.fmt_d(r["remaining"]),
            "min_text": dcoin.fmt_d(r["min_units"]) if r["min_units"] else "",
            "total_usd": cost(r["remaining"], r["price_m"]) / 10_000, "status": r["status"],
            "created_at": r["created_at"]}


def book(conn: sqlite3.Connection, side: str, limit: int = 50) -> list[dict[str, Any]]:
    """Открытые объявления: продающие — сначала дешёвые, покупающие — сначала дорогие."""
    order = "price_m ASC" if side == "sell" else "price_m DESC"
    rows = conn.execute(
        "SELECT a.*, u.login, (SELECT COUNT(*) FROM p2p_trades t WHERE t.buyer_id = a.user_id OR t.seller_id = a.user_id) "
        f"AS deals FROM p2p_ads a JOIN users u ON u.id = a.user_id WHERE a.status = 'open' AND a.side = ? "
        f"AND a.remaining > 0 ORDER BY {order}, a.id LIMIT ?", (side, limit)).fetchall()
    return [{**_view(r), "who": _mask(r["login"]), "deals": r["deals"], "user_id": r["user_id"]} for r in rows]


def mine(conn: sqlite3.Connection, user_id: int, limit: int = 20) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM p2p_ads WHERE user_id = ? ORDER BY (status = 'open') DESC, id DESC LIMIT ?",
                        (user_id, limit)).fetchall()
    return [_view(r) for r in rows]


def trades(conn: sqlite3.Connection, user_id: int, limit: int = 20) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM p2p_trades WHERE buyer_id = ? OR seller_id = ? ORDER BY id DESC LIMIT ?",
                        (user_id, user_id, limit)).fetchall()
    return [{"bought": r["buyer_id"] == user_id, "units_text": dcoin.fmt_d(r["units"]),
             "total_usd": r["total_micro"] / 10_000, "price_usd": r["price_m"] / 10_000 / PRICE_SCALE,
             "created_at": r["created_at"]} for r in rows]


def last_price_usd(conn: sqlite3.Connection) -> float | None:
    row = conn.execute("SELECT price_m FROM p2p_trades ORDER BY id DESC LIMIT 1").fetchone()
    return row["price_m"] / 10_000 / PRICE_SCALE if row else None
