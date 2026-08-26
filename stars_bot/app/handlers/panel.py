"""Админ-панель: одна точка входа, всё остальное — кнопками.

Открывается командой /panel (или /admin). Разделы:
  • Рассылка — любой тип сообщения + кнопки-ссылки
  • Цены — себестоимость, наценка, цена продажи, тарифы Premium
  • Реквизиты — карта, владелец, банк, город, примечание
  • Заявки, тикеты, пользователи, промокоды, статистика
  • Рекламные ссылки — Deep Links и статистика источников
"""
from __future__ import annotations

import asyncio
import logging

import aiosqlite
from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery, CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from contextlib import suppress

from app import db, emoji, links, reports, runtime, texts
from app.handlers.menu import top_basis
from app.config import settings
from app.emoji import substitute
from app.keyboards import DANGER, PRIMARY, SUCCESS, btn
from app.money import fmt, fmt4, parse, parse4
from app.services import dcpay, pricing
from app.services import delivery
from app.states import Panel, PromoNew

log = logging.getLogger(__name__)
router = Router(name="panel")

router.message.filter(F.from_user.func(lambda u: settings.is_admin(u.id)))
router.callback_query.filter(F.from_user.func(lambda u: settings.is_admin(u.id)))

# Аудитории рассылки: ключ -> (подпись, SQL-условие)
AUDIENCES = {
    "all": ("Всем", "is_banned = 0"),
    "buyers": ("Только покупателям", "is_banned = 0 AND id IN (SELECT user_id FROM orders)"),
    "funded": ("У кого есть баланс", "is_banned = 0 AND balance > 0"),
    "silent": ("Без покупок", "is_banned = 0 AND id NOT IN (SELECT user_id FROM orders)"),
}


# ============================================================ главный экран


def home_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(btn("📣 Рассылка", "pn:cast", style=PRIMARY))
    kb.row(
        InlineKeyboardButton(text="💵 Цены и наценка", callback_data="pn:prices"),
        InlineKeyboardButton(text="💳 Реквизиты", callback_data="pn:pay"),
    )
    kb.row(
        InlineKeyboardButton(text="📥 Заявки", callback_data="pn:deposits"),
        InlineKeyboardButton(text="📞 Тикеты", callback_data="pn:tickets"),
    )
    kb.row(
        InlineKeyboardButton(text="📦 Заказы", callback_data="pn:orders"),
        InlineKeyboardButton(text="🎟 Промокоды", callback_data="pn:promos"),
    )
    kb.row(
        InlineKeyboardButton(text="📈 Отчёты", callback_data="pn:rep"),
        InlineKeyboardButton(text="🔀 Разделы", callback_data="pn:toggles"),
    )
    kb.row(
        InlineKeyboardButton(text="👥 Клиенты", callback_data="pn:users"),
        InlineKeyboardButton(text="📊 Статистика", callback_data="pn:stats"),
    )
    kb.row(
        InlineKeyboardButton(text="💼 Кошелёк", callback_data="pn:wallet"),
        InlineKeyboardButton(text="🔌 Проверить связь", callback_data="pn:fragment"),
    )
    kb.row(
        InlineKeyboardButton(text="🎨 Оформление", callback_data="pn:look"),
        InlineKeyboardButton(text="📝 Объявление", callback_data="pn:notice"),
    )
    kb.row(InlineKeyboardButton(text="🔗 Рекламные ссылки", callback_data="pn:links"))
    kb.row(InlineKeyboardButton(text="⌨️ Все команды", callback_data="pn:help"))
    return kb.as_markup()


def back_kb(target: str = "pn:home", text: str = "‹ Назад") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=text, callback_data=target)
    return kb.as_markup()


async def home_text(conn: aiosqlite.Connection) -> str:
    data = await db.global_stats(conn)
    alerts = []
    if data["pending_deposits"]:
        alerts.append(f"📥 Пополнений ждут: <b>{data['pending_deposits']}</b>")
    if data["open_tickets"]:
        alerts.append(f"📞 Тикетов открыто: <b>{data['open_tickets']}</b>")
    if data["failed_orders"]:
        alerts.append(f"⚠️ Заказов зависло: <b>{data['failed_orders']}</b>")
    if not runtime.get("pay_card_number"):
        alerts.append("❗️ <b>Не заданы реквизиты</b> — деньги принять нельзя")
    if runtime.get_bool("autostopped"):
        alerts.append(
            "🛑 <b>Продажа выключена ботом</b> — выдача не проходит. "
            "Проверьте кошелёк."
        )
    elif runtime.get_int("fail_streak"):
        alerts.append(
            f"⚠️ Подряд не прошло заказов: <b>{runtime.get_int('fail_streak')}</b>"
        )

    block = ("\n".join(alerts) + "\n\n") if alerts else ""
    return (
        "🛠 <b>Админ-панель</b>\n\n"
        f"{block}"
        f"👥 Пользователей: <b>{data['users']}</b>\n"
        f"💰 Пополнено всего: <b>{fmt(data['deposits'])}</b>\n"
        f"🛒 Продано на: <b>{fmt(data['revenue'])}</b> ({data['orders']} заказов)\n"
        f"👛 На балансах клиентов: <b>{fmt(data['held_balance'])}</b>\n\n"
        f"⭐️ Цена звезды: <b>{fmt4(runtime.star_price_e4())}</b>"
        + (f" · прибыль <b>{fmt4(runtime.profit_per_star_e4())}</b>"
           if runtime.star_cost_e4() > 0 else " · себестоимость не задана")
    )


async def show_home(target: Message | CallbackQuery, conn: aiosqlite.Connection) -> None:
    text = await home_text(conn)
    if isinstance(target, CallbackQuery):
        await safe_edit(target, text, home_kb())
    else:
        await target.answer(text, reply_markup=home_kb())


async def safe_edit(call: CallbackQuery, text: str, markup: InlineKeyboardMarkup) -> None:
    """Перерисовать экран. Если содержимое не изменилось, Telegram ругается —
    это не ошибка, просто игнорируем."""
    try:
        await call.message.edit_text(text, reply_markup=markup)
    except TelegramAPIError as exc:
        if "not modified" not in str(exc):
            await call.message.answer(text, reply_markup=markup)


@router.message(Command("panel", "admin"))
async def cmd_panel(message: Message, state: FSMContext, conn: aiosqlite.Connection) -> None:
    await state.clear()
    await show_home(message, conn)


@router.callback_query(F.data == "pn:home")
async def cb_home(call: CallbackQuery, state: FSMContext, conn: aiosqlite.Connection) -> None:
    await state.clear()
    await show_home(call, conn)
    await call.answer()


@router.callback_query(F.data == "pn:help")
async def cb_help(call: CallbackQuery) -> None:
    await safe_edit(call, texts.ADMIN_HELP, back_kb())
    await call.answer()


# =================================================================== цены


def prices_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="💲 Себестоимость", callback_data="pn:set:star_cost_e4"),
        InlineKeyboardButton(text="📈 Наценка %", callback_data="pn:set:margin_percent"),
    )
    kb.row(InlineKeyboardButton(text="🏷 Цена продажи вручную",
                                callback_data="pn:set:star_price_e4"))
    kb.row(btn("📡 Узнать себестоимость", "pn:cost", style=PRIMARY))
    kb.row(btn("🧮 Применить наценку", "pn:recalc", style=SUCCESS))
    for plan in runtime.premium_plans():
        kb.row(InlineKeyboardButton(
            text=f"👑 Premium {plan['months']} мес — {fmt(plan['price'])}",
            callback_data=f"pn:premium:{plan['months']}",
        ))
    kb.row(
        InlineKeyboardButton(text="⬇️ Мин. звёзд", callback_data="pn:set:min_stars"),
        InlineKeyboardButton(text="⬆️ Макс. звёзд", callback_data="pn:set:max_stars"),
    )
    kb.row(
        InlineKeyboardButton(text="💵 Мин. пополнение", callback_data="pn:set:min_deposit_diram"),
        InlineKeyboardButton(text="👥 Реф. %", callback_data="pn:set:referral_percent"),
    )
    kb.row(InlineKeyboardButton(text="‹ Назад", callback_data="pn:home"))
    return kb.as_markup()


def prices_text() -> str:
    cost, price = runtime.star_cost_e4(), runtime.star_price_e4()
    margin = runtime.margin_percent()

    if cost > 0:
        profit = price - cost
        real_margin = round((price - cost) / cost * 100) if cost else 0
        economics = (
            f"├ Себестоимость: <b>{fmt4(cost)}</b>\n"
            f"├ Наценка задана: <b>{margin}%</b>\n"
            f"├ Цена продажи: <b>{fmt4(price)}</b>\n"
            f"├ Фактическая наценка: <b>{real_margin}%</b>\n"
            f"└ Прибыль с 1 звезды: <b>{fmt4(profit)}</b>\n\n"
            f"💡 С заказа в 1000 звёзд заработок: "
            f"<b>{fmt((profit * 1000 + 50) // 100)}</b>"
        )
        if profit < 0:
            economics += "\n\n❗️ <b>Продаёте ниже себестоимости — это убыток.</b>"
    else:
        economics = (
            f"├ Цена продажи: <b>{fmt4(price)}</b>\n"
            f"└ Себестоимость: <b>не задана</b>\n\n"
            "💡 Укажите себестоимость — и панель будет показывать вашу прибыль "
            "с каждого заказа."
        )

    plans = "\n".join(
        f"├ {plan['months']} мес — <b>{fmt(plan['price'])}</b>"
        for plan in runtime.premium_plans()
    )
    return (
        "💵 <b>Цены и наценка</b>\n\n"
        f"⭐️ <b>Звёзды</b>\n{economics}\n\n"
        f"👑 <b>Premium</b>\n{plans}\n\n"
        + ("🟢 <b>Автоцены включены</b> — себестоимость и наценка "
           f"обновляются каждые {runtime.get_int('auto_price_every', 60)} мин.\n\n"
           if runtime.auto_price_on() else
           "⚪️ Автоцены выключены — цена держится, пока не поменяете вручную.\n\n")
        + f"📏 Заказ: от <b>{runtime.min_stars()}</b> до <b>{runtime.max_stars()}</b> звёзд\n"
        f"💵 Мин. пополнение: <b>{fmt(runtime.min_deposit())}</b>\n"
        f"👥 Реферальный процент: <b>{runtime.referral_percent()}%</b>\n"
        + (f"💱 Курс доллара: <b>{fmt(runtime.usd_rate())}</b>"
           if runtime.usd_rate() > 0 else
           "💱 Курс доллара не задан — бот не сможет сам узнать себестоимость")
    )


