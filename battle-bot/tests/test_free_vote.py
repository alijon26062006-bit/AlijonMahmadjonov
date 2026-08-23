"""Бесплатный голос: один на весь батл, а не на каждую пару."""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import MSK
from core.models import Player, VoteResult, VoteSource
from handlers import voting
from storage.db import connect
from storage.repo import Repo
from storage.settings import Settings
from tests.test_engine import make_config

MAIN = -1001111111111


@pytest.fixture()
def env(tmp_path):
    path = str(tmp_path / "free.db")
    repo = Repo(connect(path))
    config = make_config(db_path=path)
    settings = Settings(repo.conn, config)
    settings.bootstrap()
    settings.set("main_channel_id", MAIN)

    for uid in range(1, 5):
        repo.upsert_user(uid, f"n{uid}", "N")
    for voter in range(500, 505):  # голосующие — обычные пользователи бота
        repo.upsert_user(voter, f"v{voter}", "V")
    deadline = datetime.now(MSK) + timedelta(hours=2)
    battle_id = repo.create_battle(deadline)
    first = repo.create_match(
        battle_id, 1, 1, [Player(1, "n1"), Player(2, "n2")],
        advance=1, is_final=False, deadline=deadline,
    )
    second = repo.create_match(
        battle_id, 1, 2, [Player(3, "n3"), Player(4, "n4")],
        advance=1, is_final=False, deadline=deadline,
    )
    return repo, config, settings, first, second


class Bot:
    async def get_chat_member(self, chat_id, user_id):
        return type("M", (), {"status": "member"})()

    async def get_chat(self, chat_id):
        return type("C", (), {"title": "Канал", "username": "c", "invite_link": None})()

    async def send_message(self, *args, **kwargs):
        return None


class Msg:
    def __init__(self, bot) -> None:
        self.bot = bot
        self.sent: list[str] = []
        self.markups: list = []

    async def answer(self, text, reply_markup=None, **kwargs):
        self.sent.append(text)
        self.markups.append(reply_markup)

    async def edit_reply_markup(self, **kwargs):
        pass


class Callback:
    def __init__(self, match_id, target_id, user_id, bot) -> None:
        self.data = f"vote:{match_id}:{target_id}"
        self.bot = bot
        self.message = Msg(bot)
        self.from_user = type("U", (), {"id": user_id, "username": "v", "first_name": "V"})()
        self.alerts: list[str] = []

    async def answer(self, text="", **kwargs):
        self.alerts.append(text)


def votes_in(repo, match_id) -> int:
    return sum(slot.votes for slot in repo.match_slots(match_id))


# ------------------------------------------------------ правило по умолчанию

def test_one_free_vote_for_the_whole_battle_is_the_default(env):
    _, _, settings, _, _ = env
    assert settings.get("free_vote_scope") == "battle"


def test_a_free_vote_in_one_pair_closes_the_others(env):
    repo, _, _, first, second = env

    repo.add_vote(first, 500, 1, VoteSource.FREE)

    assert repo.free_vote_used(second, 500, "battle") is True
    assert repo.free_vote_used(second, 500, "match") is False


def test_the_round_scope_sits_between_the_two(env):
    """Один на раунд: в этом раунде уже нельзя, в следующем — снова можно."""
    repo, _, _, first, _ = env
    deadline = datetime.now(MSK) + timedelta(hours=3)
    later = repo.create_match(
        1, 2, 1, [Player(1, "n1"), Player(3, "n3")],
        advance=1, is_final=False, deadline=deadline,
    )
    repo.add_vote(first, 500, 1, VoteSource.FREE)

    assert repo.free_vote_used(later, 500, "round") is False
    assert repo.free_vote_used(later, 500, "battle") is True


def test_a_bought_vote_does_not_spend_the_free_one(env):
    """Отметку ставит только бесплатный голос."""
    repo, _, _, first, second = env
    repo.add_votes(500, 5)
    repo.spend_vote(500)
    repo.add_vote(first, 500, 1, VoteSource.PAID)

    assert repo.free_vote_used(second, 500, "battle") is False


# ------------------------------------------------------- через обработчик

@pytest.mark.asyncio
async def test_the_second_pair_needs_a_bought_vote(env):
    """Ровно то, ради чего всё затевалось."""
    repo, config, settings, first, second = env
    bot = Bot()

    await voting.cast_vote(Callback(first, 1, 500, bot), repo, config, settings)
    assert votes_in(repo, first) == 1, "первый голос бесплатный"

    await voting.cast_vote(Callback(second, 3, 500, bot), repo, config, settings)
    assert votes_in(repo, second) == 0, "во вторую пару бесплатно нельзя"


@pytest.mark.asyncio
async def test_a_bought_vote_opens_the_second_pair(env):
    repo, config, settings, first, second = env
    bot = Bot()
    await voting.cast_vote(Callback(first, 1, 500, bot), repo, config, settings)
    repo.add_votes(500, 1)

    await voting.cast_vote(Callback(second, 3, 500, bot), repo, config, settings)

    assert votes_in(repo, second) == 1
    assert repo.vote_balance(500) == 0, "купленный голос списан"


