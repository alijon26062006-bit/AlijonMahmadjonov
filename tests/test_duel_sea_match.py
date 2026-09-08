"""Морской бой как матч: расстановка, ходы по очереди, выстрелы, победа."""

import random

from duel import sea
from duel.game import (
    DISCONNECT_GRACE,
    REASON_ABANDONED,
    REASON_LEFT,
    REASON_TIME,
    STATE_COUNTDOWN,
    STATE_FINISHED,
    STATE_RUNNING,
)
from duel.sea_match import (
    BATTLE_CAP_SEC,
    MAX_SKIPS,
    PLACE_SEC,
    REASON_FLEET,
    REASON_IDLE,
    STATE_PLACING,
    TURN_SEC,
    SeaMatch,
    SeaSide,
)


def match(seed=1, duration=0):
    m = SeaMatch(
        a=SeaSide(user_id=1, name="Первый"),
        b=SeaSide(user_id=2, name="Второй"),
        duration=duration,
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


def ready(seed=1, duration=0):
    """Матч, где первым ходит первый: тестам так проще рассказывать про ходы."""
    m = placed(seed, duration)
    if m.turn != 1:
        m.turn = 1
    return m


def enemy_cells(m, user_id):
    """Где на самом деле стоят корабли соперника — тесту знать можно."""
    opp = m.opponent(user_id)
    return [spot for ship in opp.board.ships for spot in ship.cells]


def empty_cell(m, user_id):
    """Клетка, где у соперника точно никого нет."""
    taken = set(enemy_cells(m, user_id))
    shots = m.opponent(user_id).board.shots
    return next(
        (r, c)
        for r in range(sea.SIZE)
        for c in range(sea.SIZE)
        if (r, c) not in taken and (r, c) not in shots
    )


# ── расстановка ─────────────────────────────────────────────────────────────


def test_a_new_match_starts_with_placement_not_a_countdown():
    m = match()
    assert m.state == STATE_PLACING
    assert m.a.task is None, "примеров в морском бою нет вовсе"


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


# ── очередь хода ────────────────────────────────────────────────────────────


def test_the_battle_starts_with_somebody_s_turn():
    m = placed()
    assert m.turn in (1, 2)
    assert m.my_turn(m.turn) and not m.my_turn(3 - m.turn)
    assert m.turn_deadline > 0


def test_the_first_move_is_drawn_by_lot():
    """Иначе первым всегда ходил бы тот, кто раньше нажал «Готов»."""
    firsts = {placed(seed=seed).turn for seed in range(12)}
    assert firsts == {1, 2}


def test_you_cannot_shoot_out_of_turn():
    m = ready()
    row, col = enemy_cells(m, 2)[0]
    assert m.fire(2, row, col, 5.0)["result"] == "not_your_turn"
    assert not m.a.board.shots, "чужое поле осталось нетронутым"


def test_a_hit_lets_you_shoot_again():
    m = ready()
    row, col = enemy_cells(m, 1)[0]
    shot = m.fire(1, row, col, 5.0)
    assert shot["result"] in ("hit", "sunk") and shot["again"] is True
    assert m.turn == 1


def test_a_miss_hands_the_turn_over():
    m = ready()
    row, col = empty_cell(m, 1)
    shot = m.fire(1, row, col, 5.0)
    assert shot["result"] == "miss" and shot["again"] is False
    assert m.turn == 2
    assert m.turn_deadline == 5.0 + TURN_SEC


def test_a_hit_gives_a_fresh_thirty_seconds():
    m = ready()
    row, col = enemy_cells(m, 1)[0]
    m.fire(1, row, col, 20.0)
    assert m.turn_deadline == 20.0 + TURN_SEC


def test_shooting_the_same_cell_twice_costs_nothing():
    """Палец попал в уже открытую клетку — это не выстрел, ход остаётся."""
    m = ready()
    row, col = enemy_cells(m, 1)[0]
    m.fire(1, row, col, 5.0)
    shots = m.a.shots_fired
    assert m.fire(1, row, col, 5.5)["result"] == "repeat"
    assert m.turn == 1 and m.a.shots_fired == shots


def test_you_cannot_fire_before_the_battle():
    m = match()
    m.place(1, sea.random_layout())
    m.place(2, sea.random_layout())
    assert m.fire(1, 0, 0, 0.5)["result"] == "not_running"


def test_thinking_too_long_loses_the_turn():
    m = ready()
    assert m.poll(m.turn_deadline + 0.1)
    assert m.turn == 2 and m.a.skips == 1


def test_three_skipped_turns_in_a_row_lose_the_match():
    m = ready()
    now = m.turn_deadline
    for _ in range(MAX_SKIPS * 2):
        now += TURN_SEC + 0.1
        m.poll(now)
        if m.state == STATE_FINISHED:
            break
    assert m.state == STATE_FINISHED and m.reason == REASON_IDLE
    assert m.winner_id == 2 and m.rated


def test_a_shot_wipes_the_skips():
    m = ready()
    m.poll(m.turn_deadline + 0.1)   # пропустил первый
    m.turn = 1
    row, col = enemy_cells(m, 1)[0]
    m.fire(1, row, col, 40.0)
    assert m.a.skips == 0


# ── попадания и победа ──────────────────────────────────────────────────────


def test_hits_and_misses_are_counted_like_answers():
    """Счёт — попадания, промахи — ошибки: рейтинг и точность считаются
    тем же кодом, что и в канате."""
    m = ready()
    row, col = enemy_cells(m, 1)[0]
    m.fire(1, row, col, 5.0)
    assert m.a.hits_made == 1 and m.a.score == 1 and m.a.streak == 1
    m.fire(1, *empty_cell(m, 1), 5.5)
    assert m.a.misses_made == 1 and m.a.streak == 0
    assert m.a.shots_fired == 2 and m.a.accuracy == 50


def test_sinking_the_whole_fleet_wins():
    m = ready()
    now = 5.0
    for row, col in enemy_cells(m, 1):
        now += 0.2
        m.turn = 1          # попадания и так оставляют ход, но страхуемся
        m.fire(1, row, col, now)
    assert m.state == STATE_FINISHED
    assert m.reason == REASON_FLEET and m.winner_id == 1
    assert m.a.sunk_made == len(sea.FLEET)
    assert m.a.best_streak == sum(sea.FLEET), "все девять подряд"


def test_the_last_hit_reports_the_sunk_ship():
    m = ready()
    opp = m.opponent(1)
    single = next(ship for ship in opp.board.ships if ship.size == 1)
    shot = m.fire(1, *single.cells[0], 5.0)
    assert shot["result"] == "sunk"
    assert set(shot["ship"]) == set(single.cells)
    assert shot["halo"], "вокруг убитого — пусто, клиенту это надо показать"


# ── время и разрывы ─────────────────────────────────────────────────────────


def test_time_up_goes_to_whoever_hit_more():
    m = ready()
    row, col = enemy_cells(m, 1)[0]
    m.fire(1, row, col, 5.0)
    m.poll(BATTLE_CAP_SEC + 10)
    assert m.state == STATE_FINISHED and m.reason == REASON_TIME
    assert m.winner_id == 1


def test_nothing_happened_at_all_is_a_draw():
    m = ready()
    m.deadline = 1.0
    m.poll(2.0)
    assert m.winner_id is None
    assert m.result_for(1)["outcome"] == "draw"
    assert not m.rated, "никто не выстрелил — не за что менять рейтинг"


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
    m = ready()
    view = m.snapshot(1, 5.0)
    assert "ships" not in view["enemy"]
    assert view["me"]["board"]["ships"], "своё поле видно целиком"
    assert view["enemy"]["alive"] == len(sea.FLEET)


def test_the_snapshot_says_whose_turn_it_is():
    m = ready()
    mine, theirs = m.snapshot(1, 5.0), m.snapshot(2, 5.0)
    assert mine["my_turn"] is True and theirs["my_turn"] is False
    assert mine["turn_ms"] > 0 and mine["turn_ms"] == theirs["turn_ms"]


def test_the_clock_does_not_change_every_tick():
    """Иначе состояние летело бы по сети двадцать раз в секунду."""
    m = ready()
    assert m.snapshot(1, 5.0)["turn_ms"] == m.snapshot(1, 5.1)["turn_ms"]


def test_the_enemy_view_shows_only_what_you_found():
    m = ready()
    row, col = enemy_cells(m, 1)[0]
    m.fire(1, row, col, 5.0)
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
    m = ready()
    row, col = enemy_cells(m, 1)[0]
    m.fire(1, row, col, 5.0)
    m.poll(BATTLE_CAP_SEC + 10)
    result = m.result_for(1)
    assert len(result["enemy_fleet"]) == len(sea.FLEET)
    assert result["game"] == "sea"
    # Последний выстрел тоже должен быть виден: состояния после него нет.
    assert (row, col) in result["enemy_view"]["hits"]


def test_the_match_knows_its_game():
    assert match().game == "sea"
    assert ready().margin() == 0
