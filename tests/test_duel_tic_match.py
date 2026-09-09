"""Матч в крестики-нолики: три партии, очередь хода, счёт."""

from duel import tic
from duel.game import (
    DISCONNECT_GRACE,
    REASON_ABANDONED,
    REASON_LEFT,
    REASON_TIME,
    STATE_FINISHED,
    STATE_RUNNING,
)
from duel.tic_match import (
    GAME_CAP_SEC,
    MAX_SKIPS,
    REASON_FULL,
    REASON_IDLE,
    REASON_ROUNDS,
    ROUNDS,
    ROUND_PAUSE,
    TO_WIN,
    TURN_SEC,
    TicMatch,
    TicSide,
)


def match(seed=1, duration=0):
    m = TicMatch(
        a=TicSide(user_id=1, name="Первый"),
        b=TicSide(user_id=2, name="Второй"),
        duration=duration,
        seed=seed,
    )
    m.begin(0.0)
    m.poll(3.5)
    assert m.state == STATE_RUNNING
    return m


def started(seed=1, duration=0):
    """Матч, где первую партию начинает первый: так тестам проще."""
    m = match(seed, duration)
    if m.turn != 1:
        m.start_round(3.5, 1)
    return m


def win_round(m, user_id, now=5.0, row=0):
    """Проводит партию до победы игрока: три его знака в одной строке."""
    other = m.opponent(user_id).user_id
    for col in range(tic.WIN):
        m.turn = user_id
        m.play(user_id, row, col, now)
        now += 0.5
        if m.between_rounds or m.state == STATE_FINISHED:
            break
        m.turn = other
        m.play(other, 2 if row != 2 else 1, col, now)   # соперник ходит в стороне
        now += 0.5
    return now


def draw_round(m, now=5.0):
    """Проводит партию вничью: классическая «мельница» без тройки."""
    order = [(1, 1), (0, 0), (0, 2), (2, 0), (0, 1), (2, 1),
             (1, 0), (1, 2), (2, 2)]
    first, second = m.turn, m.opponent(m.turn).user_id
    for i, spot in enumerate(order):
        who = first if i % 2 == 0 else second
        m.turn = who
        m.play(who, spot[0], spot[1], now)
        now += 0.2
        if m.between_rounds or m.state == STATE_FINISHED:
            break
    return now


# ── начало ──────────────────────────────────────────────────────────────────


def test_the_match_starts_with_the_first_round():
    m = match()
    assert m.round_no == 1 and m.board == {}
    assert m.a.task is None and m.b.task is None, "примеров тут нет"


def test_the_one_who_starts_gets_the_crosses():
    m = match()
    first, second = m.side(m.turn), m.opponent(m.turn)
    assert (first.mark, second.mark) == (tic.X, tic.O)


def test_who_starts_is_drawn_by_lot():
    assert {match(seed=seed).turn for seed in range(12)} == {1, 2}


# ── ходы ────────────────────────────────────────────────────────────────────


def test_a_move_puts_your_mark_and_hands_the_turn_over():
    m = started()
    result = m.play(1, 1, 1, 5.0)
    assert result["result"] == "ok" and result["cell"] == [1, 1]
    assert m.board[(1, 1)] == m.a.mark
    assert m.turn == 2 and m.turn_deadline == 5.0 + TURN_SEC
    assert m.a.moves == 1


def test_you_cannot_move_out_of_turn():
    m = started()
    assert m.play(2, 0, 0, 5.0)["result"] == "not_your_turn"
    assert m.board == {}


def test_you_cannot_take_a_taken_cell():
    m = started()
    m.play(1, 1, 1, 5.0)
    assert m.play(2, 1, 1, 5.5)["result"] == "busy"
    assert m.turn == 2, "неудачный ход очередь не отдаёт"


def test_thinking_too_long_loses_the_turn():
    m = started()
    assert m.poll(m.turn_deadline + 0.1)
    assert m.turn == 2 and m.a.skips == 1


def test_three_skipped_turns_in_a_row_lose_the_match():
    m = started()
    m.play(1, 0, 0, 1.0)
    now = m.turn_deadline
    for _ in range(MAX_SKIPS * 2 + 1):
        now += TURN_SEC + 0.1
        m.poll(now)
        if m.state == STATE_FINISHED:
            break
    assert m.reason == REASON_IDLE and m.winner_id in (1, 2) and m.rated


# ── партии ──────────────────────────────────────────────────────────────────


def test_three_in_a_row_takes_the_round_not_the_match():
    m = started()
    win_round(m, 1)
    assert m.a.rounds_won == 1 and m.b.rounds_won == 0
    assert m.state == STATE_RUNNING, "матч идёт дальше: партий три"
    assert m.between_rounds and len(m.win_line) == tic.WIN


def test_the_next_round_starts_after_a_pause():
    m = started()
    now = win_round(m, 1)
    assert not m.poll(now + ROUND_PAUSE / 2), "паузу выдерживаем"
    assert m.poll(m.round_over_at + 0.1)
    assert m.round_no == 2 and m.board == {} and not m.between_rounds


