"""Тексты сообщений.

Собраны в одном месте, чтобы правки формулировок и оформления не растекались
по обработчикам. Оформление держится на трёх приёмах: разрядка заголовков,
тонкий разделитель между блоками и шкала голосов — так экран читается сразу,
без вчитывания в цифры.
"""
from __future__ import annotations

from datetime import datetime
from html import escape

from core.models import Slot

MEDAL = {1: "🥇", 2: "🥈", 3: "🥉"}
CROWN = "👑"
RULE = "─────────────────"

BAR_FULL = "▰"
BAR_EMPTY = "▱"
BAR_WIDTH = 10


# ----------------------------------------------------------------- оформление

def spaced(text: str) -> str:
    """«РАУНД» -> «Р А У Н Д» — заголовки как в канале."""
    return " ".join(text)


def nick(value: str) -> str:
    value = escape(value)
    return value if value.startswith("@") else f"@{value}"


def plural(count: int, one: str, few: str, many: str) -> str:
    """«1 голос», «2 голоса», «5 голосов»."""
    if count % 10 == 1 and count % 100 != 11:
        return one
    if 2 <= count % 10 <= 4 and not 12 <= count % 100 <= 14:
        return few
    return many


def votes_word(count: int) -> str:
    return f"{count} {plural(count, 'голос', 'голоса', 'голосов')}"


def bar(value: int, total: int, width: int = BAR_WIDTH) -> str:
    """Шкала голосов: доля участника от всех голосов матча."""
    if total <= 0:
        return BAR_EMPTY * width
    filled = round(value / total * width)
    filled = max(1, filled) if value else 0
    return BAR_FULL * filled + BAR_EMPTY * (width - filled)


def percent(value: int, total: int) -> int:
    return round(value / total * 100) if total else 0


def scoreboard(slots: list[Slot], show_place: bool = False) -> str:
    """Список участников со шкалами — сердце и голосования, и итогов."""
    total = sum(slot.votes for slot in slots) or 0
    best = max((slot.votes for slot in slots), default=0)

    lines = []
    for index, slot in enumerate(slots, start=1):
        mark = MEDAL.get(slot.position, f"{slot.position}.") if show_place else f"{index}."
        crown = f" {CROWN}" if not show_place and slot.votes == best and best else ""
        lines.append(
            f"<b>{mark} {nick(slot.nickname)}</b>{crown}\n"
            f"<code>{bar(slot.votes, total)}</code> "
            f"<b>{votes_word(slot.votes)}</b> · <b>{percent(slot.votes, total)}%</b>"
        )
    return "\n\n".join(lines)


def round_title(round_no: int, is_final: bool) -> str:
    return spaced("ФИНАЛ") if is_final else f"{round_no} {spaced('РАУНД')}"


def prizes_block(prizes: list[int]) -> str:
    lines = [
        f"{MEDAL.get(i, f'{i}.')} <b>{amount}⭐</b>" for i, amount in enumerate(prizes, start=1)
    ]
    return "🍋 <b>Призы за финал</b>\n" + "  ·  ".join(lines)


def deadline_line(deadline: datetime) -> str:
    return f"🗓 <b>Итоги в {deadline.strftime('%H:%M')} МСК</b>"


# --------------------------------------------------------------------- канал

def channel_post(
    round_no: int,
    is_final: bool,
    slots: list[Slot],
    prizes: list[int],
    deadline: datetime,
    vote_url: str,
    join_url: str,
) -> str:
    """Пост в канале: одна пара или группа."""
    participants = "\n".join(
        f"<b>{index}.  {nick(slot.nickname)}</b>" for index, slot in enumerate(slots, start=1)
    )
    return (
        f"<b>{round_title(round_no, is_final)}</b>\n"
        f"{RULE}\n\n"
        f"{prizes_block(prizes)}\n\n"
        f'📊 <a href="{vote_url}"><b>ПРОГОЛОСОВАТЬ</b></a>\n'
        f'🎫 <a href="{join_url}"><b>Принять участие</b></a>\n\n'
        f"<b>{spaced('УЧАСТНИКИ')}</b>\n"
        f"{participants}\n\n"
        f"{RULE}\n"
        f"{deadline_line(deadline)}"
    )


