"""Правила голосования: один голос на человека и ни одного после закрытия."""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import MSK
from core.engine import BattleEngine
from core.models import BattleStatus, Player, Slot, VoteResult, VoteSource
from storage.db import connect
from storage.repo import Repo
from tests.test_engine import FakeBot, join_users, make_config


@pytest.fixture()
def env(tmp_path):
    path = str(tmp_path / "rules.db")
    repo = Repo(connect(path))
    config = make_config(db_path=path)
    return repo, config, BattleEngine(FakeBot(), repo, config)


def open_match(repo: Repo, hours: int = 1) -> int:
    for uid in (1, 2):
        repo.upsert_user(uid, f"nick{uid}", f"N{uid}")
    battle_id = repo.create_battle(datetime.now(MSK) + timedelta(hours=hours))
    return repo.create_match(
        battle_id, 1, 1,
        [Player(1, "nick1"), Player(2, "nick2")],
        advance=1, is_final=False,
        deadline=datetime.now(MSK) + timedelta(hours=hours),
    )


# --------------------------------------------------------- один голос

def test_one_free_vote_per_person_per_match(env):
    repo, _, _ = env
    match_id = open_match(repo)

    assert repo.add_vote(match_id, 500, 1, VoteSource.FREE) is VoteResult.ACCEPTED
    assert repo.add_vote(match_id, 500, 1, VoteSource.FREE) is VoteResult.DUPLICATE
    assert repo.add_vote(match_id, 500, 2, VoteSource.FREE) is VoteResult.DUPLICATE

    counts = {s.user_id: s.votes for s in repo.match_slots(match_id)}
    assert counts == {1: 1, 2: 0}, "второй голос не должен попасть в счёт"


def test_a_hundred_rapid_taps_add_exactly_one_vote(env):
    """Даже если человек долбит по кнопке — голос ровно один."""
    repo, _, _ = env
    match_id = open_match(repo)

    accepted = sum(
        repo.add_vote(match_id, 500, 1, VoteSource.FREE) is VoteResult.ACCEPTED
        for _ in range(100)
    )

    assert accepted == 1
    assert repo.match_slots(match_id)[0].votes == 1
    assert len(repo.vote_log(match_id)) == 1


def test_different_people_vote_independently(env):
    repo, _, _ = env
    match_id = open_match(repo)

    for voter in range(500, 510):
        assert repo.add_vote(match_id, voter, 1, VoteSource.FREE) is VoteResult.ACCEPTED

    assert repo.match_slots(match_id)[0].votes == 10


# ------------------------------------------------- закрытие голосования

def test_no_vote_lands_after_the_round_is_closed(env):
    repo, _, _ = env
    match_id = open_match(repo)
    repo.close_match(match_id, [Slot(1, "nick1", 0, 1), Slot(2, "nick2", 0, 2)])

    assert repo.add_vote(match_id, 500, 1, VoteSource.FREE) is VoteResult.CLOSED
    assert repo.add_vote(match_id, 501, 2, VoteSource.PAID) is VoteResult.CLOSED
    assert repo.vote_log(match_id) == []


def test_no_vote_lands_after_the_deadline_even_before_the_bot_notices(env):
    """Между дедлайном и работой планировщика есть окно — оно должно быть закрыто."""
    repo, _, _ = env
    match_id = open_match(repo, hours=-1)  # дедлайн уже прошёл

    assert repo.add_vote(match_id, 500, 1, VoteSource.FREE) is VoteResult.CLOSED
    assert repo.match_slots(match_id)[0].votes == 0


@pytest.mark.asyncio
async def test_closing_a_round_freezes_the_score(env):
    """Итог раунда не должен поехать от голоса, пришедшего следом."""
    repo, config, engine = env
    await join_users(engine, repo, 4)
    repo.add_vote(1, 900, 1, VoteSource.FREE)
    repo.add_vote(2, 901, 3, VoteSource.FREE)

    await engine.close_round()
    before = {s.user_id: s.votes for s in repo.match_slots(1)}

    assert repo.add_vote(1, 902, 1, VoteSource.FREE) is VoteResult.CLOSED
    assert {s.user_id: s.votes for s in repo.match_slots(1)} == before


@pytest.mark.asyncio
async def test_a_vote_cast_during_the_subscription_check_cannot_slip_through(env):
    """Между проверкой подписки и записью голоса раунд успевает закрыться.

    Именно поэтому все условия проверяются внутри самого INSERT, а не заранее.
    """
    repo, config, engine = env
    await join_users(engine, repo, 4)

    match = repo.get_match(1)
    assert match["status"] == "voting"  # человек видит открытый матч

    await engine.close_round()  # пока он проходил проверку подписки, раунд закрыли

    assert repo.add_vote(1, 903, 1, VoteSource.FREE) is VoteResult.CLOSED


# ------------------------------------------------------- чужой участник

def test_a_vote_for_someone_outside_the_match_is_refused(env):
    """Подделанная кнопка не должна начислять голос постороннему."""
    repo, _, _ = env
    match_id = open_match(repo)

    assert repo.add_vote(match_id, 500, 999, VoteSource.FREE) is VoteResult.UNKNOWN_TARGET
    assert repo.vote_log(match_id) == []


