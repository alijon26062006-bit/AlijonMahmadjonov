"""Экран голосования: показ, голоса, обновление счёта."""
from __future__ import annotations

import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from config import Config
from core.models import MatchStatus, VoteSource
from services import keyboards, links, texts
from services.tg import is_not_modified
from services.subscription import is_subscribed
from storage.repo import Repo

log = logging.getLogger(__name__)
router = Router(name="voting")


def _post_url(config: Config, match) -> str | None:
    if not match["message_id"]:
        return None
    if config.channel_url.startswith("https://t.me/") and "/c/" not in config.channel_url:
        return links.public_post_link(config.channel_url, match["message_id"])
    return links.post_link(config.channel_id, match["message_id"])


async def show_voting(message: Message, match_id: int, repo: Repo, config: Config) -> None:
    """Отрисовать экран голосования по матчу."""
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
    await message.answer(
        texts.voting_screen(match["round_no"], bool(match["is_final"]), slots, deadline),
        reply_markup=keyboards.voting(match_id, slots, config, _post_url(config, match)),
    )


@router.callback_query(F.data.startswith("vote:"))
async def cast_vote(callback: CallbackQuery, repo: Repo, config: Config) -> None:
    _, raw_match, raw_target = callback.data.split(":")
    match_id, target_id = int(raw_match), int(raw_target)

    match = repo.get_match(match_id)
    if match is None or match["status"] != MatchStatus.VOTING.value:
        await callback.answer("Голосование по этому матчу уже закрыто.", show_alert=True)
        return

    if repo.is_banned(callback.from_user.id):
        await callback.answer("Ваш аккаунт исключён из голосований.", show_alert=True)
        return

    if config.require_subscription and not await is_subscribed(
        callback.bot, config.channel_id, callback.from_user.id
    ):
        await callback.message.answer(
            texts.subscribe_required(config.channel_url),
            reply_markup=keyboards.subscribe(config.channel_url, match_id),
            disable_web_page_preview=True,
        )
        await callback.answer("Нужна подписка на канал.", show_alert=True)
        return

    source, note = _pick_vote_source(repo, match_id, callback.from_user.id, config)
    if source is None:
        await callback.answer(note, show_alert=True)
        return

    if not repo.add_vote(match_id, callback.from_user.id, target_id, source):
        await callback.answer("Ваш голос в этом матче уже учтён.", show_alert=True)
        return

    await callback.answer(note)
    await _refresh(callback, match_id, repo, config)


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
