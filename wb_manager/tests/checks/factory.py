"""Фиктивные данные магазина для тестов проверок."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from itertools import count

from wbm.checks.base import CheckOutcome, Finding
from wbm.domain.data import (
    CampaignStat,
    Characteristic,
    DataBundle,
    DataResult,
    Feedback,
    FinanceKind,
    FinanceRow,
    Order,
    Product,
    Question,
    Sale,
    StockItem,
    StorageCost,
    SupplyItem,
)
from wbm.domain.enums import Severity

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)
_ids = count(1)


def ago(days: float) -> datetime:
    return NOW - timedelta(days=days)


def vc(nm_id: int) -> str:
    return f"ART-{nm_id}"


def orders(
    nm_id: int, n: int, *, days_ago: float = 1, cancelled: int = 0, price: int = 1000
) -> list[Order]:
    """n заказов товара, равномерно за последние days_ago дней (первые `cancelled` — отменены)."""
    step = days_ago / max(n, 1)
    return [
        Order(
            order_id=str(next(_ids)),
            created_at=NOW - timedelta(days=step * (i + 0.5)),
            nm_id=nm_id,
            vendor_code=vc(nm_id),
            price=Decimal(price),
            is_cancelled=i < cancelled,
        )
        for i in range(n)
    ]


def orders_between(
    nm_id: int, n: int, *, start_days_ago: float, end_days_ago: float
) -> list[Order]:
    span = start_days_ago - end_days_ago
    return [
        Order(
            order_id=str(next(_ids)),
            created_at=NOW - timedelta(days=end_days_ago + span * (i + 0.5) / n),
            nm_id=nm_id,
            vendor_code=vc(nm_id),
            price=Decimal(1000),
        )
        for i in range(n)
    ]


def stock(nm_id: int, quantity: int, warehouse: str = "Коледино") -> StockItem:
    return StockItem(nm_id=nm_id, vendor_code=vc(nm_id), warehouse=warehouse, quantity=quantity)


def sales(nm_id: int, n: int, *, returns: int = 0, days_ago: float = 10) -> list[Sale]:
    return [
        Sale(
            sale_id=str(next(_ids)),
            created_at=ago(days_ago),
            nm_id=nm_id,
            vendor_code=vc(nm_id),
            amount=Decimal(1000),
            is_return=i < returns,
        )
        for i in range(n)
    ]


def feedback(
    nm_id: int,
    rating: int,
    text: str = "",
    *,
    answered: bool = False,
    days_ago: float = 2,
    cons: str = "",
) -> Feedback:
    return Feedback(
        feedback_id=str(next(_ids)),
        created_at=ago(days_ago),
        nm_id=nm_id,
        vendor_code=vc(nm_id),
        rating=rating,
        text=text,
        cons=cons,
        answered=answered,
    )


def question(nm_id: int, *, answered: bool = False, days_ago: float = 3) -> Question:
    return Question(
        question_id=str(next(_ids)),
        created_at=ago(days_ago),
        nm_id=nm_id,
        vendor_code=vc(nm_id),
        text="Какой размер брать?",
        answered=answered,
    )


def product(
    nm_id: int,
    *,
    title: str | None = None,
    description: str = "Описание " * 100,
    photos: int = 5,
    characteristics: Iterable[Characteristic] = (),
) -> Product:
    return Product(
        nm_id=nm_id,
        vendor_code=vc(nm_id),
        title=title or f"Товар {nm_id}",
        description=description,
        photos=photos,
        characteristics=tuple(characteristics),
    )


def finance(
    nm_id: int | None,
    kind: FinanceKind,
    *,
    days_ago: float = 5,
    quantity: int = 0,
    retail: int | str = 0,
    payout: int | str = 0,
    logistics: int | str = 0,
    storage: int | str = 0,
    penalty: int | str = 0,
    deduction: int | str = 0,
    comment: str = "",
) -> FinanceRow:
    return FinanceRow(
        created_at=ago(days_ago),
        kind=kind,
        nm_id=nm_id,
        vendor_code=vc(nm_id) if nm_id is not None else None,
        quantity=quantity,
        retail_amount=Decimal(retail),
        seller_payout=Decimal(payout),
        logistics=Decimal(logistics),
        storage=Decimal(storage),
        penalty=Decimal(penalty),
        deduction=Decimal(deduction),
        comment=comment,
    )


def ad_day(
    campaign_id: int, spend: int, *, orders: int = 0, orders_sum: int = 0, days_ago: float = 3
) -> CampaignStat:
    return CampaignStat(
        campaign_id=campaign_id,
        day=ago(days_ago),
        spend=Decimal(spend),
        orders=orders,
        orders_sum=Decimal(orders_sum),
        clicks=orders * 10,
        views=orders * 200,
    )


def storage_cost(nm_id: int, rub: int, *, days_ago: float = 5) -> StorageCost:
    return StorageCost(day=ago(days_ago), nm_id=nm_id, vendor_code=vc(nm_id), cost=Decimal(rub))


def supply(nm_id: int, planned: int, accepted: int, *, days_ago: float = 5) -> SupplyItem:
    return SupplyItem(
        supply_id=f"WB-GI-{next(_ids)}",
        nm_id=nm_id,
        vendor_code=vc(nm_id),
        planned=planned,
        accepted=accepted,
        accepted_at=ago(days_ago),
    )


def ok[T](rows: Iterable[T]) -> DataResult[T]:
    return DataResult.ok(rows)


def bundle(**datasets: object) -> DataBundle:
    """bundle(orders=[...], stocks=[...]) — списки превращаются в успешно загруженные данные."""
    data = DataBundle(now=NOW, period_days=30)
    for name, value in datasets.items():
        if isinstance(value, DataResult) or not isinstance(value, list | tuple):
            setattr(data, name, value)
        else:
            setattr(data, name, ok(value))
    return data


def only(outcome: CheckOutcome, severity: Severity) -> list[Finding]:
    return [f for f in outcome.findings if f.severity is severity]


def nm_ids(finding: Finding) -> list[int | None]:
    return [p.nm_id for p in finding.products]
