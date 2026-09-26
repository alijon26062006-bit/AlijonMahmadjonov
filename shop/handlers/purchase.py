"""Харид: интихоби мол → вориди ID/username → тафтиш → пардохт аз ҳисоб."""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import catalog, keyboards, texts
from ..config import Config
from ..db import Database, NotEnoughMoney, price_of
from ..fulfillment import deliver_in_background, pick_supplier
from ..states import Buy
from ..supplier import Supplier
from .common import (
    clean_player_id,
    clean_player_server,
    clean_username,
    current_user,
    safe_edit,
    show_main_menu,
)

log = logging.getLogger(__name__)
router = Router(name="purchase")


def needs_server(row) -> bool:
    """Mobile Legends ғайр аз ID рақами серверро низ талаб мекунад."""
    group = row["group_code"] if "group_code" in row.keys() else ""
    return group in catalog.SERVER_GROUPS


def ask_text(row, info: catalog.Category, price: int, currency: str) -> str:
    if needs_server(row):
        return texts.ask_player_server(info, row["title"], price, currency)
    if info.target == "username":
        return texts.ask_username(info, row["title"], price, currency)
    return texts.ask_player_id(info, row["title"], price, currency)


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
    price = price_of(row, db.is_partner(cb.from_user.id))
    await safe_edit(
        cb, ask_text(row, info, price, cfg.currency), keyboards.cancel_only()
    )
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

    server = ""
    if needs_server(row):
        pair = clean_player_server(message.text)
        if pair is None:
            await message.answer(
                texts.BAD_PLAYER_SERVER, reply_markup=keyboards.cancel_only()
            )
            return
        target, server = pair
    elif info.target == "username":
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
    if kind == "manual" or (
        kind == "premium" and pick_supplier(cfg, supplier, kind, row["sku"] or "") is None
    ):
        # Premium бе API — санҷидан имкон надорад, рост ба тасдиқи фармоиш.
        await state.update_data(target=target, nickname=None, server=server)
        await _show_confirm(message, state, db, cfg)
        return

    waiting = await message.answer("⏳ Дар ҳоли тафтиши аккаунт...")
    checked = await supplier.check(
        kind=kind, sku=row["sku"] or "", target=target, amount=row["amount"],
        server=server,
    )
    nickname = checked.nickname if checked.ok else None
    await state.update_data(target=target, nickname=nickname, server=server)
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
    partner = db.is_partner(user.id)
    await state.set_state(Buy.confirming)
    await message.answer(
        texts.confirm_order(
            info,
            row["title"],
            price_of(row, partner),
            data.get("target", "") + (
                f" ({data['server']})" if data.get("server") else ""
            ),
            data.get("nickname"),
            user.balance,
            cfg.currency,
            partner=partner,
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
    await safe_edit(
        cb,
        ask_text(row, info, price_of(row, db.is_partner(cb.from_user.id)), cfg.currency),
        keyboards.cancel_only(),
    )
    await cb.answer()


# Харидороне, ки ҳоло харид мекунанд. Пахши дуюми «Тасдиқ» дар ҳамин лаҳза
# фармоиши дуюм намесозад ва пулро ду бор намегирад.
_BUYING: set[int] = set()


@router.callback_query(F.data == keyboards.CB_BUY_OK)
async def cb_buy(
    cb: CallbackQuery,
    state: FSMContext,
    db: Database,
    cfg: Config,
    bot: Bot,
    supplier: Supplier,
) -> None:
    uid = cb.from_user.id
    if uid in _BUYING:
        await cb.answer("⏳")
        return
    _BUYING.add(uid)
    try:
        await _buy(cb, state, db, cfg, bot, supplier)
    finally:
        _BUYING.discard(uid)


async def _buy(
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
    if not row["active"]:
        # Админ молро дар ҳамин вақт хомӯш кард — фурӯхтан мумкин нест.
        await state.clear()
        await safe_edit(cb, texts.EMPTY_CATEGORY, keyboards.back_home())
        await cb.answer()
        return

    server = data.get("server", "")
    user = current_user(cb, db)
    price = price_of(row, db.is_partner(user.id))
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
            target=target + (f" ({server})" if server else ""),
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
