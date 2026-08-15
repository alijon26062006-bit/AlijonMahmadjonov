"""Создание схемы БД и загрузка справочников: python -m app.db.create"""
import asyncio

from app.db.base import Base, engine
from app.db import models  # noqa: F401 — регистрирует таблицы
from app.seed.seed import seed


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Схема БД создана")
    await seed()


if __name__ == "__main__":
    asyncio.run(main())
