"""Проверка накрутки: находит подозрительное, не обвиняет честных."""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import MSK
from core.models import Player, VoteSource
from storage.db import connect
from storage.repo import Repo


@pytest.fixture()
def repo(tmp_path) -> Repo:
    store = Repo(connect(str(tmp_path / "fraud.db")))
    for user_id in range(1, 60):
        store.upsert_user(user_id, f"n{user_id}", "N")
    return store


def open_match(repo: Repo, a: int = 1, b: int = 2) -> int:
    deadline = datetime.now(MSK) + timedelta(hours=2)
    battle_id = repo.create_battle(deadline)
    return repo.create_match(
        battle_id, 1, 1, [Player(a, f"n{a}"), Player(b, f"n{b}")],
        advance=1, is_final=False, deadline=deadline,
    )


# ------------------------------------------- голоса своих приглашённых

def test_votes_from_your_own_invitees_are_flagged(repo):
    """Нагнал знакомых по своей ссылке — самый весомый признак."""
    match_id = open_match(repo)
    for friend in range(10, 16):
        repo.record_referral(friend, 1)
        repo.reward_referral(friend, 1)
        repo.add_vote(match_id, friend, 1, VoteSource.FREE)

    flagged = repo.self_referral_votes()

    assert len(flagged) == 1
    assert flagged[0]["user_id"] == 1
    assert flagged[0]["own_votes"] == 6
    assert flagged[0]["all_votes"] == 6, "видно и общее число голосов"


def test_a_couple_of_invited_friends_is_not_suspicious(repo):
    """У всех есть друзья — придираться к двум голосам нельзя."""
    match_id = open_match(repo)
    for friend in (10, 11):
        repo.record_referral(friend, 1)
        repo.add_vote(match_id, friend, 1, VoteSource.FREE)

    assert repo.self_referral_votes() == []


def test_votes_from_strangers_are_not_flagged(repo):
    match_id = open_match(repo)
    for voter in range(20, 30):
        repo.add_vote(match_id, voter, 1, VoteSource.FREE)

    assert repo.self_referral_votes() == []


# ------------------------------------------------------------ всплески

def test_a_burst_of_votes_is_noticed(repo):
    match_id = open_match(repo)
    for voter in range(20, 32):
        repo.add_vote(match_id, voter, 1, VoteSource.FREE)

    bursts = repo.vote_bursts(threshold=8)

    assert bursts and bursts[0]["target_id"] == 1
    assert bursts[0]["burst"] >= 8


def test_a_calm_match_has_no_bursts(repo):
    match_id = open_match(repo)
    for voter in range(20, 25):
        repo.add_vote(match_id, voter, 1, VoteSource.FREE)

    assert repo.vote_bursts(threshold=8) == []


# ------------------------------------------- одни и те же голосующие

def test_someone_who_only_ever_votes_for_one_person_is_listed(repo):
    for number in range(4):
        match_id = open_match(repo, a=1, b=2 + number)
        repo.add_vote(match_id, 50, 1, VoteSource.FREE)

    loyal = repo.loyal_voters(min_votes=4)

    assert loyal and loyal[0]["voter_id"] == 50
    assert loyal[0]["targets"] == 1 and loyal[0]["votes"] == 4


def test_someone_who_votes_for_different_people_is_left_alone(repo):
    for number in range(4):
        match_id = open_match(repo, a=1 + number, b=20 + number)
        repo.add_vote(match_id, 50, 1 + number, VoteSource.FREE)

    assert repo.loyal_voters(min_votes=2) == []


# --------------------------------------------------- свежие аккаунты

def test_votes_from_brand_new_accounts_are_flagged(repo):
    """Аккаунты, заведённые прямо перед голосованием, — типичная ферма."""
    match_id = open_match(repo)
    for voter in range(40, 45):
        repo.add_vote(match_id, voter, 1, VoteSource.FREE)

    flagged = repo.fresh_account_votes(minutes=10)

    assert flagged and flagged[0]["target_id"] == 1
    assert flagged[0]["votes"] == 5


def test_old_accounts_are_not_flagged(repo):
    match_id = open_match(repo)
    repo.conn.execute(
        "UPDATE users SET created_at = datetime('now', '-30 day') WHERE user_id >= 40"
    )
    repo.conn.commit()
    for voter in range(40, 45):
        repo.add_vote(match_id, voter, 1, VoteSource.FREE)

    assert repo.fresh_account_votes(minutes=10) == []


# ------------------------------------------------------------- экран

def test_a_clean_bot_reports_nothing(repo):
    from handlers.panel import _fraud_signals
    from services import panel_ui

    text, markup = panel_ui.fraud(_fraud_signals(repo))

    assert "Ничего подозрительного" in text
    assert markup.inline_keyboard


def test_the_screen_lists_what_it_found(repo):
    from handlers.panel import _fraud_signals
    from services import panel_ui

    match_id = open_match(repo)
    for friend in range(10, 16):
        repo.record_referral(friend, 1)
        repo.add_vote(match_id, friend, 1, VoteSource.FREE)

    text, _ = panel_ui.fraud(_fraud_signals(repo))

    assert "Голосуют свои приглашённые" in text
    assert "@n1" in text
    assert "не приговор" in text, "админ должен понимать, что это подсказка"
