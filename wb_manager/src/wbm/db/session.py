"""Подключение к базе: асинхронный движок и фабрика сессий."""

from __future__ import annotations

from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def make_engine(url: str, *, echo: bool = False) -> AsyncEngine:
    """MySQL: mysql+aiomysql://user:pass@host/db?charset=utf8mb4. Тесты: sqlite+aiosqlite://."""
    if url.startswith("mysql"):
        # pool_recycle: MySQL рвёт простаивающие соединения (wait_timeout) — переоткрываем заранее.
        return create_async_engine(url, echo=echo, pool_pre_ping=True, pool_recycle=1800)
    engine = create_async_engine(url, echo=echo)
    if url.startswith("sqlite"):
        # SQLite по умолчанию не проверяет внешние ключи — без этого не работает каскадное удаление.
        event.listen(engine.sync_engine, "connect", _sqlite_foreign_keys)
    return engine


def _sqlite_foreign_keys(dbapi_connection: Any, _record: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
