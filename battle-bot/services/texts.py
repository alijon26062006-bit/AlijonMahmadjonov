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


def split_line(split, user_id: int) -> str:
    """«столько своими, столько купленными» — если купленные вообще были.

    Показывается открыто: когда исход решают купленные голоса, остальные
    должны это видеть. Скрытая покупка убивает доверие быстрее, чем
    отсутствие призов.
    """
    free, paid = (split or {}).get(user_id, (0, 0))
    if not paid:
        return ""
    return f"\n<i>👥 своими: {free} · ⭐ купленными: {paid}</i>"


def scoreboard(slots: list[Slot], show_place: bool = False, split=None) -> str:
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
            f"{split_line(split, slot.user_id)}"
        )
    return "\n\n".join(lines)


def round_title(round_no: int, is_final: bool) -> str:
    return spaced("ФИНАЛ") if is_final else f"{round_no} {spaced('РАУНД')}"


def prizes_block(prizes: list[str]) -> str:
    """Призы за финал. Длинные текстовые призы идут столбиком, а не в строку."""
    from services import prizes as prize_list

    lines = [
        f"{MEDAL.get(i, f'{i}.')} <b>{prize_list.label(value)}</b>"
        for i, value in enumerate(prizes, start=1)
    ]
    if not lines:
        return ""
    separator = "\n" if any(len(str(v)) > 16 for v in prizes) else "  ·  "
    return "🍋 <b>Призы за финал</b>\n" + separator.join(lines)


def deadline_line(deadline: datetime) -> str:
    return f"🗓 <b>Итоги в {deadline.strftime('%H:%M')} МСК</b>"


# --------------------------------------------------------------------- канал

