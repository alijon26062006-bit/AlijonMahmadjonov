"""Ҳамаи матнҳои бот — бо забони тоҷикӣ. Дар як ҷо, то тағйир додан осон бошад."""

from __future__ import annotations

from datetime import datetime
from html import escape

from . import catalog
from .db import (
    ORDER_DONE,
    ORDER_NEW,
    ORDER_REJECTED,
    ORDER_SENT,
    TOPUP_PAID,
    TOPUP_REJECTED,
    TOPUP_WAITING,
)

CURRENCY = "с."


def money(diram: int, currency: str = CURRENCY) -> str:
    """1250 → «12.50 с.»"""
    sign = "-" if diram < 0 else ""
    value = abs(int(diram))
    return f"{sign}{value // 100}.{value % 100:02d} {currency}"


def to_diram(text: str) -> int | None:
    """«12,5» ё «12.50» ё «12» → дирам. Агар нодуруст бошад — None."""
    cleaned = text.strip().replace(" ", "").replace(",", ".")
    if not cleaned:
        return None
    try:
        value = round(float(cleaned) * 100)
    except ValueError:
        return None
    return value if value > 0 else None


def esc(value: object) -> str:
    return escape(str(value or ""), quote=False)


# ── Тугмаҳои менюи асосӣ ──────────────────────────────────────────────
BTN_TELEGRAM = "⭐️ Telegram Stars ва Premium"
BTN_FF_CIS = "🔥 Free Fire (ИДМ)"
BTN_FF_ID = "🇮🇩 Free Fire (Индонезия)"
BTN_PUBG = "🎯 PUBG Mobile"
BTN_TOPUP = "💳 Пур кардани ҳисоб"
BTN_SUPPORT = "🎧 Дастгирӣ"
BTN_TOP = "🏆 Беҳтарин харидорон"
BTN_REVIEWS = "👍 Шарҳҳо"
BTN_MY_ORDERS = "🧾 Фармоишҳои ман"

BTN_STARS = "⭐️ Telegram Stars"
BTN_PREMIUM = "👑 Telegram Premium"

BTN_BACK = "◀️ Бозгашт"
BTN_HOME = "🏠 Менюи асосӣ"
BTN_CANCEL = "✖️ Бекор кардан"
BTN_CONFIRM = "✅ Тасдиқ мекунам"
BTN_YES_MINE = "✅ Ҳа, аккаунти ман аст"
BTN_NO_WRONG = "🔄 Не, ID-ро иваз мекунам"
BTN_PAY = "💰 Пардохт кардан"
BTN_PAID = "✅ Пардохт кардам"
BTN_OPEN_LINK = "🏦 Душанбе Сити"
BTN_OPEN_ALIF = "📱 Alif Mobi"
BTN_OTHER_SUM = "✏️ Маблағи дигар"
BTN_ADMIN = "🛠 Панели админ"

# ── Матнҳо ────────────────────────────────────────────────────────────
WELCOME_TITLE = "<b>Хуш омадед!</b>"
WELCOME_QUOTE = (
    "<blockquote>Дар ин ҷо шумо метавонед Telegram Stars, Telegram Premium, "
    "алмосҳои Free Fire ва UC-и PUBG Mobile харед — зуд, арзон ва "
    "бидуни ворид шудан ба аккаунт.</blockquote>"
)
CHOOSE_SECTION = "<i>Бахшро аз поён интихоб кунед</i> 👇"


def welcome(balance: int, currency: str = CURRENCY) -> str:
    return (
        f"{WELCOME_TITLE}\n\n"
        f"{WELCOME_QUOTE}\n\n"
        f"💳 Ҳисоби шумо: <b>{money(balance, currency)}</b>\n\n"
        f"{CHOOSE_SECTION}"
    )


