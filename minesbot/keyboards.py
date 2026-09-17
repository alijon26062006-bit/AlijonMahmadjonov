"""Сборка инлайн-клавиатуры поля."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from . import texts
from .config import CELLS, ROW
from .game import Board, multiplier, payout

# Формат callback_data: mn:<действие>:<game_id>:<клетка>
# game_id обязателен: без него кнопки старого сообщения продолжали бы
# управлять новой игрой (в исходном коде было именно так).
PREFIX = "mn"
NOOP = f"{PREFIX}:x:0:0"


def field(game_id: str, board: Board, bet: int, mines: int, *, edge: float = 0.03,
          cells: int = CELLS, row: int = ROW, dead: bool = False) -> InlineKeyboardMarkup:
    rows = []
    for line in board.rows(cells=cells, row=row):
        rows.append([
            InlineKeyboardButton(
                face,
                # Уже открытые клетки (и всё поле после взрыва) ведут в
                # «пустышку»: повторное нажатие не долетает до логики игры.
                callback_data=NOOP if dead or index in board.opened
                else f"{PREFIX}:o:{game_id}:{index}",
            )
            for index, face in line
        ])

    if dead:
        return InlineKeyboardMarkup(rows)

    opened = len(board.opened)
    if opened:
        prize = payout(bet, opened, mines, cells=cells, edge=edge)
        label = texts.BUTTON_TAKE.format(payout=texts.money(prize))
    else:
        label = texts.BUTTON_TAKE_EMPTY
    rows.append([InlineKeyboardButton(label, callback_data=f"{PREFIX}:take:{game_id}:0")])
    return InlineKeyboardMarkup(rows)


def caption(bet: int, mines: int, opened: int, *, edge: float = 0.03, cells: int = CELLS) -> str:
    return texts.GAME.format(
        mines=mines,
        bet=texts.money(bet),
        multiplier=f"{multiplier(opened, mines, cells=cells, edge=edge):.2f}",
        payout=texts.money(payout(bet, opened, mines, cells=cells, edge=edge) if opened else 0),
    )
