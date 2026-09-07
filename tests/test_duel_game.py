"""Правила матча: канат, серии, ошибки, время, разрыв связи."""

import pytest

from duel import game
from duel.game import Match, Side


def make_match(duration=60, level="normal", seed=1):
    match = Match(
        a=Side(user_id=1, name="Первый"),
        b=Side(user_id=2, name="Второй"),
        duration=duration,
        level=level,
        seed=seed,
    )
    match.begin(0.0, countdown=0.0)
    match.activate(0.0)
    return match


def answer(match, user_id, now, correct=True, offset=0):
    """Отвечает за игрока: верно или мимо."""
    side = match.side(user_id)
    value = side.task.answer + (0 if correct else 7)
    return match.submit(user_id, side.task.id, value, now + offset)


def test_correct_answer_pulls_the_rope():
    match = make_match()
    result = answer(match, 1, 1.0)
    assert result.correct and result.step == 1
    assert match.rope() == 1
    assert match.a.score == 1


def test_wrong_answer_freezes_and_does_not_move_the_rope():
    match = make_match()
    result = answer(match, 1, 1.0, correct=False)
    assert result.accepted and not result.correct
    assert match.rope() == 0
    assert match.a.streak == 0
    assert match.a.frozen(1.0)
    assert not match.a.frozen(1.0 + game.FREEZE_SEC + 0.01)


def test_frozen_player_cannot_answer():
    match = make_match()
    answer(match, 1, 1.0, correct=False)
    blocked = match.submit(1, match.a.task.id, match.a.task.answer, 1.2)
    assert not blocked.accepted and blocked.note == "frozen"
    assert match.rope() == 0


def test_third_correct_in_a_row_pulls_twice_as_hard():
    match = make_match()
    steps = [answer(match, 1, t).step for t in (1.0, 2.0, 3.0, 4.0)]
    assert steps == [1, 1, game.BONUS_STEP, game.BONUS_STEP]
    assert match.rope() == 1 + 1 + 2 + 2


def test_streak_resets_after_a_miss():
    match = make_match()
    answer(match, 1, 1.0)
    answer(match, 1, 2.0)
    answer(match, 1, 3.0, correct=False)
    assert match.a.streak == 0
    assert answer(match, 1, 5.0).step == 1


def test_rope_reaching_the_edge_ends_the_match():
    match = make_match(duration=0)
    now = 1.0
    while match.state == game.STATE_RUNNING:
        answer(match, 1, now)
        now += 1.0
    assert match.reason == game.REASON_ROPE
    assert match.winner_id == 1
    assert abs(match.rope()) >= game.WIN_STEPS


def test_opponent_pulling_back_moves_the_rope_to_the_middle():
    match = make_match()
    answer(match, 1, 1.0)
    answer(match, 1, 2.0)
    assert match.rope() == 2
    answer(match, 2, 3.0)
    answer(match, 2, 4.0)
    assert match.rope() == 0


def test_time_out_gives_the_win_to_the_rope_side():
    match = make_match(duration=30)
    answer(match, 2, 1.0)
    match.poll(31.0)
    assert match.state == game.STATE_FINISHED
    assert match.reason == game.REASON_TIME
    assert match.winner_id == 2


def test_dead_even_match_is_a_draw():
    match = make_match(duration=30)
    answer(match, 1, 1.0)
    answer(match, 2, 1.5)
    match.poll(31.0)
    assert match.winner_id is None
    assert match.result_for(1)["outcome"] == "draw"


def test_equal_rope_is_decided_by_correct_answers():
    """Канат посередине — считаем, кто дал больше верных ответов."""
    match = make_match(duration=30)
    match.a.pull = match.b.pull = 4
    match.a.score, match.b.score = 5, 3
    match.poll(31.0)
    assert match.winner_id == 1


def test_stale_answer_to_an_old_task_is_ignored():
    match = make_match()
    stale_id = match.a.task.id
    answer(match, 1, 1.0)
    result = match.submit(1, stale_id, 0, 2.0)
    assert not result.accepted and result.note == "stale"


def test_same_task_changes_after_two_misses():
    match = make_match()
    first = match.a.task.id
    answer(match, 1, 1.0, correct=False)
    assert match.a.task.id == first
    answer(match, 1, 1.0 + game.FREEZE_SEC + 0.1, correct=False)
    assert match.a.task.id != first


