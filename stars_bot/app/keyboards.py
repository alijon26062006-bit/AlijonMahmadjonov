"""Клавиатуры. Раскладка повторяет макет из ТЗ."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import runtime
from app.config import settings
from app.money import fmt


def main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if runtime.get_bool("stars_enabled"):
        kb.row(InlineKeyboardButton(text="⭐️ Купить звезды", callback_data="m:stars"))
    if runtime.get_bool("premium_enabled"):
        kb.row(InlineKeyboardButton(text="👑 Telegram Premium", callback_data="m:premium"))
    deposit_button = InlineKeyboardButton(text="💲 Пополнить баланс", callback_data="m:deposit")
    profile_button = InlineKeyboardButton(text="👤 Профиль", callback_data="m:profile")
    if runtime.get_bool("deposit_enabled"):
        kb.row(deposit_button, profile_button)
    else:
        kb.row(profile_button)
    kb.row(
        InlineKeyboardButton(text="📞 Поддержка", callback_data="m:support"),
        InlineKeyboardButton(text="🖩 Калькулятор", callback_data="m:calc"),
    )
    kb.row(InlineKeyboardButton(text="ℹ️ Информация", callback_data="m:info"))
    if settings.reviews_url:
        kb.row(InlineKeyboardButton(text="👍 Отзывы", url=settings.reviews_url))
    kb.row(InlineKeyboardButton(text="🏆 Топ клиентов", callback_data="m:top"))
    return kb.as_markup()


def back(target: str = "m:main", text: str = "‹ В меню") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=text, callback_data=target)
    return kb.as_markup()


def stars_entry() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="⭐️ Купить Telegram Stars", callback_data="stars:buy"))
    kb.row(InlineKeyboardButton(text="‹ Назад", callback_data="m:main"))
    return kb.as_markup()


def cancel(text: str = "❌ Отмена") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=text, callback_data="m:main")
    return kb.as_markup()


def premium_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for plan in runtime.premium_plans():
        kb.row(InlineKeyboardButton(
            text=f"{plan['months']} месяцев — {fmt(plan['price'])}",
            callback_data=f"premium:{plan['months']}",
        ))
    kb.row(InlineKeyboardButton(text="‹ Назад", callback_data="m:main"))
    return kb.as_markup()


def ask_recipient(has_username: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if has_username:
        kb.row(InlineKeyboardButton(text="⭐️ Себе", callback_data="order:self"))
    kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="m:main"))
    return kb.as_markup()


def confirm_recipient() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✅ Да, это верный аккаунт",
                                callback_data="order:recipient_ok"))
    kb.row(InlineKeyboardButton(text="✏️ Другой юзернейм", callback_data="order:again"))
    kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="m:main"))
    return kb.as_markup()


def confirm() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✅ Подтвердить и оплатить", callback_data="order:go"))
    kb.row(InlineKeyboardButton(text="✏️ Другой получатель", callback_data="order:again"))
    kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="m:main"))
    return kb.as_markup()


def deposit_methods() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="💳 Перевод на карту", callback_data="dep:card"))
    kb.row(InlineKeyboardButton(text="🏦 Другой способ", callback_data="dep:soon"))
    kb.row(InlineKeyboardButton(text="‹ Назад", callback_data="m:main"))
    return kb.as_markup()


def profile() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="📜 История покупок", callback_data="p:history"))
    kb.row(InlineKeyboardButton(text="🎟 Активировать промокод", callback_data="p:promo"))
    kb.row(InlineKeyboardButton(text="👥 Реферальная система", callback_data="p:ref"))
    kb.row(InlineKeyboardButton(text="‹ В меню", callback_data="m:main"))
    return kb.as_markup()


def support_menu(has_open: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if has_open:
        kb.row(InlineKeyboardButton(text="✍️ Дописать в тикет", callback_data="t:reply"))
    else:
        kb.row(InlineKeyboardButton(text="📝 Создать тикет", callback_data="t:new"))
    kb.row(InlineKeyboardButton(text="‹ В меню", callback_data="m:main"))
    return kb.as_markup()


def admin_deposit(deposit_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✅ Зачислить", callback_data=f"a:dep_ok:{deposit_id}"))
    kb.row(InlineKeyboardButton(text="❌ Отклонить", callback_data=f"a:dep_no:{deposit_id}"))
    return kb.as_markup()


def admin_retry(order_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🔁 Повторить выдачу", callback_data=f"a:retry:{order_id}")
    return kb.as_markup()
