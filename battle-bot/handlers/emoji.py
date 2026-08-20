"""Сбор ID премиум-эмодзи.

У Telegram нет поиска custom_emoji_id по картинке — id приходит только вместе
с сообщением, в котором эмодзи уже стоит. Поэтому владелец присылает боту
сообщение с нужными премиум-эмодзи (или пересылает чужое), а бот достаёт id
из entities и складывает в таблицу.
"""
from __future__ import annotations

import logging
from html import escape

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config import Config
from services.emoji import collect_ids, save_table

log = logging.getLogger(__name__)
router = Router(name="emoji")

HOWTO = (
    "🎨 <b>Премиум-эмодзи</b>\n\n"
    "Пришлите мне сообщение с нужными премиум-эмодзи — я покажу их ID.\n\n"
    "<b>Команды</b>\n"
    "/emojiid — показать ID (ответом на сообщение или в одном сообщении с ним)\n"
    "/emojiset — то же, но сразу сохранить в таблицу\n"
    "/emojilist — что сейчас в таблице\n"
    "/emojidel 🏆 — убрать символ из таблицы\n\n"
    "<i>Ставить премиум-эмодзи в сообщение может аккаунт с Telegram Premium. "
    "Если его нет — перешлите боту любой пост, где такие эмодзи уже стоят.</i>"
)


def _source(message: Message) -> tuple[str | None, list | None]:
    """Откуда брать эмодзи: из ответа на сообщение или из самого сообщения."""
    target = message.reply_to_message or message
    return (target.text or target.caption), (target.entities or target.caption_entities)


def _format(found: dict[str, str]) -> str:
    lines = [f'  "{char}": "{emoji_id}",' for char, emoji_id in found.items()]
    body = "\n".join(lines).rstrip(",")
    return f"<pre>{{\n{escape(body)}\n}}</pre>"


@router.message(Command("emojiid", "emojihelp"))
async def show_ids(message: Message, config: Config) -> None:
    if message.from_user.id not in config.admin_ids:
        return

    text, entities = _source(message)
    found = collect_ids(text, entities)
    if not found:
        await message.answer(HOWTO)
        return

    await message.answer(
        f"Нашёл {len(found)} шт. Скопируйте в <code>premium_emoji.json</code> "
        f"или примените командой /emojiset:\n\n{_format(found)}"
    )


@router.message(Command("emojiset"))
async def set_ids(message: Message, config: Config, emoji_table: dict) -> None:
    if message.from_user.id not in config.admin_ids:
        return

    text, entities = _source(message)
    found = collect_ids(text, entities)
    if not found:
        await message.answer(HOWTO)
        return

    emoji_table.update(found)  # таблица общая с middleware — применяется сразу
    save_table(config.premium_emoji_file, emoji_table)
    log.info("Обновлена таблица премиум-эмодзи: %s", ", ".join(found))

    await message.answer(
        f"✅ Сохранено: {' '.join(found)}\n"
        f"Всего в таблице: {len(emoji_table)}\n\n"
        "Действует сразу, перезапуск не нужен."
    )


@router.message(Command("emojilist"))
async def list_table(message: Message, config: Config, emoji_table: dict) -> None:
    if message.from_user.id not in config.admin_ids:
        return
    if not emoji_table:
        await message.answer("Таблица пуста — бот использует обычные эмодзи.\n\n" + HOWTO)
        return
    await message.answer(
        f"В таблице {len(emoji_table)} символов "
        f"(<code>{escape(config.premium_emoji_file)}</code>):\n\n{_format(emoji_table)}"
    )


@router.message(Command("emojidel"))
async def delete_from_table(message: Message, config: Config, emoji_table: dict) -> None:
    if message.from_user.id not in config.admin_ids:
        return

    argument = (message.text or "").split(maxsplit=1)
    if len(argument) < 2:
        await message.answer("Формат: /emojidel 🏆")
        return

    removed = [char for char in argument[1].strip() if emoji_table.pop(char, None)]
    if not removed:
        await message.answer("Таких символов в таблице нет.")
        return

    save_table(config.premium_emoji_file, emoji_table)
    await message.answer(f"Убрано: {' '.join(removed)}. В таблице осталось {len(emoji_table)}.")
