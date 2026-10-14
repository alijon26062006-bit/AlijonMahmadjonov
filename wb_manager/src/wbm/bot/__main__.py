"""Запуск бота: python -m wbm.bot"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from wbm.bootstrap import build_app
from wbm.bot.handlers import UserMiddleware, group_router, router
from wbm.bot.services import BotServices

logger = logging.getLogger("wbm.bot")

COMMANDS = [
    BotCommand(command="analyze", description="Проанализировать магазин"),
    BotCommand(command="history", description="Прошлые анализы и PDF"),
    BotCommand(command="shops", description="Мои магазины"),
    BotCommand(command="costs", description="Загрузить себестоимость"),
    BotCommand(command="token", description="Как подключить магазин"),
    BotCommand(command="help", description="Помощь"),
]


async def main() -> None:
    app = build_app()
    bot = Bot(app.telegram_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dispatcher = Dispatcher()
    dispatcher["services"] = BotServices(app.sessionmaker, app.cipher, app.wb_settings)
    middleware = UserMiddleware()
    for current in (router, group_router):
        current.message.outer_middleware(middleware)
        current.callback_query.outer_middleware(middleware)
    dispatcher.include_routers(router, group_router)
    await bot.set_my_commands(COMMANDS)
    logger.info("Бот запущен")
    try:
        await dispatcher.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        await bot.session.close()
        await app.engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
