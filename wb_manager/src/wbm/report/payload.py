"""Готовые результаты проверок → компактный JSON для Claude и для шаблонов.

В Claude уходят только агрегаты и названия товаров: ни текстов отзывов,
ни данных покупателей, ни токенов.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from wbm.checks.base import CheckOutcome, Finding
from wbm.domain.enums import SEVERITY_TITLES, CheckStatus

MAX_PRODUCTS_FOR_TEXT = 5
"""Сколько товаров на проблему показываем Claude — остальные видны в таблице отчёта."""


@dataclass(frozen=True, slots=True)
class FindingRef:
    check_index: int
    finding_index: int

    @property
    def key(self) -> str:
        return f"c{self.check_index}f{self.finding_index}"


def iter_findings(outcomes: Sequence[CheckOutcome]) -> list[tuple[FindingRef, Finding]]:
    return [
        (FindingRef(ci, fi), finding)
        for ci, outcome in enumerate(outcomes)
        for fi, finding in enumerate(outcome.findings)
    ]


def finding_payload(ref: FindingRef, finding: Finding) -> dict[str, object]:
    products = [
        {
            "товар": p.name or p.vendor_code or p.nm_id,
            "артикул": p.vendor_code,
            "nm_id": p.nm_id,
            **dict(p.metrics),
        }
        for p in finding.products[:MAX_PRODUCTS_FOR_TEXT]
    ]
    payload: dict[str, object] = {
        "key": ref.key,
        "важность": SEVERITY_TITLES[finding.severity],
        "заголовок": finding.title,
        "факты": dict(finding.facts),
        "причина": finding.reason,
        "рекомендация": finding.recommendation,
    }
    if products:
        payload["товары"] = products
        payload["товаров_в_списке_всего"] = len(finding.products)
    if finding.caveat:
        payload["оговорка"] = finding.caveat
    return payload


def build_payload(
    outcomes: Sequence[CheckOutcome], *, shop_name: str, period_days: int
) -> dict[str, object]:
    return {
        "магазин": shop_name,
        "период_дней": period_days,
        "проблемы": [finding_payload(ref, f) for ref, f in iter_findings(outcomes)],
        "проверки_без_данных": [
            {"проверка": o.title, "причина": o.message}
            for o in outcomes
            if o.status in (CheckStatus.NO_DATA, CheckStatus.NEEDS_COST, CheckStatus.ERROR)
        ],
    }
