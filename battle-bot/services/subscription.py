"""Гейт подписки: голосовать может только подписчик канала."""
from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

log = logging.getLogger(__name__)

SUBSCRIBED = {"creator", "administrator", "member"}


async def is_subscribed(bot: Bot, channel_id: int, user_id: int) -> bool:
    """Проверить подписку. При ошибке API пропускаем — лучше дать проголосовать,
    чем заблокировать всех из-за сбоя Telegram."""
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
    except TelegramAPIError as error:
        log.warning("Не удалось проверить подписку %s: %s", user_id, error)
        return True
    return member.status in SUBSCRIBED
