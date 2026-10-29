"""Админ-панель на кнопках: цена, реквизиты, канал, подтверждение оплат."""

from __future__ import annotations

import contextlib
import re
import sqlite3
from html import escape

from aiogram import Bot, F, Router
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, MessageOriginChannel

from . import content, db
from .config import Config
from .handlers import _btn, back_menu, fmt_date, grant_access

router = Router()


def _is_admin(event: Message | CallbackQuery, config: Config) -> bool:
    return event.from_user is not None and event.from_user.id in config.admin_ids


# Не-админ сюда не попадёт: сообщение уйдёт дальше, в обработчики ученика.
router.message.filter(_is_admin)
router.callback_query.filter(_is_admin)

# (ключ, кнопка, что прислать, пример, можно ли очистить)
SETTINGS = [
    ("price", "💰 Цена за месяц", "цену за месяц", "300 сомони", False),
    ("pay", "💳 Реквизиты", "реквизиты для оплаты (можно в несколько строк)",
     "Карта Алиф: 1234 5678 9012 3456\nПолучатель: Алиджон М.", False),
    ("schedule", "📅 График", "как часто выходят уроки", "новый урок каждые 2 дня", False),
    ("ready", "✅ Сколько уроков готово", "число готовых уроков", "3", False),
    ("contact", "💬 Мой username", "ваш username в Telegram — для кнопки «Написать администратору»",
     "alijon_admin", True),
    ("demo", "🎁 Бесплатный урок", "ссылку на бесплатный урок", "https://...", True),
]
TITLES = {key: title for key, title, *_ in SETTINGS}

# Что админ сейчас вводит: id админа → ключ настройки или "give".
WAITING: dict[int, str] = {}


def panel_text(conn: sqlite3.Connection) -> str:
    lines = ["⚙️ <b>Админ-панель</b>\n"]
    for key, title, *_ in SETTINGS:
        value = db.get_setting(conn, key) or "—"
        lines.append(f"{title}: {escape(value)}")
    channel = db.get_setting(conn, "channel_id")
    lines.append(f"📢 Канал: {'подключён ✅' if channel else 'не подключён ❌'}")
    c = db.counts(conn)
    active = sum(c.get(st, 0) for st in db.ACTIVE)
    checking = c.get("pending", 0) + c.get("renew_pending", 0)
    lines.append(f"\n🎓 Активных подписок: <b>{active}</b>, чеков на проверке: {checking}")
    lines.append("\nЧтобы поменять — нажмите кнопку 👇")
    return "\n".join(lines)


def panel_menu() -> InlineKeyboardMarkup:
    rows = [_btn(title, f"set:{key}") for key, title, *_ in SETTINGS]
    rows += [
        _btn("📢 Подключить канал", "adm:channel"),
        _btn("📊 Ученики", "adm:stats"),
        _btn("🎓 Выдать доступ вручную", "adm:give"),
    ]
    return back_menu(*rows)


def to_panel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[_btn("⬅️ В админ-панель", "adm")])


def cancel_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[_btn("❌ Отмена", "adm")])


async def _show(callback: CallbackQuery, text: str, markup: InlineKeyboardMarkup) -> None:
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
    await callback.answer()


@router.callback_query(F.data == "adm")
async def panel(callback: CallbackQuery, conn: sqlite3.Connection) -> None:
    WAITING.pop(callback.from_user.id, None)
    await _show(callback, panel_text(conn), panel_menu())


@router.callback_query(F.data.startswith("set:"))
async def ask_value(callback: CallbackQuery, conn: sqlite3.Connection) -> None:
    key = callback.data[4:]
    found = next((s for s in SETTINGS if s[0] == key), None)
    if not found:
        await callback.answer()
        return
    _, title, what, example, clearable = found
    WAITING[callback.from_user.id] = key
    current = db.get_setting(conn, key) or "—"
    text = (f"<b>{title}</b>\n\nСейчас: {escape(current)}\n\n"
            f"Отправьте следующим сообщением {what}.\n"
            f"Например:\n<code>{escape(example)}</code>")
    if clearable:
        text += "\n\nЧтобы убрать — отправьте знак <code>-</code>"
    await _show(callback, text, cancel_menu())


