"""Магазин: цены, баланс, заказы Stars / Premium / подарков, пополнения по чеку.

Деньги — в дирамах. Любое списание и зачисление — в транзакции, с записью в ledger.
"""
from __future__ import annotations

import json
import re
import secrets
import sqlite3
from decimal import Decimal
from typing import Any

from . import db
from .money import fmt, price

USERNAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$")
STAR_PACKS = (50, 100, 250, 500, 1000, 2500)
METHODS = {"alif": "Алиф Моби", "dc": "Душанбе Сити", "card": "Карта Корти Милли / Visa"}
GIFT_RECIPIENT_HOURS = 48


class ShopError(Exception):
    """Понятная клиенту ошибка: текст показываем как есть."""


# ── админы: Telegram ID из .env (SITORA_ADMIN_IDS) и добавленные в админ-панели ──

def admin_list(conn: sqlite3.Connection, config) -> list[int]:
    saved = json.loads(db.get_setting(conn, "admins", "[]"))
    return sorted(set(config.admin_ids) | {int(x) for x in saved})


def is_admin(conn: sqlite3.Connection, config, tg_id) -> bool:
    return tg_id is not None and int(tg_id) in admin_list(conn, config)


# ── пользователи и баланс ─────────────────────────────────────

def touch_user(conn: sqlite3.Connection, u: dict[str, Any]) -> sqlite3.Row:
    tg_id = int(u["id"])
    lang = "ru" if str(u.get("language_code") or "").startswith("ru") else "tj"
    conn.execute(
        "INSERT INTO users (id, username, first_name, lang, created_at, seen_at) VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET username = excluded.username, first_name = excluded.first_name, "
        "seen_at = excluded.seen_at",
        (tg_id, str(u.get("username") or ""), str(u.get("first_name") or "")[:64], lang, db.now(), db.now()))
    return conn.execute("SELECT * FROM users WHERE id = ?", (tg_id,)).fetchone()


