"""Картинка участника: то, что он выложит в сторис.

Пересланную ссылку не выкладывает почти никто, картинку — выкладывают. Это
единственный способ, которым батл растёт сам: каждый участник приводит своих.
"""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from config import Config
from services import card, keyboards, links, prizes, texts
from storage.repo import Repo
from storage.settings import Settings

log = logging.getLogger(__name__)
router = Router(name="card")


def title_of(settings: Settings) -> str:
    return settings.get("card_title") or "БИТВА НИКОВ"


def prize_of(settings: Settings) -> str:
    """Первый приз словами — ради него человека и зовут голосовать."""
    values = settings.get("prizes") or []
    if not values:
        return ""
    first = values[0]
    return f"Приз финала {first} звёзд" if prizes.is_stars(first) else f"Приз финала: {first}"


async def draw(repo: Repo, config: Config, settings: Settings, match_id: int,
               user_id: int) -> tuple[bytes | None, str]:
    """Нарисовать постер для этого человека. Пустые байты — причина отказа."""
    slots = repo.match_slots(match_id)
    me = next((slot for slot in slots if slot.user_id == user_id), None)
    if me is None:
        return None, "Это не ваша пара."

    others = [slot.nickname for slot in slots if slot.user_id != user_id]
    link = links.vote_link(config.bot_username, match_id, user_id)
    # рисование упирается в процессор — уводим в поток, чтобы бот отвечал всем
    image = await asyncio.to_thread(
        card.render, me.nickname, others[0] if others else "соперник",
        link, title_of(settings), prize_of(settings),
    )
    return image, link


@router.callback_query(F.data.startswith("card:"))
async def send_card(
    callback: CallbackQuery, bot: Bot, repo: Repo, config: Config, settings: Settings
) -> None:
    tail = callback.data.split(":")[-1]
    if not tail.isdigit():
        await callback.answer("Кнопка устарела.", show_alert=True)
        return

    if not card.available():
        await callback.answer(texts.CARD_UNAVAILABLE, show_alert=True)
        return

    await callback.answer("Рисую…")
    image, link = await draw(repo, config, settings, int(tail), callback.from_user.id)
    if image is None:
        await callback.answer(link, show_alert=True)
        return

    try:
        await bot.send_photo(
            callback.from_user.id,
            BufferedInputFile(image, filename="battle.png"),
            caption=texts.card_caption(link),
            reply_markup=keyboards.share_card(link),
        )
    except TelegramAPIError as error:
        log.warning("Не смог отправить картинку %s: %s", callback.from_user.id, error)
        await callback.answer("Картинка не отправилась, попробуйте ещё раз.", show_alert=True)


@router.message(Command("card"))
async def card_command(
    message: Message, bot: Bot, repo: Repo, config: Config, settings: Settings
) -> None:
    """«/card» — картинка по текущей паре, без поиска нужной кнопки."""
    match_id = repo.live_match_of(message.from_user.id)
    if match_id is None:
        await message.answer(texts.CARD_NO_MATCH)
        return

    if not card.available():
        await message.answer(texts.CARD_UNAVAILABLE)
        return

    image, link = await draw(repo, config, settings, match_id, message.from_user.id)
    if image is None:
        await message.answer(link)
        return

    await message.answer_photo(
        BufferedInputFile(image, filename="battle.png"),
        caption=texts.card_caption(link),
        reply_markup=keyboards.share_card(link),
    )