def channel_post(
    round_no: int,
    is_final: bool,
    slots: list[Slot],
    prizes: list[str],
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


def channel_result(round_no: int, is_final: bool, ranking: list[Slot], tie_broken: bool,
                   split=None) -> str:
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
            f"{split_line(split, slot.user_id)}"
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


def registration_open(deadline: datetime, prizes: list[str]) -> str:
    return (
        f"⚔️ <b>{spaced('НАБОР ОТКРЫТ')}</b>\n"
        f"{RULE}\n\n"
        f"{prizes_block(prizes)}\n\n"
        "🎫 <b>Подавайте заявки — пары публикуются сразу, как только "
        "наберётся двое.</b>\n\n"
        f"{deadline_line(deadline)}"
    )


def _hours_word(hours: int) -> str:
    return plural(hours, "час", "часа", "часов")


def reminder_post(hours: int, deadline: datetime, registration: bool) -> str:
    """Напоминание в канал перед закрытием раунда."""
    head = "⏰ <b>Остался последний час</b>" if hours == 1 else (
        f"⏰ <b>Осталось {hours} {_hours_word(hours)}</b>"
    )
    tail = (
        "🎫 <b>Успей подать заявку</b> — пара публикуется сразу, "
        "как только найдётся соперник."
        if registration
        else "🗳 <b>Успей позвать своих проголосовать</b> — после итогов голоса не считаются."
    )
    return f"{head}\n{RULE}\n\n{tail}\n\n{deadline_line(deadline)}"


def reminder_dm(hours: int, link: str) -> str:
    """Личное напоминание участнику: зови голосовать, пока идёт время."""
    when = "последний час" if hours == 1 else f"{hours} {_hours_word(hours)}"
    return (
        f"⏰ <b>До итогов {when}</b>\n"
        f"{RULE}\n\n"
        "<b>Самое время позвать своих.</b> Отправьте им вашу ссылку:\n"
        f"<code>{link}</code>"
    )


def daily_call(applied: int, deadline: datetime, prizes: list[str]) -> str:
    """Ежедневный зов в канал, пока идёт приём заявок."""
    who = (
        f"👥 Уже подали заявку: <b>{applied}</b>"
        if applied
        else "👥 <b>Ты можешь стать первым</b>"
    )
    return (
        f"⚔️ <b>{spaced('СЕГОДНЯ БАТЛ')}</b>\n"
        f"{RULE}\n\n"
        f"{prizes_block(prizes)}\n\n"
        f"{who}\n\n"
        f"{deadline_line(deadline)}"
    )


def battle_finished_post(ranking: list[Slot], prizes: list[str]) -> str:
    """Итоги батла для главного канала — с призывом на следующий."""
    from services import prizes as prize_list

    lines = []
    for slot in ranking[:3]:
        place = slot.position or 1
        prize = (
            f" — <b>{prize_list.label(prizes[place - 1])}</b>"
            if place <= len(prizes)
            else ""
        )
        lines.append(f"{MEDAL.get(place, '🏅')} <b>{nick(slot.nickname)}</b>{prize}")

    return (
        f"🏆 <b>{spaced('БАТЛ ЗАВЕРШЁН')}</b>\n"
        f"{RULE}\n\n"
        + "\n".join(lines)
        + "\n\n<blockquote>Призы разыграны. <b>Следующий батл собирается "
        "прямо сейчас</b> — заявку можно подать по кнопке ниже.</blockquote>\n\n"
        "↓ <b>Успей записаться</b>"
    )


def queue_call(waiting: int, prizes: list[str]) -> str:
    """Ежедневный зов, когда батла нет: собираем очередь на следующий."""
    who = (
        f"🎫 Уже в очереди: <b>{waiting}</b> "
        f"{plural(waiting, 'человек', 'человека', 'человек')}"
        if waiting
        else "🎫 <b>Ты можешь стать первым</b>"
    )
    return (
        f"⚔️ <b>{spaced('ЗАПИСЬ НА БАТЛ')}</b>\n"
        f"{RULE}\n\n"
        f"{prizes_block(prizes)}\n\n"
        f"{who}\n\n"
        "<b>Жми «Принять участие»</b> — как только наберётся народ, "
        "бот подберёт соперника и начнётся батл."
    )


def battle_started_post(participants: int, deadline: datetime, prizes: list[str]) -> str:
    """Пост в главный канал в момент запуска батла.

    Главное в нём — что заявку ещё можно подать: пока идёт первый раунд,
    бот подберёт соперника любому, кто нажмёт кнопку.
    """
    word = plural(participants, "участник", "участника", "участников")
    who = (
        f"👥 Уже в игре: <b>{participants}</b> {word}"
        if participants
        else "👥 <b>Пока никого — станьте первым</b>"
    )
    return (
        f"⚔️ <b>{spaced('БАТЛ НАЧАЛСЯ')}</b>\n"
        f"{RULE}\n\n"
        f"{prizes_block(prizes)}\n\n"
        f"{who}\n"
        f"{deadline_line(deadline)}\n\n"
        "<blockquote><b>Ещё можно успеть.</b> Пока идёт первый раунд, "
        "бот подберёт соперника каждому, кто подаст заявку — "
        "и сразу опубликует вашу пару здесь.</blockquote>\n\n"
        "↓ <b>Жми кнопку</b>"
    )


def battle_opened(deadline: datetime, waiting: int = 0) -> str:
    """Батл создан, но пар пока нет — зовём в канал батлов."""
    who = (
        f"🎫 Уже заявился: <b>{waiting}</b>"
        if waiting
        else "🎫 <b>Пока никого — станьте первым</b>"
    )
    return (
        f"⚔️ <b>{spaced('НАБОР ОТКРЫТ')}</b>\n"
        f"{RULE}\n\n"
        f"{who}\n"
        f"{deadline_line(deadline)}\n\n"
        "<blockquote>Подавайте заявку — как только наберётся пара, "
        "её пост выйдет здесь же.</blockquote>"
    )


def battle_empty() -> str:
    return (
        f"🛑 <b>{spaced('БАТЛ НЕ СОСТОЯЛСЯ')}</b>\n"
        f"{RULE}\n\n"
        "Заявок не набралось. <b>Ждём следующего набора.</b>"
    )


BATTLE_EMPTY_DM = (
    "🛑 <b>Батл не состоялся</b>\n\n"
    "<blockquote>Соперников так и не нашлось. "
    "Ваша заявка <b>вернулась в очередь</b> — участвовать заново не нужно, "
    "вы попадёте в следующий батл.</blockquote>"
)


def battle_empty_admin(returned: int) -> str:
    tail = (
        f"\n\nЗаявок вернулось в очередь: <b>{returned}</b>."
        if returned
        else ""
    )
    return (
        f"🛑 <b>Батл не состоялся</b>\n"
        f"{RULE}\n\n"
        f"К моменту итогов не набралось ни одной пары.{tail}\n\n"
        "<i>Стоит дать больше времени на набор или позвать людей рекламой.</i>"
    )


# --------------------------------------------------- вышедшие из канала

def left_the_channel(times: int, price: int) -> str:
    """Сообщение тому, кто отписался от обязательного канала."""
    again = (
        f"\n\n<i>Это уже {times}-й раз.</i>"
        if times > 1
        else ""
    )
    how = (
        f"\n\n<b>Вернуться в батлы</b> — {price}⭐, кнопка ниже. "
        "Подписаться обратно этого не заменит."
        if price
        else "\n\n<b>Участие закрыто.</b> Напишите администратору."
    )
    return (
        f"🚪 <b>Вы вышли из канала</b>\n"
        f"{RULE}\n\n"
        "Заявки от вас больше не принимаются.\n\n"
        "<blockquote>Канал — это и есть площадка батлов. Заходить, когда "
        "нужен приз, и уходить, когда он получен, — так не работает.</blockquote>"
        f"{again}{how}"
    )


def leaver_refused(times: int, price: int) -> str:
    """Отказ на заявке от того, кто выходил из канала."""
    again = f"Выходов: <b>{times}</b>\n\n" if times > 1 else ""
    how = (
        f"<b>Вернуться в батлы</b> — {price}⭐, кнопка ниже."
        if price
        else "<b>Участие закрыто.</b> Напишите администратору."
    )
    return (
        f"🚪 <b>Вы выходили из канала</b>\n"
        f"{RULE}\n\n"
        f"{again}"
        "Подписаться обратно недостаточно: заявки от вышедших не "
        "принимаются.\n\n"
        "<blockquote>Канал — это площадка батлов. Приходить только за призом "
        "и уходить сразу после — нечестно по отношению к остальным.</blockquote>\n\n"
        f"{how}"
    )


def rejoin_allowed() -> str:
    return (
        f"✅ <b>Доступ к батлам возвращён</b>\n"
        f"{RULE}\n\n"
        "<b>Подпишитесь на канал</b>, если ещё не подписаны, и подавайте "
        "заявку — кнопка «🚀 Принять участие»."
    )


def leaver_forgiven() -> str:
    return (
        f"✅ <b>Администратор вернул вам доступ</b>\n"
        f"{RULE}\n\n"
        "Заявки от вас снова принимаются."
    )


# ------------------------------------------------------- пауза призёрам

def until_line(until: datetime) -> str:
    return f"🗓 До <b>{until.strftime('%d.%m в %H:%M')}</b> МСК"


def rest_days(until: datetime, now: datetime) -> int:
    """Сколько суток осталось, округляя вверх: «меньше дня» — это ещё день."""
    left = until - now
    if left.total_seconds() <= 0:
        return 0
    return max(1, -(-int(left.total_seconds()) // 86400))


def cooldown_started(place: int, until: datetime, price: int) -> str:
    """Сообщение призёру сразу после финала."""
    buy = (
        f"\n\n<blockquote>Не хотите ждать? <b>Вернуться сразу</b> можно "
        f"за <b>{price}</b>⭐ — кнопка ниже.</blockquote>"
        if price
        else ""
    )
    return (
        f"{MEDAL.get(place, '🏆')} <b>{place} место — и заслуженный отдых</b>\n"
        f"{RULE}\n\n"
        "Призёры пропускают несколько батлов: так призы достаются не одним и "
        "тем же. Голосовать и звать друзей это не мешает.\n\n"
        f"{until_line(until)}{buy}"
    )


def on_cooldown(place: int, until: datetime, now: datetime, price: int) -> str:
    """Отказ на заявке, пока идёт пауза."""
    days = rest_days(until, now)
    word = plural(days, "день", "дня", "дней")
    buy = (
        f"\n\n<b>Вернуться сейчас</b> — {price}⭐, кнопка ниже."
        if price
        else ""
    )
    return (
        f"⏳ <b>Вы отдыхаете после {place} места</b>\n"
        f"{RULE}\n\n"
        f"Осталось: <b>{days}</b> {word}\n"
        f"{until_line(until)}\n\n"
        "<i>Голосовать, звать друзей и покупать голоса можно как обычно — "
        "закрыта только подача заявки.</i>"
        f"{buy}"
    )


def profile_rest(place: int, until: datetime) -> str:
    return (
        f"⏳ <b>Отдых после {place} места</b>\n"
        f"{until_line(until)}\n"
        "<i>Заявку пока подать нельзя. Голосовать — можно.</i>"
    )


def cooldown_lifted(paid: bool = True) -> str:
    how = "Пауза выкуплена" if paid else "Паузу снял администратор"
    return (
        f"✅ <b>{how}</b>\n"
        f"{RULE}\n\n"
        "<b>Можно подавать заявку</b> — жмите «🚀 Принять участие»."
    )


def queue_ready(waiting: int, minimum: int) -> str:
    """Админу: людей набралось, можно запускать."""
    word = plural(waiting, "человек", "человека", "человек")
    return (
        f"🎫 <b>Очередь набралась</b>\n"
        f"{RULE}\n\n"
        f"В очереди: <b>{waiting}</b> {word} "
        f"<i>(нужно было {minimum})</i>\n\n"
        "Батл можно запускать: <b>/panel → ⚔️ Батл → Создать батл</b>."
    )


def battle_cancelled(queue_size: int = 0) -> str:
    tail = (
        f"\n\n🎫 <b>Запись на следующий открыта</b> — в очереди уже {queue_size}."
        if queue_size
        else "\n\n🎫 <b>Записывайтесь на следующий</b> — кнопка «Принять участие»."
    )
    return (
        f"🛑 <b>{spaced('БАТЛ ОТМЕНЁН')}</b>\n"
        f"{RULE}\n\n"
        f"Голосование остановлено, призы не разыгрываются.{tail}"
    )


BATTLE_CANCELLED_DM = (
    "🛑 <b>Батл отменён</b>\n\n"
    "<blockquote>Голосование остановлено. "
    "Набор в новый батл уже открыт — подайте заявку снова.</blockquote>"
)


def final_announcement(ranking: list[Slot], prizes: list[str]) -> str:
    from services import prizes as prize_list

    lines = []
    for slot in ranking[: len(prizes)]:
        prize = prize_list.label(prizes[slot.position - 1])
        lines.append(f"{MEDAL.get(slot.position, '')} <b>{nick(slot.nickname)}</b> — {prize}")
    return (
        f"🏆 <b>{spaced('БАТЛ ЗАВЕРШЁН')}</b>\n"
        f"{RULE}\n\n" + "\n".join(lines)
    )


# ------------------------------------------------------------ экраны в боте

def overtaken(rival: str, rival_votes: int, your_votes: int) -> str:
    """Соперник вышел вперёд — самый подходящий момент позвать своих."""
    gap = rival_votes - your_votes
    return (
        f"⚠️ <b>Вас обошли!</b>\n"
        f"{RULE}\n\n"
        f"<b>{nick(rival)}</b> впереди: "
        f"<b>{rival_votes}</b> против <b>{your_votes}</b>.\n"
        f"Разрыв — <b>{gap}</b> {plural(gap, 'голос', 'голоса', 'голосов')}.\n\n"
        "<b>Ещё не поздно.</b> Позовите своих — кнопка ниже."
    )


def took_the_lead(rival: str, your_votes: int, rival_votes: int) -> str:
    return (
        f"🔥 <b>Вы вырвались вперёд!</b>\n"
        f"{RULE}\n\n"
        f"<b>{your_votes}</b> против <b>{rival_votes}</b> у {nick(rival)}.\n\n"
        "<i>Не расслабляйтесь — до итогов ещё есть время.</i>"
    )


def match_result_dm(
    ranking: list[Slot],
    you_id: int,
    round_no: int,
    is_final: bool,
    advanced: bool,
    tie_broken: bool,
) -> str:
    """Личный итог матча: соперники, счёт и место — без утаивания.

    Одинаковая таблица и победителю, и проигравшему: каждый видит, кто сколько
    набрал, и может проверить результат сам.
    """
    total = sum(slot.votes for slot in ranking)
    you = next((slot for slot in ranking if slot.user_id == you_id), None)
    place = you.position if you else 0

    if is_final:
        head = f"{MEDAL.get(place, '🏁')} <b>Финал · {place} место</b>"
    elif advanced:
        head = "🔥 <b>Вы прошли дальше!</b>"
    else:
        head = "❌ <b>Вы выбываете</b>"

    lines = []
    for slot in ranking:
        if is_final:
            mark = MEDAL.get(slot.position, f"{slot.position}.")
        else:
            mark = "✅" if slot.position == 1 else "❌"
        mine = " ← <b>вы</b>" if slot.user_id == you_id else ""
        lines.append(
            f"{mark} <b>{nick(slot.nickname)}</b>{mine}\n"
            f"<code>{bar(slot.votes, total)}</code> <b>{votes_word(slot.votes)}</b>"
            f" · <b>{percent(slot.votes, total)}%</b>"
        )

    stage = "Финал" if is_final else f"{round_no} раунд"
    body = f"{head}\n{RULE}\n\n<b>{stage}</b> · итог\n\n" + "\n\n".join(lines)
    body += f"\n\n{RULE}\nВсего голосов: <b>{total}</b>"

    if tie_broken:
        body += "\n\n🎲 <i>Голоса сравнялись — победитель определён жребием.</i>"
    if not advanced and not is_final:
        body += "\n\n<b>Не расстраивайтесь</b> — в следующем батле всё сначала."
    return body


def voting_screen(round_no: int, is_final: bool, slots: list[Slot], deadline: datetime,
                  split=None) -> str:
    title = spaced("ФИНАЛ") if is_final else f"{round_no} раунд"
    total = sum(slot.votes for slot in slots)
    return (
        f"🚀 <b>ГОЛОСОВАНИЕ · {title}</b>\n"
        f"{RULE}\n\n"
        f"{scoreboard(slots, split=split)}\n\n"
        f"{RULE}\n"
        f"Всего: <b>{votes_word(total)}</b>\n"
        f"{deadline_line(deadline)}\n\n"
        f"🎁 <b>Выберите, за кого голосуете</b> — кнопки ниже."
    )


def voting_rules(scope: str, balance: int = 0) -> str:
    """Правило голосования под экраном: бесплатный и купленные."""
    line = f"<i>{free_scope_line(scope)}.</i>"
    if balance:
        word = plural(balance, "голос", "голоса", "голосов")
        line += (
            f"\n<i>У вас <b>{balance}</b> купленных {word} — "
            "тратьте сколько угодно, хоть все в одну пару.</i>"
        )
    return line


FREE_SCOPE_WORDS = {
    "battle": "в этом батле",
    "round": "в этом раунде",
    "match": "в этом матче",
}


def free_scope_line(scope: str) -> str:
    """Как объяснить правило бесплатного голоса на экране."""
    return {
        "battle": "Один бесплатный голос <b>на весь батл</b>",
        "round": "Один бесплатный голос <b>на раунд</b>",
        "match": "Один бесплатный голос <b>на каждую пару</b>",
    }.get(scope, "Один бесплатный голос")


def free_vote_spent(scope: str) -> str:
    where = FREE_SCOPE_WORDS.get(scope, "здесь")
    return f"Бесплатный голос {where} уже потрачен."


def out_of_votes(price: int) -> str:
    return (
        f"🎁 <b>Голоса закончились</b>\n"
        f"{RULE}\n\n"
        "Бесплатный голос вы уже отдали. Дальше — только купленными, "
        "зато их можно тратить <b>сколько угодно</b>: хоть все в одну пару.\n\n"
        f"Один голос — <b>{price}</b>⭐\n\n"
        "<blockquote>Голоса можно и не покупать: позовите друга по своей "
        "ссылке — за него начисляется голос.</blockquote>"
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


def pair_published(rival: str) -> str:
    return (
        f"⚔️ <b>Соперник найден!</b>\n"
        f"{RULE}\n\n"
        f"Против вас: <b>{nick(rival)}</b>\n\n"
        "Ваш пост уже в канале. <b>Кто позовёт больше голосов — тот и пройдёт.</b>\n\n"
        "<i>Кнопки ниже: посмотреть счёт, позвать друзей, скопировать ссылку.</i>"
    )


# ------------------------------------------------ ежедневная активность

def nick_of_the_day(nickname: str, battles: int, wins: int, titles: int) -> str:
    """Ник дня: имя живого человека и повод прийти в канал.

    Смысл не в статистике, а во внимании: названному приятно, он расскажет
    своим, и канал не выглядит мёртвым между батлами.
    """
    if titles:
        note = f"Уже брал первое место: <b>{titles}</b> раз."
    elif wins:
        note = f"Выиграл раундов: <b>{wins}</b>."
    elif battles:
        note = "Уже участвовал — и вернулся снова."
    else:
        note = "Только записался. Встречайте новичка."

    return (
        f"🔥 <b>{spaced('НИК ДНЯ')}</b>\n"
        f"{RULE}\n\n"
        f"<b>{nick(nickname)}</b>\n"
        f"{note}\n\n"
        "<i>Хотите увидеть здесь своё имя? Жмите «Участвовать» — "
        "следующий батл собирается прямо сейчас.</i>"
    )


def record_of_the_day(nickname: str, votes: int, battle_id: int) -> str:
    """Рекорд последнего батла — самый честный аргумент «сюда ходят»."""
    return (
        f"📊 <b>{spaced('РЕКОРД БАТЛА')}</b>\n"
        f"{RULE}\n\n"
        f"{nick(nickname)} собрал <b>{votes}</b> "
        f"{plural(votes, 'голос', 'голоса', 'голосов')} в батле <b>#{battle_id}</b>.\n\n"
        "<i>Побить рекорд может любой: зовите своих — голосуют бесплатно.</i>"
    )


# ------------------------------------------------------- выплаты и слава

def payout_post(nickname: str, place: int, prize: str, battle_id: int) -> str:
    """Подпись под скриншотом выплаты в канале.

    Пост с доказательством — самая дешёвая реклама, какая у батла есть:
    призы видно, значит участвовать имеет смысл.
    """
    from services import prizes as prize_list

    return (
        f"💸 <b>Приз выплачен</b>\n"
        f"{RULE}\n\n"
        f"{MEDAL.get(place, '🏅')} <b>{nick(nickname)}</b> — "
        f"<b>{prize_list.label(prize)}</b>\n"
        f"Батл <b>#{battle_id}</b>\n\n"
        "<i>Так выглядит каждый приз этого батла. Участвуйте — "
        "следующим можете быть вы.</i>"
    )


def payout_dm(place: int, prize: str) -> str:
    from services import prizes as prize_list

    return (
        f"💸 <b>Приз отправлен</b>\n"
        f"{RULE}\n\n"
        f"{MEDAL.get(place, '🏅')} Ваше место: <b>{place}</b>\n"
        f"Приз: <b>{prize_list.label(prize)}</b>\n\n"
        "<i>Доказательство выплаты опубликовано в канале.</i>"
    )


def hall_of_fame(rows, limit: int = 15) -> str:
    """Зал славы: кому уже выплачены призы."""
    from services import prizes as prize_list

    if not rows:
        return (
            f"🏛 <b>{spaced('ЗАЛ СЛАВЫ')}</b>\n{RULE}\n\n"
            "<i>Пока пусто. Первый приз — и первое имя здесь.</i>"
        )

    lines = [
        f"{MEDAL.get(int(row['place']), '🏅')} <b>{nick(row['nickname'] or '—')}</b> — "
        f"<b>{prize_list.label(str(row['prize']))}</b>  <i>батл #{row['battle_id']}</i>"
        for row in rows[:limit]
    ]
    return (
        f"🏛 <b>{spaced('ЗАЛ СЛАВЫ')}</b>\n{RULE}\n\n"
        + "\n".join(lines)
        + "\n\n<i>Все призы выплачены и подтверждены скриншотами в канале.</i>"
    )


def pay_the_winners(battle_id: int, winners) -> str:
    """Напоминание админу сразу после финала."""
    lines = "\n".join(
        f"{MEDAL.get(slot.position or 0, '🏅')} <b>{nick(slot.nickname)}</b>"
        for slot in winners
    )
    return (
        f"💸 <b>Пора выплатить призы</b>\n"
        f"{RULE}\n\n"
        f"Батл <b>#{battle_id}</b> завершён.\n\n{lines}\n\n"
        "<blockquote>Панель → 🏆 Призы → 💸 Выплаты. Пришлите скриншот "
        "перевода — бот сам выложит его в канал. Именно эти посты и "
        "заставляют людей верить в призы.</blockquote>"
    )


PAYOUT_NEED_PHOTO = (
    "⚠️ Нужен <b>скриншот перевода</b> картинкой. "
    "Пришлите фото, а не текст и не файл."
)


# ------------------------------------------------ картинка для сторис

CARD_UNAVAILABLE = (
    "Картинка сейчас недоступна — на сервере не хватает шрифта. "
    "Скажите администратору."
)

CARD_NO_MATCH = (
    "🖼 <b>Картинка</b>\n\n"
    "Сейчас у вас нет идущей пары. Картинка появится, когда бот найдёт "
    "вам соперника."
)


def card_caption(link: str) -> str:
    """Что делать с картинкой. Без этой подписи её просто посмотрят."""
    return (
        "🖼 <b>Ваша картинка готова</b>\n\n"
        "<b>Выложите её в сторис</b> или отправьте друзьям — по ссылке ниже "
        "они попадут прямо на голосование за вас.\n\n"
        f"<code>{escape(link)}</code>\n\n"
        "<i>Кто позовёт больше голосов — тот и пройдёт дальше.</i>"
    )


def advanced(rivals: list[str]) -> str:
    against = ", ".join(nick(name) for name in rivals)
    return (
        f"🔥 <b>Вы прошли дальше!</b>\n"
        f"{RULE}\n\n"
        f"<b>Следующий раунд уже опубликован.</b>\n\n"
        f"Против вас: <b>{against}</b>\n\n"
        "<i>Кнопки ниже: посмотреть счёт, позвать друзей, скопировать ссылку.</i>"
    )


# ------------------------------------------------ личный канал участника

def my_channel_screen(channel, bot_username: str) -> str:
    """Экран «Мой канал»: как привязать и что бот будет туда публиковать."""
    if channel is None:
        return (
            f"📡 <b>{spaced('МОЙ КАНАЛ')}</b>\n"
            f"{RULE}\n\n"
            "<b>Пусть за вас голосуют ваши подписчики.</b>\n"
            "Бот сам опубликует вашу пару у вас в канале — с кнопкой, "
            "которая ведёт голосовать <b>именно за вас</b>.\n\n"
            f"<b>{spaced('КАК ПОДКЛЮЧИТЬ')}</b>\n"
            f"<b>1.</b> Откройте свой канал → <i>Управление</i> → "
            f"<i>Администраторы</i> → добавьте @{escape(bot_username)}\n"
            "<b>2.</b> Оставьте право <b>«Публикация сообщений»</b>\n"
            "<b>3.</b> Перешлите сюда любой пост из этого канала\n\n"
            "<blockquote>Публикуется только ваша пара и ваш итог. "
            "Ничего лишнего бот в канал не пишет.</blockquote>"
        )

    name = escape(channel["title"] or "канал")
    state = "✅ подключён" if channel["active"] else "⚠️ бот потерял доступ"
    posts = int(channel["posts"])
    word = plural(posts, "пост", "поста", "постов")
    tail = (
        ""
        if channel["active"]
        else "\n\n<b>Верните бота администратором</b> и нажмите «Проверить»."
    )
    return (
        f"📡 <b>{spaced('МОЙ КАНАЛ')}</b>\n"
        f"{RULE}\n\n"
        f"Канал: <b>{name}</b>\n"
        f"Статус: <b>{state}</b>\n"
        f"Опубликовано: <b>{posts}</b> {word}\n\n"
        "<blockquote>Как только начнётся ваш раунд, пост с кнопкой "
        "«Голосовать за меня» появится в канале сам.</blockquote>"
        f"{tail}"
    )


def my_channel_linked(title: str | None) -> str:
    return (
        f"✅ <b>Канал подключён</b>\n"
        f"{RULE}\n\n"
        f"<b>{escape(title or 'Ваш канал')}</b>\n\n"
        "Ваши пары бот будет публиковать туда сам — с кнопкой "
        "<b>«Голосовать за меня»</b>."
    )


def my_channel_post(
    round_no: int, is_final: bool, nickname: str, rivals: list[str],
    deadline: datetime, vote_url: str
) -> str:
    """Пост, который бот публикует в личном канале участника."""
    against = ", ".join(nick(name) for name in rivals) or "соперник"
    return (
        f"⚔️ <b>Я в батле · {round_title(round_no, is_final)}</b>\n"
        f"{RULE}\n\n"
        f"Мой ник: <b>{nick(nickname)}</b>\n"
        f"Против меня: <b>{against}</b>\n\n"
        f"<b>Голос бесплатный</b> — жмите кнопку ниже.\n"
        f'📊 <a href="{vote_url}"><b>ГОЛОСОВАТЬ ЗА МЕНЯ</b></a>\n\n'
        f"{RULE}\n"
        f"{deadline_line(deadline)}"
    )


def my_channel_result(round_no: int, is_final: bool, ranking, you_id: int) -> str:
    """Итог раунда в личном канале — честно, со всем счётом."""
    you = next((slot for slot in ranking if slot.user_id == you_id), None)
    won = you is not None and you.position == 1
    if is_final:
        place = you.position if you else 0
        header = f"{MEDAL.get(place, '🏆')} <b>{place} место в финале</b>"
    else:
        header = (
            f"✅ <b>Прошёл дальше · {round_no} раунд</b>"
            if won
            else f"❌ <b>Вылетел · {round_no} раунд</b>"
        )
    thanks = (
        "<b>Спасибо всем, кто голосовал!</b>"
        if won or is_final
        else "<b>Спасибо всем, кто поддержал.</b>"
    )
    return f"{header}\n{RULE}\n\n{scoreboard(ranking, show_place=is_final)}\n\n{thanks}"


def called_to_support(nickname: str) -> str:
    return (
        f"📣 Вас позвали поддержать <b>{nick(nickname)}</b>.\n"
        "<i>Голос всё равно ваш — выбирайте кого хотите.</i>\n\n"
    )


MY_CHANNEL_FORWARD = (
    "📡 <b>Перешлите пост из канала</b>\n\n"
    "<blockquote>Откройте свой канал, выберите любой пост → «Переслать» → "
    "выберите этого бота.</blockquote>\n\n"
    "<i>Так бот узнает, какой канал ваш.</i>"
)

MY_CHANNEL_NOT_A_CHANNEL = (
    "⚠️ <b>Это не пост из канала</b>\n\n"
    "Перешлите сообщение <b>из канала</b>, а не из чата или личной переписки."
)

MY_CHANNEL_HIDDEN = (
    "⚠️ <b>Автор поста скрыт</b>\n\n"
    "В настройках канала включена скрытая пересылка, и бот не видит, "
    "откуда пост.\n\n"
    "<blockquote>Отключите её в настройках канала или добавьте бота "
    "администратором и перешлите пост ещё раз.</blockquote>"
)

MY_CHANNEL_NOT_ADMIN = (
    "⚠️ <b>Бот не администратор этого канала</b>\n\n"
    "Добавьте его в администраторы с правом <b>«Публикация сообщений»</b> "
    "и перешлите пост ещё раз."
)

MY_CHANNEL_NOT_YOURS = (
    "⚠️ <b>Это не ваш канал</b>\n\n"
    "Подключить можно только тот канал, где вы владелец или администратор."
)

MY_CHANNEL_TAKEN = (
    "⚠️ <b>Канал уже подключён другому участнику</b>\n\n"
    "Один канал — один участник."
)

MY_CHANNEL_LOST = (
    "⚠️ <b>Не смог опубликовать в вашем канале</b>\n"
    f"{RULE}\n\n"
    "Похоже, бота убрали из администраторов или отобрали право публикации.\n\n"
    "<b>Верните права</b> и снова нажмите «📡 Мой канал» → «Проверить»."
)

MY_CHANNEL_UNLINKED = "✅ Канал отключён. Публиковать туда бот больше не будет."

MY_CHANNEL_NO_MATCH = "🗓 Сейчас у вас нет активного матча — публиковать нечего."

MY_CHANNEL_OFF = (
    "📡 Публикация в личные каналы сейчас выключена администратором."
)


def took_place(place: int, prize: str) -> str:
    from services import prizes as prize_list

    return (
        f"{MEDAL.get(place, '🏆')} <b>{place} место!</b>\n"
        f"{RULE}\n\n"
        f"Ваш приз: <b>{prize_list.label(prize)}</b>\n\n"
        "<b>Спасибо за игру</b> — ждём вас в следующем батле."
    )


def queued(size: int) -> str:
    word = plural(size, "человек", "человека", "человек")
    return (
        f"✅ <b>Вы в очереди</b>\n"
        f"{RULE}\n\n"
        f"Сейчас ждут батла: <b>{size}</b> {word}.\n\n"
        "<blockquote>Как только админ соберёт батл, бот подберёт вам соперника "
        "и пришлёт ссылку для голосующих.</blockquote>"
    )


def joined_running(round_no: int) -> str:
    """Подсел в идущий батл, но пары пока нет."""
    return (
        f"⚔️ <b>Вы в батле!</b>\n"
        f"{RULE}\n\n"
        f"Идёт <b>{round_no} раунд</b> — вы участвуете в нём.\n\n"
        "<blockquote>Как только подойдёт соперник, ваша пара выйдет в канале, "
        "а вам придёт ссылка для голосующих. Если соперник так и не найдётся "
        "до итогов — <b>пройдёте дальше без боя</b>.</blockquote>"
    )


def already_queued(size: int) -> str:
    word = plural(size, "человек", "человека", "человек")
    return (
        f"✅ <b>Вы уже в очереди</b>\n\n"
        f"<blockquote>Ждут вместе с вами: <b>{size}</b> {word}. "
        "Ждите старта батла.</blockquote>"
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

def help_screen() -> str:
    """Экран «Помощь»: коротко и по делу, всё остальное — на кнопках."""
    return (
        "⚡ <b>Здесь вы можете оставить заявку на участие в батле</b>\n\n"
        "<blockquote>⚠️ Бот сообщит о начале батла, "
        "так что <b>не блокируйте его</b></blockquote>\n\n"
        "<b><i>Если у вас есть вопросы, не стесняйтесь спрашивать</i></b>"
    )


HELP = (
    "<blockquote expandable><b>Как это работает</b>\n\n"
    "<b>1.</b> Жмёте «<b>Принять участие</b>» — заявка попадает в очередь.\n"
    "<b>2.</b> Набирается пара — <b>ваш пост выходит в канале</b>.\n"
    "<b>3.</b> Зовёте голосующих по своей ссылке, счёт виден сразу.\n"
    "<b>4.</b> В час итогов бот считает голоса: <b>кто впереди — идёт дальше</b>.\n"
    "<b>5.</b> 1 раунд — <b>1vs1</b>, дальше <b>группы по 4 ника</b>.\n"
    "<b>6.</b> Финал забирает <b>призы за 1, 2 и 3 место</b>.\n\n"
    "Голосовать может любой подписчик канала: "
    "<b>один бесплатный голос на весь батл</b>. "
    "Купленные голоса ничем не ограничены: тратьте сколько угодно "
    "и за кого угодно.\n\n"
    "📡 Есть свой канал? Подключите его в «<b>Мой канал</b>» — бот сам "
    "опубликует там вашу пару с кнопкой «Голосовать за меня».</blockquote>"
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


# --------------------------------------------- пополнение вручную

def manual_amount(votes: int, price: str, currency: str) -> str:
    """Сколько платить за столько голосов. Цена может быть дробной."""
    try:
        total = float(str(price).replace(",", ".")) * votes
    except ValueError:
        return f"{votes} × {price} {currency}"
    shown = f"{total:.2f}".rstrip("0").rstrip(".")
    return f"{shown} {currency}"


def manual_pick_screen(title: str, price: str, currency: str) -> str:
    """Первый шаг: сколько голосов покупаем."""
    return (
        f"🏦 <b>{escape(title)}</b>\n"
        f"{RULE}\n\n"
        f"Оплата переводом — без звёзд.\n"
        f"Один голос: <b>{manual_amount(1, price, currency)}</b>\n\n"
        "<b>Сколько голосов берёте?</b>\n"
        "<i>Выберите количество — покажу реквизиты и точную сумму.</i>"
    )


def manual_screen(title: str, details: str, note: str, votes: int,
                  price: str, currency: str) -> str:
    """Экран с реквизитами: сколько платить и куда."""
    tail = f"\n\n<blockquote>{escape(note)}</blockquote>" if note else ""
    return (
        f"🏦 <b>{escape(title)}</b>\n"
        f"{RULE}\n\n"
        f"Голосов: <b>{votes}</b>\n"
        f"К оплате: <b>{manual_amount(votes, price, currency)}</b>\n\n"
        f"<b>Реквизиты</b>\n<code>{escape(details)}</code>\n"
        f"<i>Нажмите на номер, чтобы скопировать.</i>{tail}\n\n"
        "После оплаты нажмите «Я оплатил» и пришлите скриншот чека. "
        "Голоса начислим после проверки."
    )


MANUAL_ASK_RECEIPT = (
    "🧾 <b>Пришлите чек</b>\n\n"
    "Скриншот или фото перевода — одним сообщением.\n\n"
    "<i>Если передумали, нажмите «Отмена».</i>"
)

MANUAL_NEED_PHOTO = (
    "⚠️ Нужен <b>скриншот или фото</b> чека. "
    "Пришлите картинку, а не текст."
)


def manual_sent(votes: int, amount: str) -> str:
    return (
        f"✅ <b>Чек отправлен</b>\n"
        f"{RULE}\n\n"
        f"Голосов: <b>{votes}</b>\nСумма: <b>{amount}</b>\n\n"
        "<blockquote>Заявка ушла администратору. Как только он проверит "
        "чек, голоса появятся на балансе — придёт сообщение.</blockquote>"
    )


def manual_already_pending(votes: int, amount: str) -> str:
    return (
        f"⏳ <b>Заявка уже на проверке</b>\n"
        f"{RULE}\n\n"
        f"Голосов: <b>{votes}</b>\nСумма: <b>{amount}</b>\n\n"
        "<blockquote>Дождитесь ответа — вторую заявку отправить нельзя. "
        "Так сделано, чтобы один чек не засчитали дважды.</blockquote>"
    )


def manual_accepted(votes: int, balance: int) -> str:
    return (
        f"✅ <b>Оплата принята</b>\n"
        f"{RULE}\n\n"
        f"Начислено: <b>{votes}</b> "
        f"{plural(votes, 'голос', 'голоса', 'голосов')}\n"
        f"Баланс: <b>{balance}</b>"
    )


def manual_declined(note: str = "") -> str:
    why = f"\n\n<b>Причина:</b> {escape(note)}" if note else ""
    return (
        f"❌ <b>Оплата не принята</b>\n"
        f"{RULE}\n\n"
        f"Администратор не подтвердил чек.{why}\n\n"
        "<i>Можно отправить заявку заново или написать администратору.</i>"
    )


def manual_for_admin(user, votes: int, amount: str, topup_id: int) -> str:
    handle = f"@{user['username']}" if user and user["username"] else (
        escape(str(user["first_name"])) if user else "—"
    )
    return (
        f"🧾 <b>Новая оплата вручную</b>\n"
        f"{RULE}\n\n"
        f"Заявка <b>#{topup_id}</b>\n"
        f"От: {escape(handle)} (<code>{user['user_id'] if user else '?'}</code>)\n"
        f"Голосов: <b>{votes}</b>\n"
        f"Сумма: <b>{amount}</b>\n\n"
        "<i>Проверьте чек и решите.</i>"
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
