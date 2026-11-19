"""Order flow: price check -> debit customer -> order at supplier -> track -> refund on failure.

Money safety rules:
* The customer is debited and the order row is written in ONE transaction before calling the supplier.
* The supplier is called with Idempotency-Key = our public order id (where supported), so a retry
  never charges twice.
* If the supplier clearly rejects (4xx), the customer is refunded at once.
* If the outcome is unknown (timeout/5xx), the order stays `processing` with needs_check=True:
  top-ups are retried later with the same key; Telegram (no idempotency) goes to manual review.
* A refund happens at most once: the order row is locked and its status checked first.
"""
import logging
import secrets
from datetime import datetime, timedelta, timezone
from decimal import ROUND_CEILING, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .ledger import InsufficientFunds, credit, debit, lock_user
from .models import LedgerEntry, Order
from .money import CENT, d, q4, sell_price
from .settings_store import get_limits, get_markup, sales_enabled
from .supplier import SupplierError, get_supplier

log = logging.getLogger("orders")

DONE = {"completed", "complete", "success", "succeeded", "done", "delivered", "fulfilled"}
FAILED = {"refunded", "refund", "cancelled", "canceled", "failed", "error", "rejected", "declined", "expired"}
FINAL = {"completed", "refunded", "failed"}


class OrderError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def new_public_id() -> str:
    return "GM-" + secrets.token_hex(5).upper()


def extract_supplier_order(resp: dict) -> dict:
    """The supplier's order object is not documented; accept common shapes."""
    if isinstance(resp.get("order"), dict):
        return resp["order"]
    return resp


def supplier_order_id(order_obj: dict) -> str | None:
    for k in ("id", "order_id", "orderId", "public_id", "publicId"):
        v = order_obj.get(k)
        if v not in (None, ""):
            return str(v)
    return None


def map_status(order_obj: dict) -> str:
    raw = str(order_obj.get("status") or order_obj.get("state") or "").strip().lower()
    if raw in DONE:
        return "completed"
    if raw in FAILED:
        return "refunded"
    return "processing"


def extract_delivery(order_obj: dict) -> dict | None:
    """What the buyer may see: codes/keys/cards if the supplier returned any."""
    out = {k: order_obj[k] for k in ("cards", "codes", "keys", "pins", "delivery") if order_obj.get(k)}
    return out or None


# ---------------- placing orders ----------------

def _check_limits(db: Session, user_id: int, price: Decimal) -> None:
    if not sales_enabled(db):
        raise OrderError("Продажи временно приостановлены. Попробуйте позже.", 503)
    lim = get_limits(db)
    if price > lim["max_order_usd"]:
        raise OrderError(f"Сумма заказа больше лимита ${lim['max_order_usd']}. Напишите в поддержку.", 400)
    since = datetime.now(timezone.utc) - timedelta(days=1)
    spent = db.scalar(select(func.coalesce(func.sum(Order.price), 0)).where(
        Order.user_id == user_id, Order.created_at >= since, Order.status.in_(("new", "processing", "completed"))))
    if d(spent) + price > lim["daily_user_usd"]:
        raise OrderError("Превышен дневной лимит покупок. Напишите в поддержку.", 400)


def _create_and_debit(db: Session, user_id: int, product_type: str, title: str, request: dict,
                      cost: Decimal, price: Decimal) -> Order:
    _check_limits(db, user_id, price)
    user = lock_user(db, user_id)
    order = Order(public_id=new_public_id(), user_id=user_id, product_type=product_type, title=title,
                  request=request, cost=q4(cost), price=q4(price), status="new")
    db.add(order)
    try:
        debit(db, user, price, "order", ref=order.public_id, note=title)
    except InsufficientFunds:
        db.rollback()
        raise OrderError("Недостаточно средств на балансе. Пополните баланс.", 402)
    db.commit()
    return order


def _refund_locked(db: Session, order: Order, reason: str) -> None:
    """Caller holds the lock on `order`. Refunds once, then marks the order final."""
    if order.status in FINAL:
        return
    user = lock_user(db, order.user_id)
    credit(db, user, order.price, "refund", ref=order.public_id, note=reason[:255])
    order.status = "refunded"
    order.error = reason[:255]
    order.needs_check = False


