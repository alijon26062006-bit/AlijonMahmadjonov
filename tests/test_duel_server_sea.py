"""Морской бой по WebSocket: расстановка, выстрелы, итог — всё через сервер."""

import asyncio
import time

import pytest

from duel import game, sea, storage
from duel.sea_match import PLACE_SEC, STATE_PLACING
from tests.test_duel_server import client, join, respond  # noqa: F401
from tests.test_duel_server import state_where as _state_where


async def state_where(player, check, tries=600):
    """Во время расстановки состояние летит каждый такт — ждём дольше."""
    return await _state_where(player, check, tries)


async def meet(client, level="normal"):
    """Два игрока находят друг друга в морском бою."""
    one, _ = await join(client, 1, "Первый")
    two, _ = await join(client, 2, "Второй")
    for player in (one, two):
        await player.send(t="find", game="sea", level=level)
    return one, two, await one.recv("found"), await two.recv("found")


async def place_both(client, one, two):
    for player in (one, two):
        await player.send(t="sea_random")
        layout = (await player.recv("sea_layout"))["layout"]
        await player.send(t="place", layout=layout)
        placed = await player.recv("placed")
        assert placed["ok"], placed
    return await one.recv("task"), await two.recv("task")


async def earn_shell(player, hub, user_id, task_id):
    await respond(player, hub, user_id, task_id)
    answer = await player.recv("ans")
    assert answer["correct"] and answer["shells"] >= 1
    return answer


def enemy_cells(hub, victim_id):
    board = hub.match_for(victim_id).side(victim_id).board
    return [cell for ship in board.ships for cell in ship.cells]


# ── поиск и расстановка ─────────────────────────────────────────────────────


async def test_sea_players_meet_and_start_with_placement(client):
    one, two, found_one, found_two = await meet(client)
    assert found_one["game"] == "sea" and found_two["game"] == "sea"
    assert found_one["opp"]["name"] == "Второй"

    state = await one.recv("state")
    assert state["game"] == "sea" and state["state"] == STATE_PLACING
    assert 0 < state["place_left_ms"] <= PLACE_SEC * 1000
    assert state["me"]["placed"] is False and state["opp"]["placed"] is False
    await one.silent("task", timeout=0.3)


async def test_sea_and_rope_seekers_never_meet(client):
    one, _ = await join(client, 1, "Море")
    two, _ = await join(client, 2, "Канат")
    await one.send(t="find", game="sea")
    await two.send(t="find", game="rope")
    await one.silent("found", timeout=0.8)
    await two.silent("found", timeout=0.2)


async def test_server_hands_out_a_valid_random_layout(client):
    one, two, _, _ = await meet(client)
    await one.send(t="sea_random")
    layout = (await one.recv("sea_layout"))["layout"]
    ships = sea.validate(layout)
    assert sorted(len(ship.cells) for ship in ships) == sorted(sea.FLEET)


async def test_a_bad_layout_is_refused_with_a_reason(client):
    one, two, _, _ = await meet(client)
    await one.send(t="place", layout=[{"row": 0, "col": 0, "size": 3}])
    placed = await one.recv("placed")
    assert placed["ok"] is False and placed["error"]
    state = await state_where(one, lambda s: s["state"] == STATE_PLACING)
    assert state["me"]["placed"] is False


async def test_the_opponent_sees_that_you_are_ready(client):
    one, two, _, _ = await meet(client)
    await one.send(t="sea_random")
    layout = (await one.recv("sea_layout"))["layout"]
    await one.send(t="place", layout=layout)
    assert (await one.recv("placed"))["ok"]
    state = await state_where(two, lambda s: s["opp"]["placed"])
    assert state["state"] == STATE_PLACING, "один готов — бой ещё не начался"
    mine = await state_where(one, lambda s: s["me"]["placed"])
    assert mine["me"]["board"] and len(mine["me"]["board"]["ships"]) == len(sea.FLEET)


async def test_when_both_are_ready_the_battle_begins(client):
    one, two, _, _ = await meet(client)
    task_one, task_two = await place_both(client, one, two)
    assert task_one["id"] and task_two["id"]
    state = await state_where(one, lambda s: s["state"] == game.STATE_RUNNING)
    assert state["me"]["shells"] == 0 and state["enemy"]["alive"] == len(sea.FLEET)


async def test_the_slow_one_gets_ships_placed_for_him(client, monkeypatch):
    one, two, _, _ = await meet(client)
    match = client.hub.match_for(1)
    match.place_deadline = time.monotonic() + 0.2
    await one.recv("task", timeout=3)
    assert match.side(1).board is not None and match.side(2).board is not None


# ── бой ─────────────────────────────────────────────────────────────────────


async def test_a_shot_needs_a_shell(client):
    one, two, _, _ = await meet(client)
    await place_both(client, one, two)
    await one.send(t="fire", row=0, col=0)
    shot = await one.recv("shot")
    assert shot["result"] == "no_shells"
    await two.silent("incoming", timeout=0.3)


async def test_a_correct_answer_loads_a_shell_and_the_shot_lands(client):
    one, two, task_one, _ = await meet(client)
    task_one, _ = await place_both(client, one, two)
    await earn_shell(one, client.hub, 1, task_one["id"])

    row, col = enemy_cells(client.hub, 2)[0]
    await one.send(t="fire", row=row, col=col)
    shot = await one.recv("shot")
    assert shot["result"] in ("hit", "sunk") and shot["cell"] == [row, col]
    assert shot["shells"] == 0

    incoming = await two.recv("incoming")
    assert incoming["result"] == shot["result"] and incoming["cell"] == [row, col]

    state = await state_where(one, lambda s: s["enemy"]["hits"])
    assert [row, col] in state["enemy"]["hits"]
    theirs = await state_where(two, lambda s: s["opp"]["last"] == [row, col])
    assert [row, col] in theirs["me"]["board"]["hits"]


