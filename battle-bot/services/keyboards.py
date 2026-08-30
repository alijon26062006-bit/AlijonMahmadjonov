"""Клавиатуры бота."""
from __future__ import annotations

from aiogram.types import (
    CopyTextButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from config import Config
from core.models import Slot
from services import links, texts
from services.emoji import leading_emoji

# Цвета кнопок (поле style в Bot API). Telegram принимает только эти три
# значения; всё остальное он отклонит, поэтому держим их в одном месте.
BLUE = "primary"
GREEN = "success"
RED = "danger"

BTN_JOIN = "🚀 Принять участие"
BTN_BUY = "🎁 Купить голоса"
BTN_INVITE = "🤝 Пригласить друзей"
BTN_CHANNEL = "📡 Мой канал"
BTN_PROFILE = "👤 Профиль"
BTN_HELP = "✅ Помощь"


def variants(label: str) -> set[str]:
    """Как подпись кнопки может прийти обратно от Telegram.

    С премиум-иконкой эмодзи уезжает в icon_custom_emoji_id и в тексте его нет,
    без неё — остаётся в подписи. Обработчик должен принимать оба варианта,
    иначе кнопки перестают отвечать при включённых премиум-эмодзи.
    """
    stripped, _ = leading_emoji(label, {label[0]: "1"})
    return {label, stripped}


def _reply_button(
    label: str, table: dict[str, str], style: str | None = None
) -> KeyboardButton:
    """Эмодзи в начале подписи становится премиум-иконкой, если она есть в таблице."""
    text, emoji_id = leading_emoji(label, table)
    return KeyboardButton(text=text, icon_custom_emoji_id=emoji_id, style=style)


def main_menu(config: Config) -> ReplyKeyboardMarkup:
    table = config.premium_emoji
    # главное действие — синим, остальное обычным цветом, чтобы не пестрило
    rows = [[_reply_button(BTN_JOIN, table, BLUE)]]
    if config.paid_votes_enabled:
        rows.append([_reply_button(BTN_BUY, table, GREEN)])
    rows.append([_reply_button(BTN_CHANNEL, table), _reply_button(BTN_PROFILE, table)])
    rows.append([_reply_button(BTN_HELP, table)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def voting(
    match_id: int,
    slots: list[Slot],
    config: Config,
    post_url: str | None,
    called_for: int | None = None,
) -> InlineKeyboardMarkup:
    """Кнопки участников со счётом + служебный ряд.

    ``called_for`` — кого человека звали поддержать (пришёл по ссылке из его
    канала). Такая кнопка помечается огоньком, чтобы её было видно сразу.
    Второй такой же кнопки сверху не делаем: выбор всё равно остаётся за
    голосующим, а дублировать одно действие двумя кнопками — путать.
    """
    best = max((s.votes for s in slots), default=0)
    crown_id = config.premium_emoji.get(texts.CROWN)
    rows = []
    for index, slot in enumerate(slots, start=1):
        leader = slot.votes == best and slot.votes > 0
        label = texts.vote_button(slot, index)
        if slot.user_id == called_for:
            label = f"🔥 {label}"
        # премиум-корона показывается отдельной иконкой, обычная — в конце подписи
        if leader and not crown_id:
            label = f"{label} {texts.CROWN}"
        rows.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"vote:{match_id}:{slot.user_id}",
                    icon_custom_emoji_id=crown_id if leader else None,
                    # зелёным горит только лидер — цвет сразу показывает,
                    # кто впереди. Пока голосов нет, лидера нет тоже.
                    style=GREEN if leader else None,
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="Копировать ссылку",
                copy_text=CopyTextButton(
                    text=links.vote_link(config.bot_username, match_id)
                ),
                style=BLUE,
            )
        ]
    )

    service = [
        InlineKeyboardButton(text="Обновить", callback_data=f"refresh:{match_id}", style=BLUE)
    ]
    if post_url:
        service.append(InlineKeyboardButton(text="Пост ↗", url=post_url, style=BLUE))
    rows.append(service)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def invited_check(channel_url: str) -> InlineKeyboardMarkup:
    """Приглашённому: подписаться и проверить."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Подписаться ↗", url=channel_url, style=GREEN)],
            [InlineKeyboardButton(text="Я подписался", callback_data="ref:check", style=BLUE)],
        ]
    )


def join_again(config: Config) -> InlineKeyboardMarkup:
    text, emoji_id = leading_emoji("⚡ Участвовать снова", config.premium_emoji)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=text,
                    callback_data="join",
                    icon_custom_emoji_id=emoji_id,
                    style=GREEN,
                )
            ]
        ]
    )


def next_battle(config: Config, referrals: bool = True) -> InlineKeyboardMarkup:
    """Что предложить человеку сразу после вылета.

    Момент вылета — самый горячий: обида свежая, реванша хочется прямо
    сейчас. Если в этот момент не дать кнопку, человек просто закроет бота.
    """
    text, emoji_id = leading_emoji("⚡ Записаться в следующий батл", config.premium_emoji)
    rows = [[
        InlineKeyboardButton(
            text=text, callback_data="join", icon_custom_emoji_id=emoji_id, style=GREEN
        )
    ]]
    if referrals:
        rows.append([
            InlineKeyboardButton(
                text="🤝 Позвать друзей — голос в подарок",
                callback_data="buy:invite",
                style=BLUE,
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


QUICK_AMOUNTS = (1, 5, 10)


def buy(price: int, referrals_on: bool, max_votes: int,
        manual_title: str = "", table: dict[str, str] | None = None
        ) -> InlineKeyboardMarkup:
    """Быстрые количества плюс другие способы получить голоса."""
    quick = [
        InlineKeyboardButton(
            text=f"{amount} — {amount * price}⭐",
            callback_data=f"buy:{amount}",
            style=BLUE,
        )
        for amount in QUICK_AMOUNTS
        if amount <= max_votes
    ]
    rows = [quick] if quick else []
    if manual_title:
        rows.append([manual_pay(manual_title, table)])
    if referrals_on:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🤝 Или позвать друзей — бесплатно",
                    callback_data="buy:invite",
                    style=GREEN,
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


# за звёзды берут по одному-два голоса, а переводом — сразу пачку,
# поэтому здесь суммы крупнее
MANUAL_AMOUNTS = (1, 5, 10, 25, 50)


def manual_pay(title: str, table: dict[str, str] | None = None) -> InlineKeyboardButton:
    """Кнопка второго способа оплаты на экране покупки.

    Значок способа — премиум-эмодзи: на кнопке он живёт отдельным полем
    ``icon_custom_emoji_id``, поэтому символ убираем из подписи.
    """
    text, emoji_id = leading_emoji(f"🏦 {title}", table or {})
    return InlineKeyboardButton(
        text=text, callback_data="manual:pick", icon_custom_emoji_id=emoji_id,
        style=BLUE,
    )


def _amount_rows(amounts: list[tuple[int, str]], current: int = 0
                 ) -> list[list[InlineKeyboardButton]]:
    """Кнопки количества по три в ряд: «5 — 7.5 сомони» в два не помещается."""
    picks = [
        InlineKeyboardButton(
            text=f"{'• ' if count == current else ''}{label}",
            callback_data=f"manual:{count}",
            style=GREEN if count == current else None,
        )
        for count, label in amounts
    ]
    return [picks[at:at + 3] for at in range(0, len(picks), 3)]


def manual_pick(amounts: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    """Первый шаг: сколько голосов покупаем. Реквизиты — на следующем экране."""
    return InlineKeyboardMarkup(
        inline_keyboard=_amount_rows(amounts)
        + [[InlineKeyboardButton(text="Отмена", callback_data="buy:cancel")]]
    )


def manual_details(details: str, votes: int) -> InlineKeyboardMarkup:
    """Второй шаг: реквизиты, копирование номера и отправка чека."""
    rows = [[
        InlineKeyboardButton(
            text="◀️ Другое количество", callback_data="manual:pick"
        )
    ]]
    if details:
        rows.append([
            InlineKeyboardButton(
                text="📋 Копировать номер", copy_text=CopyTextButton(text=details)
            )
        ])
    rows += [
        [InlineKeyboardButton(
            text="✅ Я оплатил — отправить чек",
            callback_data=f"manual:receipt:{votes}", style=GREEN,
        )],
        [InlineKeyboardButton(text="Отмена", callback_data="buy:cancel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def manual_wait() -> InlineKeyboardMarkup:
    """Пока ждём чек — единственный выход, чтобы человек не застрял."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="Отмена", callback_data="manual:cancel", style=RED)
        ]]
    )


