"""Оғози бот: python -m shop.main"""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from .config import Config, load_config
from .db import Database
from .handlers import build_router
from .middlewares import ErrorGuardMiddleware, GuardMiddleware
from .supplier import build_supplier

log = logging.getLogger("shop")

COMMANDS = [
    BotCommand(command="start", description="Оғоз ва менюи асосӣ"),
    BotCommand(command="menu", description="Менюи асосӣ"),
    BotCommand(command="bekor", description="Бекор кардани амали ҷорӣ"),
    BotCommand(command="id", description="ID-и Telegram-и ман"),
]


def build_dispatcher(db: Database, cfg: Config, supplier) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp["db"] = db
    dp["cfg"] = cfg
    dp["supplier"] = supplier
    dp.update.outer_middleware(ErrorGuardMiddleware())
    dp.update.outer_middleware(GuardMiddleware(db, cfg))
    dp.include_router(build_router())
    return dp


async def run() -> None:
    cfg = load_config()
    logging.basicConfig(
        level=getattr(logging, cfg.log_level, logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    if not cfg.admin_ids:
        log.warning(
            "SHOP_ADMIN_IDS холӣ аст — панели админ дастрас намешавад. "
            "ID-и худро аз @userinfobot гиред."
        )

    db = Database(cfg.db_path)
    supplier = build_supplier(cfg.supplier, cfg.supplier_url, cfg.supplier_key)
    bot = Bot(
        token=cfg.token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = build_dispatcher(db, cfg, supplier)

    me = await bot.get_me()
    log.info("Бот омода: @%s (таъминкунанда: %s)", me.username, supplier.name)
    try:
        await bot.set_my_commands(COMMANDS)
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await supplier.close()
        await bot.session.close()
        db.close()


def main() -> None:
    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit):
        print("\nБот хомӯш шуд.")
    except RuntimeError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
