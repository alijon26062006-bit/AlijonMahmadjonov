"""Админ-меню, статистика, просмотр пользователей, расчётов и журнала."""
import math

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.filters import IsAdmin
from bot.keyboards import admin_menu, paginate_kb
from bot.models import Calculation, Log, Order, Track, User
from bot.utils import fmt_num

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

PER_PAGE = 10


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🛠 <b>Панель администратора</b>", reply_markup=admin_menu())


@router.callback_query(F.data == "adm:menu")
async def cb_admin_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("🛠 <b>Панель администратора</b>", reply_markup=admin_menu())
    await cb.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(cb: CallbackQuery):
    await cb.answer()


@router.callback_query(F.data == "adm:stats")
async def cb_stats(cb: CallbackQuery, session: AsyncSession):
    users = await session.scalar(select(func.count(User.id)))
    orders = await session.scalar(select(func.count(Order.id)))
    calcs = await session.scalar(select(func.count(Calculation.id)))
    tracks = await session.scalar(select(func.count(Track.id)))
    by_status = (await session.execute(
        select(Order.status, func.count(Order.id)).group_by(Order.status)
    )).all()
    lines = [
        "📊 <b>Статистика</b>",
        "",
        f"👥 Пользователей: <b>{users}</b>",
        f"📦 Заявок: <b>{orders}</b>",
        f"🧮 Расчётов: <b>{calcs}</b>",
        f"🔎 Треков: <b>{tracks}</b>",
    ]
    if by_status:
        lines.append("\n<b>Заявки по статусам:</b>")
        lines += [f"• {status}: {count}" for status, count in by_status]
    await cb.message.edit_text("\n".join(lines), reply_markup=paginate_kb("adm:stats_p", 1, 1))
    await cb.answer()


async def _paged(session: AsyncSession, model, page: int):
    total = await session.scalar(select(func.count(model.id))) or 0
    pages = max(1, math.ceil(total / PER_PAGE))
    page = min(max(1, page), pages)
    rows = (await session.scalars(
        select(model).order_by(model.id.desc())
        .offset((page - 1) * PER_PAGE).limit(PER_PAGE)
    )).all()
    return rows, page, pages, total


@router.callback_query(F.data.startswith("adm:users:"))
async def cb_users(cb: CallbackQuery, session: AsyncSession):
    rows, page, pages, total = await _paged(session, User, int(cb.data.split(":")[2]))
    lines = [f"👥 <b>Пользователи</b> (всего: {total})", ""]
    for u in rows:
        reg = u.created_at.strftime("%d.%m.%Y") if u.created_at else ""
        lines.append(f"• #{u.id} {u.full_name or '-'} @{u.username or '-'} "
                     f"(<code>{u.tg_id}</code>) — {reg}")
    await cb.message.edit_text("\n".join(lines),
                               reply_markup=paginate_kb("adm:users", page, pages))
    await cb.answer()


@router.callback_query(F.data.startswith("adm:calcs:"))
async def cb_calcs(cb: CallbackQuery, session: AsyncSession):
    rows, page, pages, total = await _paged(session, Calculation, int(cb.data.split(":")[2]))
    lines = [f"🧾 <b>История расчётов</b> (всего: {total})", ""]
    for c in rows:
        when = c.created_at.strftime("%d.%m %H:%M") if c.created_at else ""
        lines.append(
            f"• {when} | {c.delivery_type or '-'} / {c.category or '-'} | "
            f"{fmt_num(c.weight or 0)} кг → <b>{fmt_num(c.total or 0)} {c.currency_code or ''}</b>"
        )
    await cb.message.edit_text("\n".join(lines),
                               reply_markup=paginate_kb("adm:calcs", page, pages))
    await cb.answer()


@router.callback_query(F.data.startswith("adm:logs:"))
async def cb_logs(cb: CallbackQuery, session: AsyncSession):
    rows, page, pages, total = await _paged(session, Log, int(cb.data.split(":")[2]))
    lines = [f"📜 <b>Журнал изменений</b> (всего: {total})", ""]
    for log in rows:
        when = log.created_at.strftime("%d.%m %H:%M") if log.created_at else ""
        entry = (f"• {when} | <code>{log.actor_tg_id or '-'}</code> | "
                 f"{log.action} {log.entity}#{log.entity_id or '-'}")
        if log.old_data:
            entry += f"\n  было: {log.old_data[:150]}"
        if log.new_data:
            entry += f"\n  стало: {log.new_data[:150]}"
        lines.append(entry)
    await cb.message.edit_text("\n".join(lines),
                               reply_markup=paginate_kb("adm:logs", page, pages))
    await cb.answer()
