"""Команды администратора: цена, реквизиты, канал, подтверждение оплат."""

from __future__ import annotations

import re
import sqlite3
from html import escape

from aiogram import Bot, F, Router
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message, MessageOriginChannel

from . import content, db
from .config import Config
from .handlers import _btn, back_menu, grant_access

router = Router()


def _is_admin(event: Message | CallbackQuery, config: Config) -> bool:
    return event.from_user is not None and event.from_user.id in config.admin_ids


# Не-админ сюда не попадёт: сообщение уйдёт дальше, в обработчики ученика.
router.message.filter(_is_admin)
router.callback_query.filter(_is_admin)


# (команда, ключ настройки, что это, пример)
SETTINGS = [
    ("setprice", "price", "Цена", "/setprice 300 сомони"),
    ("setpay", "pay", "Реквизиты", "/setpay Карта Алиф: 1234 5678 9012 3456\nПолучатель: Алиджон М."),
    ("setschedule", "schedule", "График", "/setschedule новый урок каждые 2 дня"),
    ("setready", "ready", "Готово уроков", "/setready 3"),
    ("setcontact", "contact", "Ваш @username для связи", "/setcontact alijon_admin"),
    ("setdemo", "demo", "Ссылка на бесплатный урок", "/setdemo https://..."),
]


def _validate(key: str, value: str) -> tuple[str | None, str]:
    """Возвращает (ошибка, очищенное значение)."""
    if key == "ready":
        if not value.isdigit() or int(value) > content.TOTAL_LESSONS:
            return f"Нужно число от 0 до {content.TOTAL_LESSONS}.", value
    if key == "contact":
        value = value.lstrip("@")
        if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", value):
            return "Это не похоже на @username в Telegram.", value
    if key == "demo" and not value.startswith("https://"):
        return "Ссылка должна начинаться с https://", value
    return None, value


@router.message(Command("admin"))
async def admin_help(message: Message, conn: sqlite3.Connection) -> None:
    lines = ["⚙️ <b>Панель администратора</b>\n", "<b>Сейчас в боте:</b>"]
    for _, key, title, _ in SETTINGS:
        value = db.get_setting(conn, key) or "—"
        lines.append(f"• {title}: {escape(value)}")
    channel = db.get_setting(conn, "channel_id")
    lines.append(f"• Канал: {'подключён ✅' if channel else 'не подключён ❌'}")
    lines.append("\n<b>Как поменять</b> (команда и новое значение):")
    for _, _, title, example in SETTINGS:
        lines.append(f"<code>{escape(example)}</code>")
    lines += [
        "\n<b>Подключить канал:</b> добавьте бота в канал администратором "
        "(с правом «Пригласительные ссылки»), затем перешлите сюда любой пост из канала.",
        "\n<b>Ученики:</b>",
        "/stats — сколько купили и кто ждёт проверки",
        "/give ID — выдать доступ вручную (например, оплатили наличными)",
        "\nКогда ученик присылает чек, он придёт сюда с кнопками ✅ / ❌. "
        "После ✅ бот сам отправит ученику одноразовую ссылку.",
    ]
    await message.answer("\n".join(lines), disable_web_page_preview=True)


@router.message(Command(*[cmd for cmd, *_ in SETTINGS]))
async def set_value(message: Message, command: CommandObject, conn: sqlite3.Connection) -> None:
    _, key, title, example = next(s for s in SETTINGS if s[0] == command.command)
    value = (command.args or "").strip()
    if not value:
        current = db.get_setting(conn, key) or "—"
        await message.answer(f"{title} сейчас: {escape(current)}\n\nЧтобы поменять:\n"
                             f"<code>{escape(example)}</code>")
        return
    error, value = _validate(key, value)
    if error:
        await message.answer(f"❌ {error}\nПример: <code>{escape(example)}</code>")
        return
    db.set_setting(conn, key, value)
    await message.answer(f"✅ {title} сохранено:\n{escape(value)}", disable_web_page_preview=True)


