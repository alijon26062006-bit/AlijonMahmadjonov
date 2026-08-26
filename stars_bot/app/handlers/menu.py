"""Главное меню, информация, калькулятор, топ клиентов."""
from __future__ import annotations

import aiosqlite
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app import db, keyboards, texts
from app import runtime
from app.money import fmt4, affordable_stars, fmt, parse, stars_cost
from app.states import Calc

router = Router(name="menu")


async def menu_text(conn: aiosqlite.Connection, user_id: int) -> str:
    user = await db.get_user(conn, user_id)
    return texts.MENU.format(balance=fmt(user.balance if user else 0))


async def render_menu(target: Message | CallbackQuery, conn: aiosqlite.Connection) -> None:
    """Показать меню. У Message берём отправителя, у CallbackQuery — нажавшего."""
    text = await menu_text(conn, target.from_user.id)
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=keyboards.main_menu())
    else:
        await target.answer(text, reply_markup=keyboards.main_menu())


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, conn: aiosqlite.Connection) -> None:
    await state.clear()
    await render_menu(message, conn)


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext, conn: aiosqlite.Connection) -> None:
    await state.clear()
    await render_menu(message, conn)


@router.callback_query(F.data == "m:main")
async def cb_main(call: CallbackQuery, state: FSMContext, conn: aiosqlite.Connection) -> None:
    await state.clear()
    await render_menu(call, conn)
    await call.answer()


@router.callback_query(F.data == "m:info")
async def cb_info(call: CallbackQuery) -> None:
    await call.message.edit_text(
        texts.INFO.format(support=texts.support()), reply_markup=keyboards.back()
    )
    await call.answer()


@router.callback_query(F.data == "m:top")
async def cb_top(call: CallbackQuery, conn: aiosqlite.Connection) -> None:
    clients = await db.top_clients(conn, limit=10)
    if not clients:
        await call.message.edit_text(texts.TOP_EMPTY, reply_markup=keyboards.back())
        await call.answer()
        return
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for index, client in enumerate(clients):
        badge = medals[index] if index < len(medals) else f"{index + 1}."
        name = f"@{client.username}" if client.username else (client.first_name or "Аноним")
        lines.append(f"{badge} {name} — <b>{fmt(client.total_deposit)}</b>")
    await call.message.edit_text(
        texts.TOP_CLIENTS.format(items="\n".join(lines)), reply_markup=keyboards.back()
    )
    await call.answer()


@router.callback_query(F.data == "m:calc")
async def cb_calc(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Calc.query)
    await call.message.edit_text(
        texts.CALC_ASK.format(rate=fmt4(runtime.star_price_e4())),
        reply_markup=keyboards.cancel("‹ В меню"),
    )
    await call.answer()


@router.message(Calc.query, F.text)
async def on_calc(message: Message) -> None:
    raw = (message.text or "").strip().lower()

    # «100с» / «100 сомони» — считаем, сколько звёзд выйдет за эту сумму.
    money_part = raw.rstrip(".")
    for suffix in ("сомони", "смн", "с", "tjs"):
        if money_part.endswith(suffix):
            amount = parse(money_part[: -len(suffix)])
            if amount is not None and amount > 0:
                await message.answer(texts.CALC_MONEY.format(
                    money=fmt(amount), stars=affordable_stars(amount)
                ))
                return
            break

    # Голое число — считаем стоимость такого количества звёзд.
    if raw.isdigit() and int(raw) > 0:
        quantity = int(raw)
        await message.answer(texts.CALC_STARS.format(
            stars=quantity, price=fmt(stars_cost(quantity))
        ))
        return

    await message.answer(texts.CALC_BAD)
