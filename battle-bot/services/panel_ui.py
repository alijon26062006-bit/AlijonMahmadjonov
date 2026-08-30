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
        [button("🩺 Диагностика", "health"), button("🔗 Ссылки", "links")],
        [button("🛡 Группы", "groups")],
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
        hint = (
            "Бот разобьёт их на пары и опубликует все посты сразу.\n"
            "Кто придёт позже — попадёт в этот же батл."
            if enough
            else "Создавайте смело: <b>батл заводится первым</b>, а люди "
                 "подтянутся из главного канала по кнопке «Участвовать» — "
                 "весь первый раунд идёт на набор."
        )
        body = (
            "<i>Сейчас батл не идёт.</i>\n\n"
            f"🎫 В очереди: <b>{waiting}</b> "
            f"{texts.plural(waiting, 'человек', 'человека', 'человек')}\n"
            f"<i>Удобный минимум: {stats['min_participants']} — "
            f"это подсказка, а не запрет</i>\n\n"
            f"{hint}"
        )
        rows = [[button(f"▶️ Создать батл ({waiting})", "battle:create", GREEN)]]
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
    return text, keyboard(
        [button("✏️ Изменить", "edit:prizes", BLUE)],
        [button("💸 Выплаты", "pays")],
        back_row(),
    )


def payouts(unpaid, done, total: int) -> tuple[str, InlineKeyboardMarkup]:
    """Кому приз ещё не отправлен и что уже выплачено.

    Пока список не пуст — кто-то ждёт свои звёзды и рассказывает об этом
    другим. Поэтому он стоит первым.
    """
    from services import prizes as prize_list

    waiting = "\n".join(
        f"{texts.MEDAL.get(int(row['place']), '🏅')} <b>{escape(row['nickname'])}</b> "
        f"<i>· батл #{row['battle_id']}</i>"
        for row in unpaid
    ) or "<i>никто не ждёт — все призы выплачены</i>"

    paid = "\n".join(
        f"{texts.MEDAL.get(int(row['place']), '🏅')} {escape(row['nickname'] or '—')} — "
        f"<b>{prize_list.label(str(row['prize']))}</b>"
        for row in done[:5]
    ) or "<i>пока ничего</i>"

    text = (
        f"💸 <b>{texts.spaced('ВЫПЛАТЫ')}</b>\n{RULE}\n\n"
        f"<b>Ждут приз</b>\n{waiting}\n\n"
        f"<b>Последние выплаты</b>\n{paid}\n\n"
        f"Всего выплачено: <b>{total}</b>\n\n"
        "<i>Нажмите на имя и пришлите скриншот перевода — бот выложит его "
        "в главный канал. Без доказательств призам не верят, а значит и "
        "голоса не покупают.</i>"
    )

    buttons = [
        [button(
            f"{texts.MEDAL.get(int(row['place']), '🏅')} {row['nickname']} · #{row['battle_id']}",
            f"pays:do:{row['battle_id']}:{row['user_id']}",
            GREEN,
        )]
        for row in unpaid
    ]
    return text, keyboard(
        *buttons,
        [button("🏛 Выложить зал славы", "pays:hall", BLUE)],
        [button("🔄 Обновить", "pays")],
        back_row("prizes"),
    )


# ------------------------------------------------------------------ голоса

SEEDING_TITLES = {
    "snake": "посев по силе",
    "random": "жеребьёвка",
}
SEEDING_NEXT = {"snake": "random", "random": "snake"}


SCOPE_TITLES = {
    "battle": "один на весь батл",
    "round": "один на раунд",
    "match": "один на каждую пару",
}

# по кругу: батл -> раунд -> пара -> батл
SCOPE_NEXT = {"battle": "round", "round": "match", "match": "battle"}


