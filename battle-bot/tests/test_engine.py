"""Прогон целого батла на фейковом боте — без обращения к Telegram."""
import random
import sys
from dataclasses import replace
from datetime import datetime, time, timedelta
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


async def enqueue_users(engine: BattleEngine, repo: Repo, count: int) -> None:
    """Только записать в очередь — батл при этом не создаётся."""
    for i in range(1, count + 1):
        repo.upsert_user(i, f"nick{i}", f"Name{i}")
        await engine.join(i, f"nick{i}")


class NoShuffle(random.Random):
    """Жеребьёвка без перемешивания — только для тестов.

    В бою пары тянутся случайно, но тогда проверять «первый против второго»
    невозможно. Здесь порядок очереди сохраняется.
    """

    def shuffle(self, sequence, *args, **kwargs):
        return None


async def join_users(engine: BattleEngine, repo: Repo, count: int) -> None:
    """Записать в очередь и сразу собрать батл — как это делает админ."""
    await enqueue_users(engine, repo, count)
    engine.rng = NoShuffle()
    await engine.create_from_queue()


def vote_for(repo: Repo, match_id: int, target_id: int, voters: range) -> None:
    for voter in voters:
        repo.add_vote(match_id, voter, target_id, VoteSource.FREE)


@pytest.mark.asyncio
async def test_applying_only_puts_you_in_the_queue(env):
    """Заявка больше не создаёт батл — люди копятся до команды админа."""
    bot, repo, engine = env
    repo.upsert_user(1, "nick1", "A")

    accepted, text = await engine.join(1, "nick1")

    assert accepted and "очереди" in text
    assert repo.queue_size() == 1
    assert repo.current_battle() is None
    assert bot.channel_posts == [], "в канал ничего не выходит"


@pytest.mark.asyncio
async def test_the_admin_builds_the_battle_out_of_the_queue(env):
    bot, repo, engine = env
    await enqueue_users(engine, repo, 4)
    assert bot.channel_posts == []

    engine.rng = NoShuffle()
    started, note = await engine.create_from_queue()

    assert started, note
    assert repo.queue_size() == 0, "очередь ушла в батл"
    assert repo.participant_count(1) == 4
    posts = [text for text in bot.channel_posts if "У Ч А С Т Н И К И" in text]
    assert len(posts) == 2, "две пары — два поста, все сразу"


@pytest.mark.asyncio
async def test_a_battle_is_not_built_from_too_few_people(env):
    bot, repo, engine = env
    await enqueue_users(engine, repo, 1)

    started, note = await engine.create_from_queue()

    assert not started
    assert "1 из 2" in note
    assert repo.current_battle() is None
    assert repo.queue_size() == 1, "очередь не тронута"


@pytest.mark.asyncio
async def test_a_second_battle_cannot_start_while_one_is_running(env):
    bot, repo, engine = env
    await join_users(engine, repo, 4)
    await enqueue_users(engine, repo, 6)

    started, note = await engine.create_from_queue()

    assert not started and "уже идёт" in note


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
async def test_the_same_user_cannot_queue_twice(env):
    _, repo, engine = env
    repo.upsert_user(1, "nick1", "A")
    await engine.join(1, "nick1")

    accepted, text = await engine.join(1, "nick1")

    assert not accepted and "уже в очереди" in text
    assert repo.queue_size() == 1


@pytest.mark.asyncio
async def test_an_odd_participant_gets_a_bye(env):
    bot, repo, engine = env
    await join_users(engine, repo, 5)

    posts = [text for text in bot.channel_posts if "У Ч А С Т Н И К И" in text]
    assert len(posts) == 2, "две пары, пятый проходит без боя"
    assert len(repo.unassigned_players(1)) == 1