TELEGRAM_MENU = (
    "⭐️ <b>Telegram</b>\n\n"
    "Кадом маҳсулот лозим аст?\n\n"
    "• <b>Stars</b> — ситораҳо ба ҳар аккаунт\n"
    "• <b>Premium</b> — обунаи 3, 6 ё 12 моҳа"
)


def category_menu(cat: catalog.Category, balance: int, currency: str = CURRENCY) -> str:
    return (
        f"{cat.icon} <b>{esc(cat.title)}</b>\n\n"
        f"Маҳсулотро интихоб кунед.\n"
        f"💳 Ҳисоби шумо: <b>{money(balance, currency)}</b>"
    )


EMPTY_CATEGORY = "Ҳоло дар ин бахш мол нест. Каме дертар бинед."


def ask_username(cat: catalog.Category, title: str, price: int, currency: str = CURRENCY) -> str:
    return (
        f"🛒 <b>{esc(title)}</b> — {money(price, currency)}\n\n"
        f"{esc(cat.hint)}\n\n"
        "Намуна: <code>@username</code>\n"
        "<i>Ба аккаунти шумо ворид намешавем — танҳо username лозим аст.</i>"
    )


def ask_player_id(cat: catalog.Category, title: str, price: int, currency: str = CURRENCY) -> str:
    return (
        f"🛒 <b>{esc(title)}</b> — {money(price, currency)}\n\n"
        f"{esc(cat.hint)}\n\n"
        "Намуна: <code>123456789</code>"
    )


BAD_USERNAME = (
    "❌ Username нодуруст аст.\n\n"
    "Онро бо <code>@</code> нависед, аз 5 то 32 аломат: "
    "ҳарфҳои лотинӣ, рақамҳо ва зери хат."
)
BAD_PLAYER_ID = "❌ ID нодуруст аст. Танҳо рақамҳо, аз 6 то 12 рақам."


def confirm_target(
    cat: catalog.Category, target: str, nickname: str | None, error: str | None = None
) -> str:
    """Панели тафтиш — харидор бояд тасдиқ кунад, ки ин аккаунти ӯст."""
    is_player = cat.target == "player"
    head = (
        "🔎 <b>Тафтиши аккаунт</b>\n\n"
        f"{cat.icon} Бахш: <b>{esc(cat.title)}</b>\n"
        + (
            f"🆔 ID: <code>{esc(target)}</code>\n"
            if is_player
            else f"👤 Username: <code>{esc(target)}</code>\n"
        )
    )
    if nickname:
        label = "Лақаб" if is_player else "Ном"
        head += f"✅ {label}: <b>{esc(nickname)}</b>\n"
    else:
        head += "⚠️ <i>Аккаунт худкор тафтиш нашуд"
        head += f" ({esc(error)})" if error else ""
        head += ".\nИлтимос, худатон бодиққат санҷед.</i>\n"
    return head + "\n<b>Ин аккаунти шумост?</b>"


def confirm_order(
    cat: catalog.Category,
    title: str,
    price: int,
    target: str,
    nickname: str | None,
    balance: int,
    currency: str = CURRENCY,
) -> str:
    lines = [
        "🧾 <b>Тасдиқи фармоиш</b>",
        "",
        f"📦 Мол: <b>{esc(title)}</b>",
        f"🎯 Бахш: {esc(cat.title)}",
        f"{'🆔' if cat.target == 'player' else '👤'} Гиранда: <code>{esc(target)}</code>",
    ]
    if nickname:
        lines.append(f"👤 Лақаб: <b>{esc(nickname)}</b>")
    lines += [
        "",
        f"💰 Нарх: <b>{money(price, currency)}</b>",
        f"💳 Ҳисоби шумо: {money(balance, currency)}",
        f"💵 Пас аз харид: {money(balance - price, currency)}",
        "",
        "Барои пардохт тугмаи поёнро пахш кунед.",
    ]
    return "\n".join(lines)