@pytest.mark.asyncio
async def test_the_refusal_says_where_to_get_votes(env):
    repo, config, settings, first, second = env
    bot = Bot()
    await voting.cast_vote(Callback(first, 1, 500, bot), repo, config, settings)

    callback = Callback(second, 3, 500, bot)
    await voting.cast_vote(callback, repo, config, settings)

    assert "уже потрачен" in callback.alerts[-1]
    assert any("Голоса закончились" in text for text in callback.message.sent)
    buttons = [b.text for m in callback.message.markups if m
               for row in m.inline_keyboard for b in row]
    assert any("Купить" in text for text in buttons)


@pytest.mark.asyncio
async def test_bought_votes_stack_in_the_same_pair(env):
    """Купил голоса — трать сколько хочешь, хоть все в одну пару."""
    repo, config, settings, first, _ = env
    bot = Bot()
    await voting.cast_vote(Callback(first, 1, 500, bot), repo, config, settings)
    repo.add_votes(500, 3)

    for _ in range(3):
        await voting.cast_vote(Callback(first, 1, 500, bot), repo, config, settings)

    assert votes_in(repo, first) == 4, "бесплатный плюс три купленных"
    assert repo.vote_balance(500) == 0


@pytest.mark.asyncio
async def test_a_big_balance_is_spent_to_the_last_vote(env):
    """У человека 188 голосов — все должны уйти в дело."""
    repo, config, settings, first, _ = env
    bot = Bot()
    repo.add_votes(500, 188)

    for _ in range(190):  # два лишних нажатия сверх баланса
        await voting.cast_vote(Callback(first, 1, 500, bot), repo, config, settings)

    assert votes_in(repo, first) == 189, "бесплатный плюс 188 купленных"
    assert repo.vote_balance(500) == 0


@pytest.mark.asyncio
async def test_bought_votes_can_go_to_both_sides(env):
    """Ограничения «за кого» нет — только сам факт наличия голосов."""
    repo, config, settings, first, _ = env
    bot = Bot()
    repo.add_votes(500, 2)
    await voting.cast_vote(Callback(first, 1, 500, bot), repo, config, settings)
    await voting.cast_vote(Callback(first, 2, 500, bot), repo, config, settings)

    counts = {slot.user_id: slot.votes for slot in repo.match_slots(first)}
    assert counts == {1: 1, 2: 1}


@pytest.mark.asyncio
async def test_without_a_balance_the_second_vote_is_refused(env):
    """А вот без купленных второй голос в паре по-прежнему нельзя."""
    repo, config, settings, first, _ = env
    bot = Bot()
    await voting.cast_vote(Callback(first, 1, 500, bot), repo, config, settings)

    callback = Callback(first, 1, 500, bot)
    await voting.cast_vote(callback, repo, config, settings)

    assert votes_in(repo, first) == 1
    assert "уже потрачен" in callback.alerts[-1]


def test_the_free_vote_cannot_be_doubled_even_by_a_race(env):
    """Второй бесплатный в тот же матч не пропустит сама база."""
    repo, _, _, first, _ = env

    assert repo.add_vote(first, 500, 1, VoteSource.FREE) is VoteResult.ACCEPTED
    assert repo.add_vote(first, 500, 2, VoteSource.FREE) is VoteResult.DUPLICATE
    assert votes_in(repo, first) == 1


@pytest.mark.asyncio
async def test_switching_the_rule_back_to_per_pair_works(env):
    """Админ вернул старое правило — снова по одному голосу на пару."""
    repo, config, settings, first, second = env
    settings.set("free_vote_scope", "match")
    bot = Bot()

    await voting.cast_vote(Callback(first, 1, 500, bot), repo, config, settings)
    await voting.cast_vote(Callback(second, 3, 500, bot), repo, config, settings)

    assert votes_in(repo, first) == 1 and votes_in(repo, second) == 1


@pytest.mark.asyncio
async def test_different_people_are_independent(env):
    repo, config, settings, first, _ = env
    bot = Bot()

    for voter in range(500, 505):
        await voting.cast_vote(Callback(first, 1, voter, bot), repo, config, settings)

    assert votes_in(repo, first) == 5


# ------------------------------------------------------------- как объяснено

def test_the_screen_explains_the_rule():
    from services import texts

    assert "на весь батл" in texts.free_scope_line("battle")
    assert "на раунд" in texts.free_scope_line("round")
    assert "на каждую пару" in texts.free_scope_line("match")


def test_the_panel_can_cycle_through_all_three():
    from services import panel_ui

    seen, scope = [], "battle"
    for _ in range(3):
        seen.append(scope)
        scope = panel_ui.SCOPE_NEXT[scope]

    assert sorted(seen) == ["battle", "match", "round"]
    assert scope == "battle", "переключатель должен замкнуться в круг"
