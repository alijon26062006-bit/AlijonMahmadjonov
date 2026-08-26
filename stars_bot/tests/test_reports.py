"""Отчёты за периоды, учёт себестоимости и сверка номеров заказов."""
from __future__ import annotations

import asyncio
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import env_fixture  # noqa: F401

from decimal import Decimal

from app import db, reports, runtime
from app.handlers import panel
from app.money import fmt
from app.services import pricing

PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  — {detail}" if detail else ""))


def utc(day: date, hour: int = 12) -> str:
    return datetime(day.year, day.month, day.day, hour,
                    tzinfo=timezone.utc).isoformat(timespec="seconds")


async def add_order(conn, day, *, price, cost, status=db.ORDER_DELIVERED,
                    user_id=1, qty=100, kind="stars", external=None):
    order = await db.create_order(conn, user_id=user_id, product_type=kind,
                                  quantity=qty, recipient="x", price=price, cost=cost)
    await conn.execute(
        "UPDATE orders SET status = ?, created_at = ?, fragment_order_id = ? WHERE id = ?",
        (status, utc(day), external, order.id),
    )
    await conn.commit()
    return order.id


async def main() -> None:
    for sfx in ("", "-wal", "-shm"):
        Path(str(db.settings.db_file) + sfx).unlink(missing_ok=True)
    conn = await db.connect()
    try:
        await db.init(conn)
        await runtime.load(conn)
        await run(conn)
    finally:
        await conn.close()
    print(f"\n{'=' * 52}\nПройдено: {len(PASS)}   Провалено: {len(FAIL)}")
    if FAIL:
        print("ПРОВАЛЫ:", ", ".join(FAIL))
    sys.exit(1 if FAIL else 0)


