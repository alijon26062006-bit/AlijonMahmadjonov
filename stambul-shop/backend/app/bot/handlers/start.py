"""Бот магазина: коды подтверждения, привязка аккаунта, помощь.

Продавать бот не умеет и не должен: магазин живёт на сайте. Здесь только
то, чего сайт сделать не может, — подтвердить, что номер принадлежит
человеку, и написать ему, когда что-то произойдёт с заказом.
"""
from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, Message,
    ReplyKeyboardMarkup, ReplyKeyboardRemove,
)
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.config import get_settings
from app.db.models import User
from app.services import accounts, auth_code

router = Router()

# ключ заявки на вход держим на время диалога: между нажатием ссылки и
# отправкой контакта человек может отвлечься, но не на полдня
PENDING_TTL = 900


def _pending_key(tg_id: int) -> str:
    return f"authwait:{tg_id}"


def open_shop_kb(path: str = "", label: str = "") -> InlineKeyboardMarkup:
    """Обычная ссылка на сайт: никаких Mini App, магазин открывается в браузере."""
    url = get_settings().site_url.rstrip("/") + path
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=label or texts.OPEN_SHOP, url=url),
    ]])


def menu_kb(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=texts.MENU_ORDERS),
             KeyboardButton(text=texts.MENU_HELP)]]
    if is_admin:
        rows.append([KeyboardButton(text=texts.MENU_PANEL)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def share_phone_kb() -> ReplyKeyboardMarkup:
    """Штатная кнопка Telegram: номер подставляет сам мессенджер.

    Именно поэтому ей можно верить — руками в это поле ничего не впишешь.
    """
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=texts.SHARE_PHONE, request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True)


async def greet(message: Message, user: User) -> None:
    s = get_settings()
    await message.answer(
        texts.START.format(shop=s.shop_name, tagline=s.shop_tagline),
        reply_markup=menu_kb(user.is_admin))
    await message.answer(texts.START_HINT, reply_markup=open_shop_kb())


@router.message(CommandStart(deep_link=True))
async def start_deeplink(message: Message, command: CommandObject,
                         session: AsyncSession, redis: Redis,
                         user: User) -> None:
    arg = (command.args or "")[:64]
    if not arg.startswith("c_"):
        await greet(message, user)
        return

    entry = await auth_code.by_key(session, arg.removeprefix("c_"))
    if not auth_code.alive(entry):
        await message.answer(texts.LINK_EXPIRED)
        return

    if entry.purpose == "link":
        owner = await session.get(User, entry.user_id)
        if owner is None:
            await message.answer(texts.LINK_EXPIRED)
            return
        await accounts.link_telegram(session, owner, tg_id=user.tg_id,
                                     username=user.username,
                                     name=user.first_name)
        await auth_code.mark_used(session, entry)
        await message.answer(texts.LINKED, reply_markup=menu_kb(owner.is_admin))
        return

    await redis.set(_pending_key(user.tg_id), entry.key, ex=PENDING_TTL)
    await message.answer(texts.ASK_PHONE.format(phone=entry.phone),
                         reply_markup=share_phone_kb())


@router.message(F.contact)
async def got_contact(message: Message, session: AsyncSession, redis: Redis,
                      user: User) -> None:
    key = await redis.get(_pending_key(user.tg_id))
    if key is None:
        await message.answer(texts.NO_PENDING, reply_markup=ReplyKeyboardRemove())
        return
    key = key.decode() if isinstance(key, bytes) else key

    # чужой контакт из адресной книги подтверждением не считается
    if message.contact.user_id != user.tg_id:
        await message.answer(texts.FOREIGN_CONTACT)
        return

    entry = await auth_code.by_key(session, key)
    try:
        code = await auth_code.confirm(session, entry,
                                       contact_phone=message.contact.phone_number,
                                       tg_id=user.tg_id)
    except auth_code.AuthError as error:
        await message.answer(str(error), reply_markup=ReplyKeyboardRemove())
        return

    await redis.delete(_pending_key(user.tg_id))
    await message.answer(texts.CODE.format(code=code),
                         reply_markup=menu_kb(user.is_admin))


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
    await message.answer(texts.HELP, reply_markup=open_shop_kb())


@router.message(Command("shop"))
async def shop_cmd(message: Message) -> None:
    await message.answer(texts.START_HINT, reply_markup=open_shop_kb())
