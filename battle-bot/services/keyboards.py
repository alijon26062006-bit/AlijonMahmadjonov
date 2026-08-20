"""Клавиатуры бота."""
from __future__ import annotations

from aiogram.types import (
    CopyTextButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from config import Config, VotePack
from core.models import Slot
from services import links, texts
from services.emoji import leading_emoji

BTN_JOIN = "🚀 Принять участие"
BTN_BUY = "🎁 Купить голоса"
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


def _reply_button(label: str, table: dict[str, str]) -> KeyboardButton:
    """Эмодзи в начале подписи становится премиум-иконкой, если она есть в таблице."""
    text, emoji_id = leading_emoji(label, table)
    return KeyboardButton(text=text, icon_custom_emoji_id=emoji_id)


def main_menu(config: Config) -> ReplyKeyboardMarkup:
    table = config.premium_emoji
    rows = [[_reply_button(BTN_JOIN, table)]]
    if config.paid_votes_enabled:
        rows.append([_reply_button(BTN_BUY, table)])
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
            )
        ]
    )

    service = [InlineKeyboardButton(text="Обновить", callback_data=f"refresh:{match_id}")]
    if post_url:
        service.append(InlineKeyboardButton(text="Пост ↗", url=post_url))
    rows.append(service)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def subscribe(channel_url: str, match_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Подписаться ↗", url=channel_url)],
            [InlineKeyboardButton(text="Я подписался", callback_data=f"refresh:{match_id}")],
        ]
    )


def join_again(config: Config) -> InlineKeyboardMarkup:
    text, emoji_id = leading_emoji("⚡ Участвовать снова", config.premium_emoji)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=text, callback_data="join", icon_custom_emoji_id=emoji_id
                )
            ]
        ]
    )


def vote_packs(packs: list[VotePack]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{pack.votes} голосов — {pack.stars}⭐",
                    callback_data=f"buy:{pack.votes}",
                )
            ]
            for pack in packs
        ]
    )