def move(conn: sqlite3.Connection, user_id: int, delta: int, reason: str, ref: str = "") -> int:
    """Изменить баланс (внутри транзакции). Минус не допускаем."""
    row = conn.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise ShopError("Пользователь не найден.")
    after = row[0] + delta
    if after < 0:
        raise ShopError("На балансе не хватает денег. / Маблағ дар баланс кифоя нест.")
    conn.execute("UPDATE users SET balance = ? WHERE id = ?", (after, user_id))
    conn.execute("INSERT INTO ledger (user_id, delta, balance_after, reason, ref, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                 (user_id, delta, after, reason, ref, db.now()))
    return after


# ── цены ──────────────────────────────────────────────────────

def rate(conn) -> Decimal:
    return Decimal(db.get_setting(conn, "rate", "11.0"))


def markup(conn) -> Decimal:
    return Decimal(db.get_setting(conn, "markup", "10"))


# ── ручные цены, скрытые и свои пакеты (ставит админ в боте) ──
# Ключ товара: "stars:500", "premium:3", "gift:<id>". Ручная цена — в дирамах; нет — цена по формуле.

def _json(conn, key: str, default):
    try:
        return json.loads(db.get_setting(conn, key, "") or "null") or default
    except ValueError:
        return default


def fixed_prices(conn) -> dict[str, int]:
    return {k: int(v) for k, v in _json(conn, "price_fix", {}).items()}


def set_fixed(conn, key: str, diram: int | None) -> None:
    fix = fixed_prices(conn)
    if diram is None:
        fix.pop(key, None)
    else:
        fix[key] = int(diram)
    db.set_setting(conn, "price_fix", json.dumps(fix))


def hidden(conn) -> set[str]:
    return set(_json(conn, "hidden", []))


def toggle_hidden(conn, key: str) -> bool:
    h = hidden(conn)
    h.symmetric_difference_update({key})
    db.set_setting(conn, "hidden", json.dumps(sorted(h)))
    return key in h


def star_packs(conn) -> list[int]:
    return sorted({int(q) for q in _json(conn, "star_packs", list(STAR_PACKS))})


def set_star_packs(conn, packs) -> None:
    db.set_setting(conn, "star_packs", json.dumps(sorted({int(q) for q in packs})))


def paused(conn) -> bool:
    return db.get_setting(conn, "paused") == "1"


def catalog(conn: sqlite3.Connection, everything: bool = False) -> dict[str, Any]:
    """Что продаём и почём. Закупочные цены кладёт воркер; админ может поставить свою цену на любой пакет.
    everything=True — для админа: со скрытыми пакетами и ценой по формуле (auto)."""
    r, m = rate(conn), markup(conn)
    fix, hide = fixed_prices(conn), hidden(conn)
    out: dict[str, Any] = {"stars": None, "premium": [], "gifts": []}

    def item(key: str, auto: int, **kw) -> dict[str, Any] | None:
        if key in hide and not everything:
            return None
        return {**kw, "key": key, "price": fix.get(key, auto), "auto": auto, "fixed": key in fix, "hidden": key in hide}

    star_usd = db.get_setting(conn, "star_usd")
    if star_usd:
        lo, hi = int(db.get_setting(conn, "star_min", "50")), int(db.get_setting(conn, "star_max", "10000"))
        per = Decimal(star_usd)
        packs = [item(f"stars:{q}", price(per * q, r, m), qty=q, cost_usd=str(per * q)) for q in star_packs(conn) if lo <= q <= hi]
        out["stars"] = {"min": lo, "max": hi, "per_star_diram": float(per * r * (1 + m / 100) * 100),
                        "packs": [p for p in packs if p]}
    for p in _json(conn, "premium", []):
        it = item(f"premium:{p['months']}", price(Decimal(p["price_usd"]), r, m), months=p["months"], cost_usd=str(p["price_usd"]))
        if it:
            out["premium"].append(it)
    gift_star = gift_star_price(conn)
    for g in _json(conn, "gifts", []):
        it = item(f"gift:{g['id']}", int(gift_star * g["stars"]), id=g["id"], stars=g["stars"], emoji=g.get("emoji", ""),
                  anim=g.get("fmt", "") if g.get("file") else "")
        if it:
            out["gifts"].append(it)
    return out


def public_catalog(conn) -> dict[str, Any]:
    """Для клиентов: без закупочных цен и служебных пометок."""
    cut = lambda it: {k: v for k, v in it.items() if k not in ("cost_usd", "auto", "fixed", "hidden", "key")}  # noqa: E731
    c = catalog(conn)
    if c["stars"]:
        c["stars"] = {**c["stars"], "packs": [cut(p) for p in c["stars"]["packs"]]}
    c["premium"] = [cut(p) for p in c["premium"]]
    c["gifts"] = [cut(g) for g in c["gifts"]]
    return c


def gift_star_price(conn) -> Decimal:
    """Цена одной звезды подарка в дирамах: своя настройка, иначе как у Stars."""
    own = db.get_setting(conn, "gift_star_diram")
    if own:
        return Decimal(own)
    star_usd = db.get_setting(conn, "star_usd")
    return Decimal(price(Decimal(star_usd), rate(conn), markup(conn))) if star_usd else Decimal(25)


def stars_price(conn, qty: int) -> int:
    star_usd = db.get_setting(conn, "star_usd")
    if not star_usd:
        raise ShopError("Stars временно недоступны. / Stars муваққатан нест.")
    lo, hi = int(db.get_setting(conn, "star_min", "50")), int(db.get_setting(conn, "star_max", "10000"))
    if not lo <= qty <= hi:
        raise ShopError(f"Количество — от {lo} до {hi}. / Миқдор — аз {lo} то {hi}.")
    key = f"stars:{qty}"
    if qty in star_packs(conn) and key not in hidden(conn) and key in fixed_prices(conn):
        return fixed_prices(conn)[key]   # ручная цена пакета
    return price(Decimal(star_usd) * qty, rate(conn), markup(conn))


def clean_username(raw: str) -> str:
    v = (raw or "").strip().lstrip("@").split("/")[-1]
    if not USERNAME.match(v):
        raise ShopError("Напишите @username получателя, например @ali_dev. / @username-и гирандаро нависед.")
    return v


# ── заказы ────────────────────────────────────────────────────

def quote(conn: sqlite3.Connection, item: dict[str, Any]) -> dict[str, Any]:
    """Что покупают и почём. item: {kind: stars|premium|gift, qty|months|gift_id, to}."""
    kind = item.get("kind")
    if kind == "stars":
        qty = int(item.get("qty") or 0)
        cost = Decimal(db.get_setting(conn, "star_usd") or 0) * qty
        return {"kind": "stars", "qty": qty, "title": f"{qty} Stars", "price": stars_price(conn, qty), "cost_usd": str(cost)}
    if kind == "premium":
        months = int(item.get("months") or 0)
        plan = next((p for p in catalog(conn)["premium"] if p["months"] == months), None)
        if not plan:
            raise ShopError("Такого тарифа Premium нет. / Чунин тарифи Premium нест.")
        return {"kind": "premium", "months": months, "title": f"Premium · {months} мес.", "price": plan["price"],
                "cost_usd": plan["cost_usd"]}
    if kind == "gift":
        g = next((g for g in catalog(conn)["gifts"] if g["id"] == str(item.get("gift_id"))), None)
        if not g:
            raise ShopError("Этого подарка уже нет. / Ин тӯҳфа дигар нест.")
        return {"kind": "gift", "gift_id": g["id"], "gift_stars": g["stars"], "title": f"Подарок {g['emoji']}".strip(),
                "price": g["price"]}
    raise ShopError("Неизвестный товар.")


def place_order(conn: sqlite3.Connection, user_id: int, item: dict[str, Any]) -> sqlite3.Row:
    """Списать с баланса и создать заказ. Поставщику его отправит воркер."""
    if paused(conn):
        raise ShopError("Магазин на короткой паузе — попробуйте чуть позже. / Мағоза муваққатан таваққуф кардааст.")
    q = quote(conn, item)
    to_self = item.get("kind") == "gift" and not (item.get("to") or "").strip()
    recipient = "" if to_self else clean_username(item.get("to") or "")
    with db.tx(conn):
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None or user["banned"]:
            raise ShopError("Доступ закрыт.")
        recipient_id, status, token = None, "new", None
        if q["kind"] == "gift":
            recipient_id = user_id if to_self else _known_user(conn, recipient)
            status = "paid" if recipient_id else "awaiting_recipient"
            token = None if recipient_id else secrets.token_urlsafe(9)
        cur = conn.execute(
            "INSERT INTO orders (user_id, kind, title, qty, months, gift_id, gift_stars, gift_text, recipient, "
            "recipient_id, gift_token, price, cost_usd, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (user_id, q["kind"], q["title"], q.get("qty", 1), q.get("months", 0), q.get("gift_id", ""),
             q.get("gift_stars", 0), str(item.get("text") or "")[:120], recipient or (user["username"] or ""),
             recipient_id, token, q["price"], q.get("cost_usd", ""), status, db.now(), db.now()))
        oid = cur.lastrowid
        move(conn, user_id, -q["price"], f"Заказ № {oid}: {q['title']}", f"order:{oid}")
    return conn.execute("SELECT * FROM orders WHERE id = ?", (oid,)).fetchone()


