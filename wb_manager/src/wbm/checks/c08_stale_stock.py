"""8. Залежавшийся товар с дорогим хранением."""

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
class StaleStockCheck(Check):
    id = "stale_stock"
    title = "Залежавшийся товар с дорогим хранением"
    requires = (Dataset.STOCKS, Dataset.ORDERS)
    optional = (Dataset.PAID_STORAGE, Dataset.PRODUCTS)

    def run(self, data: DataBundle, thresholds: Thresholds) -> CheckOutcome:
        t = thresholds.stale_stock
        window = period_bounds(data, t.no_orders_days)
        recently_ordered = {o.nm_id for o in data.orders.rows if in_range(o.created_at, window)}
        stock: Counter[int] = Counter()
        vendor: dict[int, str] = {}
        for item in data.stocks.rows:
            stock[item.nm_id] += item.quantity
            vendor.setdefault(item.nm_id, item.vendor_code)

        storage: defaultdict[int, Decimal] | None = None
        if data.paid_storage.usable:
            storage = defaultdict(Decimal)
            storage_window = period_bounds(data)
            for row in data.paid_storage.rows:
                if in_range(row.day, storage_window):
                    storage[row.nm_id] += row.cost

        names = ProductNames(data)
        expensive: list[AffectedProduct] = []
        cheap: list[AffectedProduct] = []
        for nm_id, quantity in stock.items():
            if quantity < t.min_units or nm_id in recently_ordered:
                continue
            metrics: dict[str, int | float | str] = {
                "остаток_шт": quantity,
                "дней_без_заказов_не_меньше": t.no_orders_days,
            }
            cost = storage.get(nm_id, Decimal(0)) if storage is not None else None
            if cost is not None:
                metrics[f"хранение_за_{data.period_days}_дней_руб"] = money(cost)
            product = names.product(nm_id, vendor.get(nm_id), metrics)
            if cost is not None and cost >= t.min_storage_cost:
                expensive.append(product)
            else:
                cheap.append(product)

        storage_key = f"хранение_за_{data.period_days}_дней_руб"
        findings: list[Finding] = []
        if expensive:
            total = sum(float(p.metrics[storage_key]) for p in expensive)
            findings.append(
                Finding(
                    severity=Severity.IMPORTANT,
                    title=f"Не продаются, но дорого хранятся: {plural(len(expensive), 'товар', 'товара', 'товаров')}",
                    facts={"товаров": len(expensive), storage_key: money(total)},
                    reason=(
                        f"Заказов не было не меньше {t.no_orders_days} дней, "
                        "а WB каждый день берёт плату за хранение."
                    ),
                    recommendation=(
                        "Снизьте цену или запустите акцию, чтобы распродать остаток. "
                        "Если товар не нужен — заберите его со склада."
                    ),
                    products=top_products(
                        expensive, key=lambda p: float(p.metrics[storage_key]), reverse=True
                    ),
                )
            )
        if cheap:
            findings.append(
                Finding(
                    severity=Severity.ADVICE,
                    title=f"Лежат без заказов: {plural(len(cheap), 'товар', 'товара', 'товаров')}",
                    facts={"товаров": len(cheap), "дней_без_заказов_не_меньше": t.no_orders_days},
                    reason=f"Товар есть на складе, но заказов не было не меньше {t.no_orders_days} дней.",
                    recommendation="Проверьте карточку, цену и видимость товара в поиске.",
                    products=top_products(
                        cheap, key=lambda p: float(p.metrics["остаток_шт"]), reverse=True
                    ),
                )
            )
        message = None
        if storage is None:
            message = "Отчёт о платном хранении не загрузился — стоимость хранения не учтена."
        return self.outcome(findings, message)
