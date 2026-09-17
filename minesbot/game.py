"""Математика и правила игры. Ни Телеграма, ни базы — чистые функции.

Именно поэтому этот файл можно полностью покрыть тестами: он не ходит в сеть
и не зависит от состояния бота.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from .config import CELLS, ROW

# Что рисуем на кнопках.
HIDDEN = "🟦"   # закрытая клетка
GEM = "💎"      # открытая безопасная
MINE = "💣"     # мина


class GameError(ValueError):
    """Ход невозможен: клетка занята, индекс не тот и т. п."""


def make_mines(count: int, *, cells: int = CELLS, rng=None) -> tuple[int, ...]:
    """Разложить `count` мин по полю.

    Берём secrets (криптостойкий источник), а не random: расклад нельзя
    предсказать, зная предыдущие игры. rng подменяется в тестах.
    """

    if not 1 <= count <= cells - 1:
        raise GameError(f"Мин должно быть от 1 до {cells - 1}, а просят {count}.")
    pick = rng if rng is not None else secrets.randbelow
    chosen: set[int] = set()
    while len(chosen) < count:
        chosen.add(pick(cells))
    return tuple(sorted(chosen))


def multiplier(opened: int, mines: int, *, cells: int = CELLS, edge: float = 0.03) -> float:
    """Множитель после `opened` удачных открытий.

    Честная (нулевая) математика: шанс открыть подряд `k` безопасных клеток
    равен произведению (safe - i) / (cells - i). Множитель — обратная величина,
    умноженная на (1 - комиссия):

        M(k) = (1 - edge) * Π (cells - i) / (cells - mines - i),  i = 0..k-1

    То есть выплата растёт ровно настолько, насколько падает шанс дожить.
    Округляем ВНИЗ до сотых: округление всегда в пользу кассы, иначе на
    больших ставках копейки утекают.
    """

    if opened < 0:
        raise GameError("Открытых клеток не может быть меньше нуля.")
    safe = cells - mines
    if opened > safe:
        raise GameError(f"Нельзя открыть {opened} клеток: безопасных всего {safe}.")
    if opened == 0:
        return 1.0

    value = 1.0
    for i in range(opened):
        value *= (cells - i) / (safe - i)
    value *= 1.0 - edge
    # Множитель не может быть меньше 1: иначе «выигрыш» отнимал бы деньги.
    value = max(value, 1.0)
    return int(value * 100) / 100


def payout(bet: int, opened: int, mines: int, *, cells: int = CELLS, edge: float = 0.03) -> int:
    """Сколько монет получит игрок, если заберёт прямо сейчас.

    Считаем в целых монетах и округляем вниз — дробных монет в боте нет.
    """

    if bet <= 0:
        raise GameError("Ставка должна быть больше нуля.")
    return int(bet * multiplier(opened, mines, cells=cells, edge=edge))


@dataclass(frozen=True)
class Board:
    """Снимок поля для отрисовки клавиатуры."""

    mine_cells: tuple[int, ...]
    opened: tuple[int, ...]
    revealed: bool = False  # True после проигрыша: показываем, где были мины

    def face(self, index: int) -> str:
        if index in self.opened:
            return MINE if index in self.mine_cells else GEM
        if self.revealed and index in self.mine_cells:
            return MINE
        return HIDDEN

    def rows(self, *, cells: int = CELLS, row: int = ROW) -> list[list[tuple[int, str]]]:
        """Поле строками: [(индекс, символ), ...] — готово для InlineKeyboard."""

        out = []
        for start in range(0, cells, row):
            out.append([(i, self.face(i)) for i in range(start, min(start + row, cells))])
        return out


def check_move(index: int, board: Board, *, cells: int = CELLS) -> bool:
    """Проверить ход и сказать, мина ли там. Бросает GameError на кривой ход.

    Проверка «уже открыта» живёт здесь, а не в обработчике кнопок: два быстрых
    нажатия на одну клетку не должны дважды начислить множитель.
    """

    if not 0 <= index < cells:
        raise GameError(f"Клетки {index} на поле нет.")
    if index in board.opened:
        raise GameError("Эта клетка уже открыта.")
    return index in board.mine_cells


def is_cleared(board: Board, *, cells: int = CELLS) -> bool:
    """Все безопасные клетки открыты — игра выиграна целиком."""

    return len(board.opened) >= cells - len(board.mine_cells)