def not_enough(price: int, balance: int, currency: str = CURRENCY) -> str:
    return (
        "❌ <b>Маблағ кифоя нест</b>\n\n"
        f"💰 Нарх: {money(price, currency)}\n"
        f"💳 Ҳисоби шумо: {money(balance, currency)}\n"
        f"➕ Лозим аст: <b>{money(price - balance, currency)}</b>\n\n"
        "Ҳисобро пур кунед ва аз нав кӯшиш кунед."
    )


def order_created(order_id: int, title: str, target: str, price: int, currency: str = CURRENCY) -> str:
    return (
        "✅ <b>Фармоиш қабул шуд!</b>\n\n"
        f"🧾 Рақами фармоиш: <code>#{order_id}</code>\n"
        f"📦 Мол: <b>{esc(title)}</b>\n"
        f"🎯 Гиранда: <code>{esc(target)}</code>\n"
        f"💰 Пардохт: {money(price, currency)}\n\n"
        "⏳ <b>Фармоиш ба коркард рафт.</b>\n"
        "Каме сабр кунед — натиҷаро ҳамин ҷо менависем."
    )


def receipt(
    order_id: int,
    title: str,
    target: str,
    nickname: str | None,
    price: int,
    external_id: str | None,
    is_player: bool,
    currency: str = CURRENCY,
) -> str:
    """Чеки ниҳоии харид."""
    stamp = datetime.now().strftime("%d.%m.%Y • %H:%M")
    number = f"<code>#{order_id}</code>"
    if external_id:
        number += f" (№ {esc(external_id)})"
    lines = [
        "🧾 <b>ЧЕКИ ХАРИД</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        "✅ <b>Ҳолат:</b> БОМУВАФФАҚИЯТ",
        f"🔢 <b>Фармоиш:</b> {number}",
        (f"🆔 <b>ID:</b> <code>{esc(target)}</code>" if is_player
         else f"👤 <b>Username:</b> <code>{esc(target)}</code>"),
    ]
    if nickname:
        lines.append(f"👤 <b>{'Лақаб' if is_player else 'Ном'}:</b> {esc(nickname)}")
    lines += [
        f"📦 <b>Мол:</b> {esc(title)}",
        f"💰 <b>Маблағ:</b> {money(price, currency)}",
        f"📅 <b>Сана:</b> {stamp}",
        "━━━━━━━━━━━━━━━━━━━━",
        "🎉 <b>Хариди шумо иҷро шуд!</b>",
        "",
        "Ташаккур барои харид! ❤️",
    ]
    return "\n".join(lines)


def auto_refunded(order_id: int, price: int, reason: str | None, currency: str = CURRENCY) -> str:
    """Фармоиш иҷро нашуд — пул худкор баргардонида шуд."""
    why = f"\n📌 Сабаб: <code>{esc(reason)}</code>" if reason else ""
    return (
        f"⚠️ <b>Фармоиши #{order_id} иҷро нашуд.</b>{why}\n\n"
        f"💳 <b>{money(price, currency)}</b> худкор ба ҳисоби шумо баргардонида шуд.\n"
        "Метавонед аз нав кӯшиш кунед ё ба дастгирӣ нависед."
    )


def order_pending_admin(order_id: int) -> str:
    """Фармоиш ба админ монд (мол API надорад ё ҷавоб дер кард)."""
    return (
        f"⏳ <b>Фармоиши #{order_id} дар коркард аст.</b>\n\n"
        "Онро админ дастӣ иҷро мекунад — одатан 5–30 дақиқа.\n"
        "Вақте тайёр шуд, ба шумо хабар медиҳем."
    )


ORDER_STATUS_LABEL = {
    ORDER_NEW: "⏳ Дар навбат",
    ORDER_SENT: "🔄 Дар коркард",
    ORDER_DONE: "✅ Иҷро шуд",
    ORDER_REJECTED: "❌ Рад шуд (пул баргардонида шуд)",
}

