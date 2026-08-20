import sys
from datetime import datetime, timedelta

from config import MSK
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.models import BattleStatus, Player, Slot, VoteResult, VoteSource
from storage.db import connect
from storage.repo import Repo


@pytest.fixture()
def repo(tmp_path) -> Repo:
    return Repo(connect(str(tmp_path / "test.db")))


def make_users(repo: Repo, count: int) -> list[Player]:
    players = []
    for i in range(1, count + 1):
        repo.upsert_user(i, f"nick{i}", f"Name{i}")
        players.append(Player(i, f"nick{i}"))
    return players


def test_battle_lifecycle(repo: Repo):
    deadline = datetime.now(MSK) + timedelta(hours=1)
    assert repo.current_battle() is None
    battle_id = repo.create_battle(deadline)
    assert repo.current_battle()["id"] == battle_id
    repo.set_battle_status(battle_id, BattleStatus.FINISHED)
    assert repo.current_battle() is None


def test_participant_cannot_join_twice(repo: Repo):
    make_users(repo, 1)
    battle_id = repo.create_battle(datetime.now(MSK))
    assert repo.add_participant(battle_id, 1, "nick1") is True
    assert repo.add_participant(battle_id, 1, "nick1") is False
    assert repo.participant_count(battle_id) == 1


def test_unassigned_players_only_lists_those_without_a_match(repo: Repo):
    players = make_users(repo, 3)
    battle_id = repo.create_battle(datetime.now(MSK))
    for player in players:
        repo.add_participant(battle_id, player.user_id, player.nickname)

    assert [p.user_id for p in repo.unassigned_players(battle_id)] == [1, 2, 3]
    repo.create_match(battle_id, 1, 1, players[:2], advance=1, is_final=False,
                      deadline=datetime.now(MSK) + timedelta(hours=1))
    assert [p.user_id for p in repo.unassigned_players(battle_id)] == [3]


def test_one_free_vote_per_match(repo: Repo):
    players = make_users(repo, 2)
    battle_id = repo.create_battle(datetime.now(MSK))
    match_id = repo.create_match(battle_id, 1, 1, players, advance=1, is_final=False,
                                 deadline=datetime.now(MSK) + timedelta(hours=1))

    assert repo.add_vote(match_id, 99, 1, VoteSource.FREE) is VoteResult.ACCEPTED
    assert repo.has_free_vote(match_id, 99) is True
    # второй бесплатный голос того же человека в этот матч не проходит
    assert repo.add_vote(match_id, 99, 2, VoteSource.FREE) is VoteResult.DUPLICATE

    slots = {s.user_id: s.votes for s in repo.match_slots(match_id)}
    assert slots == {1: 1, 2: 0}


def test_paid_votes_stack_on_top_of_the_free_one(repo: Repo):
    players = make_users(repo, 2)
    battle_id = repo.create_battle(datetime.now(MSK))
    match_id = repo.create_match(battle_id, 1, 1, players, advance=1, is_final=False,
                                 deadline=datetime.now(MSK) + timedelta(hours=1))

    repo.add_vote(match_id, 99, 1, VoteSource.FREE)
    assert repo.add_vote(match_id, 99, 1, VoteSource.PAID) is VoteResult.ACCEPTED
    assert repo.add_vote(match_id, 99, 1, VoteSource.PAID) is VoteResult.ACCEPTED

    slots = {s.user_id: s.votes for s in repo.match_slots(match_id)}
    assert slots[1] == 3
    assert len(repo.vote_log(match_id)) == 3


def test_vote_balance_cannot_go_negative(repo: Repo):
    make_users(repo, 1)
    assert repo.spend_vote(1) is False
    repo.add_votes(1, 2)
    assert repo.spend_vote(1) is True
    assert repo.spend_vote(1) is True
    assert repo.spend_vote(1) is False
    assert repo.vote_balance(1) == 0


def test_payment_is_recorded_once(repo: Repo):
    make_users(repo, 1)
    assert repo.record_payment(1, "charge-1", stars=60, votes=5) is True
    assert repo.record_payment(1, "charge-1", stars=60, votes=5) is False
    assert len(repo.payment_history(1)) == 1


def test_eliminating_participants_shrinks_the_alive_list(repo: Repo):
    players = make_users(repo, 4)
    battle_id = repo.create_battle(datetime.now(MSK))
    for player in players:
        repo.add_participant(battle_id, player.user_id, player.nickname)

    repo.eliminate(battle_id, [2, 4])
    assert [p.user_id for p in repo.alive_players(battle_id)] == [1, 3]


def test_close_match_writes_positions(repo: Repo):
    players = make_users(repo, 2)
    battle_id = repo.create_battle(datetime.now(MSK))
    match_id = repo.create_match(battle_id, 1, 1, players, advance=1, is_final=False,
                                 deadline=datetime.now(MSK) + timedelta(hours=1))

    ranking = [Slot(2, "nick2", 5, 1), Slot(1, "nick1", 3, 2)]
    repo.close_match(match_id, ranking)

    assert repo.get_match(match_id)["status"] == "closed"
    positions = {s.user_id: s.position for s in repo.match_slots(match_id)}
    assert positions == {1: 2, 2: 1}
    assert repo.open_matches(battle_id, 1) == []


def test_leaderboard_ranks_champions_first(repo: Repo):
    make_users(repo, 3)
    battle_id = repo.create_battle(datetime.now(MSK))
    for uid in (1, 2, 3):
        repo.add_participant(battle_id, uid, f"nick{uid}")
    repo.bump_wins([1, 2, 2])
    repo.record_place(2, 1)
    repo.record_place(1, 3)

    top = repo.leaderboard()
    assert top[0]["user_id"] == 2
    assert top[0]["titles"] == 1
    assert repo.stats_for(1)["best_place"] == 3


def test_refund_takes_back_the_granted_votes(repo: Repo):
    make_users(repo, 1)
    repo.record_payment(1, "charge-9", stars=60, votes=5)
    repo.add_votes(1, 5)

    assert repo.mark_refunded("charge-9") is True
    assert repo.vote_balance(1) == 0
    assert repo.payment_by_charge("charge-9")["status"] == "refunded"
    # повторный возврат ничего не делает
    assert repo.mark_refunded("charge-9") is False


def test_refund_never_pushes_the_balance_below_zero(repo: Repo):
    make_users(repo, 1)
    repo.record_payment(1, "charge-8", stars=60, votes=5)
    repo.add_votes(1, 5)
    for _ in range(4):
        repo.spend_vote(1)

    repo.mark_refunded("charge-8")
    assert repo.vote_balance(1) == 0
