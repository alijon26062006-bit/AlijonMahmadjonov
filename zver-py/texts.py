"""Тексты бота.

Полностью переведены таджикский, русский и английский — на них говорит
подавляющее большинство пользователей ZVER TAJ. Для uz / ky / kk пока
берётся русский: лучше показать понятный русский, чем кривой перевод
в боте, через который идут деньги. Добавить язык просто — скопируйте
блок RU, переведите значения и впишите код в LANGS.
"""
from __future__ import annotations

LANGS: dict[str, str] = {
    "tj": "Тоҷикӣ",
    "ru": "Русский",
    "uz": "O'zbekcha",
    "ky": "Кыргызча",
    "en": "English",
    "kk": "Қазақша",
}

DEFAULT_LANG = "tj"

TJ = {
    "choose_lang":    "Забонро интихоб кунед:",
    "lang_saved":     "Забон иваз шуд ✅",

    "menu_buy":       "🎮 Харид",
    "menu_balance":   "💰 Ҳисоб",
    "menu_orders":    "📦 Фармоишҳо",
    "menu_lang":      "🌐 Забон",
    "menu_support":   "💬 Дастгирӣ",

    "greet":          "Салом, {name}!\nҲисоби шумо: <b>{balance} {cur}</b>",
    "menu_hint":      "Аз меню интихоб кунед:",

    "choose_game":    "Бозиро интихоб кунед:",
    "no_games":       "Ҳоло бозие нест. Каме дертар кӯшиш кунед.",
    "choose_pack":    "<b>{game}</b>\nПакетро интихоб кунед:",
    "no_packs":       "Барои ин бозӣ пакет нест.",

    "enter_id":       "<b>{game}</b> — {pack}\n\n{label}-и худро нависед:",
    "enter_server":   "Акнун {label} нависед:",
    "bad_id":         "Нодуруст. Дубора нависед:",

    "confirm":        ("<b>Тасдиқ кунед</b>\n\n"
                       "Бозӣ: {game}\nПакет: {pack}\n{id_label}: <code>{pid}</code>"
                       "{server}\n\nНарх: <b>{price} {cur}</b>\n"
                       "Ҳисоби шумо: {balance} {cur}"),
    "confirm_yes":    "✅ Тасдиқ",
    "confirm_no":     "✖️ Бекор",
    "cancelled":      "Бекор карда шуд.",

    "not_enough":     ("Маблағ нокифоя.\nЛозим: <b>{need} {cur}</b>\n"
                       "Дар ҳисоб: {balance} {cur}\n\nҲисобро пур кунед."),
    "order_created":  ("✅ Фармоиш қабул шуд, рақам <b>#{oid}</b>\n\n"
                       "{game} — {pack}\n{id_label}: <code>{pid}</code>\n"
                       "Нарх: {price} {cur}\n\nДар давоми 5–15 дақиқа иҷро мешавад."),

    "balance":        ("💰 Ҳисоби шумо: <b>{balance} {cur}</b>\n\n"
                       "Барои пур кардан тугмаро пахш кунед."),
    "topup_btn":      "➕ Пур кардан",
    "topup_amount":   "Чӣ қадар пур мекунед? Рақам нависед:",
    "topup_bad":      "Рақами дуруст нависед, масалан 50",
    "topup_min":      "Ҳадди ақал {min} {cur}",
    "topup_reqs":     ("Маблағ: <b>{amount} {cur}</b>\n\n"
                       "Ба ин корт интиқол диҳед:\n\n{reqs}\n\n"
                       "Баъд <b>расми чек</b>-ро фиристед."),
    "topup_no_reqs":  "Ҳоло реквизит нест. Ба дастгирӣ муроҷиат кунед.",
    "topup_wait_photo": "Расми чекро фиристед (ҳамчун сурат):",
    "topup_created":  ("✅ Дархост қабул шуд, рақам <b>#{tid}</b>\n"
                       "Баъди тасдиқ маблағ ба ҳисоб меафтад."),

    "orders_title":   "📦 Фармоишҳои охирин:",
    "orders_empty":   "Ҳанӯз фармоиш надоред.",

    "st_new":         "⏳ Дар навбат",
    "st_done":        "✅ Иҷро шуд",
    "st_rejected":    "❌ Рад шуд",

    "back":           "⬅️ Бозгашт",
    "blocked":        "Дастрасии шумо маҳдуд аст.",
    "support":        "Дастгирӣ: {support}",
    "err":            "Хатогӣ рӯй дод. Дубора кӯшиш кунед.",
    "n_done":        "✅ Фармоиши <b>#{oid}</b> иҷро шуд.\n{game} — {pack}",
    "n_rejected":    "❌ Фармоиши <b>#{oid}</b> рад карда шуд.",
    "n_refund":      "\nБа ҳисоб баргардонида шуд: <b>{amount} {cur}</b>.",
    "n_topup_ok":    ("✅ Ҳисоб пур шуд: <b>{amount} {cur}</b>.\n"
                      "Ҳоло дар ҳисоб: <b>{balance} {cur}</b>"),
    "n_topup_rej":   "❌ Дархости пуркунии <b>#{tid}</b> рад карда шуд.",
}

