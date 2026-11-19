from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (JSON, Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

MONEY = Numeric(18, 4)


def now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="user")  # user | admin
    balance: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    ledger: Mapped[list["LedgerEntry"]] = relationship(back_populates="user")


class LedgerEntry(Base):
    """Every balance change is one row. Balance = sum of the user's entries."""

    __tablename__ = "ledger"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # credit | debit
    reason: Mapped[str] = mapped_column(String(32))  # topup | order | refund | admin
    amount: Mapped[Decimal] = mapped_column(MONEY)  # always positive
    balance_after: Mapped[Decimal] = mapped_column(MONEY)
    ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    user: Mapped[User] = relationship(back_populates="ledger")


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (Index("ix_orders_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    product_type: Mapped[str] = mapped_column(String(24))  # topup | telegram_stars | ...
    title: Mapped[str] = mapped_column(String(255))
    request: Mapped[dict] = mapped_column(JSON)  # what we send to the supplier (no secrets)
    cost: Mapped[Decimal] = mapped_column(MONEY)  # supplier price
    price: Mapped[Decimal] = mapped_column(MONEY)  # customer price
    status: Mapped[str] = mapped_column(String(16), default="new")  # new|processing|completed|refunded|failed
    supplier_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    supplier_response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    delivery: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # codes etc. shown to buyer
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Payment(Base):
    """Customer top-up invoice (USDT TRC20 with unique tail, Bybit UID, TON...)."""

    __tablename__ = "payments"
    __table_args__ = (UniqueConstraint("method", "expected_amount", "status_open", name="uq_open_amount"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    method: Mapped[str] = mapped_column(String(16))  # trc20 | bep20 | ton | bybit_uid | binance_pay
    amount: Mapped[Decimal] = mapped_column(MONEY)  # credited to balance
    expected_amount: Mapped[Decimal] = mapped_column(MONEY)  # exact amount to send (with tail)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|completed|expired
    # 1 while pending, NULL otherwise: makes "one open invoice per exact amount" a DB rule
    status_open: Mapped[int | None] = mapped_column(Integer, nullable=True, default=1)
    tx_id: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
