"""Математика игры: множители, раскладка мин, проверка хода."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from minesbot.game import (  # noqa: E402
    Board, GameError, check_move, is_cleared, make_mines, multiplier, payout,
)


def test_multiplier_grows_with_every_open():
    values = [multiplier(k, 3) for k in range(0, 10)]
    assert values[0] == 1.0
    assert all(b > a for a, b in zip(values, values[1:])), values


def test_multiplier_bigger_with_more_mines():
    assert multiplier(1, 10) > multiplier(1, 3) > multiplier(1, 1)


def test_multiplier_matches_fair_odds():
    # Без комиссии множитель — ровно обратная вероятность выжить.
    chance = (22 / 25) * (21 / 24) * (20 / 23)   # 3 мины, 3 открытия
    assert multiplier(3, 3, edge=0.0) == pytest.approx(1 / chance, abs=0.01)


def test_house_edge_lowers_payout():
    assert multiplier(5, 3, edge=0.10) < multiplier(5, 3, edge=0.0)


def test_payout_is_whole_coins_and_rounds_down():
    assert payout(101, 1, 3) == int(101 * multiplier(1, 3))
    assert isinstance(payout(100, 2, 3), int)


def test_payout_never_below_bet_at_start():
    assert payout(100, 0, 3) == 100


def test_cannot_open_more_than_safe_cells():
    with pytest.raises(GameError):
        multiplier(23, 3)          # безопасных всего 22


def test_make_mines_count_and_range():
    mines = make_mines(7)
    assert len(mines) == 7 == len(set(mines))
    assert all(0 <= m < 25 for m in mines)


def test_make_mines_rejects_impossible_counts():
    for bad in (0, -1, 25, 100):
        with pytest.raises(GameError):
            make_mines(bad)


def test_check_move_finds_mine_and_blocks_repeat():
    board = Board(mine_cells=(4,), opened=(0,))
    assert check_move(4, board) is True
    assert check_move(1, board) is False
    with pytest.raises(GameError):
        check_move(0, board)       # уже открыта
    with pytest.raises(GameError):
        check_move(99, board)      # такой клетки нет


def test_board_faces_and_reveal():
    board = Board(mine_cells=(4,), opened=(0,))
    assert board.face(0) == "💎"
    assert board.face(4) == "🟦"          # мина скрыта, пока играем
    assert Board((4,), (0,), revealed=True).face(4) == "💣"


def test_rows_are_five_by_five():
    rows = Board((), ()).rows()
    assert len(rows) == 5 and all(len(r) == 5 for r in rows)


def test_is_cleared_when_all_safe_opened():
    opened = tuple(i for i in range(25) if i not in (0, 1, 2))
    assert is_cleared(Board((0, 1, 2), opened))
    assert not is_cleared(Board((0, 1, 2), opened[:-1]))