def topup_decision(topup_id: int) -> InlineKeyboardMarkup:
    """Кнопки админа под чеком."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="✅ Принять", callback_data=f"topup:ok:{topup_id}", style=GREEN
            ),
            InlineKeyboardButton(
                text="❌ Отклонить", callback_data=f"topup:no:{topup_id}", style=RED
            ),
        ]]
    )


def share_card(link: str) -> InlineKeyboardMarkup:
    """Что делать с картинкой: отправить друзьям или скопировать ссылку."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📢 Отправить друзьям", switch_inline_query=link, style=BLUE
        )],
        [InlineKeyboardButton(
            text="📋 Копировать ссылку", copy_text=CopyTextButton(text=link)
        )],
    ])


def pay(votes: int, total: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Оплатить {total}⭐", callback_data=f"buy:{votes}", style=GREEN
                )
            ],
            [InlineKeyboardButton(text="Отмена", callback_data="buy:cancel")],
        ]
    )


def my_match(
    match_id: int, config: Config, post_url: str | None = None, own_channel: bool = True,
    with_card: bool = True,
) -> InlineKeyboardMarkup:
    """Кнопки под сообщением «нашлась пара» и «вы прошли дальше».

    Голая ссылка в тексте выглядит бедно и её неудобно отправлять друзьям,
    поэтому даём кнопки: посмотреть соперника и счёт, скопировать ссылку и
    переслать её в один тап.
    """
    link = links.vote_link(config.bot_username, match_id)
    rows = [
        [
            InlineKeyboardButton(
                text="🗳 Мой соперник и счёт", url=link, style=GREEN
            )
        ],
        [
            InlineKeyboardButton(
                text="📢 Позвать друзей голосовать",
                switch_inline_query=link,
                style=BLUE,
            )
        ],
        [
            InlineKeyboardButton(
                text="📋 Копировать ссылку", copy_text=CopyTextButton(text=link)
            )
        ],
    ]
    if with_card:
        rows.insert(1, [
            InlineKeyboardButton(
                text="🖼 Картинка для сторис",
                callback_data=f"card:{match_id}",
                style=BLUE,
            )
        ])
    if own_channel:
        rows.append(
            [
                InlineKeyboardButton(
                    text="📡 Опубликовать в моём канале",
                    callback_data=f"mych:post:{match_id}",
                )
            ]
        )
    if post_url:
        rows.append([InlineKeyboardButton(text="📄 Пост в канале ↗", url=post_url)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def after_join() -> InlineKeyboardMarkup:
    """Что предложить сразу после принятой заявки.

    Про личный канал человек сам не догадается, поэтому кнопка появляется
    ровно тогда, когда он записался в батл и ему есть что рекламировать.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📡 Публиковать в моём канале",
                    callback_data="mych:open",
                    style=BLUE,
                )
            ]
        ]
    )


# кнопки-ссылки под экраном «Помощь»: подпись, ключ настройки и ряд
HELP_LINKS = (
    ("📣 Основной канал", "link_main_channel", 0),
    ("⚔️ Канал с батлами", "link_battles", 1),
    ("⭐ Выплаты", "link_payouts", 1),
    ("✉️ Связаться", "link_contact", 2),
    ("📄 Правила", "link_rules", 2),
)


def help_links(links: dict[str, str], table: dict[str, str] | None = None) -> InlineKeyboardMarkup:
    """Ряды кнопок-ссылок. Пустая ссылка — кнопки просто нет.

    Ряды собираются из непустых кнопок, поэтому не заданная ссылка не
    оставляет после себя дырку в клавиатуре.
    """
    table = table or {}
    rows: dict[int, list[InlineKeyboardButton]] = {}
    for label, key, row in HELP_LINKS:
        url = (links.get(key) or "").strip()
        if not url:
            continue
        text, emoji_id = leading_emoji(label, table)
        rows.setdefault(row, []).append(
            InlineKeyboardButton(text=text, url=url, icon_custom_emoji_id=emoji_id)
        )

    keyboard = [rows[index] for index in sorted(rows)]
    keyboard.append(
        [InlineKeyboardButton(text="📖 Как это работает", callback_data="help:how", style=BLUE)]
    )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def buy_cooldown(price: int) -> InlineKeyboardMarkup:
    """Выкупить паузу и вернуться в батлы прямо сейчас."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"⚡ Вернуться сейчас — {price}⭐",
                    callback_data="cool:buy",
                    style=GREEN,
                )
            ]
        ]
    )


def buy_rejoin(price: int) -> InlineKeyboardMarkup:
    """Вернуть доступ к батлам после выхода из канала."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🔓 Вернуть доступ — {price}⭐",
                    callback_data="rejoin:buy",
                    style=GREEN,
                )
            ]
        ]
    )


def out_of_votes() -> InlineKeyboardMarkup:
    """Голоса кончились — куда идти дальше."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Купить голоса", callback_data="buy:open", style=GREEN)],
            [InlineKeyboardButton(text="🤝 Позвать друга", callback_data="buy:invite", style=BLUE)],
        ]
    )


def menu_labels() -> set[str]:
    """Все подписи кнопок нижнего меню, в обоих видах.

    Нужны, чтобы режим ввода значения отпускал человека при нажатии кнопки
    меню: это не значение, а желание уйти. Команды ловятся отдельно по «/».
    """
    labels: set[str] = set()
    for label in (BTN_JOIN, BTN_INVITE, BTN_BUY, BTN_CHANNEL, BTN_PROFILE, BTN_HELP):
        labels |= variants(label)
    return labels
