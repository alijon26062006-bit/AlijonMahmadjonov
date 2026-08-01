from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import main_menu
from bot.repositories import SettingsRepo
from bot.texts import t

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession):
    await state.clear()
    welcome = await SettingsRepo(session).get(
        "welcome_text", "👋 Добро пожаловать!"
    )
    await message.answer(welcome, reply_markup=main_menu())


@router.message(Command("cancel"))
@router.message(F.text == t("btn_cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(t("cancelled"), reply_markup=main_menu())
