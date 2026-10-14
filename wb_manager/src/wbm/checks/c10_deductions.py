"""10. Подозрительные удержания: штрафы, завышенная логистика, расхождения при приёмке,
товар пропал из остатков без продажи."""

from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal
from statistics import median

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
from wbm.domain.data import DataBundle, Dataset, FinanceKind
from wbm.domain.enums import Severity

_MIN_DELIVERIES_FOR_MEDIAN = 3


@register
class DeductionsCheck(Check):
    id = "deductions"
    title = "Подозрительные удержания"
    requires = (Dataset.FINANCE,)
    optional = (
        Dataset.SUPPLIES,
        Dataset.STOCKS,
        Dataset.PREVIOUS_STOCKS,
        Dataset.ORDERS,
        Dataset.PRODUCTS,
    )

    def run(self, data: DataBundle, thresholds: Thresholds) -> CheckOutcome:
        names = ProductNames(data)
        findings: list[Finding] = []
        notes: list[str] = []
        findings += self._penalties_and_deductions(data)
        findings += self._logistics(data, thresholds, names)
        if data.supplies.usable:
            findings += self._acceptance(data, names)
        else:
            notes.append("поставки не загрузились — расхождения при приёмке не проверены")
        if self._can_compare_stock(data):
            missing = self._missing_stock(data, thresholds, names)
            if missing is not None:
                findings.append(missing)
        else:
            notes.append(
                "нет остатков прошлого анализа — пропажа товара будет проверяться со второго анализа"
            )
        message = ("Не проверено: " + "; ".join(notes) + ".") if notes else None
        return self.outcome(findings, message)

    @staticmethod
    def _penalties_and_deductions(data: DataBundle) -> list[Finding]:
        bounds = period_bounds(data)
        penalties: Counter[str] = Counter()
        penalty_sum = Decimal(0)
        deductions: Counter[str] = Counter()
        deduction_sum = Decimal(0)
        for row in data.finance.rows:
            if not in_range(row.created_at, bounds):
                continue
            if row.penalty > 0 or row.kind is FinanceKind.PENALTY:
                penalty_sum += row.penalty
                penalties[row.comment or "без описания"] += 1
            if row.deduction > 0 or row.kind is FinanceKind.DEDUCTION:
                deduction_sum += row.deduction
                deductions[row.comment or "без описания"] += 1

        findings: list[Finding] = []
        if penalty_sum > 0:
            findings.append(
                Finding(
                    severity=Severity.IMPORTANT,
                    title=f"Штрафы WB за период: {money(penalty_sum):g} ₽",
                    facts={
                        "сумма_штрафов_руб": money(penalty_sum),
                        "штрафов": sum(penalties.values()),
                        "причины": "; ".join(f"{k} — {v}" for k, v in penalties.most_common(5)),
                    },
                    reason="WB удержал штрафы. Часть штрафов можно оспорить.",
                    recommendation=(
                        "Проверьте каждый штраф в личном кабинете; несогласные — оспорьте "
                        "через поддержку, приложив фото и документы."
                    ),
                )
            )
        if deduction_sum > 0:
            findings.append(
                Finding(
                    severity=Severity.ADVICE,
                    title=f"Прочие удержания за период: {money(deduction_sum):g} ₽",
                    facts={
                        "сумма_удержаний_руб": money(deduction_sum),
                        "удержаний": sum(deductions.values()),
                        "причины": "; ".join(f"{k} — {v}" for k, v in deductions.most_common(5)),
                    },
                    reason="Кроме комиссии и логистики WB удержал дополнительные суммы.",
                    recommendation="Сверьте удержания с отчётом в личном кабинете.",
                )
            )
        return findings

    @staticmethod
    def _logistics(data: DataBundle, thresholds: Thresholds, names: ProductNames) -> list[Finding]:
        t = thresholds.deductions
        bounds = period_bounds(data)
        total: defaultdict[int, Decimal] = defaultdict(Decimal)
        deliveries: Counter[int] = Counter()
        vendor: dict[int, str | None] = {}
        for row in data.finance.rows:
            if row.nm_id is None or row.logistics <= 0 or not in_range(row.created_at, bounds):
                continue
            total[row.nm_id] += row.logistics
            deliveries[row.nm_id] += max(1, row.quantity)
            vendor.setdefault(row.nm_id, row.vendor_code)

        per_unit = {
            nm: total[nm] / deliveries[nm]
            for nm in total
            if deliveries[nm] >= _MIN_DELIVERIES_FOR_MEDIAN
        }
        if len(per_unit) < _MIN_DELIVERIES_FOR_MEDIAN:
            return []
        shop_median = Decimal(str(median(per_unit.values())))
        limit = shop_median * Decimal(str(t.logistics_multiplier))
        expensive: list[AffectedProduct] = [
            names.product(
                nm,
                vendor.get(nm),
                {
                    "логистика_на_единицу_руб": money(cost),
                    "медиана_магазина_руб": money(shop_median),
                    "доставок": deliveries[nm],
                    "логистика_всего_руб": money(total[nm]),
                },
            )
            for nm, cost in per_unit.items()
            if cost >= limit and cost >= t.min_logistics_rub
        ]
        if not expensive:
            return []
        return [
            Finding(
                severity=Severity.IMPORTANT,
                title=f"Логистика заметно дороже обычной: {plural(len(expensive), 'товар', 'товара', 'товаров')}",
                facts={
                    "товаров": len(expensive),
                    "медиана_логистики_на_единицу_руб": money(shop_median),
                    "порог_раз_выше_медианы": t.logistics_multiplier,
                },
                reason=(
                    "Доставка единицы этих товаров стоит в разы дороже, чем в среднем по магазину. "
                    "Частая причина — завышенные габариты в карточке или дальний склад."
                ),
                recommendation=(
                    "Проверьте габариты и вес в карточке, коэффициент склада; при ошибке WB "
                    "запросите перерасчёт."
                ),
                products=top_products(
                    expensive,
                    key=lambda p: float(p.metrics["логистика_на_единицу_руб"]),
                    reverse=True,
                ),
            )
        ]

    @staticmethod
    def _acceptance(data: DataBundle, names: ProductNames) -> list[Finding]:
        bounds = period_bounds(data)
        short: list[AffectedProduct] = []
        for item in data.supplies.rows:
            if item.accepted_at is not None and not in_range(item.accepted_at, bounds):
                continue
            if item.accepted < item.planned:
                short.append(
                    names.product(
                        item.nm_id,
                        item.vendor_code,
                        {
                            "поставка": item.supply_id,
                            "отгружено_шт": item.planned,
                            "принято_шт": item.accepted,
                            "не_хватает_шт": item.planned - item.accepted,
                        },
                    )
                )
        if not short:
            return []
        missing_units = sum(int(p.metrics["не_хватает_шт"]) for p in short)
        return [
            Finding(
                severity=Severity.IMPORTANT,
                title=f"При приёмке принято меньше, чем отгружено: {missing_units} шт.",
                facts={"позиций": len(short), "не_хватает_шт": missing_units},
                reason="WB принял на склад меньше товара, чем указано в поставке.",
                recommendation=(
                    "Сверьте с документами отгрузки; при расхождении подайте претензию в WB "
                    "с актом и фото."
                ),
                products=top_products(
                    short, key=lambda p: float(p.metrics["не_хватает_шт"]), reverse=True
                ),
            )
        ]

    @staticmethod
    def _can_compare_stock(data: DataBundle) -> bool:
        return (
            data.previous_stocks_at is not None
            and data.previous_stocks.usable
            and data.stocks.usable
            and data.orders.usable
        )

    @staticmethod
    def _missing_stock(
        data: DataBundle, thresholds: Thresholds, names: ProductNames
    ) -> Finding | None:
        since = data.previous_stocks_at
        if since is None:  # уже проверено в _can_compare_stock
            return None
        t = thresholds.deductions
        before: Counter[int] = Counter()
        vendor: dict[int, str] = {}
        for item in data.previous_stocks.rows:
            before[item.nm_id] += item.quantity
            vendor.setdefault(item.nm_id, item.vendor_code)
        now: Counter[int] = Counter()
        for item in data.stocks.rows:
            now[item.nm_id] += item.quantity
        ordered: Counter[int] = Counter(
            o.nm_id for o in data.orders.rows if not o.is_cancelled and o.created_at >= since
        )
        supplied: Counter[int] = Counter()
        if data.supplies.usable:
            for s in data.supplies.rows:
                if s.accepted_at is not None and s.accepted_at >= since:
                    supplied[s.nm_id] += s.accepted

        missing: list[AffectedProduct] = []
        for nm_id, was in before.items():
            gone = was + supplied[nm_id] - ordered[nm_id] - now.get(nm_id, 0)
            if gone >= t.min_missing_units:
                missing.append(
                    names.product(
                        nm_id,
                        vendor.get(nm_id),
                        {
                            "было_шт": was,
                            "принято_с_поставками_шт": supplied[nm_id],
                            "заказано_шт": ordered[nm_id],
                            "стало_шт": now.get(nm_id, 0),
                            "не_объяснено_шт": gone,
                        },
                    )
                )
        if not missing:
            return None
        units = sum(int(p.metrics["не_объяснено_шт"]) for p in missing)
        return Finding(
            severity=Severity.IMPORTANT,
            title=f"Товар пропал из остатков без продажи: {units} шт.",
            facts={
                "товаров": len(missing),
                "не_объяснено_шт": units,
                "сравнение_с_датой": since.date().isoformat(),
            },
            reason=(
                "Остаток уменьшился сильнее, чем объясняют заказы и поставки "
                "с момента прошлого анализа."
            ),
            recommendation=(
                "Сверьте движение товара в отчётах WB; если товар утерян складом — "
                "запросите компенсацию через поддержку."
            ),
            products=top_products(
                missing, key=lambda p: float(p.metrics["не_объяснено_шт"]), reverse=True
            ),
            caveat=(
                "Оценка: часть разницы может быть в пути к покупателю или на возврате; "
                "учтены только заказы и принятые поставки."
            ),
        )
