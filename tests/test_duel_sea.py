"""Морской бой: расстановка и выстрелы.

Расстановку присылает клиент, поэтому её проверке здесь уделено больше всего
внимания: без этого можно поставить весь флот в один угол или вовсе за поле.
"""

import random

import pytest

from duel import sea
from duel.sea import HIT, MISS, REPEAT, SUNK, Board, PlacementError, Ship


def one(size=1, row=0, col=0, horizontal=True):
    return {"row": row, "col": col, "size": size, "horizontal": horizontal}


def fleet(changes=None):
    """Правильная расстановка, в которой можно что-нибудь испортить."""
    layout = [
        one(3, 0, 0), one(2, 2, 0), one(2, 4, 0), one(1, 6, 0), one(1, 6, 3),
    ]
    for index, item in (changes or {}).items():
        layout[index] = item
    return layout


# ── расстановка ─────────────────────────────────────────────────────────────


def test_a_correct_fleet_is_accepted():
    board = sea.build_board(fleet())
    assert [ship.size for ship in board.ships] == [3, 2, 2, 1, 1]
    assert board.total_cells == 9
    assert board.alive == 5


@pytest.mark.parametrize("seed", range(30))
def test_random_placement_is_always_legal(seed):
    layout = sea.random_layout(random.Random(seed))
    board = sea.build_board(layout)
    assert board.total_cells == sum(sea.FLEET)


@pytest.mark.parametrize("seed", range(20))
def test_random_ships_never_touch(seed):
    """Даже углами: иначе расставлять корабли незачем."""
    board = sea.build_board(sea.random_layout(random.Random(seed)))
    for ship in board.ships:
        for other in board.ships:
            if other is ship:
                continue
            assert not (ship.halo() & set(other.cells)), "корабли соприкасаются"


def test_a_ship_hanging_off_the_board_is_refused():
    with pytest.raises(PlacementError, match="за поле"):
        sea.build_board(fleet({0: one(3, 0, sea.SIZE - 1)}))
    with pytest.raises(PlacementError, match="за поле"):
        sea.build_board(fleet({0: one(3, sea.SIZE - 1, 0, horizontal=False)}))


def test_ships_on_top_of_each_other_are_refused():
    with pytest.raises(PlacementError, match="наложились"):
        sea.build_board(fleet({1: one(2, 0, 0)}))


def test_ships_side_by_side_are_refused():
    with pytest.raises(PlacementError, match="касаются"):
        sea.build_board(fleet({1: one(2, 1, 0)}))


def test_ships_touching_only_by_a_corner_are_refused():
    """Угол — тоже касание. На этом обычно и пытаются схитрить."""
    layout = [one(3, 0, 0), one(2, 1, 3), one(2, 4, 0), one(1, 6, 0), one(1, 6, 3)]
    with pytest.raises(PlacementError, match="касаются"):
        sea.build_board(layout)


def test_the_fleet_must_be_exactly_right():
    with pytest.raises(PlacementError, match="кораблей должно быть"):
        sea.build_board(fleet()[:4])
    with pytest.raises(PlacementError, match="флот должен быть"):
        sea.build_board(fleet({3: one(3, 6, 0)}))
    with pytest.raises(PlacementError, match="флот должен быть"):
        sea.build_board(fleet({0: one(1, 0, 0)}))


def test_nonsense_instead_of_a_ship_is_refused():
    with pytest.raises(PlacementError):
        sea.build_board([{"row": "юг"}, one(), one(), one(), one()])
    with pytest.raises(PlacementError):
        sea.build_board("весь флот")


# ── выстрелы ────────────────────────────────────────────────────────────────


def test_a_miss_is_just_a_miss():
    board = sea.build_board(fleet())
    shot = board.fire(3, 6)
    assert shot["result"] == MISS
    assert board.alive == 5


def test_a_hit_wounds_but_does_not_sink():
    board = sea.build_board(fleet())
    assert board.fire(0, 0)["result"] == HIT
    assert board.alive == 5, "трёхпалубный жив"


def test_the_last_hit_sinks_the_ship():
    board = sea.build_board(fleet())
    board.fire(0, 0)
    board.fire(0, 1)
    shot = board.fire(0, 2)
    assert shot["result"] == SUNK
    assert set(shot["ship"]) == {(0, 0), (0, 1), (0, 2)}
    assert board.alive == 4


def test_around_a_sunk_ship_there_is_nothing_left_to_shoot():
    """Рядом с убитым кораблём других быть не может — отмечаем сразу, чтобы
    человек не тратил снаряды на заведомо пустые клетки."""
    board = sea.build_board(fleet())
    for col in range(3):
        shot = board.fire(0, col)
    assert (1, 1) in shot["halo"]
    assert (1, 1) in board.shots
    assert board.fire(1, 1)["result"] == REPEAT


def test_shooting_the_same_cell_twice_changes_nothing():
    board = sea.build_board(fleet())
    board.fire(3, 6)
    assert board.fire(3, 6)["result"] == REPEAT


def test_shooting_outside_the_board_changes_nothing():
    board = sea.build_board(fleet())
    assert board.fire(-1, 0)["result"] == REPEAT
    assert board.fire(0, sea.SIZE)["result"] == REPEAT
    assert not board.shots


def test_the_battle_is_over_when_nothing_is_afloat():
    board = sea.build_board(fleet())
    assert not board.defeated
    for ship in list(board.ships):
        for row, col in ship.cells:
            board.fire(row, col)
    assert board.defeated and board.alive == 0


def test_an_empty_board_is_not_a_defeat():
    assert not Board().defeated


# ── что видит хозяин поля ───────────────────────────────────────────────────


def test_you_see_your_own_field_completely():
    board = sea.build_board(fleet())
    board.fire(0, 0)
    board.fire(3, 6)
    view = board.own_view()
    assert len(view["ships"]) == 5
    assert (0, 0) in view["hits"]
    assert (3, 6) in view["misses"]
    assert view["left"] == 8, "осталось восемь целых клеток из девяти"


def test_a_wounded_ship_is_still_counted_alive():
    board = sea.build_board(fleet())
    board.fire(2, 0)
    assert board.own_view()["alive"] == 5


# ── мелочи, на которых легко ошибиться ──────────────────────────────────────


def test_a_single_cell_ship_sinks_from_one_shot():
    board = sea.build_board(fleet())
    assert board.fire(6, 0)["result"] == SUNK


def test_a_ship_knows_when_it_is_done():
    ship = Ship(cells=((0, 0), (0, 1)))
    assert not ship.sunk
    ship.hits.add((0, 0))
    assert not ship.sunk
    ship.hits.add((0, 1))
    assert ship.sunk


def test_the_halo_stays_on_the_board():
    ship = Ship(cells=((0, 0),))
    assert all(sea.inside(*spot) for spot in ship.halo())
    assert (0, 0) not in ship.halo()
