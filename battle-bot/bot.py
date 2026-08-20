"""Точка входа: настройка бота и запуск long polling."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from config import load_config
from core.engine import BattleEngine
from core.scheduler import DeadlineWatcher
from handlers import admin, payments, start, voting
from services.startup import SetupError, prepare
from storage.db import connect
from storage.repo import Repo

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
log = logging.getLogger("battle-bot")

COMMANDS = [
    BotCommand(command="start", description="Главное меню"),
    BotCommand(command="join", description="Принять участие"),
    BotCommand(command="vote", description="Открыть голосование"),
    BotCommand(command="me", description="Профиль"),
    BotCommand(command="top", description="Таблица лидеров"),
    BotCommand(command="buy", description="Купить голоса"),
    BotCommand(command="help", description="Как это работает"),
]


async def main() -> None:
    config = load_config()
    conn = connect(config.db_path)
    repo = Repo(conn)

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    engine = BattleEngine(bot, repo, config)

    dispatcher = Dispatcher()
    # общие зависимости — прилетают в обработчики как аргументы
    dispatcher["repo"] = repo
    dispatcher["config"] = config
    dispatcher["engine"] = engine

    dispatcher.include_router(admin.router)
    dispatcher.include_router(payments.router)
    dispatcher.include_router(start.router)
    dispatcher.include_router(voting.router)

    watcher = DeadlineWatcher(
        due_deadline=engine.current_deadline,
        on_due=engine.close_round,
    )

    try:
        username = await prepare(bot, config)
    except SetupError as error:
        log.error("Бот не запущен.\n%s", error)
        await bot.session.close()
        conn.close()
        return

    await bot.set_my_commands(COMMANDS)
    log.info("Запущен как @%s", username)

    watcher.start()
    try:
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        await watcher.stop()
        await bot.session.close()
        conn.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Остановлен")
