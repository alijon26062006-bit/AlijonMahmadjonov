"""Создание схемы БД и загрузка справочников: python -m app.db.create

create_all создаёт недостающие таблицы, но не меняет существующие.
Поэтому изменения в уже созданных таблицах выполняются отдельным списком
идемпотентных операторов ниже — они безопасны при повторном запуске.
"""
import asyncio

from sqlalchemy import text

from app.db.base import Base, engine
from app.db import models  # noqa: F401 — регистрирует таблицы
from app.seed.seed import seed

# Каждый оператор должен быть безопасен при повторном выполнении
MIGRATIONS: list[str] = [
    # Действия над пользователями (бан) не привязаны к объявлению
    "ALTER TABLE moderation_log ALTER COLUMN listing_id DROP NOT NULL",
]


async def apply_migrations() -> None:
    applied = 0
    async with engine.begin() as conn:
        for sql in MIGRATIONS:
            try:
                await conn.execute(text(sql))
                applied += 1
            except Exception as e:      # уже применено или неприменимо
                print(f"  пропущено: {sql.split(' ALTER COLUMN')[0]}… ({type(e).__name__})")
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
