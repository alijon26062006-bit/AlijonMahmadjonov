from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup,
)

from bot.models import Category, DeliveryType, Faq
from bot.texts import t


def main_menu(lang: str = "ru") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("btn_calc", lang))],
            [KeyboardButton(text=t("btn_track", lang)),
             KeyboardButton(text=t("btn_order", lang))],
            [KeyboardButton(text=t("btn_tariffs", lang)),
             KeyboardButton(text=t("btn_warehouses", lang))],
            [KeyboardButton(text=t("btn_contacts", lang)),
             KeyboardButton(text=t("btn_faq", lang))],
        ],
        resize_keyboard=True,
    )


def cancel_kb(lang: str = "ru") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t("btn_cancel", lang))]],
        resize_keyboard=True,
    )


def delivery_types_kb(items: list[DeliveryType]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=str(dt), callback_data=f"calc:dt:{dt.id}")]
            for dt in items]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def categories_kb(items: list[Category]) -> InlineKeyboardMarkup:
    rows, row = [], []
    for c in items:
        row.append(InlineKeyboardButton(text=c.name, callback_data=f"calc:cat:{c.id}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def after_calc_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_make_order", lang), callback_data="order:start")],
    ])


def faq_kb(items: list[Faq]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f.question, callback_data=f"faq:{f.id}")]
            for f in items]
    return InlineKeyboardMarkup(inline_keyboard=rows)
