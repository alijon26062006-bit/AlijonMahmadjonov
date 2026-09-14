"""Менюи асосӣ ва бахшҳои иттилоотӣ."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import catalog, keyboards, texts
from ..config import Config
from ..db import Database
from .common import current_user, safe_edit, show_main_menu

router = Router(name="menu")
fallback_router = Router(name="fallback")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, db: Database, cfg: Config) -> None:
    await state.clear()
    current_user(message, db)
    await message.answer(texts.PRESS_BUTTON, reply_markup=keyboards.persistent_menu())
    await show_main_menu(message, db, cfg, edit=False)


@router.message(Command("menu", "home", "menyu"))
async def cmd_menu(message: Message, state: FSMContext, db: Database, cfg: Config) -> None:
    await state.clear()
    current_user(message, db)
    await show_main_menu(message, db, cfg, edit=False)


@router.message(Command("bekor", "cancel"))
async def cmd_cancel(message: Message, state: FSMContext, db: Database, cfg: Config) -> None:
    await state.clear()
    await message.answer(texts.CANCELLED)
    await show_main_menu(message, db, cfg, edit=False)


@router.message(Command("id"))
async def cmd_id(message: Message) -> None:
    await message.answer(f"🆔 ID-и шумо: <code>{message.from_user.id}</code>")


@router.message(F.text == texts.BTN_HOME)
async def text_home(message: Message, state: FSMContext, db: Database, cfg: Config) -> None:
    await state.clear()
    await show_main_menu(message, db, cfg, edit=False)


@router.callback_query(F.data == keyboards.CB_HOME)
async def cb_home(cb: CallbackQuery, state: FSMContext, db: Database, cfg: Config) -> None:
    await state.clear()
    await show_main_menu(cb, db, cfg)
    await cb.answer()


@router.callback_query(F.data == keyboards.CB_CANCEL)
async def cb_cancel(cb: CallbackQuery, state: FSMContext, db: Database, cfg: Config) -> None:
    await state.clear()
    await show_main_menu(cb, db, cfg)
    await cb.answer(texts.CANCELLED)


@router.callback_query(F.data == keyboards.CB_TG_MENU)
async def cb_telegram(cb: CallbackQuery, state: FSMContext) -> None:
    """Қадами дуюм: Stars ё Premium."""
    await state.clear()
    await safe_edit(cb, texts.TELEGRAM_MENU, keyboards.telegram_menu())
    await cb.answer()


@router.callback_query(F.data.startswith(keyboards.CB_CAT))
async def cb_category(cb: CallbackQuery, state: FSMContext, db: Database, cfg: Config) -> None:
    await state.clear()
    code = cb.data[len(keyboards.CB_CAT):]
    info = catalog.CATEGORY_INFO.get(code)
    if info is None:
        await cb.answer(texts.UNKNOWN, show_alert=True)
        return
    rows = db.products(code)
    if not rows:
        await safe_edit(cb, texts.EMPTY_CATEGORY, keyboards.back_home())
        await cb.answer()
        return
    user = current_user(cb, db)
    await safe_edit(
        cb,
        texts.category_menu(info, user.balance, cfg.currency),
        keyboards.products(rows, code, currency=cfg.currency),
    )
    await cb.answer()


@router.callback_query(F.data == keyboards.CB_SUPPORT)
async def cb_support(cb: CallbackQuery, cfg: Config) -> None:
    await safe_edit(cb, texts.support(cfg.support), keyboards.support(cfg.support))
    await cb.answer()


@router.callback_query(F.data == keyboards.CB_TOP)
async def cb_top(cb: CallbackQuery, db: Database, cfg: Config) -> None:
    await safe_edit(cb, texts.top_clients(db.top_users(10), cfg.currency), keyboards.back_home())
    await cb.answer()


@router.callback_query(F.data == keyboards.CB_MY_ORDERS)
async def cb_my_orders(cb: CallbackQuery, db: Database, cfg: Config) -> None:
    rows = db.user_orders(cb.from_user.id, 10)
    await safe_edit(cb, texts.my_orders(rows, cfg.currency), keyboards.back_home())
    await cb.answer()


# ── дар охири ҳама роутерҳо ───────────────────────────────────────────
@fallback_router.message()
async def unknown_message(message: Message, db: Database, cfg: Config) -> None:
    current_user(message, db)
    await message.answer(texts.UNKNOWN, reply_markup=keyboards.back_home())


@fallback_router.callback_query()
async def unknown_callback(cb: CallbackQuery) -> None:
    await cb.answer(texts.UNKNOWN.replace("<b>", "").replace("</b>", ""), show_alert=True)