def test_the_first_move_changes_hands_every_round():
    m = started()
    first = m.turn
    now = win_round(m, first)
    m.poll(m.round_over_at + 0.1)
    assert m.turn != first, "иначе первый ход решал бы весь матч"
    assert m.side(m.turn).mark == tic.X, "крестики всегда у начинающего"


def test_two_rounds_win_the_match():
    m = started()
    now = win_round(m, 1)
    m.poll(m.round_over_at + 0.1)
    win_round(m, 1, now + 5)
    assert m.state == STATE_FINISHED
    assert m.reason == REASON_ROUNDS and m.winner_id == 1
    assert m.a.rounds_won == TO_WIN
    assert m.result_for(1)["outcome"] == "win"
    assert m.result_for(2)["outcome"] == "loss"


def test_a_draw_in_a_round_does_not_end_the_match():
    m = started()
    now = draw_round(m)
    assert m.a.rounds_won == 0 and m.b.rounds_won == 0
    assert m.between_rounds and m.state == STATE_RUNNING
    m.poll(m.round_over_at + 0.1)
    assert m.round_no == 2


def test_three_draws_are_a_draw():
    m = started()
    now = 5.0
    for _ in range(ROUNDS):
        now = draw_round(m, now) + 1
        if m.between_rounds:
            m.poll(m.round_over_at + 0.1)
    assert m.state == STATE_FINISHED and m.reason == REASON_FULL
    assert m.winner_id is None and m.result_for(1)["outcome"] == "draw"


def test_one_win_and_two_draws_take_the_match():
    m = started()
    now = win_round(m, 1)
    m.poll(m.round_over_at + 0.1)
    now = draw_round(m, now + 1) + 1
    m.poll(m.round_over_at + 0.1)
    draw_round(m, now)
    assert m.state == STATE_FINISHED and m.winner_id == 1
    assert m.a.rounds_won == 1 and m.b.rounds_won == 0


def test_nobody_moves_while_the_round_is_over():
    m = started()
    win_round(m, 1)
    assert m.play(2, 2, 2, 30.0)["result"] == "between_rounds"


# ── время и разрывы ─────────────────────────────────────────────────────────


def test_time_up_goes_to_the_one_with_more_rounds():
    m = started()
    win_round(m, 1)
    m.poll(m.round_over_at + 0.1)
    m.poll(GAME_CAP_SEC + 10)
    assert m.reason == REASON_TIME and m.winner_id == 1


def test_leaving_hands_the_win_over():
    m = started()
    m.play(1, 1, 1, 5.0)
    m.disconnect(2, 6.0)
    m.poll(6.0 + DISCONNECT_GRACE + 0.1)
    assert m.reason == REASON_LEFT and m.winner_id == 1 and m.rated


def test_leaving_before_the_first_move_is_not_a_match():
    m = started()
    m.disconnect(2, 5.0)
    m.poll(5.0 + DISCONNECT_GRACE + 0.1)
    assert m.reason == REASON_LEFT and not m.rated


def test_both_gone_is_nobody_s_business():
    m = started()
    m.disconnect(1, 5.0)
    m.disconnect(2, 5.0)
    m.poll(5.5)
    assert m.reason == REASON_ABANDONED and not m.rated


# ── что видит клиент ────────────────────────────────────────────────────────


def test_the_snapshot_tells_the_turn_the_score_and_the_round():
    m = started()
    m.play(1, 1, 1, 5.0)
    mine, theirs = m.snapshot(1, 5.5), m.snapshot(2, 5.5)
    assert mine["my_turn"] is False and theirs["my_turn"] is True
    assert mine["cells"] == [[1, 1, m.a.mark]] and mine["last"] == [1, 1]
    assert mine["round"] == 1 and mine["rounds"] == ROUNDS
    assert mine["me"]["score"] == 0 and mine["turn_ms"] > 0
    assert mine["round_end"] == "" and mine["pause_ms"] == 0


def test_the_snapshot_shows_how_the_round_ended():
    m = started()
    now = win_round(m, 1)
    mine, theirs = m.snapshot(1, now), m.snapshot(2, now)
    assert mine["round_end"] == "win" and theirs["round_end"] == "loss"
    assert mine["pause_ms"] > 0 and mine["my_turn"] is False
    assert len(mine["win"]) == tic.WIN and mine["me"]["score"] == 1


def test_the_result_counts_rounds_and_moves():
    m = started()
    now = win_round(m, 1)
    m.poll(m.round_over_at + 0.1)
    win_round(m, 1, now + 5)
    result = m.result_for(1)
    assert result["game"] == "tic" and result["score"] == 2
    assert result["opp_score"] == 0 and result["moves"] >= 6
    assert result["cells"], "последняя партия уезжает на экран итога"


def test_the_match_knows_its_game():
    assert match().game == "tic"
