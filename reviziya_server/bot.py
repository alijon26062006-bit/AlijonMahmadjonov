"""Телеграм-бот ревизии: открывает мини-апп, спрашивает админа о новых сотрудниках, шлёт отчёт."""

from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    Message,
    WebAppInfo,
)

from . import db

log = logging.getLogger("reviziya.bot")
router = Router()


def open_button(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Открыть сканер", web_app=WebAppInfo(url=url)),
    ]])


@router.message(CommandStart())
async def start(message: Message, public_url: str) -> None:
    await message.answer(
        "Ревизия магазина. Нажмите кнопку, включите камеру и подносите бирки в рамку: "
        "сканер сам читает цену и прибавляет её к вашей сумме.",
        reply_markup=open_button(public_url),
    )


@router.callback_query(F.data.startswith("rev:"))
async def decide(query: CallbackQuery, conn, notifier: "Notifier") -> None:
    """Админ нажал «Допустить» или «Отклонить» под заявкой нового сотрудника."""
    admin = db.get_user(conn, query.from_user.id)
    if not admin or admin["role"] != "admin" or admin["status"] != "active":
        await query.answer("Это может только админ", show_alert=True)
        return
    try:
        _, verdict, raw_id = query.data.split(":")
        target = db.get_user(conn, int(raw_id))
    except ValueError:
        target = None
    if not target:
        await query.answer("Сотрудник не найден", show_alert=True)
        return
    if target["status"] != "pending":
        await query.answer("Уже решено")
    else:
        allowed = verdict == "ok"
        db.set_user(conn, target["tg_id"], status="active" if allowed else "blocked")
        await notifier.access_decided(target, allowed)
        await query.answer("Допущен" if allowed else "Отклонён")
    current = db.get_user(conn, target["tg_id"])
    verdict_text = {"active": "допущен", "blocked": "отклонён"}.get(current["status"], current["status"])
    if query.message:
        await query.message.edit_text(f"{target['name']}: {verdict_text}.")


class Notifier:
    """Всё, что сервер отправляет людям в Telegram."""

    def __init__(self, bot: Bot, conn, public_url: str):
        self.bot, self.conn, self.public_url = bot, conn, public_url

    async def access_request(self, user: dict) -> None:
        who = user["name"] + (f" (@{user['username']})" if user.get("username") else "")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Допустить", callback_data=f"rev:ok:{user['tg_id']}"),
            InlineKeyboardButton(text="Отклонить", callback_data=f"rev:no:{user['tg_id']}"),
        ]])
        for admin_id in db.admin_ids(self.conn):
            try:
                await self.bot.send_message(admin_id, f"{who} просит доступ к ревизии.", reply_markup=keyboard)
            except Exception:
                log.warning("не удалось написать админу %s", admin_id)

    async def access_decided(self, user: dict, allowed: bool) -> None:
        text = "Вас допустили к ревизии. Откройте сканер." if allowed else "Админ отклонил вашу заявку."
        try:
            await self.bot.send_message(
                user["tg_id"], text, reply_markup=open_button(self.public_url) if allowed else None
            )
        except Exception:
            log.warning("не удалось написать сотруднику %s", user["tg_id"])

    async def send_report(self, admin_id: int, data: bytes, filename: str) -> None:
        await self.bot.send_document(admin_id, BufferedInputFile(data, filename), caption="Отчёт по ревизии")


async def configure(bot: Bot, public_url: str) -> None:
    """Кнопка меню бота открывает мини-апп."""
    await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="Сканер", web_app=WebAppInfo(url=public_url)))


def build_dispatcher(conn, notifier: Notifier, public_url: str) -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    dispatcher["conn"], dispatcher["notifier"], dispatcher["public_url"] = conn, notifier, public_url
    return dispatcher
