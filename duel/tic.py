"""Крестики-нолики — правила поля. Ни сети, ни базы, поэтому проверяется тестами.

Поле три на три, три своих подряд — партия взята. Всё как в тетради, только
клетки крупные: на телефоне в них попадаешь не глядя.
"""

from __future__ import annotations

SIZE = 3
WIN = 3

X = "x"
O = "o"
MARKS = (X, O)

# Четыре направления: вправо, вниз и две диагонали. Обратные считать незачем —
# линию мы всё равно смотрим в обе стороны от поставленного знака.
LINES = ((0, 1), (1, 0), (1, 1), (1, -1))

Cell = tuple[int, int]
Board = dict[Cell, str]


def inside(row: int, col: int) -> bool:
    return 0 <= row < SIZE and 0 <= col < SIZE


def free(board: Board, row: int, col: int) -> bool:
    return inside(row, col) and (row, col) not in board


def free_cells(board: Board) -> list[Cell]:
    return [
        (row, col)
        for row in range(SIZE)
        for col in range(SIZE)
        if (row, col) not in board
    ]


def run_through(board: Board, row: int, col: int) -> list[Cell]:
    """Самая длинная линия своего знака через эту клетку.

    Возвращает саму линию целиком: клиенту она нужна, чтобы перечеркнуть
    выигрышные знаки, как это делают на бумаге.
    """

    mark = board.get((row, col))
    if not mark:
        return []
    best: list[Cell] = []
    for dr, dc in LINES:
        line = [(row, col)]
        for step in (1, -1):
            r, c = row + dr * step, col + dc * step
            while board.get((r, c)) == mark:
                line.append((r, c))
                r, c = r + dr * step, c + dc * step
        if len(line) > len(best):
            best = sorted(line)
    return best


def winning_line(board: Board, row: int, col: int) -> list[Cell]:
    """Линия, которой взята партия, или пусто, если её ещё нет."""

    line = run_through(board, row, col)
    return line if len(line) >= WIN else []


def winner(board: Board) -> tuple[str, list[Cell]]:
    """Чей знак выиграл и какой линией. Пустая строка — ещё никто."""

    for (row, col) in board:
        line = winning_line(board, row, col)
        if line:
            return board[(row, col)], line
    return "", []


def full(board: Board) -> bool:
    return len(board) >= SIZE * SIZE
