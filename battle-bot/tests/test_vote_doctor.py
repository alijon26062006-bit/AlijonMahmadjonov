"""Проверка голоса: почему человек не может проголосовать."""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.models import Player, VoteSource
from services import vote_doctor
from storage.db import connect
from storage.repo import Repo
from storage.settings import Settings
from tests.test_engine import make_config

ONE, TWO, VOTER = 1, 2, 500


class Bot:
    """Отвечает про подписку так, как скажут."""

    def __init__(self, subscribed=True, broken=False) -> None:
        self.subscribed = subscribed
        self.broken = broken

    async def get_chat_member(self, chat_id, user_id):
        if self.broken:
            from aiogram.exceptions import TelegramAPIError

            raise TelegramAPIError(method=None, message="бот не админ")
        return type("M", (), {"status": "member" if self.subscribed else "left"})()


@pytest.fixture()
def env(tmp_path):
    path = str(tmp_path / "doctor.db")
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


async def check(env_tuple, bot=None, user_id=VOTER):
    repo, config, settings, match_id = env_tuple
    return await vote_doctor.diagnose(
        bot or Bot(), repo, config, settings, user_id, match_id
    )


@pytest.mark.asyncio
async def test_a_fresh_person_can_vote(env):
    report = await check(env)

    assert report.can_vote
    assert any("Бесплатный голос ещё не потрачен" in line for line in report.lines)


@pytest.mark.asyncio
async def test_the_empty_balance_is_named(env):
    """Тот самый случай: бесплатный потрачен, купленных нет."""
    repo, _, _, match_id = env
    repo.add_vote(match_id, VOTER, ONE, VoteSource.FREE)

    report = await check(env)

    assert not report.can_vote
    assert any("баланс пуст" in line.lower() for line in report.lines)


@pytest.mark.asyncio
async def test_a_bought_balance_is_enough(env):
    repo, _, _, match_id = env
    repo.add_vote(match_id, VOTER, ONE, VoteSource.FREE)
    repo.add_votes(VOTER, 188)

    report = await check(env)

    assert report.can_vote, report.lines
    assert any("188" in line for line in report.lines)


@pytest.mark.asyncio
async def test_a_missing_subscription_is_named(env):
    report = await check(env, Bot(subscribed=False))

    assert not report.can_vote
    assert any("Нет подписки" in line for line in report.lines)


@pytest.mark.asyncio
async def test_a_silent_telegram_is_named_too(env):
    """Бот не админ в канале — самая частая причина, и её видно."""
    report = await check(env, Bot(broken=True))

    assert not report.can_vote
    assert any("не ответил" in line for line in report.lines)


@pytest.mark.asyncio
async def test_a_ban_stops_everything(env):
    repo, _, _, _ = env
    repo.set_banned(VOTER, True)

    report = await check(env)

    assert not report.can_vote
    assert "заблокирован" in report.lines[0].lower()


@pytest.mark.asyncio
async def test_spent_votes_do_not_stop_anyone(env):
    """Сколько бы ни отдал в эту пару — может отдавать ещё."""
    repo, _, _, match_id = env
    repo.add_votes(VOTER, 50)
    repo.add_vote(match_id, VOTER, ONE, VoteSource.FREE)
    for _ in range(5):
        repo.add_vote(match_id, VOTER, ONE, VoteSource.PAID)

    report = await check(env)

    assert report.can_vote
    assert any("не предел" in line for line in report.lines)


@pytest.mark.asyncio
async def test_without_a_battle_it_says_so(tmp_path):
    path = str(tmp_path / "empty.db")
    repo = Repo(connect(path))
    config = make_config(db_path=path)
    settings = Settings(repo.conn, config)
    settings.bootstrap()
    repo.upsert_user(VOTER, "voter", "voter")

    report = await vote_doctor.diagnose(Bot(), repo, config, settings, VOTER)

    assert not report.can_vote
    assert "нет открытого голосования" in report.lines[0].lower()