TOPUP_STATUS_LABEL = {
    TOPUP_WAITING: "⏳ Дар интизори тасдиқ",
    TOPUP_PAID: "✅ Тасдиқ шуд",
    TOPUP_REJECTED: "❌ Рад шуд",
}


def order_done_note(order_id: int, title: str, target: str) -> str:
    return (
        f"✅ <b>Фармоиши #{order_id} иҷро шуд!</b>\n\n"
        f"📦 {esc(title)}\n"
        f"🎯 {esc(target)}\n\n"
        "Ташаккур барои харид! 🙏\n"
        "Агар вақт доред, шарҳи худро нависед — барои мо муҳим аст."
    )


def order_rejected_note(order_id: int, price: int, currency: str = CURRENCY) -> str:
    return (
        f"❌ <b>Фармоиши #{order_id} рад шуд.</b>\n\n"
        f"💳 {money(price, currency)} ба ҳисоби шумо баргардонида шуд.\n"
        "Барои маълумот ба дастгирӣ муроҷиат кунед."
    )


# ── Пур кардани ҳисоб ─────────────────────────────────────────────────
def topup_menu(balance: int, min_sum: int, max_sum: int, currency: str = CURRENCY) -> str:
    return (
        "💳 <b>Пур кардани ҳисоб</b>\n\n"
        f"Ҳисоби ҳозира: <b>{money(balance, currency)}</b>\n\n"
        "Маблағро интихоб кунед ё худатон нависед.\n"
        f"<i>Аз {money(min_sum, currency)} то {money(max_sum, currency)}</i>"
    )


def ask_amount(min_sum: int, max_sum: int, currency: str = CURRENCY) -> str:
    return (
        "✏️ Маблағро бо рақам нависед.\n\n"
        f"Намуна: <code>150</code> ё <code>99.50</code>\n"
        f"<i>Аз {money(min_sum, currency)} то {money(max_sum, currency)}</i>"
    )


def bad_amount(min_sum: int, max_sum: int, currency: str = CURRENCY) -> str:
    return (
        "❌ Маблағ нодуруст аст.\n\n"
        f"Аз {money(min_sum, currency)} то {money(max_sum, currency)} нависед. "
        "Намуна: <code>150</code>"
    )


def payment_details(
    topup_id: int,
    amount: int,
    code: str,
    card: str,
    holder: str,
    currency: str = CURRENCY,
) -> str:
    return (
        "💳 <b>Реквизитҳо барои пардохт</b>\n\n"
        f"🏦 <b>Душанбе Сити</b>\n"
        f"💳 Корт: <code>{esc(card)}</code>\n"
        f"👤 Ном: <b>{esc(holder)}</b>\n"
        f"💰 Маблағ: <b>{money(amount, currency)}</b>\n\n"
        f"🔑 <b>Коди тасдиқ: <code>{esc(code)}</code></b>\n"
        "<i>Ин кодро ҳатман дар «Шарҳ / Комментарий»-и ҳавола нависед — "
        "бе он пардохт зуд пайдо намешавад.</i>\n\n"
        f"🧾 Рақами пардохт: <code>#{topup_id}</code>\n\n"
        "Пас аз ҳавола тугмаи <b>«✅ Пардохт кардам»</b>-ро пахш кунед "
        "ва скриншот ё чекро фиристед."
    )


def topup_waiting(topup_id: int) -> str:
    return (
        "⏳ <b>Пардохти шумо ба тафтиш рафт.</b>\n\n"
        f"🧾 Рақами пардохт: <code>#{topup_id}</code>\n\n"
        "Чек ё скриншоти ҳаволаро дар ҳамин ҷо фиристед — тафтиш тезтар мешавад.\n"
        "Одатан 5–20 дақиқа вақт мегирад."
    )


def topup_confirmed(amount: int, balance: int, currency: str = CURRENCY) -> str:
    return (
        "✅ <b>Ҳисоб пур шуд!</b>\n\n"
        f"➕ {money(amount, currency)}\n"
        f"💳 Ҳисоби нав: <b>{money(balance, currency)}</b>"
    )


