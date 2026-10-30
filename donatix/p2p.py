"""P2P D-коинов: покупатели продают и покупают монеты друг у друга по своей цене, за баланс Donatix.

Как на P2P бирж — объявления и ордера с таймером, гарант — сам сайт:
  • Объявление «Продаю D»: монеты сразу уходят из кошелька продавца в объявление (заморожены).
    «Покупаю D»: деньги сразу резервируются с баланса покупателя.
  • Ордер: человек открывает сделку по объявлению — и у ОБОИХ всё замораживается: его деньги (или монеты)
    и нужная часть объявления; эту часть больше никто не возьмёт.
  • Владелец объявления подтверждает за ORDER_MINUTES минут: монеты — покупателю, деньги — продавцу.
    Не подтвердил, отклонил или открывший отменил — ордер отменяется, всё размораживается само.
  • Закрыл объявление — несделанный остаток возвращается владельцу.
Обмануть нельзя: монеты и деньги лежат у сайта, каждый шаг — одна транзакция.

Цену владелец ставит сам — в процентах от цены копилки (MIN_PCT…MAX_PCT), в объявлении она фиксируется.
Комиссии нет. Копилку и цену D-коина P2P не трогает: монеты только переходят от человека к человеку,
поэтому сайт не может уйти в минус — это деньги самих покупателей. Монеты за ещё не выполненные заказы
продавать нельзя (как и обменивать).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from . import accounts, db, dcoin

PRICE_SCALE = 1_000_000          # цена в объявлении — микро-доллары за 1 000 000 D
MIN_PCT, MAX_PCT = 80, 150       # цена от 80% до 150% цены копилки
MAX_ADS = 5                      # открытых объявлений на одного
SIDES = ("sell", "buy")
ORDER_MINUTES = 15               # столько ждём подтверждения владельца объявления, потом ордер отменяется сам
MAX_PENDING = 3                  # открытых ордеров на одного
SHOW_PER = 1_000_000             # на экране цена — за 1 000 000 D (за 1 D — слишком много нулей)


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


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _iso(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def open_order(conn: sqlite3.Connection, user_id: int, ad_id: int, units: int) -> int:
    """Открыть ордер по чужому объявлению. У обоих всё замораживается: часть объявления (монеты или деньги
    владельца) уходит в ордер — её больше никто не возьмёт, и у открывшего — его деньги или монеты.
    Владелец объявления подтверждает за ORDER_MINUTES минут, иначе ордер отменяется сам. Вернёт id ордера."""
    expire(conn)
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
        busy = conn.execute("SELECT COUNT(*) FROM p2p_orders WHERE taker_id = ? AND status = 'pending'",
                            (user_id,)).fetchone()[0]
        if busy >= MAX_PENDING:
            raise P2PError(f"У вас уже {busy} открытых ордера — дождитесь их завершения.")
        now = _now_dt()
        cur = conn.execute("INSERT INTO p2p_orders (ad_id, owner_id, taker_id, side, units, price_m, total_micro, status, "
                           "created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)",
                           (ad_id, ad["user_id"], user_id, ad["side"], units, ad["price_m"], total, _iso(now),
                            _iso(now + timedelta(minutes=ORDER_MINUTES))))
        oid = int(cur.lastrowid)
        if ad["side"] == "sell":   # я покупаю: мои деньги замораживаются, монеты продавца уже в объявлении
            _money(conn, user_id, -total, f"P2P: заморожено для ордера #{oid}")
            conn.execute("UPDATE p2p_ads SET remaining = remaining - ?, updated_at = ? WHERE id = ?",
                         (units, db.now(), ad_id))
        else:                      # я продаю: мои монеты замораживаются, деньги покупателя уже в объявлении
            if units > free_coins(conn, user_id):
                raise P2PError("Столько свободных D-коинов у вас нет (монеты за невыполненные заказы продавать нельзя).")
            _coins(conn, user_id, -units, f"P2P: заморожено для ордера #{oid}")
            conn.execute("UPDATE p2p_ads SET remaining = remaining - ?, locked_micro = locked_micro - ?, updated_at = ? "
                         "WHERE id = ?", (units, total, db.now(), ad_id))
    return oid


def _order(conn: sqlite3.Connection, order_id: int) -> sqlite3.Row:
    o = conn.execute("SELECT * FROM p2p_orders WHERE id = ?", (order_id,)).fetchone()
    if o is None:
        raise P2PError("Ордер не найден.")
    return o


def _close_ad_if_empty(conn: sqlite3.Connection, ad_id: int) -> None:
    """Всё продано (или куплено) и открытых ордеров нет — объявление выполнено, копейки резерва — владельцу."""
    ad = conn.execute("SELECT * FROM p2p_ads WHERE id = ?", (ad_id,)).fetchone()
    if ad is None or ad["status"] != "open" or ad["remaining"] > 0:
        return
    if conn.execute("SELECT 1 FROM p2p_orders WHERE ad_id = ? AND status = 'pending'", (ad_id,)).fetchone():
        return
    if ad["side"] == "buy" and ad["locked_micro"] > 0:
        _money(conn, ad["user_id"], ad["locked_micro"], f"P2P: возврат остатка резерва (объявление #{ad_id})")
    conn.execute("UPDATE p2p_ads SET status = 'done', locked_micro = 0, updated_at = ? WHERE id = ?", (db.now(), ad_id))


def confirm(conn: sqlite3.Connection, user_id: int, order_id: int) -> dict[str, Any]:
    """Владелец объявления подтверждает ордер: монеты — покупателю, деньги — продавцу."""
    expire(conn)
    with db.tx(conn):
        o = _order(conn, order_id)
        if o["owner_id"] != user_id:
            raise P2PError("Подтверждает владелец объявления.")
        if o["status"] != "pending":
            raise P2PError("Ордер уже завершён или отменён.")
        if o["side"] == "sell":   # владелец продаёт
            buyer, seller = o["taker_id"], o["owner_id"]
        else:                     # владелец покупает
            buyer, seller = o["owner_id"], o["taker_id"]
        _coins(conn, buyer, o["units"], f"P2P: получено по ордеру #{order_id}")
        _money(conn, seller, o["total_micro"], f"P2P: продажа {dcoin.fmt_d(o['units'])} D (ордер #{order_id})")
        conn.execute("UPDATE p2p_orders SET status = 'done', finished_at = ? WHERE id = ?", (db.now(), order_id))
        conn.execute("INSERT INTO p2p_trades (ad_id, buyer_id, seller_id, units, price_m, total_micro, created_at) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?)", (o["ad_id"], buyer, seller, o["units"], o["price_m"],
                                                      o["total_micro"], db.now()))
        _close_ad_if_empty(conn, o["ad_id"])
    return {"units": o["units"], "total": o["total_micro"], "taker": o["taker_id"]}


def _unwind(conn: sqlite3.Connection, o: sqlite3.Row, status: str) -> None:
    """Ордер не состоялся: открывшему — его замороженное, владельцу — обратно в объявление (или ему, если закрыто)."""
    oid = o["id"]
    ad = conn.execute("SELECT status FROM p2p_ads WHERE id = ?", (o["ad_id"],)).fetchone()
    ad_open = ad is not None and ad["status"] == "open"
    if o["side"] == "sell":
        _money(conn, o["taker_id"], o["total_micro"], f"P2P: разморожено — ордер #{oid} не состоялся")
        if ad_open:
            conn.execute("UPDATE p2p_ads SET remaining = remaining + ?, updated_at = ? WHERE id = ?",
                         (o["units"], db.now(), o["ad_id"]))
        else:
            _coins(conn, o["owner_id"], o["units"], f"P2P: возврат — ордер #{oid} не состоялся")
    else:
        _coins(conn, o["taker_id"], o["units"], f"P2P: разморожено — ордер #{oid} не состоялся")
        if ad_open:
            conn.execute("UPDATE p2p_ads SET remaining = remaining + ?, locked_micro = locked_micro + ?, updated_at = ? "
                         "WHERE id = ?", (o["units"], o["total_micro"], db.now(), o["ad_id"]))
        else:
            _money(conn, o["owner_id"], o["total_micro"], f"P2P: возврат — ордер #{oid} не состоялся")
    conn.execute("UPDATE p2p_orders SET status = ?, finished_at = ? WHERE id = ?", (status, db.now(), oid))


def cancel_order(conn: sqlite3.Connection, user_id: int, order_id: int) -> sqlite3.Row:
    """Отменить ордер: открывший — «отменить», владелец объявления — «отклонить». Всё размораживается."""
    with db.tx(conn):
        o = _order(conn, order_id)
        if user_id not in (o["owner_id"], o["taker_id"]):
            raise P2PError("Это не ваш ордер.")
        if o["status"] != "pending":
            raise P2PError("Ордер уже завершён или отменён.")
        _unwind(conn, o, "cancelled")
    return o


def expire(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Время ордера вышло, а владелец не подтвердил — ордер отменяется сам, всё размораживается."""
    now = _iso(_now_dt())
    late = conn.execute("SELECT * FROM p2p_orders WHERE status = 'pending' AND expires_at <= ?", (now,)).fetchall()
    done = []
    for o in late:
        with db.tx(conn):
            fresh = conn.execute("SELECT * FROM p2p_orders WHERE id = ? AND status = 'pending'", (o["id"],)).fetchone()
            if fresh is None:
                continue
            _unwind(conn, fresh, "expired")
            done.append(fresh)
    return done


