"""Гейт подписки: голосовать может только подписчик канала."""
from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

log = logging.getLogger(__name__)

SUBSCRIBED = {"creator", "administrator", "member"}


async def is_subscribed(bot: Bot, channel_id: int, user_id: int) -> bool:
    """Подписан ли человек на канал.

    При ошибке API отвечаем «нет». Раньше здесь был обратный ответ, но тогда
    любой сбой Telegram открывал голосование всем подряд, а подписка
    обязательна. Показать экран «подпишитесь» и дать нажать «Я подписался»
    безопаснее, чем засчитать голос человека, которого мы не проверили.
    """
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
    except TelegramAPIError as error:
        log.warning("Не удалось проверить подписку %s на %s: %s", user_id, channel_id, error)
        return False
    return member.status in SUBSCRIBED


async def diagnose(bot: Bot, channel_id: int, user_id: int) -> str:
    """Почему проверка не работает — для панели администратора.

    Пустая строка означает, что всё в порядке: бот видит канал и может
    спрашивать статус участников.
    """
    try:
        await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
    except TelegramAPIError as error:
        return str(error)
    return ""