RU = {
    "choose_lang":    "Выберите язык:",
    "lang_saved":     "Язык изменён ✅",

    "menu_buy":       "🎮 Купить",
    "menu_balance":   "💰 Баланс",
    "menu_orders":    "📦 Заказы",
    "menu_lang":      "🌐 Язык",
    "menu_support":   "💬 Поддержка",

    "greet":          "Привет, {name}!\nВаш баланс: <b>{balance} {cur}</b>",
    "menu_hint":      "Выберите из меню:",

    "choose_game":    "Выберите игру:",
    "no_games":       "Пока нет доступных игр. Загляните позже.",
    "choose_pack":    "<b>{game}</b>\nВыберите пакет:",
    "no_packs":       "Для этой игры пока нет пакетов.",

    "enter_id":       "<b>{game}</b> — {pack}\n\nОтправьте ваш {label}:",
    "enter_server":   "Теперь отправьте {label}:",
    "bad_id":         "Не похоже на правильное значение. Отправьте ещё раз:",

    "confirm":        ("<b>Проверьте заказ</b>\n\n"
                       "Игра: {game}\nПакет: {pack}\n{id_label}: <code>{pid}</code>"
                       "{server}\n\nЦена: <b>{price} {cur}</b>\n"
                       "Ваш баланс: {balance} {cur}"),
    "confirm_yes":    "✅ Подтвердить",
    "confirm_no":     "✖️ Отмена",
    "cancelled":      "Отменено.",

    "not_enough":     ("Недостаточно средств.\nНужно: <b>{need} {cur}</b>\n"
                       "На балансе: {balance} {cur}\n\nПополните баланс."),
    "order_created":  ("✅ Заказ принят, номер <b>#{oid}</b>\n\n"
                       "{game} — {pack}\n{id_label}: <code>{pid}</code>\n"
                       "Цена: {price} {cur}\n\nОбычно выполняем за 5–15 минут."),

    "balance":        ("💰 Ваш баланс: <b>{balance} {cur}</b>\n\n"
                       "Чтобы пополнить, нажмите кнопку ниже."),
    "topup_btn":      "➕ Пополнить",
    "topup_amount":   "На какую сумму пополняете? Отправьте число:",
    "topup_bad":      "Отправьте число, например 50",
    "topup_min":      "Минимум {min} {cur}",
    "topup_reqs":     ("Сумма: <b>{amount} {cur}</b>\n\n"
                       "Переведите на эти реквизиты:\n\n{reqs}\n\n"
                       "После перевода пришлите <b>фото чека</b>."),
    "topup_no_reqs":  "Реквизиты пока не настроены. Напишите в поддержку.",
    "topup_wait_photo": "Пришлите фото чека (именно фотографией):",
    "topup_created":  ("✅ Заявка принята, номер <b>#{tid}</b>\n"
                       "После проверки деньги зачислим на баланс."),

    "orders_title":   "📦 Последние заказы:",
    "orders_empty":   "У вас пока нет заказов.",

    "st_new":         "⏳ В обработке",
    "st_done":        "✅ Выполнен",
    "st_rejected":    "❌ Отклонён",

    "back":           "⬅️ Назад",
    "blocked":        "Доступ ограничен.",
    "support":        "Поддержка: {support}",
    "err":            "Что-то пошло не так. Попробуйте ещё раз.",
    "n_done":        "✅ Заказ <b>#{oid}</b> выполнен.\n{game} — {pack}",
    "n_rejected":    "❌ Заказ <b>#{oid}</b> отклонён.",
    "n_refund":      "\nНа баланс возвращено <b>{amount} {cur}</b>.",
    "n_topup_ok":    ("✅ Баланс пополнен на <b>{amount} {cur}</b>.\n"
                      "Текущий баланс: <b>{balance} {cur}</b>"),
    "n_topup_rej":   "❌ Заявка на пополнение <b>#{tid}</b> отклонена.",
}

