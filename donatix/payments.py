"""Заявки на пополнение баланса.

Клиент выбирает способ (Алиф, DC, Эсхата, USDT…), сумму и переводит деньги
по реквизитам. Админ видит заявку, сверяет поступление и подтверждает —
баланс зачисляется автоматически, клиенту приходит уведомление.
Сюда же подключаются автоматические способы, когда появится API банка."""

from __future__ import annotations

import json
import secrets
import sqlite3
from decimal import ROUND_UP, Decimal
from typing import Any

from . import accounts, db
from .config import PAY_METHODS, Config
from .money import MoneyError, fmt, to_decimal, to_micro
from .notify import notify


class PaymentError(ValueError):
    pass


CURRENCIES = ("TJS", "USDT", "USD")


def _default_methods(conn: sqlite3.Connection, config: Config) -> list[dict[str, Any]]:
    """Первый запуск: стандартные способы с реквизитами из старых настроек или .env."""
    out = []
    for code, (title, currency) in PAY_METHODS.items():
        details = db.get_setting(conn, f"pay.{code}")
        if details is None:
            details = config.pay_methods.get(code, "")
        out.append({"code": code, "title": title, "currency": currency, "details": details.strip(),
                    "enabled": bool(details.strip())})
    return out


def settings(conn: sqlite3.Connection, config: Config) -> dict[str, Any]:
    """Способы оплаты, курс, минимум (в сомони) и порог «мало денег». Всё меняется в админке."""
    raw = db.get_setting(conn, "pay.methods_json")
    all_methods = json.loads(raw) if raw else _default_methods(conn, config)
    rate = Decimal(db.get_setting(conn, "pay.tjs_rate") or config.tjs_rate)
    min_tjs = Decimal(db.get_setting(conn, "pay.min_tjs") or config.pay_min_tjs)
    low = Decimal(db.get_setting(conn, "pay.low_balance_usd") or config.low_balance_usd)
    return {
        "all_methods": all_methods,
        "details": {m["code"]: m["details"] for m in all_methods if m.get("enabled") and m["details"].strip()},
        "tjs_rate": rate, "min_tjs": min_tjs, "low_usd": low,
        "min_usd": (min_tjs / rate).quantize(Decimal("0.01"), rounding=ROUND_UP),
    }


def save_settings(conn: sqlite3.Connection, config: Config, methods_in: list[dict[str, Any]], tjs_rate: str,
                  min_tjs: str, low_usd: str) -> None:
    try:
        rate = to_decimal(tjs_rate.replace(",", "."))
        minimum = to_decimal(min_tjs.replace(",", "."))
        low = to_decimal(low_usd.replace(",", ".") or "0")
    except MoneyError:
        raise PaymentError("Курс, минимум и порог — числа.") from None
    if rate <= 0 or minimum <= 0 or low < 0:
        raise PaymentError("Курс и минимум должны быть больше нуля.")
    clean, seen = [], set()
    for m in methods_in:
        title = str(m.get("title", "")).strip()[:60]
        details = str(m.get("details", "")).strip()[:1000]
        if m.get("delete") or (not title and not details):
            continue
        if not title:
            raise PaymentError("У каждого способа должно быть название.")
        code = str(m.get("code") or "").strip() or "m" + secrets.token_hex(3)
        if code in seen:
            code = "m" + secrets.token_hex(3)
        seen.add(code)
        currency = m.get("currency") if m.get("currency") in CURRENCIES else "TJS"
        clean.append({"code": code, "title": title, "currency": currency, "details": details,
                      "enabled": bool(m.get("enabled"))})
    with db.tx(conn):
        db.set_setting(conn, "pay.methods_json", json.dumps(clean, ensure_ascii=False))
        db.set_setting(conn, "pay.tjs_rate", str(rate))
        db.set_setting(conn, "pay.min_tjs", str(minimum))
        db.set_setting(conn, "pay.low_balance_usd", str(low))


def title_for(conn: sqlite3.Connection, config: Config, code: str) -> str:
    for m in settings(conn, config)["all_methods"]:
        if m["code"] == code:
            return m["title"]
    return PAY_METHODS.get(code, (code,))[0]


def methods(conn: sqlite3.Connection, config: Config) -> list[dict[str, str]]:
    conf = settings(conn, config)
    return [{"code": m["code"], "title": m["title"], "currency": m["currency"], "details": m["details"]}
            for m in conf["all_methods"] if m["code"] in conf["details"]]


def pay_amount(tjs_rate: Decimal, currency: str, usd: Decimal) -> tuple[str, str]:
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
    if usd * conf["tjs_rate"] < conf["min_tjs"] or usd > Decimal("100000"):
        raise PaymentError(f"Минимальная сумма пополнения — {conf['min_tjs']:f} сомони (${conf['min_usd']}).")
    open_n = conn.execute("SELECT COUNT(*) FROM payments WHERE user_id = ? AND status = 'pending'",
                          (user["id"],)).fetchone()[0]
    if open_n >= 3:
        raise PaymentError("У вас уже 3 заявки в ожидании. Дождитесь их проверки.")
    currency = next(m["currency"] for m in conf["all_methods"] if m["code"] == method)
    pay, cur = pay_amount(conf["tjs_rate"], currency, usd)
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
        title = title_for(conn, config, p["method"])
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
