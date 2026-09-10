"""Отзывы со стороны покупателя: звёзды и необязательный комментарий."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import db
from handlers.common import log
from services import reviews
from texts import DEFAULT_LANG, t

router = Router()

SKIP = {"-", "—", "нет", "не", "no", "skip"}


class Review(StatesGroup):
    text = State()


@router.callback_query(F.data.startswith("rv:"))
async def got_stars(cb: CallbackQuery, state: FSMContext) -> None:
    try:
        _, raw_oid, raw_stars = cb.data.split(":", 2)
        oid, stars = int(raw_oid), max(1, min(5, int(raw_stars)))
    except ValueError:
        await cb.answer()
        return

    order = await db.order(oid)
    lang = (await db.get_user(cb.from_user.id) or {}).get("lang") or DEFAULT_LANG

    # оценивать можно только свой заказ
    if not order or int(order["uid"]) != cb.from_user.id:
        await cb.answer()
        return

    await db.review_set_stars(oid, stars)
    await cb.answer(t(lang, "rev_thanks"))
    try:
        await cb.message.edit_text("★" * stars + "☆" * (5 - stars))
    except Exception:
        pass

    await state.set_state(Review.text)
    await state.update_data(rev_oid=oid)
    await cb.message.answer(t(lang, "rev_text_ask"))


@router.message(Review.text)
async def got_text(msg: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()
    oid = int(data.get("rev_oid", 0))
    lang = (await db.get_user(msg.from_user.id) or {}).get("lang") or DEFAULT_LANG
    if not oid:
        return

    raw = (msg.text or "").strip()
    if raw.lower() not in SKIP:
        await db.review_set_text(oid, raw)

    await msg.answer(t(lang, "rev_saved"))
    try:
        await reviews.post(msg.bot, oid)
    except Exception as e:
        log.warning("публикация отзыва #%s не прошла: %s", oid, e)
