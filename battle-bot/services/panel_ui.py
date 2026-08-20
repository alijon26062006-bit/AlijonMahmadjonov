"""Экраны и клавиатуры админ-панели.

Панель — одно сообщение, которое перерисовывается на месте. Поэтому каждый
экран это пара «текст + клавиатура», а не отдельное сообщение.
"""
from __future__ import annotations

from html import escape

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from services import texts
from services.keyboards import BLUE, GREEN, RED

RULE = texts.RULE
BACK = "◀️ Назад"


PREFIX = "p:"


def button(text: str, action: str, style: str | None = None) -> InlineKeyboardButton:
    """Кнопка панели.

    Префикс добавляется здесь и только здесь. Если вызывающий код уже передал
    его — не дублируем: иначе получалось «p:p:channel», и кнопка молча
    переставала работать.
    """
    if not action.startswith(PREFIX):
        action = PREFIX + action
    return InlineKeyboardButton(text=text, callback_data=action, style=style)


def keyboard(*rows: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[row for row in rows if row])


def back_row(action: str = "home") -> list[InlineKeyboardButton]:
    return [button(BACK, action)]


def onoff(flag: bool) -> str:
    return "включено ✅" if flag else "выключено ❌"


# ------------------------------------------------------------- главный экран

def home(stats: dict) -> tuple[str, InlineKeyboardMarkup]:
    battle = stats["battle"]
    if battle:
        stage = "финал" if stats["is_final"] else f"{battle['round_no']} раунд"
        state = (
            f"⚔️ Батл <b>#{battle['id']}</b> · {stage}\n"
            f"🗓 Итоги в <b>{stats['deadline']}</b>"
        )
    else:
        state = "⚔️ <i>Батл не идёт</i>"

    text = (
        f"🛠 <b>{texts.spaced('ПАНЕЛЬ')}</b>\n"
        f"{RULE}\n\n"
        f"👥 Пользователей: <b>{stats['users']}</b>"
        f"   <i>(+{stats['new_users']} за сутки)</i>\n"
        f"📝 Заявок в очереди: <b>{stats['queue']}</b>\n"
        f"🗳 Голосов отдано: <b>{stats['votes']}</b>\n"
        f"⭐ Продано: <b>{stats['sold_votes']}</b> голосов "
        f"на <b>{stats['sold_stars']}⭐</b>\n\n"
        f"{state}"
    )
    return text, keyboard(
        [button("⚔️ Батл", "battle"), button("🏆 Призы", "prizes")],
        [button("⭐ Голоса", "votes"), button("🤝 Друзья", "referrals")],
        [button("📣 Канал", "channel"), button("👥 Люди", "people")],
        [button("⚙️ Настройки", "settings")],
        [button("🔄 Обновить", "home", BLUE)],
    )


# -------------------------------------------------------------------- батл

def battle(stats: dict) -> tuple[str, InlineKeyboardMarkup]:
    current = stats["battle"]
    if current:
        body = (
            f"Батл <b>#{current['id']}</b>\n"
            f"Состояние: <b>{current['status']}</b>\n"
            f"Раунд: <b>{current['round_no']}</b>\n"
            f"Заявок: <b>{stats['participants']}</b>\n"
            f"В игре: <b>{stats['alive']}</b>\n"
            f"Открытых матчей: <b>{stats['open_matches']}</b>\n"
            f"🗓 Итоги в <b>{stats['deadline']}</b>\n\n"
            f"Прогноз сетки: <code>{stats['projection']}</code>"
        )
        rows = [
            [button("🏁 Подвести итоги сейчас", "battle:close", GREEN)],
            [button("⏭ Перенести дедлайн", "battle:postpone")],
            [button("🛑 Отменить батл", "battle:cancel:ask", RED)],
        ]
    else:
        body = (
            "<i>Сейчас батл не идёт.</i>\n\n"
            "Он откроется сам от первой заявки, но можно открыть приём вручную — "
            "тогда бот сразу начнёт собирать пары."
        )
        rows = [[button("▶️ Открыть приём заявок", "battle:start", GREEN)]]

    return f"⚔️ <b>{texts.spaced('БАТЛ')}</b>\n{RULE}\n\n{body}", keyboard(*rows, back_row())


def confirm(question: str, yes_action: str, back: str) -> tuple[str, InlineKeyboardMarkup]:
    return (
        f"❓ <b>Подтвердите</b>\n{RULE}\n\n{question}",
        keyboard(
            [button("Да, продолжить", yes_action, RED)],
            [button("Отмена", back)],
        ),
    )


# ------------------------------------------------------------------- призы