def votes(
    price: int, enabled: bool, sold: tuple[int, int], stars_link: str = "",
    scope: str = "battle",
) -> tuple[str, InlineKeyboardMarkup]:
    count, stars = sold
    link = f"<code>{escape(stars_link)}</code>" if stars_link else "<i>не задана</i>"
    scope_title = SCOPE_TITLES.get(scope, scope)
    text = (
        f"⭐ <b>{texts.spaced('ГОЛОСА')}</b>\n{RULE}\n\n"
        f"Цена одного голоса: <b>{price}⭐</b>\n"
        f"Продажа: <b>{onoff(enabled)}</b>\n"
        f"Ссылка «звёзды дешевле»: {link}\n\n"
        f"🎁 Бесплатный голос: <b>{scope_title}</b>\n\n"
        f"Продано всего: <b>{count}</b> голосов на <b>{stars}⭐</b>\n\n"
        "<i>Чем уже бесплатный голос, тем чаще их покупают. "
        "«Один на весь батл» — поддержал одну пару, за остальные "
        "нужны купленные.</i>"
    )
    toggle = "Выключить продажу" if enabled else "Включить продажу"
    return text, keyboard(
        [button("✏️ Изменить цену", "edit:vote_price", BLUE)],
        [button(f"🎁 Бесплатный: {scope_title}", "votes:scope")],
        [button("🏦 Оплата вручную", "pay")],
        [button("🧱 Ссылка на звёзды", "edit:stars_link")],
        [button(toggle, "votes:toggle", RED if enabled else GREEN)],
        back_row(),
    )


# --------------------------------------------------- оплата вручную

def _short(value: str, limit: int = 60) -> str:
    text = " ".join((value or "").split())
    return escape(text[:limit] + "…") if len(text) > limit else escape(text)


def manual_pay(values: dict, stats: tuple[int, int, int], rows) -> tuple[str, InlineKeyboardMarkup]:
    """Второй способ оплаты: реквизиты, цена и заявки на проверке."""
    on = bool(values.get("manual_pay_enabled"))
    details = values.get("manual_pay_details") or ""
    price = values.get("manual_pay_price") or "—"
    currency = values.get("manual_pay_currency") or ""
    note = values.get("manual_pay_note") or ""
    pending, accepted, declined = stats

    warn = ""
    if on and not details:
        warn = (
            "\n\n⚠️ <i>Реквизиты не заполнены — кнопка людям не показывается. "
            "Впишите номер, и способ включится.</i>"
        )

    text = (
        f"🏦 <b>{texts.spaced('ОПЛАТА ВРУЧНУЮ')}</b>\n{RULE}\n\n"
        f"Состояние: <b>{onoff(on)}</b>\n"
        f"Название: <b>{_short(values.get('manual_pay_title') or '—')}</b>\n"
        f"Реквизиты: <code>{_short(details) or '—'}</code>\n"
        f"Цена голоса: <b>{escape(str(price))} {escape(currency)}</b>\n"
        f"Подсказка: {_short(note) or '<i>нет</i>'}\n\n"
        f"🧾 На проверке: <b>{pending}</b>\n"
        f"✅ Принято: <b>{accepted}</b>   ❌ Отклонено: <b>{declined}</b>{warn}\n\n"
        "<i>Человек платит по реквизитам и присылает чек. "
        "Пока чек не рассмотрен, второй он отправить не может.</i>"
    )

    buttons = [
        [button(f"{mark_topup(row)} #{row['id']} · {row['votes']} гол. · {row['amount']}",
                f"pay:show:{row['id']}")]
        for row in rows
    ]
    toggle = "Выключить способ" if on else "Включить способ"
    return text, keyboard(
        *buttons,
        [button("✏️ Название", "edit:manual_pay_title"),
         button("💳 Реквизиты", "edit:manual_pay_details")],
        [button("💰 Цена", "edit:manual_pay_price"),
         button("💱 Валюта", "edit:manual_pay_currency")],
        [button("📝 Подсказка", "edit:manual_pay_note")],
        [button(toggle, "pay:toggle", RED if on else GREEN)],
        [button("🔄 Обновить", "pay", BLUE)],
        back_row("votes"),
    )