@pytest.mark.asyncio
async def test_round_closes_and_the_leftover_gets_a_bye(env):
    bot, repo, engine = env
    await join_users(engine, repo, 5)

    vote_for(repo, 1, target_id=1, voters=range(1000, 1005))  # nick1 обходит nick2
    vote_for(repo, 2, target_id=3, voters=range(2000, 2003))  # nick3 обходит nick4

    await engine.close_round(force=True)

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
    await engine.close_round(force=True)

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
    await engine.close_round(force=True)

    final_id = int(repo.open_matches(1, 2)[0]["id"])
    vote_for(repo, final_id, 1, range(3000, 3010))
    vote_for(repo, final_id, 3, range(4000, 4005))
    vote_for(repo, final_id, 5, range(5000, 5001))

    await engine.close_round(force=True)

    finished = repo.conn.execute(
        "SELECT status FROM battles WHERE id = 1"
    ).fetchone()["status"]
    assert finished == "finished"
    assert repo.current_battle() is None, "следующий батл создаёт админ"

    places = {
        row["user_id"]: row["place"]
        for row in repo.conn.execute("SELECT user_id, place FROM participants WHERE place IS NOT NULL")
    }
    assert places == {1: 1, 3: 2, 5: 3}
    assert repo.stats_for(1)["titles"] == 1
    assert "1000⭐" in "".join(bot.direct[1])
    assert "1000⭐" in "".join(bot.channel_posts)  # объявление призов


@pytest.mark.asyncio
async def test_closing_without_a_battle_does_nothing(env):
    """Батла нет — подводить нечего, и падать тоже не за что."""
    bot, repo, engine = env
    repo.upsert_user(1, "nick1", "A")
    await engine.join(1, "nick1")

    await engine.close_round(force=True)

    assert repo.current_battle() is None
    assert bot.channel_posts == []


@pytest.mark.asyncio
async def test_a_newcomer_joins_the_running_battle(env):
    """Пришёл посреди первого раунда — попадает в этот же батл, а не в очередь."""
    _, repo, engine = env
    await join_users(engine, repo, 4)

    repo.upsert_user(99, "late", "Late")
    accepted, text = await engine.join(99, "late")

    assert accepted and "в батле" in text.lower()
    assert repo.is_participant(1, 99), "новичок должен попасть в идущий батл"
    assert repo.queue_size() == 0, "в очереди ему делать нечего"


@pytest.mark.asyncio
async def test_two_newcomers_get_a_published_pair(env):
    """Набралась пара из подсевших — её пост сразу выходит в канале."""
    bot, repo, engine = env
    await join_users(engine, repo, 4)
    posts_before = len(bot.channel_posts)

    for user_id in (98, 99):
        repo.upsert_user(user_id, f"late{user_id}", "L")
        await engine.join(user_id, f"late{user_id}")

    assert len(bot.channel_posts) > posts_before, "пара должна выйти в канале"
    assert len(repo.open_matches(1, 1)) == 3, "два исходных матча плюс подсаженный"
    assert "late99" in bot.direct[98][-1], "каждому назвали соперника"


@pytest.mark.asyncio
async def test_a_lonely_newcomer_waits_and_passes_without_a_fight(env):
    """Соперник не подошёл до итогов — проход без боя, а не вылет."""
    _, repo, engine = env
    await join_users(engine, repo, 4)
    repo.upsert_user(99, "late", "Late")
    await engine.join(99, "late")

    vote_for(repo, 1, 1, range(1000, 1003))
    vote_for(repo, 2, 3, range(2000, 2003))
    await engine.close_round(force=True)

    assert 99 in [p.user_id for p in repo.alive_players(1)], "должен пройти дальше"


@pytest.mark.asyncio
async def test_after_the_window_newcomers_go_to_the_queue(env):
    """Сетка сошлась — свежих участников в неё уже не подсаживаем."""
    _, repo, engine = env
    await join_users(engine, repo, 4)
    engine.settings.set("late_join_until_round", 1)
    repo.set_round(1, 2, engine.now() + timedelta(hours=1))

    repo.upsert_user(99, "late", "Late")
    accepted, text = await engine.join(99, "late")

    assert accepted and "очереди" in text
    assert not repo.is_participant(1, 99)
    assert repo.queue_size() == 1


@pytest.mark.asyncio
async def test_nobody_is_seated_next_to_a_final(env):
    """В маленьком батле финал наступает во 2 раунде — подсадка туда запрещена."""
    _, repo, engine = env
    await join_users(engine, repo, 4)
    vote_for(repo, 1, 1, range(1000, 1003))
    vote_for(repo, 2, 3, range(2000, 2003))
    await engine.close_round(force=True)

    assert repo.open_matches(1, 2)[0]["is_final"], "второй раунд — уже финал"

    repo.upsert_user(99, "late", "Late")
    accepted, text = await engine.join(99, "late")

    assert accepted and "очереди" in text
    assert not repo.is_participant(1, 99), "рядом с финалом пар не заводим"