@router.callback_query(F.data == "adm:channel")
async def channel_help(callback: CallbackQuery) -> None:
    await _show(callback, (
        "📢 <b>Как подключить канал</b>\n\n"
        "1. Создайте <b>частный</b> канал. В настройках включите «Запретить копирование».\n"
        "2. Канал → Администраторы → Добавить администратора → найдите этого бота. "
        "Оставьте право «Пригласительные ссылки».\n"
        "3. Перешлите сюда <b>любой пост</b> из канала.\n\n"
        "Бот ответит «Канал подключён ✅»."
    ), to_panel())


@router.callback_query(F.data == "adm:stats")
async def stats(callback: CallbackQuery, conn: sqlite3.Connection, config: Config) -> None:
    c = db.counts(conn)
    lines = [
        "📊 <b>Ученики</b>\n",
        f"Активная подписка: <b>{sum(c.get(st, 0) for st in db.ACTIVE)}</b>",
        f"Чек на проверке: {c.get('pending', 0) + c.get('renew_pending', 0)}",
        f"Нажали «Я оплатил», но чек не прислали: {c.get('waiting_receipt', 0) + c.get('renew_waiting', 0)}",
        f"Подписка закончилась: {c.get('expired', 0)}",
        f"Всего открывали бота: {sum(c.values())}",
    ]
    pending = db.students_with(conn, "pending", "renew_pending")
    if pending:
        lines.append("\n<b>Ждут проверки чека:</b>")
        lines += [f"• {escape(s['full_name'] or '')} — <code>{s['user_id']}</code>" for s in pending]
    active = sorted(db.students_with(conn, *db.ACTIVE, limit=50), key=lambda s: s["paid_until"] or 0)
    if active:
        lines.append("\n<b>Подписки (сначала те, у кого скоро конец):</b>")
        lines += [f"• {escape(s['full_name'] or '')} — до {fmt_date(s['paid_until'], config)}"
                  for s in active[:30]]
    await _show(callback, "\n".join(lines), to_panel())


@router.callback_query(F.data == "adm:give")
async def ask_give(callback: CallbackQuery) -> None:
    WAITING[callback.from_user.id] = "give"
    await _show(callback, (
        "🎓 <b>Выдать доступ вручную</b>\n\n"
        "Например, если ученик оплатил наличными. Даёт ещё месяц доступа: "
        "новичку бот пришлёт ссылку, а тому, кто уже в канале, — продлит срок.\n\n"
        "Отправьте <b>ID ученика</b> — он есть в карточке чека и в «📊 Ученики». "
        "Ученик должен хотя бы раз открыть бота."
    ), cancel_menu())


# ── подключение канала: админ пересылает пост из канала ─────────────────────

@router.message(F.forward_origin.as_("origin"), F.forward_origin.type == "channel")
async def set_channel(message: Message, origin: MessageOriginChannel, bot: Bot,
                      conn: sqlite3.Connection) -> None:
    chat = origin.chat
    try:
        me = await bot.get_chat_member(chat.id, bot.id)
    except TelegramAPIError:
        await message.answer("❌ Бот не видит этот канал. Сначала добавьте бота в канал администратором.",
                             reply_markup=to_panel())
        return
    if me.status != ChatMemberStatus.ADMINISTRATOR or not getattr(me, "can_invite_users", False):
        await message.answer("❌ Бот в канале, но не может приглашать. Сделайте его администратором "
                             "и включите право «Пригласительные ссылки».", reply_markup=to_panel())
        return
    db.set_setting(conn, "channel_id", str(chat.id))
    await message.answer(f"✅ Канал «{escape(chat.title or '')}» подключён. "
                         "Теперь после оплаты бот будет выдавать ссылки в него.", reply_markup=to_panel())


