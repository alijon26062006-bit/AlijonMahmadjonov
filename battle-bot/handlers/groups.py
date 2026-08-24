"""Чистка спама в группах.

Работает только там, куда бота добавили администратором группы. Каналы —
главный и канал батлов — этот роутер не трогает: в `GROUPS` их типов нет.

Чистое сообщение пропускается дальше по цепочке (SkipHandler), чтобы команды
в группе продолжали работать как раньше.
"""
from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.exceptions import TelegramAPIError
from aiogram.types import ChatMemberUpdated, Message

from config import Config
from services import moderation
from storage.repo import Repo
from storage.settings import Settings

log = logging.getLogger(__name__)
router = Router(name="groups")

GROUPS = {"group", "supergroup"}


@router.my_chat_member(F.chat.type.in_(GROUPS))
async def added_to_group(
    event: ChatMemberUpdated, bot: Bot, repo: Repo, config: Config
) -> None:
    """Бота добавили или убрали из группы — запоминаем её сами."""
    status = event.new_chat_member.status
    if status in {"administrator", "member"}:
        repo.add_group(event.chat.id, event.chat.title)
        log.info("Бот добавлен в группу %s (%s)", event.chat.title, event.chat.id)
        for admin_id in config.admin_ids:
            try:
                await bot.send_message(
                    admin_id,
                    f"🛡 Бот добавлен в группу <b>{event.chat.title}</b>\n"
                    f"<code>{event.chat.id}</code>\n\n"
                    + (
                        "Чистка спама включена."
                        if status == "administrator"
                        else "⚠️ <b>Дайте права администратора</b> с правом удалять "
                             "сообщения — без них чистить нечем."
                    ),
                )
            except TelegramAPIError:
                pass
    elif status in {"left", "kicked"}:
        repo.forget_group(event.chat.id)
        log.info("Бот убран из группы %s", event.chat.id)


@router.message(F.chat.type.in_(GROUPS))
async def clean_group(
    message: Message, bot: Bot, repo: Repo, config: Config, settings: Settings
) -> None:
    """Проверить сообщение из группы и удалить, если это спам."""
    group = repo.group(message.chat.id)
    if group is None:
        repo.add_group(message.chat.id, message.chat.title)
        group = repo.group(message.chat.id)
    if not group["moderation"]:
        raise SkipHandler()

    user = message.from_user
    if user is None or user.id in config.admin_ids or user.is_bot:
        raise SkipHandler()
    if await _is_group_admin(bot, message.chat.id, user.id):
        raise SkipHandler()

    verdict = moderation.check(message, settings, is_new=_just_joined(message))
    if not verdict:
        raise SkipHandler()  # чистое сообщение живёт своей жизнью

    try:
        await message.delete()
    except TelegramAPIError as error:
        log.info("Не смог удалить сообщение в группе %s: %s", message.chat.id, error)
        return

    repo.count_deleted(message.chat.id)
    strikes = repo.add_strike(message.chat.id, user.id)
    limit = int(settings.get("spam_strike_limit") or 0)
    log.info(
        "Удалено в группе %s у %s: %s (нарушение %s)",
        message.chat.id, user.id, verdict.reason, strikes,
    )

    if limit and strikes >= limit:
        await _kick(bot, message.chat.id, user.id)


async def _is_group_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    """Админов группы не трогаем никогда."""
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
    except TelegramAPIError:
        return False  # не смогли проверить — правила общие
    return member.status in {"creator", "administrator"}


def _just_joined(message: Message) -> bool:
    """Человек вошёл в группу этим же сообщением — новичок."""
    return bool(getattr(message, "new_chat_members", None))


async def _kick(bot: Bot, chat_id: int, user_id: int) -> None:
    try:
        await bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
        log.info("Спамер %s убран из группы %s", user_id, chat_id)
    except TelegramAPIError as error:
        log.info("Не смог убрать %s из группы %s: %s", user_id, chat_id, error)
