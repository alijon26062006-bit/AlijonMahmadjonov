"""Пороги проверок. Значения по умолчанию — разумный старт; продавец сможет их менять."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class _Section(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StockOutThresholds(_Section):
    velocity_days: int = Field(14, ge=1, le=90)
    """За сколько последних дней считаем скорость заказов."""
    critical_days: float = Field(7, gt=0)
    warning_days: float = Field(14, gt=0)
    min_daily_orders: float = Field(0.2, ge=0)
    """Медленнее — товар не считаем «быстро заканчивающимся»."""


class OrdersDropThresholds(_Section):
    min_previous_orders: int = Field(10, ge=1)
    important_drop: float = Field(0.3, gt=0, lt=1)
    critical_drop: float = Field(0.5, gt=0, le=1)


class UnansweredThresholds(_Section):
    negative_max_rating: int = Field(3, ge=1, le=5)
    min_age_hours: float = Field(0, ge=0)
    """Не считать «без ответа» совсем свежие отзывы и вопросы."""


class ComplaintsThresholds(_Section):
    min_mentions: int = Field(3, ge=1)
    min_share: float = Field(0.15, gt=0, le=1)
    """Доля отзывов товара за период, где встречается тема."""
    critical_share: float = Field(0.3, gt=0, le=1)


class ReturnsThresholds(_Section):
    min_orders: int = Field(10, ge=1)
    min_sales: int = Field(10, ge=1)
    cancel_rate: float = Field(0.3, gt=0, le=1)
    return_rate: float = Field(0.3, gt=0, le=1)
    critical_multiplier: float = Field(1.67, ge=1)
    """Во сколько раз выше порога — уже «критично» (0,3 × 1,67 ≈ 0,5)."""
    shop_average_multiplier: float = Field(1.5, ge=1)


class UnitEconomicsThresholds(_Section):
    low_margin: float = Field(0.05, ge=0, lt=1)
    min_units: int = Field(1, ge=1)


class AdsThresholds(_Section):
    min_spend_without_orders: Decimal = Field(Decimal(1000), ge=0)
    drr_important: float = Field(0.2, gt=0)
    drr_critical: float = Field(0.35, gt=0)
    min_spend_for_drr: Decimal = Field(Decimal(500), ge=0)


class StaleStockThresholds(_Section):
    no_orders_days: int = Field(30, ge=7)
    min_units: int = Field(1, ge=1)
    min_storage_cost: Decimal = Field(Decimal(300), ge=0)
    """Стоимость хранения за период, начиная с которой залежавшийся товар — «важно»."""


class CardQualityThresholds(_Section):
    min_description_length: int = Field(500, ge=0)
    min_photos: int = Field(3, ge=0)
    empty_characteristics_share: float = Field(0.3, gt=0, le=1)


class DeductionsThresholds(_Section):
    logistics_multiplier: float = Field(2.0, gt=1)
    """Логистика на единицу выше медианы магазина во столько раз — подозрительно."""
    min_logistics_rub: Decimal = Field(Decimal(100), ge=0)
    min_missing_units: int = Field(3, ge=1)


class Thresholds(_Section):
    stock_out: StockOutThresholds = StockOutThresholds()
    orders_drop: OrdersDropThresholds = OrdersDropThresholds()
    unanswered: UnansweredThresholds = UnansweredThresholds()
    complaints: ComplaintsThresholds = ComplaintsThresholds()
    returns: ReturnsThresholds = ReturnsThresholds()
    unit_economics: UnitEconomicsThresholds = UnitEconomicsThresholds()
    ads: AdsThresholds = AdsThresholds()
    stale_stock: StaleStockThresholds = StaleStockThresholds()
    card_quality: CardQualityThresholds = CardQualityThresholds()
    deductions: DeductionsThresholds = DeductionsThresholds()
