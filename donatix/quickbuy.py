"""Купить без регистрации и без отдельного пополнения: ID игрока → «Купить» → оплата → заказ уходит сам.

  1. Гость на странице товара вводит ID и жмёт «Купить». Сначала проверяем поля и ID игрока, и только
     потом тихо заводим ему аккаунт (почта-заглушка) и входим в него — в этом браузере.
  2. Денег на балансе не хватает (у гостя их нет) — покупка запоминается в сессии, и человек попадает
     на оплату ровно на недостающую сумму в сомони. В заявке запомнено, что купить (intent).
  3. Оплату подтвердили (банк, крипта, админ или кассир по чеку) — run_pending() оформляет заказ с баланса.
     Повторно заказ не создаётся: ключ повтора — номер заявки.

Аккаунт гостя — обычный аккаунт: заказы и баланс видны в этом браузере, а сохранить его навсегда можно,
задав почту и пароль или привязав Google.
"""

from __future__ import annotations

import json
import logging
import math
import secrets
import sqlite3
import time
from decimal import Decimal
from typing import Any

from . import accounts, orders, payments
from .config import Config

log = logging.getLogger(__name__)

GUEST_DOMAIN = "guest.donatix.tj"
INTENT_TTL = 2 * 3600          # покупка в сессии живёт 2 часа — потом цены могли измениться


def is_guest(user: Any) -> bool:
    """Аккаунт, заведённый покупкой без регистрации."""
    try:
        return str(user["email"] or "").endswith("@" + GUEST_DOMAIN)
    except (KeyError, IndexError, TypeError):
        return False


def new_guest(conn: sqlite3.Connection) -> int:
    tag = secrets.token_hex(5)
    return accounts.create_user(conn, email=f"g{tag}@{GUEST_DOMAIN}", login=f"g{tag}",
                                password=secrets.token_urlsafe(18), status="active")


def precheck(supplier, product: dict[str, Any], quantity: Any, fields: dict[str, Any]) -> None:
    """Ошибки ввода и неверный ID игрока — до оплаты (и до создания аккаунта гостя), а не после."""
    qty = orders._clean_quantity(product, quantity)
    clean = orders._clean_fields(product, fields)
    if product["kind"] != "steam_gift":
        orders._units(product, qty, clean)
    if product["kind"] == "steam_topup":
        orders._check_steam_login(supplier, clean["steam_login"])
    if product["kind"] == "topup":
        orders._check_account(supplier, product, clean)


# ── Покупка, ждущая оплаты: в сессии до создания заявки, потом в самой заявке ──

def remember(session: dict, items: list[dict[str, Any]], title: str, need_micro: int) -> None:
    session["buy_intent"] = {"items": items, "title": title[:120], "need": int(need_micro), "at": int(time.time())}


def pending(session: dict) -> dict[str, Any] | None:
    intent = session.get("buy_intent")
    if not isinstance(intent, dict) or time.time() - intent.get("at", 0) > INTENT_TTL:
        session.pop("buy_intent", None)
        return None
    return intent


def to_pay_tjs(conn: sqlite3.Connection, config: Config, need_micro: int, balance_micro: int) -> Decimal:
    """Сколько сомони перевести: недостающее, округлённое вверх до дирама — зачисленного точно хватит."""
    rate = payments.settings(conn, config)["tjs_rate"]
    short = max(0, need_micro - max(balance_micro, 0))
    return Decimal(math.ceil(Decimal(short) / 10_000 * rate * 100)) / 100


def attach(conn: sqlite3.Connection, payment_id: int, intent: dict[str, Any]) -> None:
    conn.execute("UPDATE payments SET intent = ? WHERE id = ?",
                 (json.dumps({"items": intent["items"], "title": intent.get("title", "")}, ensure_ascii=False),
                  payment_id))


def describe(conn: sqlite3.Connection, payment_id: int) -> dict[str, str] | None:
    """Для страницы оплаты: что покупаем и какой заказ вышел ("" — ещё нет; "!текст" — не оформился)."""
    row = conn.execute("SELECT intent, intent_order FROM payments WHERE id = ?", (payment_id,)).fetchone()
    if row is None or not row["intent"]:
        return None
    try:
        title = json.loads(row["intent"]).get("title", "")
    except ValueError:
        title = ""
    return {"title": title, "order": row["intent_order"] or ""}