async def test_a_miss_is_marked_and_costs_the_shell(client):
    one, two, _, _ = await meet(client)
    task_one, _ = await place_both(client, one, two)
    await earn_shell(one, client.hub, 1, task_one["id"])
    taken = set(enemy_cells(client.hub, 2))
    row, col = next(
        (r, c) for r in range(sea.SIZE) for c in range(sea.SIZE) if (r, c) not in taken
    )
    await one.send(t="fire", row=row, col=col)
    shot = await one.recv("shot")
    assert shot["result"] == "miss" and shot["shells"] == 0
    state = await state_where(one, lambda s: s["enemy"]["misses"])
    assert [row, col] in state["enemy"]["misses"]


async def test_sinking_the_whole_fleet_wins(client):
    one, two, _, _ = await meet(client)
    task_one, _ = await place_both(client, one, two)
    match = client.hub.match_for(1)
    cells = enemy_cells(client.hub, 2)
    match.side(1).shells = len(cells)  # чтобы не решать девять примеров
    for row, col in cells:
        await one.send(t="fire", row=row, col=col)
        shot = await one.recv("shot")
        assert shot["result"] in ("hit", "sunk")

    win = await one.recv("end")
    loss = await two.recv("end")
    assert win["game"] == "sea" and win["outcome"] == "win" and win["reason"] == "fleet"
    assert loss["outcome"] == "loss" and loss["opp_sunk"] == len(sea.FLEET)
    assert win["sunk"] == len(sea.FLEET) and win["hits"] == len(cells)
    assert win["enemy_fleet"], "после боя показываем, где стоял флот врага"
    assert win["delta"] > 0 > loss["delta"]

    db = client.hub.db
    assert storage.standing(db, 1, "sea")["wins"] == 1
    assert storage.standing(db, 1, "rope") is None, "канат тут ни при чём"
    assert storage.place_of(db, 1, "sea") == 1


async def test_time_runs_out_and_the_better_gunner_wins(client):
    one, two, _, _ = await meet(client)
    task_one, _ = await place_both(client, one, two)
    match = client.hub.match_for(1)
    match.side(1).shells = 1
    row, col = enemy_cells(client.hub, 2)[0]
    await one.send(t="fire", row=row, col=col)
    await one.recv("shot")
    match.deadline = time.monotonic() + 0.2
    win = await one.recv("end", timeout=3)
    loss = await two.recv("end", timeout=3)
    assert win["outcome"] == "win" and win["reason"] == "time"
    assert loss["outcome"] == "loss"


async def test_leaving_during_placement_costs_no_rating(client):
    one, two, _, _ = await meet(client)
    await one.send(t="leave")
    end = await two.recv("end", timeout=3)
    assert end["rated"] is False and end["delta"] == 0
    assert storage.standing(client.hub.db, 2, "sea") is None


# ── робот, таблица, чат ─────────────────────────────────────────────────────


async def test_the_robot_plays_the_sea_too(client):
    player, _ = await join(client, 1, "Алиджон")
    await player.send(t="play_bot", game="sea", level="easy")
    found = await player.recv("found")
    assert found["game"] == "sea" and found["opp"]["name"]
    state = await state_where(player, lambda s: s["opp"]["placed"])
    assert state["state"] == STATE_PLACING, "робот расставился сразу и ждёт человека"

    await player.send(t="sea_random")
    layout = (await player.recv("sea_layout"))["layout"]
    await player.send(t="place", layout=layout)
    assert (await player.recv("placed"))["ok"]
    await player.recv("task")
    incoming = await player.recv("incoming", timeout=20)
    assert incoming["result"] in ("miss", "hit", "sunk"), "робот решает и стреляет сам"


async def test_leaderboard_is_kept_per_game(client):
    db = client.hub.db
    storage.touch_player(db, 7, "Морячка")
    storage.apply_result(db, 7, "sea", new_rating=1200, outcome="win", correct=9, wrong=0, best_streak=9)
    storage.touch_player(db, 8, "Канатчик")
    storage.apply_result(db, 8, "rope", new_rating=1150, outcome="win", correct=9, wrong=0, best_streak=9)

    sea_top = await (await client.get("/api/top?game=sea")).json()
    rope_top = await (await client.get("/api/top?game=rope")).json()
    assert sea_top["top"][0]["name"] == "Морячка"
    assert rope_top["top"][0]["name"] == "Канатчик"
    assert [r["name"] for r in sea_top["top"] if r["games"]] == ["Морячка"]

    player, ready = await join(client, 7, "Морячка")
    assert ready["profile"]["standings"]["sea"]["place"] == 1
    assert ready["profile"]["standings"]["rope"]["games"] == 0


async def test_a_chat_call_can_be_for_the_sea(client):
    room = client.hub.open_group_room(1, "Алиджон", -100500, game="sea")
    assert room.host.game == "sea" and room.host.duration == 0
    guest, _ = await join(client, 2, "Гость")
    await guest.send(t="peek", code=room.code)
    invite = await guest.recv("invite")
    assert invite["game"] == "sea" and invite["duration"] == 0
