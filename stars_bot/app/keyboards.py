"""Клавиатуры. Раскладка повторяет макет из ТЗ."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import runtime
from app.emoji import em
from app.config import settings
from app.money import fmt


def main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if runtime.get_bool("stars_enabled"):
        kb.row(InlineKeyboardButton(text=f"{em('stars')} Купить звёзды", callback_data="m:stars"))
    if runtime.get_bool("premium_enabled"):
        kb.row(InlineKeyboardButton(text=f"{em('premium')} Telegram Premium", callback_data="m:premium"))
    deposit_button = InlineKeyboardButton(text=f"{em('deposit')} Пополнить баланс", callback_data="m:deposit")
    profile_button = InlineKeyboardButton(text=f"{em('profile')} Профиль", callback_data="m:profile")
    if runtime.get_bool("deposit_enabled"):
        kb.row(deposit_button, profile_button)
    else:
        kb.row(profile_button)
    kb.row(
        InlineKeyboardButton(text=f"{em('support')} Поддержка", callback_data="m:support"),
        InlineKeyboardButton(text=f"{em('calc')} Калькулятор", callback_data="m:calc"),
    )
    kb.row(InlineKeyboardButton(text=f"{em('info')} Информация", callback_data="m:info"))
    if settings.reviews_url:
        kb.row(InlineKeyboardButton(text=f"{em('reviews')} Отзывы", url=settings.reviews_url))
    kb.row(InlineKeyboardButton(text=f"{em('top')} Топ клиентов", callback_data="m:top"))
    return kb.as_markup()


def back(target: str = "m:main", text: str = "") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=text or f"{em('back')} В меню", callback_data=target)
    return kb.as_markup()


def stars_entry() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text=f"{em('stars')} Купить звёзды", callback_data="stars:buy"))
    kb.row(InlineKeyboardButton(text=f"{em('back')} Назад", callback_data="m:main"))
    return kb.as_markup()


def cancel(text: str = "") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=text or f"{em('cancel')} Отмена", callback_data="m:main")
    return kb.as_markup()


def premium_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for plan in runtime.premium_plans():
        kb.row(InlineKeyboardButton(
            text=f"{em('premium')} {plan['months']} мес. — {fmt(plan['price'])}",
            callback_data=f"premium:{plan['months']}",
        ))
    kb.row(InlineKeyboardButton(text=f"{em('back')} Назад", callback_data="m:main"))
    return kb.as_markup()


def ask_recipient(has_username: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if has_username:
        kb.row(InlineKeyboardButton(text=f"{em('stars')} Себе", callback_data="order:self"))
    kb.row(InlineKeyboardButton(text=f"{em('cancel')} Отмена", callback_data="m:main"))
    return kb.as_markup()


def confirm_recipient() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text=f"{em('confirm')} Да, всё верно",
                                callback_data="order:recipient_ok"))
    kb.row(InlineKeyboardButton(text=f"{em('edit')} Другой юзернейм", callback_data="order:again"))
    kb.row(InlineKeyboardButton(text=f"{em('cancel')} Отмена", callback_data="m:main"))
    return kb.as_markup()


def confirm() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text=f"{em('confirm')} Оплатить", callback_data="order:go"))
    kb.row(InlineKeyboardButton(text=f"{em('edit')} Другой получатель", callback_data="order:again"))
    kb.row(InlineKeyboardButton(text=f"{em('cancel')} Отмена", callback_data="m:main"))
    return kb.as_markup()


def deposit_methods() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text=f"{em('deposit')} Перевод на карту", callback_data="dep:card"))
    kb.row(InlineKeyboardButton(text="🏦 Другой способ", callback_data="dep:soon"))
    kb.row(InlineKeyboardButton(text=f"{em('back')} Назад", callback_data="m:main"))
    return kb.as_markup()


def profile() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text=f"{em('history')} История покупок", callback_data="p:history"))
    kb.row(InlineKeyboardButton(text=f"{em('promo')} Промокод", callback_data="p:promo"))
    kb.row(InlineKeyboardButton(text=f"{em('referral')} Рефералы", callback_data="p:ref"))
    kb.row(InlineKeyboardButton(text=f"{em('back')} В меню", callback_data="m:main"))
    return kb.as_markup()


def support_menu(has_open: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if has_open:
        kb.row(InlineKeyboardButton(text=f"{em('edit')} Дописать в обращение", callback_data="t:reply"))
    else:
        kb.row(InlineKeyboardButton(text=f"{em('support')} Написать в поддержку", callback_data="t:new"))
    kb.row(InlineKeyboardButton(text=f"{em('back')} В меню", callback_data="m:main"))
    return kb.as_markup()


def admin_deposit(deposit_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text=f"{em('ok')} Зачислить", callback_data=f"a:dep_ok:{deposit_id}"))
    kb.row(InlineKeyboardButton(text=f"{em('fail')} Отклонить", callback_data=f"a:dep_no:{deposit_id}"))
    return kb.as_markup()


def admin_retry(order_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=f"{em('refresh')} Повторить выдачу", callback_data=f"a:retry:{order_id}")
    return kb.as_markup()
