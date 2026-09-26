"""Оғози бот: python -m shop.main"""

from __future__ import annotations

import asyncio
import html
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError, TelegramUnauthorizedError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat

from . import catalog, guard, requisites
from .config import ROOT, Config, load_config
from .db import Database
from .fulfillment import resume_in_background
from .fulfillment import shutdown as fulfillment_shutdown
from .handlers import build_router
from .middlewares import (
    ButtonStyleFallback,
    ConflictWatch,
    ErrorGuardMiddleware,
    GuardMiddleware,
)
from .donatix import DonatixSupplier
from .supplier import RouterSupplier, build_supplier

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


def build_shop_supplier(cfg: Config, db: Database) -> RouterSupplier:
    """FireLoot барои бозиҳо, Donatix барои Stars ва Premium (агар калид бошад)."""
    main = build_supplier(cfg.supplier, cfg.supplier_url, cfg.supplier_key)
    telegram = None
    if cfg.has_donatix:
        # Рақами фармоиш аллакай беҳамтост (пешванди база + рақам), ниг. fulfillment.
        telegram = DonatixSupplier(
            cfg.donatix_key, cfg.donatix_url, key_prefix=db.order_key_prefix()
        )
    return RouterSupplier(main, telegram)


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


async def _check_donatix(db: Database, supplier) -> None:
    """Ҳангоми оғоз: калиди Donatix кор мекунад ва ҳар Stars/Premium моли худро дорад."""
    telegram = getattr(supplier, "telegram", None)
    if telegram is None:
        log.info("Donatix хомӯш — Stars аз FireLoot, Premium дастӣ.")
        return
    bal = await telegram.balance()
    if not bal.get("ok"):
        log.error("Donatix: калид кор намекунад — %s", bal.get("error"))
        return
    log.info("Donatix: баланс %s %s", bal.get("balance"), bal.get("currency"))
    missing = []
    for category, kind in ((catalog.CAT_STARS, "stars"), (catalog.CAT_PREMIUM, "premium")):
        for row in db.products(category, only_active=False):
            if row["kind"] == kind and await telegram.resolve(kind, row["amount"]) is None:
                missing.append(row["code"])
    if missing:
        log.error("Donatix барои ин молҳо мол надорад: %s", ", ".join(missing))


HOST_KEY = "last_host"


async def _tell_admins(bot: Bot, cfg: Config, text: str) -> None:
    for admin_id in cfg.admin_ids:
        try:
            await bot.send_message(admin_id, text)
        except Exception as exc:
            log.warning("Ба админ %s нарасид: %s", admin_id, exc)


def _conflict_notifier(cfg: Config, here: str):
    async def notify(bot: Bot) -> None:
        await _tell_admins(
            bot, cfg,
            "🚨 <b>Ҳамин бот дар ҷои дигар низ кор мекунад!</b>\n\n"
            "Telegram гуфт: бо ин токен ду нусха навсозӣ мегиранд. Харидорон байни "
            "онҳо тақсим мешаванд ва пули як қисм дар базаи дигар менависад.\n\n"
            f"🖥 Ин нусха: <code>{html.escape(here)}</code>\n\n"
            "Нусхаи дигарро фавран хомӯш кунед. Дар ҳар сервер санҷед:  "
            "<code>bot doctor</code>",
        )
    return notify


async def _announce_host(bot: Bot, db: Database, cfg: Config, here: str) -> None:
    """Агар бот дар сервер ё папкаи нав сар шуда бошад — ба админ хабар медиҳем."""
    before = db.setting(HOST_KEY)
    db.set_setting(HOST_KEY, here)
    if before and before != here:
        await _tell_admins(
            bot, cfg,
            "🟢 <b>Бот дар ҷои нав оғоз шуд.</b>\n\n"
            f"🖥 Ҳозир: <code>{html.escape(here)}</code>\n"
            f"🗄 Пештар: <code>{html.escape(before)}</code>\n\n"
            "Агар ин кӯчидан набуд — нусхаи дуюм кор мекунад. Нусхаи кӯҳнаро хомӯш кунед.",
        )


async def run() -> None:
    cfg = load_config()
    logging.basicConfig(
        level=getattr(logging, cfg.log_level, logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    # Пеш аз ҳама: дар ин ҷо бот бояд танҳо як бор ва танҳо дар сервери ҷорӣ кор кунад.
    guard.check_not_moved(cfg.db_path.parent)
    instance_lock = guard.acquire_instance_lock(cfg.token, ROOT)
    here = f"{guard.host_label()} {ROOT}"
    if not cfg.admin_ids:
        log.warning(
            "SHOP_ADMIN_IDS холӣ аст — панели админ дастрас намешавад. "
            "ID-и худро аз @userinfobot гиред."
        )

    db = Database(cfg.db_path)
    requisites.seed(db, cfg)
    supplier = build_shop_supplier(cfg, db)
    bot = Bot(
        token=cfg.token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    # Агар Telegram рангҳоро нашиносад — бот кор карданашро давом медиҳад.
    bot.session.middleware(ButtonStyleFallback())
    bot.session.middleware(ConflictWatch(_conflict_notifier(cfg, here)))
    dp = build_dispatcher(db, cfg, supplier)

    try:
        try:
            me = await bot.get_me()
        except TelegramUnauthorizedError:
            raise RuntimeError(
                "SHOP_BOT_TOKEN нодуруст аст — Telegram онро қабул накард. "
                "Токенро аз @BotFather бо /mybots санҷед."
            ) from None

        log.info("Бот омода: @%s (таъминкунанда: %s) — %s", me.username, supplier.name, here)
        await _announce_host(bot, db, cfg, here)
        await _check_skus(db, cfg, supplier)
        await _check_donatix(db, supplier)

        await bot.set_my_commands(COMMANDS)
        for admin_id in cfg.admin_ids:
            try:
                await bot.set_my_commands(
                    ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=admin_id)
                )
            except Exception as exc:
                log.warning("Фармонҳои админ барои %s танзим нашуданд: %s", admin_id, exc)

        await bot.delete_webhook(drop_pending_updates=True)
        # Фармоишҳое, ки ҳангоми хомӯшшавии қаблӣ нимкора монданд, то охир
        # расонида мешаванд — дар паси парда, то бот фавран ҷавоб диҳад.
        resume_in_background(bot, db, cfg, supplier)
        await dp.start_polling(bot)
    finally:
        # Ҳатто ҳангоми хатогӣ ҳама чиз тоза баста мешавад.
        await fulfillment_shutdown()
        await supplier.close()
        await bot.session.close()
        db.close()
        instance_lock.close()


def main() -> None:
    try:
        asyncio.run(run())
    except guard.StartRefused as exc:
        logging.getLogger("shop").error("%s", exc)
        print(f"❌ {exc}", file=sys.stderr)
        sys.exit(guard.EXIT_REFUSED)
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