def topup_rejected(topup_id: int) -> str:
    return (
        f"❌ <b>Пардохти #{topup_id} тасдиқ нашуд.</b>\n\n"
        "Агар шумо воқеан ҳавола карда бошед — чекро ба дастгирӣ фиристед."
    )


NO_PAY_LINK = (
    "<i>Ҳавола бо як пахш ҳоло фаъол нест — реквизитҳоро дастӣ нусхабардорӣ кунед.</i>"
)

# ── Бахшҳои иловагӣ ───────────────────────────────────────────────────
def support(username: str) -> str:
    who = f"@{esc(username)}" if username else "<i>ҳоло нишон дода нашудааст</i>"
    return (
        "🎧 <b>Дастгирӣ</b>\n\n"
        f"Ба мо нависед: {who}\n\n"
        "Кор мекунем: ҳар рӯз, аз 08:00 то 00:00.\n"
        "Ҳангоми муроҷиат рақами фармоишро нависед — зудтар кӯмак мекунем."
    )


def top_clients(rows: list, currency: str = CURRENCY) -> str:
    if not rows:
        return (
            "🏆 <b>Беҳтарин харидорон</b>\n\n"
            "Ҳоло рӯйхат холӣ аст. Аввалин шавед! 😉"
        )
    medals = ("🥇", "🥈", "🥉")
    lines = ["🏆 <b>Беҳтарин харидорон</b>\n"]
    for i, user in enumerate(rows):
        mark = medals[i] if i < len(medals) else f"{i + 1}."
        name = esc(user.first_name or (f"@{user.username}" if user.username else "Харидор"))
        lines.append(f"{mark} <b>{name}</b> — {money(user.spent, currency)} • {user.orders_done} фармоиш")
    return "\n".join(lines)


def my_orders(rows: list, currency: str = CURRENCY) -> str:
    if not rows:
        return "🧾 <b>Фармоишҳои ман</b>\n\nҲоло фармоиш надоред."
    lines = ["🧾 <b>Фармоишҳои охирини шумо</b>\n"]
    for row in rows:
        label = ORDER_STATUS_LABEL.get(row["status"], row["status"])
        lines.append(
            f"<code>#{row['id']}</code> • {esc(row['title'])} • "
            f"{money(row['price'], currency)}\n{label}"
        )
    return "\n\n".join(lines)


BLOCKED = (
    "🚫 Дастрасии шумо ба бот маҳдуд аст.\n"
    "Барои маълумот ба дастгирӣ муроҷиат кунед."
)
CANCELLED = "✖️ Бекор карда шуд."
UNKNOWN = "Ин фармонро намефаҳмам. Тугмаи 🏠 <b>Менюи асосӣ</b>-ро пахш кунед."
ERROR = "⚠️ Хатогӣ рух дод. Каме дертар кӯшиш кунед ё ба дастгирӣ нависед."


# ── Панели админ ──────────────────────────────────────────────────────
ADM_BTN_STATS = "📊 Омор"
ADM_BTN_FIND = "🔍 Ҷустуҷӯи корбар"
ADM_BTN_ORDERS = "🧾 Фармоишҳои кушода"
ADM_BTN_TOPUPS = "💳 Пардохтҳои интизорӣ"
ADM_BTN_PRICES = "💲 Нархҳо"
ADM_BTN_BROADCAST = "📢 Эълон ба ҳама"
ADM_BTN_SUPPLIER = "🔌 Таъминкунанда"
ADM_BTN_PLUS = "➕ Илова кардан"
ADM_BTN_MINUS = "➖ Кам кардан"
ADM_BTN_BLOCK = "🚫 Маҳдуд кардан"
ADM_BTN_UNBLOCK = "✅ Кушодани дастрасӣ"
ADM_BTN_DONE = "✅ Иҷро шуд"
ADM_BTN_REJECT = "❌ Рад кардан"
ADM_BTN_CONFIRM_PAY = "✅ Пулро гирифтам"

