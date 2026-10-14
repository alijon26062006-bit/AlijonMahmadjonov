"""7. Реклама с высоким ДРР или расходами без заказов.

ДРР (доля рекламных расходов) = расход на рекламу / сумма заказов с рекламы.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from wbm.checks.base import (
    Check,
    CheckOutcome,
    Finding,
    in_range,
    money,
    percent,
    period_bounds,
    plural,
    register,
)
from wbm.checks.thresholds import Thresholds
from wbm.domain.data import DataBundle, Dataset
from wbm.domain.enums import Severity


@dataclass(slots=True)
class _Stats:
    spend: Decimal = Decimal(0)
    orders: int = 0
    orders_sum: Decimal = Decimal(0)
    clicks: int = 0
    views: int = 0


@register
class AdsCheck(Check):
    id = "ads"
    title = "Неэффективная реклама"
    requires = (Dataset.CAMPAIGN_STATS,)
    optional = (Dataset.CAMPAIGNS,)

    def run(self, data: DataBundle, thresholds: Thresholds) -> CheckOutcome:
        t = thresholds.ads
        bounds = period_bounds(data)
        stats: defaultdict[int, _Stats] = defaultdict(_Stats)
        for row in data.campaign_stats.rows:
            if not in_range(row.day, bounds):
                continue
            item = stats[row.campaign_id]
            item.spend += row.spend
            item.orders += row.orders
            item.orders_sum += row.orders_sum
            item.clicks += row.clicks
            item.views += row.views
        titles = (
            {c.campaign_id: c.name for c in data.campaigns.rows} if data.campaigns.usable else {}
        )

        no_orders: list[tuple[int, _Stats]] = []
        drr_critical: list[tuple[int, _Stats, float]] = []
        drr_high: list[tuple[int, _Stats, float]] = []
        for campaign_id, item in stats.items():
            if item.orders == 0 or item.orders_sum <= 0:
                if item.spend >= t.min_spend_without_orders:
                    no_orders.append((campaign_id, item))
                continue
            if item.spend < t.min_spend_for_drr:
                continue
            drr = float(item.spend / item.orders_sum)
            if drr >= t.drr_critical:
                drr_critical.append((campaign_id, item, drr))
            elif drr >= t.drr_important:
                drr_high.append((campaign_id, item, drr))

        def campaign_facts(campaign_id: int, item: _Stats) -> dict[str, int | float | str]:
            return {
                "кампания": titles.get(campaign_id, f"№{campaign_id}"),
                "id_кампании": campaign_id,
                "расход_руб": money(item.spend),
                "заказов": item.orders,
                "сумма_заказов_руб": money(item.orders_sum),
                "кликов": item.clicks,
            }

        findings: list[Finding] = []
        if no_orders:
            spend = sum((item.spend for _, item in no_orders), Decimal(0))
            findings.append(
                Finding(
                    severity=Severity.CRITICAL,
                    title=f"Реклама тратит деньги без заказов: {plural(len(no_orders), 'кампания', 'кампании', 'кампаний')}",
                    facts={
                        "кампаний": len(no_orders),
                        "расход_без_заказов_руб": money(spend),
                        "кампании": "; ".join(
                            f"{titles.get(cid, f'№{cid}')}: {money(item.spend):g} ₽"
                            for cid, item in sorted(no_orders, key=lambda x: -x[1].spend)[:10]
                        ),
                    },
                    reason=f"За {data.period_days} дней эти кампании потратили деньги, а заказов с них нет.",
                    recommendation=(
                        "Приостановите кампании или смените ставки, ключевые фразы и товар в рекламе. "
                        "Проверьте, есть ли товар в наличии."
                    ),
                )
            )
        for severity, items, limit in (
            (Severity.CRITICAL, drr_critical, t.drr_critical),
            (Severity.IMPORTANT, drr_high, t.drr_important),
        ):
            for campaign_id, item, drr in sorted(items, key=lambda x: -x[2]):
                facts = campaign_facts(campaign_id, item)
                facts["дрр_процентов"] = percent(drr)
                facts["порог_дрр_процентов"] = percent(limit)
                findings.append(
                    Finding(
                        severity=severity,
                        title=f"Высокий ДРР {percent(drr):g}% в кампании «{facts['кампания']}»",
                        facts=facts,
                        reason="Реклама съедает большую долю выручки от заказов, которые она приносит.",
                        recommendation=(
                            "Снизьте ставки, отключите неэффективные фразы, проверьте цену и "
                            "карточку — слабая карточка дорого обходится в рекламе."
                        ),
                    )
                )
        return self.outcome(findings)
