"""2. Падение заказов по товару к прошлому периоду."""

from __future__ import annotations

from collections import Counter

from wbm.checks.base import (
    AffectedProduct,
    Check,
    CheckOutcome,
    Finding,
    ProductNames,
    in_range,
    percent,
    period_bounds,
    plural,
    previous_period_bounds,
    register,
    top_products,
)
from wbm.checks.thresholds import Thresholds
from wbm.domain.data import DataBundle, Dataset
from wbm.domain.enums import Severity


@register
class OrdersDropCheck(Check):
    id = "orders_drop"
    title = "Падение заказов к прошлому периоду"
    requires = (Dataset.ORDERS,)
    optional = (Dataset.STOCKS, Dataset.PRODUCTS)

    def run(self, data: DataBundle, thresholds: Thresholds) -> CheckOutcome:
        t = thresholds.orders_drop
        current_bounds, previous_bounds = period_bounds(data), previous_period_bounds(data)
        current: Counter[int] = Counter()
        previous: Counter[int] = Counter()
        vendor: dict[int, str] = {}
        for order in data.orders.rows:
            if order.is_cancelled:
                continue
            vendor.setdefault(order.nm_id, order.vendor_code)
            if in_range(order.created_at, current_bounds):
                current[order.nm_id] += 1
            elif in_range(order.created_at, previous_bounds):
                previous[order.nm_id] += 1

        stock: Counter[int] | None = None
        if data.stocks.usable:
            stock = Counter()
            for item in data.stocks.rows:
                stock[item.nm_id] += item.quantity

        names = ProductNames(data)
        days = data.period_days
        by_severity: dict[Severity, list[AffectedProduct]] = {
            Severity.CRITICAL: [],
            Severity.IMPORTANT: [],
        }
        for nm_id, before in previous.items():
            if before < t.min_previous_orders:
                continue
            now = current.get(nm_id, 0)
            drop = (before - now) / before
            if drop < t.important_drop:
                continue
            metrics: dict[str, int | float | str] = {
                f"заказов_за_прошлые_{days}_дней": before,
                f"заказов_за_последние_{days}_дней": now,
                "падение_процентов": percent(drop),
            }
            if stock is not None:
                metrics["остаток_шт"] = stock.get(nm_id, 0)
            severity = Severity.CRITICAL if drop >= t.critical_drop else Severity.IMPORTANT
            by_severity[severity].append(names.product(nm_id, vendor.get(nm_id), metrics))

        findings: list[Finding] = []
        total_before, total_now = sum(previous.values()), sum(current.values())
        if total_before >= t.min_previous_orders:
            total_drop = (total_before - total_now) / total_before
            if total_drop >= t.important_drop:
                findings.append(
                    Finding(
                        severity=(
                            Severity.CRITICAL
                            if total_drop >= t.critical_drop
                            else Severity.IMPORTANT
                        ),
                        title=f"Заказы магазина упали на {percent(total_drop):g}%",
                        facts={
                            f"заказов_за_прошлые_{days}_дней": total_before,
                            f"заказов_за_последние_{days}_дней": total_now,
                            "падение_процентов": percent(total_drop),
                        },
                        reason="Магазин в целом получает заметно меньше заказов, чем месяцем ранее.",
                        recommendation=(
                            "Посмотрите товары ниже: обычно падение дают несколько позиций "
                            "(закончился товар, выросла цена, отключилась реклама, упал рейтинг)."
                        ),
                    )
                )

        for severity, items in by_severity.items():
            if not items:
                continue
            findings.append(
                Finding(
                    severity=severity,
                    title=(
                        f"Заказы упали более чем на "
                        f"{percent(t.critical_drop if severity is Severity.CRITICAL else t.important_drop):g}%: "
                        f"{plural(len(items), 'товар', 'товара', 'товаров')}"
                    ),
                    facts={"товаров": len(items), "дней_в_периоде": days},
                    reason=(
                        f"Сравнили заказы за последние {days} дней с предыдущими {days} днями. "
                        "Если остаток 0 — причина, скорее всего, в том, что товар закончился."
                    ),
                    recommendation=(
                        "Проверьте по каждому товару остаток, цену и скидку, рекламу, "
                        "свежие негативные отзывы и позиции в поиске."
                    ),
                    products=top_products(
                        items, key=lambda p: float(p.metrics["падение_процентов"]), reverse=True
                    ),
                )
            )
        return self.outcome(findings)
