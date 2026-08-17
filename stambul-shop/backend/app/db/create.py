"""Создание схемы и загрузка справочников.

Запуск: python -m app.db.create
"""
import asyncio

from sqlalchemy import text

from app.db.base import Base, engine
from app.db import models  # noqa: F401  — регистрирует таблицы в метаданных
from app.seed.seed import seed

# Изменения, которые create_all сам не сделает. Каждое пишется так, чтобы
# повторный запуск ничего не ломал.
MIGRATIONS: list[str] = []


async def apply_migrations() -> None:
    applied = 0
    async with engine.begin() as conn:
        for sql in MIGRATIONS:
            try:
                await conn.execute(text(sql))
                applied += 1
            except Exception as e:
                print(f"  пропущено: {sql[:60]}… ({type(e).__name__})")
    if applied:
        print(f"Изменения схемы применены: {applied}")


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Схема БД создана")
    await apply_migrations()
    await seed()


if __name__ == "__main__":
    asyncio.run(main())
