"""Экран голосования: показ, голоса, обновление счёта."""
from __future__ import annotations

import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from config import Config
from core.models import MatchStatus, VoteResult, VoteSource
from services import keyboards, links, nudges, sponsors, texts
from services.tg import is_not_modified
from storage.repo import Repo
from storage.settings import Settings

log = logging.getLogger(__name__)
router = Router(name="voting")

REFUSALS = {
    VoteResult.CLOSED: "Голосование по этому матчу уже завершено.",
    VoteResult.DUPLICATE: "Ваш голос в этом матче уже учтён.",
    VoteResult.UNKNOWN_TARGET: "Такого участника в этом матче нет.",
}


def _post_url(config: Config, match) -> str | None:
    if not match["message_id"]:
        return None
    if config.channel_url.startswith("https://t.me/") and "/c/" not in config.channel_url:
        return links.public_post_link(config.channel_url, match["message_id"])
    return links.post_link(config.channel_id, match["message_id"])


async def gate(
    message: Message, match_id: int, config: Config, settings: Settings, user_id: int
) -> bool:
    """Показать экран подписки, если её нет. True — проход закрыт."""
    unsubscribed = await sponsors.missing(
        message.bot, config, settings, user_id, force=True
    )
    if not unsubscribed:
        return False
    await message.answer(
        sponsors.text(unsubscribed),
        reply_markup=sponsors.keyboard(unsubscribed, f"open:{match_id}"),
        disable_web_page_preview=True,
    )
    return True


async def show_voting(
    message: Message, match_id: int, repo: Repo, config: Config,
    called_for: int | None = None,
) -> None:
    """Отрисовать экран голосования по матчу.

    ``called_for`` приходит по ссылке из личного канала участника: человека
    позвали поддержать конкретное имя, и об этом честно говорится на экране.
    """
    match = repo.get_match(match_id)
    if match is None:
        await message.answer("Такого матча нет.")
        return

    slots = repo.match_slots(match_id)
    if match["status"] == MatchStatus.CLOSED.value:
        ranking = sorted(slots, key=lambda s: s.position or 99)
        await message.answer(
            texts.channel_result(match["round_no"], bool(match["is_final"]), ranking, False)
        )
        return

    deadline = datetime.fromisoformat(match["deadline"])
    called = next((s for s in slots if s.user_id == called_for), None)
    intro = texts.called_to_support(called.nickname) if called else ""
    await message.answer(
        intro + texts.voting_screen(
            match["round_no"], bool(match["is_final"]), slots, deadline
        ),
        reply_markup=keyboards.voting(
            match_id, slots, config, _post_url(config, match), called_for
        ),
    )


@router.callback_query(F.data.startswith("vote:"))
async def cast_vote(
    callback: CallbackQuery, repo: Repo, config: Config, settings: Settings
) -> None:
    _, raw_match, raw_target = callback.data.split(":")
    match_id, target_id = int(raw_match), int(raw_target)

    match = repo.get_match(match_id)
    if match is None or match["status"] != MatchStatus.VOTING.value:
        await callback.answer("Голосование по этому матчу уже закрыто.", show_alert=True)
        return

    if repo.is_banned(callback.from_user.id):
        await callback.answer("Ваш аккаунт исключён из голосований.", show_alert=True)
        return

    # подписка обязательна всегда: без неё голос не принимается ни при каких настройках
    if await gate(callback.message, match_id, config, settings, callback.from_user.id):
        await callback.answer("Голосовать могут только подписчики канала.", show_alert=True)
        return

    source, note = _pick_vote_source(repo, match_id, callback.from_user.id, config)
    if source is None:
        await callback.answer(note, show_alert=True)
        return

    before = repo.match_slots(match_id)
    result = repo.add_vote(match_id, callback.from_user.id, target_id, source)
    if result is not VoteResult.ACCEPTED:
        # купленный голос списан заранее — при отказе возвращаем его обратно
        if source is VoteSource.PAID:
            repo.add_votes(callback.from_user.id, 1)
        await callback.answer(REFUSALS[result], show_alert=True)
        await _refresh(callback, match_id, repo, config)
        return

    await callback.answer(note)
    await _refresh(callback, match_id, repo, config)

    # сменился лидер — самый подходящий момент позвать своих
    await nudges.notify_lead_change(
        callback.bot, repo, config, match_id,
        before, repo.match_slots(match_id), _post_url(config, match),
    )


def _pick_vote_source(
    repo: Repo, match_id: int, voter_id: int, config: Config
) -> tuple[VoteSource | None, str]:
    """Первый голос — бесплатный, дальше списываем купленные."""
    if not repo.has_free_vote(match_id, voter_id):
        return VoteSource.FREE, "Голос учтён 👍"

    if not config.paid_votes_enabled:
        return None, "Вы уже голосовали в этом матче."

    if repo.spend_vote(voter_id):
        return VoteSource.PAID, "Списан 1 купленный голос ⭐"

    return None, "Вы уже голосовали. Докупить голоса можно в меню «Купить голоса»."


@router.callback_query(F.data.startswith("open:"))
async def open_voting(
    callback: CallbackQuery, repo: Repo, config: Config, settings: Settings
) -> None:
    """«Я подписался» на экране гейта: перепроверяем и открываем голосование."""
    match_id = int(callback.data.split(":")[1])
    if await gate(callback.message, match_id, config, settings, callback.from_user.id):
        await callback.answer("Подписки всё ещё нет.", show_alert=True)
        return
    await show_voting(callback.message, match_id, repo, config)
    await callback.answer()


@router.callback_query(F.data.startswith("refresh:"))
async def refresh_votes(callback: CallbackQuery, repo: Repo, config: Config) -> None:
    match_id = int(callback.data.split(":")[1])
    await _refresh(callback, match_id, repo, config)
    await callback.answer("Обновлено")


async def _refresh(callback: CallbackQuery, match_id: int, repo: Repo, config: Config) -> None:
    match = repo.get_match(match_id)
    if match is None:
        return
    slots = repo.match_slots(match_id)
    try:
        await callback.message.edit_reply_markup(
            reply_markup=keyboards.voting(match_id, slots, config, _post_url(config, match))
        )
    except TelegramBadRequest as error:
        # счёт не изменился — Telegram отказывается перерисовывать, это не ошибка
        if not is_not_modified(error):
            log.warning("Не удалось обновить экран голосования: %s", error)
