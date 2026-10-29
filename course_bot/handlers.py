"""Всё, что видит ученик: рассказ о курсе, покупка, ссылка в канал."""

from __future__ import annotations

import contextlib
import logging
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from html import escape

from aiogram import Bot, F, Router
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    ChatMemberUpdated,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from . import content, db
from .config import Config

log = logging.getLogger("course_bot")
router = Router()

LINK_COOLDOWN = 600  # новая ссылка — не чаще раза в 10 минут
LINK_TTL = timedelta(hours=24)
# Ученик с доступом: оплатил, в том числе если сейчас просит возврат.
HAS_ACCESS = {"paid", "refund_details", "refund_requested"}
IN_CHANNEL = {ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}


# ── клавиатуры ──────────────────────────────────────────────────────────────

def _btn(text: str, data: str) -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text=text, callback_data=data)]


def main_menu(conn: sqlite3.Connection, user_id: int, is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        _btn("📖 О курсе", "m:about"),
        _btn("🗺 Программа: что изучаем", "m:program"),
        _btn("🎬 Как проходят уроки", "m:format"),
        _btn("📅 График уроков", "m:schedule"),
        _btn("⚠️ Честно о курсе", "m:honest"),
        _btn("❓ Частые вопросы", "m:faq"),
    ]
    demo = db.get_setting(conn, "demo")
    if demo:
        rows.append([InlineKeyboardButton(text="🎁 Бесплатный урок", url=demo)])
    student = db.get_student(conn, user_id)
    status = student["status"] if student else "new"
    if status in HAS_ACCESS:
        rows.append(_btn("🔑 Получить ссылку в канал", "link"))
        if status == "paid" and db.refund_seconds_left(student, content.REFUND_DAYS) > 0:
            rows.append(_btn("↩️ Вернуть деньги", "refund"))
    else:
        rows.append(_btn("💳 Купить курс", "m:buy"))
    contact = db.get_setting(conn, "contact")
    if contact:
        rows.append([InlineKeyboardButton(text="💬 Написать администратору", url=f"https://t.me/{contact}")])
    if is_admin:
        rows.append(_btn("⚙️ Админ-панель", "adm"))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_menu(*extra: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[*extra, _btn("⬅️ В меню", "m:home")])


def program_menu() -> InlineKeyboardMarkup:
    rows = [_btn(f"{i}. {title}", f"mod:{i - 1}") for i, (title, _, _) in enumerate(content.MODULES, 1)]
    return back_menu(*rows)


def buy_menu() -> InlineKeyboardMarkup:
    return back_menu(_btn("✅ Я оплатил — отправить чек", "paid"), _btn("⚠️ Честно о курсе", "m:honest"))


def link_menu() -> InlineKeyboardMarkup:
    return back_menu(_btn("🔑 Получить ссылку в канал", "link"))


# ── ссылка в канал ──────────────────────────────────────────────────────────

async def issue_link(bot: Bot, conn: sqlite3.Connection, user_id: int) -> str:
    """Одноразовая ссылка: впустит ровно одного человека и сгорит через сутки.

    В названии ссылки — id ученика: так в канале видно, чья это ссылка,
    а бот замечает, если по ней вошёл кто-то другой.
    """
    channel_id = db.get_setting(conn, "channel_id")
    link = await bot.create_chat_invite_link(
        chat_id=int(channel_id),
        name=f"id{user_id}",
        expire_date=datetime.now(timezone.utc) + LINK_TTL,
        member_limit=1,
    )
    db.mark_link_issued(conn, user_id)
    return link.invite_link


async def grant_access(bot: Bot, conn: sqlite3.Connection, user_id: int) -> str | None:
    """Отмечает оплату и отправляет ученику ссылку. Возвращает текст ошибки или None."""
    if not db.get_setting(conn, "channel_id"):
        return "Канал не подключён. Откройте ⚙️ Админ-панель → 📢 Подключить канал."
    if db.status_of(conn, user_id) not in HAS_ACCESS:
        db.set_status(conn, user_id, "paid")
    try:
        link = await issue_link(bot, conn, user_id)
    except TelegramAPIError as exc:
        log.warning("Не удалось создать ссылку для %s: %s", user_id, exc)
        return (f"Оплата отмечена, но ссылку создать не удалось: {exc.message}\n"
                "Проверьте, что бот — администратор канала с правом «Пригласительные ссылки». "
                "Потом выдайте доступ снова: ⚙️ Админ-панель → 🎓 Выдать доступ вручную.")
    try:
        await bot.send_message(user_id, content.access_link(link), reply_markup=back_menu())
    except TelegramAPIError as exc:
        return f"Ссылка создана, но ученику не отправилась ({exc.message}). Ссылка: {link}"
    return None


