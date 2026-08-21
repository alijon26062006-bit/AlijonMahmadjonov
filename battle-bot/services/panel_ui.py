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
        f"🎫 В очереди на батл: <b>{stats['queue']}</b>\n"
        f"🗳 Голосов отдано: <b>{stats['votes']}</b>\n"
        f"🤝 Пришло по приглашениям: <b>{stats['referrals']}</b>\n"
        f"⭐ Продано: <b>{stats['sold_votes']}</b> голосов "
        f"на <b>{stats['sold_stars']}⭐</b>\n\n"
        f"{state}"
    )
    return text, keyboard(
        [button("⚔️ Батл", "battle"), button("🏆 Призы", "prizes")],
        [button("⭐ Голоса", "votes"), button("🤝 Друзья", "referrals")],
        [button("📣 Канал", "channel"), button("👥 Люди", "people")],
        [button("📨 Рассылка", "broadcast"), button("🤖 Автопилот", "auto")],
        [button("🔍 Проверка", "fraud"), button("📡 Каналы", "mych")],
        [button("🩺 Диагностика", "health")],
        [button("⚙️ Настройки", "settings")],
        [button("🔄 Обновить", "home", BLUE)],
    )


# -------------------------------------------------------------------- батл

def battle(stats: dict) -> tuple[str, InlineKeyboardMarkup]:
    current = stats["battle"]
    if current:
        limit = stats.get("late_join_until", 0)
        round_no = int(current["round_no"])
        if round_no <= limit:
            intake = f"🎫 Приём заявок: <b>идёт</b> <i>(до конца {limit} раунда)</i>"
        else:
            intake = "🎫 Приём заявок: <b>закрыт</b> <i>(копятся на следующий батл)</i>"

        waiting = stats.get("waiting_rival", 0)
        rival_line = (
            f"\n⏳ Ждут соперника: <b>{waiting}</b>" if waiting else ""
        )
        body = (
            f"Батл <b>#{current['id']}</b>\n"
            f"Состояние: <b>{current['status']}</b>\n"
            f"Раунд: <b>{round_no}</b>\n"
            f"Заявок: <b>{stats['participants']}</b>\n"
            f"В игре: <b>{stats['alive']}</b>\n"
            f"Открытых матчей: <b>{stats['open_matches']}</b>{rival_line}\n"
            f"{intake}\n"
            f"🗓 Итоги в <b>{stats['deadline']}</b>\n\n"
            f"Прогноз сетки: <code>{stats['projection']}</code>"
        )
        rows = [
            [button("🏁 Подвести итоги сейчас", "battle:close", GREEN)],
            [button("⏭ Перенести дедлайн", "battle:postpone")],
            [button("🛑 Отменить батл", "battle:cancel:ask", RED)],
        ]
    else:
        waiting = stats["queue"]
        enough = waiting >= stats["min_participants"]
        body = (
            "<i>Сейчас батл не идёт.</i>\n\n"
            f"🎫 В очереди: <b>{waiting}</b> "
            f"{texts.plural(waiting, 'человек', 'человека', 'человек')}\n"
            f"Нужно минимум: <b>{stats['min_participants']}</b>\n\n"
            + (
                "Бот разобьёт их на пары и опубликует все посты сразу."
                if enough
                else "<b>Людей пока не хватает.</b> Ждём новые заявки."
            )
        )
        rows = [
            [
                button(
                    f"▶️ Создать батл ({waiting})",
                    "battle:create",
                    GREEN if enough else None,
                )
            ]
        ]
        if waiting:
            rows.append([button("🗑 Очистить очередь", "battle:clear:ask", RED)])

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

