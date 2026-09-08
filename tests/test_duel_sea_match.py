"""Морской бой как матч: расстановка, снаряды, выстрелы, победа."""

import random

import pytest

from duel import sea
from duel.game import (
    DISCONNECT_GRACE,
    FREEZE_SEC,
    REASON_ABANDONED,
    REASON_LEFT,
    REASON_TIME,
    STATE_COUNTDOWN,
    STATE_FINISHED,
    STATE_RUNNING,
)
from duel.sea_match import (
    BATTLE_CAP_SEC,
    MAX_SHELLS,
    PLACE_SEC,
    REASON_FLEET,
    STATE_PLACING,
    SeaMatch,
    SeaSide,
)


def match(seed=1, duration=0):
    m = SeaMatch(
        a=SeaSide(user_id=1, name="Первый"),
        b=SeaSide(user_id=2, name="Второй"),
        duration=duration,
        level="normal",
        seed=seed,
    )
    m.begin(0.0)
    return m


def placed(seed=1, duration=0):
    """Оба расставились, отсчёт прошёл — можно стрелять."""
    m = match(seed, duration)
    m.place(1, sea.random_layout(random.Random(10 + seed)))
    m.place(2, sea.random_layout(random.Random(20 + seed)))
    m.poll(1.0)
    m.poll(1.0 + 3.1)
    assert m.state == STATE_RUNNING
    return m


def answer(m, user_id, now, correct=True):
    side = m.side(user_id)
    value = side.task.answer + (0 if correct else 7)
    return m.submit(user_id, side.task.id, value, now)


def enemy_cells(m, user_id):
    """Где на самом деле стоят корабли соперника — тесту знать можно."""
    opp = m.opponent(user_id)
    return [spot for ship in opp.board.ships for spot in ship.cells]


# ── расстановка ─────────────────────────────────────────────────────────────


def test_a_new_match_starts_with_placement_not_a_countdown():
    m = match()
    assert m.state == STATE_PLACING
    assert m.a.task is None, "примеров до боя нет"


def test_placement_is_checked_by_the_server():
    m = match()
    assert m.place(1, []) == "кораблей должно быть 5"
    assert not m.a.placed
    assert m.place(1, sea.random_layout()) == ""
    assert m.a.placed


def test_the_countdown_waits_for_both():
    m = match()
    m.place(1, sea.random_layout())
    assert not m.poll(1.0)
    assert m.state == STATE_PLACING
    m.place(2, sea.random_layout())
    assert m.poll(2.0)
    assert m.state == STATE_COUNTDOWN


def test_the_slow_one_gets_a_random_fleet():
    """Минута прошла — ждать дальше нечестно по отношению к сопернику."""
    m = match()
    m.place(1, sea.random_layout())
    m.poll(PLACE_SEC + 0.1)
    assert m.b.placed and m.b.board is not None
    assert m.state == STATE_COUNTDOWN


def test_you_cannot_place_once_the_battle_is_on():
    m = placed()
    assert m.place(1, sea.random_layout()) == "not_placing"


def test_the_robot_places_itself_at_once():
    m = SeaMatch(
        a=SeaSide(user_id=1, name="Человек"),
        b=SeaSide(user_id=-1, name="Робот", is_bot=True),
    )
    m.begin(0.0)
    assert m.b.placed


# ── снаряды ─────────────────────────────────────────────────────────────────


def test_a_correct_answer_gives_a_shell():
    m = placed()
    result = answer(m, 1, 5.0)
    assert result.correct and result.shells == 1
    assert m.a.shells == 1
    assert result.task is not None, "сразу новый пример"


def test_a_streak_gives_two_shells():
    m = placed()
    steps = [answer(m, 1, t).step for t in (5.0, 6.0, 7.0)]
    assert steps == [1, 1, 2]
    assert m.a.shells == 3


def test_shells_do_not_pile_up():
    m = placed()
    for t in range(5, 15):
        answer(m, 1, float(t))
    assert m.a.shells == MAX_SHELLS


def test_a_wrong_answer_freezes_and_gives_nothing():
    m = placed()
    result = answer(m, 1, 5.0, correct=False)
    assert not result.correct and m.a.shells == 0
    assert m.a.frozen(5.5) and not m.a.frozen(5.0 + FREEZE_SEC + 0.1)


# ── выстрелы ────────────────────────────────────────────────────────────────


def test_no_shells_no_shot():
    m = placed()
    assert m.fire(1, 0, 0, 5.0)["result"] == "no_shells"
    assert not m.b.board.shots


def test_a_shot_costs_a_shell():
    m = placed()
    answer(m, 1, 5.0)
    shot = m.fire(1, 0, 0, 5.5)
    assert shot["result"] in ("miss", "hit", "sunk")
    assert shot["shells"] == 0 and m.a.shells == 0


def test_a_hit_is_counted():
    m = placed()
    answer(m, 1, 5.0)
    row, col = enemy_cells(m, 1)[0]
    shot = m.fire(1, row, col, 5.5)
    assert shot["result"] in ("hit", "sunk")
    assert m.a.hits_made == 1


