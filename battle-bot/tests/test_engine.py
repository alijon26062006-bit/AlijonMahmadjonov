"""Прогон целого батла на фейковом боте — без обращения к Telegram."""
import sys
from dataclasses import replace
from datetime import datetime, time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import Config, VotePack
from core.engine import BattleEngine
from core.models import BattleStatus, VoteSource
from storage.db import connect
from storage.repo import Repo


class FakeMessage:
    def __init__(self, message_id: int) -> None:
        self.message_id = message_id


class FakeBot:
    """Считает исходящие сообщения вместо реальных вызовов API."""

    def __init__(self) -> None:
        self.channel_posts: list[str] = []
        self.direct: dict[int, list[str]] = {}
        self._next_id = 100

    async def send_message(self, chat_id, text, **kwargs):
        self._next_id += 1
        if chat_id < 0:  # канал
            self.channel_posts.append(text)
        else:
            self.direct.setdefault(chat_id, []).append(text)
        return FakeMessage(self._next_id)


def make_config(**overrides) -> Config:
    base = Config(
        bot_token="test",
        bot_username="TestBot",
        channel_id=-1001234567890,
        channel_url="https://t.me/testchannel",
        admin_ids=[1],
        db_path=":memory:",
        round_times=[time(18, 0), time(19, 30), time(21, 0)],
        min_participants=2,
        max_participants=100,
        require_subscription=False,
        require_username=True,
        paid_votes_enabled=True,
        vote_packs=[VotePack(1, 15)],
        prizes=[1000, 500, 250],
        publish_delay=0.0,
        dm_delay=0.0,
    )
    return replace(base, **overrides)


@pytest.fixture()
def env(tmp_path):
    repo = Repo(connect(str(tmp_path / "engine.db")))
    bot = FakeBot()
    config = make_config(db_path=str(tmp_path / "engine.db"))
    return bot, repo, BattleEngine(bot, repo, config)


async def join_users(engine: BattleEngine, repo: Repo, count: int) -> None:
    for i in range(1, count + 1):
        repo.upsert_user(i, f"nick{i}", f"Name{i}")
        await engine.join(i, f"nick{i}")


def vote_for(repo: Repo, match_id: int, target_id: int, voters: range) -> None:
    for voter in voters:
        repo.add_vote(match_id, voter, target_id, VoteSource.FREE)


@pytest.mark.asyncio
async def test_a_pair_is_published_as_soon_as_two_apply(env):
    bot, repo, engine = env
    repo.upsert_user(1, "nick1", "A")
    accepted, text = await engine.join(1, "nick1")
    assert accepted
    assert "очереди" in text
    assert bot.channel_posts == []  # одного мало, пост не выходит

    repo.upsert_user(2, "nick2", "B")
    accepted, text = await engine.join(2, "nick2")
    assert accepted
    assert len(bot.channel_posts) == 1
    assert "@nick1" in bot.channel_posts[0] and "@nick2" in bot.channel_posts[0]
    assert "Р А У Н Д" in bot.channel_posts[0]


@pytest.mark.asyncio
async def test_both_opponents_get_their_voting_link(env):
    bot, repo, engine = env
    await join_users(engine, repo, 2)
    assert "TestBot?start=v1" in "".join(bot.direct[1])
    assert "TestBot?start=v1" in "".join(bot.direct[2])


@pytest.mark.asyncio
async def test_the_same_user_cannot_apply_twice(env):
    _, repo, engine = env
    repo.upsert_user(1, "nick1", "A")
    await engine.join(1, "nick1")
    accepted, text = await engine.join(1, "nick1")
    assert not accepted
    assert "уже участвуете" in text


@pytest.mark.asyncio
async def test_odd_applicant_waits_without_a_post(env):
    bot, repo, engine = env
    await join_users(engine, repo, 5)
    assert len(bot.channel_posts) == 2  # две пары, пятый ждёт
    assert len(repo.unassigned_players(1)) == 1