def mark_topup(row) -> str:
    return "🧾" if row["photo_id"] else "⏳"


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
        f"📣 Реклама раз в: <b>{interval}</b> ч\n"
        f"🔥 Пост дня между батлами: <b>{onoff(values.get('daily_extra_enabled'))}</b>\n\n"
        f"<b>Рекламные посты</b> ({active} активных)\n{listing}\n\n"
        "<i>Бот сам напоминает перед итогами, зовёт в батл каждый день "
        "в полдень и крутит рекламу по очереди в оба канала. Вечером, когда "
        "батла нет, выходит короткий пост — ник дня, рекорд или зал славы, "
        "чтобы канал не пустовал между батлами.</i>"
    )
    toggle = "Выключить автопилот" if values["autopilot_enabled"] else "Включить автопилот"
    rows = [
        [button("⏰ Напоминания", "edit:reminder_hours", BLUE),
         button("📣 Интервал", "edit:promo_interval_hours")],
        [button("➕ Добавить рекламу", "auto:promo:add", GREEN)],
        [button(
            f"🔥 Пост дня: {'вкл' if values.get('daily_extra_enabled') else 'выкл'}",
            "auto:extra",
        )],
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


# --------------------------------------------------------------- группы

def groups(rows, values: dict) -> tuple[str, InlineKeyboardMarkup]:
    """Чистка спама в группах. Каналов это не касается."""
    lines, buttons = [], []
    for row in rows:
        mark = "✅" if row["moderation"] else "⏸"
        title = escape(row["title"] or str(row["chat_id"]))
        lines.append(f"{mark} <b>{title}</b> — удалено: {row['deleted']}")
        buttons.append([button(f"{mark} {title}", f"groups:card:{row['chat_id']}")])
    listing = "\n".join(lines) if lines else (
        "<i>бот пока не добавлен ни в одну группу</i>"
    )

    words = len([w for w in (values["spam_words"] or "").split(",") if w.strip()])
    text = (
        f"🛡 <b>{texts.spaced('ГРУППЫ')}</b>\n{RULE}\n\n"
        f"{listing}\n\n"
        f"{RULE}\n"
        f"🔗 Удалять ссылки: <b>{onoff(values['spam_delete_links'])}</b>\n"
        f"📄 Удалять пересылки из каналов: "
        f"<b>{onoff(values['spam_delete_forwards'])}</b>\n"
        f"👥 Упоминаний в сообщении: <b>{values['spam_mention_limit']}</b>\n"
        f"🚫 Запрещённых слов: <b>{words}</b>\n"
        f"⛔️ Нарушений до бана: <b>{values['spam_strike_limit']}</b>\n\n"
        "<i>Нажмите на группу, чтобы посмотреть права, число участников и ссылку.\n\n"
        "Работает только в группах, куда бот добавлен администратором. "
        "Главный канал и канал батлов это не затрагивает. Админов группы и "
        "администраторов бота чистка не трогает.</i>\n\n"
        "<blockquote>⚠️ Чтобы бот видел все сообщения группы, в @BotFather "
        "нужно выключить <b>Group Privacy</b>: /mybots → бот → Bot Settings → "
        "Group Privacy → Turn off. Иначе он видит только команды.</blockquote>"
    )
    rows_kb = buttons + [
        [button("🚫 Запрещённые слова", "edit:spam_words", BLUE)],
        [button("🔗 Ссылки", "settings:toggle:spam_delete_links"),
         button("📄 Пересылки", "settings:toggle:spam_delete_forwards")],
        [button("👥 Упоминания", "edit:spam_mention_limit"),
         button("⛔️ До бана", "edit:spam_strike_limit")],
        back_row(),
    ]
    return text, keyboard(*rows_kb)


def group_card(card: dict, row, added_by) -> tuple[str, InlineKeyboardMarkup]:
    """Карточка группы: права бота, размер, ссылка и кто добавил."""
    chat_id = card["chat_id"]
    title = escape(card["title"] or (row["title"] if row else str(chat_id)))

    if card["error"]:
        body = (
            f"⚠️ <b>Бот не видит эту группу</b>\n\n"
            f"<i>{escape(card['error'])}</i>\n\n"
            "Скорее всего, его оттуда убрали."
        )
    else:
        members = card["members"]
        rights = "\n".join(
            f"{'✅' if ok else '❌'} {escape(name)}"
            for name, ok in card["rights"].items()
        ) or "<i>прав нет — бот не администратор</i>"
        warn = (
            "\n\n⚠️ <b>Без права удалять сообщения чистка не работает.</b>"
            if "удалять сообщения" in card["missing"]
            else ""
        )
        body = (
            f"👥 Участников: <b>{members if members is not None else '—'}</b>\n"
            f"🛡 Статус бота: <b>{escape(card['status'] or '—')}</b>\n\n"
            f"<b>Права</b>\n{rights}{warn}"
        )

    who = ""
    if added_by is not None:
        handle = added_by["username"] or added_by["first_name"] or added_by["user_id"]
        who = f"\n➕ Добавил: {escape('@' + str(handle))}"

    deleted = row["deleted"] if row else 0
    on = bool(row and row["moderation"])
    text = (
        f"🛡 <b>{escape(title)}</b>\n{RULE}\n\n"
        f"<code>{chat_id}</code>{who}\n"
        f"🧹 Удалено сообщений: <b>{deleted}</b>\n"
        f"Чистка: <b>{onoff(on)}</b>\n\n"
        f"{body}"
    )

    rows = []
    if card["link"]:
        rows.append([InlineKeyboardButton(text="↗ Открыть группу", url=card["link"])])
    rows += [
        [button("⏸ Выключить чистку" if on else "▶️ Включить чистку",
                f"groups:toggle:{chat_id}", RED if on else GREEN)],
        [button("🔄 Обновить", f"groups:card:{chat_id}", BLUE)],
        [button("🚪 Выйти из группы", f"groups:leave:{chat_id}", RED)],
        back_row("groups"),
    ]
    return text, keyboard(*rows)


# ---------------------------------------------------------------- ссылки

def links(values: dict, battles_url: str) -> tuple[str, InlineKeyboardMarkup]:
    """Кнопки-ссылки под экраном «Помощь»."""
    from services import keyboards as kb

    lines, rows = [], []
    for label, key, _ in kb.HELP_LINKS:
        url = (values.get(key) or "").strip()
        if not url and key == "link_battles":
            shown = f"<i>{escape(battles_url)} (сам канал)</i>" if battles_url else "<i>нет</i>"
        elif url:
            shown = escape(url)
        else:
            shown = "<i>кнопки нет</i>"
        lines.append(f"{label} — {shown}")
        rows.append([button(f"✏️ {label}", f"edit:{key}")])

    text = (
        f"🔗 <b>{texts.spaced('ССЫЛКИ')}</b>\n{RULE}\n\n"
        + "\n".join(lines)
        + "\n\n<i>Это кнопки под экраном «Помощь». Пустая ссылка — кнопки нет. "
        "Чтобы убрать заданную, пришлите дефис.</i>"
    )
    return text, keyboard(*rows, back_row())


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
        f"Закрыли бота: <b>{stats['blocked']}</b>\n"
        f"⏳ Отдыхают после призов: <b>{stats.get('resting', 0)}</b>\n"
        f"🚪 Вышли из канала: <b>{stats.get('leavers', 0)}</b>\n\n"
        "<i>Найдите участника по нику или ID, чтобы посмотреть карточку, "
        "выдать голоса или заблокировать.</i>"
    )
    return text, keyboard(
        [button("🔎 Найти участника", "edit:find_user", BLUE)],
        [button("🏅 Таблица лидеров", "people:top"),
         button("⏳ Паузы", "people:rest")],
        [button("🚪 Вышли из канала", "people:left")],
        back_row(),
    )


