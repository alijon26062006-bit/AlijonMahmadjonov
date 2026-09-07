"""Точка входа: веб-сервер дуэли и телеграм-бот в одном процессе."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
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

    async def notify(
        user_id: int,
        text: str,
        button: str | None = None,
        url: str | None = None,
    ) -> None:
        """Сообщение в чат: итог матча или вызов на бой.

        С кнопкой приглашение открывается одним касанием прямо из чата — и
        сразу с данными об игроке, потому что кнопка под сообщением.
        Заблокировал бота — молча пропускаем.
        """

        markup = None
        if button and url:
            markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=button, web_app=WebAppInfo(url=url))]
                ]
            )
        with contextlib.suppress(Exception):
            await bot.send_message(user_id, text, reply_markup=markup)

    hub = Hub(
        config,
        conn,
        notify=notify,
        bot_username=me.username or "",
        main_app=bool(getattr(me, "has_main_web_app", False)),
    )
    runner = web.AppRunner(make_app(hub))
    await runner.setup()
    site = web.TCPSite(runner, config.host, config.port)
    await site.start()
    log.info("Сервер на http://%s:%s, Mini App: %s", config.host, config.port, config.webapp_url)

    dispatcher = Dispatcher()
    dispatcher.include_router(bot_module.router)
    dispatcher["config"] = config
    dispatcher["conn"] = conn
    dispatcher["hub"] = hub

    with contextlib.suppress(Exception):
        await bot_module.setup_bot_ui(bot, config)

    log.info("Бот @%s готов. База: %s", me.username, config.db_path)
    if not hub.main_app:
        log.warning(
            "У бота не настроено главное мини-приложение. Ссылка-приглашение "
            "будет открывать переписку, а не игру, и другу придётся нажать "
            "лишний раз. Как включить одно касание: @BotFather → /mybots → "
            "@%s → Bot Settings → Configure Mini App → Enable Mini App → %s",
            me.username, config.webapp_url,
        )
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
