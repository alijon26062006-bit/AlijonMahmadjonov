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
    rows.append([_reply_button(BTN_PROFILE, table), _reply_button(BTN_HELP, table)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def voting(
    match_id: int,
    slots: list[Slot],
    config: Config,
    post_url: str | None,
) -> InlineKeyboardMarkup:
    """Кнопки участников со счётом + служебный ряд."""
    best = max((s.votes for s in slots), default=0)
    crown_id = config.premium_emoji.get(texts.CROWN)
    rows = []
    for index, slot in enumerate(slots, start=1):
        leader = slot.votes == best and slot.votes > 0
        label = texts.vote_button(slot, index)
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


QUICK_AMOUNTS = (1, 5, 10)


def buy(price: int, referrals_on: bool, max_votes: int) -> InlineKeyboardMarkup:
    """Быстрые количества плюс второй способ — позвать друзей."""
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


def my_match(match_id: int, config: Config, post_url: str | None = None) -> InlineKeyboardMarkup:
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
    if post_url:
        rows.append([InlineKeyboardButton(text="📄 Пост в канале ↗", url=post_url)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def menu_labels() -> set[str]:
    """Все подписи кнопок нижнего меню, в обоих видах.

    Нужны, чтобы режим ввода значения отпускал человека при нажатии кнопки
    меню: это не значение, а желание уйти. Команды ловятся отдельно по «/».
    """
    labels: set[str] = set()
    for label in (BTN_JOIN, BTN_INVITE, BTN_BUY, BTN_PROFILE, BTN_HELP):
        labels |= variants(label)
    return labels
