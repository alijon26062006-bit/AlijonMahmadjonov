"""Сборка бота и диспетчера."""
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from app.bot.handlers import orders, start
from app.bot.middlewares import DbMiddleware, UserMiddleware
from app.config import get_settings


def create_bot() -> Bot:
    return Bot(token=get_settings().bot_token,
               default=DefaultBotProperties(parse_mode="HTML"))


def create_dispatcher() -> Dispatcher:
    s = get_settings()
    dp = Dispatcher(storage=RedisStorage.from_url(s.redis_url))
    dp["redis"] = Redis.from_url(s.redis_url)
    dp.update.middleware(DbMiddleware())
    dp.update.middleware(UserMiddleware())
    dp.include_router(start.router)
    dp.include_router(orders.router)
    return dp
