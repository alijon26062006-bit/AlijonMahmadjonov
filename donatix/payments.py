"""Заявки на пополнение баланса.

Клиент выбирает способ (Алиф, DC, Эсхата, USDT…), сумму и переводит деньги
по реквизитам. Админ видит заявку, сверяет поступление и подтверждает —
баланс зачисляется автоматически, клиенту приходит уведомление.
Сюда же подключаются автоматические способы, когда появится API банка."""

from __future__ import annotations

import sqlite3
from decimal import ROUND_UP, Decimal

from . import accounts, db
from .config import PAY_METHODS, Config
from .money import MoneyError, fmt, to_decimal, to_micro
from .notify import notify


class PaymentError(ValueError):
    pass


def settings(conn: sqlite3.Connection, config: Config) -> dict:
    """Реквизиты, курс и минимум. Что задано в админке — важнее, чем .env."""
    details = {}
    for code in PAY_METHODS:
        value = db.get_setting(conn, f"pay.{code}")
        if value is None:
            value = config.pay_methods.get(code, "")
        if value.strip():
            details[code] = value.strip()
    rate = db.get_setting(conn, "pay.tjs_rate")
    min_usd = db.get_setting(conn, "pay.min_usd")
    return {
        "details": details,
        "tjs_rate": Decimal(rate) if rate else config.tjs_rate,
        "min_usd": Decimal(min_usd) if min_usd else config.pay_min_usd,
    }


def save_settings(conn: sqlite3.Connection, details: dict[str, str], tjs_rate: str, min_usd: str) -> None:
    try:
        rate, minimum = to_decimal(tjs_rate.replace(",", ".")), to_decimal(min_usd.replace(",", "."))
    except MoneyError:
        raise PaymentError("Курс и минимум — числа.") from None
    if rate <= 0 or minimum <= 0:
        raise PaymentError("Курс и минимум должны быть больше нуля.")
    with db.tx(conn):
        for code in PAY_METHODS:
            db.set_setting(conn, f"pay.{code}", details.get(code, "").strip()[:1000])
        db.set_setting(conn, "pay.tjs_rate", str(rate))
        db.set_setting(conn, "pay.min_usd", str(minimum))


def methods(conn: sqlite3.Connection, config: Config) -> list[dict[str, str]]:
    return [{"code": c, "title": PAY_METHODS[c][0], "currency": PAY_METHODS[c][1], "details": d}
            for c, d in settings(conn, config)["details"].items()]


def pay_amount(tjs_rate: Decimal, method: str, usd: Decimal) -> tuple[str, str]:
    currency = PAY_METHODS[method][1]
    if currency == "TJS":
        return str((usd * tjs_rate).quantize(Decimal("0.01"), rounding=ROUND_UP)), "TJS"
    return str(usd.quantize(Decimal("0.01"), rounding=ROUND_UP)), currency


def create(conn: sqlite3.Connection, config: Config, user: sqlite3.Row, method: str, amount: str,
           reference: str = "") -> int:
    conf = settings(conn, config)
    if method not in conf["details"]:
        raise PaymentError("Выберите способ оплаты.")
    try:
        usd = to_decimal(amount.replace(",", ".").replace("$", "").strip())
    except MoneyError:
        raise PaymentError("Сумма — число в долларах, например 50.") from None
    if usd < conf["min_usd"] or usd > Decimal("100000"):
        raise PaymentError(f"Минимальная сумма пополнения — ${conf['min_usd']}.")
    open_n = conn.execute("SELECT COUNT(*) FROM payments WHERE user_id = ? AND status = 'pending'",
                          (user["id"],)).fetchone()[0]
    if open_n >= 3:
        raise PaymentError("У вас уже 3 заявки в ожидании. Дождитесь их проверки.")
    pay, cur = pay_amount(conf["tjs_rate"], method, usd)
    c = conn.execute(
        "INSERT INTO payments (user_id, method, amount_micro, pay_amount, pay_currency, reference, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user["id"], method, to_micro(usd), pay, cur, reference.strip()[:200] or None, db.now()),
    )
    return int(c.lastrowid)


def confirm(conn: sqlite3.Connection, config: Config, payment_id: int, admin_id: int,
            credit_usd: str | None = None) -> bool:
    """Подтвердить поступление и зачислить баланс. Ровно один раз."""
    with db.tx(conn):
        p = conn.execute("SELECT * FROM payments WHERE id = ? AND status = 'pending'", (payment_id,)).fetchone()
        if p is None:
            return False
        micro = p["amount_micro"]
        if credit_usd:
            try:
                micro = to_micro(credit_usd.replace(",", "."))
            except MoneyError:
                raise PaymentError("Сумма зачисления — число.") from None
            if micro <= 0:
                raise PaymentError("Сумма зачисления должна быть больше нуля.")
        title = PAY_METHODS.get(p["method"], (p["method"],))[0]
        tx_id = accounts.post_ledger(conn, p["user_id"], micro, f"Пополнение: {title}, заявка #{p['id']}",
                                     created_by=admin_id)
        conn.execute("UPDATE payments SET status = 'paid', amount_micro = ?, tx_id = ?, resolved_at = ?, "
                     "resolved_by = ? WHERE id = ?", (micro, tx_id, db.now(), admin_id, payment_id))
        notify(conn, config, p["user_id"], f"Баланс пополнен на ${fmt(micro)} ({title}).", "/panel/transactions")
    return True


def reject(conn: sqlite3.Connection, config: Config, payment_id: int, admin_id: int, reason: str) -> bool:
    p = conn.execute("SELECT * FROM payments WHERE id = ? AND status = 'pending'", (payment_id,)).fetchone()
    if p is None:
        return False
    conn.execute("UPDATE payments SET status = 'rejected', admin_note = ?, resolved_at = ?, resolved_by = ? "
                 "WHERE id = ?", (reason.strip()[:300] or None, db.now(), admin_id, payment_id))
    notify(conn, config, p["user_id"],
           f"Заявка на пополнение #{payment_id} отклонена" + (f": {reason.strip()}" if reason.strip() else "."),
           "/panel/balance")
    return True


def cancel(conn: sqlite3.Connection, user_id: int, payment_id: int) -> None:
    conn.execute("UPDATE payments SET status = 'cancelled', resolved_at = ? "
                 "WHERE id = ? AND user_id = ? AND status = 'pending'", (db.now(), payment_id, user_id))
