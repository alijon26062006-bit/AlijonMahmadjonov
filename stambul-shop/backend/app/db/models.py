"""Модель данных магазина.

Главное отличие от доски объявлений: товар и его варианты — разные вещи.
Одна футболка это одна карточка и несколько вариантов «размер + цвет», у
каждого свой остаток. Покупатель кладёт в корзину вариант, а не товар.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY, BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, Numeric,
    SmallInteger, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# ─────────────────────────── Состояния ───────────────────────────

P_DRAFT = "draft"          # заведён, но не показывается
P_ACTIVE = "active"        # в продаже
P_HIDDEN = "hidden"        # снят вручную
P_OUT = "out"              # закончился на складе

O_NEW = "new"              # заказ оформлен, ждём подтверждения
O_CONFIRMED = "confirmed"  # подтверждён, ждём оплату
O_PAID = "paid"            # оплачен
O_SHIPPED = "shipped"      # отправлен
O_DONE = "done"            # получен
O_CANCELED = "canceled"

ORDER_FLOW = {
    O_NEW: (O_CONFIRMED, O_CANCELED),
    O_CONFIRMED: (O_PAID, O_CANCELED),
    O_PAID: (O_SHIPPED, O_CANCELED),
    O_SHIPPED: (O_DONE, O_CANCELED),
    O_DONE: (),
    O_CANCELED: (),
}


class User(Base):
    """Покупатель.

    Магазин живёт на сайте, поэтому у человека может не быть Telegram вовсе:
    он войдёт через Google. И наоборот — вошедший по номеру может не иметь
    почты. Поэтому все три опознавательных поля необязательны, но хотя бы
    одно у любого пользователя есть, и каждое уникально: совпал телефон,
    почта или Telegram — это тот же человек, а не новый.
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tg_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(32))
    first_name: Mapped[str] = mapped_column(String(128), default="")
    avatar_url: Mapped[str | None] = mapped_column(String(400))

    phone: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    email: Mapped[str | None] = mapped_column(String(160), unique=True, index=True)
    google_sub: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)

    # адрес запоминается с прошлого заказа — второй раз вводить не нужно
    city_id: Mapped[int | None] = mapped_column(
        ForeignKey("cities.id", ondelete="SET NULL"))
    address: Mapped[str | None] = mapped_column(String(255))

    # куда слать про заказ. Если человек выключил оба — письмо всё равно
    # уйдёт: иначе он не узнает, куда платить.
    notify_email: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_telegram: Mapped[bool] = mapped_column(Boolean, default=True)
    onboarding_done: Mapped[bool] = mapped_column(Boolean, default=False)

    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    bot_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())


class AuthCode(Base):
    """Заявка на вход по номеру телефона.

    Живёт от нажатия «Получить код» до входа и не дольше нескольких минут.
    `key` уходит в ссылку на бота, `code_hash` хранит код — сам код в базе
    не лежит нигде. `confirmed_at` ставится, когда бот сверил номер: с этого
    момента вкладка на сайте может впустить человека, не дожидаясь цифр.
    """
    __tablename__ = "auth_codes"
    __table_args__ = (Index("ix_auth_codes_phone_time", "phone", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    key: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    # login — вход по номеру; link — привязка бота к уже открытому аккаунту
    purpose: Mapped[str] = mapped_column(String(8), default="login")
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"))
    phone: Mapped[str] = mapped_column(String(20), index=True, default="")
    code_hash: Mapped[str | None] = mapped_column(String(64))
    tg_id: Mapped[int | None] = mapped_column(BigInteger)
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())


class Setting(Base):
    """Настройки из панели: ключи сторонних сервисов и прочее, что владелец
    меняет сам, не заходя на сервер."""
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(48), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CustomCategory(Base):
    """Раздел, заведённый владельцем из бота.

    Поля у него общие: угадать, какие характеристики важны для нового вида
    товара, программа не может, а спрашивать их у владельца в момент, когда
    он торопится завести товар, — верный способ его отпугнуть.
    """
    __tablename__ = "custom_categories"

    slug: Mapped[str] = mapped_column(String(40), primary_key=True)
    title: Mapped[str] = mapped_column(String(80), unique=True)
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=100)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())


class City(Base):
    __tablename__ = "cities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    # сколько дней идёт посылка — показываем при оформлении
    delivery_days: Mapped[int] = mapped_column(SmallInteger, default=3)
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=100)


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    areas: Mapped[list[str]] = mapped_column(ARRAY(String(24)))
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=100)


class Product(Base):
    """Карточка товара. Цена и остаток живут в вариантах."""
    __tablename__ = "products"
    __table_args__ = (
        Index("ix_products_live", "category_slug", "status", "sort_order"),
        Index("ix_products_attrs", "attrs", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    public_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, default=uuid.uuid4, index=True)
    category_slug: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    brand: Mapped[str | None] = mapped_column(String(80))
    # Цена карточки — «от»: минимальная среди вариантов. Пересчитывается
    # при каждом изменении вариантов, чтобы каталог не считал её на лету.
    price: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    old_price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(10), default=P_DRAFT, index=True)
    attrs: Mapped[dict] = mapped_column(JSONB, default=dict)
    views_count: Mapped[int] = mapped_column(Integer, default=0)
    sales_count: Mapped[int] = mapped_column(Integer, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=100)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    photos: Mapped[list["ProductPhoto"]] = relationship(
        back_populates="product", cascade="all, delete-orphan",
        order_by="ProductPhoto.position")
    variants: Mapped[list["Variant"]] = relationship(
        back_populates="product", cascade="all, delete-orphan",
        order_by="Variant.sort_order")


