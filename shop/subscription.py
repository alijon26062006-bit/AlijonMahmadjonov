"""Обунаи ҳатмӣ ба каналҳо.

Админ ҳар қадар канал илова карда метавонад. То он даме, ки харидор ба
ҲАМАИ онҳо обуна нашавад, бот кор намекунад.
"""

from __future__ import annotations

import logging

from aiogram import Bot

from .db import Database

log = logging.getLogger(__name__)

#: Ин ҳолатҳо маънои «обуна шудааст»-ро доранд.
MEMBER_STATUSES = ("member", "administrator", "creator")


def channel_link(row) -> str:
    """Ҳаволаи кушодани канал."""
    link = (row["link"] or "").strip()
    if link:
        return link
    chat = (row["chat_id"] or "").strip()
    if chat.startswith("@"):
        return f"https://t.me/{chat[1:]}"
    return ""


async def missing_channels(bot: Bot, db: Database, user_id: int) -> list:
    """Каналҳое, ки корбар ба онҳо обуна нашудааст.

    Агар каналро тафтиш карда натавонем (бот дар он ҷо админ нест ё канал
    нест шудааст), онро ҳамчун «обуна шуда» мешуморем — вагарна ҳамаи
    харидорон бе гуноҳ маҳрум мешаванд.
    """
    missing = []
    for row in db.channels():
        try:
            member = await bot.get_chat_member(chat_id=row["chat_id"], user_id=user_id)
        except Exception as exc:
            log.warning("Каналро тафтиш карда натавонистам %s: %s", row["chat_id"], exc)
            continue
        if member.status not in MEMBER_STATUSES:
            missing.append(row)
    return missing


async def is_subscribed(bot: Bot, db: Database, user_id: int) -> bool:
    return not await missing_channels(bot, db, user_id)