def orders(conn: sqlite3.Connection, user_id: int, limit: int = 30) -> list[dict[str, Any]]:
    """Мои ордера — открытые сверху, с таймером."""
    rows = conn.execute(
        "SELECT o.*, uo.login AS owner_login, ut.login AS taker_login FROM p2p_orders o "
        "JOIN users uo ON uo.id = o.owner_id JOIN users ut ON ut.id = o.taker_id "
        "WHERE o.owner_id = ? OR o.taker_id = ? ORDER BY (o.status = 'pending') DESC, o.id DESC LIMIT ?",
        (user_id, user_id, limit)).fetchall()
    out = []
    for r in rows:
        mine_ad = r["owner_id"] == user_id
        buying = (r["side"] == "sell") != mine_ad      # открыл по «продаю» — я покупаю; моё «покупаю» — тоже
        left = 0
        if r["status"] == "pending":
            end = datetime.fromisoformat(r["expires_at"].replace("Z", "+00:00"))
            left = max(0, int((end - _now_dt()).total_seconds()))
        out.append({"id": r["id"], "buying": buying, "owner": mine_ad, "status": r["status"], "left": left,
                    "units_text": dcoin.fmt_d(r["units"]), "total_usd": r["total_micro"] / 10_000,
                    "price_usd": r["price_m"] / 10_000 / PRICE_SCALE, "created_at": r["created_at"],
                    "other": _mask(r["taker_login"] if mine_ad else r["owner_login"])})
    return out


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