@router.message(F.forward_origin.as_("origin"), F.forward_origin.type == "channel")
async def set_channel(message: Message, origin: MessageOriginChannel, bot: Bot,
                      conn: sqlite3.Connection) -> None:
    chat = origin.chat
    try:
        me = await bot.get_chat_member(chat.id, bot.id)
    except TelegramAPIError:
        await message.answer("❌ Бот не видит этот канал. Сначала добавьте бота в канал администратором.")
        return
    if me.status != ChatMemberStatus.ADMINISTRATOR or not getattr(me, "can_invite_users", False):
        await message.answer("❌ Бот в канале, но не может приглашать. Сделайте его администратором "
                             "и включите право «Пригласительные ссылки».")
        return
    db.set_setting(conn, "channel_id", str(chat.id))
    await message.answer(f"✅ Канал «{escape(chat.title or '')}» подключён. "
                         "Теперь после оплаты бот будет выдавать ссылки в него.")


@router.message(Command("stats"))
async def stats(message: Message, conn: sqlite3.Connection) -> None:
    c = db.counts(conn)
    lines = [
        "📊 <b>Ученики</b>\n",
        f"Купили курс: <b>{c.get('paid', 0)}</b>",
        f"Чек на проверке: {c.get('pending', 0)}",
        f"Нажали «Я оплатил», но чек не прислали: {c.get('waiting_receipt', 0)}",
        f"Отклонено: {c.get('rejected', 0)}",
        f"Всего открывали бота: {sum(c.values())}",
    ]
    pending = db.students_with(conn, "pending")
    if pending:
        lines.append("\n<b>Ждут проверки:</b>")
        lines += [f"• {escape(s['full_name'] or '')} — <code>{s['user_id']}</code>" for s in pending]
    await message.answer("\n".join(lines))


@router.message(Command("give"))
async def give(message: Message, command: CommandObject, bot: Bot, conn: sqlite3.Connection) -> None:
    arg = (command.args or "").strip()
    if not arg.isdigit():
        await message.answer("Напишите ID ученика: <code>/give 123456789</code>\n"
                             "ID видно в карточке чека и в /stats.")
        return
    user_id = int(arg)
    if not db.get_student(conn, user_id):
        await message.answer("Такого ученика нет. Пусть он сначала откроет бота и нажмёт /start.")
        return
    error = await grant_access(bot, conn, user_id)
    await message.answer(f"❌ {error}" if error else "✅ Доступ выдан, ссылка отправлена ученику.")


@router.callback_query(F.data.regexp(r"^(ok|no):(\d+)$").as_("match"))
async def decide(callback: CallbackQuery, match, bot: Bot, conn: sqlite3.Connection) -> None:
    action, user_id = match.group(1), int(match.group(2))
    status = db.status_of(conn, user_id)
    if status == "paid":
        await callback.answer("Уже подтверждено раньше.", show_alert=True)
        return
    if status != "pending":
        await callback.answer("Этот чек уже обработан.", show_alert=True)
        return

    if action == "ok":
        error = await grant_access(bot, conn, user_id)
        if error and db.status_of(conn, user_id) != "paid":
            await callback.answer(error, show_alert=True)  # канал не подключён — чек ждёт
            return
        verdict = f"❌ {error}" if error else "✅ Подтверждено — ссылка отправлена ученику"
    else:
        db.set_status(conn, user_id, "rejected")
        try:
            await bot.send_message(user_id, content.REJECTED,
                                   reply_markup=back_menu(_btn("✅ Отправить чек ещё раз", "paid")))
        except TelegramAPIError:
            pass
        verdict = "❌ Отклонено — ученику сообщили"

    await callback.answer()
    await callback.message.edit_text(f"{callback.message.html_text}\n\n<b>{escape(verdict)}</b>")
