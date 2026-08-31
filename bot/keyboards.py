"""Инлайн-кнопки под карточкой сохранённой операции."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

EDIT_PREFIX = "edit:"
DELETE_PREFIX = "del:"


def transaction_keyboard(tx_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="✏️ Исправить", callback_data=f"{EDIT_PREFIX}{tx_id}"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"{DELETE_PREFIX}{tx_id}"),
        ]]
    )
