"""Голоса за приглашённых друзей.

Правила намеренно строгие, иначе накрутка ломает весь батл:

* награда выдаётся один раз за одного приглашённого — навсегда, гарантируется
  первичным ключом в базе;
* засчитывается только новый человек: тот, кто уже пользовался ботом, награду
  не приносит;
* сам себя пригласить нельзя;
* награда выдаётся только после подписки на канал — иначе смысл теряется.
"""
from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from config import Config
from services import sponsors, texts
from storage.repo import Repo
from storage.settings import Settings

log = logging.getLogger(__name__)


def remember(repo: Repo, invited_id: int, inviter_id: int, settings: Settings) -> bool:
    """Запомнить приглашение. False — если оно не засчитывается.

    Вызывается до создания записи о пользователе, поэтому «новичок» определяется
    по отсутствию его в таблице users.
    """
    if not settings.get("referral_enabled"):
        return False
    if invited_id == inviter_id:
        return False
    if repo.get_user(invited_id) is not None:
        return False  # человек уже знаком боту — приглашением это не считается
    if repo.get_user(inviter_id) is None:
        return False  # пригласивший должен существовать
    return repo.record_referral(invited_id, inviter_id)


async def try_reward(
    bot: Bot, repo: Repo, config: Config, settings: Settings, invited_id: int
) -> int | None:
    """Выдать награду, если приглашённый подписан на канал.

    Возвращает id пригласившего, когда награда выдана.
    """
    if not settings.get("referral_enabled"):
        return None
    if repo.pending_referral(invited_id) is None:
        return None

    # подписка проверяется по тем же каналам, что и для голосования
    if await sponsors.missing(bot, config, settings, invited_id):
        return None

    reward = settings.get("referral_reward")
    inviter_id = repo.reward_referral(invited_id, reward)
    if inviter_id is None:
        return None

    log.info("Приглашение засчитано: %s привёл %s", inviter_id, invited_id)
    try:
        await bot.send_message(
            inviter_id,
            texts.referral_rewarded(reward, repo.vote_balance(inviter_id)),
        )
    except TelegramAPIError as error:
        log.info("Не смог сообщить о награде пользователю %s: %s", inviter_id, error)
    return inviter_id
