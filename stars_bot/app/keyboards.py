"""Клавиатуры бота.

Цвет кнопок доступен с Bot API 9.4: поле style принимает primary (синий),
success (зелёный) и danger (красный). Цвет здесь не украшение, а подсказка:
зелёным помечено подтверждение и приход денег, красным — отмена и всё, что
что-то ломает, синим — главное действие экрана. Навигация остаётся без
цвета, иначе выделенным окажется всё сразу и цвет перестанет что-то значить.

Оттуда же icon_custom_emoji_id — премиум-эмодзи прямо на кнопке. Ставится
только если владелец задал его для этого значка и проверка прошла.
"""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import runtime
from app.config import settings
from app.emoji import custom_id, em, premium_on
from app.money import fmt, stars_cost

#: Значения поля style из Bot API 9.4
PRIMARY = "primary"    # синий — главное действие экрана
SUCCESS = "success"    # зелёный — подтвердить, оплатить, зачислить
DANGER = "danger"      # красный — отменить, отклонить, выключить


def btn(
    text: str,
    callback_data: str | None = None,
    *,
    url: str | None = None,
    style: str | None = None,
    icon: str | None = None,
) -> InlineKeyboardButton:
    """Кнопка с цветом и, если задан, премиум-значком.

    icon — ключ значка. Когда для него задан премиум-эмодзи, он ставится
    отдельным полем кнопки, а из текста обычный значок убирается: иначе
    рядом оказались бы два одинаковых.
    """
    fields: dict = {"text": text}
    if callback_data is not None:
        fields["callback_data"] = callback_data
    if url is not None:
        fields["url"] = url
    if style is not None:
        fields["style"] = style

    if icon:
        emoji_id = custom_id(icon)
        if emoji_id and premium_on():
            fields["icon_custom_emoji_id"] = emoji_id
            plain = em(icon)
            if plain and fields["text"].startswith(plain):
                fields["text"] = fields["text"][len(plain):].lstrip()
    return InlineKeyboardButton(**fields)


def labeled(icon: str, text: str) -> str:
    """Подпись со значком — значок берётся из настроек оформления."""
    return f"{em(icon)} {text}"


# ════════════════════════════════════════════════════════ главное меню


def main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if runtime.get_bool("stars_enabled"):
        kb.row(btn(labeled("stars", "Купить звёзды"), "m:stars",
                   style=PRIMARY, icon="stars"))
    if runtime.get_bool("premium_enabled"):
        kb.row(btn(labeled("premium", "Telegram Premium"), "m:premium",
                   style=PRIMARY, icon="premium"))

    deposit = btn(labeled("deposit", "Пополнить"), "m:deposit",
                  style=SUCCESS, icon="deposit")
    profile = btn(labeled("profile", "Профиль"), "m:profile", icon="profile")
    kb.row(deposit, profile) if runtime.get_bool("deposit_enabled") else kb.row(profile)

    kb.row(
        btn(labeled("support", "Поддержка"), "m:support", icon="support"),
        btn(labeled("calc", "Калькулятор"), "m:calc", icon="calc"),
    )
    kb.row(btn(labeled("info", "Информация"), "m:info", icon="info"))
    if settings.reviews_url:
        kb.row(btn(labeled("reviews", "Отзывы"), url=settings.reviews_url, icon="reviews"))
    kb.row(btn(labeled("top", "Топ клиентов"), "m:top", icon="top"))
    return kb.as_markup()


def back(target: str = "m:main", text: str = "") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(btn(text or labeled("back", "В меню"), target))
    return kb.as_markup()


def cancel(text: str = "") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(btn(text or labeled("cancel", "Отмена"), "m:main", style=DANGER))
    return kb.as_markup()


# ═════════════════════════════════════════════════════════════ покупка


def stars_entry() -> InlineKeyboardMarkup:
    """Готовые наборы по два в ряд плюс ввод своего количества."""
    kb = InlineKeyboardBuilder()
    packs = runtime.star_packs()
    for left in range(0, len(packs), 2):
        kb.row(*[
            btn(f"{em('stars')} {quantity} — {fmt(stars_cost(quantity))}",
                f"stars:pack:{quantity}", style=PRIMARY)
            for quantity in packs[left:left + 2]
        ])
    kb.row(btn(labeled("edit", "Другое количество"), "stars:buy"))
    kb.row(btn(labeled("back", "Назад"), "m:main"))
    return kb.as_markup()


