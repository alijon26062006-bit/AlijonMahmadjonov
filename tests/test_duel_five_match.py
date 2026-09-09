"""Партия «Пять в ряд»: очередь хода, победа линией, ничья, время."""

from duel import five
from duel.game import (
    DISCONNECT_GRACE,
    REASON_ABANDONED,
    REASON_LEFT,
    REASON_TIME,
    STATE_FINISHED,
    STATE_RUNNING,
)
from duel.five_match import (
    GAME_CAP_SEC,
    MAX_SKIPS,
    REASON_FULL,
    REASON_IDLE,
    REASON_LINE,
    TURN_SEC,
    FiveMatch,
    FiveSide,
)


def match(seed=1, duration=0):
    m = FiveMatch(
        a=FiveSide(user_id=1, name="Первый"),
        b=FiveSide(user_id=2, name="Второй"),
        duration=duration,
        seed=seed,
    )
    m.begin(0.0)
    m.poll(3.5)
    assert m.state == STATE_RUNNING
    return m


def started(seed=1, duration=0):
    """Партия, где первым ходит первый: тестам так проще про неё рассказывать."""
    m = match(seed, duration)
    if m.turn != 1:
        m.turn = 1
        m.a.mark, m.b.mark = m.b.mark, m.a.mark
    return m


def fill_without_five():
    """Полное поле, на котором никто не выстроил пятёрку.

    Идём по клеткам и ставим знак, который пятёрку не создаёт; если не
    подходит ни один — отступаем на клетку назад и пробуем иначе. Так поле
    заполняется честно, по правилам игры, а не подгоняется руками.
    """
    order = [(row, col) for row in range(five.SIZE) for col in range(five.SIZE)]
    board, tried, i = {}, [0] * len(order), 0
    while i < len(order):
        spot = order[i]
        placed = False
        for choice in range(tried[i], 2):
            board[spot] = (five.X, five.O)[choice]
            if not five.winning_line(board, *spot):
                tried[i] = choice + 1
                placed = True
                break
        if placed:
            i += 1
            if i < len(order):
                tried[i] = 0
        else:
            board.pop(spot, None)
            tried[i] = 0
            i -= 1
            assert i >= 0, "поле без пятёрок должно существовать"
    return board


# ── начало ──────────────────────────────────────────────────────────────────


def test_the_game_starts_without_placing_or_tasks():
    m = match()
    assert m.state == STATE_RUNNING
    assert m.a.task is None and m.b.task is None
    assert m.board == {}


def test_the_first_player_gets_the_crosses():
    m = match()
    first, second = m.side(m.turn), m.opponent(m.turn)
    assert (first.mark, second.mark) == (five.X, five.O)


def test_who_starts_is_drawn_by_lot():
    assert {match(seed=seed).turn for seed in range(12)} == {1, 2}


# ── ходы ────────────────────────────────────────────────────────────────────


def test_a_move_puts_your_mark_and_hands_the_turn_over():
    m = started()
    result = m.play(1, 4, 4, 5.0)
    assert result["result"] == "ok" and result["cell"] == [4, 4]
    assert m.board[(4, 4)] == m.a.mark
    assert m.turn == 2 and m.turn_deadline == 5.0 + TURN_SEC
    assert m.a.moves == 1


def test_you_cannot_move_out_of_turn():
    m = started()
    assert m.play(2, 0, 0, 5.0)["result"] == "not_your_turn"
    assert m.board == {}


def test_you_cannot_take_a_taken_cell():
    m = started()
    m.play(1, 4, 4, 5.0)
    assert m.play(2, 4, 4, 5.5)["result"] == "busy"
    assert m.turn == 2, "неудачный ход очередь не отдаёт"


def test_a_move_outside_the_field_is_refused():
    m = started()
    assert m.play(1, 9, 0, 5.0)["result"] == "busy"


