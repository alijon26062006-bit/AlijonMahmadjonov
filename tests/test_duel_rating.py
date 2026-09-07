"""Рейтинг: победа над сильным дороже, ничья между равными ничего не меняет."""

import pytest

from duel import rating


def test_win_raises_and_loss_lowers():
    new_a, new_b = rating.both(1000, 1000, "a")
    assert new_a > 1000 > new_b


def test_a_draw_between_equals_changes_nothing():
    assert rating.both(1200, 1200, "draw") == (1200, 1200)


def test_beating_a_stronger_player_pays_more():
    weak_win = rating.both(1000, 1600, "a")[0] - 1000
    equal_win = rating.both(1000, 1000, "a")[0] - 1000
    assert weak_win > equal_win


def test_losing_to_a_stronger_player_costs_little():
    heavy = 1000 - rating.both(1000, 1000, "b")[0]
    light = 1000 - rating.both(1000, 1600, "b")[0]
    assert light < heavy


def test_points_move_between_the_two_players():
    """Сколько один получил, столько другой примерно и потерял."""
    new_a, new_b = rating.both(1100, 1300, "a", games_a=50, games_b=50)
    assert abs((new_a - 1100) + (new_b - 1300)) <= 1


def test_a_beginner_moves_faster_than_a_veteran():
    beginner = rating.both(1000, 1000, "a", games_a=0)[0] - 1000
    veteran = rating.both(1000, 1000, "a", games_a=200)[0] - 1000
    assert beginner > veteran


def test_rating_never_falls_below_the_floor():
    value = rating.MIN_RATING
    for _ in range(50):
        value = rating.update(value, 2000, 0.0)
    assert value >= rating.MIN_RATING


def test_expected_score_is_symmetric():
    assert rating.expected(1200, 1200) == pytest.approx(0.5)
    assert rating.expected(1400, 1000) + rating.expected(1000, 1400) == pytest.approx(1.0)


def test_titles_grow_with_rating():
    assert rating.title(700) == "новичок"
    assert rating.title(1000) == "счетовод"
    assert rating.title(2000) == "легенда"