class ProductPhoto(Base):
    __tablename__ = "product_photos"
    __table_args__ = (UniqueConstraint("product_id", "position"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    public_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, default=uuid.uuid4)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True)
    file_id: Mapped[str] = mapped_column(Text)
    thumb_file_id: Mapped[str | None] = mapped_column(Text)
    thumb_w: Mapped[int | None]
    file_unique_id: Mapped[str] = mapped_column(String(64))
    width: Mapped[int | None]
    height: Mapped[int | None]
    position: Mapped[int] = mapped_column(SmallInteger, default=0)

    # Обработанная версия живёт в той же строке, отдельными полями. Так
    # оригинал невозможно потерять, а списки товаров и галерея ничего не
    # знают об обработке: они просто просят фотографию, а какую отдать —
    # решает один флаг.
    proc_file_id: Mapped[str | None] = mapped_column(Text)
    proc_thumb_file_id: Mapped[str | None] = mapped_column(Text)
    proc_thumb_w: Mapped[int | None]
    proc_file_unique_id: Mapped[str | None] = mapped_column(String(64))
    use_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    background: Mapped[str | None] = mapped_column(String(16))
    style_version: Mapped[int | None] = mapped_column(SmallInteger)
    processing: Mapped[str] = mapped_column(String(12), default="none")
    # none | queued | working | ready | review | failed
    processing_error: Mapped[str | None] = mapped_column(String(300))
    # standard — только фон и свет, пиксели товара не трогаются;
    # reshape — ретушь с исправлением подачи, требует сверки с оригиналом
    mode: Mapped[str | None] = mapped_column(String(12))
    prompt_version: Mapped[str | None] = mapped_column(String(40))
    check_status: Mapped[str | None] = mapped_column(String(10))
    # skipped | ok | review
    check_note: Mapped[str | None] = mapped_column(String(500))

    product: Mapped[Product] = relationship(back_populates="photos")


class Variant(Base):
    """Размер и цвет со своим остатком. Именно его кладут в корзину."""
    __tablename__ = "variants"
    __table_args__ = (
        UniqueConstraint("product_id", "size", "color"),
        Index("ix_variants_stock", "product_id", "stock"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True)
    size: Mapped[str] = mapped_column(String(24), default="")   # "" — размера нет
    color: Mapped[str] = mapped_column(String(40), default="")
    sku: Mapped[str | None] = mapped_column(String(48))
    price: Mapped[float] = mapped_column(Numeric(12, 2))
    stock: Mapped[int] = mapped_column(Integer, default=0)
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=100)

    product: Mapped[Product] = relationship(back_populates="variants")

    @property
    def label(self) -> str:
        return " · ".join(p for p in (self.size, self.color) if p) or "Один размер"


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("user_id", "variant_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True)
    variant_id: Mapped[int] = mapped_column(
        ForeignKey("variants.id", ondelete="CASCADE"), index=True)
    qty: Mapped[int] = mapped_column(SmallInteger, default=1)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    public_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, default=uuid.uuid4, index=True)
    # короткий человеческий номер: его называют в переписке и в переводе
    number: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default=O_NEW, index=True)

    customer_name: Mapped[str] = mapped_column(String(128))
    phone: Mapped[str] = mapped_column(String(20))
    city_id: Mapped[int | None] = mapped_column(
        ForeignKey("cities.id", ondelete="SET NULL"))
    address: Mapped[str | None] = mapped_column(String(255))
    delivery: Mapped[str] = mapped_column(String(12), default="courier")
    comment: Mapped[str | None] = mapped_column(String(500))

    goods_total: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    delivery_price: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    total: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    tracking: Mapped[str | None] = mapped_column(String(64))
    admin_note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    """Строка заказа со снимком названия и цены.

    Товар потом переименуют или подорожает — в старом заказе должно остаться
    то, что человек покупал.
    """
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    variant_id: Mapped[int | None] = mapped_column(
        ForeignKey("variants.id", ondelete="SET NULL"))
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(200))
    variant_label: Mapped[str] = mapped_column(String(80), default="")
    price: Mapped[float] = mapped_column(Numeric(12, 2))
    qty: Mapped[int] = mapped_column(SmallInteger, default=1)

    order: Mapped[Order] = relationship(back_populates="items")


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "product_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())


class ProductEvent(Base):
    """События для витрины: просмотр, корзина, покупка."""
    __tablename__ = "product_events"
    __table_args__ = (Index("ix_events_user_time", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(12))     # view | cart | purchase
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())


class CurrencyRate(Base):
    __tablename__ = "currency_rates"

    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    per_usd: Mapped[float] = mapped_column(Numeric(12, 4))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AdminLog(Base):
    __tablename__ = "admin_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(32))
    target: Mapped[str | None] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
