"""Голос без подписки невозможен — ни при каких настройках и сбоях."""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from aiogram.exceptions import TelegramBadRequest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import MSK
from core.models import Player
from handlers.voting import cast_vote, open_voting
from services import sponsors, subscription
from storage.db import connect
from storage.repo import Repo
from storage.settings import Settings
from tests.test_engine import make_config

MAIN = -1001111111111


class Bot:
    """Телеграм, который отвечает про подписку так, как мы попросим."""

    def __init__(self, subscribed_to=(), broken=False) -> None:
        self.subscribed_to = set(subscribed_to)
        self.broken = broken

    async def approve_chat_join_request(self, chat_id, user_id):
        raise TelegramBadRequest(method=None, message="HIDE_REQUESTER_MISSING")

    async def get_chat_member(self, chat_id, user_id):
        if self.broken:
            raise TelegramBadRequest(method=None, message="chat not found")

        class Member:
            status = "member" if chat_id in self.subscribed_to else "left"

        return Member()

    async def get_chat(self, chat_id):
        class Chat:
            title = "Батлы"
            username = "battles"
            invite_link = None

        return Chat()


class Msg:
    def __init__(self, bot) -> None:
        self.bot = bot
        self.sent: list[str] = []
        self.markups: list = []

    async def answer(self, text, **kwargs):
        self.sent.append(text)
        self.markups.append(kwargs.get("reply_markup"))

    async def edit_reply_markup(self, **kwargs):
        self.markups.append(kwargs.get("reply_markup"))


class User:
    def __init__(self, user_id) -> None:
        self.id = user_id
        self.username = f"nick{user_id}"
        self.first_name = f"N{user_id}"


class Callback:
    def __init__(self, data, user_id, bot) -> None:
        self.data = data
        self.from_user = User(user_id)
        self.bot = bot
        self.message = Msg(bot)
        self.alerts: list[str] = []

    async def answer(self, text="", **kwargs):
        self.alerts.append(text)


@pytest.fixture()
def env(tmp_path):
    path = str(tmp_path / "gate.db")
    repo = Repo(connect(path))
    config = make_config(db_path=path, require_subscription=True)
    settings = Settings(repo.conn, config)
    settings.bootstrap()
    settings.set("main_channel_id", MAIN)

    for uid in (1, 2):
        repo.upsert_user(uid, f"nick{uid}", f"N{uid}")
    deadline = datetime.now(MSK) + timedelta(hours=1)
    battle_id = repo.create_battle(deadline)
    match_id = repo.create_match(
        battle_id, 1, 1, [Player(1, "nick1"), Player(2, "nick2")],
        advance=1, is_final=False, deadline=deadline,
    )
    return repo, config, settings, match_id


def votes(repo, match_id):
    return sum(slot.votes for slot in repo.match_slots(match_id))


# ------------------------------------------------------------ сам голос

@pytest.mark.asyncio
async def test_a_non_subscriber_cannot_vote(env):
    repo, config, settings, match_id = env
    callback = Callback(f"vote:{match_id}:1", 500, Bot(subscribed_to=()))

    await cast_vote(callback, repo, config, settings)

    assert votes(repo, match_id) == 0, "голос не подписчика не должен попасть в счёт"
    assert "подписчик" in callback.alerts[-1].lower()
    assert "необходимо подписаться" in callback.message.sent[0]


@pytest.mark.asyncio
async def test_a_subscriber_votes(env):
    repo, config, settings, match_id = env
    callback = Callback(f"vote:{match_id}:1", 500, Bot(subscribed_to=[MAIN]))

    await cast_vote(callback, repo, config, settings)

    assert votes(repo, match_id) == 1


@pytest.mark.asyncio
async def test_switching_the_setting_off_does_not_open_voting(env):
    """Переключатель в панели касается заявок, но не голосов."""
    repo, config, settings, match_id = env
    settings.set("require_subscription", False)
    callback = Callback(f"vote:{match_id}:1", 500, Bot(subscribed_to=()))

    await cast_vote(callback, repo, config, settings)

    assert votes(repo, match_id) == 0


@pytest.mark.asyncio
async def test_a_telegram_failure_blocks_the_vote(env):
    """Сбой проверки — отказ, а не бесплатный проход."""
    repo, config, settings, match_id = env
    callback = Callback(f"vote:{match_id}:1", 500, Bot(broken=True))

    await cast_vote(callback, repo, config, settings)

    assert votes(repo, match_id) == 0


@pytest.mark.asyncio
async def test_unsubscribing_between_votes_stops_the_second_one(env):
    repo, config, settings, match_id = env
    bot = Bot(subscribed_to=[MAIN])
    await cast_vote(Callback(f"vote:{match_id}:1", 500, bot), repo, config, settings)

    bot.subscribed_to.clear()
    await cast_vote(Callback(f"vote:{match_id}:1", 501, bot), repo, config, settings)

    assert votes(repo, match_id) == 1


# ------------------------------------------------------- экран «подпишитесь»

@pytest.mark.asyncio
async def test_the_gate_offers_a_way_back_to_the_match(env):
    repo, config, settings, match_id = env
    callback = Callback(f"vote:{match_id}:1", 500, Bot(subscribed_to=()))

    await cast_vote(callback, repo, config, settings)

    markup = callback.message.markups[0]
    assert markup.inline_keyboard[-1][0].callback_data == f"open:{match_id}"


@pytest.mark.asyncio
async def test_i_subscribed_opens_the_match_only_for_a_real_subscriber(env):
    repo, config, settings, match_id = env
    bot = Bot(subscribed_to=())

    liar = Callback(f"open:{match_id}", 500, bot)
    await open_voting(liar, repo, config, settings)
    assert "необходимо подписаться" in liar.message.sent[0]

    bot.subscribed_to.add(MAIN)
    honest = Callback(f"open:{match_id}", 500, bot)
    await open_voting(honest, repo, config, settings)
    assert "nick1" in honest.message.sent[-1], "должен открыться экран голосования"


# --------------------------------------------------------- нижний слой

@pytest.mark.asyncio
async def test_the_check_fails_closed():
    assert await subscription.is_subscribed(Bot(broken=True), MAIN, 500) is False


@pytest.mark.asyncio
async def test_diagnose_reports_the_reason():
    assert await subscription.diagnose(Bot(subscribed_to=[MAIN]), MAIN, 7) == ""
    assert "chat not found" in await subscription.diagnose(Bot(broken=True), MAIN, 7)


@pytest.mark.asyncio
async def test_force_ignores_the_switch(env):
    _, config, settings, _ = env
    settings.set("require_subscription", False)

    assert await sponsors.missing(Bot(), config, settings, 500) == []
    assert await sponsors.missing(Bot(), config, settings, 500, force=True) != []