def premium_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for plan in runtime.premium_plans():
        kb.row(btn(
            f"{em('premium')} {plan['months']} мес. — {fmt(plan['price'])}",
            f"premium:{plan['months']}", style=PRIMARY, icon="premium",
        ))
    kb.row(btn(labeled("back", "Назад"), "m:main"))
    return kb.as_markup()


def ask_recipient(has_username: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if has_username:
        kb.row(btn(labeled("stars", "Себе"), "order:self", style=SUCCESS, icon="stars"))
    kb.row(btn(labeled("cancel", "Отмена"), "m:main", style=DANGER))
    return kb.as_markup()


def confirm_recipient() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(btn(labeled("confirm", "Да, всё верно"), "order:recipient_ok", style=SUCCESS))
    kb.row(btn(labeled("edit", "Другой юзернейм"), "order:again"))
    kb.row(btn(labeled("cancel", "Отмена"), "m:main", style=DANGER))
    return kb.as_markup()


def confirm(has_promo: bool = False) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(btn(labeled("confirm", "Оплатить"), "order:go", style=SUCCESS))
    if has_promo:
        kb.row(btn("✖️ Убрать промокод", "order:promo_off"))
    else:
        kb.row(btn(labeled("promo", "Промокод"), "order:promo"))
    kb.row(btn(labeled("edit", "Другой получатель"), "order:again"))
    kb.row(btn(labeled("cancel", "Отмена"), "m:main", style=DANGER))
    return kb.as_markup()


def cancel_order(order_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(btn(labeled("cancel", "Отменить заказ"), f"order:cancel:{order_id}",
               style=DANGER))
    return kb.as_markup()


# ══════════════════════════════════════════════════════════ пополнение


def deposit_methods() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(btn(labeled("deposit", "Перевод на карту"), "dep:card",
               style=SUCCESS, icon="deposit"))
    kb.row(btn("🏦 Другой способ", "dep:soon"))
    kb.row(btn(labeled("back", "Назад"), "m:main"))
    return kb.as_markup()


# ════════════════════════════════════════════════════════════ профиль


def deposit_pay(link: str) -> InlineKeyboardMarkup:
    """Кнопка открывает приложение с готовыми счётом и суммой."""
    kb = InlineKeyboardBuilder()
    kb.row(btn("🏙 Оплатить в Душанбе Сити", url=link, style=SUCCESS))
    kb.row(btn(labeled("cancel", "Отмена"), "m:main", style=DANGER))
    return kb.as_markup()


def profile() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(btn(labeled("history", "История покупок"), "p:history", icon="history"))
    kb.row(btn(labeled("promo", "Промокод"), "p:promo", style=SUCCESS, icon="promo"))
    kb.row(btn(labeled("referral", "Рефералы"), "p:ref", icon="referral"))
    kb.row(btn(labeled("back", "В меню"), "m:main"))
    return kb.as_markup()


def support_menu(has_open: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if has_open:
        kb.row(btn(labeled("edit", "Дописать в обращение"), "t:reply", style=PRIMARY))
    else:
        kb.row(btn(labeled("support", "Написать в поддержку"), "t:new",
                   style=PRIMARY, icon="support"))
    kb.row(btn(labeled("back", "В меню"), "m:main"))
    return kb.as_markup()


# ══════════════════════════════════════════════════════════════ админ


def admin_deposit(deposit_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(btn(labeled("ok", "Зачислить"), f"a:dep_ok:{deposit_id}", style=SUCCESS))
    kb.row(btn(labeled("fail", "Отклонить"), f"a:dep_no:{deposit_id}", style=DANGER))
    return kb.as_markup()


def admin_retry(order_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(btn(labeled("refresh", "Повторить выдачу"), f"a:retry:{order_id}",
               style=PRIMARY))
    return kb.as_markup()
