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

import asyncio
import logging

from aiogram import Bot, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import ChatMemberUpdated

from config import Config
from services import keyboards, sponsors, subscription, texts
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


async def sweep(
    bot: Bot, repo: Repo, config: Config, settings: Settings,
    limit: int = 2000, delay: float = 0.05,
) -> tuple[int, int]:
    """Проверить всех, кто точно был подписан, и отметить вышедших.

    Событие о выходе Telegram присылает мгновенно, но хранит его не вечно:
    если бот в этот момент лежал, выход можно пропустить. Эта проверка
    догоняет пропущенное — по кнопке в панели.

    Возвращает (проверено, отмечено).
    """
    channels = sponsors.required(config, settings)
    if not channels:
        return 0, 0

    checked = marked = 0
    for user_id in repo.known_subscribers(limit):
        if user_id in config.admin_ids:
            continue
        checked += 1
        for channel_id in channels:
            # Здесь нужен точный ответ, а не «на всякий случай нет»: отметка
            # снимается только за звёзды, и ставить её из-за сбоя сети нельзя.
            # Поэтому «неизвестно» пропускаем — догоним при следующей проверке.
            inside = await subscription.check(bot, channel_id, user_id)
            if inside is None or inside:
                continue
            repo.mark_left(user_id, channel_id)
            marked += 1
            break
        await asyncio.sleep(delay)  # мягко к лимитам Telegram
    return checked, marked


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
