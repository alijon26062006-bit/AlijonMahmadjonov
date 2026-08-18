"""Заказы в боте: список покупателю, карточка и кнопки владельцу, панель."""
import html

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.bot import texts
from app.config import get_settings
from app.db.models import (
    O_CANCELED, O_CONFIRMED, O_DONE, O_NEW, O_PAID, Order, User,
)
from app.services import mailer, order_service, product_service

router = Router()

# Что предлагаем нажать в каждом состоянии — короткие подписи для кнопок
NEXT_LABELS = {
    O_CONFIRMED: "✅ Подтвердить",
    O_PAID: "💰 Оплачен",
    "shipped": "📦 Отправлен",
    O_DONE: "🎉 Получен",
    O_CANCELED: "❌ Отменить",
}


def money(value) -> str:
    return f"{round(float(value)):,}".replace(",", " ")


def order_kb(order: Order) -> InlineKeyboardMarkup | None:
    from app.db.models import ORDER_FLOW
    row = [InlineKeyboardButton(text=NEXT_LABELS.get(s, s),
                                callback_data=f"ord:{order.id}:{s}")
           for s in ORDER_FLOW.get(order.status, ())]
    return InlineKeyboardMarkup(inline_keyboard=[row]) if row else None


def order_text(data: dict, sign: str) -> str:
    items = "\n".join(
        f"• {html.escape(i['title'])} — {i['variant']} × {i['qty']} = "
        f"{money(i['line_total'])} {sign}" for i in data["items"])
    place = " · ".join(p for p in (data.get("city"), data.get("address")) if p) \
        or data["delivery_label"]
    comment = f"\n💬 {html.escape(data['comment'])}" if data.get("comment") else ""
    return texts.ORDER_NEW_ADMIN.format(
        number=data["number"], items=items, goods=money(data["goods_total"]),
        delivery=money(data["delivery_price"]),
        delivery_label=data["delivery_label"], total=money(data["total"]),
        sign=sign, name=html.escape(data["customer_name"]),
        phone=html.escape(data["phone"]), place=html.escape(place),
        comment=comment)


async def notify_new_order(bot: Bot, session: AsyncSession, order: Order) -> None:
    """Заказ владельцу — карточкой с кнопками, покупателю — подтверждением."""
    s = get_settings()
    data = await order_service.as_dict(session, order)
    text = order_text(data, s.currency_sign) + \
        f"\n\n<i>{data['status_label']}</i>"
    kb = order_kb(order)

    targets = list(s.admin_id_list)
    if s.admin_chat_id:
        targets.append(s.admin_chat_id)
    for chat_id in targets:
        try:
            await bot.send_message(chat_id, text, reply_markup=kb)
        except Exception:
            pass                     # владелец не запускал бота — не беда

    buyer = await session.get(User, order.user_id) if order.user_id else None
    if buyer is None:
        return

    items = "\n".join(
        f"• {html.escape(i['title'])} — {i['variant']} × {i['qty']}"
        for i in data["items"])
    msg = texts.ORDER_CREATED_BUYER.format(
        number=data["number"], items=items,
        total=money(data["total"]), sign=s.currency_sign)
    if s.payment_ready:
        msg += texts.PAYMENT_INFO.format(
            phone=s.kaspi_phone or "—", name=s.kaspi_name or "—",
            number=data["number"])

    if buyer.tg_id and buyer.notify_telegram and not buyer.bot_blocked:
        try:
            await bot.send_message(buyer.tg_id, msg)
        except Exception:
            buyer.bot_blocked = True
            await session.commit()

    # письмо о принятом заказе уходит независимо от переключателей: в нём
    # реквизиты, без которых человек просто не сможет заплатить
    lines = [f"Заказ №{data['number']} принят.", ""]
    lines += [f"{i['title']} — {i['variant']} × {i['qty']} = "
              f"{money(i['line_total'])} {s.currency_sign}"
              for i in data["items"]]
    lines += ["", f"Доставка: {data['delivery_label']} — "
                  f"{money(data['delivery_price'])} {s.currency_sign}",
              f"Итого: {money(data['total'])} {s.currency_sign}"]
    if s.payment_ready:
        lines += ["", "Оплата переводом на Kaspi:",
                  f"Номер: {s.kaspi_phone or '—'}",
                  f"Получатель: {s.kaspi_name or '—'}",
                  f"В комментарии к переводу укажите номер заказа "
                  f"{data['number']}."]
    await mailer.send(buyer.email, f"Заказ №{data['number']} принят", lines)