def _lock_order(db: Session, order_id: int) -> Order:
    return db.execute(select(Order).where(Order.id == order_id).with_for_update()
                      .execution_options(populate_existing=True)).scalar_one()


def _after_supplier_call(db: Session, order_id: int, call, retry_safe: bool) -> Order:
    try:
        resp = call()
    except SupplierError as e:
        order = _lock_order(db, order_id)
        if e.outcome_unknown:
            order.status = "processing"
            order.needs_check = True
            order.needs_review = not retry_safe
            order.error = f"Ответ поставщика неизвестен: {e}"[:255]
            log.warning("order %s outcome unknown: %s", order.public_id, e)
        else:
            log.warning("order %s rejected by supplier: %s %s", order.public_id, e.status, e.code)
            _refund_locked(db, order, f"Поставщик отклонил заказ: {e}")
            if e.code in ("insufficient_balance", "insufficient_funds") or e.status == 402:
                order.needs_review = True  # our supplier balance is empty — admin must top it up
        db.commit()
        return order
    order = _lock_order(db, order_id)
    obj = extract_supplier_order(resp)
    order.supplier_order_id = supplier_order_id(obj)
    order.supplier_response = resp
    order.needs_check = order.supplier_order_id is None
    st = map_status(obj)
    if st == "refunded":
        _refund_locked(db, order, "Поставщик вернул заказ")
    else:
        order.status = st
        order.delivery = extract_delivery(obj)
    db.commit()
    return order


def _fresh_offers(category_id: str) -> dict:
    try:
        return get_supplier().topup_offers(category_id)
    except SupplierError as e:
        if e.status == 404:
            raise OrderError("Товар не найден", 404)
        raise OrderError("Каталог временно недоступен, попробуйте через минуту", 502)


def place_topup(db: Session, user_id: int, category_id: str, offer_id: str, fields: dict[str, str],
                expected_price: Decimal | None = None) -> Order:
    data = _fresh_offers(category_id)  # always fresh price at order time
    offer = next((o for o in data.get("offers", []) if str(o.get("offer_id")) == str(offer_id)), None)
    if offer is None:
        raise OrderError("Этот пакет больше недоступен. Обновите страницу.", 409)
    clean: dict[str, str] = {}
    for f in data.get("fields", []):
        key = f.get("key")
        val = str(fields.get(key, "")).strip()
        if not val:
            raise OrderError(f"Заполните поле «{f.get('label') or key}»", 422)
        opts = f.get("options") or []
        if f.get("type") == "select" and opts:
            allowed = {str(o.get("value", o.get("key", o))) if isinstance(o, dict) else str(o) for o in opts}
            if val not in allowed:
                raise OrderError(f"Выберите значение из списка в поле «{f.get('label') or key}»", 422)
        clean[key] = val[:128]
    cost = d(offer["price_usd"])
    price = sell_price(cost, get_markup(db))
    if expected_price is not None and price != expected_price.quantize(CENT):
        raise OrderError(f"Цена изменилась: теперь ${price}. Проверьте и подтвердите заказ ещё раз.", 409)
    title = f"{data.get('name', category_id)} • {offer.get('name', offer_id)}"
    request = {"category_id": category_id, "offer_id": str(offer_id), "fields": clean}
    order = _create_and_debit(db, user_id, "topup", title, request, cost, price)
    return _after_supplier_call(
        db, order.id,
        lambda: get_supplier().topup_order(category_id, str(offer_id), clean, order.public_id),
        retry_safe=True)


