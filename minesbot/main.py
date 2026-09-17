"""Точка входа: собирает приложение и запускает опрос Telegram.

Запуск:  python -m minesbot
"""

from __future__ import annotations

import logging
import sys

from telegram import BotCommand
from telegram.ext import (
    AIORateLimiter,
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from . import config as config_module
from . import db, handlers

log = logging.getLogger("minesbot")

COMMANDS = [
    BotCommand("bet", "Бозӣ сар кардан: /bet 100"),
    BotCommand("balance", "Баланси ту"),
    BotCommand("bonus", "Тӯҳфаи ройгон"),
    BotCommand("mines", "Шумораи минаҳо: /mines 3"),
    BotCommand("send", "Пул фиристодан (reply)"),
    BotCommand("top", "Беҳтаринҳо"),
    BotCommand("stats", "Омори ту"),
    BotCommand("help", "Кӯмак"),
]


async def _post_init(app: Application) -> None:
    await app.bot.set_my_commands(COMMANDS)
    me = await app.bot.get_me()
    log.info("бот запущен: @%s (id %s)", me.username, me.id)


async def _post_shutdown(app: Application) -> None:
    conn = app.bot_data.get("conn")
    if conn is not None:
        conn.close()
        log.info("база закрыта")


def build(cfg: config_module.Config) -> Application:
    app = (
        ApplicationBuilder()
        .token(cfg.token)
        # Очередь запросов к Telegram: бот не словит flood-limit на активном чате.
        .rate_limiter(AIORateLimiter())
        # Нажатия разных людей обрабатываются параллельно; за целостность
        # денег отвечают транзакции в db.py и блокировки в handlers.py.
        .concurrent_updates(True)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )
    app.bot_data["config"] = cfg
    app.bot_data["conn"] = db.connect(cfg.db_path)

    app.add_handler(CommandHandler(["start", "help"], handlers.start))
    app.add_handler(CommandHandler("balance", handlers.balance_cmd))
    app.add_handler(CommandHandler("bonus", handlers.bonus))
    app.add_handler(CommandHandler("bet", handlers.bet))
    app.add_handler(CommandHandler("mines", handlers.mines_cmd))
    app.add_handler(CommandHandler("send", handlers.send))
    app.add_handler(CommandHandler("top", handlers.top))
    app.add_handler(CommandHandler("stats", handlers.stats))
    app.add_handler(CallbackQueryHandler(handlers.buttons, pattern=r"^mn:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.text))
    app.add_error_handler(handlers.on_error)
    return app


def main() -> int:
    try:
        cfg = config_module.load()
    except config_module.ConfigError as error:
        print(f"\n❌ {error}\n", file=sys.stderr)
        return 2

    logging.basicConfig(
        level=getattr(logging, cfg.log_level, logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s · %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    app = build(cfg)
    # drop_pending_updates: после простоя бот не отвечает на вчерашние нажатия.
    app.run_polling(drop_pending_updates=True)
    return 0


if __name__ == "__main__":  # запуск только по команде, а не при импорте
    raise SystemExit(main())
