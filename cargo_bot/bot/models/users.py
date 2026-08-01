from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class User(Base):
    """Пользователь бота."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(128))
    full_name: Mapped[str | None] = mapped_column(String(256))
    phone: Mapped[str | None] = mapped_column(String(32))
    language: Mapped[str] = mapped_column(String(8), default="ru")
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __str__(self) -> str:
        return f"#{self.id} {self.full_name or ''} @{self.username or '-'} ({self.tg_id})"


class Admin(Base):
    """Администратор (дополнительно к ADMIN_IDS из .env)."""

    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(256))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __str__(self) -> str:
        return f"{self.name or 'админ'} ({self.tg_id})"
