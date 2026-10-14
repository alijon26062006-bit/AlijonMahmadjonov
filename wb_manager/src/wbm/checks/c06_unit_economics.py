"""6. Товары, которые продаются в минус (юнит-экономика).

Прибыль по товару за период =
  к перечислению за продажи − к перечислению за возвраты
  − логистика − хранение − штрафы − удержания − платная приёмка
  − себестоимость × (продано − возвращено).
«К перечислению» уже очищено от комиссии WB.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from wbm.checks.base import (
    AffectedProduct,
    Check,
    CheckOutcome,
    Finding,
    ProductNames,
    in_range,
    money,
    percent,
    period_bounds,
    plural,
    register,
    top_products,
)
from wbm.checks.thresholds import Thresholds
from wbm.domain.data import DataBundle, Dataset, FinanceKind
from wbm.domain.enums import CheckStatus, Severity

_EXPENSES = ("logistics", "storage", "penalty", "deduction", "acceptance")
_EXPENSE_TITLES = {
    "logistics": "логистика_руб",
    "storage": "хранение_руб",
    "penalty": "штрафы_руб",
    "deduction": "удержания_руб",
    "acceptance": "приемка_руб",
}


@dataclass(slots=True)
class _Totals:
    vendor_code: str | None = None
    units: int = 0
    retail: Decimal = Decimal(0)
    payout: Decimal = Decimal(0)
    expenses: dict[str, Decimal] = field(
        default_factory=lambda: dict.fromkeys(_EXPENSES, Decimal(0))
    )


@register
class UnitEconomicsCheck(Check):
    id = "unit_economics"
    title = "Товары, которые продаются в минус"
    requires = (Dataset.FINANCE, Dataset.COST_PRICES)
    optional = (Dataset.PRODUCTS,)

    def run(self, data: DataBundle, thresholds: Thresholds) -> CheckOutcome:
        t = thresholds.unit_economics
        bounds = period_bounds(data)
        totals: defaultdict[int, _Totals] = defaultdict(_Totals)
        for row in data.finance.rows:
            if row.nm_id is None or not in_range(row.created_at, bounds):
                continue
            item = totals[row.nm_id]
            item.vendor_code = item.vendor_code or row.vendor_code
            if row.kind is FinanceKind.SALE:
                item.units += row.quantity
                item.retail += row.retail_amount
                item.payout += row.seller_payout
            elif row.kind is FinanceKind.RETURN:
                item.units -= row.quantity
                item.retail -= row.retail_amount
                item.payout -= row.seller_payout
            for name in _EXPENSES:
                item.expenses[name] += getattr(row, name)

        names = ProductNames(data)
        considered = 0
        losing: list[AffectedProduct] = []
        thin: list[AffectedProduct] = []
        without_cost: list[str] = []
        for nm_id, item in totals.items():
            if item.units < t.min_units:
                continue
            considered += 1
            cost = data.cost_for(item.vendor_code)
            if cost is None:
                without_cost.append(item.vendor_code or str(nm_id))
                continue
            expenses = sum(item.expenses.values(), Decimal(0))
            cost_total = cost * item.units
            profit = item.payout - expenses - cost_total
            margin = float(profit / item.retail) if item.retail > 0 else 0.0
            metrics: dict[str, int | float | str] = {
                "продано_шт": item.units,
                "выручка_руб": money(item.retail),
                "к_перечислению_руб": money(item.payout),
                **{_EXPENSE_TITLES[k]: money(v) for k, v in item.expenses.items() if v},
                "себестоимость_руб": money(cost_total),
                "прибыль_руб": money(profit),
                "прибыль_на_штуку_руб": money(profit / item.units),
                "маржа_процентов": percent(margin),
            }
            product = names.product(nm_id, item.vendor_code, metrics)
            if profit < 0:
                losing.append(product)
            elif margin < t.low_margin:
                thin.append(product)

        if considered and len(without_cost) == considered:
            return self._needs_cost(without_cost)

        findings: list[Finding] = []
        if losing:
            loss = sum(float(p.metrics["прибыль_руб"]) for p in losing)
            findings.append(
                Finding(
                    severity=Severity.CRITICAL,
                    title=f"Продаются в минус: {plural(len(losing), 'товар', 'товара', 'товаров')}",
                    facts={"товаров": len(losing), "убыток_за_период_руб": money(loss)},
                    reason=(
                        "После комиссии WB, логистики, хранения, штрафов и себестоимости "
                        "по этим товарам за период получился убыток."
                    ),
                    recommendation=(
                        "Пересчитайте цену и скидку, проверьте логистику (габариты, склад) "
                        "и закупочную цену. Если не выходит в плюс — выводите товар."
                    ),
                    products=top_products(losing, key=lambda p: float(p.metrics["прибыль_руб"])),
                )
            )
        if thin:
            findings.append(
                Finding(
                    severity=Severity.ADVICE,
                    title=f"Маржа ниже {percent(t.low_margin):g}%: {plural(len(thin), 'товар', 'товара', 'товаров')}",
                    facts={"товаров": len(thin), "порог_маржи_процентов": percent(t.low_margin)},
                    reason="Товар продаётся почти в ноль: любая скидка или рост логистики уведёт в минус.",
                    recommendation="Проверьте, можно ли поднять цену или снизить расходы.",
                    products=top_products(thin, key=lambda p: float(p.metrics["маржа_процентов"])),
                )
            )
        message = None
        if without_cost:
            message = (
                f"Нет себестоимости для {plural(len(without_cost), 'артикула', 'артикулов', 'артикулов')}: "
                + ", ".join(sorted(without_cost)[:10])
                + (" и др." if len(without_cost) > 10 else "")
            )
        return self.outcome(findings, message)

    def _needs_cost(self, vendor_codes: list[str]) -> CheckOutcome:
        return CheckOutcome(
            self.id,
            self.title,
            CheckStatus.NEEDS_COST,
            (),
            "Нужна себестоимость: загрузите файл «артикул; себестоимость» "
            f"(не найдено ни для одного из {len(vendor_codes)} проданных артикулов).",
        )
