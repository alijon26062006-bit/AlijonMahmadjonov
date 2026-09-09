"""«Пять в ряд» по WebSocket: очередь хода, знаки, победа линией."""

import time

from duel import five, storage
from duel.five_match import TURN_SEC
from tests.test_duel_server import client, join  # noqa: F401
from tests.test_duel_server import state_where as _state_where


async def state_where(player, check, tries=600):
    return await _state_where(player, check, tries)


async def game(client):
    """Двое нашли друг друга и партия пошла. Возвращает «ходящий, ждущий»."""
    one, _ = await join(client, 1, "Первый")
    two, _ = await join(client, 2, "Второй")
    for player in (one, two):
        await player.send(t="find", game="five")
    for player in (one, two):
        found = await player.recv("found")
        assert found["game"] == "five"
    state = await state_where(one, lambda s: s["state"] == "running")
    return (one, two) if state["my_turn"] else (two, one)


def match_of(client):
    return client.hub.match_for(1)


# ── начало ──────────────────────────────────────────────────────────────────


async def test_the_game_starts_at_once_without_tasks(client):
    one, two = await game(client)
    mine = await state_where(one, lambda s: s["state"] == "running")
    theirs = await state_where(two, lambda s: s["state"] == "running")
    assert mine["my_turn"] is True and theirs["my_turn"] is False
    assert mine["mark"] == "x" and theirs["mark"] == "o"
    assert mine["cells"] == [] and 0 < mine["turn_ms"] <= TURN_SEC * 1000
    await one.silent("task", timeout=0.3)   # примеров тут нет


async def test_five_and_sea_seekers_never_meet(client):
    one, _ = await join(client, 1, "Пятёрка")
    two, _ = await join(client, 2, "Море")
    await one.send(t="find", game="five")
    await two.send(t="find", game="sea")
    await one.silent("found", timeout=0.8)
    await two.silent("found", timeout=0.2)


# ── ходы ────────────────────────────────────────────────────────────────────


async def test_a_move_shows_up_on_both_screens(client):
    one, two = await game(client)
    await one.send(t="move", row=4, col=4)
    mine = await state_where(one, lambda s: s["cells"])
    theirs = await state_where(two, lambda s: s["cells"])
    assert mine["cells"] == [[4, 4, "x"]] and mine["last"] == [4, 4]
    assert theirs["cells"] == [[4, 4, "x"]]
    assert mine["my_turn"] is False and theirs["my_turn"] is True


async def test_you_cannot_move_out_of_turn(client):
    one, two = await game(client)
    await two.send(t="move", row=0, col=0)
    assert (await two.recv("move_error"))["reason"] == "not_your_turn"
    assert match_of(client).board == {}


async def test_you_cannot_take_a_taken_cell(client):
    one, two = await game(client)
    await one.send(t="move", row=4, col=4)
    await state_where(two, lambda s: s["my_turn"])
    await two.send(t="move", row=4, col=4)
    assert (await two.recv("move_error"))["reason"] == "busy"


async def test_a_skipped_turn_moves_on(client):
    one, two = await game(client)
    match = match_of(client)
    waiting = match.opponent(match.turn).user_id
    match.turn_deadline = time.monotonic() + 0.2
    await state_where(two, lambda s: s["state"] == "running" and s["my_turn"])
    assert match_of(client).turn == waiting


# ── победа ──────────────────────────────────────────────────────────────────


async def test_five_in_a_row_wins_and_shows_the_line(client):
    one, two = await game(client)
    match = match_of(client)
    me = match.turn
    for col in range(five.WIN):
        match.turn = me                    # соперник ходит мимо, очередь возвращаем
        await one.send(t="move", row=2, col=col)
        if col < five.WIN - 1:
            await state_where(one, lambda s: len(s["cells"]) > col)

    win = await one.recv("end")
    loss = await two.recv("end")
    assert win["game"] == "five" and win["outcome"] == "win"
    assert win["reason"] == "line" and len(win["win"]) == five.WIN
    assert loss["outcome"] == "loss"
    assert win["moves"] == five.WIN and win["line"] == five.WIN
    assert len(win["cells"]) == five.WIN, "поле уезжает на экран итога целиком"
    assert win["delta"] > 0 > loss["delta"]

    db = client.hub.db
    assert storage.standing(db, me, "five")["wins"] == 1
    assert storage.standing(db, me, "sea") is None, "море тут ни при чём"
    assert storage.place_of(db, me, "five") == 1


async def test_leaving_hands_the_win_over(client):
    one, two = await game(client)
    await one.send(t="move", row=4, col=4)
    await state_where(two, lambda s: s["cells"])
    await one.send(t="leave")
    end = await two.recv("end", timeout=5)
    assert end["outcome"] == "win" and end["reason"] == "left"


# ── робот ───────────────────────────────────────────────────────────────────


async def test_the_robot_plays_five_too(client):
    player, _ = await join(client, 1, "Алиджон")
    await player.send(t="play_bot", game="five")
    found = await player.recv("found")
    assert found["game"] == "five" and found["opp"]["name"]
    await state_where(player, lambda s: s["state"] == "running")

    # Отдаём ход роботу — он подумает и сходит сам.
    client.hub.match_for(1).turn = -1
    state = await state_where(player, lambda s: s["cells"], tries=900)
    assert len(state["cells"]) == 1 and state["my_turn"] is True


async def test_the_leaderboard_knows_the_new_game(client):
    db = client.hub.db
    storage.touch_player(db, 5, "Крестик")
    storage.apply_result(db, 5, "five", new_rating=1150, outcome="win",
                         correct=9, wrong=0, best_streak=1)
    top = await (await client.get("/api/top?game=five")).json()
    assert top["game"] == "five" and top["top"][0]["name"] == "Крестик"

    _, ready = await join(client, 5, "Крестик")
    assert ready["profile"]["standings"]["five"]["place"] == 1
    assert ready["game_info"]["five"] == {"math": False, "duration": 0}
