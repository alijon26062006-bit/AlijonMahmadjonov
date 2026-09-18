"""Тугмаҳо. Ҳама inline — тарҳбандӣ мисли намунаи фиристодашуда."""

from __future__ import annotations

from typing import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from . import catalog, db, style, texts

# ── калидҳои callback ─────────────────────────────────────────────────
CB_HOME = "m:home"
CB_TG_MENU = "m:tg"
CB_SUPPORT = "m:support"
CB_TOP = "m:top"
CB_MY_ORDERS = "m:orders"
CB_BALANCE = "m:balance"
CB_CAT = "c:"          # c:<category>
CB_GROUP = "g:"        # g:<group_code>
CB_PRODUCT = "p:"      # p:<code>
CB_BUY_OK = "buy:ok"
CB_ID_OK = "id:ok"
CB_ID_NO = "id:no"
CB_CANCEL = "x:cancel"
CB_TOPUP = "t:menu"
CB_TOPUP_SUM = "t:s:"  # t:s:<diram>
CB_TOPUP_OTHER = "t:other"
CB_TOPUP_PAID = "t:paid:"  # t:paid:<id>
CB_CHECK_SUB = "sub:check"
CB_REVIEW = "rev:new"


def _btn(text: str, data: str, color: str | None = None) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=text,
        callback_data=data,
        style=style.pick(color),
    )


def _url(text: str, link: str, color: str | None = None) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=text, url=link, style=style.pick(color)
    )


def main_menu(*, is_admin: bool = False, reviews_url: str = "") -> InlineKeyboardMarkup:
    """Менюи асосӣ — ҳамон тарҳбандии намуна."""
    rows: list[list[InlineKeyboardButton]] = [
        [_btn(texts.BTN_TELEGRAM, CB_TG_MENU, style.PRIMARY)],
        [_btn(texts.BTN_FF_CIS, CB_CAT + catalog.CAT_FF_CIS, style.PRIMARY)],
        [_btn(texts.BTN_FF_ID, CB_CAT + catalog.CAT_FF_ID, style.PRIMARY)],
        [_btn(texts.BTN_PUBG, CB_CAT + catalog.CAT_PUBG, style.PRIMARY)],
        [_btn(texts.BTN_TOPUP, CB_TOPUP, style.SUCCESS)],
        [
            _btn(texts.BTN_SUPPORT, CB_SUPPORT, style.PRIMARY),
            _btn(texts.BTN_TOP, CB_TOP, style.PRIMARY),
        ],
        [
            _btn(texts.BTN_BALANCE, CB_BALANCE, style.SUCCESS),
            _btn(texts.BTN_MY_ORDERS, CB_MY_ORDERS, style.PRIMARY),
        ],
    ]
    if reviews_url:
        rows.append([_url(texts.BTN_REVIEWS, reviews_url, style.PRIMARY)])
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


def groups(rows: Sequence, category: str) -> InlineKeyboardMarkup:
    """Зербахшҳо: масалан «Алмосҳо» ва «Ваучерҳо»."""
    buttons = [
        [_btn(row["title"], CB_GROUP + row["code"], style.PRIMARY)] for row in rows
    ]
    back = CB_TG_MENU if category in (catalog.CAT_STARS, catalog.CAT_PREMIUM) else CB_HOME
    buttons.append([_btn(texts.BTN_BACK, back), _btn(texts.BTN_HOME, CB_HOME)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def products(
    rows: Sequence,
    category: str,
    *,
    currency: str = texts.CURRENCY,
    partner: bool = False,
    back_to: str | None = None,
) -> InlineKeyboardMarkup:
    """Рӯйхати молҳо — ҳар мол дар сатри худ, то ном ва нарх пурра дида шаванд."""
    buttons: list[list[InlineKeyboardButton]] = []
    for row in rows:
        label = f"{row['title']} — {texts.money(db.price_of(row, partner), currency)}"
        buttons.append([_btn(label, CB_PRODUCT + row["code"], style.PRIMARY)])
    if back_to is None:
        back_to = (
            CB_TG_MENU
            if category in (catalog.CAT_STARS, catalog.CAT_PREMIUM)
            else CB_HOME
        )
    buttons.append([_btn(texts.BTN_BACK, back_to), _btn(texts.BTN_HOME, CB_HOME)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def subscribe(rows: Sequence) -> InlineKeyboardMarkup:
    """Рӯйхати каналҳо + тугмаи санҷиш."""
    from .subscription import channel_link

    buttons: list[list[InlineKeyboardButton]] = []
    for row in rows:
        link = channel_link(row)
        name = row["title"] or row["chat_id"]
        if link:
            buttons.append([_url(f"📢 {name}", link, style.PRIMARY)])
    buttons.append([_btn(texts.BTN_CHECK_SUB, CB_CHECK_SUB, style.SUCCESS)])
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
            [_btn(texts.BTN_NO_WRONG, CB_ID_NO, style.PRIMARY)],
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
        line.append(
            _btn(texts.money(value, currency), CB_TOPUP_SUM + str(value), style.SUCCESS)
        )
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


def review_invite() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(texts.BTN_WRITE_REVIEW, CB_REVIEW, style.SUCCESS)],
            [_btn(texts.BTN_SKIP, CB_HOME)],
        ]
    )


def admin_review(review_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _btn("✅ Нашр кардан", f"a:revok:{review_id}", style.SUCCESS),
                _btn("❌ Рад кардан", f"a:revno:{review_id}", style.DANGER),
            ]
        ]
    )


