"""Акция: один товар по особой цене в сомони на несколько дней — большой баннер на главной.

Пример: «Ваучер на месяц» Free Fire СНГ за 49 сомони три дня. Цена задаётся в сомони и
переводится в доллары по курсу оплат — на экране ровно 49.00 с. Действует только на сайте
и в своём боте-магазине: партнёры по API платят свою цену (у них своя наценка).
Кончился срок — товар снова по обычной цене, баннер пропадает сам.
"""

from __future__ import annotations

import json
import sqlite3
import time
from decimal import ROUND_DOWN, Decimal, InvalidOperation
from typing import Any

from . import cache, db
from .config import Config

KEY = "promo.v1"
MAX_DAYS = 30
# Недополученное по акции (обычная цена − цена акции) возвращаем надбавкой на остальные товары сайта:
# не больше RECOUP_PCT %, пока не вернём всё, но не дольше RECOUP_DAYS после конца акции.
RECOUP_PCT = Decimal("3")
RECOUP_DAYS = 7


def get(conn: sqlite3.Connection) -> dict[str, Any] | None:
    raw = db.get_setting(conn, KEY)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    return data if isinstance(data, dict) and data.get("product_id") else None


def active(conn: sqlite3.Connection, now: float | None = None) -> dict[str, Any] | None:
    """Акция, если она включена и срок не вышел."""
    p = get(conn)
    if not p or not p.get("on"):
        return None
    now = time.time() if now is None else now
    return p if float(p.get("starts", 0)) <= now < float(p.get("ends", 0)) else None


def save(conn: sqlite3.Connection, *, product_id: str, price_tjs: str, days: str, title: str, on: bool) -> dict:
    product_id = product_id.strip()[:120]
    if not product_id:
        raise ValueError("Выберите товар.")
    try:
        price = Decimal(price_tjs.replace(",", ".").strip()).quantize(Decimal("0.01"))
        n_days = Decimal(days.replace(",", ".").strip() or "3")
    except InvalidOperation:
        raise ValueError("Цена и дни — числами.") from None
    if not Decimal("1") <= price <= Decimal("100000"):
        raise ValueError("Цена — от 1 до 100 000 сомони.")
    if not Decimal("0.04") <= n_days <= MAX_DAYS:   # от часа до месяца
        raise ValueError(f"Срок — от 1 часа (0.04) до {MAX_DAYS} дней.")
    old = get(conn) or {}
    now = time.time()
    same = old.get("product_id") == product_id and old.get("price_tjs") == str(price) and old.get("on")
    starts = float(old["starts"]) if same and float(old.get("ends", 0)) > now else now
    data = {"product_id": product_id, "price_tjs": str(price), "title": title.strip()[:80], "on": on,
            "days": str(n_days), "starts": starts, "ends": starts + float(n_days) * 86400}
    db.set_setting(conn, KEY, json.dumps(data, ensure_ascii=False))
    cache.clear_everywhere(conn)
    return data


def stop(conn: sqlite3.Connection) -> None:
    p = get(conn)
    if p:
        p["on"] = False
        p["ends"] = min(float(p.get("ends", 0)), time.time())   # надбавка считает 7 дней от остановки
        db.set_setting(conn, KEY, json.dumps(p, ensure_ascii=False))
        cache.clear_everywhere(conn)


def _current(config: Config) -> dict[str, Any] | None:
    """Акция из базы (кеш на несколько секунд): цены считают и там, где соединения под рукой нет."""
    def load():
        pool = db.pool(config.db_path)
        c = pool.acquire()
        try:
            return get(c)
        finally:
            pool.release(c)
    p = cache.get_or_set("promo", 5, load)
    if not p or not p.get("on"):
        return None
    return p if float(p.get("starts", 0)) <= time.time() < float(p.get("ends", 0)) else None


def _rate(config: Config) -> Decimal:
    def load():
        from .payments import settings
        pool = db.pool(config.db_path)
        c = pool.acquire()
        try:
            return Decimal(str(settings(c, config)["tjs_rate"]))
        finally:
            pool.release(c)
    return cache.get_or_set("promo:rate", 30, load)


def unit_usd(config: Config, user: Any, product_id: str) -> Decimal | None:
    """Цена за 1 шт. по акции в долларах — или None (акции нет, товар другой, покупка через API).

    Вниз до 0.0001 $: 49 / 10.9 → 4.4954 $ → на экране и к оплате ровно 49.00 с., а не 49.01."""
    from .accounts import is_api
    p = _current(config)
    if p is None or p["product_id"] != product_id or (user is not None and is_api(user)):
        return None
    rate = _rate(config)
    if rate <= 0:
        return None
    return (Decimal(p["price_tjs"]) / rate).quantize(Decimal("0.0001"), rounding=ROUND_DOWN)


# ── Возврат «минуса» акции ──────────────────────────────────


def _ensure(conn: sqlite3.Connection) -> None:
    conn.execute("""CREATE TABLE IF NOT EXISTS promo_ledger (
        order_id INTEGER PRIMARY KEY,   -- заказ, по которому записали
        promo    TEXT NOT NULL,         -- какая акция (время её начала)
        micro    INTEGER NOT NULL       -- > 0 недополучили (ваучер дешевле), < 0 вернули надбавкой
    )""")


