from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Tariff(Base, TimestampMixin):
    """Тариф доставки. Все параметры редактируются из админ-панели."""

    __tablename__ = "tariffs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    delivery_type_id: Mapped[int] = mapped_column(ForeignKey("delivery_types.id"))
    # NULL = тариф применяется к любой категории, если нет более точного
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    price_per_kg: Mapped[float] = mapped_column(Numeric(14, 4))
    min_order_cost: Mapped[float] = mapped_column(Numeric(14, 4), default=0)
    min_weight: Mapped[float] = mapped_column(Numeric(14, 4), default=0)
    currency_code: Mapped[str] = mapped_column(String(8), default="USD")
    delivery_time: Mapped[str | None] = mapped_column(String(128))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def __str__(self) -> str:
        return f"{self.name} — {self.price_per_kg} {self.currency_code}/кг"


class Coefficient(Base):
    """Коэффициенты расчёта.

    code:
      volumetric — кг на 1 м³ для расчёта объёмного веса (привязка к типу доставки);
      density    — множитель цены для плотного/особого груза (привязка к категории);
      любой другой код — произвольный множитель итоговой базовой стоимости.
    """

    __tablename__ = "coefficients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    code: Mapped[str] = mapped_column(String(32), default="volumetric")
    delivery_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("delivery_types.id"), nullable=True
    )
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    value: Mapped[float] = mapped_column(Numeric(14, 4))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def __str__(self) -> str:
        return f"{self.name} [{self.code}] = {self.value}"


class ExtraService(Base):
    """Дополнительные сборы, скидки и наценки.

    kind: fee (сбор) | discount (скидка) | markup (наценка)
    calc_type: percent (% от базовой стоимости) | fixed (фикс. сумма в валюте тарифа) | per_kg
    Привязка к типу доставки/категории опциональна (NULL = применяется всегда).
    """

    __tablename__ = "extra_services"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    kind: Mapped[str] = mapped_column(String(16), default="fee")
    calc_type: Mapped[str] = mapped_column(String(16), default="fixed")
    value: Mapped[float] = mapped_column(Numeric(14, 4))
    delivery_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("delivery_types.id"), nullable=True
    )
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def __str__(self) -> str:
        sign = {"fee": "+", "markup": "+", "discount": "-"}.get(self.kind, "+")
        unit = {"percent": "%", "fixed": "", "per_kg": "/кг"}.get(self.calc_type, "")
        return f"{self.name} ({sign}{self.value}{unit})"
