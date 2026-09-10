"""Клавиатуры. Главное меню — обычные кнопки внизу экрана, всё
остальное — инлайн-кнопки под сообщением."""
from __future__ import annotations

from decimal import Decimal

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from texts import LANGS, t


def main_menu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "menu_buy")),
             KeyboardButton(text=t(lang, "menu_balance"))],
            [KeyboardButton(text=t(lang, "menu_orders")),
             KeyboardButton(text=t(lang, "menu_lang"))],
            [KeyboardButton(text=t(lang, "menu_support"))],
        ],
        resize_keyboard=True,
    )


def langs_kb() -> InlineKeyboardMarkup:
    rows, row = [], []
    for code, title in LANGS.items():
        row.append(InlineKeyboardButton(text=title, callback_data=f"lang:{code}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def games_kb(games: list[dict]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=g["label"], callback_data=f"g:{g['id']}")]
            for g in games]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _money(v) -> str:
    d = Decimal(v or 0)
    return f"{d:.0f}" if d == d.to_integral_value() else f"{d:.2f}"


def packs_kb(packs: list[dict], lang: str, cur: str) -> InlineKeyboardMarkup:
    rows = []
    for p in packs:
        tag = f" {p['tag']}" if p.get("tag") else ""
        rows.append([InlineKeyboardButton(
            text=f"{p['label']} — {_money(p['price'])} {cur}{tag}",
            callback_data=f"p:{p['id']}")])
    rows.append([InlineKeyboardButton(text=t(lang, "back"), callback_data="buy")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "confirm_yes"), callback_data="ok"),
        InlineKeyboardButton(text=t(lang, "confirm_no"), callback_data="no"),
    ]])


def topup_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "topup_btn"), callback_data="topup")
    ]])


def admin_order_kb(oid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Выполнен", callback_data=f"ao:done:{oid}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"ao:rej:{oid}"),
    ]])


def admin_topup_kb(tid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Зачислить", callback_data=f"at:ok:{tid}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"at:rej:{tid}"),
    ]])
