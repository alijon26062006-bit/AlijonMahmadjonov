"""Клавиатуры."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import catalog
from app.config import settings
from app.texts import money


def main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⭐ Купить звёзды", callback_data="menu:stars")
    kb.button(text="💎 Telegram Premium", callback_data="menu:premium")
    kb.button(text="🧾 Мои заказы", callback_data="menu:orders")
    kb.button(text="❓ Как это работает", callback_data="menu:help")
    if settings.support_username:
        kb.row(InlineKeyboardButton(text="💬 Поддержка", url=f"https://t.me/{settings.support_username}"))
    kb.adjust(1, 1, 2, 1)
    return kb.as_markup()


def stars_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for package in catalog.stars_packages():
        kb.button(
            text=f"⭐ {package.amount} — {money(package.price)}",
            callback_data=f"buy:stars:{package.amount}",
        )
    kb.button(text="⬅️ Назад", callback_data="menu:main")
    kb.adjust(1)
    return kb.as_markup()


def premium_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for package in catalog.premium_packages():
        kb.button(
            text=f"💎 {package.months} мес. — {money(package.price)}",
            callback_data=f"buy:premium:{package.months}",
        )
    kb.button(text="⬅️ Назад", callback_data="menu:main")
    kb.adjust(1)
    return kb.as_markup()


def confirm_order() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Всё верно, к оплате", callback_data="order:create")
    kb.button(text="✏️ Изменить получателя", callback_data="order:edit_recipient")
    kb.button(text="🚫 Отмена", callback_data="menu:main")
    kb.adjust(1)
    return kb.as_markup()


def cancel_order(order_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🚫 Отменить заказ", callback_data=f"order:cancel:{order_id}")
    return kb.as_markup()


def back_to_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ В меню", callback_data="menu:main")
    return kb.as_markup()


def admin_review(order_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Оплату вижу — выдать", callback_data=f"admin:approve:{order_id}")
    kb.button(text="❌ Отклонить", callback_data=f"admin:reject:{order_id}")
    kb.adjust(1)
    return kb.as_markup()


def admin_retry(order_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🔁 Повторить выдачу", callback_data=f"admin:retry:{order_id}")
    return kb.as_markup()
