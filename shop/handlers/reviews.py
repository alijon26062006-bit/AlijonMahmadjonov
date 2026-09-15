"""Шарҳҳо: пас аз харид — навиштан, тасдиқи админ, нашр дар канал."""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import keyboards, texts
from ..config import Config
from ..db import Database
from ..states import Review
from .common import notify_admins, safe_edit

log = logging.getLogger(__name__)
router = Router(name="reviews")

MIN_LENGTH = 10
REVIEW_CHANNEL_KEY = "review_channel"


@router.callback_query(F.data == keyboards.CB_REVIEW)
async def cb_write_review(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Review.waiting_text)
    await safe_edit(cb, texts.ASK_REVIEW, keyboards.cancel_only())
    await cb.answer()


@router.message(Review.waiting_text, F.text)
async def got_review(
    message: Message, state: FSMContext, db: Database, cfg: Config, bot: Bot
) -> None:
    text = message.text.strip()
    if len(text) < MIN_LENGTH:
        await message.answer(texts.REVIEW_TOO_SHORT, reply_markup=keyboards.cancel_only())
        return
    await state.clear()
    review_id = db.create_review(message.from_user.id, text)
    await message.answer(texts.REVIEW_SENT, reply_markup=keyboards.back_home())

    row = db.review(review_id)
    await notify_admins(
        bot,
        cfg,
        texts.admin_new_review(row, db.user(message.from_user.id)),
        keyboards.admin_review(review_id),
    )


async def publish_review(bot: Bot, db: Database, review_id: int) -> tuple[bool, str]:
    """Шарҳро дар канал нашр мекунад. Бармегардонад (шуд, сабаб)."""
    row = db.review(review_id)
    if row is None:
        return False, "шарҳ ёфт нашуд"
    channel = db.setting(REVIEW_CHANNEL_KEY)
    if not channel:
        return False, "канали шарҳҳо дар панел гузошта нашудааст"

    user = db.user(row["user_id"])
    name = (user.first_name if user else None) or "Харидор"
    try:
        await bot.send_message(channel, texts.review_for_channel(row["text"], name))
    except Exception as exc:
        log.warning("Шарҳ дар канал нашр нашуд: %s", exc)
        return False, str(exc)
    return True, ""
