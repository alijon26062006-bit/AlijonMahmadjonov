"""5. Высокий процент возвратов и отмен."""

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
    register,
    top_products,
)
from wbm.checks.thresholds import ReturnsThresholds, Thresholds
from wbm.domain.data import DataBundle, Dataset
from wbm.domain.enums import Severity

Rates = tuple[Counter[int], Counter[int], dict[int, str]]


@register
class ReturnsCheck(Check):
    id = "returns"
    title = "Высокий процент возвратов и отмен"
    requires = (Dataset.ORDERS,)
    optional = (Dataset.SALES, Dataset.PRODUCTS)

    def run(self, data: DataBundle, thresholds: Thresholds) -> CheckOutcome:
        t = thresholds.returns
        bounds = period_bounds(data)
        names = ProductNames(data)

        orders: Counter[int] = Counter()
        cancels: Counter[int] = Counter()
        vendor: dict[int, str] = {}
        for order in data.orders.rows:
            if in_range(order.created_at, bounds):
                orders[order.nm_id] += 1
                cancels[order.nm_id] += order.is_cancelled
                vendor.setdefault(order.nm_id, order.vendor_code)

        findings = self._findings(
            (orders, cancels, vendor),
            names,
            t,
            minimum=t.min_orders,
            threshold=t.cancel_rate,
            what="отмен",
            total_key="заказов",
            bad_key="отмен",
            reason=(
                "Покупатели часто отменяют заказ этих товаров. Частые причины: долгая доставка, "
                "цена выросла после заказа, нашли дешевле."
            ),
            recommendation="Проверьте сроки доставки со склада, цену и описание товара.",
        )

        message = None
        if data.sales.usable:
            sold: Counter[int] = Counter()
            returned: Counter[int] = Counter()
            for sale in data.sales.rows:
                if in_range(sale.created_at, bounds):
                    sold[sale.nm_id] += 1
                    returned[sale.nm_id] += sale.is_return
                    vendor.setdefault(sale.nm_id, sale.vendor_code)
            findings += self._findings(
                (sold, returned, vendor),
                names,
                t,
                minimum=t.min_sales,
                threshold=t.return_rate,
                what="возвратов",
                total_key="продаж_и_возвратов",
                bad_key="возвратов",
                reason=(
                    "Покупатели часто возвращают эти товары — вы платите за обратную логистику. "
                    "Частые причины: размер, качество, несоответствие фото."
                ),
                recommendation=(
                    "Почитайте отзывы по этим товарам (см. проверку «Частые жалобы») "
                    "и исправьте карточку или партию."
                ),
            )
        else:
            message = "Продажи и возвраты не загрузились — проверены только отмены."
        return self.outcome(findings, message)

    @staticmethod
    def _findings(
        counts: Rates,
        names: ProductNames,
        t: ReturnsThresholds,
        *,
        minimum: int,
        threshold: float,
        what: str,
        total_key: str,
        bad_key: str,
        reason: str,
        recommendation: str,
    ) -> list[Finding]:
        totals, bad, vendor = counts
        considered = {nm: n for nm, n in totals.items() if n >= minimum}
        if not considered:
            return []
        shop_rate = sum(bad[nm] for nm in considered) / sum(considered.values())
        by_severity: dict[Severity, list[AffectedProduct]] = {
            Severity.CRITICAL: [],
            Severity.IMPORTANT: [],
        }
        for nm_id, total in considered.items():
            rate = bad[nm_id] / total
            if rate < threshold or rate < shop_rate * t.shop_average_multiplier:
                continue
            severity = (
                Severity.CRITICAL
                if rate >= threshold * t.critical_multiplier
                else Severity.IMPORTANT
            )
            by_severity[severity].append(
                names.product(
                    nm_id,
                    vendor.get(nm_id),
                    {total_key: total, bad_key: bad[nm_id], "доля_процентов": percent(rate)},
                )
            )
        return [
            Finding(
                severity=severity,
                title=f"Много {what}: {plural(len(items), 'товар', 'товара', 'товаров')}",
                facts={
                    "товаров": len(items),
                    "средняя_доля_по_магазину_процентов": percent(shop_rate),
                    "порог_процентов": percent(threshold),
                },
                reason=reason,
                recommendation=recommendation,
                products=top_products(
                    items, key=lambda p: float(p.metrics["доля_процентов"]), reverse=True
                ),
            )
            for severity, items in by_severity.items()
            if items
        ]