ADMIN_HOME = "🛠 <b>Панели админ</b>\n\nАмалро интихоб кунед."
ADMIN_DENIED = "⛔️ Ин бахш танҳо барои админ аст."
ADMIN_ASK_USER = (
    "🔍 ID, @username ё рақами корбарро нависед.\n\n"
    "Намуна: <code>123456789</code> ё <code>@username</code>"
)
ADMIN_USER_NOT_FOUND = "❌ Чунин корбар ёфт нашуд."
ADMIN_ASK_SUM_PLUS = "➕ Чанд сомонӣ илова кунам?\n\nНамуна: <code>50</code> ё <code>99.50</code>"
ADMIN_ASK_SUM_MINUS = "➖ Чанд сомонӣ кам кунам?\n\nНамуна: <code>50</code>"
ADMIN_ASK_PRICE = "💲 Нархи навро бо сомонӣ нависед.\n\nНамуна: <code>21</code> ё <code>20.50</code>"
ADMIN_ASK_BROADCAST = (
    "📢 Матни эълонро нависед — ба ҳамаи корбарон фиристода мешавад.\n\n"
    "Барои бекор кардан: /bekor"
)
ADMIN_NO_ORDERS = "✅ Фармоиши кушода нест."
ADMIN_NO_TOPUPS = "✅ Пардохти интизорӣ нест."


def admin_stats(data: dict, currency: str = CURRENCY) -> str:
    return (
        "📊 <b>Омори умумӣ</b>\n\n"
        f"👥 Корбарон: <b>{data['users']}</b> (маҳдуд: {data['blocked']})\n"
        f"💳 Дар ҳисобҳо: <b>{money(data['balance'], currency)}</b>\n\n"
        f"🧾 Фармоишҳо: <b>{data['orders']}</b>\n"
        f"   ⏳ кушода: {data['orders_open']}\n"
        f"   ✅ иҷрошуда: {data['orders_done']}\n"
        f"💰 Даромад: <b>{money(data['revenue'], currency)}</b>\n\n"
        f"💵 Пур карда шуд: {money(data['topups_paid'], currency)}\n"
        f"⏳ Пардохтҳои интизорӣ: <b>{data['topups_open']}</b>"
    )


def admin_user_card(user, orders: list, topups: list, currency: str = CURRENCY) -> str:
    status = "🚫 Маҳдуд" if user.is_blocked else "✅ Фаъол"
    lines = [
        "👤 <b>Корти корбар</b>\n",
        f"🆔 ID: <code>{user.id}</code>",
        f"👤 Ном: <b>{esc(user.first_name or '—')}</b>",
        f"🔗 Username: {('@' + esc(user.username)) if user.username else '—'}",
        f"📶 Ҳолат: {status}",
        "",
        f"💳 Ҳисоб: <b>{money(user.balance, currency)}</b>",
        f"💰 Харҷ кардааст: {money(user.spent, currency)}",
        f"🧾 Фармоишҳои иҷрошуда: {user.orders_done}",
        f"📅 Сабти ном: {esc(user.created_at[:10])}",
        f"👁 Фаъолияти охирин: {esc(user.last_seen[:16].replace('T', ' '))}",
    ]
    if orders:
        lines += ["", "<b>Фармоишҳои охирин:</b>"]
        for row in orders[:5]:
            label = ORDER_STATUS_LABEL.get(row["status"], row["status"])
            lines.append(
                f"<code>#{row['id']}</code> {esc(row['title'])} — "
                f"{money(row['price'], currency)} — {label}"
            )
    if topups:
        lines += ["", "<b>Пардохтҳои охирин:</b>"]
        for row in topups[:5]:
            label = TOPUP_STATUS_LABEL.get(row["status"], row["status"])
            lines.append(
                f"<code>#{row['id']}</code> {money(row['amount'], currency)} — "
                f"код <code>{esc(row['code'])}</code> — {label}"
            )
    return "\n".join(lines)


