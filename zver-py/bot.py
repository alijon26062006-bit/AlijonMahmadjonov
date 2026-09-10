"""ZVER TAJ — Telegram-бот на Python (aiogram 3).

Работает через long polling: HTTPS, домен и nginx не нужны.
База — та же MySQL, что у PHP-версии, таблицы z_*.

Запуск вручную:   python bot.py
На сервере:       systemctl start zverbot
"""
from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import config
import db
from handlers import admin, shop, user

logging.basicConfig(
    level=logging.DEBUG if config.DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("zver")


async def main() -> None:
    await db.init()
    try:
        row = await db.one("SELECT COUNT(*) AS c FROM z_users")
        log.info("база на связи, пользователей: %s", (row or {}).get("c", "?"))
    except Exception:
        log.exception("нет связи с базой — проверьте DB_* в .env")
        await db.close()
        sys.exit(1)

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # снимаем webhook: PHP-версия могла его оставить, иначе polling не пойдёт
    try:
        await bot.delete_webhook(drop_pending_updates=False)
    except Exception as e:
        log.warning("не удалось снять webhook: %s", e)

    me = await bot.get_me()
    log.info("бот @%s запущен, админов: %s", me.username, len(config.ADMINS))

    dp = Dispatcher(storage=MemoryStorage())
    # админский роутер первым: его кнопки не должны перехватываться общими
    dp.include_router(admin.router)
    dp.include_router(shop.router)
    dp.include_router(user.router)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        await db.close()
        log.info("остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