async def notify_status(bot: Bot, session: AsyncSession, order: Order) -> None:
    template = texts.ORDER_STATUS_BUYER.get(order.status)
    if not template or not order.user_id:
        return
    buyer = await session.get(User, order.user_id)
    if buyer is None:
        return

    tracking = f"\nТрек-номер: <code>{html.escape(order.tracking)}</code>" \
        if order.tracking else ""
    if buyer.tg_id and buyer.notify_telegram and not buyer.bot_blocked:
        try:
            await bot.send_message(
                buyer.tg_id,
                template.format(number=order.number, tracking=tracking))
        except Exception:
            buyer.bot_blocked = True
            await session.commit()

    if buyer.notify_email:
        plain = template.format(number=order.number,
                                tracking=f" Трек-номер: {order.tracking}"
                                if order.tracking else "")
        plain = plain.replace("<code>", "").replace("</code>", "")
        await mailer.send(buyer.email, f"Заказ №{order.number}", [plain])


@router.callback_query(F.data.startswith("ord:"))
async def change_status(cb: CallbackQuery, session: AsyncSession, bot: Bot,
                        user: User) -> None:
    if not user.is_admin:
        await cb.answer("Только для владельца", show_alert=True)
        return
    _, raw_id, status = cb.data.split(":")
    try:
        order = await order_service.set_status(session, int(raw_id), status)
    except product_service.ShopError as e:
        await cb.answer(str(e), show_alert=True)
        return

    s = get_settings()
    data = await order_service.as_dict(session, order)
    await cb.answer(data["status_label"])
    try:
        await cb.message.edit_text(
            order_text(data, s.currency_sign) + f"\n\n<i>{data['status_label']}</i>",
            reply_markup=order_kb(order))
    except Exception:
        pass
    await notify_status(bot, session, order)


@router.message(F.text == texts.MENU_ORDERS)
@router.message(Command("orders"))
async def my_orders(message: Message, session: AsyncSession, user: User) -> None:
    s = get_settings()
    rows = (await session.scalars(
        select(Order).where(Order.user_id == user.id)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc()).limit(10))).all()
    if not rows:
        await message.answer(texts.ORDERS_EMPTY)
        return
    for order in rows:
        data = await order_service.as_dict(session, order)
        items = "\n".join(
            f"• {html.escape(i['title'])} — {i['variant']} × {i['qty']}"
            for i in data["items"])
        tracking = f"\nТрек: <code>{html.escape(order.tracking)}</code>" \
            if order.tracking else ""
        await message.answer(
            f"<b>Заказ №{data['number']}</b> · {data['status_label']}\n"
            f"{items}\n<b>Итого: {money(data['total'])} {s.currency_sign}</b>"
            f"{tracking}")


@router.message(Command("panel"))
@router.message(F.text == texts.MENU_PANEL)
async def panel(message: Message, session: AsyncSession, user: User) -> None:
    if not user.is_admin:
        await message.answer(texts.NOT_ADMIN.format(tg_id=user.tg_id))
        return
    s = get_settings()
    products = await product_service.counters(session)
    orders = await order_service.stats(session)
    low = await product_service.low_stock(session)
    low_text = texts.LOW_STOCK_HEAD + "\n".join(
        f"   {html.escape(t)} — {' '.join(x for x in (size, color) if x)}: {n} шт."
        for t, size, color, n in low) if low else texts.LOW_STOCK_EMPTY

    from app.bot.handlers.start import open_shop_kb
    await message.answer(
        texts.PANEL.format(
            shop=s.shop_name, sign=s.currency_sign,
            revenue_week=money(orders["revenue_week"]),
            revenue_total=money(orders["revenue_total"]),
            average=money(orders["average"]),
            low=low_text, **products, **{k: orders[k] for k in
                                         ("new", "in_work", "done", "canceled",
                                          "today", "week")}),
        reply_markup=open_shop_kb("/admin", "🛠 Управление"))
