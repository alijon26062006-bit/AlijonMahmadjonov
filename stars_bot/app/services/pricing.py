"""Автообновление цен: бот сам спрашивает себестоимость и держит наценку.

Курс TON и цены сервиса выдачи меняются в течение дня. Если цену не
обновлять, наценка расползается: сегодня 15%, завтра 3%, послезавтра
продажа в убыток. Задача раз в N минут спрашивает свежую цену и
пересчитывает продажную по заданному проценту.
"""
from __future__ import annotations

import asyncio
import logging
from decimal import ROUND_HALF_UP, Decimal

import aiosqlite
from aiogram import Bot

from app import db, runtime
from app.money import fmt

log = logging.getLogger(__name__)

#: Насколько цена должна скакнуть, чтобы предупредить владельца.
ALERT_PERCENT = 20


async def refresh_once(
    conn: aiosqlite.Connection, provider, bot: Bot | None = None
) -> dict:
    """Обновить себестоимость и продажные цены. Возвращает отчёт."""
    estimate_fn = getattr(provider, "cost_estimate", None)
    if estimate_fn is None:
        return {"ok": False, "reason": "сервис выдачи не отдаёт цены"}

    rate = runtime.usd_rate()
    if rate <= 0:
        return {"ok": False, "reason": "не задан курс доллара"}

    margin = runtime.margin_percent()
    if margin <= 0:
        return {"ok": False, "reason": "не задана наценка"}

    report: dict = {"ok": True, "changed": [], "reason": ""}

    # ---- звёзды ----
    try:
        estimate = await estimate_fn("stars", 1000)
    except Exception as exc:  # noqa: BLE001 — фон не должен падать
        return {"ok": False, "reason": f"цена не пришла: {exc}"}

    cost = _to_diram(estimate.usd_per_unit, rate)
    old_price = runtime.star_price()
    new_price = _with_margin(cost, margin)

    if cost != runtime.star_cost():
        await runtime.set_value(conn, "star_cost_diram", str(cost))
    if new_price != old_price:
        await runtime.set_value(conn, "star_price_diram", str(new_price))
        report["changed"].append(("Звезда", old_price, new_price, cost))

    # ---- premium ----
    costs = dict(runtime.premium_costs())
    plans = runtime.premium_plans()
    for plan in plans:
        months = int(plan["months"])
        try:
            item = await estimate_fn("premium", months)
        except Exception as exc:  # noqa: BLE001
            log.info("Цена Premium %s мес. не пришла: %s", months, exc)
            continue
        plan_cost = _to_diram(item.usd_total, rate)
        costs[months] = plan_cost
        wanted = _with_margin(plan_cost, margin)
        if wanted != int(plan["price"]):
            report["changed"].append((f"Premium {months} мес.",
                                      int(plan["price"]), wanted, plan_cost))
            plan["price"] = wanted

    if costs:
        await runtime.save_premium_costs(conn, costs)
    if any(name.startswith("Premium") for name, *_ in report["changed"]):
        await runtime.save_premium_plans(conn, plans)

    if report["changed"] and bot is not None:
        await _maybe_alert(bot, report["changed"])
    return report


def _to_diram(usd: Decimal, rate_diram: int) -> int:
    return int((usd * rate_diram).to_integral_value(rounding=ROUND_HALF_UP))


def _with_margin(cost: int, margin: int) -> int:
    return int((Decimal(cost) * (100 + margin) / 100).to_integral_value(
        rounding=ROUND_HALF_UP
    ))


async def _maybe_alert(bot: Bot, changed: list) -> None:
    """Сообщить владельцу, если цена скакнула заметно.

    Мелкие колебания курса не тревожим — иначе уведомления станут шумом
    и их перестанут читать.
    """
    from app.config import settings
    from app.services.delivery import notify_admins

    big = [
        (name, old, new)
        for name, old, new, _ in changed
        if old > 0 and abs(new - old) * 100 / old >= ALERT_PERCENT
    ]
    if not big or not settings.admin_ids:
        return

    lines = "\n".join(
        f"├ {name}: <b>{fmt(old)}</b> → <b>{fmt(new)}</b>" for name, old, new in big
    )
    await notify_admins(
        bot,
        "📈 <b>Цены заметно изменились</b>\n\n" + lines
        + f"\n\n<blockquote>Наценка {runtime.margin_percent()}% сохранена. "
          "Если рост не устраивает — выключите автоцены "
          "в /panel → Цены.</blockquote>",
    )


async def auto_price_loop(provider, bot: Bot) -> None:
    """Фоновая задача: держать наценку постоянной."""
    while True:
        try:
            minutes = max(runtime.get_int("auto_price_every", 60), 5)
            await asyncio.sleep(minutes * 60)
            if not runtime.auto_price_on():
                continue

            conn = await db.connect()
            try:
                result = await refresh_once(conn, provider, bot)
            finally:
                await conn.close()

            if not result["ok"]:
                log.info("Автоцены пропущены: %s", result["reason"])
            elif result["changed"]:
                log.info("Автоцены обновлены: %s",
                         ", ".join(name for name, *_ in result["changed"]))
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — фон не должен умирать
            log.exception("Автоцены: непредвиденная ошибка: %s", exc)
            await asyncio.sleep(60)