def test_impossibly_fast_answers_are_rejected():
    match = make_match()
    for _ in range(game.SUSPICIOUS_LIMIT - 1):
        side = match.a
        result = match.submit(1, side.task.id, side.task.answer, side.task_at + 0.01)
        assert not result.accepted and result.note == "too_fast"
    assert match.rope() == 0


def test_a_robot_loses_the_match():
    match = make_match()
    for _ in range(game.SUSPICIOUS_LIMIT):
        side = match.a
        if side.task is None:
            break
        match.submit(1, side.task.id, side.task.answer, side.task_at + 0.01)
    assert match.state == game.STATE_FINISHED
    assert match.reason == game.REASON_CHEAT
    assert match.winner_id == 2


def test_leaving_gives_the_opponent_a_technical_win():
    match = make_match()
    match.disconnect(1, 10.0)
    assert not match.poll(10.0 + game.DISCONNECT_GRACE - 1)
    assert match.poll(10.0 + game.DISCONNECT_GRACE + 0.1)
    assert match.reason == game.REASON_LEFT
    assert match.winner_id == 2


def test_coming_back_in_time_keeps_the_match_alive():
    match = make_match()
    match.disconnect(1, 10.0)
    match.reconnect(1, 12.0)
    assert not match.poll(10.0 + game.DISCONNECT_GRACE + 1)
    assert match.state == game.STATE_RUNNING


def test_both_gone_means_nobody_wins():
    match = make_match()
    match.disconnect(1, 10.0)
    match.disconnect(2, 10.5)
    match.poll(11.0)
    assert match.reason == game.REASON_ABANDONED
    assert match.winner_id is None
    assert not match.rated


def test_countdown_runs_before_the_match_starts():
    match = Match(a=Side(user_id=1, name="A"), b=Side(user_id=2, name="B"), duration=60)
    match.begin(0.0)
    assert match.state == game.STATE_COUNTDOWN
    assert match.submit(1, 1, 1, 0.5).note == "not_running"
    assert not match.poll(1.0)
    assert match.poll(game.COUNTDOWN_SEC + 0.1)
    assert match.state == game.STATE_RUNNING
    assert match.a.task is not None and match.b.task is not None


def test_endless_match_has_no_clock():
    match = make_match(duration=0)
    assert match.left_ms(5.0) is None
    assert match.snapshot(1, 5.0)["left_ms"] is None


def test_endless_match_still_ends_eventually():
    match = make_match(duration=0)
    match.poll(game.ENDLESS_CAP_SEC + 1)
    assert match.state == game.STATE_FINISHED


def test_snapshot_is_seen_from_the_players_own_side():
    match = make_match()
    answer(match, 1, 1.0)
    assert match.snapshot(1, 2.0)["rope"] == 1
    assert match.snapshot(2, 2.0)["rope"] == -1


def test_snapshot_never_leaks_the_answer():
    match = make_match()
    dump = repr(match.snapshot(1, 1.0))
    assert str(match.a.task.answer) not in dump or "score" in dump
    assert "answer" not in dump


def test_result_counts_accuracy_and_speed():
    match = make_match(duration=10)
    answer(match, 1, 1.0, offset=0)
    answer(match, 1, 2.0)
    answer(match, 1, 3.0, correct=False)
    match.poll(11.0)
    result = match.result_for(1)
    assert result["score"] == 2 and result["wrong"] == 1
    assert result["accuracy"] == 67
    assert result["avg_ms"] > 0


def test_a_match_nobody_played_is_not_rated():
    match = make_match(duration=5)
    match.poll(6.0)
    assert not match.rated


def test_a_played_match_is_rated():
    match = make_match(duration=5)
    answer(match, 1, 1.0)
    match.poll(6.0)
    assert match.rated


def test_answers_after_the_end_are_ignored():
    match = make_match(duration=5)
    match.poll(6.0)
    assert not match.submit(1, 1, 1, 7.0).accepted


def test_a_stranger_cannot_answer():
    match = make_match()
    assert not match.submit(999, 1, 1, 1.0).accepted
    assert match.side(999) is None
