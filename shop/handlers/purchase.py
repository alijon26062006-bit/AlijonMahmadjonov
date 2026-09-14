"""Харид: интихоби мол → вориди ID/username → тафтиш → пардохт аз ҳисоб."""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import catalog, keyboards, texts
from ..config import Config
from ..db import Database, NotEnoughMoney
from ..fulfillment import deliver_in_background
from ..states import Buy
from ..supplier import Supplier
from .common import (
    clean_player_id,
    clean_username,
    current_user,
    notify_admins,
    safe_edit,
    show_main_menu,
)

log = logging.getLogger(__name__)
router = Router(name="purchase")


async def _ask_target(message: Message, info: catalog.Category, row, cfg: Config) -> None:
    if info.target == "username":
        text = texts.ask_username(info, row["title"], row["price"], cfg.currency)
    else:
        text = texts.ask_player_id(info, row["title"], row["price"], cfg.currency)
    await message.answer(text, reply_markup=keyboards.cancel_only())


@router.callback_query(F.data.startswith(keyboards.CB_PRODUCT))
async def cb_product(
    cb: CallbackQuery, state: FSMContext, db: Database, cfg: Config
) -> None:
    code = cb.data[len(keyboards.CB_PRODUCT):]
    row = db.product(code)
    if row is None or not row["active"]:
        await cb.answer(texts.EMPTY_CATEGORY, show_alert=True)
        return
    info = catalog.CATEGORY_INFO.get(row["category"])
    if info is None:
        await cb.answer(texts.UNKNOWN, show_alert=True)
        return

    await state.clear()
    await state.set_state(Buy.waiting_target)
    await state.update_data(code=code)
    if info.target == "username":
        text = texts.ask_username(info, row["title"], row["price"], cfg.currency)
    else:
        text = texts.ask_player_id(info, row["title"], row["price"], cfg.currency)
    await safe_edit(cb, text, keyboards.cancel_only())
    await cb.answer()


@router.message(Buy.waiting_target, F.text)
async def got_target(
    message: Message,
    state: FSMContext,
    db: Database,
    cfg: Config,
    supplier: Supplier,
) -> None:
    data = await state.get_data()
    row = db.product(data.get("code", ""))
    if row is None:
        await state.clear()
        await show_main_menu(message, db, cfg, edit=False)
        return
    info = catalog.CATEGORY_INFO[row["category"]]

    if info.target == "username":
        target = clean_username(message.text)
        if target is None:
            await message.answer(texts.BAD_USERNAME, reply_markup=keyboards.cancel_only())
            return
    else:
        target = clean_player_id(message.text)
        if target is None:
            await message.answer(texts.BAD_PLAYER_ID, reply_markup=keyboards.cancel_only())
            return

    kind = row["kind"] or "game"
    if kind == "manual":
        # Premium: API надорад — рост ба тасдиқи фармоиш меравем.
        await state.update_data(target=target, nickname=None)
        await _show_confirm(message, state, db, cfg)
        return

    waiting = await message.answer("⏳ Дар ҳоли тафтиши аккаунт...")
    checked = await supplier.check(
        kind=kind, sku=row["sku"] or "", target=target, amount=row["amount"]
    )
    nickname = checked.nickname if checked.ok else None
    await state.update_data(target=target, nickname=nickname)
    try:
        await waiting.edit_text(
            texts.confirm_target(info, target, nickname, checked.error),
            reply_markup=keyboards.confirm_target(),
        )
    except Exception:
        await message.answer(
            texts.confirm_target(info, target, nickname, checked.error),
            reply_markup=keyboards.confirm_target(),
        )


async def _show_confirm(
    message: Message, state: FSMContext, db: Database, cfg: Config
) -> None:
    data = await state.get_data()
    row = db.product(data.get("code", ""))
    if row is None:
        await state.clear()
        await show_main_menu(message, db, cfg, edit=False)
        return
    info = catalog.CATEGORY_INFO[row["category"]]
    user = db.touch_user(message.chat.id)
    await state.set_state(Buy.confirming)
    await message.answer(
        texts.confirm_order(
            info,
            row["title"],
            row["price"],
            data.get("target", ""),
            data.get("nickname"),
            user.balance,
            cfg.currency,
        ),
        reply_markup=keyboards.confirm_order(),
    )


@router.callback_query(F.data == keyboards.CB_ID_OK)
async def cb_id_ok(cb: CallbackQuery, state: FSMContext, db: Database, cfg: Config) -> None:
    data = await state.get_data()
    if not data.get("target"):
        await cb.answer(texts.UNKNOWN, show_alert=True)
        return
    await cb.answer()
    await _show_confirm(cb.message, state, db, cfg)


@router.callback_query(F.data == keyboards.CB_ID_NO)
async def cb_id_no(cb: CallbackQuery, state: FSMContext, db: Database, cfg: Config) -> None:
    data = await state.get_data()
    row = db.product(data.get("code", ""))
    if row is None:
        await cb.answer(texts.UNKNOWN, show_alert=True)
        return
    info = catalog.CATEGORY_INFO[row["category"]]
    await state.set_state(Buy.waiting_target)
    ask = texts.ask_username if info.target == "username" else texts.ask_player_id
    await safe_edit(
        cb,
        ask(info, row["title"], row["price"], cfg.currency),
        keyboards.cancel_only(),
    )
    await cb.answer()


@router.callback_query(F.data == keyboards.CB_BUY_OK)
async def cb_buy(
    cb: CallbackQuery,
    state: FSMContext,
    db: Database,
    cfg: Config,
    bot: Bot,
    supplier: Supplier,
) -> None:
    data = await state.get_data()
    row = db.product(data.get("code", ""))
    target = data.get("target")
    if row is None or not target:
        await cb.answer(texts.UNKNOWN, show_alert=True)
        return

    user = current_user(cb, db)
    price = row["price"]
    if user.balance < price:
        await safe_edit(
            cb, texts.not_enough(price, user.balance, cfg.currency), keyboards.need_money()
        )
        await cb.answer()
        return

    try:
        order_id = db.create_order(
            user_id=user.id,
            product_code=row["code"],
            category=row["category"],
            title=row["title"],
            price=price,
            target=target,
            nickname=data.get("nickname"),
            sku=row["sku"] or "",
            kind=row["kind"] or "game",
        )
    except NotEnoughMoney:
        fresh = db.user(user.id)
        await safe_edit(
            cb,
            texts.not_enough(price, fresh.balance if fresh else 0, cfg.currency),
            keyboards.need_money(),
        )
        await cb.answer()
        return

    await state.clear()
    await safe_edit(
        cb,
        texts.order_created(order_id, row["title"], target, price, cfg.currency),
        keyboards.back_home(),
    )
    await cb.answer("✅")

    # Иҷро дар паси парда: бот фавран ҷавобгӯ мемонад.
    deliver_in_background(bot, db, cfg, supplier, order_id)