def admin_order_card(row, user, currency: str = CURRENCY) -> str:
    label = ORDER_STATUS_LABEL.get(row["status"], row["status"])
    who = f"<code>{user.id}</code>" if user else "—"
    if user and user.username:
        who += f" @{esc(user.username)}"
    return (
        f"🧾 <b>Фармоиши #{row['id']}</b>\n\n"
        f"👤 Харидор: {who}\n"
        f"📦 Мол: <b>{esc(row['title'])}</b>\n"
        f"🎯 Бахш: {esc(row['category'])}\n"
        f"🆔 Гиранда: <code>{esc(row['target'])}</code>\n"
        + (f"👤 Лақаб: <b>{esc(row['nickname'])}</b>\n" if row["nickname"] else "")
        + f"💰 Нарх: <b>{money(row['price'], currency)}</b>\n"
        f"📶 Ҳолат: {label}\n"
        f"📅 {esc(row['created_at'][:16].replace('T', ' '))}"
    )


def admin_topup_card(row, user, currency: str = CURRENCY) -> str:
    label = TOPUP_STATUS_LABEL.get(row["status"], row["status"])
    who = f"<code>{user.id}</code>" if user else "—"
    if user and user.username:
        who += f" @{esc(user.username)}"
    return (
        f"💳 <b>Пардохти #{row['id']}</b>\n\n"
        f"👤 Корбар: {who}\n"
        f"💰 Маблағ: <b>{money(row['amount'], currency)}</b>\n"
        f"🔑 Коди тасдиқ: <code>{esc(row['code'])}</code>\n"
        f"📶 Ҳолат: {label}\n"
        f"📅 {esc(row['created_at'][:16].replace('T', ' '))}"
    )


def admin_new_order(row, user, currency: str = CURRENCY) -> str:
    return "🔔 <b>ФАРМОИШИ НАВ</b>\n\n" + admin_order_card(row, user, currency)


def admin_new_topup(row, user, currency: str = CURRENCY) -> str:
    return "🔔 <b>ПАРДОХТИ НАВ</b>\n\n" + admin_topup_card(row, user, currency)


def admin_prices(rows: list, cat_title: str, currency: str = CURRENCY) -> str:
    lines = [f"💲 <b>Нархҳо — {esc(cat_title)}</b>\n", "Молро барои иваз кардани нарх интихоб кунед."]
    return "\n".join(lines)


def admin_balance_changed(user, delta: int, currency: str = CURRENCY) -> str:
    sign = "➕" if delta > 0 else "➖"
    return (
        f"{sign} Ҳисоби корбар иваз шуд.\n\n"
        f"👤 {esc(user.title)}\n"
        f"💳 Ҳисоби нав: <b>{money(user.balance, currency)}</b>"
    )


def user_balance_added(amount: int, balance: int, currency: str = CURRENCY) -> str:
    return (
        "💚 <b>Ҳисоби шумо пур шуд!</b>\n\n"
        f"➕ {money(amount, currency)}\n"
        f"💳 Ҳисоби нав: <b>{money(balance, currency)}</b>"
    )


def user_balance_removed(amount: int, balance: int, currency: str = CURRENCY) -> str:
    return (
        "🔻 <b>Аз ҳисоби шумо маблағ кам карда шуд.</b>\n\n"
        f"➖ {money(amount, currency)}\n"
        f"💳 Ҳисоби нав: <b>{money(balance, currency)}</b>"
    )


def broadcast_result(sent: int, failed: int) -> str:
    return f"📢 Эълон фиристода шуд.\n\n✅ Расид: <b>{sent}</b>\n❌ Нарасид: {failed}"