def channel_result(round_no: int, is_final: bool, ranking: list[Slot], tie_broken: bool) -> str:
    """Чем пост дополняется после закрытия голосования."""
    header = (
        f"🏆 <b>{spaced('ИТОГИ ФИНАЛА')}</b>"
        if is_final
        else f"✅ <b>ИТОГИ · {round_no} раунд</b>"
    )
    lines = []
    total = sum(slot.votes for slot in ranking)
    for slot in ranking:
        if is_final:
            mark = MEDAL.get(slot.position, f"{slot.position}.")
        else:
            mark = "✅" if slot.position == 1 else "❌"
        lines.append(
            f"<b>{mark} {nick(slot.nickname)}</b>\n"
            f"<code>{bar(slot.votes, total)}</code> <b>{votes_word(slot.votes)}</b>"
        )

    tail = "\n\n🎲 <i>Голоса сравнялись — победитель определён жребием.</i>" if tie_broken else ""
    return f"{header}\n{RULE}\n\n" + "\n\n".join(lines) + tail


def round_announcement(round_no: int, is_final: bool, alive: int, matches: int, deadline: datetime) -> str:
    what = "Финалисты" if is_final else "В игре"
    return (
        f"<b>{round_title(round_no, is_final)}</b>\n"
        f"{RULE}\n\n"
        f"{what}: <b>{alive}</b>\n"
        f"Матчей: <b>{matches}</b>\n\n"
        f"{deadline_line(deadline)}"
    )


def postponed(applied: int, needed: int, deadline: datetime) -> str:
    return (
        f"⏳ <b>{spaced('БАТЛ ПЕРЕНОСИТСЯ')}</b>\n"
        f"{RULE}\n\n"
        f"Набралось заявок: <b>{applied}</b> из <b>{needed}</b>.\n"
        f"Приём продолжается.\n\n"
        f"{deadline_line(deadline)}"
    )


def registration_open(deadline: datetime, prizes: list[int]) -> str:
    return (
        f"⚔️ <b>{spaced('НАБОР ОТКРЫТ')}</b>\n"
        f"{RULE}\n\n"
        f"{prizes_block(prizes)}\n\n"
        "🎫 <b>Подавайте заявки — пары публикуются сразу, как только "
        "наберётся двое.</b>\n\n"
        f"{deadline_line(deadline)}"
    )


def battle_cancelled() -> str:
    return (
        f"🛑 <b>{spaced('БАТЛ ОТМЕНЁН')}</b>\n"
        f"{RULE}\n\n"
        "Голосование остановлено, призы не разыгрываются.\n"
        "<b>Набор в новый батл уже открыт.</b>"
    )


BATTLE_CANCELLED_DM = (
    "🛑 <b>Батл отменён</b>\n\n"
    "<blockquote>Голосование остановлено. "
    "Набор в новый батл уже открыт — подайте заявку снова.</blockquote>"
)


def final_announcement(ranking: list[Slot], prizes: list[int]) -> str:
    lines = []
    for slot in ranking[: len(prizes)]:
        prize = prizes[slot.position - 1]
        lines.append(f"{MEDAL.get(slot.position, '')} <b>{nick(slot.nickname)}</b> — {prize}⭐")
    return (
        f"🏆 <b>{spaced('БАТЛ ЗАВЕРШЁН')}</b>\n"
        f"{RULE}\n\n" + "\n".join(lines)
    )


# ------------------------------------------------------------ экраны в боте

def voting_screen(round_no: int, is_final: bool, slots: list[Slot], deadline: datetime) -> str:
    title = spaced("ФИНАЛ") if is_final else f"{round_no} раунд"
    total = sum(slot.votes for slot in slots)
    return (
        f"🚀 <b>ГОЛОСОВАНИЕ · {title}</b>\n"
        f"{RULE}\n\n"
        f"{scoreboard(slots)}\n\n"
        f"{RULE}\n"
        f"Всего: <b>{votes_word(total)}</b>\n"
        f"{deadline_line(deadline)}\n\n"
        f"🎁 <b>Выберите, за кого голосуете</b> — кнопки ниже."
    )


def vote_button(slot: Slot, index: int) -> str:
    return f"{index}) {slot.nickname} — {votes_word(slot.votes)}"


