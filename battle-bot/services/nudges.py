"""Сообщение «вас обошли».

Самый действенный момент позвать своих — когда соперник только что вышел
вперёд. Человек уже вложился, ему обидно, и он идёт за голосами. Поэтому бот
следит за сменой лидера в матче и пишет тому, кто потерял первое место.

Чтобы это не превратилось в спам при перестрелке за первое место, между
такими сообщениями одному человеку выдерживается пауза.
"""
from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from config import Config
from core.models import Slot
from services import keyboards, texts
from services.tg import is_blocked
from storage.repo import Repo

log = logging.getLogger(__name__)

COOLDOWN_MINUTES = 10


def leader(slots: list[Slot]) -> Slot | None:
    """Кто впереди. Ничья лидером не считается — обходить ещё нечего."""
    if not slots:
        return None
    best = max(slots, key=lambda s: s.votes)
    if best.votes == 0:
        return None
    if sum(1 for s in slots if s.votes == best.votes) > 1:
        return None
    return best


async def notify_lead_change(
    bot: Bot,
    repo: Repo,
    config: Config,
    match_id: int,
    before: list[Slot],
    after: list[Slot],
    post_url: str | None = None,
) -> int | None:
    """Сообщить тому, кого только что обошли. Возвращает его id.

    Ничего не делает, если лидер не сменился или пауза ещё не вышла.
    """
    was, now = leader(before), leader(after)
    if now is None or was is None or was.user_id == now.user_id:
        return None

    markup = keyboards.my_match(match_id, config, post_url)
    loser = next((s for s in after if s.user_id == was.user_id), was)
    notified: int | None = None

    # пауза считается для каждого отдельно: при перестрелке за первое место
    # один и тот же человек иначе получал бы то «вас обошли», то поздравление
    if repo.can_nudge(match_id, was.user_id, COOLDOWN_MINUTES):
        await _send(
            bot, repo, was.user_id,
            texts.overtaken(now.nickname, now.votes, loser.votes), markup,
        )
        notified = was.user_id

    if repo.can_nudge(match_id, now.user_id, COOLDOWN_MINUTES):
        await _send(
            bot, repo, now.user_id,
            texts.took_the_lead(loser.nickname, now.votes, loser.votes), markup,
        )

    if notified is not None:
        log.info("Матч %s: %s обошёл %s", match_id, now.user_id, was.user_id)
    return notified


async def _send(bot: Bot, repo: Repo, user_id: int, text: str, markup) -> None:
    try:
        await bot.send_message(
            user_id, text, reply_markup=markup, disable_web_page_preview=True
        )
    except TelegramAPIError as error:
        if is_blocked(error):
            repo.mark_blocked(user_id)
        log.info("Не доставлено %s: %s", user_id, error)
