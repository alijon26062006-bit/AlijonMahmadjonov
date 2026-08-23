"""Посев по силе: сильнейшие доходят до финала, а не выбивают друг друга."""
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import bracket
from core.engine import BattleEngine
from core.models import Player, Slot
from storage.db import connect
from storage.repo import Repo
from storage.settings import Settings
from tests.test_engine import FakeBot, enqueue_users, make_config


def rank(players):
    """Список ников в порядке, в котором они лежат."""
    return [p.nickname for p in players]


SIXTEEN = [Player(i, f"#{i}") for i in range(1, 17)]
# сила ровно по номеру: #1 сильнейший
STRENGTH = {i: 1.0 - i / 100 for i in range(1, 17)}


# --------------------------------------------------------------- змейка

def test_the_strongest_are_split_across_groups():
    groups = bracket.snake_groups(SIXTEEN)

    assert [rank(g) for g in groups] == [
        ["#1", "#8", "#9", "#16"],
        ["#2", "#7", "#10", "#15"],
        ["#3", "#6", "#11", "#14"],
        ["#4", "#5", "#12", "#13"],
    ]


def test_the_four_strongest_all_reach_the_final():
    """Главное свойство посева ради которого он и нужен."""
    groups = bracket.snake_groups(SIXTEEN)
    best = [min(g, key=lambda p: p.user_id).nickname for g in groups]

    assert sorted(best) == ["#1", "#2", "#3", "#4"]


def test_grouping_in_a_row_would_burn_them():
    """Для сравнения: подряд по силе трое сильнейших вылетают во 2 раунде."""
    groups = bracket.split_groups(SIXTEEN)
    best = [min(g, key=lambda p: p.user_id).nickname for g in groups]

    assert best == ["#1", "#5", "#9", "#13"]


def test_an_uneven_count_leaves_no_lonely_group():
    for count in range(5, 30):
        players = [Player(i, f"#{i}") for i in range(count)]
        groups = bracket.snake_groups(players)

        assert sum(len(g) for g in groups) == count, "никто не потерялся"
        assert all(len(g) >= 2 for g in groups), f"группа из одного при {count}"


def test_a_small_field_stays_one_group():
    assert len(bracket.snake_groups(SIXTEEN[:4])) == 1


# ------------------------------------------------------ сортировка по силе

def test_the_strong_go_first():
    ordered = bracket.by_strength(SIXTEEN, STRENGTH, random.Random(1))
    assert rank(ordered) == [f"#{i}" for i in range(1, 17)]


def test_equal_strength_is_shuffled():
    """Одинаковая сила не должна давать преимущество по порядку в списке."""
    flat = {i: 0.5 for i in range(1, 17)}
    seen = {
        tuple(rank(bracket.by_strength(SIXTEEN, flat, random.Random(seed))))
        for seed in range(10)
    }
    assert len(seen) > 1


def test_without_strength_it_is_a_draw():
    seen = {
        tuple(rank(bracket.by_strength(SIXTEEN, None, random.Random(seed))))
        for seed in range(10)
    }
    assert len(seen) > 1


def test_the_first_round_is_always_a_draw():
    """В первом раунде силы ещё никто не показал — только жребий."""
    seen = set()
    for seed in range(10):
        plan = bracket.plan_round(SIXTEEN, 1, random.Random(seed), STRENGTH)
        seen.add(tuple(rank(plan.groups[0])))
    assert len(seen) > 1


def test_the_second_round_uses_the_snake():
    plan = bracket.plan_round(SIXTEEN, 2, random.Random(1), STRENGTH)
    assert rank(plan.groups[0]) == ["#1", "#8", "#9", "#16"]


def test_without_strength_the_second_round_is_a_draw():
    plan = bracket.plan_round(SIXTEEN, 2, random.Random(1))
    assert rank(plan.groups[0]) != ["#1", "#8", "#9", "#16"]


# ------------------------------------------------------- сила из базы

@pytest.fixture()
def env(tmp_path):
    path = str(tmp_path / "seed.db")
    repo = Repo(connect(path))
    config = make_config(db_path=path)
    settings = Settings(repo.conn, config)
    settings.bootstrap()
    return repo, config, settings, BattleEngine(FakeBot(), repo, config, settings=settings)