EN = {
    "choose_lang":    "Choose your language:",
    "lang_saved":     "Language changed ✅",

    "menu_buy":       "🎮 Buy",
    "menu_balance":   "💰 Balance",
    "menu_orders":    "📦 Orders",
    "menu_lang":      "🌐 Language",
    "menu_support":   "💬 Support",

    "greet":          "Hi, {name}!\nYour balance: <b>{balance} {cur}</b>",
    "menu_hint":      "Pick an option:",

    "choose_game":    "Choose a game:",
    "no_games":       "No games available yet. Check back later.",
    "choose_pack":    "<b>{game}</b>\nChoose a package:",
    "no_packs":       "No packages for this game yet.",

    "enter_id":       "<b>{game}</b> — {pack}\n\nSend your {label}:",
    "enter_server":   "Now send the {label}:",
    "bad_id":         "That doesn't look right. Send it again:",

    "confirm":        ("<b>Check your order</b>\n\n"
                       "Game: {game}\nPackage: {pack}\n{id_label}: <code>{pid}</code>"
                       "{server}\n\nPrice: <b>{price} {cur}</b>\n"
                       "Your balance: {balance} {cur}"),
    "confirm_yes":    "✅ Confirm",
    "confirm_no":     "✖️ Cancel",
    "cancelled":      "Cancelled.",

    "not_enough":     ("Not enough funds.\nNeeded: <b>{need} {cur}</b>\n"
                       "Balance: {balance} {cur}\n\nPlease top up."),
    "order_created":  ("✅ Order accepted, number <b>#{oid}</b>\n\n"
                       "{game} — {pack}\n{id_label}: <code>{pid}</code>\n"
                       "Price: {price} {cur}\n\nUsually done in 5–15 minutes."),

    "balance":        ("💰 Your balance: <b>{balance} {cur}</b>\n\n"
                       "Tap the button below to top up."),
    "topup_btn":      "➕ Top up",
    "topup_amount":   "How much do you want to add? Send a number:",
    "topup_bad":      "Send a number, for example 50",
    "topup_min":      "Minimum is {min} {cur}",
    "topup_reqs":     ("Amount: <b>{amount} {cur}</b>\n\n"
                       "Transfer to these details:\n\n{reqs}\n\n"
                       "Then send a <b>photo of the receipt</b>."),
    "topup_no_reqs":  "Payment details are not set up yet. Contact support.",
    "topup_wait_photo": "Send the receipt photo (as a photo):",
    "topup_created":  ("✅ Request accepted, number <b>#{tid}</b>\n"
                       "We'll credit your balance once it's checked."),

    "orders_title":   "📦 Recent orders:",
    "orders_empty":   "You have no orders yet.",

    "st_new":         "⏳ Pending",
    "st_done":        "✅ Completed",
    "st_rejected":    "❌ Rejected",

    "back":           "⬅️ Back",
    "blocked":        "Your access is restricted.",
    "support":        "Support: {support}",
    "err":            "Something went wrong. Please try again.",
    "n_done":        "✅ Order <b>#{oid}</b> is complete.\n{game} — {pack}",
    "n_rejected":    "❌ Order <b>#{oid}</b> was rejected.",
    "n_refund":      "\n<b>{amount} {cur}</b> refunded to your balance.",
    "n_topup_ok":    ("✅ Balance topped up by <b>{amount} {cur}</b>.\n"
                      "Current balance: <b>{balance} {cur}</b>"),
    "n_topup_rej":   "❌ Top-up request <b>#{tid}</b> was rejected.",
}

_TABLE: dict[str, dict[str, str]] = {
    "tj": TJ,
    "ru": RU,
    "en": EN,
    # ещё не переведены — показываем русский
    "uz": RU,
    "ky": RU,
    "kk": RU,
}


def t(lang: str | None, key: str, **kw) -> str:
    """Строка на нужном языке. Неизвестный язык или ключ не роняют бота."""
    table = _TABLE.get((lang or "").lower(), _TABLE[DEFAULT_LANG])
    raw = table.get(key) or _TABLE[DEFAULT_LANG].get(key) or key
    try:
        return raw.format(**kw) if kw else raw
    except (KeyError, IndexError, ValueError):
        return raw


def status_text(lang: str | None, status: str) -> str:
    return t(lang, {"new": "st_new", "done": "st_done"}.get(status, "st_rejected"))
