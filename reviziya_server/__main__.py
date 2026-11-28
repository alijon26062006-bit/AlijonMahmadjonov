"""Запуск: python -m reviziya_server. Поднимает сайт мини-аппа и бота в одном процессе."""

from __future__ import annotations

import asyncio
import contextlib
import logging

from aiogram import Bot
from aiohttp import web

from . import db
from .app import create_app
from .bot import Notifier, build_dispatcher, configure
from .config import load_config
from .reader import PriceReader


async def run() -> None:
    config = load_config()
    log = logging.getLogger("reviziya")
    conn = db.connect(config.db_path)
    db.current_revision(conn)

    bot = Bot(config.bot_token)
    notifier = Notifier(bot, conn, config.public_url)
    reader = PriceReader(config.anthropic_api_key, config.model)
    await reader.warm_up()

    runner = web.AppRunner(create_app(config, conn, reader, notifier))
    await runner.setup()
    await web.TCPSite(runner, config.host, config.port).start()
    log.info("Сайт слушает %s:%s, адрес для Telegram: %s", config.host, config.port, config.public_url)

    try:
        await configure(bot, config.public_url)
        me = await bot.get_me()
        log.info("Бот @%s запущен", me.username)
        await build_dispatcher(conn, notifier, config.public_url).start_polling(bot)
    finally:
        with contextlib.suppress(Exception):
            await runner.cleanup()
        with contextlib.suppress(Exception):
            await bot.session.close()
        conn.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(run())


if __name__ == "__main__":
    main()
