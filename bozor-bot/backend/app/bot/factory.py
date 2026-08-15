"""Сборка бота и диспетчера."""
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from app.bot.handlers import moderation, my_listings, start, wizard
from app.bot.middlewares import AlbumMiddleware, DbMiddleware, UserMiddleware
from app.config import get_settings


def create_bot() -> Bot:
    return Bot(token=get_settings().bot_token,
               default=DefaultBotProperties(parse_mode="HTML"))


def create_dispatcher() -> Dispatcher:
    s = get_settings()
    storage = RedisStorage.from_url(s.redis_url)
    dp = Dispatcher(storage=storage)
    dp["redis"] = Redis.from_url(s.redis_url)

    dp.update.middleware(DbMiddleware())
    dp.update.middleware(UserMiddleware())
    dp.message.middleware(AlbumMiddleware())

    dp.include_router(start.router)
    dp.include_router(moderation.router)
    dp.include_router(my_listings.router)
    dp.include_router(wizard.router)
    return dp