def back_home() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(texts.BTN_HOME, CB_HOME)]])


def support(username: str, whatsapp: str = "") -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if username:
        rows.append([_url("✈️ Telegram", f"https://t.me/{username}", style.PRIMARY)])
    if whatsapp:
        rows.append([_url("🟢 WhatsApp", f"https://wa.me/{whatsapp}", style.SUCCESS)])
    rows.append([_btn(texts.BTN_HOME, CB_HOME)])
    return InlineKeyboardMarkup(inline_keyboard=rows)



# ── Панели админ ──────────────────────────────────────────────────────
def admin_home() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _btn(texts.ADM_BTN_STATS, "a:stats", style.PRIMARY),
                _btn(texts.ADM_BTN_FIND, "a:find", style.PRIMARY),
            ],
            [
                _btn(texts.ADM_BTN_ORDERS, "a:orders", style.PRIMARY),
                _btn(texts.ADM_BTN_TOPUPS, "a:topups", style.PRIMARY),
            ],
            [
                _btn(texts.ADM_BTN_PRICES, "a:prices", style.PRIMARY),
                _btn(texts.ADM_BTN_BROADCAST, "a:bc", style.PRIMARY),
            ],
            [
                _btn(texts.ADM_BTN_PARTNERS, "a:partners", style.PRIMARY),
                _btn(texts.ADM_BTN_USERS, "a:users", style.PRIMARY),
            ],
            [
                _btn(texts.ADM_BTN_SETTINGS, "a:settings", style.PRIMARY),
                _btn(texts.ADM_BTN_SUPPLIER, "a:supplier", style.PRIMARY),
            ],
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
            [
                _btn(texts.ADM_BTN_FIND, "a:find", style.PRIMARY),
                _btn(texts.BTN_BACK, "a:home"),
            ],
        ]
    )


def admin_partners(rows: Sequence) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = [
        [_btn(texts.ADM_BTN_ADD_PARTNER, "a:padd", style.SUCCESS)]
    ]
    for row in rows:
        name = row["first_name"] or (f"@{row['username']}" if row["username"] else row["user_id"])
        buttons.append(
            [_btn(f"🗑 {name}", f"a:pdel:{row['user_id']}", style.DANGER)]
        )
    buttons.append([_btn(texts.BTN_BACK, "a:home")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


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


def admin_settings() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(texts.ADM_BTN_REQUISITES, "a:req", style.SUCCESS)],
            [_btn(texts.ADM_BTN_CHANNELS, "a:channels", style.PRIMARY)],
            [_btn(texts.ADM_BTN_REVIEW_CH, "a:revch", style.PRIMARY)],
            [_btn(texts.ADM_BTN_WHATSAPP, "a:wa", style.PRIMARY)],
            [_btn(texts.ADM_BTN_RATE, "a:rate", style.PRIMARY)],
            [_btn(texts.ADM_BTN_GROUPS, "a:groups", style.PRIMARY)],
            [_btn(texts.BTN_BACK, "a:home")],
        ]
    )