def closed_match(repo, battle_id, players_votes, round_no=1, number=1):
    from datetime import datetime, timedelta

    from config import MSK

    deadline = datetime.now(MSK) + timedelta(hours=1)
    players = [Player(uid, f"n{uid}") for uid, _ in players_votes]
    match_id = repo.create_match(
        battle_id, round_no, number, players,
        advance=1, is_final=False, deadline=deadline,
    )
    ranking = [
        Slot(uid, f"n{uid}", votes, place)
        for place, (uid, votes) in enumerate(
            sorted(players_votes, key=lambda pair: -pair[1]), start=1
        )
    ]
    for slot in ranking:
        repo.conn.execute(
            "UPDATE match_slots SET votes = ? WHERE match_id = ? AND user_id = ?",
            (slot.votes, match_id, slot.user_id),
        )
    repo.conn.commit()
    repo.close_match(match_id, ranking)
    return match_id


def test_share_beats_raw_votes(env):
    """Победа 3:0 сильнее победы 20:19, хотя голосов там меньше."""
    repo, _, _, _ = env
    for uid in (1, 2, 3, 4):
        repo.upsert_user(uid, f"n{uid}", "N")
    battle_id = repo.create_battle(__import__("datetime").datetime.now())

    closed_match(repo, battle_id, [(1, 3), (2, 0)], number=1)
    closed_match(repo, battle_id, [(3, 20), (4, 19)], number=2)

    strength = repo.player_strength(battle_id)
    assert strength[1] == 1.0, "разгром — полная доля"
    assert 0.5 < strength[3] < 0.6, "почти ничья — доля около половины"
    assert strength[1] > strength[3], "разгромивший сильнее вымучившего"


def test_a_bye_is_neutral(env):
    repo, _, _, _ = env
    for uid in (1, 2, 3):
        repo.upsert_user(uid, f"n{uid}", "N")
    battle_id = repo.create_battle(__import__("datetime").datetime.now())
    repo.add_participant(battle_id, 3, "n3")
    closed_match(repo, battle_id, [(1, 5), (2, 1)])

    strength = repo.player_strength(battle_id)
    assert strength[3] == 0.5, "прошедший без боя ничего не доказал"


def test_a_match_without_votes_is_neutral(env):
    repo, _, _, _ = env
    for uid in (1, 2):
        repo.upsert_user(uid, f"n{uid}", "N")
    battle_id = repo.create_battle(__import__("datetime").datetime.now())
    closed_match(repo, battle_id, [(1, 0), (2, 0)])

    strength = repo.player_strength(battle_id)
    assert strength[1] == strength[2] == 0.5


# ------------------------------------------------------------ настройка

def test_the_seeding_is_on_by_default(env):
    _, _, settings, _ = env
    assert settings.get("seeding") == "snake"


def test_the_admin_can_switch_to_a_draw():
    from services import panel_ui

    assert panel_ui.SEEDING_NEXT["snake"] == "random"
    assert panel_ui.SEEDING_NEXT["random"] == "snake"


@pytest.mark.asyncio
async def test_a_whole_battle_runs_with_seeding(tmp_path):
    """Сквозная проверка: с посевом батл доигрывается до конца."""
    path = str(tmp_path / "flow.db")
    repo = Repo(connect(path))
    config = make_config(db_path=path, min_participants=4)
    settings = Settings(repo.conn, config)
    settings.bootstrap()
    engine = BattleEngine(FakeBot(), repo, config, settings=settings)

    await enqueue_users(engine, repo, 16)
    await engine.create_from_queue()
    rounds = 0
    while repo.current_battle() is not None and rounds < 10:
        battle = repo.current_battle()
        for match in repo.open_matches(1, int(battle["round_no"])):
            slots = repo.match_slots(int(match["id"]))
            for index, slot in enumerate(slots):
                repo.conn.execute(
                    "UPDATE match_slots SET votes = ? WHERE match_id = ? AND user_id = ?",
                    (10 - index, int(match["id"]), slot.user_id),
                )
        repo.conn.commit()
        await engine.close_round(force=True)
        rounds += 1

    assert repo.current_battle() is None, "батл должен дойти до финала"
    assert rounds <= 5
