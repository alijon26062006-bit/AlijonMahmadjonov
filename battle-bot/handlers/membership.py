"""Кто ушёл из канала.

Telegram присылает боту событие о входе и выходе участника канала, но
**только если бот там администратор** — а он им и так является, иначе не смог
бы публиковать посты.

Перечислить всех подписчиков канала Bot API не позволяет вовсе. Это и не
нужно: отметка ставится в момент выхода, поэтому все, кто просто остаётся
подписанным, в список не попадают никогда. Обновление никого не задевает
задним числом.
"""
from __future__ import annotations

import logging

from aiogram import Bot, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import ChatMemberUpdated

from config import Config
from services import keyboards, sponsors, texts
from storage.repo import Repo
from storage.settings import Settings

log = logging.getLogger(__name__)
router = Router(name="membership")

# статусы, при которых человек считается подписанным
INSIDE = {"creator", "administrator", "member", "restricted"}
OUTSIDE = {"left", "kicked"}


def has_left(event: ChatMemberUpdated) -> bool:
    """Человек действительно вышел, а не поменял роль внутри канала."""
    was = event.old_chat_member.status
    now = event.new_chat_member.status
    if was == "restricted" and not getattr(event.old_chat_member, "is_member", False):
        was = "left"
    return was in INSIDE and now in OUTSIDE


@router.chat_member()
async def someone_left(
    event: ChatMemberUpdated, bot: Bot, repo: Repo, config: Config, settings: Settings
) -> None:
    """Отметить выход из обязательного канала."""
    if not settings.get("leave_penalty_enabled"):
        return
    if event.chat.id not in sponsors.required(config, settings):
        return  # канал не из обязательных — уход из него ничего не значит
    if not has_left(event):
        return

    user = event.new_chat_member.user
    if user.is_bot or user.id in config.admin_ids:
        return

    repo.upsert_user(user.id, user.username, user.first_name)
    times = repo.mark_left(user.id, event.chat.id)
    price = int(settings.get("rejoin_price") or 0)
    log.info("Участник %s вышел из канала %s (раз %s)", user.id, event.chat.id, times)

    try:
        await bot.send_message(
            user.id,
            texts.left_the_channel(times, price),
            reply_markup=keyboards.buy_rejoin(price) if price else None,
        )
    except TelegramAPIError as error:
        # закрыл бота — отметка всё равно стоит и сработает при возвращении
        log.info("Не смог написать вышедшему %s: %s", user.id, error)
