"""Главный пост — постоянная витрина батлов в главном канале.

Одно фото с подписью и кнопкой «Участвую», которая ведёт в бота. Панель его
публикует, обновляет и закрепляет; счётчик участников подтягивается сам.
"""
from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import Config
from services import links, texts
from services.emoji import leading_emoji
from services.keyboards import GREEN
from services.tg import is_not_modified
from storage.repo import Repo
from storage.settings import Settings

log = logging.getLogger(__name__)

JOIN_BUTTON = "⚡ Участвовать"


def default_text(prizes: list[int]) -> str:
    """Витрина набора: заголовок, призы в цитате и указание на кнопку."""
    places = "\n".join(
        f"{index} место — <b>{amount}</b>⭐"
        for index, amount in enumerate(prizes, start=1)
    )
    return (
        "⚔️ <b>НАБОР НА БИТВУ НИКОВ</b>\n\n"
        "🎁 <b>Призы:</b>\n"
        f"<blockquote>{places}</blockquote>\n\n"
        "↓ <b>Участвовать по кнопке</b>"
    )


def caption(settings: Settings, participants: int) -> str:
    body = settings.get("main_post_text") or default_text(settings.get("prizes"))
    if participants:
        word = texts.plural(participants, "участник", "участника", "участников")
        body += f"\n\n👥 Уже в игре: <b>{participants} {word}</b>"
    return body


def keyboard(bot_username: str, emoji_table: dict[str, str] | None = None) -> InlineKeyboardMarkup:
    text, emoji_id = leading_emoji(JOIN_BUTTON, emoji_table or {})
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=text,
                    url=links.join_link(bot_username),
                    style=GREEN,
                    icon_custom_emoji_id=emoji_id,
                )
            ]
        ]
    )


def state(repo: Repo, config: Config, settings: Settings) -> dict:
    """Что показать на экране «Канал» в панели."""
    battle = repo.current_battle()
    return {
        "main_channel_id": settings.get("main_channel_id"),
        "photo": settings.get("main_post_photo"),
        "text": settings.get("main_post_text"),
        "message_id": settings.get("main_post_message_id"),
        "battle_posts": len(repo.posts(chat_id=config.channel_id)),
        "participants": repo.participant_count(int(battle["id"])) if battle else 0,
    }


class MainPostError(RuntimeError):
    """Понятная человеку причина, почему пост не вышел."""


async def publish(bot: Bot, repo: Repo, config: Config, settings: Settings) -> int:
    """Опубликовать главный пост или обновить уже опубликованный."""
    channel_id = settings.get("main_channel_id")
    if not channel_id:
        raise MainPostError("Сначала задайте ID главного канала.")

    photo = settings.get("main_post_photo")  # необязательно: без фото выйдет текстовый пост
    battle = repo.current_battle()
    participants = repo.participant_count(int(battle["id"])) if battle else 0
    text = caption(settings, participants)
    markup = keyboard(config.bot_username, config.premium_emoji)
    existing = settings.get("main_post_message_id")

    if existing:
        try:
            edit = bot.edit_message_caption if photo else bot.edit_message_text
            field = {"caption": text} if photo else {"text": text}
            await edit(
                chat_id=channel_id, message_id=existing, reply_markup=markup, **field
            )
            return existing
        except TelegramAPIError as error:
            if is_not_modified(error):
                return existing
            log.info("Не удалось обновить главный пост, публикую заново: %s", error)

    try:
        if photo:
            message = await bot.send_photo(
                chat_id=channel_id, photo=photo, caption=text, reply_markup=markup
            )
        else:
            message = await bot.send_message(
                chat_id=channel_id, text=text, reply_markup=markup,
                disable_web_page_preview=True,
            )
    except TelegramAPIError as error:
        raise MainPostError(
            f"Telegram не принял пост: {error}\n\n"
            "Проверьте, что бот — администратор главного канала с правом публикации."
        ) from error

    settings.set("main_post_message_id", message.message_id)
    repo.record_post(channel_id, message.message_id, None, kind="main")
    return message.message_id


async def pin(bot: Bot, settings: Settings) -> None:
    channel_id = settings.get("main_channel_id")
    message_id = settings.get("main_post_message_id")
    if not (channel_id and message_id):
        raise MainPostError("Главный пост ещё не опубликован.")
    try:
        await bot.pin_chat_message(
            chat_id=channel_id, message_id=message_id, disable_notification=True
        )
    except TelegramAPIError as error:
        raise MainPostError(f"Не удалось закрепить: {error}") from error


async def refresh_counter(bot: Bot, repo: Repo, config: Config, settings: Settings) -> None:
    """Тихо обновить счётчик участников — вызывается после новой заявки."""
    if not (settings.get("main_channel_id") and settings.get("main_post_message_id")):
        return
    try:
        await publish(bot, repo, config, settings)
    except (MainPostError, TelegramAPIError) as error:
        log.info("Счётчик в главном посте не обновился: %s", error)


async def wipe_battle_posts(bot: Bot, repo: Repo, config: Config) -> tuple[int, int]:
    """Удалить посты батлов из канала. Возвращает (удалено, не удалось)."""
    deleted = failed = 0
    for row in repo.posts(chat_id=config.channel_id):
        try:
            await bot.delete_message(chat_id=row["chat_id"], message_id=row["message_id"])
            deleted += 1
        except TelegramAPIError as error:
            # сообщение старше 48 часов Telegram удалить не даст
            log.info("Не удалось удалить пост %s: %s", row["message_id"], error)
            failed += 1
        repo.forget_post(row["chat_id"], row["message_id"])
    return deleted, failed
