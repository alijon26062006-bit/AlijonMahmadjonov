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


# ------------------------------------------------------------- отчёт

def test_the_report_counts_everything_the_admin_needs(env):
    repo, _, settings, _ = env
    for friend in range(200, 207):
        repo.record_referral(friend, INVITER)
    for friend in range(200, 205):
        repo.reward_referral(friend, 1)

    repo.upsert_user(300, "second", "S")
    repo.record_referral(400, 300)

    report = repo.referral_report()

    assert report["total"] == 8, "все, кто пришёл по ссылкам"
    assert report["rewarded"] == 5, "из них засчитано"
    assert report["pending"] == 3, "остальные ещё не подписались"
    assert report["share"] == 63, "доля дошедших до подписки"
    assert report["inviters"] == 2, "сколько людей вообще приглашали"
    assert report["today"] == 8 and report["week"] == 8


def test_an_empty_report_does_not_divide_by_zero(env):
    repo, _, _, _ = env
    report = repo.referral_report()

    assert report == {
        "total": 0, "rewarded": 0, "pending": 0,
        "today": 0, "week": 0, "inviters": 0, "share": 0,
    }


def test_the_top_shows_who_brings_the_most(env):
    repo, _, _, _ = env
    repo.upsert_user(300, "second", "S")

    for friend in range(200, 205):
        repo.record_referral(friend, INVITER)
        repo.reward_referral(friend, 1)
    for friend in range(400, 402):
        repo.record_referral(friend, 300)
        repo.reward_referral(friend, 1)

    top = repo.top_inviters(10)
    assert top[0]["inviter_id"] == INVITER and top[0]["rewarded"] == 5
    assert top[1]["inviter_id"] == 300 and top[1]["rewarded"] == 2


def test_the_panel_screen_shows_the_totals(env):
    from services import panel_ui

    repo, _, _, _ = env
    for friend in range(200, 204):
        repo.record_referral(friend, INVITER)
    repo.reward_referral(200, 1)

    text, _ = panel_ui.referrals(1, True, repo.referral_report(), repo.top_inviters(10))

    assert "Всего пришло по ссылкам: 4" in text
    assert "<b>1</b>" in text and "25%" in text
    assert "Ждут подписки: <b>3</b>" in text


def test_a_person_card_shows_how_many_they_brought(env):
    from services import panel_ui

    repo, _, _, _ = env
    for friend in range(200, 203):
        repo.record_referral(friend, INVITER)
    repo.reward_referral(200, 1)

    text, _ = panel_ui.person(
        repo.get_user(INVITER), repo.stats_for(INVITER), 0, repo.referral_stats(INVITER)
    )

    assert "Привёл друзей: <b>1</b> из 3" in text


def test_the_share_rounds_the_way_people_expect(env):
    """62,5% должно показываться как 63%, а не как 62% из-за округления к чётному."""
    repo, _, _, _ = env
    for friend in range(200, 208):
        repo.record_referral(friend, INVITER)
    for friend in range(200, 205):
        repo.reward_referral(friend, 1)

    assert repo.referral_report()["share"] == 63