# ── меню ────────────────────────────────────────────────────────────────────

def _name(user) -> str:
    return user.full_name or user.username or "друг"


@router.message(CommandStart())
async def start(message: Message, conn: sqlite3.Connection, config: Config) -> None:
    user = message.from_user
    db.touch_student(conn, user.id, user.username, _name(user))
    text = content.welcome(_name(user))
    is_admin = user.id in config.admin_ids
    if is_admin:
        text += "\n\n<i>Вы администратор — настройки в кнопке «⚙️ Админ-панель».</i>"
    await message.answer(text, reply_markup=main_menu(conn, user.id, is_admin))


async def _show(callback: CallbackQuery, text: str, markup: InlineKeyboardMarkup) -> None:
    # «message is not modified» — если нажали ту же кнопку дважды, это не ошибка.
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
    await callback.answer()


@router.callback_query(F.data.startswith("m:"))
async def menu(callback: CallbackQuery, conn: sqlite3.Connection, config: Config) -> None:
    user = callback.from_user
    db.touch_student(conn, user.id, user.username, _name(user))
    page = callback.data[2:]
    ready = db.ready_count(conn)
    schedule = db.get_setting(conn, "schedule")

    if page == "about":
        await _show(callback, content.about(), back_menu(_btn("🗺 Программа курса", "m:program")))
    elif page == "program":
        await _show(callback, content.program_overview(ready), program_menu())
    elif page == "format":
        await _show(callback, content.lesson_format(), back_menu())
    elif page == "schedule":
        await _show(callback, content.schedule_text(schedule, ready), back_menu())
    elif page == "honest":
        await _show(callback, content.honest(schedule, ready, bool(db.get_setting(conn, "demo"))),
                    back_menu(_btn("💳 Купить курс", "m:buy")))
    elif page == "faq":
        await _show(callback, content.faq(), back_menu())
    elif page == "buy":
        if db.status_of(conn, user.id) in HAS_ACCESS:
            await _show(callback, content.ALREADY_PAID, link_menu())
            return
        pay = db.get_setting(conn, "pay")
        if not pay:
            await _show(callback, content.PAY_NOT_SET, back_menu())
            return
        await _show(callback, content.buy(db.get_setting(conn, "price"), pay), buy_menu())
    else:
        await _show(callback, content.welcome(_name(user)),
                    main_menu(conn, user.id, user.id in config.admin_ids))


@router.callback_query(F.data.startswith("mod:"))
async def module(callback: CallbackQuery, conn: sqlite3.Connection) -> None:
    index = int(callback.data[4:])
    if not 0 <= index < len(content.MODULES):
        await callback.answer()
        return
    await _show(callback, content.module_text(index, db.ready_count(conn)),
                back_menu(_btn("⬅️ Все модули", "m:program")))


# ── покупка ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "paid")
async def paid_pressed(callback: CallbackQuery, conn: sqlite3.Connection) -> None:
    user = callback.from_user
    db.touch_student(conn, user.id, user.username, _name(user))
    status = db.status_of(conn, user.id)
    await callback.answer()
    if status in HAS_ACCESS:
        await callback.message.answer(content.ALREADY_PAID, reply_markup=link_menu())
    elif status == "pending":
        await callback.message.answer(content.RECEIPT_ALREADY)
    else:
        db.set_status(conn, user.id, "waiting_receipt")
        await callback.message.answer(content.SEND_RECEIPT)


def approve_menu(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"ok:{user_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"no:{user_id}"),
    ]])