def prizes(values: list[int]) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        f"{texts.MEDAL.get(i, f'{i}.')} <b>{amount}⭐</b>"
        for i, amount in enumerate(values, start=1)
    ]
    text = (
        f"🏆 <b>{texts.spaced('ПРИЗЫ')}</b>\n{RULE}\n\n"
        + "\n".join(lines)
        + "\n\n<i>Призы получают первые места финала. "
        "Сколько мест — столько и призов.</i>"
    )
    return text, keyboard([button("✏️ Изменить", "edit:prizes", BLUE)], back_row())


# ------------------------------------------------------------------ голоса

def votes(
    price: int, enabled: bool, sold: tuple[int, int], stars_link: str = ""
) -> tuple[str, InlineKeyboardMarkup]:
    count, stars = sold
    link = f"<code>{escape(stars_link)}</code>" if stars_link else "<i>не задана</i>"
    text = (
        f"⭐ <b>{texts.spaced('ГОЛОСА')}</b>\n{RULE}\n\n"
        f"Цена одного голоса: <b>{price}⭐</b>\n"
        f"Продажа: <b>{onoff(enabled)}</b>\n"
        f"Ссылка «звёзды дешевле»: {link}\n\n"
        f"Продано всего: <b>{count}</b> голосов на <b>{stars}⭐</b>\n\n"
        "<i>Первый голос в матче всегда бесплатный. "
        "Купленные добавляются сверх него.</i>"
    )
    toggle = "Выключить продажу" if enabled else "Включить продажу"
    return text, keyboard(
        [button("✏️ Изменить цену", "edit:vote_price", BLUE)],
        [button("🧱 Ссылка на звёзды", "edit:stars_link")],
        [button(toggle, "votes:toggle", RED if enabled else GREEN)],
        back_row(),
    )


# ---------------------------------------------------------------- друзья

def referrals(reward: int, enabled: bool, totals: tuple[int, int], top) -> tuple[str, InlineKeyboardMarkup]:
    invited, rewarded = totals
    lines = [
        f"{index}. {escape('@' + (row['username'] or str(row['inviter_id'])))} — "
        f"<b>{row['rewarded']}</b> из {row['invited']}"
        for index, row in enumerate(top, start=1)
    ]
    top_block = "\n".join(lines) if lines else "<i>пока никто никого не привёл</i>"

    text = (
        f"🤝 <b>{texts.spaced('ДРУЗЬЯ')}</b>\n{RULE}\n\n"
        f"Награда за друга: <b>{reward}</b> "
        f"{texts.plural(reward, 'голос', 'голоса', 'голосов')}\n"
        f"Приглашения: <b>{onoff(enabled)}</b>\n\n"
        f"👥 Пришло по ссылкам: <b>{invited}</b>\n"
        f"✅ Засчитано: <b>{rewarded}</b>\n\n"
        f"<b>Кто приводит больше всех</b>\n{top_block}\n\n"
        "<i>Голос засчитывается, только когда друг новый и подписался на канал.</i>"
    )
    toggle = "Выключить приглашения" if enabled else "Включить приглашения"
    return text, keyboard(
        [button("✏️ Изменить награду", "edit:referral_reward", BLUE)],
        [button(toggle, "referrals:toggle", RED if enabled else GREEN)],
        back_row(),
    )


# ------------------------------------------------------------------- канал

def channel(state: dict) -> tuple[str, InlineKeyboardMarkup]:
    main_id = state["main_channel_id"]
    where = f"<code>{main_id}</code>" if main_id else "<i>не задан</i>"
    photo = "есть ✅" if state["photo"] else "без фото — обычный пост"
    published = "опубликован ✅" if state["message_id"] else "не опубликован ❌"

    text = (
        f"📣 <b>{texts.spaced('КАНАЛ')}</b>\n{RULE}\n\n"
        f"<b>Главный пост</b>\n"
        f"Канал: {where}\n"
        f"Фото: <b>{photo}</b>\n"
        f"Текст: <b>{'задан' if state['text'] else 'по умолчанию'}</b>\n"
        f"Состояние: <b>{published}</b>\n\n"
        f"<b>Канал батлов</b>\n"
        f"Постов опубликовано: <b>{state['battle_posts']}</b>"
    )

    rows = [
        [button("🆔 Задать главный канал", "edit:main_channel_id", BLUE)],
        [button("🖼 Фото (необязательно)", "edit:main_post_photo")],
        [button("✏️ Изменить текст", "edit:main_post_text")],
    ]
    if main_id:
        label = "🔄 Обновить главный пост" if state["message_id"] else "📤 Опубликовать"
        rows.append([button(label, "channel:publish", GREEN)])
        if state["message_id"]:
            rows.append([button("📌 Закрепить", "channel:pin")])
    if state["battle_posts"]:
        rows.append([button("🗑 Удалить посты батла", "channel:wipe:ask", RED)])
    return text, keyboard(*rows, back_row())


