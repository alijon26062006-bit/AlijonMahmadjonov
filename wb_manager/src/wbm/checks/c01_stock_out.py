"""1. Товар закончился или скоро закончится (по скорости заказов)."""

from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal

from wbm.checks.base import (
    AffectedProduct,
    Check,
    CheckOutcome,
    Finding,
    ProductNames,
    in_range,
    money,
    period_bounds,
    plural,
    register,
    top_products,
)
from wbm.checks.thresholds import Thresholds
from wbm.domain.data import DataBundle, Dataset
from wbm.domain.enums import Severity


@register
class StockOutCheck(Check):
    id = "stock_out"
    title = "Товар закончился или скоро закончится"
    requires = (Dataset.STOCKS, Dataset.ORDERS)
    optional = (Dataset.PRODUCTS,)

    def run(self, data: DataBundle, thresholds: Thresholds) -> CheckOutcome:
        t = thresholds.stock_out
        window = period_bounds(data, t.velocity_days)
        orders = Counter[int]()
        revenue: defaultdict[int, Decimal] = defaultdict(Decimal)
        vendor: dict[int, str] = {}
        for order in data.orders.rows:
            if order.is_cancelled or not in_range(order.created_at, window):
                continue
            orders[order.nm_id] += 1
            revenue[order.nm_id] += order.price
            vendor.setdefault(order.nm_id, order.vendor_code)

        stock: Counter[int] = Counter()
        for item in data.stocks.rows:
            stock[item.nm_id] += item.quantity
            vendor.setdefault(item.nm_id, item.vendor_code)

        names = ProductNames(data)
        ended: list[AffectedProduct] = []
        critical: list[AffectedProduct] = []
        warning: list[AffectedProduct] = []
        for nm_id, count in orders.items():
            per_day = count / t.velocity_days
            on_hand = stock.get(nm_id, 0)
            average_price = revenue[nm_id] / count
            metrics: dict[str, int | float | str] = {
                "остаток_шт": on_hand,
                f"заказов_за_{t.velocity_days}_дней": count,
                "заказов_в_день": round(per_day, 2),
                "средняя_цена_заказа_руб": money(average_price),
            }
            if on_hand <= 0:
                metrics["выручка_в_день_под_угрозой_руб"] = money(average_price * Decimal(per_day))
                ended.append(names.product(nm_id, vendor.get(nm_id), metrics))
                continue
            if per_day < t.min_daily_orders:
                continue
            days_left = on_hand / per_day
            metrics["дней_запаса"] = round(days_left, 1)
            if days_left < t.critical_days:
                critical.append(names.product(nm_id, vendor.get(nm_id), metrics))
            elif days_left < t.warning_days:
                warning.append(names.product(nm_id, vendor.get(nm_id), metrics))

        findings: list[Finding] = []
        if ended:
            lost = sum(float(p.metrics["выручка_в_день_под_угрозой_руб"]) for p in ended)
            findings.append(
                Finding(
                    severity=Severity.CRITICAL,
                    title=f"Закончились товары, которые покупают: {plural(len(ended), 'товар', 'товара', 'товаров')}",
                    facts={"товаров": len(ended), "выручка_в_день_под_угрозой_руб": money(lost)},
                    reason=(
                        f"Эти товары заказывали за последние {t.velocity_days} дней, "
                        "а сейчас на складах их нет. Пока товара нет, заказы уходят к конкурентам."
                    ),
                    recommendation=(
                        "Срочно отгрузите поставку по этим товарам. Начните с тех, "
                        "у кого больше заказов в день."
                    ),
                    products=top_products(
                        ended, key=lambda p: float(p.metrics["заказов_в_день"]), reverse=True
                    ),
                )
            )
        for severity, items, limit in (
            (Severity.CRITICAL, critical, t.critical_days),
            (Severity.IMPORTANT, warning, t.warning_days),
        ):
            if not items:
                continue
            findings.append(
                Finding(
                    severity=severity,
                    title=(
                        f"Закончатся в ближайшие {limit:g} дней: "
                        f"{plural(len(items), 'товар', 'товара', 'товаров')}"
                    ),
                    facts={"товаров": len(items), "порог_дней": limit},
                    reason=(
                        "При нынешней скорости заказов остатка хватит меньше чем на "
                        f"{limit:g} дней. Поставка на склад WB занимает время."
                    ),
                    recommendation="Запланируйте поставку сейчас, чтобы товар не закончился.",
                    products=top_products(items, key=lambda p: float(p.metrics["дней_запаса"])),
                )
            )
        return self.outcome(findings)
