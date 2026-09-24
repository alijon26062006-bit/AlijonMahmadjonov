"""Заказы — самое важное место. Порядок, при котором деньги не теряются:

1. Списываем у клиента и создаём заказ «processing» — в одной транзакции.
2. Отправляем заказ поставщику со своим уникальным ключом (Idempotency-Key).
3. Поставщик точно отказал → возвращаем деньги.
   Ответ непонятен (таймаут, сеть) → деньги НЕ возвращаем, заказ остаётся
   «processing», воркер выясняет, что случилось.
4. Воркер спрашивает статус у поставщика, пока заказ не выполнится или не упадёт.
   Упал → возврат. Никто не понимает, что с заказом → статус «attention» для админа.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from . import accounts, db
from .catalog import get_product
from .config import Config
from .money import MoneyError, apply_markup, fmt, fmt_unit, order_total_micro, to_decimal
from .suppliers import Supplier, SupplierRejected, SupplierUnavailable

log = logging.getLogger(__name__)

MAX_CREATE_ATTEMPTS = 5
IN_FLIGHT_SECONDS = 30  # столько ждём, пока запрос из веба сам дойдёт до поставщика
STUCK_HOURS = 24
REFRESH_ON_READ_SECONDS = 5

TG_USERNAME_RE = re.compile(r"^@?[A-Za-z][A-Za-z0-9_]{3,31}$")
STEAM_LOGIN_RE = re.compile(r"^[A-Za-z0-9_.\-]{2,64}$")


class OrderError(Exception):
    def __init__(self, message: str, code: str, http_status: int = 400):
        super().__init__(message)
        self.code = code
        self.http_status = http_status


# ── Проверка ввода ───────────────────────────────────────────


def _clean_fields(product: dict[str, Any], raw: dict[str, Any] | None) -> dict[str, str]:
    raw = raw or {}
    result: dict[str, str] = {}
    for spec in product["fields"]:
        key = spec["key"]
        value = str(raw.get(key, "") or "").strip()
        if not value:
            raise OrderError(f"Не заполнено поле «{spec.get('label') or key}» ({key}).", "missing_field")
        if len(value) > 256:
            raise OrderError(f"Поле {key} слишком длинное.", "invalid_field")
        if key == "telegram_username":
            if not TG_USERNAME_RE.match(value):
                raise OrderError("Неверный Telegram username.", "invalid_field")
            value = "@" + value.lstrip("@")
        elif key == "steam_login":
            if not STEAM_LOGIN_RE.match(value):
                raise OrderError("Неверный логин Steam.", "invalid_field")
        elif key == "currency" and product["kind"] == "steam_topup":
            value = value.upper()
            if value not in product["supplier_ref"].get("rates", {}):
                raise OrderError("Валюта: USD, RUB, KZT или UAH.", "invalid_field")
        elif key == "invite_url":
            from .steam_gifts import INVITE_RE
            if not INVITE_RE.match(value):
                raise OrderError("Ссылка-приглашение Steam должна быть вида https://s.team/p/…/…", "invalid_field")
        elif key in ("app_id", "sub_id"):
            if not value.isdigit():
                raise OrderError(f"{key} — число.", "invalid_field")
        elif key == "region" and product["kind"] == "steam_gift":
            from .steam_gifts import REGION_RE
            if not REGION_RE.match(value):
                raise OrderError("Неверный регион.", "invalid_field")
        elif key == "amount":
            try:
                amount = to_decimal(value.replace(",", "."))
            except MoneyError:
                raise OrderError("Сумма — число.", "invalid_field") from None
            if amount <= 0 or amount != amount.quantize(Decimal("0.01")):
                raise OrderError("Сумма — положительное число, не больше 2 знаков после точки.", "invalid_field")
            value = f"{amount:.2f}"
        result[key] = value
    return result


def _units(product: dict[str, Any], qty: int, fields: dict[str, str]) -> Decimal:
    """Сколько «единиц» закупаем: штук/звёзд, а для Steam — долларов, зачисляемых на аккаунт."""
    if product["kind"] != "steam_topup":
        return Decimal(qty)
    ref = product["supplier_ref"]
    rate = to_decimal(ref["rates"][fields["currency"]])
    usd = to_decimal(fields["amount"]) / rate
    lo, hi = to_decimal(ref.get("min_usd", "0.5")), to_decimal(ref.get("max_usd", "1000"))
    if not lo <= usd <= hi:
        cur = fields["currency"]
        raise OrderError(
            f"Сумма: от {lo * rate:.2f} до {hi * rate:.2f} {cur}.", "invalid_quantity"
        )
    return usd


def _clean_quantity(product: dict[str, Any], quantity: Any) -> int:
    if product["max_qty"] <= 1 and product["min_qty"] <= 1:
        return 1
    try:
        qty = int(quantity)
    except (TypeError, ValueError):
        raise OrderError("quantity — целое число.", "invalid_quantity") from None
    if not product["min_qty"] <= qty <= product["max_qty"]:
        raise OrderError(
            f"Количество: от {product['min_qty']} до {product['max_qty']}.", "invalid_quantity"
        )
    if product["stock"] is not None and qty > product["stock"]:
        raise OrderError(f"В наличии только {product['stock']} шт.", "out_of_stock", 409)
    return qty


# ── Создание ────────────────────────────────────────────────


def quote(config: Config, user: sqlite3.Row, product: dict[str, Any], units: Decimal | int) -> dict[str, Any]:
    unit = apply_markup(to_decimal(product["base_price"]), accounts.markup_for(user, config, product["kind"]))
    return {"unit_price": unit, "total_micro": order_total_micro(unit, units)}


def create_order(
    conn: sqlite3.Connection,
    config: Config,
    supplier: Supplier,
    user: sqlite3.Row,
    *,
    product_id: str,
    quantity: Any = 1,
    fields: dict[str, Any] | None = None,
    client_idem_key: str | None = None,
    source: str = "api",
) -> tuple[sqlite3.Row, bool]:
    """Возвращает (заказ, повтор_ли). Повтор — тот же Idempotency-Key, новый заказ не создан."""
    if user["status"] != "active":
        raise OrderError("Аккаунт не активирован. Дождитесь одобрения.", "account_inactive", 403)
    product = get_product(conn, product_id)
    if product is None:
        raise OrderError("Товар не найден или недоступен.", "product_not_found", 404)
    qty = _clean_quantity(product, quantity)
    clean = _clean_fields(product, fields)
    fields_json = json.dumps(clean, ensure_ascii=False, sort_keys=True)
    if client_idem_key is not None:
        client_idem_key = client_idem_key.strip()[:255] or None

    if client_idem_key:
        existing = _by_client_key(conn, user["id"], client_idem_key)
        if existing is not None:
            return _replay(existing, product_id, qty, fields_json), True

    display = _display_name(product, qty, clean)
    if product["kind"] == "steam_gift":
        from . import steam_gifts
        edition, units = steam_gifts.resolve(supplier, clean)
        display = f"Steam Gift — {edition} ({clean['region']})"
    else:
        units = _units(product, qty, clean)
    if product["kind"] == "steam_topup":
        _check_steam_login(supplier, clean["steam_login"])
    if product["kind"] == "topup":
        _check_account(supplier, product, clean)
    q = quote(config, user, product, units)
    cost_micro = order_total_micro(to_decimal(product["base_price"]), units)
    ts = db.now()
    try:
        with db.tx(conn):
            cur = conn.execute(
                """INSERT INTO orders (user_id, product_id, kind, product_name, quantity, fields_json,
                       unit_price, total_micro, cost_micro, status, supplier_idem_key, idempotent_supply,
                       client_idem_key, source, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'processing', ?, ?, ?, ?, ?, ?)""",
                (user["id"], product["id"], product["kind"], display, qty, fields_json,
                 fmt_unit(q["unit_price"]), q["total_micro"], cost_micro, f"dx-{uuid.uuid4()}",
                 1 if supplier.is_idempotent(product["kind"]) else 0, client_idem_key, source, ts, ts),
            )
            order_id = int(cur.lastrowid)
            public_id = f"dx-{order_id}"
            conn.execute("UPDATE orders SET public_id = ? WHERE id = ?", (public_id, order_id))
            accounts.post_ledger(conn, user["id"], -q["total_micro"], f"Заказ {public_id}", order_id=order_id)
    except accounts.InsufficientBalance as exc:
        raise OrderError(
            f"Недостаточно средств: нужно ${fmt(exc.need)}, на балансе ${fmt(exc.have)}.",
            "insufficient_balance", 402,
        ) from None
    except sqlite3.IntegrityError:
        # Два одинаковых запроса пришли одновременно — второй получает первый заказ.
        existing = _by_client_key(conn, user["id"], client_idem_key) if client_idem_key else None
        if existing is None:
            raise
        return _replay(existing, product_id, qty, fields_json), True

    order = get_order_row(conn, order_id)
    _send_to_supplier(conn, supplier, order, product)
    return get_order_row(conn, order_id), False


def _check_steam_login(supplier: Supplier, login: str) -> None:
    """До списания денег: можно ли пополнить этот аккаунт."""
    try:
        ok = supplier.check_steam_login(login)
    except SupplierRejected as exc:
        raise OrderError(f"Проверка логина Steam: {exc}", "invalid_field") from None
    except SupplierUnavailable:
        raise OrderError("Не удалось проверить логин Steam. Попробуйте через минуту.", "supplier_unavailable",
                         503) from None
    if not ok:
        raise OrderError("Этот аккаунт Steam нельзя пополнить. Проверьте логин (не никнейм).",
                         "steam_login_invalid")


def _check_account(supplier: Supplier, product: dict[str, Any], fields: dict[str, str]) -> None:
    """До списания денег: существует ли аккаунт игрока. Если поставщик не ответил — не мешаем заказу."""
    from . import account_check
    if not fields or not account_check.can_check(supplier, product):
        return
    result = account_check.check(supplier, product, fields)
    if result["valid"] is False:
        raise OrderError(f"Аккаунт не найден — проверьте ID. {result.get('message') or ''}".strip(),
                         "account_not_found")


def _display_name(product: dict[str, Any], qty: int, fields: dict[str, str] | None = None) -> str:
    if product["kind"] == "steam_topup" and fields:
        return f"Steam {fields['amount']} {fields['currency']}"
    if product["kind"] == "telegram_stars":
        return f"Telegram Stars {qty}"
    if product["kind"] == "gift_card" and qty > 1:
        return f"{product['name']} × {qty}"
    if product["category_name"] and product["category_name"] not in product["name"]:
        return f"{product['category_name']} — {product['name']}"
    return product["name"]


def _by_client_key(conn: sqlite3.Connection, user_id: int, key: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM orders WHERE user_id = ? AND client_idem_key = ?", (user_id, key)
    ).fetchone()


def _replay(existing: sqlite3.Row, product_id: str, qty: int, fields_json: str) -> sqlite3.Row:
    if existing["product_id"] != product_id or existing["quantity"] != qty or existing["fields_json"] != fields_json:
        raise OrderError(
            "Этот Idempotency-Key уже использован для другого заказа.", "idempotency_key_reused", 409
        )
    return existing


def _send_to_supplier(
    conn: sqlite3.Connection, supplier: Supplier, order: sqlite3.Row, product: dict[str, Any] | None = None
) -> None:
    if product is None:
        product = get_product(conn, order["product_id"], for_sale=False)
        if product is None:
            _to_attention(conn, order["id"], "Товар пропал из каталога — проверьте вручную.")
            return
    conn.execute(
        "UPDATE orders SET supplier_attempts = supplier_attempts + 1, updated_at = ? WHERE id = ?",
        (db.now(), order["id"]),
    )
    try:
        result = supplier.create_order(
            product, order["quantity"], json.loads(order["fields_json"]), order["supplier_idem_key"]
        )
    except SupplierRejected as exc:
        log.warning("поставщик отказал по %s: %s", order["public_id"], exc)
        fail_and_refund(conn, order["id"], _client_error(exc))
        return
    except SupplierUnavailable as exc:
        log.warning("поставщик не ответил по %s: %s", order["public_id"], exc)
        conn.execute("UPDATE orders SET error = ? WHERE id = ?", (f"поставщик: {exc}", order["id"]))
        return
    except Exception as exc:  # неожиданное — не теряем заказ, отдаём админу
        log.exception("ошибка при отправке %s", order["public_id"])
        _to_attention(conn, order["id"], f"Ошибка при отправке поставщику: {exc}")
        return
    conn.execute(
        "UPDATE orders SET supplier_order_id = ?, supplier_status = ?, error = NULL, updated_at = ? WHERE id = ?",
        (result.order_id, result.raw_status, db.now(), order["id"]),
    )
    if result.order_id is None:
        _to_attention(conn, order["id"], "Поставщик принял заказ, но не вернул его номер.")
    elif result.status == "failed":
        fail_and_refund(conn, order["id"], result.message or "Поставщик отклонил заказ.")


def _client_error(exc: SupplierRejected) -> str:
    # Не показываем клиенту, что у нас кончились деньги у поставщика.
    if exc.code == "insufficient_balance" or "баланс" in str(exc).lower() or "balance" in str(exc).lower():
        return "Товар временно недоступен. Деньги возвращены на баланс."
    return f"Поставщик отклонил заказ: {exc}"


# ── Итоги заказа ─────────────────────────────────────────────


def fail_and_refund(conn: sqlite3.Connection, order_id: int, reason: str, *, by_admin: int | None = None) -> bool:
    """Отменить заказ и вернуть деньги. Возврат делается ровно один раз."""
    with db.tx(conn):
        changed = conn.execute(
            "UPDATE orders SET status = 'failed', error = ?, updated_at = ?, completed_at = ?, "
            "webhook_state = 'pending' WHERE id = ? AND status IN ('processing', 'attention')",
            (reason[:500], db.now(), db.now(), order_id),
        ).rowcount
        if not changed:
            return False
        order = get_order_row(conn, order_id)
        accounts.post_ledger(
            conn, order["user_id"], order["total_micro"], f"Возврат за {order['public_id']}",
            order_id=order_id, created_by=by_admin,
        )
        from .notify import notify
        notify(conn, None, order["user_id"],
               f"Заказ {order['public_id']} не выполнен, ${fmt(order['total_micro'])} вернулись на баланс.",
               f"/panel/orders/{order['public_id']}")
    return True


def complete(conn: sqlite3.Connection, order_id: int, delivery: dict[str, Any] | None, raw_status: str = "") -> bool:
    changed = conn.execute(
        "UPDATE orders SET status = 'completed', delivery_json = ?, supplier_status = ?, error = NULL, "
        "updated_at = ?, completed_at = ?, webhook_state = 'pending' "
        "WHERE id = ? AND status IN ('processing', 'attention')",
        (json.dumps(delivery or {}, ensure_ascii=False), raw_status or "completed", db.now(), db.now(), order_id),
    ).rowcount
    return bool(changed)


def _to_attention(conn: sqlite3.Connection, order_id: int, reason: str) -> None:
    conn.execute(
        "UPDATE orders SET status = 'attention', error = ?, updated_at = ? WHERE id = ? AND status = 'processing'",
        (reason[:500], db.now(), order_id),
    )


def _age_seconds(ts: str) -> float:
    created = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - created).total_seconds()


def refresh(conn: sqlite3.Connection, supplier: Supplier, order: sqlite3.Row, *, from_worker: bool = True) -> None:
    """Довести заказ до конца: доотправить поставщику или спросить статус."""
    if order["status"] != "processing":
        return
    if order["supplier_order_id"] is None:
        if not from_worker or _age_seconds(order["updated_at"]) < IN_FLIGHT_SECONDS:
            return
        if not order["idempotent_supply"]:
            _to_attention(
                conn, order["id"],
                "Связь с поставщиком прервалась при создании. Проверьте заказ в панели FazerCards: "
                "если он там есть — отметьте выполненным, если нет — верните деньги.",
            )
            return
        if order["supplier_attempts"] >= MAX_CREATE_ATTEMPTS:
            _to_attention(conn, order["id"], "Поставщик не отвечает после нескольких попыток.")
            return
        _send_to_supplier(conn, supplier, order)
        return
    try:
        result = supplier.get_order(order["supplier_order_id"])
    except SupplierRejected as exc:
        _to_attention(conn, order["id"], f"Поставщик не нашёл заказ {order['supplier_order_id']}: {exc}")
        return
    except SupplierUnavailable:
        return
    conn.execute(
        "UPDATE orders SET supplier_status = ?, updated_at = ? WHERE id = ?",
        (result.raw_status, db.now(), order["id"]),
    )
    if result.status == "completed":
        complete(conn, order["id"], result.delivery, result.raw_status)
    elif result.status == "failed":
        fail_and_refund(conn, order["id"], result.message or f"Поставщик: {result.raw_status}")
    elif _age_seconds(order["created_at"]) > STUCK_HOURS * 3600:
        _to_attention(conn, order["id"], f"Заказ в работе у поставщика больше {STUCK_HOURS} ч.")


def refresh_if_stale(conn: sqlite3.Connection, supplier: Supplier, order: sqlite3.Row) -> sqlite3.Row:
    """При чтении заказа клиентом — быстро спросить статус, не чаще раза в 5 секунд."""
    if order["status"] == "processing" and order["supplier_order_id"] and \
            _age_seconds(order["updated_at"]) >= REFRESH_ON_READ_SECONDS:
        refresh(conn, supplier, order, from_worker=False)
        return get_order_row(conn, order["id"])
    return order


def process_pending(conn: sqlite3.Connection, supplier: Supplier, limit: int = 50) -> int:
    rows = conn.execute(
        "SELECT * FROM orders WHERE status = 'processing' ORDER BY updated_at LIMIT ?", (limit,)
    ).fetchall()
    for order in rows:
        try:
            refresh(conn, supplier, order)
        except Exception:
            log.exception("воркер: заказ %s", order["public_id"])
    return len(rows)


# ── Действия админа ──────────────────────────────────────────


def admin_complete(conn: sqlite3.Connection, order_id: int, note: str) -> bool:
    return complete(conn, order_id, {"message": note.strip() or "Выполнено"}, "manual")


def admin_recheck(conn: sqlite3.Connection, order_id: int) -> None:
    conn.execute(
        "UPDATE orders SET status = 'processing', supplier_attempts = 0, updated_at = ? "
        "WHERE id = ? AND status = 'attention' AND supplier_order_id IS NOT NULL",
        (db.now(), order_id),
    )


# ── Чтение ───────────────────────────────────────────────────


def get_order_row(conn: sqlite3.Connection, order_id: int) -> sqlite3.Row:
    return conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()


def find_user_order(conn: sqlite3.Connection, user_id: int, public_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM orders WHERE user_id = ? AND public_id = ?", (user_id, public_id.strip())
    ).fetchone()


def client_status(status: str) -> str:
    # «attention» — наша внутренняя кухня; клиент видит «в обработке».
    return "processing" if status == "attention" else status


def public_view(order: sqlite3.Row) -> dict[str, Any]:
    status = client_status(order["status"])
    return {
        "order_id": order["public_id"],
        "status": status,
        "kind": order["kind"],
        "product_id": order["product_id"],
        "product_name": order["product_name"],
        "quantity": order["quantity"],
        "fields": json.loads(order["fields_json"] or "{}"),
        "unit_price_usd": order["unit_price"],
        "total_usd": fmt(order["total_micro"]),
        "delivery": json.loads(order["delivery_json"]) if order["delivery_json"] and status == "completed" else None,
        "error": order["error"] if status == "failed" else None,
        "created_at": order["created_at"],
        "completed_at": order["completed_at"],
    }


def stats(conn: sqlite3.Connection, since_days: int = 1) -> dict[str, Any]:
    since = (datetime.now(timezone.utc) - timedelta(days=since_days)).strftime("%Y-%m-%dT%H:%M:%S")
    row = conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(total_micro),0) AS revenue, COALESCE(SUM(total_micro - cost_micro),0) "
        "AS profit FROM orders WHERE status = 'completed' AND created_at >= ?",
        (since,),
    ).fetchone()
    return {"orders": row["n"], "revenue": row["revenue"], "profit": row["profit"]}
