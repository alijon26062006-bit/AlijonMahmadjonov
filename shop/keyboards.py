"""Тугмаҳо. Ҳама inline — тарҳбандӣ мисли намунаи фиристодашуда."""

from __future__ import annotations

from typing import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from . import catalog, style, texts

# ── калидҳои callback ─────────────────────────────────────────────────
CB_HOME = "m:home"
CB_TG_MENU = "m:tg"
CB_SUPPORT = "m:support"
CB_TOP = "m:top"
CB_MY_ORDERS = "m:orders"
CB_CAT = "c:"          # c:<category>
CB_PRODUCT = "p:"      # p:<code>
CB_BUY_OK = "buy:ok"
CB_ID_OK = "id:ok"
CB_ID_NO = "id:no"
CB_CANCEL = "x:cancel"
CB_TOPUP = "t:menu"
CB_TOPUP_SUM = "t:s:"  # t:s:<diram>
CB_TOPUP_OTHER = "t:other"
CB_TOPUP_PAID = "t:paid:"  # t:paid:<id>


def _btn(text: str, data: str, color: str | None = None) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=style.decorate(text, color),
        callback_data=data,
        style=style.pick(color),
    )


def _url(text: str, link: str, color: str | None = None) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=style.decorate(text, color), url=link, style=style.pick(color)
    )


def main_menu(*, is_admin: bool = False, reviews_url: str = "") -> InlineKeyboardMarkup:
    """Менюи асосӣ — ҳамон тарҳбандии намуна."""
    rows: list[list[InlineKeyboardButton]] = [
        [_btn(texts.BTN_TELEGRAM, CB_TG_MENU, style.PRIMARY)],
        [_btn(texts.BTN_FF_CIS, CB_CAT + catalog.CAT_FF_CIS, style.PRIMARY)],
        [_btn(texts.BTN_FF_ID, CB_CAT + catalog.CAT_FF_ID, style.PRIMARY)],
        [_btn(texts.BTN_PUBG, CB_CAT + catalog.CAT_PUBG, style.PRIMARY)],
        [_btn(texts.BTN_TOPUP, CB_TOPUP, style.SUCCESS)],
        [_btn(texts.BTN_SUPPORT, CB_SUPPORT), _btn(texts.BTN_TOP, CB_TOP)],
        [_btn(texts.BTN_MY_ORDERS, CB_MY_ORDERS)],
    ]
    if reviews_url:
        rows.append([_url(texts.BTN_REVIEWS, reviews_url)])
    if is_admin:
        rows.append([_btn(texts.BTN_ADMIN, "a:home", style.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def telegram_menu() -> InlineKeyboardMarkup:
    """Қадами дуюм: Stars ё Premium."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(texts.BTN_STARS, CB_CAT + catalog.CAT_STARS, style.PRIMARY)],
            [_btn(texts.BTN_PREMIUM, CB_CAT + catalog.CAT_PREMIUM, style.PRIMARY)],
            [_btn(texts.BTN_HOME, CB_HOME)],
        ]
    )


def products(rows: Sequence, category: str, *, currency: str = texts.CURRENCY) -> InlineKeyboardMarkup:
    """Рӯйхати молҳо: ду дар як сатр, агар номҳо кӯтоҳ бошанд."""
    buttons: list[list[InlineKeyboardButton]] = []
    line: list[InlineKeyboardButton] = []
    two_columns = len(rows) > 6
    for row in rows:
        label = f"{row['title']} — {texts.money(row['price'], currency)}"
        line.append(_btn(label, CB_PRODUCT + row["code"]))
        if not two_columns or len(line) == 2:
            buttons.append(line)
            line = []
    if line:
        buttons.append(line)
    back = CB_TG_MENU if category in (catalog.CAT_STARS, catalog.CAT_PREMIUM) else CB_HOME
    buttons.append([_btn(texts.BTN_BACK, back), _btn(texts.BTN_HOME, CB_HOME)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cancel_only() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            _btn(texts.BTN_CANCEL, CB_CANCEL, style.DANGER),
            _btn(texts.BTN_HOME, CB_HOME),
        ]]
    )


def confirm_target() -> InlineKeyboardMarkup:
    """Панели тафтиши аккаунт."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(texts.BTN_YES_MINE, CB_ID_OK, style.SUCCESS)],
            [_btn(texts.BTN_NO_WRONG, CB_ID_NO)],
            [_btn(texts.BTN_CANCEL, CB_CANCEL, style.DANGER)],
        ]
    )


def confirm_order() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(texts.BTN_PAY, CB_BUY_OK, style.SUCCESS)],
            [_btn(texts.BTN_CANCEL, CB_CANCEL, style.DANGER)],
        ]
    )


def need_money() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(texts.BTN_TOPUP, CB_TOPUP, style.SUCCESS)],
            [_btn(texts.BTN_HOME, CB_HOME)],
        ]
    )


