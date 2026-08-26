"""Админ-панель: одна точка входа, всё остальное — кнопками.

Открывается командой /panel (или /admin). Разделы:
  • Рассылка — любой тип сообщения + кнопки-ссылки
  • Цены — себестоимость, наценка, цена продажи, тарифы Premium
  • Реквизиты — карта, владелец, банк, город, примечание
  • Заявки, тикеты, пользователи, промокоды, статистика
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
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import db, emoji, runtime, texts
from app.config import settings
from app.money import fmt, parse
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
    kb.row(InlineKeyboardButton(text="📣 Рассылка", callback_data="pn:cast"))
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
        InlineKeyboardButton(text="📊 Статистика", callback_data="pn:stats"),
        InlineKeyboardButton(text="🔀 Разделы", callback_data="pn:toggles"),
    )
    kb.row(
        InlineKeyboardButton(text="💼 Кошелёк", callback_data="pn:wallet"),
        InlineKeyboardButton(text="🔌 Проверить связь", callback_data="pn:fragment"),
    )
    kb.row(
        InlineKeyboardButton(text="🎨 Оформление", callback_data="pn:look"),
        InlineKeyboardButton(text="📝 Объявление", callback_data="pn:notice"),
    )
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
        f"⭐️ Цена звезды: <b>{fmt(runtime.star_price())}</b>"
        + (f" · прибыль <b>{fmt(runtime.profit_per_star())}</b>"
           if runtime.star_cost() > 0 else " · себестоимость не задана")
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
        InlineKeyboardButton(text="💲 Себестоимость", callback_data="pn:set:star_cost_diram"),
        InlineKeyboardButton(text="📈 Наценка %", callback_data="pn:set:margin_percent"),
    )
    kb.row(InlineKeyboardButton(text="🏷 Цена продажи вручную",
                                callback_data="pn:set:star_price_diram"))
    kb.row(InlineKeyboardButton(text="📡 Узнать себестоимость", callback_data="pn:cost"))
    kb.row(InlineKeyboardButton(text="🧮 Применить наценку", callback_data="pn:recalc"))
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
    cost, price = runtime.star_cost(), runtime.star_price()
    margin = runtime.margin_percent()

    if cost > 0:
        profit = price - cost
        real_margin = round((price - cost) / cost * 100) if cost else 0
        economics = (
            f"├ Себестоимость: <b>{fmt(cost)}</b>\n"
            f"├ Наценка задана: <b>{margin}%</b>\n"
            f"├ Цена продажи: <b>{fmt(price)}</b>\n"
            f"├ Фактическая наценка: <b>{real_margin}%</b>\n"
            f"└ Прибыль с 1 звезды: <b>{fmt(profit)}</b>\n\n"
            f"💡 С заказа в 1000 звёзд заработок: <b>{fmt(profit * 1000)}</b>"
        )
        if profit < 0:
            economics += "\n\n❗️ <b>Продаёте ниже себестоимости — это убыток.</b>"
    else:
        economics = (
            f"├ Цена продажи: <b>{fmt(price)}</b>\n"
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
        f"📏 Заказ: от <b>{runtime.min_stars()}</b> до <b>{runtime.max_stars()}</b> звёзд\n"
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
    if runtime.star_cost() <= 0:
        await call.answer("Сначала задайте себестоимость.", show_alert=True)
        return
    new_price = runtime.price_from_margin()
    await runtime.set_value(conn, "star_price_diram", str(new_price))
    await call.answer(f"Цена продажи: {fmt(new_price)}")
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
    kb.row(InlineKeyboardButton(text="👁 Как видит клиент", callback_data="pn:preview_pay"))
    kb.row(InlineKeyboardButton(text="‹ Назад", callback_data="pn:home"))
    return kb.as_markup()


def pay_text() -> str:
    def show(key: str) -> str:
        value = runtime.get(key)
        return f"<b>{value}</b>" if value else "<i>не задано</i>"

    warning = ""
    if not runtime.get("pay_card_number"):
        warning = "\n❗️ <b>Без номера карты клиенты не смогут пополнить баланс.</b>\n"
    return (
        "💳 <b>Реквизиты для приёма оплаты</b>\n"
        f"{warning}\n"
        f"├ Карта: {show('pay_card_number')}\n"
        f"├ Владелец: {show('pay_card_holder')}\n"
        f"├ Банк: {show('pay_card_bank')}\n"
        f"├ Город: {show('pay_city')}\n"
        f"└ Примечание: {show('pay_extra')}"
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
    "star_cost_diram": ("💲 Себестоимость звезды",
                        "Сколько ОДНА звезда стоит вам на Fragment, в сомони.\n"
                        "Например <code>0.18</code>:", "money"),
    "star_price_diram": ("🏷 Цена продажи звезды",
                         "За сколько продаёте ОДНУ звезду, в сомони.\n"
                         "Например <code>0.25</code>:", "money"),
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
    "star_cost_diram": "pn:prices", "star_price_diram": "pn:prices",
    "margin_percent": "pn:prices", "min_stars": "pn:prices",
    "usd_rate_diram": "pn:prices",
    "max_stars": "pn:prices", "min_deposit_diram": "pn:prices",
    "referral_percent": "pn:prices", "support_notice": "pn:home",
    "autostop_after": "pn:wallet",
})


def current_display(key: str) -> str:
    kind = FIELDS[key][2]
    raw = runtime.get(key)
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
    if kind == "money":
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
        f"{'✅' if runtime.get_bool('deposit_enabled') else '🚫'} Пополнение баланса"
    )


def toggles_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for key, label in (
        ("stars_enabled", "звёзды"),
        ("premium_enabled", "Premium"),
        ("deposit_enabled", "пополнение"),
    ):
        state = runtime.get_bool(key)
        kb.row(InlineKeyboardButton(
            text=("🚫 Выключить " if state else "✅ Включить ") + label,
            callback_data=f"pn:toggle:{key}",
        ))
    kb.row(InlineKeyboardButton(text="‹ Назад", callback_data="pn:home"))
    return kb.as_markup()


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


@router.callback_query(F.data == "pn:promos")
async def cb_promos(call: CallbackQuery, state: FSMContext, conn: aiosqlite.Connection) -> None:
    await state.clear()
    promos = await db.list_promos(conn, limit=15)
    if promos:
        lines = "\n".join(
            f"<code>{p['code']}</code> — {fmt(p['amount'])} · "
            f"использован {p['used_count']}/{p['max_uses']}"
            for p in promos
        )
        body = f"🎟 <b>Промокоды</b>\n\n{lines}"
    else:
        body = "🎟 <b>Промокоды</b>\n\nПока ни одного."
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="➕ Создать промокод", callback_data="pn:promo_new"))
    kb.row(InlineKeyboardButton(text="‹ Назад", callback_data="pn:home"))
    await safe_edit(call, body, kb.as_markup())
    await call.answer()


@router.callback_query(F.data == "pn:promo_new")
async def cb_promo_new(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(PromoNew.data)
    await safe_edit(
        call,
        "🎟 <b>Новый промокод</b>\n\n"
        "Пришлите одной строкой: <b>код сумма лимит</b>\n\n"
        "Например:\n<code>SALE10 10 100</code>\n"
        "— код SALE10 на 10 сомони, 100 активаций.",
        back_kb("pn:promos", "❌ Отмена"),
    )
    await call.answer()


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
        kb.row(InlineKeyboardButton(text="🔍 Найти адреса API", callback_data="pn:probe"))
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
    kb.row(InlineKeyboardButton(text="✅ Я пополнил кошелёк", callback_data="pn:topup"))
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
    cost = int((estimate.usd_per_unit * rate).to_integral_value(rounding="ROUND_HALF_UP"))
    margin = runtime.margin_percent()
    suggested = round(cost * (100 + margin) / 100) if margin else cost

    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text=f"✅ Записать {fmt(cost)} как себестоимость",
        callback_data=f"pn:cost_save:{cost}",
    ))
    kb.row(InlineKeyboardButton(text="📈 Изменить наценку", callback_data="pn:set:margin_percent"))
    kb.row(InlineKeyboardButton(text="💱 Изменить курс", callback_data="pn:set:usd_rate_diram"))
    kb.row(InlineKeyboardButton(text="‹ Назад", callback_data="pn:prices"))

    margin_line = (
        f"\n📈 С вашей наценкой <b>{margin}%</b> продавать по "
        f"<b>{fmt(suggested)}</b> за звезду\n"
        f"   (прибыль <b>{fmt(suggested - cost)}</b> со звезды, "
        f"<b>{fmt((suggested - cost) * 1000)}</b> с 1000)"
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
        f"└ одна звезда обходится в <b>{fmt(cost)}</b>\n"
        f"{margin_line}\n\n"
        "⚠️ Курс TON меняется — проверяйте себестоимость раз в несколько дней.",
        kb.as_markup(),
    )


@router.callback_query(F.data.startswith("pn:cost_save:"))
async def cb_cost_save(call: CallbackQuery, conn: aiosqlite.Connection) -> None:
    cost = int(call.data.rsplit(":", 1)[1])
    await runtime.set_value(conn, "star_cost_diram", str(cost))

    margin = runtime.margin_percent()
    if margin > 0:
        await runtime.set_value(conn, "star_price_diram", str(runtime.price_from_margin()))
        await call.answer(f"Себестоимость {fmt(cost)}, цена продажи пересчитана")
    else:
        await call.answer(f"Себестоимость {fmt(cost)} записана")
    await safe_edit(call, prices_text(), prices_kb())


# ============================================================= оформление


@router.callback_query(F.data == "pn:look")
async def cb_look(call: CallbackQuery, state: FSMContext) -> None:
    """Список групп значков. Меняются по одному, видно сразу."""
    await state.clear()
    kb = InlineKeyboardBuilder()
    for group in emoji.GROUPS:
        kb.row(InlineKeyboardButton(text=group, callback_data=f"pn:emg:{group}"))
    kb.row(InlineKeyboardButton(text="♻️ Вернуть все по умолчанию",
                                callback_data="pn:emreset"))
    kb.row(InlineKeyboardButton(text="‹ Назад", callback_data="pn:home"))

    preview = "  ".join(emoji.em(key) for key in list(emoji.DEFAULTS)[:12])
    await safe_edit(
        call,
        "🎨 <b>Оформление</b>\n\n"
        "<blockquote>Каждый значок в боте можно заменить своим. "
        "Изменения видны клиентам сразу, перезапуск не нужен.</blockquote>\n\n"
        f"Сейчас: {preview}\n\n"
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
    kb.row(InlineKeyboardButton(text=f"♻️ Вернуть {emoji.DEFAULTS[key]}",
                                callback_data=f"pn:emdef:{key}"))
    kb.row(InlineKeyboardButton(text="‹ Назад", callback_data=f"pn:emg:{group}"))

    await safe_edit(
        call,
        f"🎨 <b>{emoji.TITLES[key]}</b>\n\n"
        f"├ Сейчас: {emoji.em(key)}\n"
        f"└ По умолчанию: {emoji.DEFAULTS[key]}\n\n"
        "<blockquote>Пришлите новый значок одним сообщением — "
        "любой эмодзи или символ.</blockquote>",
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

    value = (message.text or "").strip()
    if not emoji.is_emoji_like(value):
        await message.answer(
            "❌ Нужен один значок — эмодзи или символ вроде <code>•</code>.\n"
            "Слова и длинный текст не подойдут."
        )
        return

    await runtime.set_value(conn, f"emoji_{key}", value)
    await state.clear()
    group = next(g for g, items in emoji.GROUPS.items() if key in items)
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
    kb.row(InlineKeyboardButton(text="♻️ Да, вернуть всё", callback_data="pn:emreset2"))
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
