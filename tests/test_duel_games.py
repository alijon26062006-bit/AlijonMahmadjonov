"""Реестр игр: по имени собирается нужный матч, сторона и робот."""

from duel import games
from duel.game import Match, Side
from duel.robot import ROBOT_ID, Robot
from duel.sea_match import SeaMatch, SeaSide
from duel.sea_robot import SeaRobot


def test_unknown_game_falls_back_to_the_first_one():
    assert games.normalize("чепуха") == "rope"
    assert games.normalize(None) == "rope"
    assert games.normalize(" SEA ") == "sea"


def test_each_game_builds_its_own_pieces():
    a = games.make_side("sea", user_id=1, name="A")
    b = games.robot_side("sea", "Робот", 1000)
    assert isinstance(a, SeaSide) and isinstance(b, SeaSide) and b.is_bot
    assert b.user_id == ROBOT_ID
    assert isinstance(games.make_match("sea", a, b), SeaMatch)
    assert isinstance(games.make_robot("sea", "normal", 1), SeaRobot)

    a = games.make_side("rope", user_id=1, name="A")
    b = games.make_side("rope", user_id=2, name="B")
    assert type(a) is Side
    assert type(games.make_match("rope", a, b)) is Match
    assert isinstance(games.make_robot("rope", "fast"), Robot)


def test_every_registered_game_is_complete():
    for game_id, info in games.GAMES.items():
        assert info.id == game_id
        assert issubclass(info.match_cls, Match)
        assert issubclass(info.side_cls, Side)
        assert hasattr(info.robot_cls, "step")
        assert info.duration >= 0


def test_the_registry_says_where_the_maths_is():
    """Морской бой — чистая игра по клеткам, сложность там настраивать нечему."""
    assert games.info("rope").math is True
    assert games.info("sea").math is False