@router.callback_query(F.data == "pn:prices")
async def cb_prices(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await safe_edit(call, prices_text(), prices_kb())
    await call.answer()


@router.callback_query(F.data == "pn:recalc")
async def cb_recalc(call: CallbackQuery, conn: aiosqlite.Connection) -> None:
    if runtime.star_cost_e4() <= 0:
        await call.answer("Сначала задайте себестоимость.", show_alert=True)
        return
    new_price = runtime.price_from_margin_e4()
    await runtime.set_value(conn, "star_price_e4", str(new_price))
    await call.answer(f"Цена продажи: {fmt4(new_price)}")
    await safe_edit(call, prices_text(), prices_kb())


@router.callback_query(F.data.startswith("pn:premium:"))
async def cb_premium_edit(call: CallbackQuery, state: FSMContext) -> None:
    months = int(call.data.rsplit(":", 1)[1])
    plan = runtime.find_premium(months)
    if plan is None:
        await call.answer("Тариф не найден.", show_alert=True)
        return
    await state.set_state(Panel.value)
    await state.update_data(field=f"premium:{months}")
    await safe_edit(
        call,
        f"👑 <b>Premium {months} мес.</b>\n\n"
        f"Сейчас: <b>{fmt(plan['price'])}</b>\n\n"
        f"Введите новую цену в сомони (например <code>175</code> или <code>175.50</code>):",
        back_kb("pn:prices"),
    )
    await call.answer()


# ============================================================== реквизиты


PAY_FIELDS = {
    "pay_card_number": ("💳 Номер карты", "Введите номер карты:"),
    "dc_account": ("🏙 Счёт «Душанбе Сити»",
                   "По умолчанию берётся карта из реквизитов. Заполняйте, "
                   "только если деньги приходят на другой счёт "
                   "(параметр <code>a</code> из ссылки pay.dc.tj):"),
    "dc_comment": ("📝 Подпись в платеже",
                   "Что писать в комментарии к переводу перед кодом платежа — "
                   "например <code>@uwayscoder</code>:"),
    "dc_service": ("🔢 Код услуги", "Параметр <code>f1</code> из ссылки. Обычно 133:"),
    "pay_card_holder": ("👤 Владелец", "Введите имя владельца карты:"),
    "pay_card_bank": ("🏦 Банк", "Введите название банка:"),
    "pay_city": ("🏙 Город", "Введите город:"),
    "pay_extra": ("📝 Примечание", "Введите примечание под реквизитами "
                                   "(или <code>-</code>, чтобы убрать):"),
}


def pay_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for key, (label, _) in PAY_FIELDS.items():
        kb.row(InlineKeyboardButton(text=label, callback_data=f"pn:set:{key}"))
    kb.row(btn("👁 Как видит клиент", "pn:preview_pay", style=PRIMARY))
    kb.row(btn("🏙 Проверить кнопку оплаты", "pn:dctest"))
    kb.row(InlineKeyboardButton(text="‹ Назад", callback_data="pn:home"))
    return kb.as_markup()


def pay_text() -> str:
    def show(key: str) -> str:
        value = runtime.get(key)
        return f"<b>{value}</b>" if value else "<i>не задано</i>"

    warning = ""
    if not runtime.get("pay_card_number"):
        warning = "\n❗️ <b>Без номера карты клиенты не смогут пополнить баланс.</b>\n"

    dc_state = "✅ <b>работает</b>" if dcpay.is_ready() else "⚪️ <i>не настроена</i>"
    dc_source = (
        "<i>та же, что в реквизитах</i>" if not runtime.get("dc_account")
        else f"<b>{runtime.get('dc_account')}</b>"
    )
    return (
        "💳 <b>Реквизиты для приёма оплаты</b>\n"
        f"{warning}\n"
        f"├ Карта: {show('pay_card_number')}\n"
        f"├ Владелец: {show('pay_card_holder')}\n"
        f"├ Банк: {show('pay_card_bank')}\n"
        f"├ Город: {show('pay_city')}\n"
        f"└ Примечание: {show('pay_extra')}\n\n"
        f"🏙 <b>Кнопка «Душанбе Сити»</b> — {dc_state}\n"
        f"├ Счёт: {dc_source}\n"
        f"├ Подпись: <b>{dcpay.comment_prefix() or '—'}</b>\n"
        f"└ Код услуги: {show('dc_service')}\n\n"
        "<blockquote>Кнопка открывает приложение с уже вписанными счётом "
        "и суммой — покупателю не нужно переписывать их вручную, а значит "
        "негде ошибиться.</blockquote>"
    )


@router.callback_query(F.data == "pn:pay")
async def cb_pay(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await safe_edit(call, pay_text(), pay_kb())
    await call.answer()


@router.callback_query(F.data == "pn:preview_pay")
async def cb_preview_pay(call: CallbackQuery) -> None:
    holder = runtime.get("pay_card_holder")
    bank = runtime.get("pay_card_bank")
    note = runtime.get("pay_extra")
    preview = texts.DEPOSIT_REQUISITES.format(
        amount=fmt(10000),
        card=runtime.get("pay_card_number") or "— реквизиты не заданы —",
        holder=f"👤 Получатель: <b>{holder}</b>\n" if holder else "",
        bank=f"🏦 Банк: <b>{bank}</b>\n" if bank else "",
        city=runtime.get("pay_city"),
        extra=f"\n{note}\n" if note else "",
    )
    await safe_edit(
        call, "👁 <b>Так это видит клиент:</b>\n\n" + preview, back_kb("pn:pay")
    )
    await call.answer()


# ==================================================== универсальный ввод


# Поле -> (заголовок, подсказка, тип). Тип: money | int | percent | text
FIELDS: dict[str, tuple[str, str, str]] = {
    "star_cost_e4": ("💲 Себестоимость звезды",
                        "Сколько ОДНА звезда стоит вам на Fragment, в сомони.\n"
                        "Например <code>0.1416</code>:", "price4"),
    "star_price_e4": ("🏷 Цена продажи звезды",
                         "За сколько продаёте ОДНУ звезду, в сомони.\n"
                         "Например <code>0.1629</code>:", "price4"),
    "usd_rate_diram": ("💱 Курс доллара",
                       "Сколько сомони стоит 1 доллар. Например <code>10.90</code>:", "money"),
    "margin_percent": ("📈 Наценка",
                       "Процент наценки к себестоимости. Например <code>30</code>:", "percent"),
    "min_stars": ("⬇️ Минимум звёзд", "Минимум звёзд в одном заказе:", "int"),
    "max_stars": ("⬆️ Максимум звёзд", "Максимум звёзд в одном заказе:", "int"),
    "min_deposit_diram": ("💵 Минимальное пополнение",
                          "Минимальная сумма пополнения в сомони:", "money"),
    "referral_percent": ("👥 Реферальный процент",
                         "Сколько процентов получает пригласивший "
                         "с каждого пополнения:", "percent"),
    "autostop_after": ("🔢 Порог автостопа",
                       "После скольких неудачных заказов подряд бот гасит "
                       "продажу. Обычно 3:", "int"),
    "support_notice": ("📝 Объявление в поддержке",
                       "Текст, который увидят клиенты в разделе «Поддержка» "
                       "(или <code>-</code>, чтобы убрать):", "text"),
}
FIELDS.update({
    key: (label, prompt, "text") for key, (label, prompt) in PAY_FIELDS.items()
})

# Куда возвращаться после сохранения
FIELD_PARENT = {key: "pn:pay" for key in PAY_FIELDS}
FIELD_PARENT.update({
    "star_cost_e4": "pn:prices", "star_price_e4": "pn:prices",
    "margin_percent": "pn:prices", "min_stars": "pn:prices",
    "usd_rate_diram": "pn:prices",
    "max_stars": "pn:prices", "min_deposit_diram": "pn:prices",
    "referral_percent": "pn:prices", "support_notice": "pn:home",
    "autostop_after": "pn:wallet",
})


def current_display(key: str) -> str:
    kind = FIELDS[key][2]
    raw = runtime.get(key)
    if kind == "price4":
        return fmt4(runtime.get_int(key))
    if kind == "money":
        return fmt(runtime.get_int(key))
    if kind == "percent":
        return f"{raw or 0}%"
    return raw or "не задано"


async def start_field_edit(call: CallbackQuery, state: FSMContext, key: str) -> bool:
    """Показать экран ввода значения. False — поля не существует."""
    if key not in FIELDS:
        return False
    label, prompt, _ = FIELDS[key]
    await state.set_state(Panel.value)
    await state.update_data(field=key)
    await safe_edit(
        call,
        f"{label}\n\nСейчас: <b>{current_display(key)}</b>\n\n{prompt}",
        back_kb(FIELD_PARENT.get(key, "pn:home"), "❌ Отмена"),
    )
    return True


@router.callback_query(F.data.startswith("pn:set:"))
async def cb_set_field(call: CallbackQuery, state: FSMContext) -> None:
    key = call.data.rsplit(":", 1)[1]
    if not await start_field_edit(call, state, key):
        await call.answer("Неизвестное поле.", show_alert=True)
        return
    await call.answer()


@router.message(Panel.value, F.text)
async def on_field_value(
    message: Message, state: FSMContext, conn: aiosqlite.Connection
) -> None:
    data = await state.get_data()
    field = data.get("field", "")
    raw = (message.text or "").strip()

    # Тариф Premium — отдельная ветка, он живёт в JSON-списке.
    if field.startswith("premium:"):
        months = int(field.split(":")[1])
        amount = parse(raw)
        if amount is None or amount <= 0:
            await message.answer("❌ Введите сумму числом, например <code>175</code>.")
            return
        plans = runtime.premium_plans()
        for plan in plans:
            if plan["months"] == months:
                plan["price"] = amount
        await runtime.save_premium_plans(conn, plans)
        await state.clear()
        await message.answer(
            f"✅ Premium {months} мес. теперь <b>{fmt(amount)}</b>",
            reply_markup=back_kb("pn:prices", "‹ К ценам"),
        )
        return

    if field not in FIELDS:
        await state.clear()
        await message.answer("Не понял, что менять. Откройте /panel заново.")
        return

    kind = FIELDS[field][2]
    if kind == "price4":
        amount = parse4(raw)
        if amount is None or amount < 0:
            await message.answer(
                "❌ Введите цену числом, например <code>0.1629</code>. "
                "Можно до четырёх знаков после точки."
            )
            return
        value, shown = str(amount), fmt4(amount)
    elif kind == "money":
        amount = parse(raw)
        if amount is None or amount < 0:
            await message.answer("❌ Введите сумму числом, например <code>0.25</code> или <code>150</code>.")
            return
        value = str(amount)
        shown = fmt(amount)
    elif kind in ("int", "percent"):
        if not raw.isdigit():
            await message.answer("❌ Введите целое число.")
            return
        number = int(raw)
        if kind == "percent" and number > 100:
            await message.answer("❌ Процент не может быть больше 100.")
            return
        if kind == "int" and number <= 0:
            await message.answer("❌ Число должно быть больше нуля.")
            return
        value = str(number)
        shown = f"{number}%" if kind == "percent" else str(number)
    else:
        value = "" if raw == "-" else raw
        shown = value or "убрано"

    await runtime.set_value(conn, field, value)
    await state.clear()

    extra = ""
    if field == "star_cost_diram" and runtime.margin_percent() > 0:
        extra = (f"\n\nПо наценке {runtime.margin_percent()}% цена продажи должна быть "
                 f"<b>{fmt(runtime.price_from_margin())}</b> — нажмите «Пересчитать по наценке».")
    if field in ("min_stars", "max_stars") and runtime.min_stars() > runtime.max_stars():
        extra = "\n\n❗️ Минимум больше максимума — клиенты не смогут купить ничего."

    await message.answer(
        f"✅ <b>{FIELDS[field][0]}</b> → <b>{shown}</b>{extra}",
        reply_markup=back_kb(FIELD_PARENT.get(field, "pn:home"), "‹ Назад"),
    )


@router.callback_query(F.data == "pn:notice")
async def cb_notice(call: CallbackQuery, state: FSMContext) -> None:
    await start_field_edit(call, state, "support_notice")
    await call.answer()


# ============================================================== разделы


@router.callback_query(F.data == "pn:toggles")
async def cb_toggles(call: CallbackQuery) -> None:
    await safe_edit(call, toggles_text(), toggles_kb())
    await call.answer()


def toggles_text() -> str:
    return (
        "🔀 <b>Разделы бота</b>\n\n"
        "Выключенный раздел пропадает из меню у клиентов. Удобно, когда "
        "закончились звёзды на Fragment или меняете реквизиты.\n\n"
        f"{'✅' if runtime.get_bool('stars_enabled') else '🚫'} Продажа звёзд\n"
        f"{'✅' if runtime.get_bool('premium_enabled') else '🚫'} Продажа Premium\n"
        f"{'✅' if runtime.get_bool('deposit_enabled') else '🚫'} Пополнение баланса\n\n"
        f"🏆 Топ клиентов считается по сумме {top_basis(runtime.get('top_by'))}."
    )


def toggles_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for key, label in (
        ("stars_enabled", "звёзды"),
        ("premium_enabled", "Premium"),
        ("deposit_enabled", "пополнение"),
    ):
        state = runtime.get_bool(key)
        kb.row(btn(
            ("🚫 Выключить " if state else "✅ Включить ") + label,
            f"pn:toggle:{key}", style=DANGER if state else SUCCESS,
        ))
    by_deposits = runtime.get("top_by") == "deposits"
    kb.row(btn(
        "🏆 Топ по " + ("покупкам" if by_deposits else "пополнениям"),
        "pn:topby", style=PRIMARY,
    ))
    kb.row(InlineKeyboardButton(text="‹ Назад", callback_data="pn:home"))
    return kb.as_markup()


@router.callback_query(F.data == "pn:topby")
async def cb_topby(call: CallbackQuery, conn: aiosqlite.Connection) -> None:
    """Переключить, по чему строится топ клиентов."""
    value = "purchases" if runtime.get("top_by") == "deposits" else "deposits"
    await runtime.set_value(conn, "top_by", value)
    await call.answer("Готово")
    await safe_edit(call, toggles_text(), toggles_kb())


@router.callback_query(F.data.startswith("pn:toggle:"))
async def cb_toggle(call: CallbackQuery, conn: aiosqlite.Connection) -> None:
    key = call.data.rsplit(":", 1)[1]
    if key not in ("stars_enabled", "premium_enabled", "deposit_enabled"):
        await call.answer("Неизвестный раздел.", show_alert=True)
        return
    await runtime.set_value(conn, key, "0" if runtime.get_bool(key) else "1")
    await call.answer("Готово")
    await safe_edit(call, toggles_text(), toggles_kb())


# ============================================================== списки


@router.callback_query(F.data == "pn:stats")
async def cb_stats(call: CallbackQuery, conn: aiosqlite.Connection) -> None:
    await safe_edit(call, texts.money_stats(await db.global_stats(conn)), back_kb())
    await call.answer()


@router.callback_query(F.data == "pn:deposits")
async def cb_deposits(call: CallbackQuery, conn: aiosqlite.Connection) -> None:
    deposits = await db.list_deposits(conn, status=db.DEP_PENDING, limit=10)
    kb = InlineKeyboardBuilder()
    if not deposits:
        body = "📥 <b>Заявки на пополнение</b>\n\nНа проверке ничего нет."
    else:
        lines = []
        for dep in deposits:
            lines.append(f"<b>№{dep.id}</b> · {fmt(dep.amount)} · <code>{dep.user_id}</code>")
            kb.row(
                InlineKeyboardButton(text=f"✅ №{dep.id}", callback_data=f"a:dep_ok:{dep.id}"),
                InlineKeyboardButton(text=f"❌ №{dep.id}", callback_data=f"a:dep_no:{dep.id}"),
            )
        body = (
            "📥 <b>Заявки на пополнение</b>\n\n" + "\n".join(lines)
            + "\n\n💡 Чек с кнопками пришёл отдельным сообщением — "
              "сверьте сумму в банке перед зачислением."
        )
    kb.row(InlineKeyboardButton(text="🔄 Обновить", callback_data="pn:deposits"))
    kb.row(InlineKeyboardButton(text="‹ Назад", callback_data="pn:home"))
    await safe_edit(call, body, kb.as_markup())
    await call.answer()


@router.callback_query(F.data == "pn:tickets")
async def cb_tickets(call: CallbackQuery, conn: aiosqlite.Connection) -> None:
    tickets = await db.list_tickets(conn, status=db.TICKET_OPEN, limit=10)
    if not tickets:
        body = "📞 <b>Тикеты</b>\n\nОткрытых нет."
    else:
        lines = [
            f"<b>№{t.id}</b> от <code>{t.user_id}</code>\n"
            f"<i>{t.subject[:150]}</i>\n"
            f"Ответить: <code>/answer {t.id} текст</code>"
            for t in tickets
        ]
        body = "📞 <b>Открытые тикеты</b>\n\n" + "\n\n".join(lines)
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔄 Обновить", callback_data="pn:tickets"))
    kb.row(InlineKeyboardButton(text="‹ Назад", callback_data="pn:home"))
    await safe_edit(call, body, kb.as_markup())
    await call.answer()


@router.callback_query(F.data == "pn:orders")
async def cb_orders(call: CallbackQuery, conn: aiosqlite.Connection) -> None:
    failed = await db.list_orders(conn, status=db.ORDER_FAILED, limit=5)
    recent = await db.list_orders(conn, limit=8)

    blocks = []
    if failed:
        blocks.append(
            "⚠️ <b>Требуют решения</b>\n"
            + "\n".join(
                f"<b>№{o.id}</b> {o.title} → @{o.recipient} · {fmt(o.price)}\n"
                f"Дошёл: <code>/done {o.id}</code> · Вернуть: <code>/refund {o.id}</code>"
                for o in failed
            )
        )
    if recent:
        blocks.append(
            "📦 <b>Последние заказы</b>\n"
            + "\n".join(
                f"<b>№{o.id}</b> {o.title} → @{o.recipient}\n"
                f"{fmt(o.price)} · {o.status_title}"
                for o in recent
            )
        )
    body = "\n\n".join(blocks) if blocks else "📦 <b>Заказы</b>\n\nЗаказов ещё нет."

    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔄 Обновить", callback_data="pn:orders"))
    kb.row(InlineKeyboardButton(text="‹ Назад", callback_data="pn:home"))
    await safe_edit(call, body, kb.as_markup())
    await call.answer()


def promo_line(row) -> str:
    """Одна строка списка: что за код, сколько потрачено и жив ли он."""
    left = max(row["max_uses"] - row["used_count"], 0)
    alive = left > 0
    value = (f"−{row['percent']}%" if row["kind"] == "discount"
             else f"+{fmt(row['amount'])}")
    return (
        f"{'🟢' if alive else '🔴'} <code>{row['code']}</code> — <b>{value}</b>\n"
        f"├ Использован: <b>{row['used_count']}</b> из <b>{row['max_uses']}</b>\n"
        f"├ Осталось: <b>{left}</b>\n"
        f"└ Статус: <b>{'Активен' if alive else 'Закончился'}</b>"
    )


def promos_text(rows: list) -> str:
    if not rows:
        body = (
            "<blockquote>Пока ни одного. Нажмите «Создать промокод» — "
            "спрошу код, процент скидки и число активаций.</blockquote>"
        )
    else:
        body = "\n\n".join(promo_line(row) for row in rows)
    return (
        "🎟 <b>Промокоды</b>\n"
        f"<code>{texts.LINE}</code>\n\n"
        f"{body}\n\n"
        "<blockquote>Скидка действует на все товары бота. Активация "
        "списывается только после успешно выданного заказа.</blockquote>"
    )


def promos_kb(rows: list) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(btn("➕ Создать промокод", "pn:promo_new", style=SUCCESS))
    for row in rows[:15]:
        kb.row(InlineKeyboardButton(
            text=f"🗑 {row['code']}", callback_data=f"pn:promo_del:{row['code']}",
        ))
    kb.row(InlineKeyboardButton(text="‹ Назад", callback_data="pn:home"))
    return kb.as_markup()


@router.callback_query(F.data == "pn:promos")
async def cb_promos(call: CallbackQuery, state: FSMContext, conn: aiosqlite.Connection) -> None:
    await state.clear()
    rows = await db.list_promos(conn, limit=15)
    await safe_edit(call, promos_text(rows), promos_kb(rows))
    await call.answer()


@router.callback_query(F.data.startswith("pn:promo_del:"))
async def cb_promo_delete(call: CallbackQuery, conn: aiosqlite.Connection) -> None:
    code = call.data.split(":", 2)[2]
    await db.delete_promo(conn, code)
    await call.answer(f"{code} удалён")
    rows = await db.list_promos(conn, limit=15)
    await safe_edit(call, promos_text(rows), promos_kb(rows))


# ------------------------------------------- пошаговое создание промокода


@router.callback_query(F.data == "pn:promo_new")
async def cb_promo_new(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(PromoNew.code)
    await state.update_data(promo={})
    await safe_edit(
        call,
        "🎟 <b>Новый промокод</b>\n"
        f"<code>{texts.LINE}</code>\n\n"
        "<b>Шаг 1 из 3 — Промокод</b>\n\n"
        "<blockquote>Введите промокод.\n\nНапример: <code>ALI10</code></blockquote>",
        back_kb("pn:promos", "❌ Отмена"),
    )
    await call.answer()


@router.message(PromoNew.code, F.text)
async def on_promo_code(
    message: Message, state: FSMContext, conn: aiosqlite.Connection
) -> None:
    code = (message.text or "").strip().upper()
    if not code.isalnum() or len(code) > 32:
        await message.answer(
            "❌ Код — латинские буквы и цифры, до 32 символов.\n\n"
            "<i>Например: <code>ALI10</code></i>"
        )
        return
    if await db.get_promo(conn, code):
        await message.answer(f"❌ Промокод <code>{code}</code> уже есть.")
        return

    await state.update_data(promo={"code": code})
    await state.set_state(PromoNew.percent)
    await message.answer(
        f"🎟 <b>Промокод {code}</b>\n"
        f"<code>{texts.LINE}</code>\n\n"
        "<b>Шаг 2 из 3 — Скидка</b>\n\n"
        "<blockquote>Сколько процентов скидка?\n\nНапример: <code>10</code></blockquote>",
        reply_markup=back_kb("pn:promos", "❌ Отмена"),
    )


@router.message(PromoNew.percent, F.text)
async def on_promo_percent(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip().rstrip("%").replace(",", ".").strip()
    if not raw.isdigit() or not 1 <= int(raw) <= 100:
        await message.answer("❌ Введите целое число от 1 до 100.")
        return

    data = await state.get_data()
    promo = dict(data.get("promo") or {})
    promo["percent"] = int(raw)
    await state.update_data(promo=promo)
    await state.set_state(PromoNew.limit)
    await message.answer(
        f"🎟 <b>Промокод {promo['code']}</b>\n"
        f"<code>{texts.LINE}</code>\n\n"
        "<b>Шаг 3 из 3 — Количество активаций</b>\n\n"
        "<blockquote>Сколько раз можно активировать этот промокод?\n\n"
        "Например: <code>100</code></blockquote>",
        reply_markup=back_kb("pn:promos", "❌ Отмена"),
    )


@router.message(PromoNew.limit, F.text)
async def on_promo_limit(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if not raw.isdigit() or not 1 <= int(raw) <= 1_000_000:
        await message.answer("❌ Введите целое число активаций, например <code>100</code>.")
        return

    data = await state.get_data()
    promo = dict(data.get("promo") or {})
    promo["limit"] = int(raw)
    await state.update_data(promo=promo)
    await state.set_state(PromoNew.confirm)

    kb = InlineKeyboardBuilder()
    kb.row(btn("💾 Сохранить", "pn:promo_save", style=SUCCESS))
    kb.row(btn("❌ Отмена", "pn:promos", style=DANGER))
    await message.answer(promo_preview(promo), reply_markup=kb.as_markup())


def promo_preview(promo: dict) -> str:
    return (
        "🎟 <b>Проверьте промокод</b>\n"
        f"<code>{texts.LINE}</code>\n\n"
        f"├ Промокод: <code>{promo.get('code')}</code>\n"
        f"├ Скидка: <b>{promo.get('percent')}%</b>\n"
        f"└ Лимит активаций: <b>{promo.get('limit')}</b>\n\n"
        "<blockquote>После сохранения код сразу заработает: клиенты смогут "
        "ввести его при покупке любого товара.</blockquote>"
    )


@router.callback_query(PromoNew.confirm, F.data == "pn:promo_save")
async def cb_promo_save(
    call: CallbackQuery, state: FSMContext, conn: aiosqlite.Connection
) -> None:
    data = await state.get_data()
    promo = data.get("promo") or {}
    await state.clear()

    if not promo.get("code") or not promo.get("percent") or not promo.get("limit"):
        await call.answer("Данные потерялись — начните заново.", show_alert=True)
        rows = await db.list_promos(conn, limit=15)
        await safe_edit(call, promos_text(rows), promos_kb(rows))
        return

    saved = await db.create_promo(
        conn, promo["code"], amount=0, max_uses=promo["limit"],
        kind="discount", percent=promo["percent"],
    )
    if not saved:
        await call.answer("Такой промокод уже есть.", show_alert=True)
        rows = await db.list_promos(conn, limit=15)
        await safe_edit(call, promos_text(rows), promos_kb(rows))
        return

    await call.answer("Сохранён")
    await safe_edit(
        call,
        f"✅ <b>Промокод {promo['code']} создан</b>\n"
        f"<code>{texts.LINE}</code>\n\n"
        f"├ Скидка: <b>{promo['percent']}%</b>\n"
        f"└ Активаций: <b>{promo['limit']}</b>\n\n"
        "<blockquote>Код уже активен.</blockquote>",
        back_kb("pn:promos", "‹ К промокодам"),
    )


# ----------------------------- старый однострочный ввод (код на баланс)


@router.message(PromoNew.data, F.text)
async def on_promo_new(
    message: Message, state: FSMContext, conn: aiosqlite.Connection
) -> None:
    parts = (message.text or "").split()
    if len(parts) != 3 or not parts[2].isdigit():
        await message.answer("❌ Формат: <code>КОД сумма лимит</code>, например "
                             "<code>SALE10 10 100</code>")
        return
    amount = parse(parts[1])
    if amount is None or amount <= 0:
        await message.answer("❌ Сумма должна быть положительным числом.")
        return
    if not await db.create_promo(conn, parts[0], amount, int(parts[2])):
        await message.answer("❌ Такой промокод уже есть.")
        return
    await state.clear()
    await message.answer(
        f"✅ Промокод <code>{parts[0].upper()}</code> на <b>{fmt(amount)}</b>, "
        f"активаций: <b>{parts[2]}</b>",
        reply_markup=back_kb("pn:promos", "‹ К промокодам"),
    )


# =========================================================== проверка связи


@router.callback_query(F.data == "pn:fragment")
async def cb_fragment(call: CallbackQuery, provider) -> None:
    """Пошаговая проверка: можно ли вообще выдавать товар."""
    await safe_edit(call, "🔌 Проверяю связь с Fragment…", back_kb())
    await call.answer()

    try:
        report = await provider.healthcheck()
    except Exception as exc:  # noqa: BLE001 — показать админу любую поломку
        log.exception("Проверка Fragment упала")
        await safe_edit(
            call,
            f"🔌 <b>Проверка Fragment</b>\n\n❌ Сорвалась с ошибкой:\n"
            f"<code>{type(exc).__name__}: {exc}</code>",
            back_kb(),
        )
        return

    lines = [f"├ {name}: {result}" for name, result in report["steps"]]
    if lines:
        lines[-1] = "└" + lines[-1][1:]

    if report["mode"] == "mock":
        verdict = (
            "⚠️ <b>Режим MOCK.</b>\n\n"
            "Бот работает целиком, но звёзды <b>никуда не отправляются</b> — "
            "это режим для проверки. Клиенты будут получать «заказ выполнен», "
            "не получая звёзд.\n\n"
            "Для реальных продаж поставьте <code>FRAGMENT_MODE=api</code> "
            "в .env и перезапустите бота."
        )
    elif report["ok"]:
        verdict = (
            "✅ <b>Связь есть, выдача возможна.</b>\n\n"
            "Проверьте, что на кошельке хватает средств: при нехватке "
            "заказ упадёт, а деньги вернутся клиенту на баланс."
        )
    else:
        verdict = (
            "❌ <b>Выдача невозможна.</b>\n\n"
            "Пока не починить — не включайте продажу звёзд, иначе клиенты "
            "будут платить и получать возврат. Выключить можно "
            "в разделе «Разделы»."
        )

    kb = InlineKeyboardBuilder()
    if getattr(provider, "probe_paths", None) is not None:
        kb.row(btn("🔍 Найти адреса API", "pn:probe", style=PRIMARY))
    kb.row(InlineKeyboardButton(text="🔄 Проверить снова", callback_data="pn:fragment"))
    kb.row(InlineKeyboardButton(text="‹ Назад", callback_data="pn:home"))

    await safe_edit(
        call,
        "🔌 <b>Проверка связи</b>\n\n" + "\n".join(lines) + "\n\n" + verdict,
        kb.as_markup(),
    )


@router.callback_query(F.data == "pn:probe")
async def cb_probe(call: CallbackQuery, provider) -> None:
    """Найти рабочие адреса перебором — быстрее, чем сверять документацию."""
    probe = getattr(provider, "probe_paths", None)
    if probe is None:
        await call.answer("Этот сервис не умеет искать адреса.", show_alert=True)
        return

    await safe_edit(call, "🔍 Перебираю адреса, это займёт секунд десять…",
                    back_kb("pn:fragment"))
    await call.answer()

    try:
        found = await probe()
    except Exception as exc:  # noqa: BLE001
        log.warning("Перебор адресов не удался: %s", exc)
        await safe_edit(call, f"❌ Не получилось: <code>{exc}</code>",
                        back_kb("pn:fragment"))
        return

    kb = InlineKeyboardBuilder()
    blocks = []

    for kind, title, prefix in (
        ("balance", "💰 Баланс", "pn:usepath:balance:"),
        ("orders", "📦 Заказы", "pn:usepath:orders:"),
    ):
        hits = found.get(kind) or []
        if not hits:
            blocks.append(f"{title}\n└ ничего не нашлось")
            continue
        lines = [f"├ <code>{path}</code>\n│  <i>{sample}</i>" for path, sample in hits]
        blocks.append(f"{title}\n" + "\n".join(lines))
        for path, _ in hits[:3]:
            kb.row(InlineKeyboardButton(
                text=f"✅ Взять {path}", callback_data=prefix + path,
            ))

    kb.row(InlineKeyboardButton(text="‹ Назад", callback_data="pn:fragment"))
    await safe_edit(
        call,
        "🔍 <b>Что ответило сервисом</b>\n\n" + "\n\n".join(blocks)
        + "\n\nВыберите подходящий адрес — бот запомнит его.",
        kb.as_markup(),
    )


@router.callback_query(F.data.startswith("pn:usepath:"))
async def cb_use_path(call: CallbackQuery, conn: aiosqlite.Connection) -> None:
    _, _, kind, path = call.data.split(":", 3)
    if kind == "balance":
        await runtime.set_value(conn, "fazer_balance_path", path)
    else:
        # Одиночный заказ обычно лежит рядом со списком.
        await runtime.set_value(conn, "fazer_order_path", path.rstrip("/") + "/{order_id}")
    await call.answer("Адрес сохранён — нажмите «Проверить связь»")


# ============================================================== кошелёк


def wallet_text() -> str:
    stars = runtime.get_int("stars_since_topup")
    months = runtime.get_int("premium_since_topup")
    topup = runtime.get("topup_at") or "не отмечалось"
    cost = runtime.star_cost()

    spent = f"~{fmt(stars * cost)}" if cost > 0 else "неизвестно (не задана себестоимость)"
    status = (
        "🛑 <b>Продажа выключена ботом</b> — выдача не проходила подряд."
        if runtime.get_bool("autostopped")
        else f"✅ Продажа работает. Неудач подряд: <b>{runtime.get_int('fail_streak')}</b>."
    )

    return (
        "💼 <b>Кошелёк Fragment</b>\n\n"
        f"{status}\n\n"
        f"📅 Последнее пополнение: <b>{topup}</b>\n\n"
        "<b>Выдано с тех пор:</b>\n"
        f"├ Звёзд: <b>{stars}</b> (себестоимость {spent})\n"
        f"└ Premium: <b>{months} мес.</b>\n\n"
        f"🛑 Бот гасит продажу после <b>{runtime.autostop_after()}</b> неудач подряд — "
        "чтобы клиенты не платили в пустоту, пока вас нет.\n\n"
        "💡 Пополнили кошелёк — нажмите кнопку ниже: счётчики обнулятся, "
        "продажа включится обратно."
    )


def wallet_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(btn("✅ Я пополнил кошелёк", "pn:topup", style=SUCCESS))
    kb.row(InlineKeyboardButton(text="🔢 Порог автостопа", callback_data="pn:set:autostop_after"))
    kb.row(InlineKeyboardButton(text="‹ Назад", callback_data="pn:home"))
    return kb.as_markup()


@router.callback_query(F.data == "pn:wallet")
async def cb_wallet(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await safe_edit(call, wallet_text(), wallet_kb())
    await call.answer()


@router.callback_query(F.data == "pn:topup")
async def cb_topup(call: CallbackQuery, conn: aiosqlite.Connection) -> None:
    was_stopped = runtime.get_bool("autostopped")
    # Дату берём из сообщения Telegram, а не из системных часов сервера:
    # так она совпадает с тем, что видит владелец в переписке.
    await runtime.mark_topup(conn, call.message.date.strftime("%d.%m.%Y %H:%M UTC"))
    await call.answer("Счётчики обнулены" + (", продажа включена" if was_stopped else ""))
    await safe_edit(call, wallet_text(), wallet_kb())


# ================================================= себестоимость из API


@router.callback_query(F.data == "pn:cost")
async def cb_cost(call: CallbackQuery, provider) -> None:
    """Спросить у сервиса выдачи, во что заказ обходится владельцу."""
    estimate_fn = getattr(provider, "cost_estimate", None)
    if estimate_fn is None:
        await call.answer(
            "Этот способ выдачи не умеет отдавать цену. "
            "Себестоимость придётся вписать вручную.",
            show_alert=True,
        )
        return

    rate = runtime.usd_rate()
    if rate <= 0:
        await safe_edit(
            call,
            "💱 <b>Сначала задайте курс доллара</b>\n\n"
            "Сервис выдачи считает в TON и долларах, а вы продаёте за сомони. "
            "Чтобы перевести одно в другое, боту нужен курс.\n\n"
            "Посмотрите курс доллара к сомони и нажмите кнопку ниже.",
            back_kb("pn:set:usd_rate_diram", "💱 Задать курс"),
        )
        await call.answer()
        return

    await safe_edit(call, "📡 Спрашиваю цену у сервиса выдачи…", back_kb("pn:prices"))
    await call.answer()

    try:
        # Считаем на 1000 звёзд: так точнее, чем на 50, и меньше округления.
        estimate = await estimate_fn("stars", 1000)
    except Exception as exc:  # noqa: BLE001 — показать админу любую поломку
        log.warning("Не удалось узнать себестоимость: %s", exc)
        await safe_edit(
            call,
            f"❌ <b>Цена не пришла</b>\n\n<code>{exc}</code>\n\n"
            "Проверьте связь: /panel → 🔌 Проверить связь.",
            back_kb("pn:prices"),
        )
        return

    # Себестоимость одной звезды в дирамах.
    cost = int((estimate.usd_per_unit * rate * 100).to_integral_value(
        rounding="ROUND_HALF_UP"))
    margin = runtime.margin_percent()
    suggested = round(cost * (100 + margin) / 100) if margin else cost

    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text=f"✅ Записать {fmt4(cost)} как себестоимость",
        callback_data=f"pn:cost_save:{cost}",
    ))
    kb.row(InlineKeyboardButton(text="📈 Изменить наценку", callback_data="pn:set:margin_percent"))
    kb.row(InlineKeyboardButton(text="💱 Изменить курс", callback_data="pn:set:usd_rate_diram"))
    kb.row(InlineKeyboardButton(text="‹ Назад", callback_data="pn:prices"))

    margin_line = (
        f"\n📈 С вашей наценкой <b>{margin}%</b> продавать по "
        f"<b>{fmt4(suggested)}</b> за звезду\n"
        f"   (прибыль <b>{fmt4(suggested - cost)}</b> со звезды, "
        f"<b>{fmt(((suggested - cost) * 1000 + 50) // 100)}</b> с 1000)"
        if margin else
        "\n📈 Наценка не задана — поставьте её, и бот посчитает цену продажи."
    )

    await safe_edit(
        call,
        "📡 <b>Себестоимость от сервиса выдачи</b>\n\n"
        f"За <b>{estimate.quantity} звёзд</b> вы платите "
        f"<b>{estimate.amount} {estimate.currency.upper()}</b>\n"
        f"Это <b>${estimate.usd_total:.2f}</b>"
        + (f" (курс TON: ${estimate.usdt_per_ton})" if estimate.usdt_per_ton else "")
        + f"\n\n💱 По вашему курсу <b>{fmt(rate)}</b> за доллар:\n"
        f"└ одна звезда обходится в <b>{fmt4(cost)}</b>\n"
        f"{margin_line}\n\n"
        "⚠️ Курс TON меняется — проверяйте себестоимость раз в несколько дней.",
        kb.as_markup(),
    )


@router.callback_query(F.data.startswith("pn:cost_save:"))
async def cb_cost_save(call: CallbackQuery, conn: aiosqlite.Connection) -> None:
    cost = int(call.data.rsplit(":", 1)[1])
    await runtime.set_value(conn, "star_cost_e4", str(cost))

    margin = runtime.margin_percent()
    if margin > 0:
        await runtime.set_value(conn, "star_price_e4",
                                str(runtime.price_from_margin_e4()))
        await call.answer(f"Себестоимость {fmt4(cost)}, цена пересчитана")
    else:
        await call.answer(f"Себестоимость {fmt4(cost)} записана")
    await safe_edit(call, prices_text(), prices_kb())


# ============================================================= оформление


@router.callback_query(F.data == "pn:look")
async def cb_look(call: CallbackQuery, state: FSMContext) -> None:
    """Список групп значков. Меняются по одному, видно сразу."""
    await state.clear()
    kb = InlineKeyboardBuilder()
    for group in emoji.GROUPS:
        kb.row(InlineKeyboardButton(text=group, callback_data=f"pn:emg:{group}"))
    kb.row(btn(
        "🚫 Выключить премиум-эмодзи" if emoji.premium_on()
        else "💎 Проверить премиум-эмодзи",
        "pn:emtest",
        style=DANGER if emoji.premium_on() else PRIMARY,
    ))
    kb.row(btn("♻️ Вернуть все по умолчанию", "pn:emreset", style=DANGER))
    kb.row(InlineKeyboardButton(text="‹ Назад", callback_data="pn:home"))

    preview = "  ".join(emoji.em(key) for key in list(emoji.DEFAULTS)[:12])
    custom_count = sum(1 for key in emoji.DEFAULTS if emoji.custom_id(key))
    await safe_edit(
        call,
        "🎨 <b>Оформление</b>\n\n"
        "<blockquote>Каждый значок в боте можно заменить своим. "
        "Изменения видны клиентам сразу, перезапуск не нужен.</blockquote>\n\n"
        f"Сейчас: {preview}\n\n"
        f"💎 Премиум-эмодзи: <b>{'включены' if emoji.premium_on() else 'выключены'}</b> "
        f"<i>({custom_count} шт. задано)</i>\n\n"
        "<i>Выберите группу</i> 👇",
        kb.as_markup(),
    )
    await call.answer()


async def render_emoji_group(call: CallbackQuery, group: str) -> bool:
    """Показать значки одной группы. False — такой группы нет."""
    items = emoji.GROUPS.get(group)
    if not items:
        return False

    kb = InlineKeyboardBuilder()
    lines = []
    for key, (default, title) in items.items():
        current = emoji.em(key)
        changed = " <i>(изменено)</i>" if current != default else ""
        lines.append(f"{current} — {title}{changed}")
        kb.row(InlineKeyboardButton(
            text=f"{current} {title}", callback_data=f"pn:emset:{key}",
        ))
    kb.row(InlineKeyboardButton(text="‹ Назад", callback_data="pn:look"))

    await safe_edit(
        call,
        f"🎨 <b>{group}</b>\n\n" + "\n".join(lines)
        + "\n\n<i>Нажмите на значок, чтобы заменить.</i>",
        kb.as_markup(),
    )
    return True


@router.callback_query(F.data.startswith("pn:emg:"))
async def cb_emoji_group(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if not await render_emoji_group(call, call.data.split(":", 2)[2]):
        await call.answer("Группа не найдена.", show_alert=True)
        return
    await call.answer()


@router.callback_query(F.data.startswith("pn:emset:"))
async def cb_emoji_set(call: CallbackQuery, state: FSMContext) -> None:
    key = call.data.rsplit(":", 1)[1]
    if key not in emoji.DEFAULTS:
        await call.answer("Такого значка нет.", show_alert=True)
        return
    await state.set_state(Panel.emoji)
    await state.update_data(emoji_key=key)

    group = next(g for g, items in emoji.GROUPS.items() if key in items)
    kb = InlineKeyboardBuilder()
    if emoji.custom_id(key):
        kb.row(btn("🚫 Убрать премиум-эмодзи", f"pn:emcustdel:{key}", style=DANGER))
    kb.row(InlineKeyboardButton(text=f"♻️ Вернуть {emoji.DEFAULTS[key]}",
                                callback_data=f"pn:emdef:{key}"))
    kb.row(InlineKeyboardButton(text="‹ Назад", callback_data=f"pn:emg:{group}"))

    premium_line = ""
    if emoji.custom_id(key):
        state_note = "работает" if emoji.premium_on() else "выключен — включите проверку"
        premium_line = (
            f"├ Премиум-эмодзи: <code>{emoji.custom_id(key)}</code> "
            f"<i>({state_note})</i>\n"
        )

    await safe_edit(
        call,
        f"🎨 <b>{emoji.TITLES[key]}</b>\n\n"
        f"├ Сейчас: {emoji.em(key)}\n"
        f"{premium_line}"
        f"└ По умолчанию: {emoji.DEFAULTS[key]}\n\n"
        "<blockquote>Пришлите новый значок одним сообщением.\n\n"
        "Обычный эмодзи — заменит везде, включая кнопки.\n"
        "<b>Премиум-эмодзи</b> — бот сам возьмёт его ID. В кнопках он "
        "не отображается (Telegram не поддерживает), поэтому там "
        "останется обычный.</blockquote>",
        kb.as_markup(),
    )
    await call.answer()


@router.message(Panel.emoji, F.text)
async def on_emoji_value(
    message: Message, state: FSMContext, conn: aiosqlite.Connection
) -> None:
    data = await state.get_data()
    key = data.get("emoji_key")
    if key not in emoji.DEFAULTS:
        await state.clear()
        await message.answer("Не понял, что менять. Откройте /panel заново.")
        return

    group = next(g for g, items in emoji.GROUPS.items() if key in items)

    # Премиум-эмодзи приходит обычным символом плюс сущность с его ID —
    # владельцу не надо искать ID руками, достаточно прислать сам эмодзи.
    custom = emoji.extract_custom(message)
    if custom is not None:
        emoji_id, fallback = custom
        await runtime.set_value(conn, f"emoji_id_{key}", emoji_id)
        await runtime.set_value(conn, f"emoji_{key}", fallback)
        await state.clear()

        note = (
            "" if emoji.premium_on() else
            "\n\n<blockquote>[[warn]] Премиум-эмодзи пока выключены. "
            "Нажмите «Проверить премиум-эмодзи» в разделе «Оформление» — "
            "бот убедится, что Telegram их принимает, и включит.</blockquote>"
        )
        await message.answer(
            f"✅ <b>{emoji.TITLES[key]}</b> — премиум-эмодзи принят\n\n"
            f"├ ID: <code>{emoji_id}</code>\n"
            f"└ Запасной значок: {fallback}\n\n"
            "<i>Запасной увидят там, где премиум-эмодзи не отображается "
            "(в кнопках и у части клиентов).</i>" + substitute(note),
            reply_markup=back_kb(f"pn:emg:{group}", "‹ К группе"),
        )
        return

    value = (message.text or "").strip()
    if not emoji.is_emoji_like(value):
        await message.answer(
            "❌ Нужен один значок — эмодзи или символ вроде <code>•</code>.\n"
            "Слова и длинный текст не подойдут."
        )
        return

    await runtime.set_value(conn, f"emoji_{key}", value)
    await runtime.reset(conn, f"emoji_id_{key}")   # обычный значок отменяет премиум
    await state.clear()
    await message.answer(
        f"✅ <b>{emoji.TITLES[key]}</b> теперь {value}\n\n"
        "<i>Клиенты увидят изменение сразу.</i>",
        reply_markup=back_kb(f"pn:emg:{group}", "‹ К группе"),
    )


@router.callback_query(F.data.startswith("pn:emdef:"))
async def cb_emoji_default(call: CallbackQuery, conn: aiosqlite.Connection) -> None:
    key = call.data.rsplit(":", 1)[1]
    await runtime.reset(conn, f"emoji_{key}")
    await call.answer(f"Вернул {emoji.DEFAULTS.get(key, '')}")
    group = next((g for g, items in emoji.GROUPS.items() if key in items), None)
    if group:
        await render_emoji_group(call, group)


@router.callback_query(F.data == "pn:emreset")
async def cb_emoji_reset_all(call: CallbackQuery, state: FSMContext) -> None:
    kb = InlineKeyboardBuilder()
    kb.row(btn("♻️ Да, вернуть всё", "pn:emreset2", style=DANGER))
    kb.row(InlineKeyboardButton(text="‹ Отмена", callback_data="pn:look"))
    await safe_edit(
        call,
        "♻️ <b>Вернуть значки по умолчанию?</b>\n\n"
        "<blockquote>Все ваши замены будут сброшены.</blockquote>",
        kb.as_markup(),
    )
    await call.answer()


@router.callback_query(F.data == "pn:emreset2")
async def cb_emoji_reset_confirm(
    call: CallbackQuery, state: FSMContext, conn: aiosqlite.Connection
) -> None:
    for key in emoji.DEFAULTS:
        await runtime.reset(conn, f"emoji_{key}")
    await call.answer("Значки возвращены")
    await cb_look(call, state)


@router.callback_query(F.data.startswith("pn:emcustdel:"))
async def cb_custom_delete(call: CallbackQuery, conn: aiosqlite.Connection) -> None:
    key = call.data.rsplit(":", 1)[1]
    await runtime.reset(conn, f"emoji_id_{key}")
    await call.answer("Премиум-эмодзи убран")
    group = next((g for g, items in emoji.GROUPS.items() if key in items), None)
    if group:
        await render_emoji_group(call, group)


@router.callback_query(F.data == "pn:emtest")
async def cb_emoji_test(
    call: CallbackQuery, state: FSMContext, conn: aiosqlite.Connection, bot: Bot
) -> None:
    """Проверить, принимает ли Telegram премиум-эмодзи от этого бота.

    Без проверки включать нельзя: если у владельца нет Premium, Telegram
    отвергает каждое такое сообщение, и бот перестаёт отвечать вообще.
    """
    if emoji.premium_on():
        await runtime.set_value(conn, "custom_emoji_on", "0")
        await call.answer("Премиум-эмодзи выключены")
        await cb_look(call, state)
        return

    sample = next((key for key in emoji.DEFAULTS if emoji.custom_id(key)), None)
    if sample is None:
        await call.answer(
            "Сначала пришлите хотя бы один премиум-эмодзи — "
            "выберите значок в любой группе.",
            show_alert=True,
        )
        return

    probe = (
        f'<tg-emoji emoji-id="{emoji.custom_id(sample)}">{emoji.em(sample)}</tg-emoji>'
        " проверка премиум-эмодзи"
    )
    try:
        sent = await bot.send_message(call.from_user.id, probe)
    except TelegramAPIError as exc:
        await safe_edit(
            call,
            "💎 <b>Премиум-эмодзи не работают</b>\n\n"
            f"<blockquote>Telegram ответил:\n<code>{exc}</code></blockquote>\n\n"
            "Такое бывает, если у владельца бота нет Telegram Premium. "
            "Обычные значки продолжают работать.",
            back_kb("pn:look", "‹ К оформлению"),
        )
        await call.answer()
        return

    with suppress(TelegramAPIError):
        await bot.delete_message(sent.chat.id, sent.message_id)

    await runtime.set_value(conn, "custom_emoji_on", "1")
    await call.answer("Работает — включил")
    await cb_look(call, state)


# ══════════════════════════════════════════════════════════════ отчёты


def report_kb(active: str = "") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    row = []
    for key, (label, _) in reports.PRESETS.items():
        mark = "• " if key == active else ""
        row.append(btn(mark + label, f"pn:rep:{key}"))
        if len(row) == 3:
            kb.row(*row)
            row = []
    if row:
        kb.row(*row)
    kb.row(btn("📅 Свой период", "pn:repcustom", style=PRIMARY))
    kb.row(btn("‹ Назад", "pn:home"))
    return kb.as_markup()


def format_report(title: str, data: dict, days: list, hint: str = "") -> str:
    """Отчёт за период. Ручные правки показываем отдельной строкой:
    без этого деньги на балансах не сходились бы с пополнениями."""
    """Отчёт за период. Прибыль показываем, только если знаем себестоимость."""
    revenue, cost, profit = data["revenue"], data["cost"], data["profit"]
    margin = round(profit * 100 / cost) if cost else 0

    money_block = (
        f"├ Продано на: <b>{fmt(revenue)}</b>\n"
        f"├ Себестоимость: <b>{fmt(cost)}</b>\n"
        f"└ <b>Прибыль: {fmt(profit)}</b> <i>({margin}%)</i>"
        if cost else
        f"├ Продано на: <b>{fmt(revenue)}</b>\n"
        "└ <i>Прибыль не посчитать — себестоимость по этим заказам "
        "не сохранялась</i>"
    )

    chart = ""
    if len(days) > 1:
        rows = days[-7:]
        peak = max((r[2] for r in rows), default=0) or 1
        bars = []
        for day, done, day_revenue, day_profit in rows:
            filled = round(day_revenue * 10 / peak)
            bars.append(
                f"<code>{day[5:]}</code> {'█' * filled}{'░' * (10 - filled)} "
                f"{fmt(day_revenue)}"
            )
        chart = "\n\n<b>По дням</b>\n" + "\n".join(bars)

    return (
        f"📈 <b>{title}</b>\n"
        f"<code>{texts.LINE}</code>\n\n"
        f"[[money]] <b>Деньги</b>\n{money_block}\n\n"
        f"📦 <b>Заказы</b>\n"
        f"├ Выполнено: <b>{data['done']}</b>\n"
        f"├ Возвращено: <b>{data['refunded']}</b> "
        f"<i>({fmt(data['refunded_sum'])})</i>\n"
        f"├ На разборе: <b>{data['failed']}</b>\n"
        f"├ Звёзд продано: <b>{data['stars']}</b>\n"
        f"└ Premium: <b>{data['premium_months']}</b> мес.\n\n"
        f"[[referral]] <b>Клиенты</b>\n"
        f"├ Новых: <b>{data['new_users']}</b>\n"
        f"├ Покупали: <b>{data['buyers']}</b>\n"
        f"└ Пополнений: <b>{data['deposits']}</b> "
        f"<i>({fmt(data['deposits_sum'])})</i>"
        + (f"\n\n✍️ <b>Правки вручную</b>\n"
           f"├ Начислено: <b>{fmt(data['adjust_added'])}</b>\n"
           f"└ Списано: <b>{fmt(data['adjust_taken'])}</b>"
           if data.get("adjust_added") or data.get("adjust_taken") else "")
        + chart + (f"\n\n<i>{hint}</i>" if hint else "")
    )


async def show_report(
    call: CallbackQuery, conn: aiosqlite.Connection,
    start, end, title: str, active: str = "",
) -> None:
    since, until = reports.bounds(start, end)
    data = await db.report(conn, since, until)
    days = await db.daily_series(conn, since, until, reports.tz_hours())
    await safe_edit(
        call,
        substitute(format_report(title, data, days)),
        report_kb(active),
    )


@router.callback_query(F.data == "pn:rep")
async def cb_report(call: CallbackQuery, state: FSMContext, conn: aiosqlite.Connection) -> None:
    await state.clear()
    start, end, title = reports.preset_range("today")
    await show_report(call, conn, start, end, title, "today")
    await call.answer()


@router.callback_query(F.data.startswith("pn:rep:"))
async def cb_report_preset(
    call: CallbackQuery, state: FSMContext, conn: aiosqlite.Connection
) -> None:
    await state.clear()
    key = call.data.rsplit(":", 1)[1]
    start, end, title = reports.preset_range(key)
    await show_report(call, conn, start, end, title, key)
    await call.answer()


@router.callback_query(F.data == "pn:repcustom")
async def cb_report_custom(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Panel.period)
    await safe_edit(
        call,
        "📅 <b>Свой период</b>\n\n"
        "<blockquote>Пришлите две даты через пробел:\n"
        "<code>01.08 15.08</code>\n\n"
        "Год можно не писать. Одна дата — отчёт за этот день."
        "</blockquote>",
        back_kb("pn:rep", "‹ Назад"),
    )
    await call.answer()


@router.message(Panel.period, F.text)
async def on_report_period(
    message: Message, state: FSMContext, conn: aiosqlite.Connection
) -> None:
    parsed = reports.parse_range(message.text or "")
    if parsed is None:
        await message.answer(
            "❌ Не разобрал даты. Формат: <code>01.08 15.08</code>"
        )
        return

    start, end = parsed
    await state.clear()
    since, until = reports.bounds(start, end)
    data = await db.report(conn, since, until)
    days = await db.daily_series(conn, since, until, reports.tz_hours())
    title = (f"{start.strftime('%d.%m.%Y')} — {end.strftime('%d.%m.%Y')}"
             if start != end else start.strftime("%d.%m.%Y"))
    await message.answer(
        substitute(format_report(title, data, days)),
        reply_markup=report_kb(),
    )


@router.callback_query(F.data == "pn:autoprice")
async def cb_autoprice(
    call: CallbackQuery, conn: aiosqlite.Connection, provider
) -> None:
    """Включить или выключить автоматическое обновление цен."""
    if runtime.auto_price_on():
        await runtime.set_value(conn, "auto_price", "0")
        await call.answer("Автоцены выключены")
        await safe_edit(call, prices_text(), prices_kb())
        return

    # Включаем только после успешного пробного обновления: иначе владелец
    # решит, что цены обновляются, а они молча стоят.
    await safe_edit(call, "📡 Проверяю, получится ли обновить цены…",
                    back_kb("pn:prices"))
    await call.answer()

    result = await pricing.refresh_once(conn, provider)
    if not result["ok"]:
        await safe_edit(
            call,
            f"❌ <b>Автоцены не включить</b>\n\n"
            f"<blockquote>{result['reason']}</blockquote>\n\n"
            "Задайте курс доллара и наценку, потом попробуйте снова.",
            back_kb("pn:prices"),
        )
        return

    await runtime.set_value(conn, "auto_price", "1")
    changed = "\n".join(
        f"├ {name}: {fmt(old)} → <b>{fmt(new)}</b>"
        for name, old, new, _ in result["changed"]
    ) or "├ цены уже верные"
    await safe_edit(
        call,
        "🟢 <b>Автоцены включены</b>\n\n"
        f"{changed}\n\n"
        f"<blockquote>Бот будет спрашивать цену каждые "
        f"{runtime.get_int('auto_price_every', 60)} мин. и держать вашу "
        f"наценку {runtime.margin_percent()}%. О заметных скачках предупредит."
        "</blockquote>",
        prices_kb(),
    )


@router.callback_query(F.data == "pn:dctest")
async def cb_dc_test(call: CallbackQuery) -> None:
    """Показать готовую ссылку на пробную сумму — проверить, что открывается."""
    if not dcpay.is_ready():
        await safe_edit(
            call,
            "🏙 <b>Кнопка оплаты не настроена</b>\n\n"
            "<blockquote>Возьмите свою ссылку вида\n"
            "<code>pay.dc.tj/?a=9762...&amp;c=...&amp;f1=133&amp;s=50</code>\n\n"
            "и впишите из неё номер счёта — это параметр <code>a</code>."
            "</blockquote>",
            back_kb("pn:set:dc_account", "🏙 Вписать счёт"),
        )
        await call.answer()
        return

    reference = dcpay.make_reference()
    link = dcpay.build_link(
        dcpay.account(), 5000,
        dcpay.build_comment(dcpay.comment_prefix(), reference),
        dcpay.service(),
    )
    kb = InlineKeyboardBuilder()
    kb.row(btn("🏙 Открыть (проба на 50 с.)", url=link, style=SUCCESS))
    kb.row(btn("‹ Назад", "pn:pay"))
    await safe_edit(
        call,
        "🏙 <b>Проверка кнопки оплаты</b>\n\n"
        "<blockquote>Нажмите кнопку ниже: должно открыться приложение "
        "со счётом и суммой 50 сомони. Платить не нужно — просто "
        "убедитесь, что данные подставились.</blockquote>\n\n"
        f"Ссылка:\n<code>{link}</code>",
        kb.as_markup(),
    )
    await call.answer()


# ═════════════════════════════════════════════════════════════ клиенты


def user_card(user: db.User, stats: dict, history: list) -> str:
    name = f"@{user.username}" if user.username else (user.first_name or "без имени")
    lines = "\n".join(
        f"├ {'+' if adj.amount > 0 else '−'}{fmt(abs(adj.amount))}"
        + (f" — <i>{adj.reason}</i>" if adj.reason else "")
        for adj in history[:5]
    )
    manual = f"\n\n✍️ <b>Правки баланса</b>\n{lines}" if history else ""

    return (
        f"👤 <b>{name}</b>\n"
        f"<code>{texts.LINE}</code>\n\n"
        f"├ ID: <code>{user.id}</code>\n"
        f"├ С нами с {user.created_at[:10]}\n"
        f"└ Пришёл: <b>{user.source or 'сам'}</b>\n\n"
        f"[[money]] <b>Финансы</b>\n"
        f"├ Баланс: <b>{fmt(user.balance)}</b>\n"
        f"└ Пополнено всего: <b>{fmt(user.total_deposit)}</b>\n\n"
        f"📦 <b>Заказы</b>\n"
        f"├ Всего: <b>{stats['total']}</b>, выполнено: <b>{stats['done']}</b>\n"
        f"└ Звёзд куплено: <b>{stats['stars']}</b>\n\n"
        + (f"[[block]] <b>Заблокирован</b>" if user.is_banned else "")
        + manual
    )


def user_kb(user: db.User) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        btn("➕ Начислить", f"pn:give:{user.id}", style=SUCCESS),
        btn("➖ Списать", f"pn:take:{user.id}", style=DANGER),
    )
    kb.row(btn(
        "✅ Разблокировать" if user.is_banned else "🚫 Заблокировать",
        f"pn:ban:{user.id}",
        style=SUCCESS if user.is_banned else DANGER,
    ))
    kb.row(btn("🔍 Другой клиент", "pn:users"))
    kb.row(btn("‹ В панель", "pn:home"))
    return kb.as_markup()


async def show_user(call: CallbackQuery, conn: aiosqlite.Connection, user_id: int) -> None:
    user = await db.get_user(conn, user_id)
    if user is None:
        await safe_edit(call, "Клиент не найден.", back_kb("pn:users", "🔍 Искать"))
        return
    stats = await db.user_order_stats(conn, user_id)
    history = await db.list_adjustments(conn, user_id=user_id)
    await safe_edit(call, substitute(user_card(user, stats, history)), user_kb(user))


@router.callback_query(F.data == "pn:users")
async def cb_users(call: CallbackQuery, state: FSMContext, conn: aiosqlite.Connection) -> None:
    await state.set_state(Panel.user_search)
    recent = await db.list_adjustments(conn, limit=5)
    tail = ""
    if recent:
        rows = "\n".join(
            f"├ <code>{a.user_id}</code>: "
            f"{'+' if a.amount > 0 else '−'}{fmt(abs(a.amount))}"
            + (f" — <i>{a.reason}</i>" if a.reason else "")
            for a in recent
        )
        tail = f"\n\n✍️ <b>Последние правки</b>\n{rows}"

    await safe_edit(
        call,
        "👥 <b>Клиенты</b>\n\n"
        "<blockquote>Пришлите <b>ID</b> или <b>@username</b> — покажу карточку "
        "с балансом и кнопками начисления и списания.</blockquote>" + tail,
        back_kb("pn:home", "‹ В панель"),
    )
    await call.answer()


@router.message(Panel.user_search, F.text)
async def on_user_search(
    message: Message, state: FSMContext, conn: aiosqlite.Connection
) -> None:
    user = await db.find_user(conn, message.text or "")
    if user is None:
        await message.answer(
            "❌ Такого клиента нет.\n\n"
            "<blockquote>Он появится в базе только после того, как хотя бы "
            "раз напишет боту.</blockquote>"
        )
        return

    await state.clear()
    stats = await db.user_order_stats(conn, user.id)
    history = await db.list_adjustments(conn, user_id=user.id)
    await message.answer(
        substitute(user_card(user, stats, history)), reply_markup=user_kb(user)
    )


@router.callback_query(F.data.startswith(("pn:give:", "pn:take:")))
async def cb_adjust_start(call: CallbackQuery, state: FSMContext, conn: aiosqlite.Connection) -> None:
    kind, user_id = call.data.split(":")[1], int(call.data.rsplit(":", 1)[1])
    user = await db.get_user(conn, user_id)
    if user is None:
        await call.answer("Клиент не найден.", show_alert=True)
        return

    await state.set_state(Panel.adjust)
    await state.update_data(adjust_user=user_id, adjust_kind=kind)

    if kind == "give":
        head = "➕ <b>Начислить на баланс</b>"
        note = "Деньги появятся у клиента сразу, он получит уведомление."
    else:
        head = "➖ <b>Списать с баланса</b>"
        note = ("Списать больше, чем есть, нельзя — баланс не уйдёт в минус.")

    await safe_edit(
        call,
        f"{head}\n\n"
        f"├ Клиент: <code>{user_id}</code>\n"
        f"└ Сейчас на балансе: <b>{fmt(user.balance)}</b>\n\n"
        f"<blockquote>{note}</blockquote>\n\n"
        "Пришлите сумму в сомони. Можно с причиной через пробел:\n"
        "<code>50</code>  или  <code>50 бонус за отзыв</code>",
        back_kb(f"pn:user:{user_id}", "✖️ Отмена"),
    )
    await call.answer()


@router.callback_query(F.data.startswith("pn:user:"))
async def cb_user_card(call: CallbackQuery, state: FSMContext, conn: aiosqlite.Connection) -> None:
    await state.clear()
    await show_user(call, conn, int(call.data.rsplit(":", 1)[1]))
    await call.answer()


@router.message(Panel.adjust, F.text)
async def on_adjust_amount(
    message: Message, state: FSMContext, conn: aiosqlite.Connection, bot: Bot
) -> None:
    data = await state.get_data()
    user_id, kind = data.get("adjust_user"), data.get("adjust_kind")
    if not user_id:
        await state.clear()
        await message.answer("Не понял, кому. Откройте /panel заново.")
        return

    parts = (message.text or "").strip().split(maxsplit=1)
    amount = parse(parts[0]) if parts else None
    reason = parts[1].strip() if len(parts) > 1 else ""

    if amount is None or amount <= 0:
        await message.answer(
            "❌ Введите сумму числом: <code>50</code> или <code>50.50</code>.\n"
            "Причину можно дописать через пробел."
        )
        return

    user = await db.get_user(conn, user_id)
    if user is None:
        await state.clear()
        await message.answer("Клиент пропал из базы.")
        return

    if kind == "give":
        await db.credit(conn, user_id, amount)
        signed = amount
        await delivery.notify(
            bot, user_id,
            substitute(
                f"[[money]] <b>Вам начислено {fmt(amount)}</b>"
                + (f"\n\n<blockquote>{reason}</blockquote>" if reason else "")
            ),
        )
    else:
        if not await db.charge(conn, user_id, amount):
            await message.answer(
                f"❌ Не хватает средств: на балансе <b>{fmt(user.balance)}</b>.\n\n"
                "<blockquote>Баланс не уводится в минус — иначе клиент ушёл бы "
                "в долг, которого он не брал.</blockquote>"
            )
            return
        signed = -amount
        await delivery.notify(
            bot, user_id,
            substitute(
                f"[[refund]] <b>С баланса списано {fmt(amount)}</b>"
                + (f"\n\n<blockquote>{reason}</blockquote>" if reason else "")
            ),
        )

    await db.add_adjustment(
        conn, user_id=user_id, admin_id=message.from_user.id,
        amount=signed, reason=reason,
    )
    await state.clear()

    fresh = await db.get_user(conn, user_id)
    kb = InlineKeyboardBuilder()
    kb.row(btn("👤 Карточка клиента", f"pn:user:{user_id}"))
    kb.row(btn("‹ В панель", "pn:home"))
    await message.answer(
        f"✅ <b>{'Начислено' if kind == 'give' else 'Списано'} {fmt(amount)}</b>\n\n"
        f"├ Клиент: <code>{user_id}</code>\n"
        f"└ Баланс теперь: <b>{fmt(fresh.balance if fresh else 0)}</b>"
        + (f"\n\n<i>Причина: {reason}</i>" if reason else ""),
        reply_markup=kb.as_markup(),
    )


@router.callback_query(F.data.startswith("pn:ban:"))
async def cb_ban_toggle(call: CallbackQuery, conn: aiosqlite.Connection) -> None:
    user_id = int(call.data.rsplit(":", 1)[1])
    user = await db.get_user(conn, user_id)
    if user is None:
        await call.answer("Клиент не найден.", show_alert=True)
        return
    await db.set_banned(conn, user_id, not user.is_banned)
    await call.answer("Разблокирован" if user.is_banned else "Заблокирован")
    await show_user(call, conn, user_id)


# ═════════════════════════════════════════════════════════ Deep Links


def links_text(rows: list[tuple[db.Link, dict]]) -> str:
    if not rows:
        body = (
            "<blockquote>Пока ни одной. Нажмите «Создать ссылку» и придумайте "
            "название — например <code>instagram</code>, <code>reklama1</code> "
            "или <code>partner_1</code>.</blockquote>"
        )
    else:
        body = "\n".join(
            f"├ <code>{link.code}</code> — переходов <b>{stats['hits']}</b>, "
            f"новых <b>{stats['fresh']}</b>"
            for link, stats in rows
        )
    return (
        "🔗 <b>Рекламные ссылки</b>\n"
        f"<code>{texts.LINE}</code>\n\n"
        f"{body}\n\n"
        "<blockquote>Каждой площадке — своя ссылка. Бот сам запомнит, откуда "
        "пришёл клиент, и покажет, какая реклама приносит покупателей.</blockquote>"
    )


def links_kb(rows: list[tuple[db.Link, dict]]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(btn("➕ Создать ссылку", "pn:link:new", style=SUCCESS))
    for link, _ in rows[:20]:
        kb.row(InlineKeyboardButton(
            text=f"🔗 {link.code}", callback_data=f"pn:link:{link.id}",
        ))
    kb.row(InlineKeyboardButton(text="‹ В панель", callback_data="pn:home"))
    return kb.as_markup()


def link_card(link: db.Link, stats: dict, url: str) -> str:
    conversion = ""
    if stats["people"]:
        share = round(stats["buyers"] * 100 / stats["people"])
        conversion = f"\n└ Из перешедших купили: <b>{share}%</b>"

    return (
        f"🔗 <b>{link.code}</b>\n"
        f"<code>{texts.LINE}</code>\n\n"
        f"<code>{url}</code>\n\n"
        "📊 <b>Переходы</b>\n"
        f"├ Всего запусков: <b>{stats['hits']}</b>\n"
        f"├ Уникальных людей: <b>{stats['people']}</b>\n"
        f"└ Новых пользователей: <b>{stats['fresh']}</b>\n\n"
        "[[money]] <b>Отдача</b>\n"
        f"├ Покупателей: <b>{stats['buyers']}</b>\n"
        f"├ Куплено на: <b>{fmt(stats['revenue'])}</b>"
        f"{conversion}\n\n"
        f"📅 Создана {link.created_at[:10]}\n\n"
        "<blockquote>Telegram сообщает боту не о самом клике, а о запуске: "
        "человек открыл ссылку и нажал «Запустить».</blockquote>"
    )


def link_kb(link: db.Link, url: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text="📋 Копировать ссылку", copy_text=CopyTextButton(text=url),
    ))
    kb.row(btn("🗑 Удалить", f"pn:link:del:{link.id}", style=DANGER))
    kb.row(InlineKeyboardButton(text="‹ К ссылкам", callback_data="pn:links"))
    return kb.as_markup()


async def show_links(call: CallbackQuery, conn: aiosqlite.Connection) -> None:
    rows = await db.list_links(conn)
    await safe_edit(call, links_text(rows), links_kb(rows))


async def show_link(call: CallbackQuery, conn: aiosqlite.Connection, link_id: int) -> bool:
    link = await db.get_link(conn, link_id)
    if link is None:
        await call.answer("Ссылка удалена.", show_alert=True)
        await show_links(call, conn)
        return False
    stats = await db.link_stats(conn, link.id)
    url = links.build(await links.bot_username(call.bot), link.code)
    await safe_edit(call, substitute(link_card(link, stats, url)), link_kb(link, url))
    return True


@router.callback_query(F.data == "pn:links")
async def cb_links(call: CallbackQuery, state: FSMContext, conn: aiosqlite.Connection) -> None:
    await state.clear()
    await show_links(call, conn)
    await call.answer()


@router.callback_query(F.data == "pn:link:new")
async def cb_link_new(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Panel.link)
    await safe_edit(
        call,
        "➕ <b>Новая ссылка</b>\n\n"
        "<blockquote>Пришлите название — оно встанет в конец ссылки.\n\n"
        "Например <code>instagram</code>, <code>reklama1</code>, "
        "<code>partner_1</code>.\n\n"
        "Только латиница, цифры, дефис и подчёркивание.</blockquote>",
        back_kb("pn:links", "‹ Отмена"),
    )
    await call.answer()


@router.message(Panel.link, F.text)
async def on_link_name(
    message: Message, state: FSMContext, conn: aiosqlite.Connection
) -> None:
    code = (message.text or "").strip().lstrip("@")
    problem = links.check(code)
    if problem:
        await message.answer(f"❌ {problem}\n\n<i>Попробуйте другое название.</i>")
        return

    link = await db.create_link(conn, code)
    if link is None:
        await message.answer(
            f"❌ Ссылка <code>{code}</code> уже есть.\n\n"
            "<i>Придумайте другое название.</i>"
        )
        return

    await state.clear()
    url = links.build(await links.bot_username(message.bot), code)
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text="📋 Копировать ссылку", copy_text=CopyTextButton(text=url),
    ))
    kb.row(InlineKeyboardButton(text="📊 Статистика", callback_data=f"pn:link:{link.id}"))
    kb.row(InlineKeyboardButton(text="‹ К ссылкам", callback_data="pn:links"))
    await message.answer(
        f"✅ <b>Ссылка готова</b>\n\n"
        f"<code>{url}</code>\n\n"
        "<blockquote>Ставьте её в рекламу. Каждый, кто запустит бота по этой "
        "ссылке, попадёт в её статистику.</blockquote>",
        reply_markup=kb.as_markup(),
    )


@router.callback_query(F.data.startswith("pn:link:del:"))
async def cb_link_delete(call: CallbackQuery, conn: aiosqlite.Connection) -> None:
    """Первое нажатие — предупреждение, второе — удаление."""
    link_id = int(call.data.rsplit(":", 1)[1])
    link = await db.get_link(conn, link_id)
    if link is None:
        await call.answer("Уже удалена.", show_alert=True)
        await show_links(call, conn)
        return

    stats = await db.link_stats(conn, link_id)
    kb = InlineKeyboardBuilder()
    kb.row(btn("🗑 Да, удалить", f"pn:link:kill:{link_id}", style=DANGER))
    kb.row(InlineKeyboardButton(text="‹ Отмена", callback_data=f"pn:link:{link_id}"))
    await safe_edit(
        call,
        f"🗑 <b>Удалить ссылку {link.code}?</b>\n\n"
        f"<blockquote>Пропадёт её статистика: <b>{stats['hits']}</b> переходов "
        f"и <b>{stats['fresh']}</b> новых пользователей. Сами клиенты и их "
        "заказы останутся на месте.</blockquote>",
        kb.as_markup(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("pn:link:kill:"))
async def cb_link_kill(call: CallbackQuery, conn: aiosqlite.Connection) -> None:
    link_id = int(call.data.rsplit(":", 1)[1])
    await db.delete_link(conn, link_id)
    await call.answer("Удалена")
    await show_links(call, conn)


@router.callback_query(F.data.startswith("pn:link:"))
async def cb_link_card(call: CallbackQuery, conn: aiosqlite.Connection) -> None:
    await show_link(call, conn, int(call.data.rsplit(":", 1)[1]))
    await call.answer()