@router.message(F.chat.type == "private", F.photo | F.document)
async def receipt(message: Message, bot: Bot, conn: sqlite3.Connection, config: Config) -> None:
    user = message.from_user
    db.touch_student(conn, user.id, user.username, _name(user))
    status = db.status_of(conn, user.id)
    if status == "refund_details":
        await message.answer(content.REFUND_ASK_DETAILS)
        return
    if status in HAS_ACCESS:
        await message.answer(content.ALREADY_PAID, reply_markup=link_menu())
        return
    if status == "pending":
        await message.answer(content.RECEIPT_ALREADY)
        return
    if status != "waiting_receipt":
        await message.answer(content.PRESS_BUY_FIRST,
                             reply_markup=main_menu(conn, user.id, user.id in config.admin_ids))
        return

    username = f" @{user.username}" if user.username else ""
    info = (f"🧾 <b>Новый чек</b>\n"
            f"Ученик: <a href=\"tg://user?id={user.id}\">{escape(_name(user))}</a>{username}\n"
            f"ID: <code>{user.id}</code>\n\n"
            f"Проверьте, пришли ли деньги, и нажмите кнопку.")
    delivered = 0
    for admin_id in config.admin_ids:
        try:
            copied = await message.copy_to(admin_id)
            await bot.send_message(admin_id, info, reply_markup=approve_menu(user.id),
                                   reply_to_message_id=copied.message_id)
            delivered += 1
        except TelegramAPIError as exc:
            log.warning("Чек не дошёл до админа %s: %s", admin_id, exc)
    if not delivered:
        await message.answer("Не получилось передать чек администратору. Попробуйте позже.")
        return
    db.set_status(conn, user.id, "pending")
    await message.answer(content.RECEIPT_RECEIVED)


# ── повторная ссылка ────────────────────────────────────────────────────────

@router.callback_query(F.data == "link")
async def new_link(callback: CallbackQuery, bot: Bot, conn: sqlite3.Connection) -> None:
    user_id = callback.from_user.id
    student = db.get_student(conn, user_id)
    if not student or student["status"] not in HAS_ACCESS:
        await callback.answer(content.NOT_PAID, show_alert=True)
        return
    channel_id = db.get_setting(conn, "channel_id")
    if not channel_id:
        await callback.answer(content.NO_CHANNEL, show_alert=True)
        return
    with contextlib.suppress(TelegramAPIError):
        member = await bot.get_chat_member(int(channel_id), user_id)
        if member.status in IN_CHANNEL or getattr(member, "is_member", False):
            await callback.answer(content.ALREADY_IN_CHANNEL, show_alert=True)
            return
    if student["last_link_at"] and time.time() - student["last_link_at"] < LINK_COOLDOWN:
        await callback.answer(content.LINK_TOO_OFTEN, show_alert=True)
        return
    await callback.answer()
    try:
        link = await issue_link(bot, conn, user_id)
    except TelegramAPIError as exc:
        log.warning("Не удалось создать ссылку для %s: %s", user_id, exc)
        await callback.message.answer(content.NO_CHANNEL)
        return
    await callback.message.answer(content.access_link(link), reply_markup=back_menu())


# ── возврат денег (только первые REFUND_DAYS дней) ──────────────────────────

@router.callback_query(F.data == "refund")
async def refund(callback: CallbackQuery, conn: sqlite3.Connection) -> None:
    student = db.get_student(conn, callback.from_user.id)
    status = student["status"] if student else "new"
    if status in ("refund_details", "refund_requested"):
        await callback.answer(content.REFUND_IN_PROGRESS, show_alert=True)
        return
    if status != "paid":
        await callback.answer(content.NOT_PAID, show_alert=True)
        return
    left = db.refund_seconds_left(student, content.REFUND_DAYS)
    if left <= 0:
        await callback.answer(content.REFUND_EXPIRED, show_alert=True)
        return
    await _show(callback, content.refund_confirm(left), InlineKeyboardMarkup(inline_keyboard=[
        _btn("Да, вернуть деньги", "refund_yes"),
        _btn("Нет, продолжаю учиться", "m:home"),
    ]))


@router.callback_query(F.data == "refund_yes")
async def refund_yes(callback: CallbackQuery, conn: sqlite3.Connection) -> None:
    student = db.get_student(conn, callback.from_user.id)
    if not student or student["status"] != "paid":
        await callback.answer(content.REFUND_IN_PROGRESS if student and student["status"] in HAS_ACCESS
                              else content.NOT_PAID, show_alert=True)
        return
    # Срок проверяем ещё раз: экран подтверждения мог висеть открытым.
    if db.refund_seconds_left(student, content.REFUND_DAYS) <= 0:
        await callback.answer(content.REFUND_EXPIRED, show_alert=True)
        return
    db.set_status(conn, student["user_id"], "refund_details")
    await callback.answer()
    await callback.message.answer(content.REFUND_ASK_DETAILS)


