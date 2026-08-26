"""Точка входа. Запуск: python -m app.main (из папки stars_bot)."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from app import db
from app.config import settings
from app.handlers import admin, deposit, menu, profile, shop, support
from app.middlewares.guard import UserGuardMiddleware
from app.services.fragment import build_provider

log = logging.getLogger(__name__)

USER_COMMANDS = [
    BotCommand(command="start", description="Главное меню"),
    BotCommand(command="menu", description="Главное меню"),
]


async def main() -> None:
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    if not settings.admin_ids:
        log.warning("ADMIN_IDS пуст — подтверждать пополнения будет некому!")
    if not settings.pay_card_number:
        log.warning("PAY_CARD_NUMBER не задан — пользователям некуда переводить деньги!")

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    conn = await db.connect()
    await db.init(conn)
    provider = build_provider()

    dp = Dispatcher(conn=conn, provider=provider)
    dp.message.middleware(UserGuardMiddleware())
    dp.callback_query.middleware(UserGuardMiddleware())

    # admin первым: его фильтр отсекает чужие апдейты и пропускает их дальше.
    dp.include_router(admin.router)
    dp.include_router(menu.router)
    dp.include_router(shop.router)
    dp.include_router(deposit.router)
    dp.include_router(profile.router)
    dp.include_router(support.router)

    await bot.set_my_commands(USER_COMMANDS)
    me = await bot.me()
    log.info("Запущен @%s. Fragment: %s", me.username, settings.fragment_mode)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await provider.close()
        await conn.close()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Остановлено")