def admin_requisites(req) -> InlineKeyboardMarkup:
    dc_toggle = "🚫 Душанбе Ситиро хомӯш" if req.dc_enabled else "✅ Душанбе Ситиро фаъол"
    alif_toggle = "🚫 Alif-ро хомӯш" if req.alif_enabled else "✅ Alif-ро фаъол"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("💳 Рақами корт", "a:card", style.PRIMARY)],
            [_btn("👤 Номи соҳиби корт", "a:holder", style.PRIMARY)],
            [_btn(dc_toggle, "a:dctoggle", style.DANGER if req.dc_enabled else style.SUCCESS)],
            [_btn("🔢 Ҳисоби Alif Mobi", "a:alif", style.PRIMARY)],
            [_btn(alif_toggle, "a:aliftoggle", style.DANGER if req.alif_enabled else style.SUCCESS)],
            [_btn(texts.BTN_BACK, "a:settings")],
        ]
    )


def admin_channels(rows: Sequence) -> InlineKeyboardMarkup:
    buttons = [[_btn("➕ Канали нав", "a:chadd", style.SUCCESS)]]
    for row in rows:
        name = row["title"] or row["chat_id"]
        buttons.append([_btn(f"🗑 {name}", f"a:chdel:{row['id']}", style.DANGER)])
    buttons.append([_btn(texts.BTN_BACK, "a:settings")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_groups(rows: Sequence) -> InlineKeyboardMarkup:
    buttons = [
        [_btn(f"{row['title']}  ✏️", f"a:gname:{row['code']}", style.PRIMARY)]
        for row in rows
    ]
    buttons.append([_btn(texts.BTN_BACK, "a:settings")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_group_categories() -> InlineKeyboardMarkup:
    rows = [
        [_btn(f"{c.icon} {c.title}", f"a:gcat:{c.code}", style.PRIMARY)]
        for c in catalog.CATEGORY_INFO.values()
    ]
    rows.append([_btn(texts.BTN_BACK, "a:settings")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_bc_confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("📤 Фиристодан", "a:bcgo", style.SUCCESS)],
            [_btn(texts.BTN_CANCEL, "a:home", style.DANGER)],
        ]
    )


def admin_price_categories() -> InlineKeyboardMarkup:
    rows = [
        [_btn(f"{c.icon} {c.title}", f"a:pcat:{c.code}", style.PRIMARY)]
        for c in catalog.CATEGORY_INFO.values()
    ]
    rows.append([_btn(texts.ADM_BTN_COSTS, "a:costs", style.SUCCESS)])
    rows.append([_btn(texts.BTN_BACK, "a:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_price_list(
    rows: Sequence, *, currency: str = texts.CURRENCY, rate: float = 11.0
) -> InlineKeyboardMarkup:
    """Рӯйхати нархҳо. Моле, ки бо зарар фурӯхта мешавад, фавран нишон дода мешавад."""
    buttons: list[list[InlineKeyboardButton]] = []
    for row in rows:
        cost = row["cost"] if "cost" in row.keys() else None
        losing = bool(cost) and row["price"] < round(cost / 1000 * rate * 100)
        if not row["active"]:
            mark, color = "🚫 ", style.DANGER
        elif losing:
            mark, color = "🔴 ", style.DANGER   # зарар
        else:
            mark, color = "", style.PRIMARY
        buttons.append([
            _btn(
                f"{mark}{row['title']} — {texts.money(row['price'], currency)}",
                f"a:price:{row['code']}",
                color,
            )
        ])
    buttons.append([_btn(texts.BTN_BACK, "a:prices")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_price_item(
    code: str, active: bool, has_partner_price: bool = False
) -> InlineKeyboardMarkup:
    toggle = "🚫 Хомӯш кардан" if active else "✅ Фаъол кардан"
    rows = [
        [_btn("💲 Нархи оддӣ", f"a:setprice:{code}", style.PRIMARY)],
        [_btn(texts.ADM_BTN_PARTNER_PRICE, f"a:setpp:{code}", style.PRIMARY)],
    ]
    if has_partner_price:
        rows.append(
            [_btn(texts.ADM_BTN_PARTNER_OFF, f"a:delpp:{code}", style.DANGER)]
        )
    rows.append([_btn(toggle, f"a:toggle:{code}", style.DANGER if active else style.SUCCESS)])
    rows.append([_btn(texts.BTN_BACK, "a:prices")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