def test_shooting_the_same_cell_twice_is_free():
    """Палец промахнулся по уже открытой клетке — снаряд остаётся."""
    m = placed()
    answer(m, 1, 5.0)
    answer(m, 1, 6.0)
    m.fire(1, 0, 0, 6.5)
    before = m.a.shells
    assert m.fire(1, 0, 0, 6.6)["result"] == "repeat"
    assert m.a.shells == before


def test_you_cannot_fire_before_the_battle():
    m = match()
    m.place(1, sea.random_layout())
    m.place(2, sea.random_layout())
    assert m.fire(1, 0, 0, 0.5)["result"] == "not_running"


def test_sinking_the_whole_fleet_wins():
    m = placed()
    now = 5.0
    for row, col in enemy_cells(m, 1):
        while m.a.shells == 0:
            now += 1.0
            answer(m, 1, now)
        now += 0.2
        m.fire(1, row, col, now)
    assert m.state == STATE_FINISHED
    assert m.reason == REASON_FLEET and m.winner_id == 1
    assert m.a.sunk_made == len(sea.FLEET)


def test_the_last_hit_reports_the_sunk_ship():
    m = placed()
    opp = m.opponent(1)
    single = next(ship for ship in opp.board.ships if ship.size == 1)
    answer(m, 1, 5.0)
    shot = m.fire(1, *single.cells[0], 5.5)
    assert shot["result"] == "sunk"
    assert set(shot["ship"]) == set(single.cells)
    assert shot["halo"], "вокруг убитого — пусто, клиенту это надо показать"


# ── время и разрывы ─────────────────────────────────────────────────────────


def test_time_up_goes_to_whoever_hit_more():
    m = placed()
    answer(m, 1, 5.0)
    row, col = enemy_cells(m, 1)[0]
    m.fire(1, row, col, 5.5)
    answer(m, 2, 6.0)
    m.fire(2, 6, 6, 6.5)   # почти наверняка мимо, но проверим честно
    if m.b.hits_made == 1:
        pytest.skip("случайно попал — не тот случай")
    m.poll(BATTLE_CAP_SEC + 10)
    assert m.state == STATE_FINISHED and m.reason == REASON_TIME
    assert m.winner_id == 1


def test_time_up_with_equal_hits_goes_to_the_better_solver():
    m = placed()
    answer(m, 1, 5.0)
    answer(m, 1, 6.0)
    answer(m, 2, 6.5)
    m.poll(BATTLE_CAP_SEC + 10)
    assert m.winner_id == 1


def test_nothing_happened_at_all_is_a_draw():
    m = placed()
    m.poll(BATTLE_CAP_SEC + 10)
    assert m.winner_id is None
    assert m.result_for(1)["outcome"] == "draw"


def test_leaving_during_placement_ends_the_match():
    m = match()
    m.place(1, sea.random_layout())
    m.disconnect(2, 5.0)
    m.poll(5.0 + DISCONNECT_GRACE + 0.1)
    assert m.reason == REASON_LEFT and m.winner_id == 1
    assert not m.rated, "не сыграли и не расставились — не матч"


def test_leaving_the_battle_is_a_rated_loss():
    m = placed()
    m.disconnect(2, 5.0)
    m.poll(5.0 + DISCONNECT_GRACE + 0.1)
    assert m.reason == REASON_LEFT and m.winner_id == 1
    assert m.rated


def test_both_gone_is_nobody_s_business():
    m = placed()
    m.disconnect(1, 5.0)
    m.disconnect(2, 5.0)
    m.poll(5.5)
    assert m.reason == REASON_ABANDONED and not m.rated


def test_a_fixed_duration_is_honoured():
    m = placed(duration=30)
    m.poll(1.0 + 3.1 + 31)
    assert m.state == STATE_FINISHED and m.reason == REASON_TIME


# ── что видит клиент ────────────────────────────────────────────────────────


def test_you_never_see_the_enemy_fleet():
    m = placed()
    view = m.snapshot(1, 5.0)
    assert "ships" not in view["enemy"]
    assert view["me"]["board"]["ships"], "своё поле видно целиком"
    assert view["enemy"]["alive"] == len(sea.FLEET)


def test_the_enemy_view_shows_only_what_you_found():
    m = placed()
    answer(m, 1, 5.0)
    row, col = enemy_cells(m, 1)[0]
    m.fire(1, row, col, 5.5)
    view = m.snapshot(1, 6.0)["enemy"]
    assert (row, col) in view["hits"]
    assert view["last"] == [row, col]


def test_the_snapshot_says_which_stage_we_are_in():
    m = match()
    assert m.snapshot(1, 0.0)["state"] == STATE_PLACING
    assert m.snapshot(1, 0.0)["place_left_ms"] > 0
    m.place(1, sea.random_layout())
    m.place(2, sea.random_layout())
    m.poll(1.0)
    assert m.snapshot(1, 1.0)["starts_in_ms"] > 0


def test_the_result_reveals_the_enemy_fleet_at_last():
    m = placed()
    m.poll(BATTLE_CAP_SEC + 10)
    result = m.result_for(1)
    assert len(result["enemy_fleet"]) == len(sea.FLEET)
    assert result["game"] == "sea"


def test_the_match_knows_its_game():
    assert match().game == "sea"
    assert placed().margin() == 0