# -------------------------------------------------------------------- люди

def people(stats: dict) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"👥 <b>{texts.spaced('ЛЮДИ')}</b>\n{RULE}\n\n"
        f"Всего: <b>{stats['users']}</b>\n"
        f"Новых за сутки: <b>{stats['new_users']}</b>\n"
        f"Заблокировано: <b>{stats['banned']}</b>\n\n"
        "<i>Найдите участника по нику или ID, чтобы посмотреть карточку, "
        "выдать голоса или заблокировать.</i>"
    )
    return text, keyboard(
        [button("🔎 Найти участника", "edit:find_user", BLUE)],
        [button("🏅 Таблица лидеров", "people:top")],
        back_row(),
    )


def person(row, stats_row, balance: int) -> tuple[str, InlineKeyboardMarkup]:
    handle = f"@{row['username']}" if row["username"] else escape(row["first_name"] or "—")
    banned = bool(row["is_banned"])
    text = (
        f"👤 <b>{escape(handle)}</b>\n{RULE}\n\n"
        f"ID: <code>{row['user_id']}</code>\n"
        f"С нами с: <b>{row['created_at'][:10]}</b>\n"
        f"Статус: <b>{'заблокирован ⛔️' if banned else 'активен ✅'}</b>\n\n"
        f"🏆 Титулов: <b>{stats_row['titles'] if stats_row else 0}</b>\n"
        f"✅ Побед: <b>{stats_row['wins'] if stats_row else 0}</b>\n"
        f"⚔️ Батлов: <b>{stats_row['battles'] if stats_row else 0}</b>\n"
        f"🎁 Голосов на балансе: <b>{balance}</b>"
    )
    unban = button("Разблокировать", f"person:unban:{row['user_id']}", GREEN)
    ban = button("Заблокировать", f"person:ban:{row['user_id']}", RED)
    return text, keyboard(
        [button("🎁 Начислить голоса", f"edit:grant:{row['user_id']}", BLUE)],
        [unban if banned else ban],
        [button("🔎 Найти другого", "edit:find_user")],
        back_row("people"),
    )


# --------------------------------------------------------------- настройки

def settings_screen(values: dict, sponsors: list[int]) -> tuple[str, InlineKeyboardMarkup]:
    times = ", ".join(t.strftime("%H:%M") for t in values["round_times"])
    listing = ", ".join(f"<code>{cid}</code>" for cid in sponsors) or "<i>нет</i>"
    source = "" if values["sponsor_channels"] else " <i>(главный канал)</i>"
    text = (
        f"⚙️ <b>{texts.spaced('НАСТРОЙКИ')}</b>\n{RULE}\n\n"
        f"🗓 Время итогов: <b>{times}</b>\n"
        f"👥 Участников: от <b>{values['min_participants']}</b> "
        f"до <b>{values['max_participants']}</b>\n"
        f"🔖 Требовать @username: <b>{onoff(values['require_username'])}</b>\n"
        f"🎨 Премиум-эмодзи в канале: <b>{values['premium_emoji_in_channel']}</b>\n\n"
        f"<b>Обязательная подписка</b>\n"
        f"Проверка: <b>{onoff(values['require_subscription'])}</b>\n"
        f"Каналы: {listing}{source}\n\n"
        "<i>Подписка нужна, чтобы участвовать, голосовать и приводить друзей. "
        "Канал с парами сюда обычно не входит — в него заходят по ссылке из поста.</i>"
    )
    return text, keyboard(
        [button("🗓 Время итогов", "edit:round_times", BLUE)],
        [button("👥 Минимум", "edit:min_participants"),
         button("Максимум", "edit:max_participants")],
        [button("📣 Подписка", "settings:toggle:require_subscription")],
        [button("🆔 Каналы подписки", "edit:sponsor_channels")],
        [button("🔖 @username", "settings:toggle:require_username")],
        back_row(),
    )


def ask(field_title: str, current: str, hint: str, back: str) -> tuple[str, InlineKeyboardMarkup]:
    """Экран ожидания ввода."""
    text = (
        f"✏️ <b>{escape(field_title)}</b>\n{RULE}\n\n"
        f"Сейчас: <b>{escape(current)}</b>\n\n"
        f"Пришлите новое значение сообщением."
    )
    if hint:
        text += f"\n<i>{escape(hint)}</i>"
    return text, keyboard([button("Отмена", back)])
