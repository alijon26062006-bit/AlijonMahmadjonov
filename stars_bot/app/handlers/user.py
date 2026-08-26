"""Пользовательский сценарий: меню → выбор товара → получатель → оплата → чек."""
from __future__ import annotations

import logging
import re

import aiosqlite
from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app import catalog, db, keyboards, texts
from app.config import settings
from app.services.fragment import DeliveryProvider
from app.states import Purchase
from app.texts import money

log = logging.getLogger(__name__)
router = Router(name="user")

USERNAME_RE = re.compile(r"^@?([a-zA-Z][a-zA-Z0-9_]{4,31})$")


def _parse_username(raw: str) -> str | None:
    raw = raw.strip().rsplit("/", 1)[-1]  # принимаем и ссылку t.me/username
    match = USERNAME_RE.match(raw)
    return match.group(1) if match else None


async def _show_menu(message: Message, name: str) -> None:
    await message.answer(texts.START.format(name=name), reply_markup=keyboards.main_menu())


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await _show_menu(message, message.from_user.first_name or "друг")


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.MENU_PROMPT, reply_markup=keyboards.main_menu())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(texts.HELP.format(support=texts.support()))


@router.callback_query(F.data == "menu:main")
async def cb_main(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text(texts.MENU_PROMPT, reply_markup=keyboards.main_menu())
    await call.answer()


@router.callback_query(F.data == "menu:stars")
async def cb_stars(call: CallbackQuery) -> None:
    await call.message.edit_text(texts.CHOOSE_STARS, reply_markup=keyboards.stars_menu())
    await call.answer()


@router.callback_query(F.data == "menu:premium")
async def cb_premium(call: CallbackQuery) -> None:
    await call.message.edit_text(texts.CHOOSE_PREMIUM, reply_markup=keyboards.premium_menu())
    await call.answer()


@router.callback_query(F.data == "menu:help")
async def cb_help(call: CallbackQuery) -> None:
    await call.message.edit_text(
        texts.HELP.format(support=texts.support()), reply_markup=keyboards.back_to_menu()
    )
    await call.answer()


@router.callback_query(F.data == "menu:orders")
async def cb_orders(call: CallbackQuery, conn: aiosqlite.Connection) -> None:
    orders = await db.list_orders(conn, user_id=call.from_user.id, limit=10)
    if not orders:
        await call.message.edit_text(texts.NO_ORDERS, reply_markup=keyboards.back_to_menu())
        await call.answer()
        return
    lines = [
        f"<b>№{o.id}</b> · {o.title} → @{o.recipient}\n"
        f"{money(o.price)} · {o.status_title}"
        for o in orders
    ]
    await call.message.edit_text(
        "🧾 <b>Твои заказы</b>\n\n" + "\n\n".join(lines),
        reply_markup=keyboards.back_to_menu(),
    )
    await call.answer()


# ------------------------------------------------------------ оформление


@router.callback_query(F.data.startswith("buy:"))
async def cb_buy(call: CallbackQuery, state: FSMContext) -> None:
    _, product_type, raw_value = call.data.split(":")
    value = int(raw_value)
    package = catalog.find_stars(value) if product_type == "stars" else catalog.find_premium(value)
    if package is None:
        await call.answer("Этого пакета больше нет в продаже.", show_alert=True)
        return

    await state.set_state(Purchase.recipient)
    await state.update_data(product_type=product_type, quantity=value, price=package.price)
    await call.message.edit_text(
        texts.ASK_RECIPIENT.format(title=package.title, price=money(package.price))
    )
    await call.answer()


@router.callback_query(F.data == "order:edit_recipient")
async def cb_edit_recipient(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("product_type"):
        await call.answer("Начни заказ заново: /menu", show_alert=True)
        return
    await state.set_state(Purchase.recipient)
    await call.message.edit_text(
        texts.ASK_RECIPIENT.format(
            title=_title(data["product_type"], data["quantity"]),
            price=money(data["price"]),
        )
    )
    await call.answer()


def _title(product_type: str, quantity: int) -> str:
    return f"⭐ {quantity} звёзд" if product_type == "stars" else f"💎 Premium {quantity} мес."


@router.message(Purchase.recipient, F.text)
async def on_recipient(
    message: Message, state: FSMContext, provider: DeliveryProvider
) -> None:
    username = _parse_username(message.text or "")
    if not username:
        await message.answer(texts.BAD_USERNAME)
        return

    if not await provider.check_username(username):
        await message.answer(texts.UNKNOWN_RECIPIENT.format(username=username))
        return

    data = await state.get_data()
    await state.update_data(recipient=username)
    await state.set_state(Purchase.confirm)
    await message.answer(
        texts.CONFIRM_ORDER.format(
            title=_title(data["product_type"], data["quantity"]),
            recipient=username,
            price=money(data["price"]),
        ),
        reply_markup=keyboards.confirm_order(),
    )


@router.callback_query(Purchase.confirm, F.data == "order:create")
async def cb_create_order(
    call: CallbackQuery, state: FSMContext, conn: aiosqlite.Connection
) -> None:
    data = await state.get_data()
    order = await db.create_order(
        conn,
        user_id=call.from_user.id,
        product_type=data["product_type"],
        quantity=data["quantity"],
        recipient=data["recipient"],
        price=data["price"],
        currency=settings.currency,
    )
    await state.set_state(Purchase.receipt)
    await state.update_data(order_id=order.id)

    holder = f"Получатель: <b>{settings.payment_card_holder}</b>\n" if settings.payment_card_holder else ""
    bank = f"Банк: {settings.payment_bank}" if settings.payment_bank else ""
    await call.message.edit_text(
        texts.PAYMENT_INSTRUCTIONS.format(
            order_id=order.id,
            title=order.title,
            recipient=order.recipient,
            price=money(order.price),
            card=settings.payment_card_number or "— реквизиты не заданы —",
            holder=holder,
            bank=bank,
        ),
        reply_markup=keyboards.cancel_order(order.id),
    )
    await call.answer()


@router.callback_query(F.data.startswith("order:cancel:"))
async def cb_cancel_order(
    call: CallbackQuery, state: FSMContext, conn: aiosqlite.Connection
) -> None:
    order_id = int(call.data.rsplit(":", 1)[1])
    order = await db.get_order(conn, order_id)
    if order is None or order.user_id != call.from_user.id:
        await call.answer("Заказ не найден.", show_alert=True)
        return
    ok = await db.transition(
        conn, order_id, expected=db.STATUS_AWAITING_RECEIPT, new=db.STATUS_CANCELLED
    )
    if not ok:
        await call.answer("Заказ уже нельзя отменить — напиши в поддержку.", show_alert=True)
        return
    await state.clear()
    await call.message.edit_text(
        texts.ORDER_CANCELLED.format(order_id=order_id), reply_markup=keyboards.main_menu()
    )
    await call.answer()


@router.message(Purchase.receipt, F.photo | F.document)
async def on_receipt(
    message: Message, state: FSMContext, conn: aiosqlite.Connection, bot: Bot
) -> None:
    data = await state.get_data()
    order = await db.get_order(conn, data.get("order_id", 0))
    if order is None or order.user_id != message.from_user.id:
        await state.clear()
        await message.answer("Заказ не найден. Начни заново: /menu")
        return

    file_id = message.photo[-1].file_id if message.photo else message.document.file_id
    ok = await db.transition(
        conn, order.id,
        expected=db.STATUS_AWAITING_RECEIPT,
        new=db.STATUS_PENDING_REVIEW,
        receipt_file_id=file_id,
    )
    if not ok:
        await message.answer("По этому заказу чек уже принят — жди ответа.")
        return

    await state.clear()
    await message.answer(
        texts.RECEIPT_ACCEPTED.format(order_id=order.id), reply_markup=keyboards.main_menu()
    )
    await _notify_admins(bot, order, message)


@router.message(Purchase.receipt)
async def on_receipt_wrong_type(message: Message) -> None:
    await message.answer(texts.NEED_PHOTO)


async def _notify_admins(bot: Bot, order: db.Order, message: Message) -> None:
    buyer = f"@{message.from_user.username}" if message.from_user.username else (
        message.from_user.first_name or "без имени"
    )
    caption = texts.ADMIN_NEW_ORDER.format(
        order_id=order.id,
        title=order.title,
        recipient=order.recipient,
        price=money(order.price),
        buyer=buyer,
        user_id=order.user_id,
    )
    targets = list(settings.admin_ids)
    if settings.orders_chat_id:
        targets.append(settings.orders_chat_id)

    for chat_id in targets:
        try:
            await message.copy_to(
                chat_id, caption=caption, reply_markup=keyboards.admin_review(order.id)
            )
        except TelegramAPIError as exc:
            log.warning("Не смог отправить заявку %s в чат %s: %s", order.id, chat_id, exc)