def prizes(values: list[str]) -> tuple[str, InlineKeyboardMarkup]:
    from services import prizes as prize_list

    lines = [
        f"{texts.MEDAL.get(i, f'{i}.')} <b>{prize_list.label(value)}</b>"
        for i, value in enumerate(values, start=1)
    ] or ["<i>призы не заданы</i>"]
    text = (
        f"🏆 <b>{texts.spaced('ПРИЗЫ')}</b>\n{RULE}\n\n"
        + "\n".join(lines)
        + "\n\n<i>Призы получают первые места финала. "
        "Сколько мест — столько и призов.</i>\n\n"
        "<blockquote>Приз можно писать текстом: <b>число</b> бот покажет "
        "как звёзды, а любой другой текст — как есть. "
        "Например «Telegram Premium на 3 месяца» или «Реклама в канале».</blockquote>"
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


# ------------------------------------------------------ проверка накрутки

def _who(row, field: str = "username") -> str:
    name = row[field] if field in row.keys() and row[field] else None
    return escape("@" + name) if name else f"<code>{row['target_id']}</code>"


def fraud(signals: dict) -> tuple[str, InlineKeyboardMarkup]:
    """Что выглядит подозрительно. Бот не банит сам — решает админ."""
    blocks = []

    own = signals["own_referrals"]
    if own:
        lines = [
            f"• {_who(row, 'username')} — <b>{row['own_votes']}</b> из "
            f"{row['all_votes']} голосов от им же приглашённых"
            for row in own
        ]
        blocks.append("<b>🚩 Голосуют свои приглашённые</b>\n" + "\n".join(lines))

    bursts = signals["bursts"]
    if bursts:
        lines = [
            f"• {_who(row)} — <b>{row['burst']}</b> голосов за минуту "
            f"<i>({row['started'][11:16]})</i>"
            for row in bursts
        ]
        blocks.append("<b>⚡ Всплески голосов</b>\n" + "\n".join(lines))

    loyal = signals["loyal"]
    if loyal:
        lines = [
            f"• <code>{row['voter_id']}</code> — <b>{row['votes']}</b> голосов "
            f"и все за одного"
            for row in loyal
        ]
        blocks.append("<b>👥 Голосуют всегда за одного</b>\n" + "\n".join(lines))

    fresh = signals["fresh"]
    if fresh:
        lines = [
            f"• {_who(row)} — <b>{row['votes']}</b> голосов от новых аккаунтов"
            for row in fresh
        ]
        blocks.append("<b>🆕 Голоса свежих аккаунтов</b>\n" + "\n".join(lines))

    body = "\n\n".join(blocks) if blocks else "✅ <i>Ничего подозрительного не вижу.</i>"

    text = (
        f"🔍 <b>{texts.spaced('ПРОВЕРКА')}</b>\n{RULE}\n\n"
        f"{body}\n\n{RULE}\n"
        "<i>Это подсказки, а не приговор: у популярного участника всплеск "
        "голосов бывает и честным. Смотрите сами — заблокировать можно "
        "в разделе «Люди».</i>"
    )
    return text, keyboard(
        [button("🔄 Пересчитать", "fraud", BLUE)],
        [button("👥 К людям", "people")],
        back_row(),
    )


# -------------------------------------------------------------- автопилот

def autopilot(values: dict, promos: list) -> tuple[str, InlineKeyboardMarkup]:
    hours = values["reminder_hours"] or "—"
    interval = values["promo_interval_hours"]
    active = sum(1 for row in promos if row["enabled"])

    lines = []
    for row in promos:
        mark = "✅" if row["enabled"] else "⏸"
        preview = escape(row["text"][:40]) + ("…" if len(row["text"]) > 40 else "")
        lines.append(f"{mark} <code>#{row['id']}</code> {preview} · показов: {row['sent_count']}")
    listing = "\n".join(lines) if lines else "<i>пока пусто</i>"

    text = (
        f"🤖 <b>{texts.spaced('АВТОПИЛОТ')}</b>\n{RULE}\n\n"
        f"Состояние: <b>{onoff(values['autopilot_enabled'])}</b>\n"
        f"⏰ Напоминать за: <b>{hours}</b> ч до итогов\n"
        f"📣 Реклама раз в: <b>{interval}</b> ч\n\n"
        f"<b>Рекламные посты</b> ({active} активных)\n{listing}\n\n"
        "<i>Бот сам напоминает перед итогами, зовёт в батл каждый день "
        "в полдень и крутит рекламу по очереди в оба канала.</i>"
    )
    toggle = "Выключить автопилот" if values["autopilot_enabled"] else "Включить автопилот"
    rows = [
        [button("⏰ Напоминания", "edit:reminder_hours", BLUE),
         button("📣 Интервал", "edit:promo_interval_hours")],
        [button("➕ Добавить рекламу", "auto:promo:add", GREEN)],
    ]
    if promos:
        rows.append([button("🗂 Управление постами", "auto:promos")])
    rows.append([button(toggle, "auto:toggle", RED if values["autopilot_enabled"] else GREEN)])
    return text, keyboard(*rows, back_row())


def promo_list(promos: list) -> tuple[str, InlineKeyboardMarkup]:
    rows = []
    for row in promos:
        mark = "✅" if row["enabled"] else "⏸"
        title = escape(row["text"][:24]) + ("…" if len(row["text"]) > 24 else "")
        rows.append([
            button(f"{mark} #{row['id']} {title}", f"auto:promo:toggle:{row['id']}"),
            button("🗑", f"auto:promo:del:{row['id']}", RED),
        ])
    return (
        f"🗂 <b>Рекламные посты</b>\n{RULE}\n\n"
        "<i>Нажмите на пост, чтобы включить или выключить. "
        "Корзина удаляет его насовсем.</i>",
        keyboard(*rows, back_row("auto")),
    )


# ---------------------------------------------------------------- друзья

def referrals(reward: int, enabled: bool, report: dict, top) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        f"{texts.MEDAL.get(index, f'{index}.')} "
        f"{escape('@' + (row['username'] or str(row['inviter_id'])))} — "
        f"<b>{row['rewarded']}</b> из {row['invited']}"
        for index, row in enumerate(top, start=1)
    ]
    top_block = "\n".join(lines) if lines else "<i>пока никто никого не привёл</i>"

    text = (
        f"🤝 <b>{texts.spaced('ДРУЗЬЯ')}</b>\n{RULE}\n\n"
        f"<b>Всего пришло по ссылкам: {report['total']}</b>\n"
        f"✅ Засчитано: <b>{report['rewarded']}</b> "
        f"<i>({report['share']}%)</i>\n"
        f"⏳ Ждут подписки: <b>{report['pending']}</b>\n\n"
        f"📅 За сутки: <b>{report['today']}</b>\n"
        f"🗓 За неделю: <b>{report['week']}</b>\n"
        f"👤 Приглашали: <b>{report['inviters']}</b> "
        f"{texts.plural(report['inviters'], 'человек', 'человека', 'человек')}\n\n"
        f"{RULE}\n"
        f"Награда за друга: <b>{reward}</b> "
        f"{texts.plural(reward, 'голос', 'голоса', 'голосов')}\n"
        f"Приглашения: <b>{onoff(enabled)}</b>\n\n"
        f"<b>Кто приводит больше всех</b>\n{top_block}\n\n"
        "<i>Засчитывается только новый друг, который подписался на канал. "
        "«Ждут подписки» — пришли по ссылке, но ещё не подписались.</i>"
    )
    toggle = "Выключить приглашения" if enabled else "Включить приглашения"
    return text, keyboard(
        [button("✏️ Изменить награду", "edit:referral_reward", BLUE)],
        [button(toggle, "referrals:toggle", RED if enabled else GREEN)],
        back_row(),
    )


