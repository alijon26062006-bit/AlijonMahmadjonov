"""Робот в «Пять в ряд»: достраивает своё и не зевает чужое."""

import random

from duel import five
from duel.five_match import FiveMatch, FiveSide, REASON_LINE
from duel.five_robot import FiveRobot, line_value
from duel.game import STATE_FINISHED, STATE_RUNNING
from duel.robot import ROBOT_ID


def duel(speed="normal", seed=1):
    """Робот против человека, партия уже идёт, ходит робот."""
    m = FiveMatch(
        a=FiveSide(user_id=1, name="Человек"),
        b=FiveSide(user_id=ROBOT_ID, name="Робот", is_bot=True),
        seed=seed,
    )
    m.begin(0.0)
    m.poll(3.5)
    assert m.state == STATE_RUNNING
    m.deadline = 1e9
    m.turn = ROBOT_ID
    m.a.mark, m.b.mark = five.O, five.X
    return m, FiveRobot(speed=speed, seed=seed)


def move_now(m, robot, at=5.0):
    """Прокручиваем время, пока робот не сходит."""
    now = at
    before = m.b.moves
    while m.b.moves == before and now < at + 60:
        now += 0.1
        robot.step(m, now)
    return now


def dumb_human(m, now, rng):
    """Человек, который ставит куда попало рядом со знаками."""
    if not m.my_turn(1):
        return
    spots = five.neighbourhood(m.board, 1) or [(0, 0)]
    spot = rng.choice(spots)
    m.play(1, spot[0], spot[1], now)


def run(m, robot, rng, until=600):
    now = 4.0
    while m.state != STATE_FINISHED and now < until:
        now += 0.1
        m.poll(now)
        robot.step(m, now)
        dumb_human(m, now, rng)
    return now


# ── как считает ─────────────────────────────────────────────────────────────


def test_a_longer_line_is_worth_more():
    board = {}
    alone = line_value(board, (4, 4), five.X)
    board[(4, 3)] = five.X
    pair = line_value(board, (4, 4), five.X)
    board[(4, 2)] = five.X
    three = line_value(board, (4, 4), five.X)
    assert alone < pair < three


def test_a_line_closed_on_both_sides_is_worth_nothing():
    open_line = {(4, c): five.X for c in (1, 2)}
    closed = dict(open_line)
    closed[(4, 0)] = five.O
    closed[(4, 4)] = five.O
    assert line_value(closed, (4, 3), five.X) < line_value(open_line, (4, 3), five.X)


def test_the_winning_cell_is_worth_the_most():
    four = {(4, c): five.X for c in range(4)}
    assert line_value(four, (4, 4), five.X) >= 200000


# ── как ходит ───────────────────────────────────────────────────────────────


def test_the_robot_waits_for_its_turn():
    m, robot = duel()
    m.turn = 1
    for tick in range(300):
        assert robot.step(m, 5.0 + tick * 0.1) is False
    assert m.board == {}


def test_the_robot_thinks_before_it_moves():
    m, robot = duel()
    assert robot.step(m, 5.0) is False
    assert robot.think_at > 5.0
    move_now(m, robot)
    assert m.b.moves == 1


def test_the_robot_finishes_its_own_five():
    m, robot = duel(speed="fast")
    for col in range(4):
        m.board[(4, col)] = five.X          # четыре робота подряд
    move_now(m, robot)
    assert m.state == STATE_FINISHED
    assert m.reason == REASON_LINE and m.winner_id == ROBOT_ID


def test_the_robot_blocks_a_human_four():
    for speed in ("slow", "normal", "fast"):
        m, robot = duel(speed=speed, seed=3)
        for col in range(1, 5):
            m.board[(4, col)] = five.O      # четыре человека подряд
        move_now(m, robot)
        blocked = {(4, 0), (4, 5)}
        assert any(m.board.get(spot) == five.X for spot in blocked), \
            f"робот «{speed}» проглядел чужую четвёрку"


def test_the_robot_prefers_its_own_win_to_a_block():
    """Своя пятёрка кончает партию, чужая четвёрка — ещё нет."""
    m, robot = duel(speed="fast")
    for col in range(4):
        m.board[(0, col)] = five.X
    for col in range(1, 5):
        m.board[(6, col)] = five.O
    move_now(m, robot)
    assert m.winner_id == ROBOT_ID


def test_the_robot_beats_a_careless_player():
    wins = 0
    for seed in range(10):
        m, robot = duel(speed="fast", seed=seed)
        run(m, robot, random.Random(seed))
        wins += m.winner_id == ROBOT_ID
    assert wins >= 8, f"робот выиграл лишь {wins} из 10"


def test_a_slow_robot_gives_a_chance():
    """Слабому сопернику — слабый робот: он думает дольше и придирается меньше."""
    from duel.five_robot import REACH, SLOPPY, THINK
    assert THINK["slow"][0] > THINK["fast"][0]
    assert SLOPPY["slow"] > SLOPPY["fast"] == 0
    assert REACH["slow"] < REACH["fast"]


def test_the_robot_is_not_rated():
    m, robot = duel()
    run(m, robot, random.Random(1))
    assert not m.rated
