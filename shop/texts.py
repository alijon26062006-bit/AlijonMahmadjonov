"""Ҳамаи матнҳои бот — бо забони тоҷикӣ. Дар як ҷо, то тағйир додан осон бошад."""

from __future__ import annotations

import math
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

#: Ҳадди болоии ҳар маблағе, ки дастӣ ворид мешавад (сомонӣ).
MAX_SUM_SOMONI = 10_000_000


def money(diram: int, currency: str = CURRENCY) -> str:
    """1250 → «12.50 с.»"""
    sign = "-" if diram < 0 else ""
    value = abs(int(diram))
    return f"{sign}{value // 100}.{value % 100:02d} {currency}"


def to_diram(text: str) -> int | None:
    """«12,5» ё «12.50» ё «12» → дирам. Агар нодуруст бошад — None."""
    cleaned = (text or "").strip().replace(" ", "").replace(",", ".")
    if not cleaned:
        return None
    try:
        number = float(cleaned)
    except ValueError:
        return None
    # «inf», «nan», «1e20» — бот меафтод ё ба ҳисоб рақами бемаъно менавишт.
    if not math.isfinite(number) or number > MAX_SUM_SOMONI:
        return None
    value = round(number * 100)
    return value if value > 0 else None


def esc(value: object) -> str:
    return escape(str(value or ""), quote=False)


# ── Тугмаҳои менюи асосӣ ──────────────────────────────────────────────
BTN_TELEGRAM = "⭐️ Telegram Stars ва Premium"
BTN_FF_CIS = "🔥 Free Fire"
BTN_FF_ID = "🇮🇩 Free Fire (Индонезия)"
BTN_PUBG = "🎯 PUBG Mobile"
BTN_OTHER = "🎮 Дигар бозиҳо"
BTN_TOPUP = "💳 Пур кардани ҳисоб"
BTN_SUPPORT = "🎧 Дастгирӣ"
BTN_TOP = "🏆 Беҳтарин харидорон"
BTN_REVIEWS = "👍 Шарҳҳо"
BTN_MY_ORDERS = "🧾 Фармоишҳои ман"
BTN_BALANCE = "💰 Ҳисоби ман"
BTN_API = "🔌 API барои барномасозон"

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


def welcome(balance: int, currency: str = CURRENCY, partner: bool = False) -> str:
    badge = f"\n{PARTNER_BADGE}\n" if partner else ""
    return (
        f"{WELCOME_TITLE}\n\n"
        f"{WELCOME_QUOTE}\n"
        f"{badge}\n"
        f"💳 Ҳисоби шумо: <b>{money(balance, currency)}</b>\n\n"
        f"{CHOOSE_SECTION}"
    )


TELEGRAM_MENU = (
    "⭐️ <b>Telegram</b>\n\n"
    "Кадом маҳсулот лозим аст?\n\n"
    "• <b>Stars</b> — ситораҳо ба ҳар аккаунт\n"
    "• <b>Premium</b> — обунаи 3, 6 ё 12 моҳа"
)


PARTNER_BADGE = "🤝 <b>Нархи шарикӣ</b> барои шумо фаъол аст"


def category_menu(
    cat: catalog.Category, balance: int, currency: str = CURRENCY, partner: bool = False
) -> str:
    badge = f"\n{PARTNER_BADGE}" if partner else ""
    return (
        f"{cat.icon} <b>{esc(cat.title)}</b>{badge}\n\n"
        f"Маҳсулотро интихоб кунед.\n"
        f"💳 Ҳисоби шумо: <b>{money(balance, currency)}</b>"
    )


