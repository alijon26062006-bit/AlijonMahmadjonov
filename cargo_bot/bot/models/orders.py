from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class Order(Base, TimestampMixin):
    """Заявка клиента."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(256))
    phone: Mapped[str] = mapped_column(String(64))
    product_url: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    weight: Mapped[float | None] = mapped_column(Numeric(14, 4))
    volume: Mapped[float | None] = mapped_column(Numeric(14, 6))
    comment: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(64), default="Новая")

    def __str__(self) -> str:
        return f"{self.number} — {self.name}, {self.phone} [{self.status}]"


class Track(Base, TimestampMixin):
    """Трек-номер груза."""

    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(primary_key=True)
    track_number: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(128), default="Получен на складе")

    history: Mapped[list["TrackHistory"]] = relationship(
        back_populates="track", order_by="TrackHistory.created_at"
    )

    def __str__(self) -> str:
        return f"{self.track_number} [{self.status}]"


class TrackHistory(Base):
    """История изменения статусов груза."""

    __tablename__ = "track_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id"), index=True)
    status: Mapped[str] = mapped_column(String(128))
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    track: Mapped[Track] = relationship(back_populates="history")


class Calculation(Base):
    """История расчётов стоимости доставки."""

    __tablename__ = "calculations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    tariff_id: Mapped[int | None] = mapped_column(ForeignKey("tariffs.id"), nullable=True)
    delivery_type: Mapped[str | None] = mapped_column(String(128))
    category: Mapped[str | None] = mapped_column(String(128))
    weight: Mapped[float | None] = mapped_column(Numeric(14, 4))
    volume: Mapped[float | None] = mapped_column(Numeric(14, 6))
    chargeable_weight: Mapped[float | None] = mapped_column(Numeric(14, 4))
    total: Mapped[float | None] = mapped_column(Numeric(14, 4))
    currency_code: Mapped[str | None] = mapped_column(String(8))
    details: Mapped[str | None] = mapped_column(Text)  # JSON с разбивкой расчёта
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