@pytest.mark.asyncio
async def test_the_window_can_be_switched_off(env):
    """Ноль в настройке — подсадки нет вовсе, всё копится в очереди."""
    _, repo, engine = env
    await join_users(engine, repo, 4)
    engine.settings.set("late_join_until_round", 0)

    repo.upsert_user(99, "late", "Late")
    accepted, text = await engine.join(99, "late")

    assert accepted and "очереди" in text
    assert not repo.is_participant(1, 99)


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
        await engine.close_round(force=True)

    champions = [
        row["user_id"]
        for row in repo.conn.execute("SELECT user_id FROM participants WHERE place = 1")
    ]
    assert len(champions) == 1


@pytest.mark.asyncio
async def test_the_minimum_is_respected(tmp_path):
    """Пока в очереди меньше минимума, батл не собирается."""
    path = str(tmp_path / "enough.db")
    repo = Repo(connect(path))
    engine = BattleEngine(FakeBot(), repo, make_config(db_path=path, min_participants=6))

    await enqueue_users(engine, repo, 5)
    started, _ = await engine.create_from_queue()
    assert not started

    repo.upsert_user(6, "nick6", "N")
    await engine.join(6, "nick6")
    engine.rng = NoShuffle()
    started, _ = await engine.create_from_queue()

    assert started
    assert repo.participant_count(1) == 6


# ------------------------------------------------- очередь между батлами

@pytest.mark.asyncio
async def test_the_queue_survives_a_whole_battle(env):
    """Записавшиеся во время батла ждут следующего, а не теряются."""
    bot, repo, engine = env
    await join_users(engine, repo, 4)
    engine.settings.set("late_join_until_round", 0)  # проверяем именно очередь

    for user_id in (10, 11, 12):
        repo.upsert_user(user_id, f"new{user_id}", "N")
        await engine.join(user_id, f"new{user_id}")

    vote_for(repo, 1, 1, range(1000, 1003))
    vote_for(repo, 2, 3, range(2000, 2003))
    await engine.close_round(force=True)          # финал из двоих
    final_id = int(repo.open_matches(1, 2)[0]["id"])
    vote_for(repo, final_id, 1, range(3000, 3003))
    await engine.close_round(force=True)          # батл завершён

    assert repo.current_battle() is None
    assert repo.queue_size() == 3, "очередь дождалась своего часа"

    engine.rng = NoShuffle()
    started, _ = await engine.create_from_queue()
    assert started
    assert repo.participant_count(2) == 3


@pytest.mark.asyncio
async def test_leaving_the_queue_is_possible(env):
    _, repo, engine = env
    await enqueue_users(engine, repo, 3)

    repo.leave_queue(2)

    assert repo.queue_size() == 2
    assert [p.user_id for p in repo.queue_players()] == [1, 3]


@pytest.mark.asyncio
async def test_the_queue_keeps_the_order_people_joined_in(env):
    _, repo, engine = env
    await enqueue_users(engine, repo, 5)

    assert [p.user_id for p in repo.queue_players()] == [1, 2, 3, 4, 5]
    assert [p.user_id for p in repo.queue_players(limit=3)] == [1, 2, 3]


@pytest.mark.asyncio
async def test_a_battle_takes_no_more_than_the_limit(tmp_path):
    """Очередь больше предела — лишние остаются ждать следующего батла."""
    path = str(tmp_path / "limit.db")
    repo = Repo(connect(path))
    engine = BattleEngine(FakeBot(), repo, make_config(db_path=path, max_participants=4))

    await enqueue_users(engine, repo, 7)
    engine.rng = NoShuffle()
    await engine.create_from_queue()

    assert repo.participant_count(1) == 4
    assert repo.queue_size() == 3, "остальные ждут следующего"


@pytest.mark.asyncio
async def test_clearing_the_queue_empties_it(env):
    _, repo, engine = env
    await enqueue_users(engine, repo, 4)

    assert repo.clear_queue() == 4
    assert repo.queue_size() == 0