def _known_user(conn, username: str) -> int | None:
    row = conn.execute("SELECT id FROM users WHERE lower(username) = lower(?)", (username,)).fetchone()
    return row[0] if row else None


def refund(conn: sqlite3.Connection, order_id: int, reason: str) -> bool:
    """Заказ не выполнен — деньги на баланс. Один раз: статус меняется в той же транзакции."""
    with db.tx(conn):
        o = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if o is None or o["status"] in ("completed", "sent", "failed"):
            return False
        conn.execute("UPDATE orders SET status = 'failed', error = ?, updated_at = ? WHERE id = ?",
                     (reason[:300], db.now(), order_id))
        move(conn, o["user_id"], o["price"], f"Возврат за заказ № {order_id}", f"refund:{order_id}")
    return True


def gift_for(conn, gift_id: str) -> dict[str, Any] | None:
    """Подарок из каталога (с file_id анимации) — для отдачи анимации в мини-приложение."""
    return next((g for g in json.loads(db.get_setting(conn, "gifts", "[]")) if str(g.get("id")) == str(gift_id)), None)


def claim_gift(conn: sqlite3.Connection, token: str, user: dict[str, Any]) -> tuple[str, sqlite3.Row | None]:
    """Кто-то открыл ссылку подарка и нажал Start.

    Подарок отдаётся ТОЛЬКО тому, чей @username указал покупатель. Чужой человек ссылку использовать не может.
    Ответ: ("ok", заказ) · ("gone", None) — ссылка использована/устарела · ("buyer", заказ) — открыл сам покупатель ·
    ("notyours", заказ) — это не получатель.
    """
    with db.tx(conn):
        o = conn.execute("SELECT * FROM orders WHERE gift_token = ? AND status = 'awaiting_recipient'", (token,)).fetchone()
        if o is None:
            return "gone", None
        mine = (user.get("username") or "").lower()
        if not mine or mine != (o["recipient"] or "").lower():
            return ("buyer" if int(user["id"]) == o["user_id"] else "notyours"), o
        conn.execute("UPDATE orders SET recipient_id = ?, status = 'paid', updated_at = ? WHERE id = ?",
                     (int(user["id"]), db.now(), o["id"]))
    return "ok", conn.execute("SELECT * FROM orders WHERE id = ?", (o["id"],)).fetchone()


def claim_waiting(conn: sqlite3.Connection, user: dict[str, Any]) -> list[sqlite3.Row]:
    """Получатель сам зашёл в бота (без ссылки): все подарки на его @username уходят ему."""
    name = (user.get("username") or "").lower()
    if not name:
        return []
    with db.tx(conn):
        rows = conn.execute("SELECT * FROM orders WHERE status = 'awaiting_recipient' AND lower(recipient) = ?", (name,)).fetchall()
        for o in rows:
            conn.execute("UPDATE orders SET recipient_id = ?, status = 'paid', updated_at = ? WHERE id = ?",
                         (int(user["id"]), db.now(), o["id"]))
    return rows


