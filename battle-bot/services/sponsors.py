"""Обязательная подписка — спонсорские каналы.

Голосовать и участвовать можно только подписчикам. По умолчанию проверяется
главный канал: именно там выходит анонс набора, а в канал с самими парами
человек попадает по ссылке из поста, и подписка там не требуется.

Список задаётся в панели, поэтому каналов может быть и несколько.
"""
from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import Config
from services.keyboards import BLUE, GREEN
from services.subscription import is_subscribed
from storage.settings import Settings

log = logging.getLogger(__name__)

# ссылки на каналы меняются редко — держим их в памяти процесса
_links: dict[int, tuple[str, str]] = {}


def required(config: Config, settings: Settings) -> list[int]:
    """Каналы, подписка на которые обязательна."""
    raw = (settings.get("sponsor_channels") or "").replace(";", ",")
    ids = []
    for part in raw.split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            ids.append(int(part))
    if ids:
        return ids

    # ничего не задано — требуем главный канал, а если его нет, канал батлов
    main = settings.get("main_channel_id")
    return [main] if main else [config.channel_id]


async def describe(bot: Bot, channel_id: int) -> tuple[str, str]:
    """Название и ссылка канала для кнопки «Подписаться»."""
    if channel_id in _links:
        return _links[channel_id]

    title, url = "Канал", ""
    try:
        chat = await bot.get_chat(channel_id)
        title = chat.title or title
        url = f"https://t.me/{chat.username}" if chat.username else (chat.invite_link or "")
    except TelegramAPIError as error:
        log.warning("Не удалось узнать канал %s: %s", channel_id, error)

    if url:
        _links[channel_id] = (title, url)
    return title, url


async def missing(
    bot: Bot, config: Config, settings: Settings, user_id: int
) -> list[tuple[str, str]]:
    """На какие обязательные каналы человек ещё не подписан."""
    if not settings.get("require_subscription"):
        return []

    result = []
    for channel_id in required(config, settings):
        if await is_subscribed(bot, channel_id, user_id):
            continue
        title, url = await describe(bot, channel_id)
        result.append((title, url))
    return result


def keyboard(channels: list[tuple[str, str]], retry: str) -> InlineKeyboardMarkup:
    """Кнопка на каждый неподписанный канал плюс «Я подписался»."""
    rows = [
        [InlineKeyboardButton(text=f"Подписаться на {title} ↗", url=url, style=GREEN)]
        for title, url in channels
        if url
    ]
    rows.append([InlineKeyboardButton(text="✅ Я подписался", callback_data=retry, style=BLUE)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def text(channels: list[tuple[str, str]]) -> str:
    from services import texts

    listing = "\n".join(f"• <b>{title}</b>" for title, _ in channels)
    word = texts.plural(len(channels), "канал", "канала", "каналов")
    return (
        f"⚠️ <b>Нужна подписка</b>\n"
        f"{texts.RULE}\n\n"
        f"Чтобы участвовать и голосовать, подпишитесь на {len(channels)} {word}:\n\n"
        f"{listing}\n\n"
        "<i>После подписки нажмите «Я подписался».</i>"
    )
