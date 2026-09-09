"""Пять в ряд — правила поля. Ни сети, ни базы, поэтому проверяется тестами.

Поле 9×9: на телефоне клетка выходит крупной, в неё легко попасть пальцем,
а партия укладывается в несколько минут. Выигрывает тот, кто первым выстроит
пять своих знаков подряд — по строке, по столбцу или по диагонали.
"""

from __future__ import annotations

SIZE = 9
WIN = 5

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
    """Линия, которой выигран матч, или пусто, если её ещё нет."""

    line = run_through(board, row, col)
    return line if len(line) >= WIN else []


def longest(board: Board, mark: str) -> int:
    """Самая длинная линия этого знака на поле — для итогов матча."""

    best = 0
    for (row, col), value in board.items():
        if value != mark:
            continue
        best = max(best, len(run_through(board, row, col)))
    return best


def full(board: Board) -> bool:
    return len(board) >= SIZE * SIZE


def neighbourhood(board: Board, reach: int = 2) -> list[Cell]:
    """Пустые клетки рядом с уже занятыми.

    Смотреть всё поле роботу незачем: ход в пустом углу не значит ничего,
    игра всегда идёт вокруг поставленных знаков.
    """

    if not board:
        middle = SIZE // 2
        return [(middle, middle)]
    spots = set()
    for (row, col) in board:
        for dr in range(-reach, reach + 1):
            for dc in range(-reach, reach + 1):
                spot = (row + dr, col + dc)
                if inside(*spot) and spot not in board:
                    spots.add(spot)
    return sorted(spots)
