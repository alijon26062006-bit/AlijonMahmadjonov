"""Заявки на вступление в канал: автоприём и «принять всех».

Telegram **не умеет** отдавать список уже накопленных заявок: в Bot API нет
такого метода. Зато он присылает событие на каждую новую заявку, пока бот
администратор канала с правом добавлять участников. Поэтому бот записывает
каждую заявку в свою базу — и дальше может либо принимать сразу, либо
принять все разом одной кнопкой.

Из этого следует честное ограничение: заявки, поданные до того, как бот стал
администратором, боту не видны. Их принимает только сам Telegram, руками.
"""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import ChatJoinRequest

from services import texts
from storage.repo import Repo
from storage.settings import Settings

log = logging.getLogger(__name__)
router = Router(name="join-requests")

# пауза между одобрениями: тысяча заявок подряд иначе упрётся во флуд-контроль
PACE = 0.1

# ошибки, после которых заявку нужно просто вычеркнуть: человек уже в канале,
# сам отозвал заявку или его заявки больше нет
GONE = ("USER_ALREADY_PARTICIPANT", "HIDE_REQUESTER_MISSING", "USER_CHANNELS_TOO_MUCH")


@router.chat_join_request()
async def new_request(
    event: ChatJoinRequest, bot: Bot, repo: Repo, settings: Settings
) -> None:
    """Пришла заявка: записать и, если включён автоприём, сразу принять."""
    user = event.from_user
    repo.add_join_request(event.chat.id, user.id, user.username, user.first_name)

    if not settings.get("join_auto_approve"):
        return

    await approve_one(bot, repo, event.chat.id, user.id)


async def approve_one(bot: Bot, repo: Repo, chat_id: int, user_id: int) -> bool:
    """Принять одну заявку. False — не вышло, заявка остаётся ждать."""
    try:
        await bot.approve_chat_join_request(chat_id=chat_id, user_id=user_id)
    except TelegramAPIError as error:
        if any(mark in str(error) for mark in GONE):
            # человек уже внутри или заявки давно нет — держать её незачем
            repo.close_join_request(chat_id, user_id, "gone")
            return True
        log.warning("Не принял заявку %s в %s: %s", user_id, chat_id, error)
        return False

    repo.close_join_request(chat_id, user_id, "approved")
    return True


async def approve_all(
    bot: Bot, repo: Repo, chat_id: int | None = None,
    report=None, every: int = 25,
) -> tuple[int, int]:
    """Принять все записанные заявки. Возвращает (принято, не вышло).

    Идём по одной с паузой: тысяча запросов подряд упрётся во флуд-контроль,
    и половина заявок останется непринятой. ``report`` — необязательный
    обработчик хода работы, чтобы админ видел прогресс, а не тишину.
    """
    rows = repo.pending_join_requests(chat_id)
    done = failed = 0

    for index, row in enumerate(rows, start=1):
        if await approve_one(bot, repo, int(row["chat_id"]), int(row["user_id"])):
            done += 1
        else:
            failed += 1

        if report is not None and index % every == 0:
            await report(index, len(rows), done, failed)
        if index < len(rows):
            await asyncio.sleep(PACE)

    log.info("Принято заявок: %s, не вышло: %s", done, failed)
    return done, failed


async def tell_admins(bot: Bot, repo: Repo, admin_ids, waiting: int) -> None:
    """Сказать админам, что заявки копятся. Зовётся из панели, не по каждой."""
    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, texts.join_requests_waiting(waiting))
        except TelegramAPIError as error:
            log.info("Не смог написать админу %s: %s", admin_id, error)