def person(row, stats_row, balance: int, invited: tuple[int, int] = (0, 0),
           rest=None, left=None) -> tuple[str, InlineKeyboardMarkup]:
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
    rows = [[button("🎁 Начислить голоса", f"edit:grant:{row['user_id']}", BLUE)]]
    if rest is not None:
        text += (
            f"\n\n⏳ <b>Отдыхает после {rest['place']} места</b>\n"
            f"до {escape(str(rest['until'])[:16].replace('T', ' '))}"
        )
        rows.append([button("⏳ Снять паузу", f"person:rest:{row['user_id']}", GREEN)])
    if left is not None:
        text += (
            f"\n\n🚪 <b>Выходил из канала</b>\n"
            f"раз: <b>{left['times']}</b>, последний "
            f"{escape(str(left['left_at'])[:16].replace('T', ' '))}"
        )
        rows.append([button("🔓 Вернуть доступ", f"person:left:{row['user_id']}", GREEN)])

    unban = button("Разблокировать", f"person:unban:{row['user_id']}", GREEN)
    ban = button("Заблокировать", f"person:ban:{row['user_id']}", RED)
    rows += [
        [unban if banned else ban],
        [button("🔎 Найти другого", "edit:find_user")],
        back_row("people"),
    ]
    return text, keyboard(*rows)