def topup_menu(presets: Sequence[int], *, currency: str = texts.CURRENCY) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    line: list[InlineKeyboardButton] = []
    for value in presets:
        line.append(_btn(texts.money(value, currency), CB_TOPUP_SUM + str(value)))
        if len(line) == 2:
            buttons.append(line)
            line = []
    if line:
        buttons.append(line)
    buttons.append([_btn(texts.BTN_OTHER_SUM, CB_TOPUP_OTHER, style.PRIMARY)])
    buttons.append([_btn(texts.BTN_HOME, CB_HOME)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def payment(
    topup_id: int, link: str | None, alif: str | None = None
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    pay_row: list[InlineKeyboardButton] = []
    if link:
        pay_row.append(_url(texts.BTN_OPEN_LINK, link, style.PRIMARY))
    if alif:
        pay_row.append(_url(texts.BTN_OPEN_ALIF, alif, style.PRIMARY))
    if pay_row:
        rows.append(pay_row)
    rows.append([_btn(texts.BTN_PAID, f"{CB_TOPUP_PAID}{topup_id}", style.SUCCESS)])
    rows.append([_btn(texts.BTN_CANCEL, CB_CANCEL, style.DANGER)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_home() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(texts.BTN_HOME, CB_HOME)]])


def support(username: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if username:
        rows.append([_url("✍️ Навиштан", f"https://t.me/{username}", style.PRIMARY)])
    rows.append([_btn(texts.BTN_HOME, CB_HOME)])
    return InlineKeyboardMarkup(inline_keyboard=rows)



# ── Панели админ ──────────────────────────────────────────────────────
def admin_home() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(texts.ADM_BTN_STATS, "a:stats"), _btn(texts.ADM_BTN_FIND, "a:find")],
            [_btn(texts.ADM_BTN_ORDERS, "a:orders"), _btn(texts.ADM_BTN_TOPUPS, "a:topups")],
            [_btn(texts.ADM_BTN_PRICES, "a:prices"), _btn(texts.ADM_BTN_BROADCAST, "a:bc")],
            [_btn(texts.ADM_BTN_SUPPLIER, "a:supplier")],
            [_btn(texts.BTN_HOME, CB_HOME)],
        ]
    )


def admin_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(texts.BTN_BACK, "a:home")]])


def admin_user(user) -> InlineKeyboardMarkup:
    block = (
        _btn(texts.ADM_BTN_UNBLOCK, f"a:unblock:{user.id}", style.SUCCESS)
        if user.is_blocked
        else _btn(texts.ADM_BTN_BLOCK, f"a:block:{user.id}", style.DANGER)
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _btn(texts.ADM_BTN_PLUS, f"a:plus:{user.id}", style.SUCCESS),
                _btn(texts.ADM_BTN_MINUS, f"a:minus:{user.id}", style.DANGER),
            ],
            [block],
            [_btn(texts.ADM_BTN_FIND, "a:find"), _btn(texts.BTN_BACK, "a:home")],
        ]
    )


def admin_order(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _btn(texts.ADM_BTN_DONE, f"a:odone:{order_id}", style.SUCCESS),
                _btn(texts.ADM_BTN_REJECT, f"a:orej:{order_id}", style.DANGER),
            ],
            [_btn(texts.BTN_BACK, "a:home")],
        ]
    )


def admin_topup(topup_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _btn(texts.ADM_BTN_CONFIRM_PAY, f"a:tok:{topup_id}", style.SUCCESS),
                _btn(texts.ADM_BTN_REJECT, f"a:trej:{topup_id}", style.DANGER),
            ],
            [_btn(texts.BTN_BACK, "a:home")],
        ]
    )


def admin_price_categories() -> InlineKeyboardMarkup:
    rows = [
        [_btn(f"{c.icon} {c.title}", f"a:pcat:{c.code}")]
        for c in catalog.CATEGORY_INFO.values()
    ]
    rows.append([_btn(texts.BTN_BACK, "a:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_price_list(rows: Sequence, *, currency: str = texts.CURRENCY) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    line: list[InlineKeyboardButton] = []
    for row in rows:
        mark = "" if row["active"] else "🚫 "
        line.append(
            _btn(f"{mark}{row['title']} — {texts.money(row['price'], currency)}",
                 f"a:price:{row['code']}")
        )
        if len(line) == 2:
            buttons.append(line)
            line = []
    if line:
        buttons.append(line)
    buttons.append([_btn(texts.BTN_BACK, "a:prices")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_price_item(code: str, active: bool) -> InlineKeyboardMarkup:
    toggle = "Хомӯш кардан" if active else "Фаъол кардан"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("💲 Иваз кардани нарх", f"a:setprice:{code}", style.PRIMARY)],
            [_btn(toggle, f"a:toggle:{code}", style.DANGER if active else style.SUCCESS)],
            [_btn(texts.BTN_BACK, "a:prices")],
        ]
    )
