"""Гейт подписки: голосовать может только подписчик канала."""
from __future__ import annotations

import logging
import time

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

log = logging.getLogger(__name__)

SUBSCRIBED = {"creator", "administrator", "member"}

# Подписка проверяется на каждый голос, а голосов у популярного батла тысячи.
# Спрашивать Telegram каждый раз — лишний сетевой вызов на нажатие кнопки и
# верный путь во флуд-контроль, из-за которого «крутится и ничего не
# происходит». Поэтому положительный ответ ненадолго запоминается.
#
# Отказ не кэшируется никогда: человек подписывается и сразу жмёт
# «Я подписался» — он должен пройти в ту же секунду.
CACHE_TTL = 120.0
_cache: dict[tuple[int, int], float] = {}
MAX_CACHE = 50_000  # страховка от разрастания памяти на большом батле


def _fresh(key: tuple[int, int], now: float) -> bool:
    until = _cache.get(key)
    return until is not None and until > now


def remember(channel_id: int, user_id: int, now: float | None = None) -> None:
    moment = time.monotonic() if now is None else now
    if len(_cache) >= MAX_CACHE:
        _cache.clear()
    _cache[(channel_id, user_id)] = moment + CACHE_TTL


def forget(channel_id: int | None = None, user_id: int | None = None) -> None:
    """Забыть отметку — например, когда человек нажал «Я подписался»."""
    if channel_id is None or user_id is None:
        _cache.clear()
        return
    _cache.pop((channel_id, user_id), None)


async def is_subscribed(
    bot: Bot, channel_id: int, user_id: int, use_cache: bool = True
) -> bool:
    """Подписан ли человек на канал.

    При ошибке API отвечаем «нет». Раньше здесь был обратный ответ, но тогда
    любой сбой Telegram открывал голосование всем подряд, а подписка
    обязательна. Показать экран «подпишитесь» и дать нажать «Я подписался»
    безопаснее, чем засчитать голос человека, которого мы не проверили.
    """
    key = (channel_id, user_id)
    now = time.monotonic()
    if use_cache and _fresh(key, now):
        return True

    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
    except TelegramAPIError as error:
        log.warning("Не удалось проверить подписку %s на %s: %s", user_id, channel_id, error)
        return False

    subscribed = member.status in SUBSCRIBED
    if subscribed:
        remember(channel_id, user_id, now)
    else:
        _cache.pop(key, None)  # отписался — забываем прошлую отметку
    return subscribed


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
