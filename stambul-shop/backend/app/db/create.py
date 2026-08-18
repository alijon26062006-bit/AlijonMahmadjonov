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
MIGRATIONS: list[str] = [
    # Магазин переехал с Mini App на обычный сайт: Telegram перестал быть
    # обязательным, зато появились почта, Google и переключатели уведомлений.
    "ALTER TABLE users ALTER COLUMN tg_id DROP NOT NULL",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(400)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN "
    "NOT NULL DEFAULT FALSE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(160)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS google_sub VARCHAR(64)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS notify_email BOOLEAN "
    "NOT NULL DEFAULT TRUE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS notify_telegram BOOLEAN "
    "NOT NULL DEFAULT TRUE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarding_done BOOLEAN "
    "NOT NULL DEFAULT FALSE",
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_sub ON users (google_sub)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_phone ON users (phone)",
]


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
