"""Запуск бота. Long polling: ни домена, ни белого IP не нужно."""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import CallbackQuery, ErrorEvent, Message, TelegramObject

from . import db, handlers, reports
from .config import Config, load_config
from .stt import Recognizer

log = logging.getLogger("counter")


class AccessMiddleware(BaseMiddleware):
    """Если в .env перечислены id — пускаем только их. Пусто — пускаем всех."""

    def __init__(self, allowed: frozenset[int]) -> None:
        self.allowed = allowed

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not self.allowed:
            return await handler(event, data)
        user = data.get("event_from_user")
        if user is not None and user.id in self.allowed:
            return await handler(event, data)
        log.warning("Чужой стучится: %s", getattr(user, "id", "?"))
        if isinstance(event, Message):
            await event.answer("Этот бот не для общего пользования.")
        elif isinstance(event, CallbackQuery):
            await event.answer("Нет доступа", show_alert=True)
        return None


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)


async def run(config: Config) -> None:
    config.ensure_dirs()
    if not reports.register_fonts(config.font_path, config.font_bold_path):
        log.warning("Шрифт с кириллицей не найден — PDF будет латиницей (Excel не пострадает)")

    conn = db.connect(config.db_path)
    recognizer = Recognizer(config.model_path)

    bot = Bot(config.telegram_token, default=DefaultBotProperties(parse_mode=None))
    dispatcher = Dispatcher()

    access = AccessMiddleware(config.allowed_user_ids)
    dispatcher.message.outer_middleware(access)
    dispatcher.callback_query.outer_middleware(access)

    dispatcher["conn"] = conn
    dispatcher["config"] = config
    dispatcher["recognizer"] = recognizer
    dispatcher.include_router(handlers.router)

    @dispatcher.errors()
    async def on_error(event: ErrorEvent) -> bool:
        """Любая непойманная ошибка: пишем в лог и извиняемся, но не падаем."""
        log.exception("Ошибка в обработчике: %s", event.exception)
        message = getattr(event.update, "message", None) or getattr(
            getattr(event.update, "callback_query", None), "message", None
        )
        if message is not None:
            try:
                await message.answer(
                    "Что-то пошло не так, но все записи целы. Попробуй ещё раз "
                    "или нажми «📋 Список», чтобы проверить."
                )
            except Exception:  # noqa: BLE001
                pass
        return True

    # Модель грузим параллельно опросу — бот отвечает сразу, не ждёт её.
    warmup = asyncio.create_task(recognizer.prepare())

    me = await bot.get_me()
    log.info("Запущен как @%s. База: %s", me.username, config.db_path)
    log.info("Голосовая модель: %s", config.model_path)
    if config.allowed_user_ids:
        log.info("Доступ только для: %s", sorted(config.allowed_user_ids))

    try:
        await bot.delete_webhook(drop_pending_updates=False)
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        warmup.cancel()
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
