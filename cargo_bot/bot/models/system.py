from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Log(Base):
    """Журнал всех изменений и действий.

    Хранит: кто (actor_tg_id), что (action/entity/entity_id),
    старые и новые значения (JSON), когда (created_at).
    """

    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_tg_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    action: Mapped[str] = mapped_column(String(64))  # create/update/delete/toggle/...
    entity: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    old_data: Mapped[str | None] = mapped_column(Text)
    new_data: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Broadcast(Base):
    """История массовых рассылок."""

    __tablename__ = "broadcasts"

    id: Mapped[int] = mapped_column(primary_key=True)
    admin_tg_id: Mapped[int] = mapped_column(BigInteger)
    text: Mapped[str] = mapped_column(Text)
    total: Mapped[int] = mapped_column(Integer, default=0)
    sent: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Setting(Base):
    """Гибкие настройки (правила округления, списки статусов и т.д.)."""

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)

    def __str__(self) -> str:
        return f"{self.key} = {self.value}"
