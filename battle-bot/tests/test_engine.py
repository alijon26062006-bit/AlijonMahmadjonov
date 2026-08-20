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
        self.markups: dict[int, list] = {}
        self._next_id = 100

    async def send_message(self, chat_id, text, reply_markup=None, **kwargs):
        self._next_id += 1
        if chat_id < 0:  # канал
            self.channel_posts.append(text)
        else:
            self.direct.setdefault(chat_id, []).append(text)
            self.markups.setdefault(chat_id, []).append(reply_markup)
        return FakeMessage(self._next_id)

    def buttons(self, user_id: int) -> list:
        """Все кнопки, что бот прислал этому человеку."""
        return [
            button
            for markup in self.markups.get(user_id, [])
            if markup is not None
            for row in markup.inline_keyboard
            for button in row
        ]


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
        referral_enabled=True,
        referral_reward=1,
        premium_emoji_file="",
        premium_emoji_in_channel="auto",
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
async def test_both_opponents_get_their_voting_link_on_a_button(env):
    """Голая ссылка в тексте выглядит бедно — её несут кнопки."""
    bot, repo, engine = env
    await join_users(engine, repo, 2)

    for user_id in (1, 2):
        links_on_buttons = [
            b.url or (b.copy_text.text if b.copy_text else None) or b.switch_inline_query
            for b in bot.buttons(user_id)
        ]
        assert any(
            link and "TestBot?start=v1" in link for link in links_on_buttons
        ), f"участник {user_id} остался без ссылки на кнопке"


@pytest.mark.asyncio
async def test_the_pair_message_offers_the_useful_actions(env):
    bot, repo, engine = env
    await join_users(engine, repo, 2)

    labels = [b.text for b in bot.buttons(1)]
    assert any("соперник" in label.lower() for label in labels)
    assert any("друзей" in label.lower() for label in labels)
    assert any("копировать" in label.lower() for label in labels)


@pytest.mark.asyncio
async def test_the_rival_is_named_in_the_message(env):
    bot, repo, engine = env
    await join_users(engine, repo, 2)

    assert "@nick2" in "".join(bot.direct[1])
    assert "@nick1" in "".join(bot.direct[2])


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
    # проигравший получает разбор своего матча, а не безликое «вы проиграли»
    loser = "".join(bot.direct[2])
    assert "Вы выбываете" in loser
    assert "@nick1" in loser and "@nick2" in loser, "видны оба соперника"


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

    # прежний батл закрыт, а набор в следующий открыт сразу
    finished = repo.conn.execute(
        "SELECT status FROM battles WHERE id = 1"
    ).fetchone()["status"]
    assert finished == "finished"

    fresh = repo.current_battle()
    assert fresh is not None and fresh["id"] == 2
    assert fresh["status"] == BattleStatus.REGISTRATION.value
    assert repo.participant_count(2) == 0, "новый батл собирает новых людей"

    places = {
        row["user_id"]: row["place"]
        for row in repo.conn.execute("SELECT user_id, place FROM participants WHERE place IS NOT NULL")
    }
    assert places == {1: 1, 3: 2, 5: 3}
    assert repo.stats_for(1)["titles"] == 1
    assert "1000⭐" in "".join(bot.direct[1])
    assert "1000⭐" in "".join(bot.channel_posts)  # объявление призов


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
    assert "Набралось заявок" in "".join(bot.channel_posts)
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
    while True:
        guard += 1
        assert guard < 10, "батл должен сходиться за несколько раундов"
        battle = repo.current_battle()
        assert battle is not None
        if int(battle["id"]) != 1:
            break  # первый батл доигран, открылся набор в следующий
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


@pytest.mark.asyncio
async def test_too_few_applications_postpone_the_battle_and_keep_the_votes(tmp_path):
    """Батл с призами не должен стартовать на паре человек."""
    repo = Repo(connect(str(tmp_path / "few.db")))
    bot = FakeBot()
    config = make_config(db_path=str(tmp_path / "few.db"), min_participants=6)
    engine = BattleEngine(bot, repo, config)

    await join_users(engine, repo, 4)
    vote_for(repo, 1, target_id=1, voters=range(1000, 1003))

    await engine.close_round()

    battle = repo.current_battle()
    assert battle["status"] == BattleStatus.REGISTRATION.value
    assert battle["round_no"] == 1
    assert "Набралось заявок" in "".join(bot.channel_posts)
    # новый дедлайн всегда в будущем (в бою это следующий день — см. test_scheduler)
    assert datetime.fromisoformat(battle["deadline"]) > engine.now()

    # матчи остались открытыми, голоса на месте, дедлайн у них тоже сдвинут
    open_matches = repo.open_matches(1, 1)
    assert len(open_matches) == 2
    assert open_matches[0]["deadline"] == battle["deadline"]
    assert {s.user_id: s.votes for s in repo.match_slots(1)} == {1: 3, 2: 0}


@pytest.mark.asyncio
async def test_battle_starts_once_enough_people_applied(tmp_path):
    repo = Repo(connect(str(tmp_path / "enough.db")))
    bot = FakeBot()
    config = make_config(db_path=str(tmp_path / "enough.db"), min_participants=6)
    engine = BattleEngine(bot, repo, config)

    await join_users(engine, repo, 6)
    for match_id, winner in ((1, 1), (2, 3), (3, 5)):
        vote_for(repo, match_id, winner, range(match_id * 100, match_id * 100 + 3))

    await engine.close_round()

    assert repo.current_battle()["round_no"] == 2
    assert {p.user_id for p in repo.alive_players(1)} == {1, 3, 5}
