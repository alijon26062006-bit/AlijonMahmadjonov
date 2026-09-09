"""Поле «Пять в ряд»: линии, победа, ничья."""

from duel import five


def board(*cells):
    """board((0, 0, 'x'), (0, 1, 'o')) — короткая запись поля для теста."""
    return {(row, col): mark for row, col, mark in cells}


def line(row, col, dr, dc, count, mark=five.X):
    return board(*[(row + dr * i, col + dc * i, mark) for i in range(count)])


# ── клетки ──────────────────────────────────────────────────────────────────


def test_the_field_is_nine_by_nine():
    assert five.SIZE == 9 and five.WIN == 5
    assert five.inside(0, 0) and five.inside(8, 8)
    assert not five.inside(-1, 0) and not five.inside(9, 0) and not five.inside(0, 9)


def test_a_taken_cell_is_not_free():
    b = board((3, 3, five.X))
    assert not five.free(b, 3, 3)
    assert five.free(b, 3, 4)
    assert not five.free(b, 9, 9), "за краем поля свободных клеток нет"


# ── линии ───────────────────────────────────────────────────────────────────


def test_four_in_a_row_is_not_a_win_yet():
    b = line(2, 1, 0, 1, 4)
    assert len(five.run_through(b, 2, 1)) == 4
    assert five.winning_line(b, 2, 1) == []


def test_five_across_wins():
    b = line(2, 1, 0, 1, 5)
    assert five.winning_line(b, 2, 3) == sorted(b)


def test_five_down_wins():
    b = line(1, 4, 1, 0, 5)
    assert len(five.winning_line(b, 3, 4)) == 5


def test_both_diagonals_win():
    down = line(0, 0, 1, 1, 5)
    up = line(8, 0, -1, 1, 5)
    assert len(five.winning_line(down, 2, 2)) == 5
    assert len(five.winning_line(up, 6, 2)) == 5


def test_a_row_of_six_counts_too():
    """Шестёрка — это та же победа, и перечеркнуть надо её целиком."""
    b = line(4, 1, 0, 1, 6)
    assert len(five.winning_line(b, 4, 3)) == 6


def test_somebody_else_s_mark_breaks_the_line():
    b = line(2, 0, 0, 1, 5)
    b[(2, 2)] = five.O
    assert five.winning_line(b, 2, 0) == []
    assert five.winning_line(b, 2, 4) == []


def test_the_line_is_counted_from_both_sides():
    b = line(4, 2, 0, 1, 5)
    # ставим в середину — линия должна найтись и влево, и вправо
    assert len(five.run_through(b, 4, 4)) == 5


def test_the_longest_line_is_reported_for_the_result():
    b = line(0, 0, 0, 1, 3)
    b.update(line(5, 0, 1, 0, 4))
    b[(8, 8)] = five.O
    assert five.longest(b, five.X) == 4
    assert five.longest(b, five.O) == 1
    assert five.longest(b, five.X) >= five.longest(b, five.O)


# ── поле целиком ────────────────────────────────────────────────────────────


def test_the_field_ends_when_the_cells_do():
    b = {(r, c): five.X for r in range(five.SIZE) for c in range(five.SIZE)}
    assert five.full(b)
    del b[(4, 4)]
    assert not five.full(b)


def test_the_first_move_of_the_game_goes_to_the_middle():
    assert five.neighbourhood({}) == [(4, 4)]


def test_the_robot_only_looks_next_to_the_marks():
    """Ход в пустом углу ничего не значит — смотреть туда незачем."""
    spots = five.neighbourhood(board((4, 4, five.X)), reach=1)
    assert (3, 3) in spots and (4, 5) in spots
    assert (4, 4) not in spots, "занятую клетку не предлагаем"
    assert (0, 0) not in spots and len(spots) == 8
