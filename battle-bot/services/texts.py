"""Тексты сообщений. Собраны в одном месте, чтобы правки формулировок
не растекались по обработчикам."""
from __future__ import annotations

from datetime import datetime
from html import escape

from core.models import Slot

MEDAL = {1: "🥇", 2: "🥈", 3: "🥉"}


def spaced(text: str) -> str:
    """«РАУНД» -> «Р А У Н Д» — заголовки как в канале."""
    return " ".join(text)


def nick(value: str) -> str:
    value = escape(value)
    return value if value.startswith("@") else f"@{value}"


def round_title(round_no: int, is_final: bool) -> str:
    return spaced("ФИНАЛ") if is_final else f"{round_no} {spaced('РАУНД')}"


def prizes_block(prizes: list[int]) -> str:
    lines = [f"{i} место — {amount}⭐" for i, amount in enumerate(prizes, start=1)]
    return "🍋 <b>Призы за финал:</b>\n" + "\n".join(lines)


def deadline_line(deadline: datetime) -> str:
    return f"🗓 <b>Итоги в {deadline.strftime('%H:%M')} МСК</b>"


def channel_post(
    round_no: int,
    is_final: bool,
    slots: list[Slot],
    prizes: list[int],
    deadline: datetime,
    vote_url: str,
    join_url: str,
) -> str:
    """Пост в канале: одна пара (или группа) первого/любого раунда."""
    participants = "\n".join(f"{i}. {nick(s.nickname)}" for i, s in enumerate(slots, start=1))
    return (
        f"<b>{round_title(round_no, is_final)}</b>\n\n"
        f"{prizes_block(prizes)}\n\n"
        f'📊 <a href="{vote_url}"><b>ПРОГОЛОСОВАТЬ</b></a>\n'
        f'🎫 <a href="{join_url}"><b>Принять участие</b></a>\n\n'
        f"<b>{spaced('УЧАСТНИКИ')}</b>\n"
        f"{participants}\n\n"
        f"{deadline_line(deadline)}"
    )


def channel_result(round_no: int, is_final: bool, ranking: list[Slot], tie_broken: bool) -> str:
    """Чем пост становится после закрытия голосования."""
    lines = []
    for slot in ranking:
        mark = MEDAL.get(slot.position, f"{slot.position}.") if is_final else (
            "✅" if slot.position == 1 else "❌"
        )
        lines.append(f"{mark} {nick(slot.nickname)} — {slot.votes} голос(ов)")

    header = "🏆 <b>ИТОГИ ФИНАЛА</b>" if is_final else f"✅ <b>ИТОГИ · {round_no} раунд</b>"
    tail = "\n\n🎲 Голоса сравнялись — победитель определён жребием." if tie_broken else ""
    return f"{header}\n\n" + "\n".join(lines) + tail


def voting_screen(round_no: int, is_final: bool, deadline: datetime) -> str:
    """Шапка экрана голосования в боте."""
    title = "ФИНАЛ" if is_final else f"{round_no} раунд"
    return (
        f"🚀 <b>ГОЛОСОВАНИЕ | {title}</b>\n\n"
        f"<blockquote>Условия: нужно опередить соперника по голосам.</blockquote>\n\n"
        f"🎁 <b>Выберите, за кого голосуете:</b>\n"
        f"<i>Итоги в {deadline.strftime('%H:%M')} МСК</i>"
    )


CROWN = "👑"


def vote_button(slot: Slot, index: int) -> str:
    return f"{index}) {slot.nickname} — {slot.votes} голосов"


APPLICATION_ACCEPTED = (
    "✅ <b>Заявка принята</b>\n\n"
    "<blockquote>Ожидайте старта батла</blockquote>"
)

IN_QUEUE = (
    "✅ <b>Вы в очереди</b>\n\n"
    "<blockquote>Как только подойдёт соперник, вы получите ссылку на свой пост.</blockquote>"
)

YOU_LOST = (
    "❌ <b>Вы проиграли</b>\n\n"
    "<i>Попробуйте снова в следующем батле</i>"
)

YOU_ADVANCED = "🔥 <b>Вы прошли дальше!</b>\n\nСледующий раунд уже опубликован."

NEED_USERNAME = (
    "⚠️ Чтобы участвовать, задайте себе @username в настройках Telegram — "
    "ник показывается в посте канала."
)

ALREADY_IN_BATTLE = "Вы уже участвуете в текущем батле."

NO_ACTIVE_BATTLE = "Сейчас батл не идёт. Ждите анонса в канале."

HELP = (
    "ℹ️ <b>Как это работает</b>\n\n"
    "1. Жмёте «Принять участие» — заявка попадает в очередь.\n"
    "2. Как только набирается пара, ваш пост выходит в канале.\n"
    "3. Зовёте голосующих по своей ссылке — счёт виден в реальном времени.\n"
    "4. В час подведения итогов бот считает голоса: кто впереди — идёт дальше.\n"
    "5. 1 раунд — 1vs1, дальше группы по 4 ника, финал забирает призы.\n\n"
    "Голосовать может любой подписчик канала: один бесплатный голос на матч."
)


def subscribe_required(channel_url: str) -> str:
    return (
        "⚠️ Чтобы проголосовать, необходимо подписаться на канал: "
        f'<a href="{channel_url}">{escape(channel_url)}</a>'
    )


def profile(username: str | None, stats, balance: int) -> str:
    battles = stats["battles"] if stats else 0
    wins = stats["wins"] if stats else 0
    titles = stats["titles"] if stats else 0
    best = stats["best_place"] if stats and stats["best_place"] else "—"
    return (
        f"👤 <b>Профиль</b>\n\n"
        f"Ник: {nick(username or 'без username')}\n"
        f"Батлов: {battles}\n"
        f"Побед в матчах: {wins}\n"
        f"Титулов: {titles}\n"
        f"Лучшее место: {best}\n"
        f"Купленных голосов: {balance}"
    )


def leaderboard(rows) -> str:
    if not rows:
        return "Таблица лидеров пока пуста."
    lines = []
    for index, row in enumerate(rows, start=1):
        mark = MEDAL.get(index, f"{index}.")
        lines.append(
            f"{mark} {nick(row['username'] or str(row['user_id']))} — "
            f"{row['titles']} 🏆 / {row['wins']} побед"
        )
    return "🏅 <b>Таблица лидеров</b>\n\n" + "\n".join(lines)


def final_announcement(ranking: list[Slot], prizes: list[int]) -> str:
    lines = []
    for slot in ranking[: len(prizes)]:
        prize = prizes[slot.position - 1]
        lines.append(f"{MEDAL.get(slot.position, '')} {nick(slot.nickname)} — {prize}⭐")
    return "🏆 <b>Батл завершён!</b>\n\n" + "\n".join(lines)
