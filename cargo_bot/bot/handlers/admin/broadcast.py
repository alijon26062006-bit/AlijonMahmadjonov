"""Массовая рассылка всем пользователям бота."""
import asyncio

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.filters import IsAdmin
from bot.keyboards import back_to_admin, main_menu
from bot.models import Broadcast, User
from bot.services import log_action
from bot.states import AdminStates
from bot.texts import t

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.callback_query(F.data == "adm:broadcast")
async def broadcast_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.broadcast_text)
    await cb.message.answer("📣 Введите текст рассылки (HTML-разметка поддерживается):")
    await cb.answer()


@router.message(AdminStates.broadcast_text)
async def broadcast_text(message: Message, state: FSMContext):
    if message.text == t("btn_cancel"):
        await state.clear()
        await message.answer(t("cancelled"), reply_markup=main_menu())
        return
    await state.update_data(text=message.html_text)
    await state.set_state(AdminStates.broadcast_confirm)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отправить всем", callback_data="adm:bc_go"),
         InlineKeyboardButton(text="❌ Отмена", callback_data="adm:menu")],
    ])
    await message.answer(f"Проверьте текст:\n\n{message.html_text}", reply_markup=kb)


@router.callback_query(AdminStates.broadcast_confirm, F.data == "adm:bc_go")
async def broadcast_go(cb: CallbackQuery, state: FSMContext,
                       session: AsyncSession, bot: Bot):
    data = await state.get_data()
    await state.clear()
    text = data["text"]
    users = (await session.scalars(select(User).where(User.is_blocked.is_(False)))).all()
    await cb.message.edit_text(f"⏳ Рассылка запущена ({len(users)} получателей)...")
    await cb.answer()

    sent = failed = 0
    for user in users:
        try:
            await bot.send_message(user.tg_id, text)
            sent += 1
        except Exception:  # noqa: BLE001
            failed += 1
        await asyncio.sleep(0.05)  # лимиты Telegram

    bc = Broadcast(admin_tg_id=cb.from_user.id, text=text,
                   total=len(users), sent=sent, failed=failed)
    session.add(bc)
    await session.commit()
    await log_action(session, cb.from_user.id, "broadcast", "broadcasts", bc.id,
                     new={"total": str(len(users)), "sent": str(sent),
                          "failed": str(failed)})
    await cb.message.answer(
        f"✅ Рассылка завершена.\nОтправлено: {sent}\nОшибок: {failed}",
        reply_markup=back_to_admin(),
    )
