"""Что бот знает о группе: права, размер, ссылка.

Всё спрашивается у Telegram в момент открытия карточки, а не берётся из
базы: права меняют, людей добавляют, ссылку отзывают — сохранённая копия
устарела бы через час.
"""
from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

log = logging.getLogger(__name__)

# права, без которых чистка не работает или работает наполовину
NEEDED = (
    ("can_delete_messages", "удалять сообщения"),
    ("can_restrict_members", "banить участников"),
)


async def describe(bot: Bot, chat_id: int) -> dict:
    """Собрать карточку группы. Что не удалось узнать — остаётся None."""
    card: dict = {
        "chat_id": chat_id,
        "title": None,
        "link": None,
        "members": None,
        "status": None,
        "rights": {},
        "missing": [],
        "error": "",
    }

    try:
        chat = await bot.get_chat(chat_id)
    except TelegramAPIError as error:
        card["error"] = str(error)
        return card

    card["title"] = chat.title
    card["link"] = (
        f"https://t.me/{chat.username}" if chat.username else (chat.invite_link or None)
    )

    try:
        card["members"] = await bot.get_chat_member_count(chat_id)
    except TelegramAPIError as error:
        log.info("Не узнал число участников %s: %s", chat_id, error)

    try:
        me = await bot.get_chat_member(chat_id=chat_id, user_id=(await bot.me()).id)
    except TelegramAPIError as error:
        card["error"] = str(error)
        return card

    card["status"] = me.status
    for field, title in NEEDED:
        allowed = bool(getattr(me, field, False))
        card["rights"][title] = allowed
        if not allowed:
            card["missing"].append(title)
    return card
