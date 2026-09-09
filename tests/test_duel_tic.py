"""Поле крестиков-ноликов: линии, победа, ничья."""

from duel import tic


def board(*cells):
    """board((0, 0, 'x'), (0, 1, 'o')) — короткая запись поля для теста."""
    return {(row, col): mark for row, col, mark in cells}


def line(row, col, dr, dc, count, mark=tic.X):
    return board(*[(row + dr * i, col + dc * i, mark) for i in range(count)])


# ── клетки ──────────────────────────────────────────────────────────────────


def test_the_field_is_three_by_three():
    assert tic.SIZE == 3 and tic.WIN == 3
    assert tic.inside(0, 0) and tic.inside(2, 2)
    assert not tic.inside(-1, 0) and not tic.inside(3, 0) and not tic.inside(0, 3)


def test_a_taken_cell_is_not_free():
    b = board((1, 1, tic.X))
    assert not tic.free(b, 1, 1)
    assert tic.free(b, 0, 0)
    assert not tic.free(b, 3, 3), "за краем поля свободных клеток нет"


def test_free_cells_are_listed_for_the_robot():
    b = board((1, 1, tic.X), (0, 0, tic.O))
    spots = tic.free_cells(b)
    assert len(spots) == 7
    assert (1, 1) not in spots and (0, 0) not in spots and (2, 2) in spots


# ── линии ───────────────────────────────────────────────────────────────────


def test_two_in_a_row_is_not_a_win_yet():
    b = line(1, 0, 0, 1, 2)
    assert len(tic.run_through(b, 1, 0)) == 2
    assert tic.winning_line(b, 1, 0) == []


def test_three_across_wins():
    b = line(1, 0, 0, 1, 3)
    assert tic.winning_line(b, 1, 1) == sorted(b)


def test_three_down_wins():
    b = line(0, 2, 1, 0, 3)
    assert len(tic.winning_line(b, 1, 2)) == 3


def test_both_diagonals_win():
    down = line(0, 0, 1, 1, 3)
    up = line(2, 0, -1, 1, 3)
    assert len(tic.winning_line(down, 1, 1)) == 3
    assert len(tic.winning_line(up, 1, 1)) == 3


def test_somebody_else_s_mark_breaks_the_line():
    b = line(0, 0, 0, 1, 3)
    b[(0, 1)] = tic.O
    assert tic.winning_line(b, 0, 0) == []
    assert tic.winning_line(b, 0, 2) == []


def test_the_winner_of_the_whole_field_is_found():
    b = line(2, 0, 0, 1, 3)
    b[(0, 0)] = tic.O
    mark, cells = tic.winner(b)
    assert mark == tic.X and len(cells) == 3


def test_nobody_wins_an_empty_field():
    assert tic.winner({}) == ("", [])


# ── поле целиком ────────────────────────────────────────────────────────────


def test_the_field_ends_when_the_cells_do():
    b = {(r, c): tic.X for r in range(tic.SIZE) for c in range(tic.SIZE)}
    assert tic.full(b)
    del b[(1, 1)]
    assert not tic.full(b)
