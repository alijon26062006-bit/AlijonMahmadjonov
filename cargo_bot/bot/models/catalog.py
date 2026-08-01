from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class DeliveryType(Base):
    """Тип доставки: Авиа, Авто, Море, ЖД и т.д."""

    __tablename__ = "delivery_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    emoji: Mapped[str | None] = mapped_column(String(16))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    def __str__(self) -> str:
        return f"{self.emoji or ''} {self.name}".strip()


class Category(Base):
    """Категория товара: Одежда, Обувь, Электроника и т.д."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    def __str__(self) -> str:
        return self.name


class Currency(Base):
    """Валюта расчёта."""

    __tablename__ = "currencies"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(8), unique=True)
    name: Mapped[str] = mapped_column(String(64))
    symbol: Mapped[str | None] = mapped_column(String(8))
    is_base: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"


class ExchangeRate(Base):
    """Курс валюты к базовой (TJS). 1 <валюта> = rate TJS."""

    __tablename__ = "exchange_rates"

    id: Mapped[int] = mapped_column(primary_key=True)
    currency_id: Mapped[int] = mapped_column(ForeignKey("currencies.id"))
    rate: Mapped[float] = mapped_column(Numeric(14, 4))
    updated_by: Mapped[int | None] = mapped_column(BigInteger)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    def __str__(self) -> str:
        return f"currency_id={self.currency_id}: {self.rate}"
