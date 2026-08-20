"""Проверки при запуске.

Большинство поломок в таком боте — это не код, а настройка: не тот ID канала,
бот не админ, забыт username. Ловим это сразу, а не в момент первого поста.
"""
from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from config import Config

log = logging.getLogger(__name__)

ADMIN_STATUSES = {"administrator", "creator"}


class SetupError(RuntimeError):
    """Настройка не даёт боту работать — запускаться бессмысленно."""


async def prepare(bot: Bot, config: Config) -> str:
    """Дозаполнить конфиг из Telegram и проверить доступ к каналу.

    Возвращает username бота.
    """
    me = await bot.get_me()
    if not config.bot_username:
        if not me.username:
            raise SetupError("У бота нет username — задайте его в @BotFather.")
        config.bot_username = me.username
        log.info("BOT_USERNAME определён автоматически: @%s", config.bot_username)

    try:
        chat = await bot.get_chat(config.channel_id)
    except TelegramAPIError as error:
        raise SetupError(
            f"Не вижу канал {config.channel_id}: {error}\n"
            "Проверьте CHANNEL_ID (должен быть вида -100...) и что бот добавлен в канал."
        ) from error

    try:
        member = await bot.get_chat_member(config.channel_id, me.id)
    except TelegramAPIError as error:
        raise SetupError(f"Не удалось проверить права бота в канале: {error}") from error

    if member.status not in ADMIN_STATUSES:
        raise SetupError(
            f"Бот не администратор канала «{chat.title}». "
            "Добавьте его в админы с правом публикации сообщений."
        )

    if not config.channel_url:
        config.channel_url = _channel_url(chat)
        log.info("CHANNEL_URL определён автоматически: %s", config.channel_url)

    if not config.admin_ids:
        log.warning("ADMIN_IDS пуст — админские команды будут недоступны всем.")

    log.info("Канал: «%s» (%s)", chat.title, config.channel_id)
    return me.username or ""


def _channel_url(chat) -> str:
    if chat.username:
        return f"https://t.me/{chat.username}"
    if chat.invite_link:
        return chat.invite_link
    raise SetupError(
        "У канала нет публичной ссылки. Укажите CHANNEL_URL вручную "
        "или создайте пригласительную ссылку — она нужна для кнопки «Подписаться»."
    )
