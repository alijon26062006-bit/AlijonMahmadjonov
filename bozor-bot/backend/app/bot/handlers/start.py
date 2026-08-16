"""Главное меню, /start (в т.ч. подтверждение входа на сайте), помощь."""
from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton,
    Message, ReplyKeyboardMarkup, WebAppInfo,
)
from redis.asyncio import Redis

from app.bot import texts
from app.config import get_settings
from app.db.models import User

router = Router()


def main_menu_kb() -> ReplyKeyboardMarkup:
    s = get_settings()
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=texts.MENU_POST)],
        [KeyboardButton(text=texts.MENU_CATALOG,
                        web_app=WebAppInfo(url=s.webapp_url))],
        [KeyboardButton(text=texts.MENU_MY), KeyboardButton(text=texts.MENU_HELP)],
    ], resize_keyboard=True)


def open_app_kb() -> InlineKeyboardMarkup:
    """Кнопка прямо под приветствием. Именно web_app: Telegram передаёт
    приложению подписанные данные, и человек оказывается внутри уже под своим
    аккаунтом — регистрироваться и входить повторно не нужно."""
    s = get_settings()
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🏠 Открыть приложение",
                             web_app=WebAppInfo(url=s.webapp_url)),
    ]])


async def greet(message: Message) -> None:
    await message.answer(texts.START, reply_markup=main_menu_kb())
    await message.answer(texts.OPEN_APP, reply_markup=open_app_kb())


@router.message(CommandStart(deep_link=True))
async def start_deeplink(message: Message, command: CommandObject,
                         redis: Redis, user: User) -> None:
    arg = command.args or ""
    if arg.startswith("login_"):
        code = arg.removeprefix("login_")[:64]
        exists = await redis.get(f"login:{code}")
        if not exists:
            await message.answer("Ссылка входа устарела. Обновите страницу сайта "
                                 "и попробуйте снова.")
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Подтвердить вход",
                                 callback_data=f"login:{code}"),
        ]])
        await message.answer(
            "<b>Вход на сайт Бозор</b>\n\n"
            "Кто-то (надеемся, вы) входит на сайт через этот Telegram-аккаунт.\n"
            "Если это вы — подтвердите:", reply_markup=kb)
        return
    await greet(message)


@router.callback_query(F.data.startswith("login:"))
async def confirm_login(cb: CallbackQuery, redis: Redis, user: User) -> None:
    code = cb.data.split(":", 1)[1]
    pending = await redis.get(f"login:{code}")
    if not pending:
        await cb.answer("Код устарел", show_alert=True)
        return
    await redis.set(f"login:{code}", str(user.id), ex=120)
    await cb.answer("Вход подтверждён!")
    await cb.message.edit_text("✅ Вход подтверждён — вернитесь на сайт.")


@router.message(CommandStart())
async def start(message: Message) -> None:
    await greet(message)


@router.message(Command("help"))
@router.message(F.text == texts.MENU_HELP)
async def help_cmd(message: Message) -> None:
    await message.answer(texts.HELP)
