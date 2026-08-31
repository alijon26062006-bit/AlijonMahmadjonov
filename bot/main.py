"""Точка входа: long polling, без домена и HTTPS."""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from . import brain as brain_module
from . import db, handlers, reports, stt
from .config import Config, load_config


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


async def run(config: Config) -> None:
    log = logging.getLogger("bot")
    config.ensure_dirs()

    # Шрифты проверяем на старте, а не когда пользователь попросит отчёт.
    reports.register_fonts(config.font_path, config.font_bold_path)

    conn = db.connect(config.db_path)
    transcriber = stt.Transcriber(
        stt.make_client(config.openai_api_key), model=config.whisper_model
    )
    brain = brain_module.Brain(brain_module.make_client(config), conn, config)

    bot = Bot(config.telegram_token, default=DefaultBotProperties(parse_mode=None))
    dispatcher = Dispatcher()
    dispatcher.include_router(handlers.router)

    # Зависимости прокидываются в хендлеры как аргументы.
    dispatcher["config"] = config
    dispatcher["conn"] = conn
    dispatcher["brain"] = brain
    dispatcher["stt"] = transcriber

    me = await bot.get_me()
    log.info("Запущен как @%s. База: %s", me.username, config.db_path)
    log.info("Отвечаю только этим id: %s", sorted(config.allowed_user_ids))

    try:
        await bot.delete_webhook(drop_pending_updates=False)
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
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
