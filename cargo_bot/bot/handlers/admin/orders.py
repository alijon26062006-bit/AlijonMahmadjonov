"""Управление заявками: список, карточка, смена статуса с уведомлением клиента."""
import math

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.filters import IsAdmin
from bot.keyboards import paginate_kb
from bot.models import Order, User
from bot.repositories import Repository, SettingsRepo
from bot.services import log_action, notify_user
from bot.utils import fmt_num

router = Router()
router.callback_query.filter(IsAdmin())

B = InlineKeyboardButton
PER_PAGE = 8


@router.callback_query(F.data.startswith("adm:orders:"))
async def orders_list(cb: CallbackQuery, session: AsyncSession):
    page = int(cb.data.split(":")[2])
    total = await session.scalar(select(func.count(Order.id))) or 0
    pages = max(1, math.ceil(total / PER_PAGE))
    page = min(max(1, page), pages)
    rows = (await session.scalars(
        select(Order).order_by(Order.id.desc())
        .offset((page - 1) * PER_PAGE).limit(PER_PAGE)
    )).all()
    buttons = [[B(text=f"{o.number} | {o.name} | {o.status}",
                  callback_data=f"adm:order:{o.id}")] for o in rows]
    await cb.message.edit_text(
        f"📦 <b>Заявки</b> (всего: {total})",
        reply_markup=paginate_kb("adm:orders", page, pages, extra_rows=buttons),
    )
    await cb.answer()


async def _order_view(session: AsyncSession, order: Order):
    user = await session.get(User, order.user_id) if order.user_id else None
    statuses = await SettingsRepo(session).get_json("order_statuses", []) or []
    text = "\n".join([
        f"📦 <b>Заявка {order.number}</b>",
        f"Статус: <b>{order.status}</b>",
        "",
        f"👤 {order.name}",
        f"📱 {order.phone}",
        f"🔗 {order.product_url or '-'}",
        f"📄 {order.description or '-'}",
        f"⚖️ {fmt_num(order.weight) + ' кг' if order.weight is not None else '-'} | "
        f"📐 {fmt_num(order.volume) + ' м³' if order.volume is not None else '-'}",
        f"💬 {order.comment or '-'}",
        f"🕓 {order.created_at.strftime('%d.%m.%Y %H:%M') if order.created_at else '-'}",
        f"От: @{user.username if user and user.username else '-'} "
        f"(<code>{user.tg_id if user else '-'}</code>)",
        "",
        "Сменить статус:",
    ])
    rows = [[B(text=("✅ " if s == order.status else "") + s,
               callback_data=f"adm:ostatus:{order.id}:{i}")]
            for i, s in enumerate(statuses)]
    rows.append([B(text="◀️ К заявкам", callback_data="adm:orders:1")])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data.startswith("adm:order:"))
async def order_view(cb: CallbackQuery, session: AsyncSession):
    order = await Repository(session, Order).get(int(cb.data.split(":")[2]))
    if not order:
        await cb.answer("Заявка не найдена", show_alert=True)
        return
    text, kb = await _order_view(session, order)
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data.startswith("adm:ostatus:"))
async def order_status(cb: CallbackQuery, session: AsyncSession, bot: Bot):
    _, _, order_id, idx = cb.data.split(":")
    order = await Repository(session, Order).get(int(order_id))
    statuses = await SettingsRepo(session).get_json("order_statuses", []) or []
    if not order or int(idx) >= len(statuses):
        await cb.answer("Ошибка", show_alert=True)
        return
    new_status = statuses[int(idx)]
    old_status = order.status
    if new_status == old_status:
        await cb.answer("Этот статус уже установлен")
        return
    await Repository(session, Order).update(order, status=new_status)
    await log_action(session, cb.from_user.id, "status", "orders", order.id,
                     old={"status": old_status}, new={"status": new_status})
    if order.user_id:
        user = await session.get(User, order.user_id)
        if user:
            await notify_user(bot, user.tg_id,
                              f"ℹ️ Статус вашей заявки <b>{order.number}</b> "
                              f"изменён: <b>{new_status}</b>")
    text, kb = await _order_view(session, order)
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer("Статус обновлён")
