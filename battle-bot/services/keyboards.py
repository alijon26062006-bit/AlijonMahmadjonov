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

BTN_JOIN = "🚀 Принять участие"
BTN_BUY = "🎁 Купить голоса"
BTN_PROFILE = "👤 Профиль"
BTN_HELP = "✅ Помощь"


def main_menu(paid_votes: bool) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=BTN_JOIN)]]
    if paid_votes:
        rows.append([KeyboardButton(text=BTN_BUY)])
    rows.append([KeyboardButton(text=BTN_PROFILE), KeyboardButton(text=BTN_HELP)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def voting(
    match_id: int,
    slots: list[Slot],
    config: Config,
    post_url: str | None,
) -> InlineKeyboardMarkup:
    """Кнопки участников со счётом + служебный ряд."""
    best = max((s.votes for s in slots), default=0)
    rows = [
        [
            InlineKeyboardButton(
                text=texts.vote_button(slot, index, leader=slot.votes == best),
                callback_data=f"vote:{match_id}:{slot.user_id}",
            )
        ]
        for index, slot in enumerate(slots, start=1)
    ]

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


def join_again() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚡ Участвовать снова", callback_data="join")]
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
