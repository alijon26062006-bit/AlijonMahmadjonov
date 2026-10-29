"""Точка входа: long polling, без домена и HTTPS.

    python -m course_bot
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from . import admin, db, handlers, subscriptions
from .config import Config, load_config


def build_dispatcher(config: Config, conn) -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.include_router(admin.router)     # админ — раньше общих обработчиков
    dispatcher.include_router(handlers.router)
    dispatcher["config"] = config
    dispatcher["conn"] = conn
    return dispatcher


async def run(config: Config) -> None:
    log = logging.getLogger("course_bot")
    conn = db.connect(config.db_path)
    bot = Bot(config.token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dispatcher = build_dispatcher(config, conn)
    me = await bot.get_me()
    log.info("Запущен как @%s. Админы: %s. База: %s", me.username, sorted(config.admin_ids), config.db_path)
    # Раз в полчаса: напомнить о продлении, убрать из канала тех, у кого срок вышел.
    checker = asyncio.create_task(subscriptions.run(bot, conn, config))
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        # chat_member нужен, чтобы заметить вход в канал по чужой ссылке.
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        checker.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await checker
        await bot.session.close()
        conn.close()


def main() -> int:
    try:
        config = load_config()
    except (RuntimeError, ValueError) as exc:
        print(f"Ошибка настройки: {exc}", file=sys.stderr)
        return 1
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
                        datefmt="%H:%M:%S")
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    try:
        asyncio.run(run(config))
    except KeyboardInterrupt:
        print("\nОстановлен.")
    return 0
