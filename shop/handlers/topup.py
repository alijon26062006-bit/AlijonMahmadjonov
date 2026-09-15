"""Пур кардани ҳисоб: интихоби маблағ → реквизитҳо → чек → тасдиқи админ."""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import catalog, keyboards, payments, requisites, texts
from ..config import Config
from ..db import Database, TOPUP_WAITING
from ..states import Topup
from .common import current_user, notify_admins, safe_edit

log = logging.getLogger(__name__)
router = Router(name="topup")


@router.callback_query(F.data == keyboards.CB_TOPUP)
async def cb_topup(cb: CallbackQuery, state: FSMContext, db: Database, cfg: Config) -> None:
    await state.clear()
    user = current_user(cb, db)
    await safe_edit(
        cb,
        texts.topup_menu(user.balance, cfg.min_topup, cfg.max_topup, cfg.currency),
        keyboards.topup_menu(catalog.TOPUP_PRESETS, currency=cfg.currency),
    )
    await cb.answer()


@router.callback_query(F.data == keyboards.CB_TOPUP_OTHER)
async def cb_other_sum(cb: CallbackQuery, state: FSMContext, cfg: Config) -> None:
    await state.set_state(Topup.waiting_amount)
    await safe_edit(
        cb,
        texts.ask_amount(cfg.min_topup, cfg.max_topup, cfg.currency),
        keyboards.cancel_only(),
    )
    await cb.answer()


@router.message(Topup.waiting_amount, F.text)
async def got_amount(
    message: Message, state: FSMContext, db: Database, cfg: Config
) -> None:
    amount = texts.to_diram(message.text)
    if amount is None or amount < cfg.min_topup or amount > cfg.max_topup:
        await message.answer(
            texts.bad_amount(cfg.min_topup, cfg.max_topup, cfg.currency),
            reply_markup=keyboards.cancel_only(),
        )
        return
    await state.clear()
    await _start_payment(message, message.from_user.id, amount, state, db, cfg)


@router.callback_query(F.data.startswith(keyboards.CB_TOPUP_SUM))
async def cb_preset_sum(
    cb: CallbackQuery, state: FSMContext, db: Database, cfg: Config
) -> None:
    try:
        amount = int(cb.data[len(keyboards.CB_TOPUP_SUM):])
    except ValueError:
        await cb.answer(texts.UNKNOWN, show_alert=True)
        return
    if amount < cfg.min_topup or amount > cfg.max_topup:
        await cb.answer(texts.bad_amount(cfg.min_topup, cfg.max_topup, cfg.currency), show_alert=True)
        return
    await cb.answer()
    await _start_payment(cb.message, cb.from_user.id, amount, state, db, cfg)


async def _start_payment(
    message: Message,
    user_id: int,
    amount: int,
    state: FSMContext,
    db: Database,
    cfg: Config,
) -> None:
    """Сабти пардохт месозад ва реквизитҳоро нишон медиҳад."""
    db.touch_user(user_id)
    req = requisites.get(db, cfg)
    if not req.any_enabled:
        await message.answer(texts.NO_REQUISITES, reply_markup=keyboards.back_home())
        return
    code = payments.make_code()
    topup_id = db.create_topup(user_id, amount, code)
    link, alif = requisites.pay_links(req, cfg, amount, code)
    text = texts.payment_details(
        topup_id,
        amount,
        code,
        payments.format_card(req.card) if req.dc_enabled and req.card else "",
        req.holder,
        cfg.currency,
        alif_account=req.alif_account if req.alif_enabled else "",
    )
    if link is None and alif is None:
        text += "\n\n" + texts.NO_PAY_LINK
    elif alif is not None:
        text += (
            "\n\n<i>Тавассути Alif маблағ худкор пур мешавад, вале кодро "
            "ҳатман дар шарҳ нависед.</i>"
        )
    await state.update_data(topup_id=topup_id)
    await message.answer(text, reply_markup=keyboards.payment(topup_id, link, alif))


@router.callback_query(F.data.startswith(keyboards.CB_TOPUP_PAID))
async def cb_paid(
    cb: CallbackQuery, state: FSMContext, db: Database, cfg: Config, bot: Bot
) -> None:
    try:
        topup_id = int(cb.data[len(keyboards.CB_TOPUP_PAID):])
    except ValueError:
        await cb.answer(texts.UNKNOWN, show_alert=True)
        return
    row = db.topup(topup_id)
    if row is None or row["user_id"] != cb.from_user.id:
        await cb.answer(texts.UNKNOWN, show_alert=True)
        return
    if row["status"] != TOPUP_WAITING:
        await cb.answer(texts.TOPUP_STATUS_LABEL.get(row["status"], ""), show_alert=True)
        return

    await state.set_state(Topup.waiting_receipt)
    await state.update_data(topup_id=topup_id)
    await safe_edit(cb, texts.topup_waiting(topup_id), keyboards.back_home())
    await cb.answer()
    await notify_admins(
        bot,
        cfg,
        texts.admin_new_topup(row, db.user(cb.from_user.id), cfg.currency),
        keyboards.admin_topup(topup_id),
    )


@router.message(Topup.waiting_receipt, F.photo | F.document)
async def got_receipt(
    message: Message, state: FSMContext, db: Database, cfg: Config, bot: Bot
) -> None:
    """Чекро ба админҳо мефиристад."""
    data = await state.get_data()
    topup_id = data.get("topup_id")
    row = db.topup(topup_id) if topup_id else None
    user = current_user(message, db)
    caption = (
        texts.admin_topup_card(row, user, cfg.currency)
        if row
        else f"🧾 Чек аз {texts.esc(user.title)} (<code>{user.id}</code>)"
    )
    for admin_id in cfg.admin_ids:
        try:
            await bot.copy_message(
                chat_id=admin_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                caption=caption,
                reply_markup=keyboards.admin_topup(topup_id) if row else None,
            )
        except Exception as exc:
            log.warning("Чек ба админ %s нарасид: %s", admin_id, exc)
    await state.clear()
    await message.answer(
        "✅ Чек қабул шуд. Дар интизори тасдиқ бошед.",
        reply_markup=keyboards.back_home(),
    )