def test_thinking_too_long_loses_the_turn():
    m = started()
    assert m.poll(m.turn_deadline + 0.1)
    assert m.turn == 2 and m.a.skips == 1


def test_three_skipped_turns_in_a_row_lose_the_game():
    m = started()
    m.play(1, 0, 0, 1.0)   # чтобы партия считалась сыгранной
    now = m.turn_deadline
    for _ in range(MAX_SKIPS * 2 + 1):
        now += TURN_SEC + 0.1
        m.poll(now)
        if m.state == STATE_FINISHED:
            break
    assert m.reason == REASON_IDLE and m.winner_id in (1, 2)
    assert m.rated


# ── победа ──────────────────────────────────────────────────────────────────


def test_five_in_a_row_wins_at_once():
    m = started()
    now = 5.0
    for step in range(5):
        now += 0.5
        result = m.play(1, 2, step, now)
        if step < 4:
            assert not result["win"]
            m.turn = 1          # соперник ходит в сторону, очередь возвращаем
    assert m.state == STATE_FINISHED
    assert m.reason == REASON_LINE and m.winner_id == 1
    assert len(m.win_line) == 5
    assert m.result_for(1)["outcome"] == "win"
    assert m.result_for(2)["outcome"] == "loss"


def test_a_diagonal_wins_too():
    m = started()
    for step in range(5):
        m.turn = 1
        m.play(1, step, step, 5.0 + step)
    assert m.reason == REASON_LINE and m.winner_id == 1


def test_a_full_field_is_a_draw():
    m = started()
    board = fill_without_five()
    last = (8, 8)
    mark = board.pop(last)
    m.board = board
    m.a.mark, m.b.mark = mark, five.O if mark == five.X else five.X
    m.play(1, *last, 9.0)
    assert m.state == STATE_FINISHED and m.reason == REASON_FULL
    assert m.winner_id is None and m.result_for(1)["outcome"] == "draw"


def test_time_up_goes_to_the_longer_line():
    m = started()
    for step in range(3):
        m.turn = 1
        m.play(1, 0, step, 5.0 + step)
    m.turn = 2
    m.play(2, 8, 0, 9.0)
    m.poll(GAME_CAP_SEC + 10)
    assert m.reason == REASON_TIME and m.winner_id == 1
    assert m.result_for(1)["line"] == 3 and m.result_for(1)["opp_line"] == 1


def test_leaving_hands_the_win_over():
    m = started()
    m.play(1, 4, 4, 5.0)
    m.disconnect(2, 6.0)
    m.poll(6.0 + DISCONNECT_GRACE + 0.1)
    assert m.reason == REASON_LEFT and m.winner_id == 1 and m.rated


def test_leaving_before_the_first_move_is_not_a_game():
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


def test_the_snapshot_tells_whose_turn_and_what_is_on_the_field():
    m = started()
    m.play(1, 4, 4, 5.0)
    mine, theirs = m.snapshot(1, 5.5), m.snapshot(2, 5.5)
    assert mine["my_turn"] is False and theirs["my_turn"] is True
    assert mine["cells"] == [[4, 4, m.a.mark]]
    assert mine["last"] == [4, 4] and mine["mark"] == m.a.mark
    assert mine["turn_ms"] > 0 and mine["win"] == []


def test_the_snapshot_shows_the_winning_line():
    m = started()
    for step in range(5):
        m.turn = 1
        m.play(1, 3, step, 5.0)
    assert len(m.snapshot(1, 5.5)["win"]) == 5


def test_the_result_counts_moves_and_lines():
    m = started()
    m.play(1, 4, 4, 5.0)
    m.play(2, 0, 0, 5.5)
    m.poll(GAME_CAP_SEC + 10)
    result = m.result_for(1)
    assert result["game"] == "five" and result["moves"] == 1
    assert result["opp_moves"] == 1 and result["cells"]


def test_the_match_knows_its_game():
    assert match().game == "five"
