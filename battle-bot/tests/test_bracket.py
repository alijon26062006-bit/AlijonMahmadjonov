import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import bracket
from core.models import Player, Slot


def players(n: int) -> list[Player]:
    return [Player(user_id=i, nickname=f"nick{i}") for i in range(1, n + 1)]


def test_rolling_pairs_even():
    pairs, leftover = bracket.rolling_pairs(players(6))
    assert len(pairs) == 3
    assert all(len(p) == 2 for p in pairs)
    assert leftover == []


def test_rolling_pairs_odd_leaves_one_waiting():
    pairs, leftover = bracket.rolling_pairs(players(7))
    assert len(pairs) == 3
    assert len(leftover) == 1
    assert leftover[0].user_id == 7


def test_first_round_is_one_vs_one():
    plan = bracket.plan_round(players(16), round_no=1, rng=random.Random(0))
    assert not plan.is_final
    assert plan.match_count == 8
    assert all(len(g) == 2 for g in plan.groups)


def test_odd_first_round_gives_a_bye():
    plan = bracket.plan_round(players(9), round_no=1, rng=random.Random(0))
    assert plan.match_count == 4
    assert len(plan.byes) == 1


def test_second_round_groups_of_four():
    plan = bracket.plan_round(players(16), round_no=2, rng=random.Random(0))
    assert plan.match_count == 4
    assert all(len(g) == 4 for g in plan.groups)
    assert bracket.base_advance(plan) == 1


def test_few_groups_advance_two_so_the_final_has_prizes():
    plan = bracket.plan_round(players(8), round_no=2, rng=random.Random(0))
    assert plan.match_count == 2
    assert bracket.base_advance(plan) == 2


def test_final_when_seven_or_fewer_remain():
    plan = bracket.plan_round(players(7), round_no=3, rng=random.Random(0))
    assert plan.is_final
    assert plan.match_count == 1
    assert len(plan.groups[0]) == 7


def test_single_leftover_is_merged_not_left_alone():
    groups = bracket.split_groups(players(9))
    assert [len(g) for g in groups] == [4, 5]
    assert all(len(g) >= 2 for g in groups)


def test_resolve_match_picks_the_leader():
    slots = [Slot(1, "a", votes=5), Slot(2, "b", votes=9), Slot(3, "c", votes=1)]
    result = bracket.resolve_match(10, slots, advance=1, rng=random.Random(0))
    assert result.winners == [2]
    assert set(result.losers) == {1, 3}
    assert result.ranking[0].position == 1
    assert not result.tie_broken


def test_resolve_match_marks_a_coin_flip():
    slots = [Slot(1, "a", votes=3), Slot(2, "b", votes=3)]
    result = bracket.resolve_match(11, slots, advance=1, rng=random.Random(1))
    assert len(result.winners) == 1
    assert result.tie_broken


def test_final_ranking_keeps_everyone_and_awards_places():
    slots = [Slot(i, f"n{i}", votes=10 - i) for i in range(1, 5)]
    result = bracket.resolve_match(12, slots, advance=0, rng=random.Random(0))
    assert result.winners == []
    assert [s.user_id for s in result.ranking] == [1, 2, 3, 4]
    assert [s.position for s in result.ranking] == [1, 2, 3, 4]


def test_at_least_one_participant_is_eliminated_per_group():
    assert bracket.advance_count(group_size=2, base=2) == 1
    assert bracket.advance_count(group_size=4, base=2) == 2
    assert bracket.advance_count(group_size=3, base=1) == 1


@pytest.mark.parametrize("count", [4, 5, 8, 9, 16, 17, 32, 33, 64, 100, 257])
def test_every_battle_size_converges_to_a_final(count):
    stages = bracket.project_rounds(count)
    assert stages[0] == count
    assert stages[-1] == 1
    assert len(stages) < 20, "сетка должна сходиться, а не крутиться бесконечно"
    for earlier, later in zip(stages, stages[1:]):
        assert later <= earlier, f"раунд не сократил число участников: {stages}"


@pytest.mark.parametrize("count", [8, 12, 16, 20, 33, 64, 100])
def test_final_has_enough_players_for_three_prizes(count):
    stages = bracket.project_rounds(count)
    finalists = stages[-2]
    assert finalists >= 3, f"в финале всего {finalists} участников: {stages}"


def test_full_battle_run_ends_with_one_champion():
    rng = random.Random(42)
    alive = players(37)
    round_no = 1
    guard = 0
    while True:
        guard += 1
        assert guard < 20
        plan = bracket.plan_round(alive, round_no, rng)
        advance = bracket.base_advance(plan)
        survivors: list[Player] = list(plan.byes)
        for match_id, group in enumerate(plan.groups):
            slots = [Slot(p.user_id, p.nickname, votes=rng.randint(0, 50)) for p in group]
            result = bracket.resolve_match(match_id, slots, advance, rng)
            if plan.is_final:
                champion = result.ranking[0]
                assert champion.position == 1
                assert len(result.ranking) == len(group)
                return
            by_id = {p.user_id: p for p in group}
            survivors.extend(by_id[uid] for uid in result.winners)
        assert survivors, "раунд не должен обнулять сетку"
        alive = survivors
        round_no += 1
