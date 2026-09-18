"""Менюи асосӣ ва бахшҳои иттилоотӣ."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from .. import catalog, keyboards, texts
from ..config import Config
from ..db import Database
from .common import current_user, safe_edit, show_main_menu

router = Router(name="menu")
fallback_router = Router(name="fallback")


async def _drop_bottom_keyboard(message: Message, db: Database) -> None:
    """Клавиатураи поёниро аз мизоҷони версияи кӯҳна мебардорад.

    Telegram онро танҳо ҳамроҳи паём бардошта метавонад, бинобар ин
    паёми хидматӣ мефиристем ва фавран нест мекунем. Барои ҳар корбар
    ин як маротиба иҷро мешавад — то ҳар дафъа дар назар нанамояд.
    """
    key = f"kb_cleared:{message.from_user.id}"
    if db.setting(key) == "1":
        return
    try:
        service = await message.answer("⌛️", reply_markup=ReplyKeyboardRemove())
        await service.delete()
    except Exception:  # паём аллакай нест ё ҳуқуқ нарасид — муҳим нест
        pass
    db.set_setting(key, "1")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, db: Database, cfg: Config) -> None:
    await state.clear()
    current_user(message, db)
    await _drop_bottom_keyboard(message, db)
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


@router.message(Command("admin", "panel"))
async def cmd_admin_denied(message: Message, cfg: Config) -> None:
    """Сюда попадают только НЕ админы — роутери админ онҳоро намегузаронад."""
    await message.answer(
        f"{texts.ADMIN_DENIED}\n\n"
        f"🆔 ID-и шумо: <code>{message.from_user.id}</code>\n\n"
        "<i>Агар ин ID-и шумо бошад ва панел лозим бошад — онро ба "
        "<code>SHOP_ADMIN_IDS</code> дар файли <code>.env</code> илова кунед "
        "ва ботро аз нав оғоз кунед.</i>"
    )


@router.message(Command("id"))
async def cmd_id(message: Message) -> None:
    await message.answer(f"🆔 ID-и шумо: <code>{message.from_user.id}</code>")


@router.message(F.text == texts.BTN_HOME)
async def text_home(message: Message, state: FSMContext, db: Database, cfg: Config) -> None:
    await state.clear()
    await show_main_menu(message, db, cfg, edit=False)


@router.callback_query(F.data == keyboards.CB_CHECK_SUB)
async def cb_check_sub(
    cb: CallbackQuery, state: FSMContext, db: Database, cfg: Config, bot
) -> None:
    from ..subscription import missing_channels

    missing = await missing_channels(bot, db, cb.from_user.id)
    if missing:
        await cb.answer(texts.SUB_NOT_YET, show_alert=True)
        await safe_edit(
            cb, texts.subscribe_required(missing), keyboards.subscribe(missing)
        )
        return
    await cb.answer(texts.SUB_OK)
    await state.clear()
    await show_main_menu(cb, db, cfg)


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
    """Агар бахш зербахш дошта бошад — аввал онҳоро нишон медиҳем."""
    await state.clear()
    code = cb.data[len(keyboards.CB_CAT):]
    info = catalog.CATEGORY_INFO.get(code)
    if info is None:
        await cb.answer(texts.UNKNOWN, show_alert=True)
        return

    user = current_user(cb, db)
    partner = db.is_partner(user.id)
    # Зербахши холӣ ба харидор нишон дода намешавад — вагарна экрани
    # иловагӣ бо як тугма пайдо мешуд.
    group_rows = [g for g in db.groups(code) if db.group_products(g["code"])]

    if len(group_rows) > 1:
        await safe_edit(
            cb,
            texts.category_menu(info, user.balance, cfg.currency, partner=partner),
            keyboards.groups(group_rows, code),
        )
        await cb.answer()
        return

    rows = db.group_products(group_rows[0]["code"]) if group_rows else db.products(code)
    if not rows:
        await safe_edit(cb, texts.EMPTY_CATEGORY, keyboards.back_home())
        await cb.answer()
        return
    await safe_edit(
        cb,
        texts.category_menu(info, user.balance, cfg.currency, partner=partner),
        keyboards.products(rows, code, currency=cfg.currency, partner=partner),
    )
    await cb.answer()


@router.callback_query(F.data.startswith(keyboards.CB_GROUP))
async def cb_group(cb: CallbackQuery, state: FSMContext, db: Database, cfg: Config) -> None:
    await state.clear()
    code = cb.data[len(keyboards.CB_GROUP):]
    group = db.group(code)
    if group is None:
        await cb.answer(texts.UNKNOWN, show_alert=True)
        return
    info = catalog.CATEGORY_INFO.get(group["category"])
    rows = db.group_products(code)
    if not rows or info is None:
        await safe_edit(cb, texts.EMPTY_CATEGORY, keyboards.back_home())
        await cb.answer()
        return
    user = current_user(cb, db)
    partner = db.is_partner(user.id)
    await safe_edit(
        cb,
        texts.group_menu(info, group["title"], user.balance, cfg.currency, partner=partner),
        keyboards.products(
            rows, group["category"], currency=cfg.currency, partner=partner,
            back_to=keyboards.CB_CAT + group["category"],
        ),
    )
    await cb.answer()


@router.callback_query(F.data == keyboards.CB_SUPPORT)
async def cb_support(cb: CallbackQuery, db: Database, cfg: Config) -> None:
    whatsapp = db.setting("whatsapp")
    await safe_edit(
        cb,
        texts.support(cfg.support, whatsapp),
        keyboards.support(cfg.support, whatsapp),
    )
    await cb.answer()


@router.callback_query(F.data == keyboards.CB_BALANCE)
async def cb_balance(cb: CallbackQuery, db: Database, cfg: Config) -> None:
    user = current_user(cb, db)
    await safe_edit(
        cb,
        texts.my_balance(user.balance, db.balance_log(user.id, 8), cfg.currency),
        keyboards.need_money(),
    )
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