def refund_menu(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Деньги вернул", callback_data=f"rfok:{user_id}"),
        InlineKeyboardButton(text="❌ Отказать", callback_data=f"rfno:{user_id}"),
    ]])


async def _waits_refund_details(message: Message, conn: sqlite3.Connection) -> bool:
    return message.from_user is not None and db.status_of(conn, message.from_user.id) == "refund_details"


@router.message(F.chat.type == "private", F.text, _waits_refund_details)
async def refund_details(message: Message, bot: Bot, conn: sqlite3.Connection, config: Config) -> None:
    user = message.from_user
    student = db.get_student(conn, user.id)
    paid = datetime.fromtimestamp(student["paid_at"]).strftime("%d.%m.%Y %H:%M")
    username = f" @{user.username}" if user.username else ""
    text = (f"↩️ <b>Запрос на возврат</b>\n"
            f"Ученик: <a href=\"tg://user?id={user.id}\">{escape(_name(user))}</a>{username}\n"
            f"ID: <code>{user.id}</code>\n"
            f"Оплатил: {paid}\n\n"
            f"<b>Куда вернуть:</b>\n{escape(message.text)}\n\n"
            f"Верните деньги и нажмите «✅ Деньги вернул» — бот уберёт ученика из канала.")
    delivered = 0
    for admin_id in config.admin_ids:
        try:
            await bot.send_message(admin_id, text, reply_markup=refund_menu(user.id))
            delivered += 1
        except TelegramAPIError as exc:
            log.warning("Запрос на возврат не дошёл до админа %s: %s", admin_id, exc)
    if not delivered:
        await message.answer("Не получилось передать запрос администратору. Попробуйте позже.")
        return
    db.set_status(conn, user.id, "refund_requested")
    await message.answer(content.REFUND_SENT)


async def remove_from_channel(bot: Bot, conn: sqlite3.Connection, user_id: int) -> None:
    """Убрать из канала. Бан сразу снимаем — иначе ученик не смог бы купить курс снова."""
    channel_id = db.get_setting(conn, "channel_id")
    if not channel_id:
        return
    with contextlib.suppress(TelegramAPIError):
        await bot.ban_chat_member(int(channel_id), user_id)
        await bot.unban_chat_member(int(channel_id), user_id, only_if_banned=True)


# ── кто вошёл в канал по чужой ссылке ───────────────────────────────────────

@router.chat_member()
async def joined(event: ChatMemberUpdated, bot: Bot, conn: sqlite3.Connection, config: Config) -> None:
    link = event.invite_link
    if not link or not (link.name or "").startswith("id"):
        return
    if str(event.chat.id) != db.get_setting(conn, "channel_id"):
        return
    if event.new_chat_member.status != ChatMemberStatus.MEMBER:
        return
    try:
        owner = int(link.name[2:])
    except ValueError:
        return
    joiner = event.new_chat_member.user
    if joiner.id == owner:
        return
    text = (f"⚠️ По ссылке ученика <code>{owner}</code> в канал вошёл другой человек: "
            f"<a href=\"tg://user?id={joiner.id}\">{escape(joiner.full_name)}</a> "
            f"(ID <code>{joiner.id}</code>).\nЕсли он не платил — удалите его из канала.")
    for admin_id in config.admin_ids:
        with contextlib.suppress(TelegramAPIError):
            await bot.send_message(admin_id, text)


@router.message(F.chat.type == "private")
async def anything_else(message: Message, conn: sqlite3.Connection, config: Config) -> None:
    user = message.from_user
    db.touch_student(conn, user.id, user.username, _name(user))
    await message.answer("Выберите раздел в меню 👇",
                         reply_markup=main_menu(conn, user.id, user.id in config.admin_ids))


@router.callback_query()
async def stale_button(callback: CallbackQuery) -> None:
    # Старые кнопки и чужие (например, ✅ админа у ученика) — просто гасим «часики».
    await callback.answer()
