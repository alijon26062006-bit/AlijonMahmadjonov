"""Точка входа: веб-сервер дуэли и телеграм-бот в одном процессе."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiohttp import web

from . import bot as bot_module
from . import storage
from .config import DuelConfig, load_config
from .server import Hub, make_app


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)


async def run(config: DuelConfig) -> None:
    log = logging.getLogger("duel")
    config.ensure_dirs()
    conn = storage.connect(config.db_path)

    bot = Bot(config.bot_token, default=DefaultBotProperties(parse_mode=None))
    me = await bot.get_me()

    async def notify(user_id: int, text: str) -> None:
        """Итог матча в чат. Если человек заблокировал бота — молча пропускаем."""
        with contextlib.suppress(Exception):
            await bot.send_message(user_id, text)

    hub = Hub(config, conn, notify=notify, bot_username=me.username or "")
    runner = web.AppRunner(make_app(hub))
    await runner.setup()
    site = web.TCPSite(runner, config.host, config.port)
    await site.start()
    log.info("Сервер на http://%s:%s, Mini App: %s", config.host, config.port, config.webapp_url)

    dispatcher = Dispatcher()
    dispatcher.include_router(bot_module.router)
    dispatcher["config"] = config
    dispatcher["conn"] = conn

    with contextlib.suppress(Exception):
        await bot_module.setup_bot_ui(bot, config)

    log.info("Бот @%s готов. База: %s", me.username, config.db_path)
    if config.dev_mode:
        log.warning("DUEL_DEV_MODE включён: подпись Telegram не проверяется. "
                    "На боевом сервере обязательно выключи.")

    try:
        await bot.delete_webhook(drop_pending_updates=False)
        await dispatcher.start_polling(
            bot, allowed_updates=dispatcher.resolve_used_update_types()
        )
    finally:
        await runner.cleanup()
        await bot.session.close()
        conn.close()


def main() -> int:
    try:
        config = load_config()
    except (RuntimeError, ValueError) as exc:
        print(f"Ошибка настройки: {exc}", file=sys.stderr)
        return 1

    setup_logging(config.log_level)
    try:
        asyncio.run(run(config))
    except KeyboardInterrupt:
        print("\nОстановлен.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