def leavers(rows, enabled: bool, price: int, total: int) -> tuple[str, InlineKeyboardMarkup]:
    """Кто вышел из обязательного канала."""
    lines = []
    for row in rows:
        who = escape("@" + (row["username"] or str(row["user_id"])))
        when = escape(str(row["left_at"])[:16].replace("T", " "))
        again = f" · выходов: {row['times']}" if int(row["times"]) > 1 else ""
        lines.append(f"🚪 {who} — {when}{again}")
    listing = "\n".join(lines) if lines else "<i>никто не выходил</i>"

    money = f"Возврат доступа: <b>{price}⭐</b>" if price else "Возврат: <i>отключён</i>"
    text = (
        f"🚪 <b>{texts.spaced('ВЫШЛИ ИЗ КАНАЛА')}</b>\n{RULE}\n\n"
        f"Штраф: <b>{onoff(enabled)}</b>\n{money}\n"
        f"Всего в списке: <b>{total}</b>\n\n"
        f"{listing}\n\n"
        "<i>Отметка ставится сама, в момент выхода из обязательного канала. "
        "Кнопка «Проверить всех» нужна на случай, если бот в этот момент "
        "лежал: она заново проверяет каждого, кто участвовал или голосовал, "
        "и отмечает тех, кого уже нет в канале.\n\n"
        "Заявки от таких людей не принимаются, пока они не вернут доступ "
        "звёздами. Подписаться обратно недостаточно. "
        "Простить конкретного человека можно в его карточке.</i>"
    )
    toggle = "Выключить штраф" if enabled else "Включить штраф"
    return text, keyboard(
        [button("🔍 Проверить всех сейчас", "people:sweep", BLUE)],
        [button("⭐ Цена возврата", "edit:rejoin_price")],
        [button(toggle, "settings:toggle:leave_penalty_enabled",
                RED if enabled else GREEN)],
        back_row("people"),
    )


def cooldowns(rows, days: int, places: int, price: int) -> tuple[str, InlineKeyboardMarkup]:
    """Кто сейчас отдыхает после призовых мест."""
    lines = []
    for row in rows:
        who = escape("@" + (row["username"] or str(row["user_id"])))
        until = escape(str(row["until"])[:16].replace("T", " "))
        lines.append(f"{texts.MEDAL.get(row['place'], '🏆')} {who} — до {until}")
    listing = "\n".join(lines) if lines else "<i>сейчас никто не отдыхает</i>"

    state = f"<b>{days}</b> дн. за места <b>1–{places}</b>" if days else "<b>выключена</b>"
    buy = f"Выкуп: <b>{price}⭐</b>" if price else "Выкуп: <i>отключён</i>"
    text = (
        f"⏳ <b>{texts.spaced('ПАУЗА ПРИЗЁРАМ')}</b>\n{RULE}\n\n"
        f"Пауза: {state}\n{buy}\n\n"
        f"{listing}\n\n"
        "<i>Призёры пропускают несколько батлов, чтобы призы доставались не "
        "одним и тем же. Голосовать это не мешает — закрыта только заявка. "
        "Снять паузу конкретному человеку можно в его карточке.</i>"
    )
    return text, keyboard(
        [button("✏️ Дней паузы", "edit:cooldown_days", BLUE)],
        [button("🏅 Мест под паузой", "edit:cooldown_places")],
        [button("⭐ Цена выкупа", "edit:cooldown_skip_price")],
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
        f"🎲 Подбор соперников: <b>{SEEDING_TITLES.get(values['seeding'], values['seeding'])}</b>\n"
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
        [button("🎲 Подбор соперников", "settings:seeding")],
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