# ── ввод значения после нажатия кнопки ──────────────────────────────────────

def _validate(key: str, value: str) -> tuple[str | None, str]:
    """Возвращает (ошибка, очищенное значение)."""
    if key == "ready":
        if not value.isdigit() or int(value) > content.TOTAL_LESSONS:
            return f"Нужно число от 0 до {content.TOTAL_LESSONS}.", value
    if key == "contact":
        value = value.lstrip("@")
        if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", value):
            return "Это не похоже на username в Telegram.", value
    if key == "demo" and not value.startswith("https://"):
        return "Ссылка должна начинаться с https://", value
    return None, value


def _is_waiting(message: Message) -> bool:
    # /start во время ввода — это не значение, а возврат в меню.
    if (message.text or "").startswith("/"):
        return False
    return message.from_user is not None and message.from_user.id in WAITING


@router.message(_is_waiting)
async def receive_value(message: Message, bot: Bot, conn: sqlite3.Connection, config: Config) -> None:
    admin_id = message.from_user.id
    key = WAITING[admin_id]
    value = (message.text or "").strip()
    if not value:
        await message.answer("Отправьте текстом, пожалуйста.", reply_markup=cancel_menu())
        return

    if key == "give":
        if not value.isdigit() or not db.get_student(conn, int(value)):
            await message.answer("Не нашёл такого ученика. Проверьте ID — ученик должен хотя бы раз "
                                 "открыть бота.", reply_markup=cancel_menu())
            return
        WAITING.pop(admin_id)
        error = await grant_access(bot, conn, config, int(value))
        await message.answer(f"❌ {error}" if error else "✅ Доступ на месяц выдан, ученику сообщили.",
                             reply_markup=to_panel())
        return

    clearable = next(s[4] for s in SETTINGS if s[0] == key)
    if clearable and value == "-":
        value, error = "", None
    else:
        error, value = _validate(key, value)
    if error:
        await message.answer(f"❌ {error} Попробуйте ещё раз.", reply_markup=cancel_menu())
        return
    WAITING.pop(admin_id)
    db.set_setting(conn, key, value)
    shown = escape(value) if value else "убрано"
    await message.answer(f"✅ {TITLES[key]}: {shown}", reply_markup=to_panel(), disable_web_page_preview=True)


# ── решения по чекам и возвратам ────────────────────────────────────────────

async def _mark(callback: CallbackQuery, verdict: str) -> None:
    await callback.answer()
    with contextlib.suppress(TelegramBadRequest):
        await callback.message.edit_text(f"{callback.message.html_text}\n\n<b>{escape(verdict)}</b>")


@router.callback_query(F.data.regexp(r"^(ok|no):(\d+)$").as_("match"))
async def decide(callback: CallbackQuery, match, bot: Bot, conn: sqlite3.Connection, config: Config) -> None:
    action, user_id = match.group(1), int(match.group(2))
    status = db.status_of(conn, user_id)
    if status not in ("pending", "renew_pending"):
        await callback.answer("Этот чек уже обработан.", show_alert=True)
        return

    if action == "ok":
        error = await grant_access(bot, conn, config, user_id)
        if error and db.status_of(conn, user_id) == status:
            await callback.answer(error, show_alert=True)  # канал не подключён — чек ждёт
            return
        until = fmt_date(db.get_student(conn, user_id)["paid_until"], config)
        await _mark(callback, f"❌ {error}" if error else f"✅ Подтверждено — доступ до {until}")
        return

    # Продление отклонено — текущий оплаченный срок остаётся.
    db.set_status(conn, user_id, "paid" if status == "renew_pending" else "rejected")
    with contextlib.suppress(TelegramAPIError):
        await bot.send_message(user_id, content.REJECTED,
                               reply_markup=back_menu(_btn("✅ Отправить чек ещё раз", "paid")))
    await _mark(callback, "❌ Отклонено — ученику сообщили")