def place_telegram_stars(db: Session, user_id: int, username: str, quantity: int,
                         expected_price: Decimal | None = None) -> Order:
    try:
        q = get_supplier().telegram_stars()
    except SupplierError:
        raise OrderError("Цены Telegram временно недоступны, попробуйте через минуту", 502)
    if not (int(q["min_amount"]) <= quantity <= int(q["max_amount"])):
        raise OrderError(f"Количество звёзд: от {q['min_amount']} до {q['max_amount']}", 422)
    cost = (d(q["price_per_star"]) * quantity).quantize(Decimal("0.0001"), rounding=ROUND_CEILING)
    price = sell_price(cost, get_markup(db))
    if expected_price is not None and price != expected_price.quantize(CENT):
        raise OrderError(f"Цена изменилась: теперь ${price}. Подтвердите заказ ещё раз.", 409)
    request = {"telegram_username": username, "quantity": quantity}
    order = _create_and_debit(db, user_id, "telegram_stars", f"Telegram Stars • {quantity} зв. • @{username}",
                              request, cost, price)
    return _after_supplier_call(db, order.id, lambda: get_supplier().telegram_stars_buy(username, quantity),
                                retry_safe=False)


def place_telegram_premium(db: Session, user_id: int, username: str, months: int,
                           expected_price: Decimal | None = None) -> Order:
    try:
        q = get_supplier().telegram_premium()
    except SupplierError:
        raise OrderError("Цены Telegram временно недоступны, попробуйте через минуту", 502)
    plan = next((p for p in q.get("plans", []) if int(p["months"]) == months), None)
    if plan is None:
        raise OrderError("Срок Premium: 3, 6 или 12 месяцев", 422)
    cost = d(plan["price_usd"])
    price = sell_price(cost, get_markup(db))
    if expected_price is not None and price != expected_price.quantize(CENT):
        raise OrderError(f"Цена изменилась: теперь ${price}. Подтвердите заказ ещё раз.", 409)
    request = {"telegram_username": username, "months": months}
    order = _create_and_debit(db, user_id, "telegram_premium", f"Telegram Premium • {months} мес. • @{username}",
                              request, cost, price)
    return _after_supplier_call(db, order.id, lambda: get_supplier().telegram_premium_buy(username, months),
                                retry_safe=False)


# ---------------- tracking ----------------

def sync_order(db: Session, order_id: int) -> Order:
    """Ask the supplier for the latest status. Safe to call many times."""
    order = _lock_order(db, order_id)
    if order.status in FINAL:
        db.commit()
        return order
    order.sync_attempts += 1
    order.last_sync_at = datetime.now(timezone.utc)
    if order.supplier_order_id is None:
        if order.product_type == "topup" and order.needs_check:
            req = order.request
            db.commit()  # release the lock during the network call
            return _after_supplier_call(
                db, order.id,
                lambda: get_supplier().topup_order(req["category_id"], req["offer_id"], req["fields"], order.public_id),
                retry_safe=True)
        order.needs_review = True  # cannot be checked automatically
        db.commit()
        return order
    sid = order.supplier_order_id
    db.commit()
    try:
        resp = get_supplier().get_order(sid)
    except SupplierError as e:
        log.info("sync %s failed: %s", sid, e)
        return order
    order = _lock_order(db, order_id)
    if order.status in FINAL:
        db.commit()
        return order
    obj = extract_supplier_order(resp)
    order.supplier_response = resp
    st = map_status(obj)
    if st == "refunded":
        _refund_locked(db, order, "Поставщик вернул заказ")
    else:
        order.status = st
        order.needs_check = False
        order.delivery = extract_delivery(obj) or order.delivery
    db.commit()
    return order


def sync_pending(db: Session, limit: int = 50) -> int:
    ids = db.scalars(select(Order.id).where(Order.status.in_(("new", "processing")), Order.needs_review.is_(False))
                     .order_by(Order.last_sync_at.asc().nullsfirst()).limit(limit)).all()
    for oid in ids:
        try:
            sync_order(db, oid)
        except Exception:  # one bad order must not stop the others
            db.rollback()
            log.exception("sync of order %s failed", oid)
    return len(ids)


def admin_adjust_balance(db: Session, user_id: int, amount: Decimal, note: str) -> LedgerEntry:
    user = lock_user(db, user_id)
    if amount > 0:
        e = credit(db, user, amount, "admin", note=note)
    else:
        e = debit(db, user, -amount, "admin", note=note)
    db.commit()
    return e
