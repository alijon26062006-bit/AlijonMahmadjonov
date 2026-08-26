"""Покупка звёзд и Premium: количество → получатель → подтверждение → выдача."""
from __future__ import annotations

import logging
import re

import aiosqlite
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app import db, keyboards, texts
from app.config import settings
from app.handlers.menu import menu_text
from app.money import affordable_stars, fmt, stars_cost
from app.services import delivery
from app.services.fragment import DeliveryProvider
from app.states import Buy

log = logging.getLogger(__name__)
router = Router(name="shop")

USERNAME_RE = re.compile(r"^@?([a-zA-Z][a-zA-Z0-9_]{4,31})$")


def parse_username(raw: str) -> str | None:
    """'@name', 'name', 'https://t.me/name' -> 'name'."""
    text = raw.strip().rstrip("/").rsplit("/", 1)[-1]
    match = USERNAME_RE.match(text)
    return match.group(1) if match else None


def title_of(product_type: str, quantity: int) -> str:
    return f"⭐️ {quantity} звёзд" if product_type == "stars" else f"👑 Premium {quantity} мес."


# ------------------------------------------------------------------ звёзды


@router.callback_query(F.data == "m:stars")
async def cb_stars(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text(
        texts.STARS_ENTRY.format(rate=fmt(settings.star_price_diram)),
        reply_markup=keyboards.stars_entry(),
    )
    await call.answer()


@router.callback_query(F.data == "stars:buy")
async def cb_stars_buy(
    call: CallbackQuery, state: FSMContext, conn: aiosqlite.Connection
) -> None:
    user = await db.get_user(conn, call.from_user.id)
    balance = user.balance if user else 0
    await state.set_state(Buy.quantity)
    await state.update_data(product_type="stars")
    await call.message.edit_text(
        texts.STARS_ASK_QUANTITY.format(
            rate=fmt(settings.star_price_diram),
            min_stars=settings.min_stars,
            max_stars=f"{settings.max_stars:,}".replace(",", " "),
            affordable=affordable_stars(balance),
            balance=fmt(balance),
        ),
        reply_markup=keyboards.cancel(),
    )
    await call.answer()


@router.message(Buy.quantity, F.text)
async def on_quantity(message: Message, state: FSMContext, conn: aiosqlite.Connection) -> None:
    raw = (message.text or "").strip().replace(" ", "")
    if not raw.isdigit():
        await message.answer(texts.STARS_BAD_QUANTITY.format(
            min_stars=settings.min_stars, max_stars=settings.max_stars
        ))
        return

    quantity = int(raw)
    if not settings.min_stars <= quantity <= settings.max_stars:
        await message.answer(texts.STARS_BAD_QUANTITY.format(
            min_stars=settings.min_stars, max_stars=settings.max_stars
        ))
        return

    price = stars_cost(quantity)
    user = await db.get_user(conn, message.from_user.id)
    balance = user.balance if user else 0
    if balance < price:
        await message.answer(
            texts.STARS_NOT_ENOUGH.format(
                need=fmt(price), balance=fmt(balance), missing=fmt(price - balance)
            ),
            reply_markup=keyboards.deposit_methods(),
        )
        await state.clear()
        return

    await state.update_data(quantity=quantity, price=price)
    await _ask_recipient(message, state, "stars", quantity, price)


# ----------------------------------------------------------------- premium


@router.callback_query(F.data == "m:premium")
async def cb_premium(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text(texts.PREMIUM_ENTRY, reply_markup=keyboards.premium_menu())
    await call.answer()


@router.callback_query(F.data.startswith("premium:"))
async def cb_premium_plan(
    call: CallbackQuery, state: FSMContext, conn: aiosqlite.Connection
) -> None:
    months = int(call.data.split(":")[1])
    plan = keyboards.find_premium(months)
    if plan is None:
        await call.answer("Этого тарифа больше нет.", show_alert=True)
        return

    price = int(plan["price"])
    user = await db.get_user(conn, call.from_user.id)
    balance = user.balance if user else 0
    if balance < price:
        await call.message.edit_text(
            texts.STARS_NOT_ENOUGH.format(
                need=fmt(price), balance=fmt(balance), missing=fmt(price - balance)
            ),
            reply_markup=keyboards.deposit_methods(),
        )
        await call.answer()
        return

    await state.update_data(product_type="premium", quantity=months, price=price)
    await _ask_recipient(call, state, "premium", months, price)
    await call.answer()


# -------------------------------------------------------------- получатель


async def _ask_recipient(
    target: Message | CallbackQuery, state: FSMContext,
    product_type: str, quantity: int, price: int,
) -> None:
    await state.set_state(Buy.recipient)
    text = texts.ASK_RECIPIENT.format(
        title=title_of(product_type, quantity), price=fmt(price)
    )
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=keyboards.cancel())
    else:
        await target.answer(text, reply_markup=keyboards.cancel())


@router.callback_query(Buy.confirm, F.data == "order:again")
async def cb_change_recipient(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await _ask_recipient(
        call, state, data["product_type"], data["quantity"], data["price"]
    )
    await call.answer()


@router.message(Buy.recipient, F.text)
async def on_recipient(
    message: Message, state: FSMContext, conn: aiosqlite.Connection,
    provider: DeliveryProvider,
) -> None:
    username = parse_username(message.text or "")
    if not username:
        await message.answer(texts.BAD_USERNAME)
        return

    if not await provider.check_username(username):
        await message.answer(texts.UNKNOWN_RECIPIENT.format(username=username))
        return

    data = await state.get_data()
    price = data["price"]
    user = await db.get_user(conn, message.from_user.id)
    balance = user.balance if user else 0

    await state.update_data(recipient=username)
    await state.set_state(Buy.confirm)
    await message.answer(
        texts.CONFIRM.format(
            title=title_of(data["product_type"], data["quantity"]),
            recipient=username,
            price=fmt(price),
            rest=fmt(max(balance - price, 0)),
        ),
        reply_markup=keyboards.confirm(),
    )


# ------------------------------------------------------------------ оплата


@router.callback_query(Buy.confirm, F.data == "order:go")
async def cb_pay(
    call: CallbackQuery, state: FSMContext, conn: aiosqlite.Connection,
    provider: DeliveryProvider, bot: Bot,
) -> None:
    data = await state.get_data()
    await state.clear()

    title = title_of(data["product_type"], data["quantity"])
    await call.message.edit_text(
        texts.PROCESSING.format(title=title, recipient=data["recipient"])
    )
    await call.answer()

    try:
        await delivery.purchase(
            bot, conn, provider,
            user_id=call.from_user.id,
            product_type=data["product_type"],
            quantity=data["quantity"],
            recipient=data["recipient"],
            price=data["price"],
        )
    except delivery.NotEnoughFunds:
        user = await db.get_user(conn, call.from_user.id)
        balance = user.balance if user else 0
        await call.message.answer(
            texts.STARS_NOT_ENOUGH.format(
                need=fmt(data["price"]), balance=fmt(balance),
                missing=fmt(data["price"] - balance),
            ),
            reply_markup=keyboards.deposit_methods(),
        )
        return

    # Итоговое сообщение (успех, возврат или «проверяю») отправляет
    # delivery-сервис — он единственный знает, чем всё кончилось.
    # Здесь только возвращаем пользователя в меню со свежим балансом.
    await call.message.answer(
        await menu_text(conn, call.from_user.id), reply_markup=keyboards.main_menu()
    )
