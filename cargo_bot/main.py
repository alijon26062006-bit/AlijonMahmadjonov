"""Точка входа бота карго-доставки Китай → Таджикистан."""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import get_settings
from bot.database import create_tables, session_maker
from bot.database.seed import seed
from bot.handlers import router
from bot.middlewares import DbSessionMiddleware, UserMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()

    # Для MVP таблицы создаются автоматически; в продакшене — alembic upgrade head
    await create_tables()
    if settings.seed_on_start:
        async with session_maker() as session:
            await seed(session)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    dp.update.middleware(DbSessionMiddleware(session_maker))
    dp.update.middleware(UserMiddleware())
    dp.include_router(router)

    logger.info("Бот запущен")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
