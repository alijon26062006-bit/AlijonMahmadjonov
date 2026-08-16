"""Все таблицы проекта.

Динамические поля категорий живут в listings.attrs (JSONB).
Enum'ы — VARCHAR, не нативные PG-типы (совместимость с миграциями).
"""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, Numeric,
    SmallInteger, String, Text, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# Статусы объявления
ST_DRAFT = "draft"
ST_PENDING = "pending"
ST_APPROVED = "approved"
ST_REJECTED = "rejected"
ST_ARCHIVED = "archived"
ST_SOLD = "sold"
ST_OCCUPIED = "occupied"   # аренда: занято, вернётся в каталог


def now() -> datetime:
    return datetime.utcnow()


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(32))
    first_name: Mapped[str] = mapped_column(String(128), default="")
    phone: Mapped[str | None] = mapped_column(String(20))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    bot_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class City(Base):
    __tablename__ = "cities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    lat: Mapped[float | None]
    lon: Mapped[float | None]
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    districts: Mapped[list["District"]] = relationship(back_populates="city")


class District(Base):
    __tablename__ = "districts"
    __table_args__ = (UniqueConstraint("city_id", "name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))

    city: Mapped[City] = relationship(back_populates="districts")


class Brand(Base):
    """Общий справочник брендов. Один бренд — несколько областей (Samsung: телефоны и ТВ)."""
    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    areas: Mapped[list[str]] = mapped_column(ARRAY(String(24)))
    popular: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=100)


class VehicleModel(Base):
    __tablename__ = "models"
    __table_args__ = (UniqueConstraint("brand_id", "name", "area"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    area: Mapped[str] = mapped_column(String(24), default="cars")
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=100)


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    public_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, default=uuid.uuid4)
    author_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category_slug: Mapped[str] = mapped_column(String(40), index=True)

    title: Mapped[str] = mapped_column(String(140))
    description: Mapped[str] = mapped_column(String(1000), default="")

    price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="TJS")
    price_usd: Mapped[Decimal] = mapped_column(Numeric(14, 2))       # нормализованная
    is_negotiable: Mapped[bool] = mapped_column(Boolean, default=False)

    city_id: Mapped[int | None] = mapped_column(ForeignKey("cities.id"))
    district_id: Mapped[int | None] = mapped_column(ForeignKey("districts.id"))
    address: Mapped[str | None] = mapped_column(String(255))
    lat: Mapped[float | None]
    lon: Mapped[float | None]

    contact_mode: Mapped[str] = mapped_column(String(10), default="telegram")
    contact_phone: Mapped[str | None] = mapped_column(String(20))
    contact_username: Mapped[str | None] = mapped_column(String(32))

    status: Mapped[str] = mapped_column(String(12), default=ST_DRAFT, index=True)
    reject_reason: Mapped[str | None] = mapped_column(String(500))
    flag_note: Mapped[str | None] = mapped_column(String(300))   # заметка проверок для модератора

    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    channel_message_id: Mapped[int | None] = mapped_column(Integer)

    views_count: Mapped[int] = mapped_column(Integer, default=0)
    favorites_count: Mapped[int] = mapped_column(Integer, default=0)
    contacts_count: Mapped[int] = mapped_column(Integer, default=0)

    attrs: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    photos: Mapped[list["ListingPhoto"]] = relationship(
        back_populates="listing", order_by="ListingPhoto.position",
        cascade="all, delete-orphan")
    author: Mapped[User] = relationship()

    __table_args__ = (
        Index("ix_listings_feed", text("published_at DESC"), text("id DESC"),
              postgresql_where=text("status = 'approved'")),
        Index("ix_listings_cat_price", "category_slug", "price_usd",
              postgresql_where=text("status = 'approved'")),
        Index("ix_listings_attrs", "attrs", postgresql_using="gin",
              postgresql_ops={"attrs": "jsonb_path_ops"}),
        Index("ix_listings_pending", "created_at",
              postgresql_where=text("status = 'pending'")),
    )


class ListingPhoto(Base):
    __tablename__ = "listing_photos"
    __table_args__ = (UniqueConstraint("listing_id", "position"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    public_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, default=uuid.uuid4)
    listing_id: Mapped[int] = mapped_column(
        ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    file_id: Mapped[str] = mapped_column(Text)
    thumb_file_id: Mapped[str | None] = mapped_column(Text)
    # ширина превью: Telegram отдаёт размеры от ~90 px, такой в сетке мутный.
    # Заодно метка «превью выбрано новым правилом» для разовой чистки старых.
    thumb_w: Mapped[int | None]
    file_unique_id: Mapped[str] = mapped_column(String(64))
    width: Mapped[int | None]
    height: Mapped[int | None]
    position: Mapped[int] = mapped_column(SmallInteger, default=0)

    listing: Mapped[Listing] = relationship(back_populates="photos")


class Favorite(Base):
    __tablename__ = "favorites"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    listing_id: Mapped[int] = mapped_column(
        ForeignKey("listings.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (UniqueConstraint("listing_id", "reporter_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"))
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    reason: Mapped[str] = mapped_column(String(20))
    comment: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(12), default="new")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ListingEvent(Base):
    """Поведение пользователей — основа алгоритма ленты.

    Собирается с первого дня работы: задним числом эти данные получить неоткуда.
    """
    __tablename__ = "listing_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    listing_id: Mapped[int] = mapped_column(
        ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True)
    # view | favorite | contact_click | share
    kind: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        # Профиль интересов строится по последним событиям человека
        Index("ix_events_user_time", "user_id", "created_at"),
        Index("ix_events_listing_kind", "listing_id", "kind"),
    )


class ModerationLog(Base):
    __tablename__ = "moderation_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # NULL — для действий над пользователем, не связанных с объявлением
    listing_id: Mapped[int | None] = mapped_column(
        ForeignKey("listings.id", ondelete="CASCADE"))
    admin_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CurrencyRate(Base):
    __tablename__ = "currency_rates"

    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    per_usd: Mapped[Decimal] = mapped_column(Numeric(18, 8))   # сколько единиц за 1 USD
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TacModel(Base):
    """TAC → модель устройства. Первые 8 цифр IMEI одинаковы у всей партии
    одной модели, поэтому по ним аппарат узнаётся без единого запроса в сеть.

    Наполняется двумя путями: разовым импортом открытого списка
    (`python -m app.seed.import_tac файл.csv`) и самой площадкой — когда
    модератор одобряет объявление, где IMEI и модель указаны вместе.
    `confirmations` — сколько одобренных объявлений сошлись на этой паре;
    показываем подсказку начиная с двух, чтобы одна опечатка не стала правдой.
    """
    __tablename__ = "tac_models"

    tac: Mapped[str] = mapped_column(String(8), primary_key=True)
    brand: Mapped[str] = mapped_column(String(60))
    model: Mapped[str] = mapped_column(String(120))
    source: Mapped[str] = mapped_column(String(12), default="learned")  # import | learned
    confirmations: Mapped[int] = mapped_column(default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class BlacklistEntry(Base):
    """Чёрный список площадки: IMEI/VIN украденных вещей от пользователей."""
    __tablename__ = "blacklist"
    __table_args__ = (UniqueConstraint("kind", "value_norm"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    kind: Mapped[str] = mapped_column(String(12))          # imei | vin | serial
    value_norm: Mapped[str] = mapped_column(String(64))
    note: Mapped[str | None] = mapped_column(String(300))
    reported_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
