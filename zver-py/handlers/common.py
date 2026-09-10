"""Мелкие помощники, общие для всех обработчиков."""
from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup

import config
import db
from texts import DEFAULT_LANG

log = logging.getLogger("zver")


def money(v) -> str:
    """50.00 → «50», 50.50 → «50.50». Деньги считаем Decimal, не float."""
    try:
        d = Decimal(v or 0)
    except (InvalidOperation, TypeError):
        return "0"
    return f"{d:.0f}" if d == d.to_integral_value() else f"{d:.2f}"


def parse_amount(raw: str) -> Decimal | None:
    """Разбирает сумму от пользователя: «50», «50.5», «50,5», «1 000»."""
    cleaned = (raw or "").strip().replace(",", ".").replace(" ", "")
    if not cleaned:
        return None
    try:
        val = Decimal(cleaned)
    except InvalidOperation:
        return None
    if val <= 0 or val > Decimal("1000000"):
        return None
    return val.quantize(Decimal("0.01"))


async def lang_of(uid: int) -> str:
    user = await db.get_user(uid)
    return (user or {}).get("lang") or DEFAULT_LANG


def is_admin(uid: int) -> bool:
    return uid in config.ADMINS


async def notify_admins(bot: Bot, text: str,
                        kb: InlineKeyboardMarkup | None = None) -> None:
    """Разослать админам. Один недоступный админ не мешает остальным."""
    for admin_id in config.ADMINS:
        try:
            await bot.send_message(admin_id, text, reply_markup=kb)
        except Exception as e:  # заблокировал бота, удалил чат и т.п.
            log.warning("не доставлено админу %s: %s", admin_id, e)
