"""Робот в морском бою: ходит по очереди и стреляет с умом."""

import random

from duel import sea
from duel.robot import ROBOT_ID
from duel.sea_match import STATE_FINISHED, STATE_RUNNING, SeaMatch, SeaSide
from duel.sea_robot import SeaRobot


def duel(speed="normal", seed=1):
    """Робот против человека, оба расставлены, бой уже идёт."""
    m = SeaMatch(
        a=SeaSide(user_id=1, name="Человек"),
        b=SeaSide(user_id=ROBOT_ID, name="Робот", is_bot=True),
        seed=seed,
    )
    m.begin(0.0)
    m.place(1, sea.random_layout(random.Random(100 + seed)))
    m.poll(1.0)
    m.poll(1.0 + 3.1)
    assert m.state == STATE_RUNNING
    # Потолок боя тестам мешает: считаем выстрелы, а не время.
    m.deadline = 1e9
    return m, SeaRobot(speed=speed, seed=seed)


def polite_human(m, now):
    """Человек, который в свой ход всегда мажет: отдаёт ход роботу и не
    мешает считать, за сколько выстрелов робот топит флот."""

    if not m.my_turn(1):
        return
    board = m.opponent(1).board
    ships = {cell for ship in board.ships for cell in ship.cells}
    free = [
        (r, c)
        for r in range(sea.SIZE)
        for c in range(sea.SIZE)
        if (r, c) not in ships and (r, c) not in board.shots
    ]
    if free:
        m.fire(1, *free[0], now)


def run(m, robot, until, human=polite_human, step=0.1):
    now = 4.1
    while now < until and m.state != STATE_FINISHED:
        now += step
        m.poll(now)
        robot.step(m, now)
        if human is not None:
            human(m, now)
    return now


def test_the_robot_places_its_fleet_before_the_battle():
    m, _ = duel()
    assert m.b.placed and m.b.board.total_cells == sum(sea.FLEET)


def test_the_robot_waits_for_its_turn():
    m, robot = duel()
    m.turn = 1
    for tick in range(200):
        assert robot.step(m, 5.0 + tick * 0.1) is False
    assert m.a.board.shots == set(), "в чужой ход робот не стреляет"


def test_the_robot_aims_before_it_shoots():
    """Мгновенный выстрел выглядит как автомат, а не как соперник."""
    m, robot = duel()
    m.turn = ROBOT_ID
    assert robot.step(m, 5.0) is False
    assert robot.fire_at > 5.0
    while not m.b.shots_fired:
        robot.step(m, robot.fire_at)
    assert m.b.shots_fired == 1


def test_the_robot_shoots_again_after_a_hit():
    m, robot = duel(speed="fast")
    m.turn = ROBOT_ID
    robot.targets = [m.a.board.ships[0].cells[0]]
    now = 5.0
    while not m.b.shots_fired:
        now += 0.1
        robot.step(m, now)
    assert m.b.hits_made == 1
    assert m.turn == ROBOT_ID, "попал — ходит снова"


def test_the_robot_sinks_the_human_fleet():
    m, robot = duel()
    run(m, robot, until=900)
    assert m.state == STATE_FINISHED
    assert m.winner_id == ROBOT_ID


def test_the_robot_hunts_rather_than_guesses():
    """Случайный перебор тратит около сорока выстрелов на девять клеток.
    Робот, который добивает вокруг попадания, должен укладываться заметно быстрее."""
    total = 0
    for seed in range(8):
        m, robot = duel(seed=seed)
        run(m, robot, until=900)
        total += m.b.shots_fired
    assert total / 8 < 34


def test_a_slow_robot_is_easier_than_a_fast_one():
    """Слабому сопернику — слабый робот: он и целится дольше, и мажет чаще."""
    shots = {}
    for speed in ("slow", "fast"):
        spent = 0
        for seed in range(8):
            m, robot = duel(speed=speed, seed=seed)
            run(m, robot, until=3000)
            assert m.state == STATE_FINISHED, "флот всё-таки потоплен"
            spent += m.b.shots_fired
        shots[speed] = spent
    assert shots["slow"] > shots["fast"]


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
    m, robot = duel(speed="fast", seed=5)
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
    run(m, robot, until=900)
    assert not m.rated