def run_pending(conn: sqlite3.Connection, config: Config, supplier, payment_id: int | None = None) -> int:
    """Оплаченные заявки с покупкой → заказы. Вызывают воркер и страница оплаты (кто первый)."""
    from .notify import notify
    sql = ("SELECT * FROM payments WHERE status = 'paid' AND intent IS NOT NULL AND intent_order IS NULL"
           + (" AND id = ?" if payment_id else "") + " ORDER BY id LIMIT 20")
    done = 0
    for p in conn.execute(sql, (payment_id,) if payment_id else ()).fetchall():
        try:
            items = json.loads(p["intent"])["items"]
        except (ValueError, KeyError, TypeError):
            conn.execute("UPDATE payments SET intent_order = '!' WHERE id = ?", (p["id"],))
            continue
        made: list[str] = []
        error = ""
        for i, item in enumerate(items):
            try:
                order, _ = orders.create_order(
                    conn, config, supplier, accounts.get_user(conn, p["user_id"]),
                    product_id=item["product_id"], quantity=item.get("quantity", 1), fields=item.get("fields") or {},
                    client_idem_key=f"quick-{p['id']}-{i}", source="quick")
            except orders.OrderError as exc:
                error = str(exc)
                break
            except Exception:  # noqa: BLE001 — сбой сети поставщика: этот заказ повторим на следующем круге
                log.exception("покупка после оплаты: заявка #%s", p["id"])
                error = "retry"
                break
            made.append(order["public_id"])
        if error == "retry":
            continue
        result = ",".join(made) if not error else ("!" + error[:180])
        conn.execute("UPDATE payments SET intent_order = ? WHERE id = ? AND intent_order IS NULL", (result, p["id"]))
        if error:
            # Деньги уже на балансе — заказ человек оформит сам; говорим, почему не вышло
            notify(conn, config, p["user_id"],
                   (f"Оформлено заказов: {len(made)}. " if made else "")
                   + f"Оплата получена, деньги на балансе, но заказ не оформился: {error} "
                     "Откройте каталог и купите заново.", "/panel/catalog")
        else:
            first = made[0] if made else ""
            notify(conn, config, p["user_id"], f"✅ Оплата получена — заказ {', '.join(made)} оформлен и выполняется.",
                   f"/panel/orders/{first}" if len(made) == 1 else "/panel/orders")
            done += 1
    return done


def product_title(product: dict[str, Any], fields: dict[str, Any]) -> str:
    who = ", ".join(str(v) for v in fields.values() if v)
    name = orders._display_name(product, 1, None)
    return f"{name}" + (f" · {who}" if who else "")



def need_micro(config: Config, supplier, user: Any, product: dict[str, Any], quantity: Any,
               fields: dict[str, Any]) -> int:
    """Сколько стоит покупка этому покупателю — как посчитает create_order."""
    qty = orders._clean_quantity(product, quantity)
    clean = orders._clean_fields(product, fields)
    if product["kind"] == "steam_gift":
        from . import steam_gifts
        _, units = steam_gifts.resolve(supplier, clean)
    else:
        units = orders._units(product, qty, clean)
    return orders.quote(config, user, product, units)["total_micro"]


def save_account(conn: sqlite3.Connection, user_id: int, email: str, login: str, password: str) -> None:
    """Гость сохраняет аккаунт: своя почта, имя и пароль — дальше входит как все, с любого устройства."""
    from .security import hash_password
    email, login = email.strip().lower(), login.strip()
    if not accounts.EMAIL_RE.match(email) or email.endswith("@" + GUEST_DOMAIN):
        raise accounts.AccountError("Неверный email.")
    if not accounts.LOGIN_RE.match(login):
        raise accounts.AccountError("Имя пользователя: 3–32 символа, латиница, цифры, _ . -")
    if len(password) < 8:
        raise accounts.AccountError("Пароль — минимум 8 символов.")
    if conn.execute("SELECT 1 FROM users WHERE (email = ? OR lower(login) = lower(?)) AND id != ?",
                    (email, login, user_id)).fetchone():
        raise accounts.AccountError("Такой email или имя уже заняты.")
    conn.execute("UPDATE users SET email = ?, login = ?, password_hash = ? WHERE id = ?",
                 (email, login, hash_password(password), user_id))
