"""Прозрачность голосов: видно, сколько своих, а сколько куплено."""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.models import Player, VoteSource
from handlers.voting import _pick_vote_source
from services import panel_ui, texts
from storage.db import connect
from storage.repo import Repo
from storage.settings import Settings
from tests.test_engine import make_config

ONE, TWO, VOTER = 1, 2, 500


@pytest.fixture()
def env(tmp_path):
    path = str(tmp_path / "clear.db")
    repo = Repo(connect(path))
    config = make_config(db_path=path)
    settings = Settings(repo.conn, config)
    settings.bootstrap()
    for user_id, name in ((ONE, "one"), (TWO, "two"), (VOTER, "voter")):
        repo.upsert_user(user_id, name, name)

    deadline = datetime.now() + timedelta(hours=2)
    battle_id = repo.create_battle(deadline)
    match_id = repo.create_match(
        battle_id=battle_id, round_no=1, number=1,
        players=[Player(ONE, "one"), Player(TWO, "two")],
        advance=1, is_final=False, deadline=deadline,
    )
    return repo, config, settings, match_id


# ------------------------------------------------------------- подсчёт

def test_free_and_paid_votes_are_counted_apart(env):
    repo, _, _, match_id = env
    repo.add_vote(match_id, VOTER, ONE, VoteSource.FREE)
    repo.add_vote(match_id, VOTER, ONE, VoteSource.PAID)
    repo.add_vote(match_id, VOTER, ONE, VoteSource.PAID)

    assert repo.vote_split(match_id)[ONE] == (1, 2)


def test_a_participant_without_votes_is_absent(env):
    repo, _, _, match_id = env
    repo.add_vote(match_id, VOTER, ONE, VoteSource.FREE)

    assert TWO not in repo.vote_split(match_id)


# ------------------------------------------------------------- показ

def test_the_screen_says_how_many_were_bought(env):
    from core.models import Slot

    body = texts.scoreboard([Slot(ONE, "one", 10)], split={ONE: (2, 8)})

    assert "своими: 2" in body and "купленными: 8" in body


def test_nothing_is_added_when_nobody_bought(env):
    from core.models import Slot

    body = texts.scoreboard([Slot(ONE, "one", 3)], split={ONE: (3, 0)})

    assert "купленными" not in body, "лишняя строка там, где покупок не было"


def test_the_result_post_shows_it_too():
    from core.models import Slot

    body = texts.channel_result(1, False, [Slot(ONE, "one", 9, 1)], False, {ONE: (1, 8)})

    assert "купленными: 8" in body


# --------------------------------------------- необязательный лимит

def test_bought_votes_are_unlimited_by_default(env):
    """Покупка голосов — заработок бота, по умолчанию ничего не ограничено."""
    repo, config, settings, match_id = env
    repo.add_votes(VOTER, 100)
    repo.add_vote(match_id, VOTER, ONE, VoteSource.FREE)

    for _ in range(10):
        source, _ = _pick_vote_source(repo, match_id, VOTER, config, settings)
        assert source is VoteSource.PAID
        repo.add_vote(match_id, VOTER, ONE, source)

    assert repo.vote_split(match_id)[ONE] == (1, 10)


def test_the_limit_stops_one_wallet_from_deciding(env):
    repo, config, settings, match_id = env
    settings.set("paid_votes_per_match", 3)
    repo.add_votes(VOTER, 100)
    repo.add_vote(match_id, VOTER, ONE, VoteSource.FREE)

    for _ in range(3):
        source, _ = _pick_vote_source(repo, match_id, VOTER, config, settings)
        repo.add_vote(match_id, VOTER, ONE, source)

    source, note = _pick_vote_source(repo, match_id, VOTER, config, settings)

    assert source is None
    assert "не больше 3" in note
    assert repo.vote_balance(VOTER) == 97, "лишний голос не списывается"


def test_the_limit_is_per_match_not_forever(env):
    """Лимит на пару: в другой паре голоса снова в силе."""
    repo, config, settings, match_id = env
    settings.set("paid_votes_per_match", 1)
    repo.add_votes(VOTER, 10)
    repo.add_vote(match_id, VOTER, ONE, VoteSource.FREE)
    repo.add_vote(match_id, VOTER, ONE, VoteSource.PAID)

    other = repo.create_match(
        battle_id=1, round_no=1, number=2,
        players=[Player(ONE, "one"), Player(TWO, "two")],
        advance=1, is_final=False, deadline=datetime.now() + timedelta(hours=2),
    )

    source, _ = _pick_vote_source(repo, other, VOTER, config, settings)
    assert source is VoteSource.PAID


def test_the_panel_shows_the_limit():
    text, markup = panel_ui.votes(5, True, (0, 0), "", "battle", 0)
    assert "сколько угодно" in text

    text, _ = panel_ui.votes(5, True, (0, 0), "", "battle", 3)
    assert "Купленных на одну пару: <b>3</b>" in text

    actions = [b.callback_data for row in markup.inline_keyboard for b in row]
    assert "p:edit:paid_votes_per_match" in actions
