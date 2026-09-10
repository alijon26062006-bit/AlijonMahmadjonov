"""Кнопки. Всё управление — пальцем, команды помнить не нужно."""

from __future__ import annotations

from typing import Iterable, Sequence

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

BTN_ADD_WORKER = "➕ Человек"
BTN_LIST = "📋 Список"
BTN_REPORT = "📊 Отчёт"
BTN_NEW_SESSION = "🔄 Новая смена"
BTN_UNDO = "↩️ Отменить"
BTN_HELP = "❓ Помощь"
BTN_WORKERS = "👥 Люди"

SERVICE_BUTTONS = frozenset(
    {BTN_ADD_WORKER, BTN_LIST, BTN_REPORT, BTN_NEW_SESSION, BTN_UNDO, BTN_HELP, BTN_WORKERS}
)

ACTIVE_MARK = "✅ "
IDLE_MARK = "👤 "


def worker_button_name(text: str) -> str | None:
    """«👤 Азиз» → «Азиз». Не кнопка человека — None."""
    for mark in (ACTIVE_MARK, IDLE_MARK):
        if text.startswith(mark):
            return text[len(mark):].strip()
    return None


def main_keyboard(workers: Sequence, active_id: int | None) -> ReplyKeyboardMarkup:
    rows: list[list[KeyboardButton]] = []
    line: list[KeyboardButton] = []
    for worker in workers:
        mark = ACTIVE_MARK if worker["id"] == active_id else IDLE_MARK
        line.append(KeyboardButton(text=mark + worker["name"]))
        if len(line) == 2:
            rows.append(line)
            line = []
    if line:
        rows.append(line)

    rows.append([KeyboardButton(text=BTN_ADD_WORKER), KeyboardButton(text=BTN_LIST)])
    rows.append([KeyboardButton(text=BTN_REPORT), KeyboardButton(text=BTN_WORKERS)])
    rows.append([KeyboardButton(text=BTN_UNDO), KeyboardButton(text=BTN_HELP)])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        input_field_placeholder="Скажи число голосом или напиши цифрами",
    )


def entry_keyboard(entry_id: int, deleted: bool = False) -> InlineKeyboardMarkup:
    if deleted:
        buttons = [[InlineKeyboardButton(text="↩️ Вернуть", callback_data=f"e:res:{entry_id}")]]
    else:
        buttons = [[
            InlineKeyboardButton(text="✏️ Исправить", callback_data=f"e:edit:{entry_id}"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"e:del:{entry_id}"),
        ]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def choose_worker_keyboard(workers: Iterable, index: str) -> InlineKeyboardMarkup:
    """Кому записать число: index — какое из распознанных чисел брать."""
    rows: list[list[InlineKeyboardButton]] = []
    line: list[InlineKeyboardButton] = []
    for worker in workers:
        line.append(
            InlineKeyboardButton(
                text=worker["name"], callback_data=f"add:{worker['id']}:{index}"
            )
        )
        if len(line) == 2:
            rows.append(line)
            line = []
    if line:
        rows.append(line)
    rows.append([InlineKeyboardButton(text="✖️ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def choose_number_keyboard(labels: Sequence[str], worker_id: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"add:{worker_id}:{index}")]
        for index, label in enumerate(labels)
    ]
    if len(labels) > 1:
        rows.append(
            [InlineKeyboardButton(text="➕ Записать все", callback_data=f"add:{worker_id}:all")]
        )
    rows.append([InlineKeyboardButton(text="✖️ Ничего не писать", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_keyboard(worker_id: int, value: int, label: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ Да, {label}", callback_data=f"force:{worker_id}:{value}")],
        [InlineKeyboardButton(text="✖️ Нет, не писать", callback_data="cancel")],
    ])


def report_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📗 Excel — смена", callback_data="rep:now:xlsx"),
         InlineKeyboardButton(text="📕 PDF — смена", callback_data="rep:now:pdf")],
        [InlineKeyboardButton(text="📗 Excel — всё время", callback_data="rep:all:xlsx"),
         InlineKeyboardButton(text="📕 PDF — всё время", callback_data="rep:all:pdf")],
        [InlineKeyboardButton(text="📦 Оба файла за смену", callback_data="rep:now:both")],
        [InlineKeyboardButton(text="✖️ Закрыть", callback_data="cancel")],
    ])


def workers_keyboard(workers: Iterable) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"👤 {worker['name']}", callback_data=f"w:menu:{worker['id']}")]
        for worker in workers
    ]
    rows.append([InlineKeyboardButton(text="➕ Добавить человека", callback_data="w:add")])
    rows.append([InlineKeyboardButton(text="🔄 Новая смена", callback_data="s:new")])
    rows.append([InlineKeyboardButton(text="✖️ Закрыть", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def worker_menu_keyboard(worker_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📍 Сделать текущим", callback_data=f"w:set:{worker_id}")],
        [InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"w:ren:{worker_id}")],
        [InlineKeyboardButton(text="🚪 Убрать из списка", callback_data=f"w:arch:{worker_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="w:list")],
    ])


def confirm_new_session_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, начать новую смену", callback_data="s:new:yes")],
        [InlineKeyboardButton(text="✖️ Нет", callback_data="cancel")],
    ])


def manual_input_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Напишу цифрами", callback_data="manual")]
    ])
