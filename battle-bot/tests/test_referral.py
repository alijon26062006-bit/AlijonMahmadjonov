"""Голоса за приглашённых: строго один раз и только за подписавшегося новичка."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import links, referral
from storage.db import connect
from storage.repo import Repo
from storage.settings import Settings
from tests.test_engine import FakeBot, make_config

INVITER = 100
FRIEND = 200


@pytest.fixture()
def env(tmp_path):
    path = str(tmp_path / "ref.db")
    repo = Repo(connect(path))
    config = make_config(db_path=path, require_subscription=False)
    settings = Settings(repo.conn, config)
    settings.bootstrap()
    repo.upsert_user(INVITER, "inviter", "Inviter")
    return repo, config, settings, FakeBot()


async def invite(env, invited_id=FRIEND, inviter_id=INVITER) -> int | None:
    repo, config, settings, bot = env
    referral.remember(repo, invited_id, inviter_id, settings)
    repo.upsert_user(invited_id, f"user{invited_id}", "Friend")
    return await referral.try_reward(bot, repo, config, settings, invited_id)


# ------------------------------------------------------------ основной путь

@pytest.mark.asyncio
async def test_a_friend_brings_one_vote(env):
    repo, _, settings, _ = env

    assert await invite(env) == INVITER
    assert repo.vote_balance(INVITER) == settings.get("referral_reward")
    assert repo.referral_stats(INVITER) == (1, 1)


@pytest.mark.asyncio
async def test_the_reward_amount_is_configurable(env):
    repo, _, settings, _ = env
    settings.set("referral_reward", 3)

    await invite(env)

    assert repo.vote_balance(INVITER) == 3


@pytest.mark.asyncio
async def test_the_inviter_is_told_about_the_reward(env):
    repo, _, _, bot = env
    await invite(env)

    assert any("Друг присоединился" in text for text in bot.direct[INVITER])


# ----------------------------------------------------------- защита от накрутки

@pytest.mark.asyncio
async def test_the_same_friend_never_pays_twice(env):
    """Повторный заход по ссылке не должен приносить второй голос."""
    repo, config, settings, bot = env
    await invite(env)

    referral.remember(repo, FRIEND, INVITER, settings)
    assert await referral.try_reward(bot, repo, config, settings, FRIEND) is None
    assert repo.vote_balance(INVITER) == 1


@pytest.mark.asyncio
async def test_a_friend_cannot_be_resold_to_another_inviter(env):
    """Один человек приносит награду одному пригласившему, и только раз."""
    repo, config, settings, bot = env
    repo.upsert_user(300, "other", "Other")
    await invite(env)

    assert referral.remember(repo, FRIEND, 300, settings) is False
    assert repo.vote_balance(300) == 0


def test_you_cannot_invite_yourself(env):
    repo, _, settings, _ = env
    assert referral.remember(repo, INVITER, INVITER, settings) is False
    assert repo.referral_stats(INVITER) == (0, 0)


def test_an_existing_user_is_not_a_new_friend(env):
    """Старый пользователь по чужой ссылке награду не приносит."""
    repo, _, settings, _ = env
    repo.upsert_user(FRIEND, "old", "Old")

    assert referral.remember(repo, FRIEND, INVITER, settings) is False


def test_an_unknown_inviter_is_ignored(env):
    repo, _, settings, _ = env
    assert referral.remember(repo, FRIEND, 999999, settings) is False


def test_referrals_can_be_switched_off(env):
    repo, _, settings, _ = env
    settings.set("referral_enabled", False)

    assert referral.remember(repo, FRIEND, INVITER, settings) is False


# ------------------------------------------------------ требование подписки

@pytest.mark.asyncio
async def test_without_a_subscription_the_reward_waits(tmp_path, monkeypatch):
    path = str(tmp_path / "sub.db")
    repo = Repo(connect(path))
    config = make_config(db_path=path, require_subscription=True)
    settings = Settings(repo.conn, config)
    settings.bootstrap()
    repo.upsert_user(INVITER, "inviter", "I")

    subscribed = {"value": False}

    async def fake_missing(bot, cfg, sets, user_id):
        return [] if subscribed["value"] else [("Батлы", "https://t.me/realed")]

    monkeypatch.setattr(referral.sponsors, "missing", fake_missing)

    referral.remember(repo, FRIEND, INVITER, settings)
    repo.upsert_user(FRIEND, "friend", "F")
    bot = FakeBot()

    assert await referral.try_reward(bot, repo, config, settings, FRIEND) is None
    assert repo.vote_balance(INVITER) == 0
    assert repo.pending_referral(FRIEND) is not None, "приглашение ждёт подписки"

    subscribed["value"] = True
    assert await referral.try_reward(bot, repo, config, settings, FRIEND) == INVITER
    assert repo.vote_balance(INVITER) == 1
    assert repo.pending_referral(FRIEND) is None


@pytest.mark.asyncio
async def test_many_friends_add_up(env):
    repo, _, _, _ = env
    for friend_id in range(200, 205):
        await invite(env, invited_id=friend_id)

    assert repo.vote_balance(INVITER) == 5
    assert repo.referral_stats(INVITER) == (5, 5)


# ------------------------------------------------------------------ ссылка

def test_the_invite_link_carries_the_inviter():
    link = links.invite_link("MyBot", 7418217143)
    assert link == "https://t.me/MyBot?start=r7418217143"
    assert links.parse_start_payload("r7418217143") == ("ref", 7418217143)


def test_a_broken_payload_is_ignored_not_crashed():
    for payload in ("r", "rabc", "r-1", "", None, "junk"):
        kind, value = links.parse_start_payload(payload)
        assert kind in {"plain", "ref", "vote", "join"}
        if kind == "ref":
            assert isinstance(value, int)