# ------------------------------------------------------------ диагностика

def health(summary, recent, tasks: dict) -> tuple[str, InlineKeyboardMarkup]:
    """Что и как часто ломалось. Отсюда становится видно причину «нестабильности»."""
    if summary:
        counts = "\n".join(
            f"• <b>{escape(row['kind'])}</b> — {row['times']} "
            f"{texts.plural(row['times'], 'раз', 'раза', 'раз')}"
            for row in summary
        )
    else:
        counts = "✅ <i>за сутки ни одного сбоя</i>"

    lines = []
    for row in recent:
        when = str(row["created_at"])[5:16]
        what = escape(str(row["message"])[:110])
        where = escape(str(row["action"])[:40]) if row["action"] else "—"
        lines.append(f"<b>{when}</b> · <code>{escape(row['kind'])}</code>\n"
                     f"   {what}\n   <i>на: {where}</i>")
    journal = "\n\n".join(lines) if lines else "<i>журнал пуст</i>"

    alive = "\n".join(
        f"{'✅' if ok else '❌'} {escape(name)}" for name, ok in tasks.items()
    )

    text = (
        f"🩺 <b>{texts.spaced('ДИАГНОСТИКА')}</b>\n{RULE}\n\n"
        f"<b>Фоновые задачи</b>\n{alive}\n\n"
        f"<b>Сбои за сутки</b>\n{counts}\n\n"
        f"{RULE}\n<b>Последние записи</b>\n\n{journal}"
    )
    return text, keyboard(
        [button("🔄 Обновить", "health", BLUE)],
        [button("🧹 Очистить журнал", "health:clear", RED)],
        back_row(),
    )


# -------------------------------------------------- каналы участников

