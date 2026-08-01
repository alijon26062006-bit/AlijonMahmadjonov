"""Управление треками: создание трек-номеров, смена статусов, история."""
import math
import secrets

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.filters import IsAdmin
from bot.keyboards import main_menu, paginate_kb
from bot.models import Track, TrackHistory, User
from bot.repositories import Repository, SettingsRepo
from bot.services import log_action, notify_user
from bot.states import AdminStates
from bot.texts import t

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

B = InlineKeyboardButton
PER_PAGE = 8


@router.callback_query(F.data.startswith("adm:tracks:"))
async def tracks_list(cb: CallbackQuery, session: AsyncSession):
    page = int(cb.data.split(":")[2])
    total = await session.scalar(select(func.count(Track.id))) or 0
    pages = max(1, math.ceil(total / PER_PAGE))
    page = min(max(1, page), pages)
    rows = (await session.scalars(
        select(Track).order_by(Track.id.desc())
        .offset((page - 1) * PER_PAGE).limit(PER_PAGE)
    )).all()
    buttons = [[B(text=f"{tr.track_number} | {tr.status}",
                  callback_data=f"adm:track:{tr.id}")] for tr in rows]
    buttons.append([B(text="➕ Создать трек", callback_data="adm:track_new")])
    await cb.message.edit_text(
        f"🔎 <b>Треки</b> (всего: {total})",
        reply_markup=paginate_kb("adm:tracks", page, pages, extra_rows=buttons),
    )
    await cb.answer()


async def _track_view(session: AsyncSession, track_id: int):
    track = await session.scalar(
        select(Track).options(selectinload(Track.history)).where(Track.id == track_id)
    )
    if not track:
        return None, None
    statuses = await SettingsRepo(session).get_json("track_statuses", []) or []
    user = await session.get(User, track.user_id) if track.user_id else None
    lines = [
        f"📦 <b>Трек {track.track_number}</b>",
        f"Статус: <b>{track.status}</b>",
        f"Клиент: {f'@{user.username or user.tg_id}' if user else '—'}",
    ]
    if track.history:
        lines.append("\n📜 История:")
        for h in track.history:
            when = h.created_at.strftime("%d.%m %H:%M") if h.created_at else ""
            lines.append(f"• {when} — {h.status}")
    lines.append("\nСменить статус:")
    rows = [[B(text=("✅ " if s == track.status else "") + s,
               callback_data=f"adm:tstatus:{track.id}:{i}")]
            for i, s in enumerate(statuses)]
    rows.append([B(text="◀️ К трекам", callback_data="adm:tracks:1")])
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data.startswith("adm:track:"))
async def track_view(cb: CallbackQuery, session: AsyncSession):
    text, kb = await _track_view(session, int(cb.data.split(":")[2]))
    if not text:
        await cb.answer("Трек не найден", show_alert=True)
        return
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data.startswith("adm:tstatus:"))
async def track_status(cb: CallbackQuery, session: AsyncSession, bot: Bot):
    _, _, track_id, idx = cb.data.split(":")
    track = await Repository(session, Track).get(int(track_id))
    statuses = await SettingsRepo(session).get_json("track_statuses", []) or []
    if not track or int(idx) >= len(statuses):
        await cb.answer("Ошибка", show_alert=True)
        return
    new_status = statuses[int(idx)]
    old_status = track.status
    if new_status == old_status:
        await cb.answer("Этот статус уже установлен")
        return
    await Repository(session, Track).update(track, status=new_status)
    session.add(TrackHistory(track_id=track.id, status=new_status))
    await session.commit()
    await log_action(session, cb.from_user.id, "status", "tracks", track.id,
                     old={"status": old_status}, new={"status": new_status})
    if track.user_id:
        user = await session.get(User, track.user_id)
        if user:
            await notify_user(bot, user.tg_id,
                              f"📦 Статус вашего груза <b>{track.track_number}</b> "
                              f"изменён: <b>{new_status}</b>")
    text, kb = await _track_view(session, track.id)
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer("Статус обновлён")


# ---- создание трека ----

@router.callback_query(F.data == "adm:track_new")
async def track_new(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.track_number)
    await cb.message.answer(
        "Введите трек-номер (или отправьте «auto» для автогенерации):"
    )
    await cb.answer()


@router.message(AdminStates.track_number)
async def track_new_number(message: Message, state: FSMContext, session: AsyncSession):
    if message.text == t("btn_cancel"):
        await state.clear()
        await message.answer(t("cancelled"), reply_markup=main_menu())
        return
    number = (message.text or "").strip()
    if number.lower() == "auto":
        number = f"TRK-{secrets.token_hex(4).upper()}"
    exists = await session.scalar(select(Track).where(Track.track_number == number))
    if exists:
        await message.answer("Такой трек уже существует, введите другой номер.")
        return
    await state.update_data(track_number=number)
    await state.set_state(AdminStates.track_user)
    await message.answer(
        "Telegram ID клиента для уведомлений (или «-», если не привязывать):"
    )


@router.message(AdminStates.track_user)
async def track_new_user(message: Message, state: FSMContext, session: AsyncSession):
    raw = (message.text or "").strip()
    user_id = None
    if raw not in {"-", "—"}:
        try:
            tg_id = int(raw)
        except ValueError:
            await message.answer("Введите числовой Telegram ID или «-».")
            return
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            await message.answer("Пользователь с таким ID не найден в боте. "
                                 "Введите другой ID или «-».")
            return
        user_id = user.id
    data = await state.get_data()
    await state.clear()

    statuses = await SettingsRepo(session).get_json("track_statuses", []) or []
    first_status = statuses[0] if statuses else "Получен на складе"
    track = await Repository(session, Track).add(
        track_number=data["track_number"], user_id=user_id, status=first_status,
    )
    session.add(TrackHistory(track_id=track.id, status=first_status))
    await session.commit()
    await log_action(session, message.from_user.id, "create", "tracks", track.id,
                     new={"track_number": track.track_number, "status": first_status})
    text, kb = await _track_view(session, track.id)
    await message.answer(f"✅ Трек создан.\n\n{text}", reply_markup=kb)
