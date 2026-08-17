"""Приветствие, вход на сайт, помощь, «мой id»."""
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


def main_menu_kb(is_admin: bool = False) -> ReplyKeyboardMarkup:
    s = get_settings()
    rows = [
        [KeyboardButton(text=texts.MENU_SHOP,
                        web_app=WebAppInfo(url=s.webapp_url))],
        [KeyboardButton(text=texts.MENU_ORDERS),
         KeyboardButton(text=texts.MENU_HELP)],
    ]
    if is_admin:
        rows.append([KeyboardButton(text=texts.MENU_ADMIN),
                     KeyboardButton(text=texts.MENU_PANEL)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def open_shop_kb(path: str = "") -> InlineKeyboardMarkup | None:
    """Кнопка web_app: Telegram передаёт подписанные данные, и человек
    оказывается внутри уже под своим аккаунтом."""
    s = get_settings()
    url = f"{s.webapp_url.rstrip('/')}{path}"
    if not url.startswith("https://"):
        return None                      # Telegram примет только HTTPS
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=texts.OPEN_SHOP, web_app=WebAppInfo(url=url)),
    ]])


async def greet(message: Message, user: User | None = None) -> None:
    s = get_settings()
    await message.answer(
        texts.START.format(shop=s.shop_name, tagline=s.shop_tagline),
        reply_markup=main_menu_kb(bool(user and user.is_admin)))
    if (kb := open_shop_kb()):
        await message.answer("Каталог открывается одной кнопкой:", reply_markup=kb)


@router.message(CommandStart(deep_link=True))
async def start_deeplink(message: Message, command: CommandObject,
                         redis: Redis, user: User) -> None:
    arg = command.args or ""
    if arg.startswith("login_"):
        code = arg.removeprefix("login_")[:64]
        if not await redis.get(f"login:{code}"):
            await message.answer("Ссылка входа устарела. Обновите страницу сайта.")
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Подтвердить вход",
                                 callback_data=f"login:{code}")]])
        await message.answer(
            "<b>Вход в магазин</b>\n\nЕсли это вы входите на сайт — подтвердите:",
            reply_markup=kb)
        return
    await greet(message, user)


@router.callback_query(F.data.startswith("login:"))
async def confirm_login(cb: CallbackQuery, redis: Redis, user: User) -> None:
    code = cb.data.split(":", 1)[1]
    if not await redis.get(f"login:{code}"):
        await cb.answer("Код устарел", show_alert=True)
        return
    await redis.set(f"login:{code}", str(user.id), ex=120)
    await cb.answer("Вход подтверждён!")
    await cb.message.edit_text("✅ Вход подтверждён — вернитесь на сайт.")


@router.message(CommandStart())
async def start(message: Message, user: User) -> None:
    await greet(message, user)


@router.message(Command("id"))
@router.message(Command("whoami"))
async def whoami(message: Message, user: User) -> None:
    await message.answer(texts.WHOAMI.format(
        tg_id=user.tg_id, name=user.first_name or "—",
        username=f"@{user.username}" if user.username else "не задан",
        role="владелец магазина" if user.is_admin else "покупатель"))


@router.message(Command("help"))
@router.message(F.text == texts.MENU_HELP)
async def help_cmd(message: Message) -> None:
    await message.answer(texts.HELP)


@router.message(F.text == texts.MENU_ADMIN)
async def open_admin(message: Message, user: User) -> None:
    if not user.is_admin:
        await message.answer(texts.NOT_ADMIN.format(tg_id=user.tg_id))
        return
    kb = open_shop_kb("/admin")
    if kb is None:
        await message.answer("Панель открывается по HTTPS-адресу — задайте WEBAPP_URL.")
        return
    await message.answer("Управление товарами и заказами:", reply_markup=kb)
