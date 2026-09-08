"""Робот в морском бою: считает как в канате, стреляет с умом."""

import random

from duel import sea
from duel.robot import ROBOT_ID
from duel.sea_match import STATE_FINISHED, SeaMatch, SeaSide
from duel.sea_robot import SeaRobot


def duel(speed="normal", seed=1):
    m = SeaMatch(
        a=SeaSide(user_id=1, name="Человек"),
        b=SeaSide(user_id=ROBOT_ID, name="Робот", is_bot=True),
        seed=seed,
    )
    m.begin(0.0)
    m.place(1, sea.random_layout(random.Random(100 + seed)))
    return m, SeaRobot(speed=speed, seed=seed)


def run(m, robot, until, step=0.1):
    now = 0.0
    while now < until and m.state != STATE_FINISHED:
        now += step
        m.poll(now)
        robot.step(m, now)
    return now


def test_the_robot_places_its_fleet_before_the_battle():
    m, _ = duel()
    assert m.b.placed and m.b.board.total_cells == sum(sea.FLEET)


def test_the_robot_earns_shells_and_spends_them():
    m, robot = duel()
    run(m, robot, until=30)
    assert m.b.score > 0, "решает примеры"
    assert m.b.shots_fired > 0, "и стреляет"


def test_the_robot_sinks_a_silent_human():
    m, robot = duel()
    run(m, robot, until=600)
    assert m.state == STATE_FINISHED
    assert m.winner_id == ROBOT_ID


def test_the_robot_hunts_rather_than_guesses():
    """Случайный перебор тратит около сорока выстрелов на девять клеток.
    Робот, который добивает вокруг попадания, должен укладываться заметно быстрее."""
    total = 0
    for seed in range(8):
        m, robot = duel(seed=seed)
        run(m, robot, until=600)
        total += m.b.shots_fired
    assert total / 8 < 34


def test_after_a_hit_the_robot_shoots_next_door():
    m, robot = duel(seed=3)
    human_board = m.a.board
    target = human_board.ships[0].cells[0]
    # подсовываем роботу попадание и смотрим, куда он соберётся дальше
    shot = human_board.fire(*target)
    robot.learn(shot, human_board)
    if shot["result"] == "hit":
        assert robot.targets
        assert all(abs(t[0] - target[0]) + abs(t[1] - target[1]) == 1 for t in robot.targets)


def test_after_a_sunk_ship_the_robot_starts_over():
    m, robot = duel(seed=4)
    robot.targets = [(0, 0)]
    robot.wounded = [(1, 1)]
    robot.learn({"result": "sunk", "cell": (1, 2), "ship": [(1, 1), (1, 2)], "halo": []},
                m.a.board)
    assert not robot.targets and not robot.wounded


def test_the_robot_never_wastes_a_shot_on_a_known_cell():
    m, robot = duel(seed=5)
    board = m.a.board
    for row in range(sea.SIZE):
        for col in range(sea.SIZE):
            if (row, col) != (6, 6):
                board.shots.add((row, col))
    assert robot.choose(board) == (6, 6)
    board.shots.add((6, 6))
    assert robot.choose(board) is None


def test_the_robot_is_not_rated():
    m, robot = duel()
    run(m, robot, until=600)
    assert not m.rated
