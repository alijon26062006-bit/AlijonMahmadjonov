"""Админка: подтверждение заказов и пополнений.

Смена статуса идёт условным UPDATE (... AND status='new'), поэтому если
два админа нажмут кнопку одновременно, деньги вернутся или спишутся
ровно один раз.
"""
from __future__ import annotations

from decimal import Decimal

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

import db
import keyboards as kb
from handlers.common import is_admin, log, money
from texts import DEFAULT_LANG, t

router = Router()


@router.message(Command("admin"))
async def cmd_admin(msg: Message) -> None:
    if not is_admin(msg.from_user.id):
        return
    cur = await db.currency()
    orders = await db.orders_by_status("new", 10)
    topups = await db.topups_by_status("new", 10)

    await msg.answer(
        f"<b>Админка</b>\n\n"
        f"Заказов в очереди: <b>{len(orders)}</b>\n"
        f"Пополнений на проверке: <b>{len(topups)}</b>"
    )

    for o in orders:
        await msg.answer(
            f"🎮 <b>Заказ #{o['id']}</b>\n"
            f"{o['game_name']} — {o['pack_name']}\n"
            f"ID: <code>{o['player_id']}</code>"
            + (f"\nServer: <code>{o['server_id']}</code>" if o.get("server_id") else "")
            + f"\nЦена: <b>{money(o['price'])} {cur}</b>\n"
            f"Клиент: <code>{o['uid']}</code>",
            reply_markup=kb.admin_order_kb(o["id"]),
        )

    for tp in topups:
        await msg.answer(
            f"💰 <b>Пополнение #{tp['id']}</b>\n"
            f"Сумма: <b>{money(tp['amount'])} {cur}</b>\n"
            f"Клиент: <code>{tp['uid']}</code>",
            reply_markup=kb.admin_topup_kb(tp["id"]),
        )

    if not orders and not topups:
        await msg.answer("Очередь пуста.")


async def _ulang(uid: int) -> str:
    user = await db.get_user(uid)
    return (user or {}).get("lang") or DEFAULT_LANG


@router.callback_query(F.data.startswith("ao:"))
async def order_action(cb: CallbackQuery) -> None:
    if not is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return

    _, action, raw_id = cb.data.split(":", 2)
    oid = int(raw_id)
    order = await db.order(oid)
    if not order:
        await cb.answer("Заказ не найден", show_alert=True)
        return

    cur = await db.currency()

    if action == "done":
        if not await db.set_order_status(oid, "done", cb.from_user.id):
            await cb.answer("Уже обработан", show_alert=True)
            return
        await cb.answer("Отмечен выполненным")
        await _edit(cb, f"✅ Заказ #{oid} выполнен")
        await _tell(cb, order["uid"],
                    t(await _ulang(order["uid"]), "n_done", oid=oid,
                      game=order["game_name"], pack=order["pack_name"]))
        return

    # отклонение — возвращаем деньги, но только один раз
    if not await db.set_order_status(oid, "rejected", cb.from_user.id):
        await cb.answer("Уже обработан", show_alert=True)
        return

    price = Decimal(order["price"] or 0)
    refunded = False
    if not order.get("refunded") and price > 0:
        try:
            await db.credit(order["uid"], price,
                            f"Возврат за заказ #{oid}", kind="refund", ref_id=oid)
            await db.mark_refunded(oid)
            refunded = True
        except Exception as e:
            log.exception("возврат по заказу #%s не прошёл: %s", oid, e)

    await cb.answer("Отклонён" + (", деньги возвращены" if refunded else ""))
    await _edit(cb, f"❌ Заказ #{oid} отклонён"
                    + (f", возвращено {money(price)} {cur}" if refunded else ""))
    ulang = await _ulang(order["uid"])
    await _tell(cb, order["uid"],
                t(ulang, "n_rejected", oid=oid)
                + (t(ulang, "n_refund", amount=money(price), cur=cur)
                   if refunded else ""))


@router.callback_query(F.data.startswith("at:"))
async def topup_action(cb: CallbackQuery) -> None:
    if not is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return

    _, action, raw_id = cb.data.split(":", 2)
    tid = int(raw_id)
    tp = await db.topup(tid)
    if not tp:
        await cb.answer("Заявка не найдена", show_alert=True)
        return

    cur = await db.currency()
    amount = Decimal(tp["amount"] or 0)

    if action == "ok":
        if not await db.set_topup_status(tid, "done", cb.from_user.id):
            await cb.answer("Уже обработана", show_alert=True)
            return
        new_bal = await db.credit(tp["uid"], amount,
                                  f"Пополнение #{tid}", kind="topup", ref_id=tid)
        await cb.answer("Зачислено")
        await _edit(cb, f"✅ Пополнение #{tid} зачислено: {money(amount)} {cur}")
        await _tell(cb, tp["uid"],
                    t(await _ulang(tp["uid"]), "n_topup_ok",
                      amount=money(amount), cur=cur, balance=money(new_bal)))
        return

    if not await db.set_topup_status(tid, "rejected", cb.from_user.id):
        await cb.answer("Уже обработана", show_alert=True)
        return
    await cb.answer("Отклонена")
    await _edit(cb, f"❌ Пополнение #{tid} отклонено")
    await _tell(cb, tp["uid"],
                t(await _ulang(tp["uid"]), "n_topup_rej", tid=tid))


async def _edit(cb: CallbackQuery, text: str) -> None:
    try:
        await cb.message.edit_text(text)
    except Exception:
        pass


async def _tell(cb: CallbackQuery, uid: int, text: str) -> None:
    """Сообщить клиенту. Если он заблокировал бота — не падаем."""
    try:
        await cb.bot.send_message(uid, text)
    except Exception as e:
        log.warning("клиенту %s не доставлено: %s", uid, e)
