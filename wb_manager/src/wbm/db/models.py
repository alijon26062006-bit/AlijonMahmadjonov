"""Таблицы базы данных.

Сырые ответы WB не храним: только настройки магазинов, результаты проверок
и короткие сведения о загрузке данных. Так база маленькая и в ней меньше
персональных данных покупателей.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wbm.db.base import Base, BigInt, LongText, UTCDateTime, utcnow


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


ACTIVE_RUN_STATUSES = (RunStatus.QUEUED, RunStatus.RUNNING)


class RunSource(StrEnum):
    WEB = "web"
    TELEGRAM = "telegram"


class DatasetStatus(StrEnum):
    OK = "ok"
    EMPTY = "empty"
    ERROR = "error"
    ANOMALY = "anomaly"
    SKIPPED = "skipped"


class CheckStatus(StrEnum):
    PROBLEMS = "problems"
    OK = "ok"
    NO_DATA = "no_data"
    NEEDS_COST = "needs_cost"
    ERROR = "error"


class Severity(StrEnum):
    CRITICAL = "critical"
    IMPORTANT = "important"
    ADVICE = "advice"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    telegram_chat_id: Mapped[int | None] = mapped_column(
        BigInt, unique=True, nullable=True, default=None
    )
    telegram_link_code: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True, default=None
    )
    telegram_link_expires_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime, nullable=True, default=None
    )

    shops: Mapped[list[Shop]] = relationship(back_populates="user", cascade="all, delete-orphan")


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    __table_args__ = (
        Index(None, "email", "created_at"),
        Index(None, "ip", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(254))
    ip: Mapped[str] = mapped_column(String(45))
    success: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Shop(Base):
    __tablename__ = "shops"
    __table_args__ = (UniqueConstraint("user_id", "seller_id"),)

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInt, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    seller_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    token_encrypted: Mapped[str] = mapped_column(Text)
    """Токен WB, зашифрованный Fernet. Ключ — только в .env."""
    token_fingerprint: Mapped[str] = mapped_column(String(16))
    token_kind: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    token_categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    """Категории WB, доступ к которым подтверждён при проверке токена."""
    token_checked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    sandbox: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="shops")


class CostPrice(Base):
    __tablename__ = "cost_prices"
    __table_args__ = (UniqueConstraint("shop_id", "vendor_code"),)

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(BigInt, ForeignKey("shops.id", ondelete="CASCADE"))
    vendor_code: Mapped[str] = mapped_column(String(100))
    """Артикул продавца из файла себестоимости."""
    cost: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    uploaded_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (Index(None, "status", "created_at"),)

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(
        BigInt, ForeignKey("shops.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(16), default=RunStatus.QUEUED)
    source: Mapped[str] = mapped_column(String(16), default=RunSource.WEB)
    period_days: Mapped[int] = mapped_column(SmallInteger, default=30)
    progress: Mapped[int] = mapped_column(SmallInteger, default=0)
    stage: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    report_text: Mapped[str | None] = mapped_column(LongText, nullable=True)

    shop: Mapped[Shop] = relationship()
    datasets: Mapped[list[RunDataset]] = relationship(
        cascade="all, delete-orphan", order_by="RunDataset.id"
    )
    checks: Mapped[list[CheckResult]] = relationship(
        cascade="all, delete-orphan", order_by="CheckResult.position"
    )


class RunDataset(Base):
    """Как загрузился каждый набор данных WB в конкретном анализе."""

    __tablename__ = "run_datasets"
    __table_args__ = (UniqueConstraint("run_id", "dataset"),)

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(BigInt, ForeignKey("analysis_runs.id", ondelete="CASCADE"))
    dataset: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    rows: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)


class CheckResult(Base):
    """Итог одной проверки в анализе."""

    __tablename__ = "check_results"
    __table_args__ = (UniqueConstraint("run_id", "check_id"),)

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(BigInt, ForeignKey("analysis_runs.id", ondelete="CASCADE"))
    check_id: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16))
    position: Mapped[int] = mapped_column(SmallInteger, default=0)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    """Почему «нет данных» / «нужна себестоимость» / оговорка об аномалии данных."""

    findings: Mapped[list[Finding]] = relationship(
        cascade="all, delete-orphan", order_by="Finding.position"
    )


class Finding(Base):
    """Одна найденная проблема."""

    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    check_result_id: Mapped[int] = mapped_column(
        BigInt, ForeignKey("check_results.id", ondelete="CASCADE"), index=True
    )
    severity: Mapped[str] = mapped_column(String(16))
    position: Mapped[int] = mapped_column(SmallInteger, default=0)
    title: Mapped[str] = mapped_column(String(255))
    products: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    facts: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    reason: Mapped[str] = mapped_column(Text)
    recommendation: Mapped[str] = mapped_column(Text)
    caveat: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    """Понятный текст от Claude (этап 5)."""