def welcome(channel_url: str) -> str:
    return (
        f"👋 <b>{spaced('БИТВА НИКОВ')}</b>\n"
        f"{RULE}\n\n"
        "<b>Подавайте заявку, зовите своих голосовать — и забирайте звёзды.</b>\n\n"
        f"{HELP}\n\n"
        f'📣 Все батлы: <a href="{channel_url}">{escape(channel_url)}</a>'
    )


def pair_published(rival: str, link: str) -> str:
    return (
        f"⚔️ <b>Ваш пост опубликован!</b>\n"
        f"{RULE}\n\n"
        f"Соперник: <b>{nick(rival)}</b>\n\n"
        "<b>Ссылка для ваших голосующих</b> — отправьте её друзьям:\n"
        f"<code>{link}</code>"
    )


def advanced(link: str) -> str:
    return (
        f"🔥 <b>Вы прошли дальше!</b>\n"
        f"{RULE}\n\n"
        "<b>Следующий раунд уже опубликован.</b>\n\n"
        "Ваша ссылка для голосующих:\n"
        f"<code>{link}</code>"
    )


def took_place(place: int, prize: int) -> str:
    return (
        f"{MEDAL.get(place, '🏆')} <b>{place} место!</b>\n"
        f"{RULE}\n\n"
        f"Ваш приз: <b>{prize}⭐</b>\n\n"
        "<b>Спасибо за игру</b> — ждём вас в следующем батле."
    )


APPLICATION_ACCEPTED = (
    "✅ <b>Заявка принята</b>\n\n"
    "<blockquote><b>Пара набралась</b> — ваш пост уже в канале. "
    "Ссылку для голосующих пришлю следующим сообщением.</blockquote>"
)

IN_QUEUE = (
    "✅ <b>Вы в очереди</b>\n\n"
    "<blockquote>Как только подойдёт соперник, <b>ваш пост выйдет в канале</b>, "
    "а вы получите личную ссылку для голосующих.</blockquote>"
)

YOU_LOST = (
    "❌ <b>Вы проиграли</b>\n\n"
    "<b>Не расстраивайтесь</b> — в следующем батле всё сначала."
)

BYE_ROUND = (
    "🎟 <b>Проход без боя</b>\n\n"
    "<blockquote>Соперник не нашёлся — вы <b>автоматически в следующем "
    "раунде</b>.</blockquote>"
)

NEED_USERNAME = (
    "⚠️ <b>Нужен @username</b>\n\n"
    "Задайте его в настройках Telegram — <b>ник показывается в посте канала</b>."
)

ALREADY_IN_BATTLE = "✅ Вы уже участвуете в текущем батле."

NO_ACTIVE_BATTLE = "🗓 Сейчас батл не идёт. Ждите анонса в канале."

HELP = (
    "<blockquote expandable><b>Как это работает</b>\n\n"
    "<b>1.</b> Жмёте «<b>Принять участие</b>» — заявка попадает в очередь.\n"
    "<b>2.</b> Набирается пара — <b>ваш пост выходит в канале</b>.\n"
    "<b>3.</b> Зовёте голосующих по своей ссылке, счёт виден сразу.\n"
    "<b>4.</b> В час итогов бот считает голоса: <b>кто впереди — идёт дальше</b>.\n"
    "<b>5.</b> 1 раунд — <b>1vs1</b>, дальше <b>группы по 4 ника</b>.\n"
    "<b>6.</b> Финал забирает <b>призы за 1, 2 и 3 место</b>.\n\n"
    "Голосовать может любой подписчик канала: "
    "<b>один бесплатный голос на матч</b>.</blockquote>"
)


MAX_STARS_PER_INVOICE = 2500  # предел одного счёта в Telegram


def buy_screen(price: int, balance: int, stars_link: str, max_votes: int) -> str:
    link_line = (
        f'🧱 <b>Звёзды по низкой цене:</b> <a href="{stars_link}">тут</a>\n'
        if stars_link
        else ""
    )
    return (
        f"⚡️ <b>Покупка дополнительных голосов за звёзды</b>\n"
        f"{RULE}\n\n"
        f"📊 <b>Стоимость:</b> <code>1 голос = {price}⭐</code>\n"
        f"{link_line}"
        f"🎁 <b>Ваш баланс:</b> {balance} "
        f"{plural(balance, 'голос', 'голоса', 'голосов')}\n\n"
        "<blockquote>Чтобы использовать дополнительные голоса, "
        "просто проголосуйте за участника ещё раз.</blockquote>\n\n"
        f"📝 <b>Введите количество голосов для покупки:</b>\n"
        f"<i>от 1 до {max_votes}</i>"
    )