def member_channels(
    enabled: bool, total: int, live: int, posts: int, rows
) -> tuple[str, InlineKeyboardMarkup]:
    """Кто из участников подключил свой канал и сколько постов туда ушло."""
    lines = []
    for row in rows:
        owner = escape("@" + (row["owner_username"] or str(row["user_id"])))
        title = escape(row["title"] or str(row["chat_id"]))
        mark = "✅" if row["active"] else "⚠️"
        lines.append(f"{mark} <b>{title}</b> — {owner}, постов: <b>{row['posts']}</b>")
    listing = "\n".join(lines) if lines else "<i>пока никто не подключил</i>"

    text = (
        f"📡 <b>{texts.spaced('КАНАЛЫ УЧАСТНИКОВ')}</b>\n{RULE}\n\n"
        f"Публикация: <b>{onoff(enabled)}</b>\n"
        f"Подключено: <b>{total}</b>, из них живых: <b>{live}</b>\n"
        f"Постов опубликовано: <b>{posts}</b>\n\n"
        f"{listing}\n\n"
        "<i>Участник добавляет бота администратором в свой канал, и бот сам "
        "публикует туда его пару с кнопкой «Голосовать за меня». "
        "⚠️ — бота лишили прав, публикация в этот канал выключена.</i>"
    )
    toggle = "Выключить публикацию" if enabled else "Включить публикацию"
    return text, keyboard(
        [button(toggle, "mych:toggle", RED if enabled else GREEN)],
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
        f"Заблокировано админом: <b>{stats['banned']}</b>\n"
        f"Закрыли бота: <b>{stats['blocked']}</b>\n\n"
        "<i>Найдите участника по нику или ID, чтобы посмотреть карточку, "
        "выдать голоса или заблокировать.</i>"
    )
    return text, keyboard(
        [button("🔎 Найти участника", "edit:find_user", BLUE)],
        [button("🏅 Таблица лидеров", "people:top")],
        back_row(),
    )


def person(row, stats_row, balance: int, invited: tuple[int, int] = (0, 0)) -> tuple[str, InlineKeyboardMarkup]:
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
        f"🎁 Голосов на балансе: <b>{balance}</b>\n"
        f"🤝 Привёл друзей: <b>{invited[1]}</b> из {invited[0]}"
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
        f"🎫 Приём заявок в идущий батл: <b>до {values['late_join_until_round']} раунда</b>\n"
        f"🔖 Требовать @username: <b>{onoff(values['require_username'])}</b>\n"
        f"🎨 Премиум-эмодзи в канале: <b>{values['premium_emoji_in_channel']}</b>\n\n"
        f"<b>Обязательная подписка</b>\n"
        f"Голосование: <b>всегда</b>\n"
        f"Заявки и рефералы: <b>{onoff(values['require_subscription'])}</b>\n"
        f"Каналы: {listing}{source}\n\n"
        "<i>Проголосовать без подписки нельзя ни при каких настройках — "
        "переключатель влияет только на заявки и приглашения. "
        "Канал с парами сюда обычно не входит: в него заходят по ссылке из поста.</i>"
    )
    return text, keyboard(
        [button("🗓 Время итогов", "edit:round_times", BLUE)],
        [button("👥 Минимум", "edit:min_participants"),
         button("Максимум", "edit:max_participants")],
        [button("🎫 Приём заявок до раунда", "edit:late_join_until_round")],
        [button("📣 Подписка для заявок", "settings:toggle:require_subscription")],
        [button("🆔 Каналы подписки", "edit:sponsor_channels")],
        [button("🩺 Проверить каналы", "settings:check", BLUE)],
        [button("🔖 @username", "settings:toggle:require_username")],
        back_row(),
    )


def subscription_check(rows: list[tuple[int, str]]) -> tuple[str, InlineKeyboardMarkup]:
    """Отчёт: может ли бот спрашивать статус подписчика в каждом канале."""
    lines = []
    for channel_id, problem in rows:
        if problem:
            lines.append(f"❌ <code>{channel_id}</code>\n    <i>{escape(problem)}</i>")
        else:
            lines.append(f"✅ <code>{channel_id}</code> — проверка работает")
    body = "\n".join(lines) or "<i>Каналы не заданы.</i>"
    hint = (
        "\n\n<i>Если стоит ❌, добавьте бота в этот канал администратором — "
        "иначе он не видит подписчиков и никто не сможет проголосовать.</i>"
        if any(problem for _, problem in rows) else ""
    )
    text = f"🩺 <b>{texts.spaced('ПРОВЕРКА ПОДПИСКИ')}</b>\n{RULE}\n\n{body}{hint}"
    return text, keyboard(back_row("settings"))


def ask(field_title: str, current: str, hint: str, back: str) -> tuple[str, InlineKeyboardMarkup]:
    """Экран ожидания ввода.

    Многострочное значение (список призов) показываем блоком — в строку
    «Сейчас: …» оно не помещается и читается как каша.
    """
    if "\n" in current:
        now = f"Сейчас:\n<blockquote>{escape(current)}</blockquote>\n"
    else:
        now = f"Сейчас: <b>{escape(current)}</b>\n\n"
    text = (
        f"✏️ <b>{escape(field_title)}</b>\n{RULE}\n\n"
        f"{now}"
        f"Пришлите новое значение сообщением."
    )
    if hint:
        text += f"\n<i>{escape(hint)}</i>"
    return text, keyboard([button("Отмена", back)])