def _promo_id(p: dict[str, Any]) -> str:
    return str(int(float(p.get("starts", 0))))


def record(conn: sqlite3.Connection, order_id: int, micro: int) -> None:
    """Записать в той же транзакции, что и заказ: минус ваучера (+) или возврат надбавкой (−)."""
    p = get(conn)
    if not p or not micro:
        return
    _ensure(conn)
    conn.execute("INSERT OR REPLACE INTO promo_ledger (order_id, promo, micro) VALUES (?, ?, ?)",
                 (order_id, _promo_id(p), int(micro)))


def totals(conn: sqlite3.Connection, p: dict[str, Any] | None = None) -> dict[str, int]:
    """Сколько недополучили, сколько вернули, сколько осталось (микро-доллары). Отменённые заказы не в счёт."""
    p = p or get(conn)
    if not p:
        return {"lost": 0, "back": 0, "left": 0, "sold": 0}
    _ensure(conn)
    row = conn.execute(
        "SELECT COALESCE(SUM(CASE WHEN l.micro > 0 THEN l.micro END), 0) AS lost, "
        "COALESCE(-SUM(CASE WHEN l.micro < 0 THEN l.micro END), 0) AS back, "
        "COUNT(CASE WHEN l.micro > 0 THEN 1 END) AS sold "
        "FROM promo_ledger l JOIN orders o ON o.id = l.order_id WHERE l.promo = ? AND o.status != 'failed'",
        (_promo_id(p),)).fetchone()
    lost, back = int(row["lost"]), int(row["back"])
    return {"lost": lost, "back": back, "left": max(0, lost - back), "sold": int(row["sold"])}


def recoup_pct(config: Config, user: Any) -> Decimal | None:
    """Надбавка в % на остальные товары, пока минус акции не вернули; None — не нужна (или покупка по API)."""
    from .accounts import is_api
    if user is not None and is_api(user):
        return None

    def load():
        pool = db.pool(config.db_path)
        c = pool.acquire()
        try:
            p = get(c)
            if not p or time.time() >= float(p.get("ends", 0)) + RECOUP_DAYS * 86400:
                return None
            return totals(c, p)["left"] > 0
        finally:
            pool.release(c)
    return RECOUP_PCT if cache.get_or_set("promo:recoup", 5, load) else None


def banner(conn: sqlite3.Connection, config: Config) -> dict[str, Any] | None:
    """Всё для баннера на главной: товар, старая и новая цена, когда конец."""
    p = active(conn)
    if p is None:
        return None
    from . import catalog
    from .money import apply_markup, to_decimal
    product = catalog.get_product(conn, p["product_id"])
    if product is None:
        return None
    from .payments import settings
    rate = Decimal(str(settings(conn, config)["tjs_rate"]))
    markup = config.kind_markups.get(product["kind"], config.markups["bronze"])
    old_tjs = (apply_markup(to_decimal(product["base_price"]), markup) * rate).quantize(Decimal("1"))
    new_tjs = Decimal(p["price_tjs"])
    off = int((1 - new_tjs / old_tjs) * 100) if old_tjs > new_tjs else 0
    from . import packs
    from .suppliers import region_title
    return {
        "product_id": product["id"], "game": product["category_name"],
        "title": p.get("title") or packs.label(product["name"]),
        "region_title": region_title(product.get("region")) if product.get("region") else "", "image": product.get("image_url"),
        "price": f"{new_tjs:.2f}".removesuffix(".00"), "old": str(old_tjs) if off >= 5 else "", "off": off if off >= 5 else 0,
        "ends": int(float(p["ends"])),
    }


def admin_view(conn: sqlite3.Connection, config: Config) -> dict[str, Any]:
    """Для админки: текущая акция, закупка товара в сомони (чтобы не продать в минус)."""
    from . import catalog, packs
    from .payments import settings
    p = get(conn) or {}
    rate = Decimal(str(settings(conn, config)["tjs_rate"]))
    cost = None
    if p.get("product_id"):
        product = catalog.get_product(conn, p["product_id"], for_sale=False)
        if product:
            cost = (Decimal(str(product["base_price"])) * rate).quantize(Decimal("0.01"))
    rows = conn.execute("SELECT id, name, category_name, region, base_price FROM products "
                        "WHERE kind = 'topup' AND active = 1 ORDER BY category_name, region, name").fetchall()
    options = [{"id": r["id"], "label": f"{r['category_name']} · {r['region'] or '—'} · {packs.label(r['name'])}",
                "cost": str((Decimal(str(r["base_price"])) * rate).quantize(Decimal("0.01")))}
               for r in rows if packs.group(r["name"]) == 1]
    t = totals(conn, p) if p else {"lost": 0, "back": 0, "left": 0, "sold": 0}
    tjs = {k: (Decimal(v) / 10_000 * rate).quantize(Decimal("0.01")) for k, v in t.items() if k != "sold"}
    recouping = bool(p) and t["left"] > 0 and time.time() < float(p.get("ends", 0)) + RECOUP_DAYS * 86400
    return {"promo": p, "live": active(conn) is not None, "cost_tjs": cost, "options": options,
            "sold": t["sold"], "lost_tjs": tjs["lost"], "back_tjs": tjs["back"], "left_tjs": tjs["left"],
            "recouping": recouping, "recoup_pct": RECOUP_PCT, "recoup_days": RECOUP_DAYS}
