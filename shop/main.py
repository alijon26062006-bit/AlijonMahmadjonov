"""Оғози бот: python -m shop.main"""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError, TelegramUnauthorizedError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat

from . import catalog, requisites
from .config import Config, load_config
from .db import Database
from .handlers import build_router
from .middlewares import ButtonStyleFallback, ErrorGuardMiddleware, GuardMiddleware
from .supplier import build_supplier

log = logging.getLogger("shop")

COMMANDS = [
    BotCommand(command="start", description="Оғоз ва менюи асосӣ"),
    BotCommand(command="menu", description="Менюи асосӣ"),
    BotCommand(command="bekor", description="Бекор кардани амали ҷорӣ"),
    BotCommand(command="id", description="ID-и Telegram-и ман"),
]

ADMIN_COMMANDS = COMMANDS + [
    BotCommand(command="admin", description="Панели админ"),
    BotCommand(command="balance", description="Баланси таъминкунанда"),
    BotCommand(command="sku", description="Санҷиши SKU-ҳо"),
    BotCommand(command="rang", description="Санҷиши ранги тугмаҳо"),
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


async def _check_skus(db: Database, cfg: Config, supplier) -> None:
    """Ҳангоми оғоз SKU-ҳоро бо каталоги таъминкунанда месанҷад."""
    if not cfg.has_supplier:
        log.warning(
            "Таъминкунанда хомӯш аст — фармоишҳо дастӣ иҷро мешаванд. "
            "Барои худкор: SHOP_SUPPLIER=fireloot ва SHOP_SUPPLIER_KEY дар .env"
        )
        return
    live = await supplier.products()
    if not live:
        log.warning("Каталоги таъминкунанда гирифта нашуд — SKU-ҳо санҷида нашуданд.")
        return
    missing = [
        f"{row['code']} → {row['sku']}"
        for category in catalog.CATEGORIES
        for row in db.products(category, only_active=False)
        if row["kind"] == "game" and row["sku"] and row["sku"] not in live
    ]
    if missing:
        log.error("SKU-ҳои зерин дар каталоги таъминкунанда нестанд: %s", ", ".join(missing))
    else:
        log.info("Ҳамаи SKU-ҳо дурустанд (%s мол дар каталоги таъминкунанда).", len(live))


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
    requisites.seed(db, cfg)
    supplier = build_supplier(cfg.supplier, cfg.supplier_url, cfg.supplier_key)
    bot = Bot(
        token=cfg.token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    # Агар Telegram рангҳоро нашиносад — бот кор карданашро давом медиҳад.
    bot.session.middleware(ButtonStyleFallback())
    dp = build_dispatcher(db, cfg, supplier)

    try:
        try:
            me = await bot.get_me()
        except TelegramUnauthorizedError:
            raise RuntimeError(
                "SHOP_BOT_TOKEN нодуруст аст — Telegram онро қабул накард. "
                "Токенро аз @BotFather бо /mybots санҷед."
            ) from None

        log.info("Бот омода: @%s (таъминкунанда: %s)", me.username, supplier.name)
        await _check_skus(db, cfg, supplier)

        await bot.set_my_commands(COMMANDS)
        for admin_id in cfg.admin_ids:
            try:
                await bot.set_my_commands(
                    ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=admin_id)
                )
            except Exception as exc:
                log.warning("Фармонҳои админ барои %s танзим нашуданд: %s", admin_id, exc)

        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        # Ҳатто ҳангоми хатогӣ ҳама чиз тоза баста мешавад.
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
    except TelegramNetworkError as exc:
        print(f"❌ Telegram дастнорас аст: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