def public_order(o: sqlite3.Row) -> dict[str, Any]:
    st = {"new": "work", "processing": "work", "attention": "work", "paid": "work", "sending": "work",
          "awaiting_recipient": "wait", "completed": "done", "sent": "done", "failed": "fail"}.get(o["status"], "work")
    return {"id": o["id"], "title": o["title"], "to": o["recipient"], "price": o["price"], "status": st,
            "at": o["created_at"], "token": o["gift_token"] if o["status"] == "awaiting_recipient" else None}


# ── пополнение по чеку ────────────────────────────────────────

def cards(conn, method: str | None = None) -> list[sqlite3.Row]:
    q = "SELECT * FROM cards WHERE active = 1" + (" AND method = ?" if method else "") + " ORDER BY id"
    return conn.execute(q, (method,) if method else ()).fetchall()


def methods(conn) -> list[dict[str, Any]]:
    have = {c["method"] for c in cards(conn)}
    return [{"code": k, "title": v} for k, v in METHODS.items() if k in have]


def min_topup(conn) -> int:
    """Минимальная сумма пополнения в дирамах (ставит админ). По умолчанию 1 сомони."""
    try:
        return max(100, int(db.get_setting(conn, "min_topup", "100") or 100))
    except ValueError:
        return 100


def create_topup(conn: sqlite3.Connection, user_id: int, method: str, amount: int,
                 intent: dict[str, Any] | None = None) -> sqlite3.Row:
    if method not in METHODS:
        raise ShopError("Выберите способ оплаты.")
    low = min_topup(conn)
    if amount < low:
        raise ShopError(f"Минимальная сумма — {fmt(low)} сомони. / Маблағи ҳадди ақал — {fmt(low)} сомонӣ.")
    if amount > 5_000_000:
        raise ShopError("Сумма — до 50 000 сомони. / Маблағ — то 50 000 сомонӣ.")
    pool = cards(conn, method)
    if not pool:
        raise ShopError("Этот способ сейчас недоступен. / Ин усул ҳоло дастрас нест.")
    with db.tx(conn):
        conn.execute("UPDATE topups SET status = 'cancelled', resolved_at = ? "
                     "WHERE user_id = ? AND status = 'waiting'", (db.now(), user_id))   # одна открытая заявка
        turn = int(db.get_setting(conn, f"turn.{method}", "0"))
        card = pool[turn % len(pool)]   # карты по очереди
        db.set_setting(conn, f"turn.{method}", str(turn + 1))
        cur = conn.execute("INSERT INTO topups (user_id, method, card_id, amount, status, intent, created_at) "
                           "VALUES (?, ?, ?, ?, 'waiting', ?, ?)",
                           (user_id, method, card["id"], amount, json.dumps(intent or {}, ensure_ascii=False), db.now()))
    return conn.execute("SELECT * FROM topups WHERE id = ?", (cur.lastrowid,)).fetchone()


def topup_view(conn, t: sqlite3.Row) -> dict[str, Any]:
    card = conn.execute("SELECT * FROM cards WHERE id = ?", (t["card_id"],)).fetchone()
    return {"id": t["id"], "method": METHODS.get(t["method"], t["method"]), "amount": t["amount"],
            "amount_text": fmt(t["amount"]), "details": card["details"] if card else "", "status": t["status"]}


def decide_topup(conn: sqlite3.Connection, topup_id: int, ok: bool, who: str, note: str = "") -> sqlite3.Row | None:
    """Админ решил: зачислить или отклонить. Один раз — кто первый нажал."""
    with db.tx(conn):
        t = conn.execute("SELECT * FROM topups WHERE id = ? AND status = 'pending'", (topup_id,)).fetchone()
        if t is None:
            return None
        conn.execute("UPDATE topups SET status = ?, decided_by = ?, note = ?, resolved_at = ? WHERE id = ?",
                     ("paid" if ok else "rejected", who, note[:200], db.now(), topup_id))
        if ok:
            move(conn, t["user_id"], t["amount"], f"Пополнение № {topup_id}", f"topup:{topup_id}")
    return conn.execute("SELECT * FROM topups WHERE id = ?", (topup_id,)).fetchone()


def run_intent(conn: sqlite3.Connection, t: sqlite3.Row) -> sqlite3.Row | None:
    """После зачисления: если клиент пополнял ради покупки — оформить её сразу."""
    try:
        intent = json.loads(t["intent"] or "{}")
    except ValueError:
        return None
    if not intent.get("kind"):
        return None
    try:
        return place_order(conn, t["user_id"], intent)
    except ShopError:
        return None   # цена изменилась или товара нет — деньги остаются на балансе