def buy_confirm(votes: int, price: int) -> str:
    total = votes * price
    return (
        f"🧾 <b>К оплате</b>\n"
        f"{RULE}\n\n"
        f"Голосов: <b>{votes}</b>\n"
        f"Цена: <b>{price}⭐</b> за голос\n\n"
        f"Итого: <b>{total}⭐</b>"
    )


def invite_screen(link: str, invited: int, rewarded: int, reward: int, channel_url: str) -> str:
    word = plural(reward, "голос", "голоса", "голосов")
    return (
        f"🤝 <b>{spaced('ПРИГЛАШАЙ ДРУЗЕЙ')}</b>\n"
        f"{RULE}\n\n"
        f"За каждого друга — <b>{reward} {word}</b> сверх бесплатного.\n\n"
        "<blockquote>Друг переходит по вашей ссылке, "
        f"<b>подписывается на канал</b> и запускает бота — голос ваш.</blockquote>\n\n"
        f"👥 Пришло по ссылке: <b>{invited}</b>\n"
        f"✅ Засчитано: <b>{rewarded}</b>\n\n"
        "Ваша ссылка:\n"
        f"<code>{link}</code>"
    )


def referral_rewarded(reward: int, balance: int) -> str:
    word = plural(reward, "голос", "голоса", "голосов")
    return (
        f"🤝 <b>Друг присоединился!</b>\n"
        f"{RULE}\n\n"
        f"Вам начислено <b>{reward} {word}</b>.\n"
        f"Баланс: <b>{balance}</b>"
    )


def referral_pending(channel_url: str) -> str:
    return (
        "🤝 <b>Почти готово</b>\n\n"
        "<blockquote>Подпишитесь на канал — и тот, кто вас пригласил, "
        "получит свой голос.</blockquote>\n"
        f'<a href="{channel_url}">{escape(channel_url)}</a>'
    )


def subscribe_required(channel_url: str) -> str:
    return (
        "⚠️ <b>Нужна подписка</b>\n\n"
        "<b>Голосовать могут только подписчики канала:</b>\n"
        f'<a href="{channel_url}">{escape(channel_url)}</a>'
    )


def profile(username: str | None, stats, balance: int) -> str:
    battles = stats["battles"] if stats else 0
    wins = stats["wins"] if stats else 0
    titles = stats["titles"] if stats else 0
    best = stats["best_place"] if stats and stats["best_place"] else "—"
    place = MEDAL.get(best, "") if isinstance(best, int) else ""
    return (
        f"👤 <b>{spaced('ПРОФИЛЬ')}</b>\n"
        f"{RULE}\n\n"
        f"Ник:  <b>{nick(username or 'без username')}</b>\n\n"
        f"🏆 Титулов:  <b>{titles}</b>\n"
        f"✅ Побед в матчах:  <b>{wins}</b>\n"
        f"⚔️ Батлов сыграно:  <b>{battles}</b>\n"
        f"🏅 Лучшее место:  <b>{best}</b> {place}\n"
        f"🎁 Купленных голосов:  <b>{balance}</b>"
    )


def leaderboard(rows) -> str:
    if not rows:
        return "🏅 <b>Таблица лидеров</b>\n\n<i>Пока пусто — всё впереди.</i>"
    lines = []
    for index, row in enumerate(rows, start=1):
        mark = MEDAL.get(index, f"{index}.")
        lines.append(
            f"{mark} <b>{nick(row['username'] or str(row['user_id']))}</b>\n"
            f"     🏆 <b>{row['titles']}</b>  ·  ✅ <b>{row['wins']}</b>"
            f"  ·  ⚔️ <b>{row['battles']}</b>"
        )
    return (
        f"🏅 <b>{spaced('ТАБЛИЦА ЛИДЕРОВ')}</b>\n"
        f"{RULE}\n\n" + "\n\n".join(lines)
    )
