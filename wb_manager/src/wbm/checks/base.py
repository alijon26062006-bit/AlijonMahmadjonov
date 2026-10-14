"""Основа проверок: формат результата, реестр, общие помощники.

Каждая проверка — детерминированный код: на одних и тех же данных и порогах
всегда один и тот же результат. Цифры в фактах берутся только из данных.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import ClassVar

from wbm.checks.thresholds import Thresholds
from wbm.domain.data import DataBundle, Dataset, Product
from wbm.domain.enums import CheckStatus, Severity

Number = int | float
FactValue = int | float | str

MAX_PRODUCTS_PER_FINDING = 50


@dataclass(frozen=True, slots=True)
class AffectedProduct:
    nm_id: int | None
    vendor_code: str | None
    name: str | None = None
    metrics: Mapping[str, FactValue] = field(default_factory=dict)
    """Цифры по товару: остаток, заказы в день и т. п. — только из данных."""

    def as_dict(self) -> dict[str, object]:
        return {
            "nm_id": self.nm_id,
            "vendor_code": self.vendor_code,
            "name": self.name,
            "metrics": dict(self.metrics),
        }


@dataclass(frozen=True, slots=True)
class Finding:
    severity: Severity
    title: str
    facts: Mapping[str, FactValue]
    reason: str
    recommendation: str
    products: tuple[AffectedProduct, ...] = ()
    caveat: str | None = None


@dataclass(frozen=True, slots=True)
class CheckOutcome:
    check_id: str
    title: str
    status: CheckStatus
    findings: tuple[Finding, ...] = ()
    message: str | None = None


class Check(ABC):
    id: ClassVar[str]
    title: ClassVar[str]
    requires: ClassVar[tuple[Dataset, ...]]
    """Без этих данных проверка не выполняется («нет данных»)."""
    optional: ClassVar[tuple[Dataset, ...]] = ()
    """Улучшают выводы, но без них проверка всё равно работает."""

    @abstractmethod
    def run(self, data: DataBundle, thresholds: Thresholds) -> CheckOutcome: ...

    def outcome(self, findings: Iterable[Finding], message: str | None = None) -> CheckOutcome:
        items = tuple(sorted(findings, key=lambda f: SEVERITY_ORDER[f.severity]))
        status = CheckStatus.PROBLEMS if items else CheckStatus.OK
        return CheckOutcome(self.id, self.title, status, items, message)


SEVERITY_ORDER = {Severity.CRITICAL: 0, Severity.IMPORTANT: 1, Severity.ADVICE: 2}

REGISTRY: list[type[Check]] = []


def register[C: type[Check]](check_class: C) -> C:
    if any(existing.id == check_class.id for existing in REGISTRY):
        raise RuntimeError(f"Проверка {check_class.id} зарегистрирована дважды")
    REGISTRY.append(check_class)
    return check_class


# ── помощники ─────────────────────────────────────────────────────────────────


def money(value: Decimal | Number) -> float:
    """Рубли с копейками для фактов отчёта."""
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def ratio(value: float) -> float:
    """Доля с точностью до 0,1 % — например, 0.347 → 0.347."""
    return round(value, 3)


def percent(value: float) -> float:
    """Доля → проценты с одним знаком: 0.347 → 34.7."""
    return round(value * 100, 1)


def period_bounds(data: DataBundle, days: int | None = None) -> tuple[datetime, datetime]:
    span = timedelta(days=days if days is not None else data.period_days)
    return data.now - span, data.now


def previous_period_bounds(data: DataBundle) -> tuple[datetime, datetime]:
    span = timedelta(days=data.period_days)
    return data.now - 2 * span, data.now - span


def in_range(moment: datetime, bounds: tuple[datetime, datetime]) -> bool:
    start, end = bounds
    return start <= moment < end


class ProductNames:
    """Названия и артикулы товаров для отчёта (если карточки загрузились)."""

    def __init__(self, data: DataBundle) -> None:
        self._by_nm: dict[int, Product] = (
            {p.nm_id: p for p in data.products.rows} if data.products.usable else {}
        )

    def product(
        self,
        nm_id: int | None,
        vendor_code: str | None = None,
        metrics: Mapping[str, FactValue] | None = None,
    ) -> AffectedProduct:
        card = self._by_nm.get(nm_id) if nm_id is not None else None
        return AffectedProduct(
            nm_id=nm_id,
            vendor_code=vendor_code or (card.vendor_code if card else None),
            name=card.title if card else None,
            metrics=dict(metrics or {}),
        )


def top_products(
    products: Iterable[AffectedProduct],
    key: Callable[[AffectedProduct], float] | Callable[[AffectedProduct], str],
    *,
    reverse: bool = False,
) -> tuple[AffectedProduct, ...]:
    ordered = sorted(products, key=key, reverse=reverse)
    return tuple(ordered[:MAX_PRODUCTS_PER_FINDING])


def plural(count: int, one: str, few: str, many: str) -> str:
    """plural(5, "товар", "товара", "товаров") → «5 товаров»."""
    tail = count % 100
    if 11 <= tail <= 14:
        word = many
    elif count % 10 == 1:
        word = one
    elif 2 <= count % 10 <= 4:
        word = few
    else:
        word = many
    return f"{count} {word}"
