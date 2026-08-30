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
from core.autopilot import Autopilot
from core.scheduler import DeadlineWatcher, Ticker
from handlers import (
    admin, broadcast, card, emoji, errors, groups, membership, mychannel, panel,
    payments, referral, start, topup, voting,
)
from services.emoji import PremiumEmojiMiddleware, load_table
from services.retry import RetryMiddleware
from services.startup import SetupError, prepare
from storage.db import connect
from storage.repo import Repo
from storage.settings import Settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
log = logging.getLogger("battle-bot")

COMMANDS = [
    BotCommand(command="start", description="Главное меню"),
    BotCommand(command="join", description="Принять участие"),
    BotCommand(command="vote", description="Открыть голосование"),
    BotCommand(command="card", description="Картинка для сторис"),
    BotCommand(command="me", description="Профиль"),
    BotCommand(command="top", description="Таблица лидеров"),
    BotCommand(command="hall", description="Зал славы: выплаченные призы"),
    BotCommand(command="buy", description="Купить голоса"),
    BotCommand(command="invite", description="Пригласить друзей"),
    BotCommand(command="mychannel", description="Мой канал"),
    BotCommand(command="help", description="Как это работает"),
    BotCommand(command="panel", description="Панель управления (админ)"),
]


# Порядок важен: первый подходящий обработчик забирает событие.
# Страховка панели идёт последней, иначе она перехватывала бы чужие кнопки.
ROUTERS = (
    errors.router,
    groups.router,
    panel.router,
    broadcast.router,
    admin.router,
    emoji.router,
    card.router,
    topup.router,
    payments.router,
    referral.router,
    membership.router,
    mychannel.router,
    start.router,
    voting.router,
    panel.fallback_router,
)


def include_routers(dispatcher: Dispatcher) -> None:
    for router in ROUTERS:
        dispatcher.include_router(router)


async def main() -> None:
    config = load_config()
    conn = connect(config.db_path)
    repo = Repo(conn)

    # настройки из базы перекрывают .env и правятся из панели без перезапуска
    settings = Settings(conn, config)
    settings.bootstrap()

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    # повтор ставим первым, чтобы он обнимал весь запрос целиком
    bot.session.middleware(RetryMiddleware())

    # таблица одна на всех: middleware подменяет по ней, /emojiset её пополняет
    config.premium_emoji = load_table(config.premium_emoji_file)
    # "0" — никогда, "1" — всегда, "auto" — пробуем и отключаем при отказе
    emoji_skip: set[int] = set()
    if config.premium_emoji_in_channel == "0":
        emoji_skip.add(config.channel_id)
    bot.session.middleware(PremiumEmojiMiddleware(config.premium_emoji, emoji_skip))

    engine = BattleEngine(bot, repo, config, emoji_skip, settings)

    dispatcher = Dispatcher()
    # общие зависимости — прилетают в обработчики как аргументы
    dispatcher["repo"] = repo
    dispatcher["config"] = config
    dispatcher["engine"] = engine
    dispatcher["emoji_table"] = config.premium_emoji
    # общий набор чатов без премиум-эмодзи: пополняется при первом отказе
    dispatcher["emoji_skip"] = emoji_skip
    dispatcher["settings"] = settings

    include_routers(dispatcher)

    watcher = DeadlineWatcher(
        due_deadline=engine.current_deadline,
        on_due=engine.close_round,
    )
    # автопилот: напоминания, ежедневный анонс и реклама без участия админа
    autopilot = Ticker(Autopilot(bot, repo, config, settings, engine).tick, every=60.0)

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
    autopilot.start("автопилот")
    try:
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        await watcher.stop()
        await autopilot.stop()
        await bot.session.close()
        conn.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Остановлен")