async def run(conn) -> None:
    today = reports.local_today()
    yesterday = today - timedelta(days=1)
    long_ago = today - timedelta(days=20)

    await db.upsert_user(conn, 1, "a", "A")
    await db.upsert_user(conn, 2, "b", "B")

    # Сегодня: два выполненных и один возврат
    await add_order(conn, today, price=2500, cost=2000, external="FZ-109")
    await add_order(conn, today, price=5000, cost=4000, user_id=2)
    await add_order(conn, today, price=1000, cost=800, status=db.ORDER_REFUNDED)
    # Вчера и давно
    await add_order(conn, yesterday, price=3000, cost=2400)
    await add_order(conn, long_ago, price=9000, cost=7000)

    # -------------------------------------------------- отчёт за сегодня
    since, until = reports.bounds(today, today)
    data = await db.report(conn, since, until)

    check("за сегодня учтены только сегодняшние заказы",
          data["orders"] == 3 and data["done"] == 2, str(data["orders"]))
    check("выручка считается по выполненным",
          data["revenue"] == 7500, fmt(data["revenue"]))
    check("себестоимость суммируется", data["cost"] == 6000, fmt(data["cost"]))
    check("прибыль = выручка минус себестоимость",
          data["profit"] == 1500, fmt(data["profit"]))
    check("возвраты считаются отдельно",
          data["refunded"] == 1 and data["refunded_sum"] == 1000, str(data["refunded"]))
    check("возврат не попал в выручку", data["revenue"] == 7500)
    check("покупатели считаются по головам", data["buyers"] == 2, str(data["buyers"]))
    check("звёзды суммируются", data["stars"] == 200, str(data["stars"]))

    # -------------------------------------------------- вчера и период
    since, until = reports.bounds(yesterday, yesterday)
    y = await db.report(conn, since, until)
    check("вчерашний отчёт видит только вчера",
          y["done"] == 1 and y["revenue"] == 3000, str(y["revenue"]))

    since, until = reports.bounds(yesterday, today)
    both = await db.report(conn, since, until)
    check("период из двух дней складывает оба",
          both["done"] == 3 and both["revenue"] == 10500, fmt(both["revenue"]))

    since, until = reports.bounds(long_ago, today)
    month = await db.report(conn, since, until)
    check("месячный отчёт включает старые заказы",
          month["done"] == 4 and month["revenue"] == 19500, fmt(month["revenue"]))

    # ----------------------------------------------------- разбивка по дням
    days = await db.daily_series(conn, *reports.bounds(long_ago, today),
                                 reports.tz_hours())
    check("разбивка по дням отдаёт три дня с продажами",
          len(days) == 3, str(days))
    check("в дне видно выручку и прибыль",
          any(d[2] == 7500 and d[3] == 1500 for d in days), str(days))

    # ------------------------------- заказ без себестоимости не врёт о прибыли
    await add_order(conn, today, price=4000, cost=0)
    data = await db.report(conn, *reports.bounds(today, today))
    order = await db.get_order(conn, 6)
    check("заказ без себестоимости показывает нулевую прибыль",
          order.profit == 0, str(order.profit))

    text = panel.format_report("Тест", data, days)
    check("отчёт собирается", "Прибыль" in text or "не посчитать" in text)
    check("в отчёте видны возвраты", "Возвращено" in text)

    empty = await db.report(conn, *reports.bounds(date(2020, 1, 1), date(2020, 1, 2)))
    check("пустой период не ломает отчёт",
          empty["orders"] == 0 and empty["profit"] == 0)
    panel.format_report("Пусто", empty, [])
    check("пустой отчёт тоже собирается", True)

    # ------------------------------------------- сверка номеров заказов
    found = await db.find_order_by_external(conn, "FZ-109")
    check("заказ находится по номеру платформы",
          found is not None and found.id == 1, str(found.id if found else None))
    check("несуществующий номер не находится",
          await db.find_order_by_external(conn, "FZ-999") is None)

    # ------------------------------------------------- разбор периодов
    check("границы включают весь последний день",
          reports.bounds(today, today)[1] > reports.bounds(today, today)[0])
    check("часовой пояс сдвигает границы",
          reports.bounds(date(2026, 8, 1), date(2026, 8, 1))[0].startswith("2026-07-31"),
          reports.bounds(date(2026, 8, 1), date(2026, 8, 1))[0])

    # ------------------------------------------------------- автоцены
    class FakeEstimate:
        def __init__(self, per_unit, total):
            self.usd_per_unit = Decimal(per_unit)
            self.usd_total = Decimal(total)
            self.quantity = 1000

    class Provider:
        async def cost_estimate(self, kind, amount):
            if kind == "stars":
                return FakeEstimate("0.0154", "15.40")
            return FakeEstimate("1", {3: "12.20", 6: "16.27", 12: "29.50"}[amount])

    await runtime.set_value(conn, "usd_rate_diram", "1090")
    await runtime.set_value(conn, "margin_percent", "0")
    result = await pricing.refresh_once(conn, Provider())
    check("без наценки автоцены не включаются", not result["ok"], result.get("reason"))

    await runtime.set_value(conn, "margin_percent", "15")
    result = await pricing.refresh_once(conn, Provider())
    check("автоцены отработали", result["ok"], str(result))
    # 0.0154 × 10.90 = 0.16786 -> 17 дирам; +15% = 19.55 -> 20
    check("себестоимость посчитана", runtime.star_cost() == 17, str(runtime.star_cost()))
    check("цена продажи держит наценку 15%",
          runtime.star_price() == 20, str(runtime.star_price()))
    check("себестоимость Premium сохранена",
          runtime.premium_costs().get(3) == 13298, str(runtime.premium_costs()))
    check("цена Premium пересчитана с наценкой",
          runtime.find_premium(3)["price"] == 15293,
          str(runtime.find_premium(3)))

    check("себестоимость заказа берётся из настроек",
          runtime.cost_of("stars", 100) == 1700, str(runtime.cost_of("stars", 100)))
    check("себестоимость Premium берётся по сроку",
          runtime.cost_of("premium", 3) == 13298)
    check("неизвестный срок Premium даёт ноль",
          runtime.cost_of("premium", 24) == 0)

    await runtime.set_value(conn, "usd_rate_diram", "0")
    result = await pricing.refresh_once(conn, Provider())
    check("без курса доллара автоцены отказываются работать",
          not result["ok"] and "курс" in result["reason"], result.get("reason"))

    class NoPrices:
        pass

    result = await pricing.refresh_once(conn, NoPrices())
    check("провайдер без цен не ломает автоцены", not result["ok"])


asyncio.run(main())
