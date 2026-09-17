"""Все тексты бота в одном месте — на таджикском, как в исходной версии.

Отдельный файл нужен, чтобы менять формулировки, не трогая логику, и чтобы
случайно не потерять перевод внутри кода.
"""

from __future__ import annotations

COIN = "🪙"


def money(amount: int) -> str:
    """12345 → «12 345 🪙». Неразрывный пробел, чтобы сумма не рвалась."""

    return f"{amount:,}".replace(",", " ") + f" {COIN}"


START = (
    "💣 <b>MINES</b>\n\n"
    "Дар майдони 5×5 мина пинҳон аст. Ҳар як катаки холӣ — зарб зиёд мешавад.\n"
    "Мина зада — пул сӯхт. Пеш аз мина <b>💰 Гирифтан</b> зан — пул аз они ту.\n\n"
    "<b>Фармонҳо</b>\n"
    "/bet 100 — бозӣ бо сатҳи 100\n"
    "/mines 3 — шумораи минаҳо (1–24)\n"
    "/balance — баланси ту\n"
    "/bonus — тӯҳфаи ройгон\n"
    "/send 100 — ба ҷавоб (reply) пул фиристодан\n"
    "/top — беҳтаринҳо\n"
    "/stats — омори ту\n"
    "/help — ҳамин матн"
)

HELP = START

BALANCE = "💳 Баланс: <b>{balance}</b>"

NEED_NUMBER = "❌ Рақамро нависед. Мисол: <code>/bet 100</code>"
BET_RANGE = "❌ Сатҳ аз {low} то {high} мешавад."
NOT_ENOUGH = "❌ Баланс кофӣ нест.\n💳 Дар ту: {balance}\n💡 <code>/bonus</code> зан."
ALREADY_PLAYING = "⚠️ Ту аллакай бозӣ дорӣ. Аввал онро тамом кун."
MINES_RANGE = "❌ Минаҳо аз 1 то 24 мешавад."
MINES_SET = "💣 Минаҳо: <b>{mines}</b>. Ҳозир <code>/bet {bet}</code> зан."

GAME = (
    "💣 <b>MINES</b> · минаҳо: {mines}\n"
    "🎯 Сатҳ: {bet}\n"
    "📈 Зарб: <b>x{multiplier}</b>\n"
    "💰 Гирифтанӣ: <b>{payout}</b>"
)

TAKEN = (
    "💰 Ту <b>{payout}</b> гирифтӣ!\n"
    "📈 Зарб: x{multiplier} · сатҳ: {bet}\n\n"
    "💳 Баланс: <b>{balance}</b>"
)

CLEARED = (
    "🏆 Ҳамаи катакҳо кушода шуд!\n"
    "💰 Бурд: <b>{payout}</b> (x{multiplier})\n\n"
    "💳 Баланс: <b>{balance}</b>"
)

BOOM = (
    "💥 <b>МИНА!</b>\n"
    "❌ Сатҳи {stake} сӯхт.\n"
    "📈 Кушода будӣ: {opened} катак (x{multiplier})\n\n"
    "💳 Баланс: <b>{balance}</b>\n"
    "🔁 <code>/bet {bet}</code> — аз нав"
)

NOT_YOUR_GAME = "❌ Ин бозии ту нест!"
GAME_OVER = "❌ Бозӣ тамом шудааст."
CELL_TAKEN = "Ин катак кушода шудааст."
NOTHING_TO_TAKE = "❌ Ҳоло бурд надорӣ — аввал як катак кушо."
CELL_WIN = "💎 x{multiplier} · {payout}"

BONUS_OK = "🎁 Тӯҳфа: <b>{amount}</b>\n💳 Баланс: <b>{balance}</b>"
BONUS_WAIT = "⏳ Тӯҳфаи навбатӣ баъд аз <b>{minutes} дақиқа</b>.\n💳 Баланс: {balance}"

SEND_HOW = (
    "💸 Ба паёми одам <b>reply</b> кунед ва нависед: <code>/send 100</code>"
)
SEND_TO_BOT = "❌ Ба бот пул намефиристанд."
SEND_TO_SELF = "❌ Ба худат пул фиристода намешавад."
SEND_OK = "💸 <b>{amount}</b> ба {name} фиристода шуд!\n💳 Баланс: <b>{balance}</b>"
SEND_GOT = "💸 {name} ба ту <b>{amount}</b> фиристод!\n💳 Баланс: <b>{balance}</b>"

TOP_HEAD = "🏆 <b>Беҳтаринҳо</b>\n\n"
TOP_ROW = "{place}. {name} — <b>{balance}</b>\n"
TOP_EMPTY = "Ҳоло касе бозӣ накардааст."

STATS = (
    "📊 <b>Омори ту</b>\n\n"
    "🎮 Бозиҳо: {games}\n"
    "💰 Бурд: {won}\n"
    "💥 Бохт: {lost}\n"
    "📈 Ҳисоб: <b>{net}</b>\n\n"
    "💳 Баланс: <b>{balance}</b>"
)

ERROR = "⚠️ Хатогӣ шуд. Каме баъд аз нав кӯшиш кун."
PRIVATE_ONLY = "Ин фармон танҳо дар чати шахсӣ кор мекунад."
BUTTON_TAKE = "💰 Гирифтан · {payout}"
BUTTON_TAKE_EMPTY = "💰 Гирифтан"
