from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.config import get_settings
from bot.models import Base

engine = create_async_engine(get_settings().database_url, echo=False)
session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def create_tables() -> None:
    """Создание таблиц для MVP. В продакшене использовать Alembic-миграции."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
