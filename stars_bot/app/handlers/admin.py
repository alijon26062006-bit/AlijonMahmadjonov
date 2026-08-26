"""Админка: подтверждение оплат, повтор выдачи, статистика."""
from __future__ import annotations

import logging

import aiosqlite
from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message

from app import db, keyboards, texts
from app.config import settings
from app.services import delivery
from app.services.fragment import DeliveryProvider
from app.texts import money

log = logging.getLogger(__name__)
router = Router(name="admin")


def _is_admin(user_id: int) -> bool:
    return settings.is_admin(user_id)


# Все хендлеры этого роутера — только для админов.
router.message.filter(F.from_user.func(lambda u: _is_admin(u.id)))
router.callback_query.filter(F.from_user.func(lambda u: _is_admin(u.id)))


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    await message.answer(texts.ADMIN_HELP)


@router.message(Command("stats"))
async def cmd_stats(message: Message, conn: aiosqlite.Connection) -> None:
    data = await db.stats(conn)
    lines = [f"👥 Пользователей: <b>{data['users']}</b>", f"💰 Выручка: <b>{money(data['revenue'])}</b>", ""]
    for status, info in sorted(data["by_status"].items()):
        lines.append(f"{db.STATUS_TITLES.get(status, status)}: {info['count']}")
    await message.answer("📊 <b>Статистика</b>\n\n" + "\n".join(lines))


@router.message(Command("orders"))
async def cmd_orders(message: Message, conn: aiosqlite.Connection) -> None:
    await _dump_orders(message, await db.list_orders(conn, limit=15), "Последние заказы")


@router.message(Command("pending"))
async def cmd_pending(message: Message, conn: aiosqlite.Connection) -> None:
    orders = await db.list_orders(conn, status=db.STATUS_PENDING_REVIEW, limit=15)
    await _dump_orders(message, orders, "Заказы на проверке")


async def _dump_orders(message: Message, orders: list[db.Order], title: str) -> None:
    if not orders:
        await message.answer(f"<b>{title}</b>\n\nПусто.")
        return
    lines = [
        f"<b>№{o.id}</b> · {o.title} → @{o.recipient}\n"
        f"{money(o.price)} · {o.status_title} · <code>{o.user_id}</code>"
        for o in orders
    ]
    await message.answer(f"<b>{title}</b>\n\n" + "\n\n".join(lines))


@router.message(Command("balance"))
async def cmd_balance(message: Message, provider: DeliveryProvider) -> None:
    try:
        balance = await provider.get_balance()
    except Exception as exc:  # noqa: BLE001
        await message.answer(f"⚠️ Не удалось получить баланс:\n<code>{exc}</code>")
        return
    await message.answer(f"💼 Баланс Fragment: <b>{balance}</b>")


@router.message(Command("ban"))
async def cmd_ban(message: Message, command: CommandObject, conn: aiosqlite.Connection) -> None:
    await _set_ban(message, command, conn, banned=True)


@router.message(Command("unban"))
async def cmd_unban(message: Message, command: CommandObject, conn: aiosqlite.Connection) -> None:
    await _set_ban(message, command, conn, banned=False)


async def _set_ban(
    message: Message, command: CommandObject, conn: aiosqlite.Connection, *, banned: bool
) -> None:
    if not command.args or not command.args.strip().isdigit():
        await message.answer("Использование: <code>/ban 123456789</code>")
        return
    user_id = int(command.args.strip())
    await db.set_banned(conn, user_id, banned)
    await message.answer(("🚫 Забанен: " if banned else "✅ Разбанен: ") + f"<code>{user_id}</code>")


