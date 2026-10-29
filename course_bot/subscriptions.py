"""Проверка подписок: за WARN_DAYS дней — напоминание, в конце срока — из канала."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import sqlite3
import time
from html import escape

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from . import content, db
from .config import Config
from .handlers import _btn, back_menu, fmt_date, remove_from_channel, renew_menu

log = logging.getLogger("course_bot")

CHECK_EVERY = 30 * 60  # секунд


async def check(bot: Bot, conn: sqlite3.Connection, config: Config, now: float | None = None) -> None:
    now = now or time.time()

    for s in db.ending_soon(conn, content.WARN_DAYS * 86400, now):
        # Отмечаем до отправки: если ученик заблокировал бота, не долбим его каждые полчаса.
        db.mark_warned(conn, s["user_id"], now)
        with contextlib.suppress(TelegramAPIError):
            await bot.send_message(s["user_id"],
                                   content.warning(fmt_date(s["paid_until"], config), s["paid_until"] - now),
                                   reply_markup=renew_menu())

    for s in db.overdue(conn, now):
        db.set_status(conn, s["user_id"], "expired")
        await remove_from_channel(bot, conn, s["user_id"])
        with contextlib.suppress(TelegramAPIError):
            await bot.send_message(s["user_id"], content.EXPIRED,
                                   reply_markup=back_menu(_btn("💳 Оплатить снова", "m:buy")))
        note = (f"📭 Подписка закончилась, ученик убран из канала: "
                f"{escape(s['full_name'] or '')} (ID <code>{s['user_id']}</code>)")
        for admin_id in config.admin_ids:
            with contextlib.suppress(TelegramAPIError):
                await bot.send_message(admin_id, note)
        log.info("Подписка %s закончилась", s["user_id"])


async def run(bot: Bot, conn: sqlite3.Connection, config: Config) -> None:
    while True:
        try:
            await check(bot, conn, config)
        except Exception:  # планировщик не должен падать из-за одной ошибки
            log.exception("Ошибка при проверке подписок")
        await asyncio.sleep(CHECK_EVERY)
