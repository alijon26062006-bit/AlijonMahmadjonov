"""Данные магазина в формате, с которым работают проверки.

Это НЕ поля ответов WB. Сборщики данных (collectors) переводят ответы WB в эти
структуры — каждый перевод добавляется только после сверки с документацией.
Так проверки не зависят от того, как WB назовёт поле завтра.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from wbm.domain.enums import DatasetStatus


class Dataset(StrEnum):
    PRODUCTS = "products"
    CARD_ERRORS = "card_errors"
    PRICES = "prices"
    STOCKS = "stocks"
    PREVIOUS_STOCKS = "previous_stocks"
    ORDERS = "orders"
    SALES = "sales"
    FEEDBACKS = "feedbacks"
    QUESTIONS = "questions"
    CAMPAIGNS = "campaigns"
    CAMPAIGN_STATS = "campaign_stats"
    FINANCE = "finance"
    PAID_STORAGE = "paid_storage"
    SUPPLIES = "supplies"
    COST_PRICES = "cost_prices"


DATASET_TITLES: dict[Dataset, str] = {
    Dataset.PRODUCTS: "карточки товаров",
    Dataset.CARD_ERRORS: "ошибки карточек",
    Dataset.PRICES: "цены и скидки",
    Dataset.STOCKS: "остатки",
    Dataset.PREVIOUS_STOCKS: "остатки на момент прошлого анализа",
    Dataset.ORDERS: "заказы",
    Dataset.SALES: "продажи и возвраты",
    Dataset.FEEDBACKS: "отзывы",
    Dataset.QUESTIONS: "вопросы покупателей",
    Dataset.CAMPAIGNS: "рекламные кампании",
    Dataset.CAMPAIGN_STATS: "статистика рекламы",
    Dataset.FINANCE: "финансовый отчёт",
    Dataset.PAID_STORAGE: "платное хранение",
    Dataset.SUPPLIES: "поставки",
    Dataset.COST_PRICES: "себестоимость",
}


# ── записи ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Characteristic:
    name: str
    value: str | None
    required: bool = False


@dataclass(frozen=True, slots=True)
class Product:
    nm_id: int
    vendor_code: str
    title: str | None = None
    subject: str | None = None
    brand: str | None = None
    description: str | None = None
    photos: int = 0
    characteristics: tuple[Characteristic, ...] = ()


@dataclass(frozen=True, slots=True)
class CardError:
    vendor_code: str
    errors: tuple[str, ...]
    nm_id: int | None = None


@dataclass(frozen=True, slots=True)
class Price:
    nm_id: int
    vendor_code: str
    price: Decimal
    discount_percent: int = 0


@dataclass(frozen=True, slots=True)
class StockItem:
    nm_id: int
    vendor_code: str
    warehouse: str
    quantity: int
    """Доступно для продажи."""


@dataclass(frozen=True, slots=True)
class Order:
    order_id: str
    created_at: datetime
    nm_id: int
    vendor_code: str
    price: Decimal
    """Цена для покупателя."""
    is_cancelled: bool = False


@dataclass(frozen=True, slots=True)
class Sale:
    sale_id: str
    created_at: datetime
    nm_id: int
    vendor_code: str
    amount: Decimal
    is_return: bool = False


@dataclass(frozen=True, slots=True)
class Feedback:
    feedback_id: str
    created_at: datetime
    nm_id: int
    vendor_code: str
    rating: int
    text: str = ""
    pros: str = ""
    cons: str = ""
    answered: bool = False

    @property
    def full_text(self) -> str:
        return " ".join(part for part in (self.text, self.pros, self.cons) if part)


@dataclass(frozen=True, slots=True)
class Question:
    question_id: str
    created_at: datetime
    nm_id: int
    vendor_code: str
    text: str = ""
    answered: bool = False


@dataclass(frozen=True, slots=True)
class Campaign:
    campaign_id: int
    name: str
    status: str = ""


@dataclass(frozen=True, slots=True)
class CampaignStat:
    campaign_id: int
    day: datetime
    spend: Decimal
    views: int = 0
    clicks: int = 0
    orders: int = 0
    orders_sum: Decimal = Decimal(0)


class FinanceKind(StrEnum):
    SALE = "sale"
    RETURN = "return"
    LOGISTICS = "logistics"
    STORAGE = "storage"
    PENALTY = "penalty"
    DEDUCTION = "deduction"
    ACCEPTANCE = "acceptance"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class FinanceRow:
    """Строка финансового отчёта. Суммы — в рублях, со знаком «как для продавца»."""

    created_at: datetime
    kind: FinanceKind
    nm_id: int | None = None
    vendor_code: str | None = None
    quantity: int = 0
    retail_amount: Decimal = Decimal(0)
    """Цена продажи покупателю."""
    seller_payout: Decimal = Decimal(0)
    """К перечислению продавцу (уже за вычетом комиссии WB)."""
    logistics: Decimal = Decimal(0)
    storage: Decimal = Decimal(0)
    penalty: Decimal = Decimal(0)
    deduction: Decimal = Decimal(0)
    acceptance: Decimal = Decimal(0)
    comment: str = ""


@dataclass(frozen=True, slots=True)
class StorageCost:
    day: datetime
    nm_id: int
    vendor_code: str
    cost: Decimal


@dataclass(frozen=True, slots=True)
class SupplyItem:
    supply_id: str
    nm_id: int
    vendor_code: str
    planned: int
    accepted: int
    accepted_at: datetime | None = None


# ── набор данных анализа ──────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class DataResult[T]:
    """Набор данных и то, как он загрузился."""

    status: DatasetStatus
    rows: tuple[T, ...] = ()
    message: str | None = None

    @classmethod
    def ok(cls, rows: Iterable[T]) -> DataResult[T]:
        items = tuple(rows)
        return cls(DatasetStatus.OK if items else DatasetStatus.EMPTY, items)

    @classmethod
    def error(cls, message: str) -> DataResult[T]:
        return cls(DatasetStatus.ERROR, (), message)

    @classmethod
    def skipped(cls, message: str) -> DataResult[T]:
        return cls(DatasetStatus.SKIPPED, (), message)

    @property
    def usable(self) -> bool:
        """Данные есть (возможно, пустые или с аномалией) — на них можно строить выводы."""
        return self.status in (DatasetStatus.OK, DatasetStatus.EMPTY, DatasetStatus.ANOMALY)


def _not_loaded() -> DataResult[Any]:
    return DataResult(DatasetStatus.SKIPPED, (), "данные не загружались")


@dataclass(slots=True)
class DataBundle:
    """Всё, что собрано для одного анализа. Отсутствующий набор = «не загружался»."""

    now: datetime
    period_days: int = 30
    products: DataResult[Product] = field(default_factory=_not_loaded)
    card_errors: DataResult[CardError] = field(default_factory=_not_loaded)
    prices: DataResult[Price] = field(default_factory=_not_loaded)
    stocks: DataResult[StockItem] = field(default_factory=_not_loaded)
    previous_stocks: DataResult[StockItem] = field(default_factory=_not_loaded)
    previous_stocks_at: datetime | None = None
    orders: DataResult[Order] = field(default_factory=_not_loaded)
    sales: DataResult[Sale] = field(default_factory=_not_loaded)
    feedbacks: DataResult[Feedback] = field(default_factory=_not_loaded)
    questions: DataResult[Question] = field(default_factory=_not_loaded)
    campaigns: DataResult[Campaign] = field(default_factory=_not_loaded)
    campaign_stats: DataResult[CampaignStat] = field(default_factory=_not_loaded)
    finance: DataResult[FinanceRow] = field(default_factory=_not_loaded)
    paid_storage: DataResult[StorageCost] = field(default_factory=_not_loaded)
    supplies: DataResult[SupplyItem] = field(default_factory=_not_loaded)
    cost_prices: dict[str, Decimal] = field(default_factory=dict)
    """Себестоимость по артикулу продавца (ключ — артикул в нижнем регистре)."""

    def result(self, dataset: Dataset) -> DataResult[object]:
        if dataset is Dataset.COST_PRICES:
            if self.cost_prices:
                return DataResult(DatasetStatus.OK, ())
            return DataResult(DatasetStatus.SKIPPED, (), "себестоимость не загружена")
        value: DataResult[object] = getattr(self, dataset.value)
        return value

    def set_result(self, dataset: Dataset, result: DataResult[object]) -> None:
        if dataset is Dataset.COST_PRICES:
            raise ValueError("Себестоимость задаётся через cost_prices")
        setattr(self, dataset.value, result)

    def cost_for(self, vendor_code: str | None) -> Decimal | None:
        if not vendor_code:
            return None
        return self.cost_prices.get(normalize_vendor_code(vendor_code))


def normalize_vendor_code(vendor_code: str) -> str:
    return vendor_code.strip().lower()
