"""Экспорт заявок и пользователей в Excel."""
import os

from aiogram import F, Router
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup

from bot.filters import IsAdmin
from bot.services import export_orders, export_users

router = Router()
router.callback_query.filter(IsAdmin())


@router.callback_query(F.data == "adm:export")
async def export_menu(cb: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Заявки (.xlsx)", callback_data="adm:exp:orders")],
        [InlineKeyboardButton(text="👥 Пользователи (.xlsx)", callback_data="adm:exp:users")],
        [InlineKeyboardButton(text="◀️ Админ-меню", callback_data="adm:menu")],
    ])
    await cb.message.edit_text("📤 Что экспортировать?", reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data.startswith("adm:exp:"))
async def export_run(cb: CallbackQuery, session):
    kind = cb.data.split(":")[2]
    await cb.answer("Готовлю файл...")
    path = await (export_orders(session) if kind == "orders" else export_users(session))
    try:
        await cb.message.answer_document(FSInputFile(path))
    finally:
        if os.path.exists(path):
            os.remove(path)