# --------------------------------------------------- купленные голоса

def test_a_refused_paid_vote_is_returned_to_the_balance(env):
    """Списали голос, а матч закрылся — деньги человека возвращаются."""
    repo, config, _ = env
    match_id = open_match(repo)
    repo.upsert_user(500, "voter", "V")
    repo.add_votes(500, 3)

    repo.add_vote(match_id, 500, 1, VoteSource.FREE)
    repo.close_match(match_id, [Slot(1, "nick1", 1, 1), Slot(2, "nick2", 0, 2)])

    assert repo.spend_vote(500) is True          # списали заранее
    result = repo.add_vote(match_id, 500, 1, VoteSource.PAID)
    assert result is VoteResult.CLOSED
    repo.add_votes(500, 1)                       # обработчик возвращает

    assert repo.vote_balance(500) == 3, "баланс не должен пострадать"


def test_paid_votes_stack_but_only_while_the_match_is_open(env):
    repo, _, _ = env
    match_id = open_match(repo)

    repo.add_vote(match_id, 500, 1, VoteSource.FREE)
    assert repo.add_vote(match_id, 500, 1, VoteSource.PAID) is VoteResult.ACCEPTED
    assert repo.add_vote(match_id, 500, 1, VoteSource.PAID) is VoteResult.ACCEPTED
    assert repo.match_slots(match_id)[0].votes == 3

    repo.close_match(match_id, [Slot(1, "nick1", 3, 1), Slot(2, "nick2", 0, 2)])
    assert repo.add_vote(match_id, 500, 1, VoteSource.PAID) is VoteResult.CLOSED
    assert repo.match_slots(match_id)[0].votes == 3


# ------------------------------------------- отмена батла из панели

@pytest.mark.asyncio
async def test_cancelling_a_battle_stops_all_voting(env):
    """Отменили батл — проголосовать нельзя ни в одном его матче."""
    repo, config, engine = env
    await join_users(engine, repo, 4)
    battle_id = int(repo.current_battle()["id"])

    closed = await engine.cancel(battle_id)

    assert closed == 2, "оба матча должны закрыться"
    assert repo.add_vote(1, 900, 1, VoteSource.FREE) is VoteResult.CLOSED
    assert repo.add_vote(2, 901, 3, VoteSource.FREE) is VoteResult.CLOSED


@pytest.mark.asyncio
async def test_a_cancelled_battle_cannot_be_voted_in_even_if_a_match_stayed_open(env):
    """Страховка: голос смотрит и на статус батла, не только матча."""
    repo, config, engine = env
    await join_users(engine, repo, 4)
    battle_id = int(repo.current_battle()["id"])

    repo.set_battle_status(battle_id, BattleStatus.CANCELLED)  # матчи намеренно не трогаем
    assert repo.get_match(1)["status"] == "voting"

    assert repo.add_vote(1, 900, 1, VoteSource.FREE) is VoteResult.CLOSED


@pytest.mark.asyncio
async def test_cancelling_leaves_it_to_the_admin_to_start_the_next(env):
    """Новый батл больше не открывается сам — его создаёт админ."""
    repo, config, engine = env
    await join_users(engine, repo, 4)
    old_id = int(repo.current_battle()["id"])

    await engine.cancel(old_id)

    assert repo.current_battle() is None, "автоматически ничего не открылось"


@pytest.mark.asyncio
async def test_participants_of_a_cancelled_battle_are_told(env):
    repo, config, engine = env
    await join_users(engine, repo, 4)

    await engine.cancel(int(repo.current_battle()["id"]))

    assert any("отменён" in text for text in engine.bot.direct[1])


@pytest.mark.asyncio
async def test_people_keep_queueing_after_a_cancel(env):
    """Запись продолжается всегда — очередь ждёт следующего батла."""
    repo, config, engine = env
    await join_users(engine, repo, 4)
    await engine.cancel(int(repo.current_battle()["id"]))

    repo.upsert_user(50, "newcomer", "N")
    accepted, _ = await engine.join(50, "newcomer")

    assert accepted
    assert repo.queue_size() == 1
    assert repo.current_battle() is None, "батл всё ещё создаёт админ"


@pytest.mark.asyncio
async def test_a_finished_battle_does_not_start_the_next_one(env):
    """Следующий батл создаёт админ, а не бот."""
    repo, config, engine = env
    await join_users(engine, repo, 4)
    repo.add_vote(1, 900, 1, VoteSource.FREE)
    repo.add_vote(2, 901, 3, VoteSource.FREE)
    await engine.close_round()          # финал из двоих

    final_id = int(repo.open_matches(1, 2)[0]["id"])
    repo.add_vote(final_id, 902, 1, VoteSource.FREE)
    await engine.close_round()

    assert repo.current_battle() is None
    assert repo.add_vote(final_id, 903, 1, VoteSource.FREE) is VoteResult.CLOSED