@router.message(Command("retry"))
async def cmd_retry(
    message: Message,
    command: CommandObject,
    conn: aiosqlite.Connection,
    provider: DeliveryProvider,
    bot: Bot,
) -> None:
    if not command.args or not command.args.strip().isdigit():
        await message.answer("Использование: <code>/retry 42</code>")
        return
    order_id = int(command.args.strip())
    order = await db.get_order(conn, order_id)
    if order is None:
        await message.answer("Заказ не найден.")
        return
    if order.status != db.STATUS_FAILED:
        await message.answer(f"Повтор возможен только для упавших заказов (сейчас: {order.status_title}).")
        return
    if not await db.transition(
        conn, order_id, expected=db.STATUS_FAILED, new=db.STATUS_DELIVERING,
        reviewed_by=message.from_user.id,
    ):
        await message.answer(texts.ADMIN_ALREADY_HANDLED)
        return
    _, report = await delivery.deliver(bot, conn, provider, order)
    await message.answer(report)


# ------------------------------------------------------ кнопки под заявкой


@router.callback_query(F.data.startswith("admin:approve:"))
async def cb_approve(
    call: CallbackQuery, conn: aiosqlite.Connection, provider: DeliveryProvider, bot: Bot
) -> None:
    order_id = int(call.data.rsplit(":", 1)[1])
    order = await db.get_order(conn, order_id)
    if order is None:
        await call.answer("Заказ не найден.", show_alert=True)
        return

    # Атомарный переход: второй админ, нажавший кнопку, получит False.
    if not await db.transition(
        conn, order_id,
        expected=db.STATUS_PENDING_REVIEW,
        new=db.STATUS_DELIVERING,
        reviewed_by=call.from_user.id,
    ):
        await call.answer(texts.ADMIN_ALREADY_HANDLED, show_alert=True)
        return

    await call.answer(texts.ADMIN_APPROVED.format(order_id=order_id))
    await _strip_buttons(call)

    ok, report = await delivery.deliver(bot, conn, provider, order)
    await call.message.reply(report, reply_markup=None if ok else keyboards.admin_retry(order_id))


@router.callback_query(F.data.startswith("admin:retry:"))
async def cb_retry(
    call: CallbackQuery, conn: aiosqlite.Connection, provider: DeliveryProvider, bot: Bot
) -> None:
    order_id = int(call.data.rsplit(":", 1)[1])
    order = await db.get_order(conn, order_id)
    if order is None:
        await call.answer("Заказ не найден.", show_alert=True)
        return
    if not await db.transition(
        conn, order_id, expected=db.STATUS_FAILED, new=db.STATUS_DELIVERING,
        reviewed_by=call.from_user.id,
    ):
        await call.answer(texts.ADMIN_ALREADY_HANDLED, show_alert=True)
        return
    await call.answer("Повторяю выдачу…")
    await _strip_buttons(call)
    ok, report = await delivery.deliver(bot, conn, provider, order)
    await call.message.reply(report, reply_markup=None if ok else keyboards.admin_retry(order_id))


@router.callback_query(F.data.startswith("admin:reject:"))
async def cb_reject(call: CallbackQuery, conn: aiosqlite.Connection, bot: Bot) -> None:
    order_id = int(call.data.rsplit(":", 1)[1])
    order = await db.get_order(conn, order_id)
    if order is None:
        await call.answer("Заказ не найден.", show_alert=True)
        return
    if not await db.transition(
        conn, order_id,
        expected=db.STATUS_PENDING_REVIEW,
        new=db.STATUS_REJECTED,
        reviewed_by=call.from_user.id,
    ):
        await call.answer(texts.ADMIN_ALREADY_HANDLED, show_alert=True)
        return

    await delivery.notify_user(
        bot, order.user_id,
        texts.ORDER_REJECTED.format(
            order_id=order_id, reason="оплата не найдена", support=texts.support()
        ),
    )
    await call.answer(texts.ADMIN_REJECTED.format(order_id=order_id))
    await _strip_buttons(call)
    await call.message.reply(texts.ADMIN_REJECTED.format(order_id=order_id))


async def _strip_buttons(call: CallbackQuery) -> None:
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception as exc:  # noqa: BLE001 — сообщение могло быть уже изменено
        log.debug("Не смог убрать кнопки: %s", exc)