def group_menu(
    cat: catalog.Category,
    group_title: str,
    balance: int,
    currency: str = CURRENCY,
    partner: bool = False,
) -> str:
    badge = f"\n{PARTNER_BADGE}" if partner else ""
    return (
        f"{cat.icon} <b>{esc(cat.title)}</b> · {esc(group_title)}{badge}\n\n"
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
BAD_PLAYER_SERVER = (
    "❌ Нодуруст аст.\n\n"
    "ID ва рақами серверро бо фосила нависед:\n"
    "<code>123456789 1234</code>\n\n"
    "<i>Онҳоро дар бозӣ, дар профили худ мебинед: ID (сервер).</i>"
)


def ask_player_server(cat: catalog.Category, title: str, price: int, currency: str = CURRENCY) -> str:
    return (
        f"🛒 <b>{esc(title)}</b> — {money(price, currency)}\n\n"
        "ID ва рақами серверро <b>бо фосила</b> нависед.\n\n"
        "Намуна: <code>123456789 1234</code>\n"
        "<i>Дар бозӣ дар профили худ чунин навишта шудааст: ID (сервер).</i>"
    )


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
    partner: bool = False,
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
        f"💰 Нарх: <b>{money(price, currency)}</b>"
        + ("  🤝 <i>нархи шарикӣ</i>" if partner else ""),
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
        # Ин ҳанӯз чек нест: мол ҳоло харида нашудааст. Чек танҳо пас аз
        # тасдиқи таъминкунанда меояд.
        "🕐 <b>Фармоиш сабт шуд — ҳанӯз иҷро нашудааст.</b>\n\n"
        f"🧾 Рақами фармоиш: <code>#{order_id}</code>\n"
        f"📦 Мол: <b>{esc(title)}</b>\n"
        f"🎯 Гиранда: <code>{esc(target)}</code>\n"
        f"💰 Пардохт: {money(price, currency)}\n\n"
        "⏳ <b>Фармоиш ба таъминкунанда фиристода мешавад.</b>\n"
        "Вақте мол воқеан расид, чеки харид ҳамин ҷо меояд."
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


NO_REQUISITES = (
    "⚠️ <b>Пур кардани ҳисоб ҳоло дастрас нест.</b>\n\n"
    "Реквизитҳо танзим нашудаанд. Лутфан ба дастгирӣ муроҷиат кунед."
)


def payment_details(
    topup_id: int,
    amount: int,
    code: str,
    card: str,
    holder: str,
    currency: str = CURRENCY,
    alif_account: str = "",
) -> str:
    lines = ["💳 <b>Реквизитҳо барои пардохт</b>\n"]
    if card:
        lines += [
            "🏦 <b>Душанбе Сити</b>",
            f"💳 Корт: <code>{esc(card)}</code>",
        ]
        if holder:
            lines.append(f"👤 Ном: <b>{esc(holder)}</b>")
        lines.append("")
    if alif_account:
        lines += [
            "📱 <b>Alif Mobi</b>",
            f"🔢 Ҳисоб: <code>{esc(alif_account)}</code>",
            "",
        ]
    lines += [
        f"💰 Маблағ: <b>{money(amount, currency)}</b>",
        "",
        f"🔑 <b>Коди тасдиқ: <code>{esc(code)}</code></b>",
        "<i>Ин кодро ҳатман дар «Шарҳ / Комментарий»-и ҳавола нависед — "
        "бе он пардохт зуд пайдо намешавад.</i>",
        "",
        f"🧾 Рақами пардохт: <code>#{topup_id}</code>",
        "",
        "Пас аз ҳавола тугмаи <b>«✅ Пардохт кардам»</b>-ро пахш кунед "
        "ва скриншот ё чекро фиристед.",
    ]
    return "\n".join(lines)


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
def support(username: str, whatsapp: str = "") -> str:
    lines = ["🎧 <b>Дастгирӣ</b>\n"]
    if username:
        lines.append(f"✈️ Telegram: @{esc(username)}")
    if whatsapp:
        lines.append(f"🟢 WhatsApp: <code>+{esc(whatsapp)}</code>")
    if not username and not whatsapp:
        lines.append("<i>Тамос ҳоло нишон дода нашудааст.</i>")
    lines += [
        "",
        "Кор мекунем: ҳар рӯз, аз 08:00 то 00:00.",
        "Ҳангоми муроҷиат рақами фармоишро нависед — зудтар кӯмак мекунем.",
    ]
    return "\n".join(lines)


def my_balance(balance: int, log_rows: list, currency: str = CURRENCY) -> str:
    lines = [
        "💰 <b>Ҳисоби ман</b>\n",
        f"💳 Маблағ: <b>{money(balance, currency)}</b>",
    ]
    if log_rows:
        lines.append("\n<b>Ҳаракати охирин:</b>")
        for row in log_rows[:8]:
            sign = "➕" if row["delta"] > 0 else "➖"
            when = esc(row["created_at"][:10])
            lines.append(f"{sign} {money(abs(row['delta']), currency)} · {when}")
    else:
        lines.append("\n<i>Ҳоло ҳаракат нест.</i>")
    return "\n".join(lines)


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


BTN_CHECK_SUB = "✅ Обуна шудам — санҷед"
BTN_WRITE_REVIEW = "✍️ Шарҳ навиштан"
BTN_SKIP = "⏭ Ҳозир не"

ASK_REVIEW = (
    "✍️ <b>Шарҳи худро нависед</b>\n\n"
    "Чанд ҷумла кифоя аст — чӣ харидед ва чӣ гуна буд.\n"
    "<i>Шарҳ пас аз тасдиқи админ дар канал нашр мешавад.</i>"
)
REVIEW_TOO_SHORT = "❌ Шарҳ хеле кӯтоҳ аст. Ақаллан 10 аломат нависед."
REVIEW_SENT = (
    "🙏 <b>Ташаккур барои шарҳ!</b>\n\n"
    "Онро месанҷем ва дар канал нашр мекунем."
)
REVIEW_PUBLISHED_NOTE = "✅ Шарҳи шумо дар канал нашр шуд. Ташаккур! ❤️"
REVIEW_REJECTED_NOTE = "ℹ️ Шарҳи шумо нашр нашуд."
REVIEW_INVITE = (
    "\n\n💬 <b>Шарҳи худро мемонед?</b>\n"
    "<i>Ба мо кӯмак мекунад, ба шумо — чанд сония вақт.</i>"
)


def review_for_channel(text: str, name: str) -> str:
    """Чӣ тавр шарҳ дар канал нашр мешавад."""
    return (
        "⭐️ <b>Шарҳи харидор</b>\n\n"
        f"<blockquote>{esc(text)}</blockquote>\n\n"
        f"👤 {esc(name)}"
    )


def admin_new_review(row, user) -> str:
    who = f"<code>{user.id}</code>" if user else "—"
    if user and user.username:
        who += f" @{esc(user.username)}"
    return (
        f"💬 <b>ШАРҲИ НАВ #{row['id']}</b>\n\n"
        f"👤 Аз: {who}\n\n"
        f"<blockquote>{esc(row['text'])}</blockquote>\n\n"
        "Нашр кунем?"
    )


def subscribe_required(rows: list) -> str:
    word = "канал" if len(rows) == 1 else "каналҳо"
    return (
        "🔒 <b>Барои истифодаи бот обуна лозим аст</b>\n\n"
        f"Ба {word}и зерин обуна шавед, баъд тугмаи "
        f"<b>«{BTN_CHECK_SUB}»</b>-ро пахш кунед.\n\n"
        "<i>Ин як маротиба аст — баъдан бот озод кор мекунад.</i>"
    )


SUB_NOT_YET = "❌ Шумо ҳанӯз ба ҳамаи каналҳо обуна нашудаед."
SUB_OK = "✅ Ташаккур! Акнун бот дастрас аст."

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
ADM_BTN_PARTNERS = "🤝 Шарикон"
ADM_BTN_SETTINGS = "⚙️ Танзимот"
ADM_BTN_USERS = "👥 Корбарон"
ADM_BTN_CHANNELS = "📢 Каналҳои обуна"
ADM_BTN_REVIEW_CH = "💬 Канали шарҳҳо"
ADM_BTN_WHATSAPP = "🟢 WhatsApp"
ADM_BTN_GROUPS = "🗂 Номи зербахшҳо"
ADM_BTN_REQUISITES = "💳 Реквизитҳо"
ADM_BTN_COSTS = "🔄 Нархи харидро нав кардан"
ADM_BTN_RATE = "💱 Курси доллар"
ADM_BTN_MARKUP = "📈 Фоизи нарх"
ADM_BTN_ADDGAME = "➕ Бозии нав аз таъминкунанда"
ADM_BTN_ADD_PARTNER = "➕ Шарики нав"
ADM_BTN_PARTNER_PRICE = "🤝 Нархи шарикӣ"
ADM_BTN_PARTNER_OFF = "🗑 Нархи шарикиро бардоштан"
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


ADMIN_ASK_PARTNER = (
    "🤝 ID ё @username-и шарики навро нависед.\n\n"
    "Намуна: <code>123456789</code> ё <code>@username</code>\n\n"
    "<i>Шахс бояд ҳадди ақал як бор /start-ро пахш карда бошад — "
    "вагарна ботро намешиносад.</i>"
)
ADMIN_ASK_PARTNER_PRICE = (
    "🤝 Нархи шарикиро бо сомонӣ нависед.\n\n"
    "Намуна: <code>8.40</code>\n"
    "Барои бардоштан нависед: <code>0</code>"
)


#: Рӯйхатҳо дар як паём: Telegram зиёда аз 4096 аломат ва 100 тугма қабул намекунад.
LIST_CAP = 30


def _more(rows: list) -> str:
    extra = len(rows) - LIST_CAP
    return f"\n<i>… ва боз {extra} нафар (танҳо {LIST_CAP}-тои аввал нишон дода шуд)</i>" if extra > 0 else ""


def admin_partners(rows: list, currency: str = CURRENCY) -> str:
    if not rows:
        return (
            "🤝 <b>Шарикон</b>\n\n"
            "Ҳоло шарик нест.\n\n"
            "<i>Шарик нархи махсуси шуморо мебинад — ба ҷои нархи оддӣ.</i>"
        )
    lines = [f"🤝 <b>Шарикон</b> ({len(rows)} нафар)\n"]
    for row in rows[:LIST_CAP]:
        name = esc(row["first_name"] or "—")
        user = f"@{esc(row['username'])}" if row["username"] else "—"
        note = f" · {esc(row['note'])}" if row["note"] else ""
        lines.append(
            f"• <code>{row['user_id']}</code> — <b>{name}</b> {user}{note}\n"
            f"  💳 {money(row['balance'] or 0, currency)} · "
            f"харҷ: {money(row['spent'] or 0, currency)}"
        )
    return "\n".join(lines) + _more(rows)


def partner_added(user) -> str:
    return (
        "✅ <b>Шарик илова шуд!</b>\n\n"
        f"👤 {esc(user.title)}\n"
        f"🆔 <code>{user.id}</code>\n\n"
        "Акнун ӯ дар ҳамаи бахшҳо нархи шарикиро мебинад."
    )


PARTNER_WELCOME = (
    "🤝 <b>Табрик! Шумо шарики мо шудед.</b>\n\n"
    "Акнун барои шумо нархҳои махсус — аз нархи оддӣ арзонтар.\n"
    "Онҳо худкор дар ҳамаи бахшҳо нишон дода мешаванд.\n\n"
    "Барои дидан /start-ро пахш кунед."
)

PARTNER_REMOVED = (
    "ℹ️ Нархи шарикии шумо бекор карда шуд.\n"
    "Аз ин пас нархҳои оддӣ амал мекунанд."
)


ADMIN_ASK_CHANNEL = (
    "📢 Каналро нависед: <code>@username</code> ё ID-и рақамӣ "
    "(<code>-1001234567890</code>).\n\n"
    "<b>Муҳим:</b> ботро дар он канал <b>админ</b> кунед — вагарна обунаро "
    "тафтиш карда наметавонад.\n\n"
    "Барои канали пӯшида ҳаволаро низ илова кунед:\n"
    "<code>-1001234567890 | https://t.me/+abc123</code>"
)
ADMIN_ASK_REVIEW_CHANNEL = (
    "💬 Канали шарҳҳоро нависед: <code>@username</code> ё ID-и рақамӣ.\n\n"
    "Шарҳҳои тасдиқшуда маҳз ба он ҷо мераванд.\n"
    "Ботро дар канал админ кунед.\n\n"
    "Барои хомӯш кардан нависед: <code>-</code>"
)
ADMIN_ASK_WHATSAPP = (
    "🟢 Рақами WhatsApp-ро нависед.\n\n"
    "Намуна: <code>992939880805</code>\n"
    "Барои бардоштан нависед: <code>-</code>"
)
ADMIN_ASK_GROUP_TITLE = (
    "🗂 Номи нави зербахшро нависед.\n\nНамуна: <code>💎 Алмосҳо</code>"
)
ADMIN_BC_STEP1 = (
    "📢 <b>Эълон — қадами 1 аз 3</b>\n\n"
    "Акс ё видео фиристед.\n"
    "Агар лозим набошад — нависед <code>-</code>"
)
ADMIN_BC_STEP2 = (
    "📢 <b>Эълон — қадами 2 аз 3</b>\n\n"
    "Акнун худи паёмро фиристед: матн, овоз, стикер, доира, ҳуҷҷат, файл ё ҳавола.\n"
    "Агар лозим набошад — нависед <code>-</code>"
)
ADMIN_BC_STEP3 = (
    "📢 <b>Эълон — қадами 3 аз 3</b>\n\n"
    "Тугмаи ҳавола илова кунем?\n"
    "Дар як сатр нависед: <code>Ном | https://ҳавола</code>\n"
    "Якчанд тугма — ҳар кадом дар сатри нав.\n\n"
    "Агар лозим набошад — нависед <code>-</code>"
)
ADMIN_BC_EMPTY = "❌ Эълони холӣ. Ақаллан як қадамро пур кунед."
ADMIN_BC_BAD_BUTTON = (
    "❌ Тугма нодуруст аст.\n\nНамуна: <code>Канали мо | https://t.me/almaz_tj</code>"
)


def admin_bc_preview(has_media: bool, has_body: bool, buttons: int, users: int) -> str:
    return (
        "📢 <b>Эълон тайёр аст</b>\n\n"
        f"🖼 Акс/видео: {'ҳа' if has_media else 'не'}\n"
        f"✉️ Паём: {'ҳа' if has_body else 'не'}\n"
        f"🔗 Тугмаҳо: {buttons}\n"
        f"👥 Гирандагон: <b>{users}</b>\n\n"
        "Мефиристем?"
    )


ADMIN_ASK_CARD = (
    "💳 Рақами корти Душанбе Ситиро нависед.\n\n"
    "Намуна: <code>9762 0001 0986 6409</code>\n"
    "<i>Фосилаҳо муҳим нестанд — бот худаш тартиб медиҳад.</i>"
)
ADMIN_ASK_HOLDER = (
    "👤 Номи соҳиби кортро нависед.\n\nНамуна: <code>ALIJON M.</code>"
)
ADMIN_ASK_ALIF = (
    "📱 Рақами ҳисоби Alif Mobi-ро нависед.\n\n"
    "Намуна: <code>939880805</code>"
)
ADMIN_LAST_METHOD = (
    "⚠️ Ин ягона тарзи пардохт аст — хомӯш карда намешавад.\n"
    "Аввал тарзи дуюмро фаъол кунед."
)


def admin_requisites(req, currency: str = CURRENCY) -> str:
    dc_state = "✅ фаъол" if req.dc_enabled else "🚫 хомӯш"
    alif_state = "✅ фаъол" if req.alif_enabled else "🚫 хомӯш"
    return (
        "💳 <b>Реквизитҳои пардохт</b>\n\n"
        f"🏦 <b>Душанбе Сити</b> — {dc_state}\n"
        f"   💳 Корт: <code>{esc(req.card or '—')}</code>\n"
        f"   👤 Ном: <b>{esc(req.holder or '—')}</b>\n\n"
        f"📱 <b>Alif Mobi</b> — {alif_state}\n"
        f"   🔢 Ҳисоб: <code>{esc(req.alif_account or '—')}</code>\n\n"
        "<i>Ҳаволаҳои пардохт худкор сохта мешаванд — маблағ ва коди тасдиқ "
        "дар онҳо аллакай пур мешаванд.</i>"
    )


def admin_settings(
    channels: int, review_channel: str, whatsapp: str, api: dict | None = None
) -> str:
    text = (
        "⚙️ <b>Танзимот</b>\n\n"
        f"📢 Каналҳои обунаи ҳатмӣ: <b>{channels}</b>\n"
        f"💬 Канали шарҳҳо: <code>{esc(review_channel or '—')}</code>\n"
        f"🟢 WhatsApp: <code>{esc(whatsapp or '—')}</code>"
    )
    if api is not None:
        state = "✅ фаъол" if api.get("open") else "🚫 хомӯш"
        text += (
            f"\n\n🔌 API барои барномасозон: <b>{state}</b>\n"
            f"   калидҳо: <b>{api.get('keys', 0)}</b> · фармоишҳо имрӯз: "
            f"<b>{api.get('orders_today', 0)}</b> · ҳамагӣ: <b>{api.get('orders', 0)}</b>"
        )
        if "markup" in api:
            stamp = (api.get("costs_at") or "")[:16].replace("T", " ") or "ҳанӯз не"
            text += (
                f"\n   💹 нарх: нархи харид <b>+{api['markup']:g}%</b> "
                f"(нархи харид нав шуд: {esc(stamp)})"
            )
        if api.get("url"):
            text += f"\n   📖 {esc(api['url'])}"
    return text


def admin_channels(rows: list) -> str:
    if not rows:
        return (
            "📢 <b>Каналҳои обунаи ҳатмӣ</b>\n\n"
            "Ҳоло канал нест — бот ба ҳама кушода аст.\n\n"
            "<i>Пас аз илова кардан, то обуна нашудан бот кор намекунад.</i>"
        )
    lines = [f"📢 <b>Каналҳои обунаи ҳатмӣ</b> ({len(rows)})\n"]
    for row in rows:
        name = esc(row["title"] or row["chat_id"])
        lines.append(f"• <b>{name}</b> — <code>{esc(row['chat_id'])}</code>")
    lines.append("\n<i>Бот бояд дар ҳар канал админ бошад.</i>")
    return "\n".join(lines)


def admin_users(total: int, with_money: list, money_sum: int, currency: str = CURRENCY) -> str:
    lines = [
        "👥 <b>Корбарон</b>\n",
        f"Ҳамагӣ: <b>{total}</b>",
        f"Бо маблағ дар ҳисоб: <b>{len(with_money)}</b>",
        f"Дар ҳисобҳо ҷамъ: <b>{money(money_sum, currency)}</b>",
    ]
    if with_money:
        lines.append("\n<b>Онҳое, ки маблағ доранд:</b>")
        for user in with_money[:25]:
            name = esc(user.first_name or "—")
            tag = f"@{esc(user.username)}" if user.username else f"<code>{user.id}</code>"
            lines.append(f"• {name} {tag} — <b>{money(user.balance, currency)}</b>")
        if len(with_money) > 25:
            lines.append(f"<i>… ва боз {len(with_money) - 25} нафар</i>")
    return "\n".join(lines)


def admin_groups(rows: list) -> str:
    return "🗂 <b>Зербахшҳо</b>\n\nБарои иваз кардани ном яке аз онҳоро интихоб кунед."


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


def admin_user_card(
    user, orders: list, topups: list, currency: str = CURRENCY, partner: bool = False
) -> str:
    status = "🚫 Маҳдуд" if user.is_blocked else "✅ Фаъол"
    lines = [
        "👤 <b>Корти корбар</b>" + ("  🤝 <b>ШАРИК</b>" if partner else "") + "\n",
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
        f"🧾 <b>Фармоиши #{row['id']}</b>"
        + (" · 🔌 API" if "source" in row.keys() and row["source"] == "api" else "")
        + "\n\n"
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


ADMIN_ASK_RATE = (
    "💱 Курси доллар ба сомониро нависед.\n\n"
    "Намуна: <code>11</code> ё <code>11.20</code>\n"
    "<i>Он танҳо барои ҳисоби нархи харид дар панел истифода мешавад.</i>"
)


def cost_line(cost_milli: int | None, price: int, rate: float, currency: str = CURRENCY) -> str:
    """Нархи харид, ҳамон дар сомонӣ ва фоидаи шумо."""
    if not cost_milli:
        return "🏷 Нархи харид: <i>номаълум</i> — тугмаи «🔄» -ро пахш кунед"
    usd = cost_milli / 1000
    in_somoni = round(usd * rate * 100)          # дирам
    line = (
        f"🏷 Нархи харид: <b>{usd:.3f} $</b> ≈ {money(in_somoni, currency)}"
    )
    if in_somoni <= 0:
        return line
    profit = price - in_somoni
    percent = profit / in_somoni * 100
    if profit < 0:
        line += f"\n🔴 <b>ЗАРАР: {money(profit, currency)}</b> — нархро баланд кунед!"
    else:
        line += f"\n💚 Фоида: <b>{money(profit, currency)}</b> ({percent:+.0f}%)"
    return line


def wholesale_line(wholesale: int | None, price: int, currency: str = CURRENCY) -> str:
    """Боти шарик: нархи яклухт ва фоидаи шарик аз ҳар фурӯш."""
    if wholesale is None:
        return "🏷 Нархи яклухт: <i>нест</i> — платформа ин молро ҳоло намефурӯшад"
    line = f"🏷 Нархи яклухт: <b>{money(wholesale, currency)}</b>"
    profit = price - wholesale
    if profit < 0:
        return line + f"\n🔴 <b>ЗАРАР: {money(profit, currency)}</b> — нархро баланд кунед!"
    percent = profit / wholesale * 100 if wholesale else 0
    return line + f"\n💚 Фоидаи шумо: <b>{money(profit, currency)}</b> ({percent:+.0f}%)"


ADMIN_ASK_MARKUP = (
    "📈 Фоизи илова ба нархи харидро нависед.\n\n"
    "Намуна: <code>20</code> — яъне нарх = харид + 20%\n"
    "<i>Он ҳангоми илова кардани бозии нав истифода мешавад.</i>"
)


def admin_add_game(families: list, rate: float, markup: int) -> str:
    """Экрани интихоби бозии нав аз каталоги таъминкунанда."""
    if not families:
        return (
            "➕ <b>Бозии нав</b>\n\n"
            "Ҳамаи бозиҳои таъминкунанда аллакай дар бот ҳастанд. 👍"
        )
    return (
        "➕ <b>Бозии нав аз таъминкунанда</b>\n\n"
        f"Ёфт шуд: <b>{len(families)}</b> бозӣ, ки ҳанӯз дар бот нест.\n\n"
        f"💱 Курс: <b>{rate:g}</b> с. = 1 $\n"
        f"📈 Фоиз: <b>+{markup}%</b>\n\n"
        "Бозиро интихоб кунед — бот ҳамаи молҳои онро месозад ва нархҳоро "
        "аз нархи харид ҳисоб мекунад.\n\n"
        "<i>Молҳои нав хомӯш меоянд — аввал нархҳоро санҷед.</i>"
    )


def game_added(title: str, added: int, skipped: int, rate: float, markup: int) -> str:
    extra = f"\n<i>{skipped} мол аллакай буд.</i>" if skipped else ""
    return (
        f"✅ <b>{esc(title)}</b> илова шуд!\n\n"
        f"📦 Молҳои нав: <b>{added}</b>{extra}\n"
        f"💰 Нархҳо: харид × {rate:g} + {markup}%\n\n"
        "Ҳоло онҳо <b>хомӯш</b>-анд.\n"
        "Нархҳоро санҷед ва зербахшро фаъол кунед — баъд харидорон "
        "тугмаи «🎮 Дигар бозиҳо»-ро мебинанд."
    )


def admin_prices(rows: list, cat_title: str, currency: str = CURRENCY) -> str:
    return (
        f"💲 <b>Нархҳо — {esc(cat_title)}</b>\n\n"
        "Молро барои иваз кардани нарх интихоб кунед.\n\n"
        "🔴 — бо зарар фурӯхта мешавад\n"
        "🚫 — хомӯш"
    )


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


# ── API барои барномасозон ────────────────────────────────────────────
BTN_API_NEW = "🔑 Калид сохтан"
BTN_API_RENEW = "♻️ Калиди нав"
BTN_API_REVOKE = "🗑 Калидро бекор кардан"
BTN_API_DOCS = "📖 Ҳуҷҷатҳо"
BTN_API_YES_RENEW = "✅ Ҳа, калиди нав созед"
BTN_API_YES_REVOKE = "✅ Ҳа, бекор кунед"


def api_screen(key, balance: int, url: str, is_open: bool, currency: str = CURRENCY) -> str:
    """Экрани «🔌 API» барои харидор."""
    head = (
        "🔌 <b>API барои барномасозон</b>\n\n"
        "<blockquote>Боти ё сайти шумо метавонад аз мо <b>худкор</b> харид кунад: "
        "алмоси Free Fire, UC-и PUBG, Telegram Stars ва Premium — аз ҳамин ҳисоб."
        "</blockquote>\n\n"
        f"💳 Ҳисоб: <b>{money(balance, currency)}</b>\n"
    )
    if not is_open:
        return head + "\n🚫 <b>API ҳоло хомӯш аст.</b> Каме дертар бинед."
    if key is None:
        body = "🔑 Калид: <i>ҳанӯз нест</i>\n\nБарои оғоз «🔑 Калид сохтан»-ро пахш кунед."
    else:
        used = (key["last_used_at"] or "")[:16].replace("T", " ") or "ҳанӯз не"
        body = (
            f"🔑 Калид: <code>{esc(key['hint'])}</code>\n"
            f"📅 Сохта шуд: {esc(key['created_at'][:16].replace('T', ' '))}\n"
            f"🕐 Охирин истифода: {esc(used)}"
        )
    body += "\n\n💲 Нархҳо дар API махсус ҳастанд — рӯйхаташ дар <code>/products</code>."
    if url:
        body += f"\n\n📖 Ҳуҷҷатҳо (бо забони русӣ):\n{esc(url)}"
    return head + body


def api_key_created(plain: str) -> str:
    return (
        "✅ <b>Калиди API сохта шуд</b>\n\n"
        f"<code>{esc(plain)}</code>\n\n"
        "⚠️ <b>Онро ҳозир нусха бардоред</b> — бори дигар нишон дода намешавад.\n\n"
        "🔒 Калидро ба касе надиҳед: бо он аз ҳисоби шумо харид кардан мумкин аст. "
        "Агар ба дасти бегона афтад — «♻️ Калиди нав»-ро пахш кунед, калиди кӯҳна "
        "фавран кор намекунад."
    )


API_CONFIRM_RENEW = (
    "♻️ <b>Калиди нав созем?</b>\n\n"
    "Калиди ҳозира <b>фавран кор намекунад</b> — барномаҳое, ки бо он кор мекунанд, "
    "то иваз кардани калид харид карда наметавонанд.\n"
    "Ҳисоб ва фармоишҳо ҷои худ мемонанд."
)
API_CONFIRM_REVOKE = (
    "🗑 <b>Калидро бекор кунем?</b>\n\n"
    "Пас аз ин ҳеҷ барнома бо калиди шумо харид карда наметавонад. "
    "Ҳар вақт калиди нав сохтан мумкин аст."
)
API_REVOKED = "🗑 Калид бекор шуд."
API_CLOSED = "API ҳоло хомӯш аст."

ADMIN_ASK_API_MARKUP = (
    "💹 <b>Наценкаи API</b>\n\n"
    "Нархи API = нархи хариди таъминкунанда × курси доллар + ин фоиз.\n"
    "Фоизро нависед. Намуна: <code>5</code> ё <code>10</code>\n\n"
    "<i>Нархҳои бот тағйир намеёбанд — ин танҳо барои харидорони API.</i>"
)


# ══ Конструктор ═══════════════════════════════════════════════════════
BTN_CONSTRUCTOR = "🤖 Боти худро созед"
BTN_NEW_BOT = "➕ Боти нав пайваст кардан"
BTN_TOPUP_WHOLESALE = "💳 Пур кардани ҳисоби яклухт"
ADM_BTN_CONSTRUCTOR = "🏗 Конструктор"

TENANT_STATUS = {
    "active": "🟢 кор мекунад",
    "paused": "⏸ хомӯш (худатон)",
    "blocked": "🚫 баста (соҳиби платформа)",
    "disabled": "🔴 токен кор намекунад",
    "expired": "💳 обуна тамом шуд — пардохт кунед",
}
LANG_TITLE = {"tj": "🇹🇯 Тоҷикӣ", "ru": "🇷🇺 Русӣ"}


def _date(stamp) -> str:
    """2026-11-25T08:00:00+00:00 → 25.11.2026"""
    if stamp is None:
        return "—"
    if isinstance(stamp, str):
        try:
            stamp = datetime.fromisoformat(stamp)
        except ValueError:
            return esc(stamp)
    return stamp.strftime("%d.%m.%Y")


def sub_line(row, exempt: bool) -> str:
    """Як сатр дар бораи обунаи бот."""
    if exempt:
        return "♾ Обуна: бепул (соҳиби платформа)"
    until = row["paid_until"] if "paid_until" in row.keys() else None
    auto = " · 🔄 пардохти худкор" if row["auto_renew"] else ""
    if row["status"] == "expired" or not until:
        return "💳 Обуна: <b>пардохт нашудааст</b>" + auto
    return f"📅 Обуна то: <b>{_date(until)}</b>{auto}"


def constructor_home(rows: list, balance: int, can_add: bool, limit: int,
                     currency: str = CURRENCY, *, sub_price: int | None = None) -> str:
    lines = [
        "🤖 <b>Ботҳои ман</b>\n",
        "<blockquote>Боти худро пайваст кунед — дӯкони тайёр бо номи худ, нархҳои худ "
        "ва реквизитҳои худ. Фармоишҳо худкор иҷро мешаванд.</blockquote>\n",
        f"💳 Ҳисоби яклухт: <b>{money(balance, currency)}</b>",
        "<i>Аз ин ҳисоб нархи яклухти ҳар фармоиши боти шумо гирифта мешавад.</i>\n",
    ]
    if rows:
        for row in rows:
            name = f"@{row['username']}" if row["username"] else f"#{row['id']}"
            lines.append(f"• {esc(name)} — {TENANT_STATUS.get(row['status'], row['status'])}")
    else:
        lines.append("Ҳоло бот надоред.")
    lines.append(f"\n📦 Ботҳо: <b>{len(rows)}</b> аз <b>{limit}</b>")
    if sub_price:
        lines.append(f"💳 Обуна: <b>{money(sub_price, currency)}</b> барои ҳар бот дар як моҳ")
    if not can_add and len(rows) < limit:
        lines.append("<i>Ҳадди ботҳои платформа пур аст.</i>")
    return "\n".join(lines)


def sub_pay_confirm(row, cost: int, balance: int, until_after: str,
                    currency: str = CURRENCY) -> str:
    name = f"@{row['username']}" if row["username"] else f"#{row['id']}"
    enough = balance >= cost
    return (
        f"💳 <b>Обунаи боти {esc(name)}</b>\n\n"
        f"💵 Нарх: <b>{money(cost, currency)}</b> барои 30 рӯз\n"
        f"💳 Ҳисоби шумо: <b>{money(balance, currency)}</b>\n"
        f"📅 Пас аз пардохт — то <b>{_date(until_after)}</b>\n\n"
        + ("Маблағ аз ҳисоби шумо гирифта мешавад." if enough
           else f"🔴 Маблағ кофӣ нест — аввал ҳисобро {money(cost - balance, currency)} пур кунед.")
    )


def sub_paid(name: str, until: str) -> str:
    return (f"✅ <b>Обуна пардохт шуд</b>\n\n🤖 @{esc(name)} кор мекунад то "
            f"<b>{_date(until)}</b>.")


def sub_renewed(name: str, cost: int, until: str, currency: str = CURRENCY) -> str:
    return (
        f"🔄 <b>Обунаи @{esc(name)} худкор дароз шуд</b>\n\n"
        f"➖ {money(cost, currency)} аз ҳисоби шумо\n"
        f"📅 Акнун то <b>{_date(until)}</b>"
    )


def sub_expired(name: str, cost: int, currency: str = CURRENCY) -> str:
    return (
        f"⛔️ <b>Обунаи @{esc(name)} тамом шуд — бот хомӯш шуд</b>\n\n"
        f"Барои боз фаъол кардан {money(cost, currency)} пардохт кунед: "
        "«🤖 Ботҳои ман» → бот → «💳 Пардохти обуна».\n"
        "Маълумоти бот (харидорон, ҳисобҳо, нархҳо) нигоҳ дошта шудааст."
    )


def sub_reminder(name: str, until, cost: int, auto: bool, balance: int,
                 currency: str = CURRENCY) -> str:
    head = f"⏰ <b>Обунаи @{esc(name)} то {_date(until)} тамом мешавад</b>\n\n"
    if auto and balance >= cost:
        return head + f"🔄 Пардохти худкор фаъол аст — {money(cost, currency)} худкор гирифта мешавад."
    if auto:
        return head + (
            f"🔄 Пардохти худкор фаъол аст, аммо дар ҳисоб {money(balance, currency)} аст — "
            f"барои {money(cost, currency)} кофӣ нест. Ҳисобро пур кунед, вагарна бот хомӯш мешавад."
        )
    return head + (
        f"💳 Барои давом {money(cost, currency)} пардохт кунед: «🤖 Ботҳои ман» → бот → "
        "«💳 Пардохти обуна». Ё пардохти худкорро фаъол кунед."
    )


SUB_NOT_ENOUGH = "Маблағ кофӣ нест — аввал ҳисобро пур кунед."
ADMIN_ASK_SUB_PRICE = (
    "💳 <b>Нархи обунаи моҳонаи конструктор</b>\n\n"
    "Барои ҳар бот дар 30 рӯз. <code>0</code> — бепул.\nНамуна: <code>50</code>"
)


ASK_BOT_TOKEN = (
    "🔑 <b>Токени боти худро фиристед</b>\n\n"
    "1. Ба @BotFather нависед ва <code>/newbot</code>-ро пахш кунед.\n"
    "2. Ном ва username-и ботро гузоред.\n"
    "3. BotFather токен медиҳад, масалан:\n"
    "<code>123456789:AAH...</code>\n"
    "4. Онро ҳамин ҷо фиристед.\n\n"
    "<i>Токенро ба каси дигар надиҳед.</i>"
)
BAD_TOKEN = "❌ Ин ба токени бот монанд нест. Намуна: <code>123456789:AAH...</code>"
TOKEN_REJECTED = "❌ Telegram ин токенро қабул накард. Аз @BotFather токени навро гиред."
BOT_ALREADY_ADDED = "❌ Ин бот аллакай ба платформа пайваст аст."
BOT_IS_MAIN = "❌ Ин худи боти асосӣ аст — боти дигари худро созед."
BOT_LIMIT = "❌ Ба шумо зиёда аз ин миқдор бот иҷозат нест."
CONSTRUCTOR_CLOSED = "🚫 Конструктор ҳоло хомӯш аст."
CONSTRUCTOR_NO_ACCESS = (
    "🔒 Конструктор танҳо бо иҷозати соҳиби платформа.\n"
    "Ба дастгирӣ нависед, то ба шумо дастрасӣ диҳанд."
)


def bot_created(username: str) -> str:
    return (
        "✅ <b>Боти шумо тайёр аст!</b>\n\n"
        f"🤖 @{esc(username)}\n\n"
        "<b>Қадамҳои навбатӣ:</b>\n"
        f"1. Ботро кушоед: t.me/{esc(username)} ва /start-ро пахш кунед.\n"
        "2. Дар он <code>/admin</code> нависед — шумо админ ҳастед.\n"
        "3. ⚙️ Танзимот → реквизитҳои худро гузоред (корт, Alif).\n"
        "4. Наценка ва нархҳоро бинед — нархҳо аллакай худкор гузошта шудаанд.\n"
        "5. Ҳисоби яклухтро пур кунед — бе он фармоишҳо иҷро намешаванд."
    )


def tenant_screen(row, sales: dict, balance: int, currency: str = CURRENCY, *,
                  exempt: bool = False, sub_price: int = 0) -> str:
    name = f"@{row['username']}" if row["username"] else f"#{row['id']}"
    return (
        f"🤖 <b>{esc(name)}</b>\n\n"
        f"📶 Ҳолат: {TENANT_STATUS.get(row['status'], row['status'])}\n"
        f"🌐 Забон: {LANG_TITLE.get(row['lang'], row['lang'])}\n"
        f"🧾 Фармоишҳои иҷрошуда: <b>{sales['orders']}</b>\n"
        f"💰 Харидҳои яклухт: <b>{money(sales['revenue'], currency)}</b>\n"
        f"💳 Ҳисоби яклухт: <b>{money(balance, currency)}</b>\n"
        f"{sub_line(row, exempt)}\n"
        + ("" if exempt else f"💵 Нархи обуна: {money(sub_price, currency)} / {30} рӯз\n")
        + f"\n🔗 t.me/{esc(row['username'] or '')}"
    )


def tenant_token_revoked(username: str) -> str:
    return (
        f"🔴 <b>Боти @{esc(username)} хомӯш шуд</b>\n\n"
        "Telegram токени онро қабул намекунад (токен бекор шуд ё бот нест карда шуд).\n"
        "Дар «🤖 Ботҳои ман» токени навро гузоред — бот бо ҳамаи харидорон ва "
        "фармоишҳо боз кор мекунад."
    )


def partner_low_balance(balance: int, currency: str = CURRENCY) -> str:
    return (
        "⚠️ <b>Ҳисоби яклухт кам монд</b>\n\n"
        f"💳 Боқимонда: <b>{money(balance, currency)}</b>\n"
        "Ҳисобро пур кунед — вагарна фармоишҳои харидорони боти шумо иҷро намешаванд."
    )


def partner_empty_balance(balance: int, currency: str = CURRENCY) -> str:
    return (
        "🚨 <b>Фармоиш иҷро нашуд — ҳисоби яклухт кофӣ нест</b>\n\n"
        f"💳 Боқимонда: <b>{money(balance, currency)}</b>\n"
        "Пули харидор худкор баргардонида шуд. Ҳисобро пур кунед: "
        "«💳 Пур кардани ҳисоб» дар боти асосӣ."
    )


# ── соҳиби платформа ──
def admin_constructor(is_open: bool, tenants: int, active: int, partners: int,
                      markup: float, max_bots: int, *, sub_price: int = 0,
                      income: tuple[int, int] = (0, 0), expired: int = 0) -> str:
    return (
        admin_constructor_head(is_open, tenants, active, partners, markup, max_bots)
        + f"\n\n💳 Обуна: <b>{money(sub_price)}</b> / 30 рӯз барои ҳар бот"
        + (f"\n⛔️ Обуна тамом: {expired} бот" if expired else "")
        + f"\n💰 Обунаҳо дар 30 рӯз: {income[0]} пардохт, <b>{money(income[1])}</b>"
    )


def admin_constructor_head(is_open: bool, tenants: int, active: int, partners: int,
                           markup: float, max_bots: int) -> str:
    return (
        "🏗 <b>Конструктор</b>\n\n"
        f"📶 Ҳолат: <b>{'✅ фаъол' if is_open else '🚫 хомӯш'}</b>\n"
        f"🤖 Ботҳо: <b>{tenants}</b> (кор мекунанд: {active}) · ҳадди аксар: {max_bots}\n"
        f"👥 Шарикон бо дастрасӣ: <b>{partners}</b>\n"
        f"💹 Наценкаи яклухт: <b>+{markup:g}%</b> аз нархи харид\n\n"
        "<i>Шарик аз ҳисоби худ нархи яклухт мепардозад, ба харидорони худ бо "
        "нархи худ мефурӯшад.</i>"
    )


ADMIN_ASK_ACCESS = (
    "👥 ID-и Telegram ё @username-и шарикро нависед.\n"
    "Агар ба ӯ зиёда аз як бот иҷозат бошад — баъд аз фосила рақам:\n"
    "<code>123456789 3</code>"
)
ADMIN_ASK_C_MARKUP = (
    "💹 <b>Наценкаи яклухт барои конструктор</b>\n\n"
    "Нархи яклухт = нархи харид × курс + ин фоиз.\n"
    "Намуна: <code>10</code>"
)
ADMIN_ASK_MAX_BOTS = "🔢 Ҳадди аксари ботҳои шарикон дар платформа. Намуна: <code>50</code>"


def admin_c_partners(rows: list, currency: str = CURRENCY) -> str:
    if not rows:
        return "👥 <b>Шарикони конструктор</b>\n\nҲоло касе дастрасӣ надорад."
    lines = ["👥 <b>Шарикони конструктор</b>\n"]
    for row in rows[:LIST_CAP]:
        who = f"@{row['username']}" if row["username"] else (row["first_name"] or "")
        lines.append(
            f"• <code>{row['user_id']}</code> {esc(who)} — ботҳо {row['bots']}/{row['max_bots']}, "
            f"ҳисоб {money(row['balance'] or 0, currency)}"
        )
    return "\n".join(lines) + _more(rows)


def admin_tenants(rows: list) -> str:
    if not rows:
        return "🤖 <b>Ботҳои шарикон</b>\n\nҲоло бот нест."
    lines = ["🤖 <b>Ботҳои шарикон</b>\n"]
    for row in rows[:LIST_CAP]:
        until = row["paid_until"] if "paid_until" in row.keys() else None
        lines.append(
            f"• @{esc(row['username'] or '?')} — шарик <code>{row['owner_id']}</code> — "
            f"{TENANT_STATUS.get(row['status'], row['status'])}"
            + (f" · то {_date(until)}" if until else "")
            + (" · 🔄" if row["auto_renew"] else "")
        )
    return "\n".join(lines) + _more(rows)


def tenant_delete_confirm(row, stats: dict | None, sales: dict, currency: str = CURRENCY) -> str:
    name = f"@{row['username']}" if row["username"] else f"#{row['id']}"
    lines = [
        f"🗑 <b>Боти {esc(name)}-ро пурра нест кунем?</b>\n",
        f"👤 Шарик: <code>{row['owner_id']}</code>",
        f"📶 Ҳолат: {TENANT_STATUS.get(row['status'], row['status'])}",
    ]
    if stats:
        lines += [
            f"👥 Харидорон: <b>{stats['users']}</b>",
            f"💳 Пул дар ҳисобҳои харидорон: <b>{money(stats['balance'], currency)}</b>",
            f"🧾 Фармоишҳо: {stats['orders']} (кушода: <b>{stats['orders_open']}</b>)",
        ]
    lines += [
        f"💰 Харидҳои яклухт: {sales['orders']} фармоиш, {money(sales['revenue'], currency)}",
        "",
        "⚠️ <b>Ин амал баргашт надорад.</b> Бот хомӯш мешавад, базаи он (харидорон, "
        "ҳисобҳо, фармоишҳо, нархҳо, танзимот) аз сервер пок мешавад.",
        "📦 Пеш аз нест кардан нусхаи база ба шумо ҳамчун файл фиристода мешавад.",
        "<i>Ҳисоби яклухти шарик дар боти асосӣ ва дастрасии ӯ ба конструктор мемонад.</i>",
    ]
    if stats and (stats["orders_open"] or stats["balance"]):
        lines.insert(-3, "🔴 <b>Дар бот пул ё фармоишҳои кушода ҳаст</b> — аввал бо шарик ҳал кунед.")
    return "\n".join(lines)


def tenant_deleted(username: str) -> str:
    return f"🗑 Боти @{esc(username)} пурра нест карда шуд."


def tenant_deleted_partner(username: str) -> str:
    return (
        f"🗑 <b>Боти @{esc(username)} аз платформа нест карда шуд.</b>\n\n"
        "Ҳисоби яклухти шумо дар ин бот мемонад. Саволҳо бошад — ба дастгирӣ нависед."
    )


TENANT_BUSY = "⏳ Дар ин бот ҳоло фармоиш иҷро мешавад. Пас аз 1–2 дақиқа боз кӯшиш кунед."


# ── боти шарик: панели админ ──
ADMIN_ASK_PARTNER_MARKUP = (
    "💹 <b>Наценкаи шумо</b>\n\n"
    "Нархи фурӯш = нархи яклухт + ин фоиз (ба боло то 0.50 сомонӣ).\n"
    "Ба молҳое, ки нархашонро дастӣ гузоштед, таъсир намекунад.\n\n"
    "Намуна: <code>15</code>"
)
ADMIN_ASK_OPERATOR = "👥 ID-и Telegram-и операторро нависед (ӯ бояд аввал ботро /start кунад)."
ADMIN_ASK_SUPPORT = "🎧 Username-и дастгирӣ (бе @) ё <code>-</code> барои хомӯш кардан."
ADMIN_ASK_PRODUCT_TITLE = "✏️ Номи нави молро нависед (то 60 аломат)."
ADMIN_ASK_LOW_BALANCE = (
    "🔔 Вақте ҳисоби яклухт аз ин маблағ кам шавад, огоҳ мекунем.\n"
    "Намуна: <code>50</code>"
)


def tenant_settings(markup: float, operators: tuple, support: str, lang: str,
                    low: int, balance: int, currency: str = CURRENCY) -> str:
    ops = ", ".join(f"<code>{o}</code>" for o in operators) or "—"
    return (
        "\n\n🤖 <b>Боти шумо</b>\n"
        f"💹 Наценка: <b>+{markup:g}%</b> аз нархи яклухт\n"
        f"💳 Ҳисоби яклухт: <b>{money(balance, currency)}</b> "
        f"(огоҳӣ аз {money(low, currency)})\n"
        f"👥 Операторон: {ops}\n"
        f"🎧 Дастгирӣ: {('@' + esc(support)) if support else '—'}\n"
        f"🌐 Забон: {LANG_TITLE.get(lang, lang)}"
    )


# ── нархҳо барои API ва конструктор ───────────────────────────────────
BTN_PRICES = "💰 Нархҳои шумо (API / яклухт)"
BTN_PRICES_SHORT = "💰 Нархҳо"
BTN_WHOLESALE_LIST = "💰 Нархи яклухт ва фоида"


def _price_kinds(api: bool, whole: bool) -> str:
    if api and whole:
        return "🔌 <b>API</b> — нархи харид тавассути API\n🤖 <b>Яклухт</b> — нархе, ки аз боти шумо гирифта мешавад"
    if api:
        return "🔌 Нархи харид тавассути API (аз ҳисоби шумо)"
    return "🤖 Нархи яклухт — ҳар фармоиши боти шумо аз ҳисоби шумо ҳамин қадар мегирад"


def prices_home(cats: list, balance: int, api: bool, whole: bool, updated: str | None,
                currency: str = CURRENCY) -> str:
    lines = [
        "💰 <b>Нархҳои шумо</b>\n",
        _price_kinds(api, whole) + "\n",
        f"💳 Ҳисоб: <b>{money(balance, currency)}</b>",
    ]
    if updated:
        lines.append(f"🔄 Нархҳо нав шуданд: {esc(updated[:16].replace('T', ' '))} (UTC)")
    lines.append("<i>Нархҳо худкор аз нархи харид ҳисоб мешаванд.</i>\n")
    if not cats:
        lines.append("Ҳоло моли нархдор нест.")
    else:
        for code, count in cats:
            info = catalog.CATEGORY_INFO[code]
            lines.append(f"{info.icon} {esc(info.title)} — {count} мол")
        lines.append("\nБахшро интихоб кунед 👇")
    return "\n".join(lines)


def price_lines(category: str, rows: list, api: bool, whole: bool,
                currency: str = CURRENCY) -> list[str]:
    """Сатрҳои рӯйхат: «• 60 UC — 10.50 · pubg_60», бо сарлавҳаи зербахшҳо."""
    info = catalog.CATEGORY_INFO[category]
    lines = [f"{info.icon} <b>{esc(info.title)}</b>"]
    if api and whole:
        lines.append("<i>🔌 API · 🤖 яклухт</i>")
    group = None
    for item in rows:
        if item.group != group:
            group = item.group
            if group:
                lines.append(f"\n<b>{esc(group)}</b>")
        parts = []
        if api and item.api is not None:
            parts.append(("🔌 " if whole else "") + f"<b>{money(item.api, currency)}</b>")
        if whole and item.wholesale is not None:
            parts.append(("🤖 " if api else "") + f"<b>{money(item.wholesale, currency)}</b>")
        line = f"• {esc(item.title)} — {' · '.join(parts)}"
        if api:
            line += f" · <code>{esc(item.code)}</code>"
        lines.append(line)
    if api:
        lines.append("\n<i><code>код</code> — барои майдони «product» дар API.</i>")
    return lines


def wholesale_lines(category: str, rows: list, currency: str = CURRENCY) -> list[str]:
    """Боти шарик: яклухт → нархи шумо → фоида, барои ҳар мол."""
    info = catalog.CATEGORY_INFO[category]
    lines = [f"{info.icon} <b>{esc(info.title)}</b>",
             "<i>яклухт → нархи шумо (фоида)</i>"]
    for row in rows:
        whole, price = row["wholesale"], row["price"]
        if whole is None:
            lines.append(f"⛔ {esc(row['title'])} — платформа намефурӯшад")
            continue
        profit = price - whole
        mark = "🔴" if profit < 0 else ("🚫" if not row["active"] else "•")
        lines.append(
            f"{mark} {esc(row['title'])} — {money(whole, currency)} → "
            f"<b>{money(price, currency)}</b> ({'+' if profit >= 0 else ''}{money(profit, currency)})"
        )
    return lines


WHOLESALE_LIST_HEAD = (
    "💰 <b>Нархи яклухт ва фоидаи шумо</b>\n\n"
    "🔴 — бо зарар · 🚫 — хомӯш · ⛔ — платформа ҳоло намефурӯшад\n"
    "Нархро дар «💲 Нархҳо» иваз кунед.\n\nБахшро интихоб кунед 👇"
)
