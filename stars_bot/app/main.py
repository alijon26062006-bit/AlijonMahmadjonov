"""Точка входа. Запуск: python -m app.main (из папки stars_bot)."""
from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramNetworkError, TelegramUnauthorizedError
from aiogram.types import BotCommand, BotCommandScopeChat

from app import db, runtime
from app.config import settings
from app.handlers import (
    admin, broadcast, deposit, menu, panel, profile, shop, support,
)
from app.middlewares.emoji_guard import CustomEmojiGuard
from app.middlewares.guard import UserGuardMiddleware
from app.services.billing import make_sender
from app.services.fragment import build_provider
from app.services.pricing import auto_price_loop

log = logging.getLogger(__name__)

USER_COMMANDS = [
    BotCommand(command="start", description="Главное меню"),
    BotCommand(command="menu", description="Главное меню"),
]

ADMIN_COMMANDS = USER_COMMANDS + [
    BotCommand(command="panel", description="Админ-панель"),
]


def readiness() -> tuple[list[str], list[str]]:
    """Что мешает работать (blockers) и что стоит доделать (warnings)."""
    blockers, warnings = [], []

    if not settings.admin_ids:
        blockers.append(
            "ADMIN_IDS пуст — некому подтверждать пополнения, "
            "деньги будут зависать. Свой ID узнайте у @userinfobot."
        )
    if not runtime.get("pay_card_number"):
        blockers.append(
            "Не заданы реквизиты карты — покупателям некуда переводить деньги. "
            "Задайте их в /panel → Реквизиты или в .env."
        )
    if runtime.star_price() <= 0:
        blockers.append("Цена звезды должна быть больше нуля (/panel → Цены).")

    if settings.fragment_mode.lower() != "api":
        warnings.append(
            "FRAGMENT_MODE=mock — бот работает, но звёзды НЕ отправляются. "
            "Для реальных продаж поставьте api."
        )
    if not settings.support_username:
        warnings.append("SUPPORT_USERNAME пуст — покупателям некуда писать при проблеме.")

    return blockers, warnings


def print_readiness() -> bool:
    """Печатает отчёт о готовности. False — запускаться нельзя."""
    blockers, warnings = readiness()
    for item in warnings:
        log.warning("⚠️  %s", item)
    for item in blockers:
        log.error("❌ %s", item)
    if blockers:
        log.error(
            "Бот не запущен: сначала исправьте пункты выше. "
            "Проще всего — запустить `python setup.py`."
        )
        return False
    return True


async def main() -> None:
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    # Если премиум-эмодзи перестанут приниматься, бот не должен замолчать.
    bot.session.middleware(CustomEmojiGuard())
    conn = await db.connect()
    await db.init(conn)
    # Настройки из панели грузим до проверки готовности: реквизиты могли
    # быть заданы через бота, а не в .env.
    await runtime.load(conn)

    if not print_readiness():
        await conn.close()
        await bot.session.close()
        raise SystemExit(1)

    # ManualPayer нужен только режиму mystars: он присылает владельцу
    # ссылку на оплату вместо того, чтобы подписывать перевод самому.
    payer = None
    if settings.fragment_mode.strip().lower() in ("mystars", "faas"):
        from app.services.mystars import ManualPayer

        payer = ManualPayer(make_sender(bot))
    provider = build_provider(payer)

    dp = Dispatcher(conn=conn, provider=provider)
    dp.message.middleware(UserGuardMiddleware())
    dp.callback_query.middleware(UserGuardMiddleware())

    # Админские роутеры первыми: их фильтр отсекает чужие апдейты
    # и пропускает их дальше по цепочке.
    dp.include_router(panel.router)
    dp.include_router(broadcast.router)
    dp.include_router(admin.router)
    dp.include_router(menu.router)
    dp.include_router(shop.router)
    dp.include_router(deposit.router)
    dp.include_router(profile.router)
    dp.include_router(support.router)

    try:
        me = await bot.me()
        await bot.set_my_commands(USER_COMMANDS)
        # У админов в меню команд появляется /panel.
        for admin_id in settings.admin_ids:
            try:
                await bot.set_my_commands(
                    ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=admin_id)
                )
            except TelegramAPIError:
                log.debug("Не смог поставить команды админу %s", admin_id)
    except TelegramUnauthorizedError:
        log.error(
            "❌ Telegram отверг токен. Проверьте BOT_TOKEN в .env — возможно, "
            "он отозван. Новый берётся у @BotFather: /mybots → бот → API Token."
        )
        await _shutdown(bot, conn, provider)
        raise SystemExit(1) from None
    except TelegramNetworkError as exc:
        log.error(
            "❌ Нет связи с Telegram: %s\n"
            "Проверьте интернет. Если Telegram блокируется провайдером — "
            "запускайте бота на сервере за границей.", exc,
        )
        await _shutdown(bot, conn, provider)
        raise SystemExit(1) from None
    except TelegramAPIError as exc:
        log.error("❌ Telegram вернул ошибку при старте: %s", exc)
        await _shutdown(bot, conn, provider)
        raise SystemExit(1) from None

    log.info("✅ Запущен @%s. Режим Fragment: %s", me.username, settings.fragment_mode)
    log.info("   Админы: %s", ", ".join(map(str, settings.admin_ids)))

    # Автоцены держат наценку постоянной, пока курс гуляет.
    pricing_task = asyncio.create_task(auto_price_loop(provider, bot))

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        pricing_task.cancel()
        with suppress(asyncio.CancelledError):
            await pricing_task
        await _shutdown(bot, conn, provider)


async def _shutdown(bot: Bot, conn, provider) -> None:
    """Аккуратно закрыть всё: незакрытое соединение с базой держит процесс."""
    await provider.close()
    await conn.close()
    await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Остановлено")
    except SystemExit as exc:
        # Код выхода должен дойти до systemd, иначе упавший бот
        # будет выглядеть как штатно завершённый и не перезапустится.
        raise SystemExit(exc.code) from None