@pytest.mark.asyncio
async def test_round_closes_and_the_leftover_gets_a_bye(env):
    bot, repo, engine = env
    await join_users(engine, repo, 5)

    vote_for(repo, 1, target_id=1, voters=range(1000, 1005))  # nick1 обходит nick2
    vote_for(repo, 2, target_id=3, voters=range(2000, 2003))  # nick3 обходит nick4

    await engine.close_round()

    alive = {p.user_id for p in repo.alive_players(1)}
    assert alive == {1, 3, 5}  # два победителя + пятый без боя
    assert "без боя" in "".join(bot.direct[5])
    assert "проиграли" in "".join(bot.direct[2])


@pytest.mark.asyncio
async def test_three_survivors_go_straight_to_the_final(env):
    bot, repo, engine = env
    await join_users(engine, repo, 5)
    vote_for(repo, 1, 1, range(1000, 1005))
    vote_for(repo, 2, 3, range(2000, 2003))
    await engine.close_round()

    battle = repo.current_battle()
    assert battle["round_no"] == 2
    final = repo.open_matches(1, 2)
    assert len(final) == 1
    assert final[0]["is_final"] == 1
    assert len(repo.match_slots(int(final[0]["id"]))) == 3


@pytest.mark.asyncio
async def test_the_final_awards_three_places_and_ends_the_battle(env):
    bot, repo, engine = env
    await join_users(engine, repo, 5)
    vote_for(repo, 1, 1, range(1000, 1005))
    vote_for(repo, 2, 3, range(2000, 2003))
    await engine.close_round()

    final_id = int(repo.open_matches(1, 2)[0]["id"])
    vote_for(repo, final_id, 1, range(3000, 3010))
    vote_for(repo, final_id, 3, range(4000, 4005))
    vote_for(repo, final_id, 5, range(5000, 5001))

    await engine.close_round()

    assert repo.current_battle() is None  # батл закрыт
    places = {
        row["user_id"]: row["place"]
        for row in repo.conn.execute("SELECT user_id, place FROM participants WHERE place IS NOT NULL")
    }
    assert places == {1: 1, 3: 2, 5: 3}
    assert repo.stats_for(1)["titles"] == 1
    assert "1000⭐" in "".join(bot.direct[1])
    assert "Батл завершён" in "".join(bot.channel_posts)


@pytest.mark.asyncio
async def test_a_single_applicant_keeps_registration_open(env):
    """Пары не набралось — батл не стартует и не отменяется, приём продолжается."""
    bot, repo, engine = env
    repo.upsert_user(1, "nick1", "A")
    await engine.join(1, "nick1")

    await engine.close_round()

    battle = repo.current_battle()
    assert battle is not None
    assert battle["status"] == BattleStatus.REGISTRATION.value
    assert battle["round_no"] == 1
    assert bot.channel_posts == []
    # дедлайн всегда впереди, иначе фоновая задача крутила бы итоги без остановки
    assert datetime.fromisoformat(battle["deadline"]) > engine.now()


@pytest.mark.asyncio
async def test_applications_are_closed_once_the_battle_is_running(env):
    bot, repo, engine = env
    await join_users(engine, repo, 4)
    vote_for(repo, 1, 1, range(1000, 1003))
    vote_for(repo, 2, 3, range(2000, 2003))
    await engine.close_round()

    repo.upsert_user(99, "late", "Late")
    accepted, text = await engine.join(99, "late")
    assert not accepted
    assert "уже идёт" in text


@pytest.mark.asyncio
async def test_banned_user_cannot_apply(env):
    _, repo, engine = env
    repo.upsert_user(7, "nick7", "G")
    repo.set_banned(7, True)
    accepted, _ = await engine.join(7, "nick7")
    assert not accepted


@pytest.mark.asyncio
async def test_large_battle_runs_to_a_champion(env):
    bot, repo, engine = env
    await join_users(engine, repo, 20)

    guard = 0
    while repo.current_battle() is not None:
        guard += 1
        assert guard < 10, "батл должен сходиться за несколько раундов"
        battle = repo.current_battle()
        for match in repo.open_matches(int(battle["id"]), int(battle["round_no"])):
            match_id = int(match["id"])
            for offset, slot in enumerate(repo.match_slots(match_id)):
                base = match_id * 1000 + offset * 100
                vote_for(repo, match_id, slot.user_id, range(base, base + 5 - offset))
        await engine.close_round()

    champions = [
        row["user_id"]
        for row in repo.conn.execute("SELECT user_id FROM participants WHERE place = 1")
    ]
    assert len(champions) == 1
