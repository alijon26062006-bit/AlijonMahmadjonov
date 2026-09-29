"""Деньги за сутки — с 00:00 до 00:00 следующего дня (по времени Душанбе).

Для владельца: сколько за сутки перевели на карты и в крипте, сколько из этого —
его прибыль (продажи минус закупка у поставщика) и сколько можно отправить
поставщику, чтобы пополнять его баланс, а прибыль забирать себе.

  отправить поставщику = поступило − прибыль

Остаток поступлений, не потраченный клиентами за сутки, остаётся на их балансах
(«деньги клиентов») — его тоже закупают у поставщика, только позже.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from . import db, timez
from .config import Config

CUTOFF_HOUR = 0   # сутки с 00:00 до 00:00 следующего дня (по времени Душанбе)


def cutoff_hour(conn: sqlite3.Connection) -> int:
    raw = db.get_setting(conn, "report.cutoff_hour")
    return int(raw) if raw and raw.isdigit() and 0 <= int(raw) <= 23 else CUTOFF_HOUR


def window(conn: sqlite3.Connection, now: datetime | None = None, days_back: int = 0) -> tuple[datetime, datetime]:
    """Сутки 00:00 → 00:00 (местное время). days_back=0 — текущие (ещё идут), 1 — прошлые закрытые."""
    tz = timez.zone(timez.site_zone_name(conn))
    local = (now or datetime.now(timezone.utc)).astimezone(tz)
    hour = cutoff_hour(conn)
    start = local.replace(hour=hour, minute=0, second=0, microsecond=0)
    if local < start:
        start -= timedelta(days=1)
    start -= timedelta(days=days_back)   # арифметика по местным часам: всегда «12:00»
    return start, start + timedelta(days=1)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def summary(conn: sqlite3.Connection, config: Config, start: datetime, end: datetime) -> dict[str, Any]:
    from .payments import settings as pay_settings
    from .payments import title_for
    a, b = _iso(start), _iso(end)
    rate = Decimal(str(pay_settings(conn, config)["tjs_rate"] or 0))

    methods = []
    for r in conn.execute(
            "SELECT method, pay_currency, COALESCE(auto_kind, '') AS auto, COUNT(*) AS n, SUM(amount_micro) AS usd, "
            "SUM(CAST(pay_amount AS REAL)) AS paid FROM payments WHERE status = 'paid' "
            "AND resolved_at >= ? AND resolved_at < ? GROUP BY method, pay_currency, auto ORDER BY usd DESC",
            (a, b)).fetchall():
        methods.append({"title": title_for(conn, config, r["method"]), "currency": r["pay_currency"],
                        "auto": bool(r["auto"]), "count": r["n"], "usd_micro": int(r["usd"] or 0),
                        "paid": Decimal(str(round(r["paid"] or 0, 2)))})
    received = sum(m["usd_micro"] for m in methods)
    to_card = sum(m["usd_micro"] for m in methods if not m["auto"])
    by_currency: dict[str, Decimal] = {}
    for m in methods:
        by_currency[m["currency"]] = by_currency.get(m["currency"], Decimal(0)) + m["paid"]

    o = conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(total_micro), 0) AS revenue, COALESCE(SUM(cost_micro), 0) AS cost "
        "FROM orders WHERE status = 'completed' AND COALESCE(completed_at, created_at) >= ? "
        "AND COALESCE(completed_at, created_at) < ?", (a, b)).fetchone()
    revenue, cost = int(o["revenue"]), int(o["cost"])
    profit = revenue - cost
    # Реферальные бонусы — наш расход: вычитаем, чтобы видеть чистую прибыль
    referral = int(conn.execute(
        "SELECT COALESCE(SUM(amount_micro), 0) FROM referral_rewards WHERE created_at >= ? AND created_at < ?",
        (a, b)).fetchone()[0])
    net = profit - referral
    manual = int(conn.execute(
        "SELECT COALESCE(SUM(amount_micro), 0) FROM transactions WHERE amount_micro > 0 AND order_id IS NULL "
        "AND created_by IS NOT NULL AND note NOT LIKE 'Пополнение:%' AND created_at >= ? AND created_at < ?",
        (a, b)).fetchone()[0])
    clients = int(conn.execute("SELECT COALESCE(SUM(balance_micro), 0) FROM users WHERE role = 'client'")
                  .fetchone()[0])
    supplier = db.get_setting(conn, "supplier_balance")
    return {
        "start": start, "end": end, "rate": rate,
        "methods": methods, "received": received, "to_card": to_card, "crypto": received - to_card,
        "by_currency": by_currency, "payments": sum(m["count"] for m in methods),
        "orders": int(o["n"]), "revenue": revenue, "cost": cost, "gross_profit": profit,
        "referral": referral, "profit": net,
        "to_supplier": max(received - net, 0), "manual_credit": manual,
        "clients_balance": clients, "supplier_balance": supplier,
    }


def history(conn: sqlite3.Connection, config: Config, days: int = 14) -> list[dict[str, Any]]:
    out = []
    for back in range(days):
        start, end = window(conn, days_back=back)
        out.append(summary(conn, config, start, end))
    return out


def tjs(micro: int, rate: Decimal) -> str:
    """$ в микро → «1 234.50» сомони по курсу оплат."""
    from .money import SCALE
    value = (Decimal(micro) / Decimal(SCALE) * rate).quantize(Decimal("0.01"))
    return f"{value:,.2f}".replace(",", " ")


def usd(micro: int) -> str:
    """$ в микро → «1 234.50» (для отчётов хватает центов)."""
    from .money import SCALE
    value = (Decimal(micro) / Decimal(SCALE)).quantize(Decimal("0.01"))
    return f"{value:,.2f}".replace(",", " ")


def report_text(s: dict[str, Any]) -> str:
    from .packs import plural

    def both(micro: int) -> str:
        return f"${usd(micro)}" + (f" ≈ {tjs(micro, s['rate'])} с." if s["rate"] else "")

    def fmt(micro: int) -> str:
        return usd(micro)

    lines = [f"💰 <b>Деньги за {s['start']:%d.%m.%Y}</b> (сутки 00:00 → 00:00)", ""]
    lines.append(f"📥 Поступило: <b>{both(s['received'])}</b> ({s['payments']} пополн.)")
    for m in s["methods"]:
        lines.append(f"   • {m['title']}: {m['paid']:.2f} {m['currency']} · {m['count']} шт.")
    if s["manual_credit"]:
        lines.append(f"   • вручную админом (не в итоге): ${fmt(s['manual_credit'])}")
    lines += ["",
              f"🛒 Продано: {s['orders']} {plural(s['orders'], 'заказ', 'заказа', 'заказов')} на {both(s['revenue'])}",
              f"🏭 Закупка у поставщика: {both(s['cost'])}",
              *([f"📈 Прибыль с продаж: {both(s['gross_profit'])}",
                 f"🎁 Бонусы рефералам: −{both(s['referral'])}"] if s.get("referral") else []),
              f"📈 <b>Ваша прибыль: {both(s['profit'])}</b>",
              "",
              f"➡️ <b>Отправить поставщику: {both(s['to_supplier'])}</b>",
              "<i>= поступило − прибыль. Прибыль забираете себе.</i>",
              "",
              f"👛 Деньги клиентов на балансах: {both(s['clients_balance'])}",
              f"🏦 Баланс поставщика: {'$' + s['supplier_balance'] if s['supplier_balance'] else '—'}"]
    return "\n".join(lines)


def maybe_send(conn: sqlite3.Connection, config: Config, now: datetime | None = None) -> bool:
    """Раз в сутки в 00:00 — итог прошедших суток 00:00 → 00:00 в админ-бот."""
    from .worker import notify_admin
    if (db.get_setting(conn, "report.daily_on") or "1") != "1":
        return False
    start, end = window(conn, now, days_back=1)
    key = end.strftime("%Y-%m-%d")
    if db.get_setting(conn, "finance.last_day") == key:
        return False
    db.set_setting(conn, "finance.last_day", key)
    notify_admin(config, report_text(summary(conn, config, start, end)), html=True)
    return True