def book(conn: sqlite3.Connection, side: str, limit: int = 50, sort: str = "price",
         amount_usd: float | None = None) -> list[dict[str, Any]]:
    """Открытые объявления: продающие — сначала дешёвые, покупающие — сначала дорогие (или по числу сделок).
    amount_usd — фильтр «Сумма»: только объявления, где такую сумму можно провести одной сделкой."""
    order = "price_m ASC" if side == "sell" else "price_m DESC"
    if sort == "deals":
        order = "deals DESC, " + order
    rows = conn.execute(
        "SELECT a.*, u.login, (SELECT COUNT(*) FROM p2p_trades t WHERE t.buyer_id = a.user_id OR t.seller_id = a.user_id) "
        "AS deals, (SELECT COUNT(*) FROM p2p_orders o WHERE o.owner_id = a.user_id AND o.status != 'pending') AS ended, "
        "(SELECT COUNT(*) FROM p2p_orders o WHERE o.owner_id = a.user_id AND o.status = 'done') AS ok "
        f"FROM p2p_ads a JOIN users u ON u.id = a.user_id WHERE a.status = 'open' AND a.side = ? "
        f"AND a.remaining > 0 ORDER BY {order}, a.id LIMIT ?", (side, limit)).fetchall()
    out = []
    for r in rows:
        v = {**_view(r), "who": _mask(r["login"]), "deals": r["deals"], "user_id": r["user_id"],
             "letter": (r["login"] or "?")[:1].upper(), "color": r["user_id"] % 6,
             "rate": round(100 * r["ok"] / r["ended"]) if r["ended"] else 100,
             "min_usd": cost(min(r["min_units"], r["remaining"]) or r["remaining"], r["price_m"]) / 10_000
             if r["min_units"] else 0.0, "max_usd": cost(r["remaining"], r["price_m"]) / 10_000}
        if amount_usd is not None and not (v["min_usd"] <= amount_usd <= v["max_usd"]):
            continue
        out.append(v)
    if out:   # «Рекомендации» — у кого больше всего сделок
        best = max(out, key=lambda v: v["deals"])
        best["top"] = best["deals"] > 0
    return out


def profile(conn: sqlite3.Connection, user_id: int) -> dict[str, Any]:
    """Мой P2P-профиль: сделки, сколько купил и продал, оборот."""
    r = conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(CASE WHEN buyer_id = ? THEN units END), 0) AS bought, "
        "COALESCE(SUM(CASE WHEN seller_id = ? THEN units END), 0) AS sold, COALESCE(SUM(total_micro), 0) AS volume "
        "FROM p2p_trades WHERE buyer_id = ? OR seller_id = ?", (user_id, user_id, user_id, user_id)).fetchone()
    ads = conn.execute("SELECT COUNT(*) FROM p2p_ads WHERE user_id = ? AND status = 'open'", (user_id,)).fetchone()[0]
    # Заморожено: в своих объявлениях и в открытых ордерах
    coins = conn.execute(
        "SELECT COALESCE((SELECT SUM(remaining) FROM p2p_ads WHERE user_id = ? AND status = 'open' AND side = 'sell'), 0)"
        " + COALESCE((SELECT SUM(units) FROM p2p_orders WHERE status = 'pending' AND ((owner_id = ? AND side = 'sell')"
        " OR (taker_id = ? AND side = 'buy'))), 0)", (user_id, user_id, user_id)).fetchone()[0]
    money = conn.execute(
        "SELECT COALESCE((SELECT SUM(locked_micro) FROM p2p_ads WHERE user_id = ? AND status = 'open' AND side = 'buy'), 0)"
        " + COALESCE((SELECT SUM(total_micro) FROM p2p_orders WHERE status = 'pending' AND ((owner_id = ? AND side = 'buy')"
        " OR (taker_id = ? AND side = 'sell'))), 0)", (user_id, user_id, user_id)).fetchone()[0]
    return {"frozen_coins": dcoin.fmt_d(coins), "frozen_usd": money / 10_000,"deals": r["n"], "bought": dcoin.fmt_d(r["bought"]), "sold": dcoin.fmt_d(r["sold"]),
            "volume_usd": r["volume"] / 10_000, "open_ads": ads}


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
