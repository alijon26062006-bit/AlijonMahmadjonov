from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.keyboards import cancel_kb, main_menu
from bot.models import Track
from bot.states import TrackStates
from bot.texts import t

router = Router()


@router.message(F.text == t("btn_track"))
async def track_start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(TrackStates.number)
    await message.answer(t("track_ask"), reply_markup=cancel_kb())


@router.message(TrackStates.number)
async def track_number(message: Message, state: FSMContext, session: AsyncSession):
    number = (message.text or "").strip()
    track = await session.scalar(
        select(Track).options(selectinload(Track.history))
        .where(Track.track_number == number)
    )
    if not track:
        await message.answer(t("track_not_found"))
        return
    await state.clear()

    lines = [
        f"📦 <b>Груз {track.track_number}</b>",
        f"Текущий статус: <b>{track.status}</b>",
        f"Обновлено: {track.updated_at.strftime('%d.%m.%Y %H:%M') if track.updated_at else '-'}",
    ]
    if track.history:
        lines.append("\n📜 <b>История:</b>")
        for h in track.history:
            when = h.created_at.strftime("%d.%m.%Y %H:%M") if h.created_at else ""
            lines.append(f"• {when} — {h.status}" + (f" ({h.comment})" if h.comment else ""))
    await message.answer("\n".join(lines), reply_markup=main_menu())
