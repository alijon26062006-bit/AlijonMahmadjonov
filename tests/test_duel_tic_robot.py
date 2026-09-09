"""Робот в крестиках-ноликах: доводит свою тройку и не зевает чужую."""

import random

from duel import tic
from duel.game import STATE_FINISHED, STATE_RUNNING
from duel.robot import ROBOT_ID
from duel.tic_match import TicMatch, TicSide
from duel.tic_robot import TicRobot, wins_with


def duel(speed="normal", seed=1):
    """Робот против человека, партия идёт, ходит робот."""
    m = TicMatch(
        a=TicSide(user_id=1, name="Человек"),
        b=TicSide(user_id=ROBOT_ID, name="Робот", is_bot=True),
        seed=seed,
    )
    m.begin(0.0)
    m.poll(3.5)
    assert m.state == STATE_RUNNING
    m.deadline = 1e9
    m.start_round(3.5, ROBOT_ID)
    return m, TicRobot(speed=speed, seed=seed)


def move_now(m, robot, at=5.0):
    """Прокручиваем время, пока робот не сходит."""
    now, before = at, m.b.moves
    while m.b.moves == before and now < at + 60:
        now += 0.1
        robot.step(m, now)
    return now


def careless_human(m, now, rng):
    """Человек, который ставит куда попало."""
    if not m.my_turn(1) or m.between_rounds:
        return
    spots = tic.free_cells(m.board)
    if spots:
        spot = rng.choice(spots)
        m.play(1, spot[0], spot[1], now)


def run(m, robot, rng, until=600):
    now = 4.0
    while m.state != STATE_FINISHED and now < until:
        now += 0.1
        m.poll(now)
        robot.step(m, now)
        careless_human(m, now, rng)
    return now


# ── как считает ─────────────────────────────────────────────────────────────


def test_a_winning_cell_is_recognised():
    board = {(0, 0): tic.X, (0, 1): tic.X}
    assert wins_with(board, (0, 2), tic.X)
    assert not wins_with(board, (2, 2), tic.X)
    assert board == {(0, 0): tic.X, (0, 1): tic.X}, "проверка поле не портит"


# ── как ходит ───────────────────────────────────────────────────────────────


def test_the_robot_waits_for_its_turn():
    m, robot = duel()
    m.turn = 1
    for tick in range(300):
        assert robot.step(m, 5.0 + tick * 0.1) is False
    assert m.board == {}


def test_the_robot_does_not_move_between_rounds():
    m, robot = duel()
    m.round_over_at = 100.0
    for tick in range(50):
        assert robot.step(m, 5.0 + tick * 0.1) is False


def test_the_robot_thinks_before_it_moves():
    m, robot = duel()
    assert robot.step(m, 5.0) is False
    assert robot.think_at > 5.0
    move_now(m, robot)
    assert m.b.moves == 1


def test_the_robot_finishes_its_own_three():
    m, robot = duel(speed="fast")
    m.board = {(0, 0): m.b.mark, (0, 1): m.b.mark, (2, 2): m.a.mark}
    move_now(m, robot)
    assert m.board.get((0, 2)) == m.b.mark
    assert m.b.rounds_won == 1


def test_the_robot_blocks_a_human_three():
    for speed in ("slow", "normal", "fast"):
        m, robot = duel(speed=speed, seed=4)
        m.board = {(1, 0): m.a.mark, (1, 1): m.a.mark, (0, 0): m.b.mark}
        move_now(m, robot)
        assert m.board.get((1, 2)) == m.b.mark, f"робот «{speed}» проглядел чужую тройку"


def test_the_robot_prefers_its_own_win_to_a_block():
    m, robot = duel(speed="fast")
    m.board = {(0, 0): m.b.mark, (0, 1): m.b.mark,
               (2, 0): m.a.mark, (2, 1): m.a.mark}
    move_now(m, robot)
    assert m.board.get((0, 2)) == m.b.mark, "своя тройка кончает партию раньше"


def test_a_strong_robot_takes_the_middle_first():
    m, robot = duel(speed="fast")
    move_now(m, robot)
    assert m.board.get((1, 1)) == m.b.mark


def test_a_strong_robot_never_loses():
    """Три на три — игра, в которой сильный не проигрывает никогда."""
    for seed in range(12):
        m, robot = duel(speed="fast", seed=seed)
        run(m, robot, random.Random(seed))
        assert m.state == STATE_FINISHED
        assert m.winner_id in (ROBOT_ID, None), f"проиграл на seed={seed}"


def test_a_weak_robot_gives_a_chance():
    from duel.tic_robot import SLOPPY, THINK
    assert THINK["slow"][0] > THINK["fast"][0]
    assert SLOPPY["slow"] > SLOPPY["normal"] > SLOPPY["fast"] == 0


def test_the_robot_is_not_rated():
    m, robot = duel()
    run(m, robot, random.Random(1))
    assert not m.rated
