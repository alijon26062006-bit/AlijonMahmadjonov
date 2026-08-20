"""Автопилот: напоминает вовремя, не повторяется и не роняет бота."""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import MSK
from core.autopilot import Autopilot, parse_hours
from core.engine import BattleEngine
from storage.db import connect
from storage.repo import Repo
from storage.settings import Settings
from tests.test_engine import FakeBot, join_users, make_config


class Bot(FakeBot):
    """Фейковый бот с методом send_message, как у автопилота."""

    async def send_message(self, chat_id=None, text="", **kwargs):
        return await super().send_message(chat_id, text, **kwargs)


@pytest.fixture()
def env(tmp_path):
    path = str(tmp_path / "auto.db")
    repo = Repo(connect(path))
    config = make_config(db_path=path)
    settings = Settings(repo.conn, config)
    settings.bootstrap()
    bot = Bot()
    engine = BattleEngine(bot, repo, config)
    return bot, repo, config, settings, Autopilot(bot, repo, config, settings, engine)


def move_deadline(repo: Repo, hours: float) -> None:
    """Поставить дедлайн так, будто до него осталось столько-то часов."""
    battle = repo.current_battle()
    repo.extend_deadlines(int(battle["id"]), datetime.now(MSK) + timedelta(hours=hours))


# --------------------------------------------------------- разбор настройки

@pytest.mark.parametrize("raw,expected", [
    ("3,1", [3, 1]),
    ("1, 3, 6", [6, 3, 1]),
    ("", []),
    ("мусор", []),
    ("3,3,1", [3, 1]),
    ("0,100,2", [2]),
])
def test_reminder_hours_are_read_forgivingly(raw, expected):
    """Мусор в настройке не должен останавливать автопилот."""
    assert parse_hours(raw) == expected


# -------------------------------------------------------------- напоминания

@pytest.mark.asyncio
async def test_a_reminder_goes_out_in_its_window(env):
    bot, repo, _, _, auto = env
    await join_users(auto.engine, repo, 2)
    move_deadline(repo, 1.0)

    await auto.tick()

    assert any("Остался последний час" in text for text in bot.channel_posts)


@pytest.mark.asyncio
async def test_the_same_reminder_never_repeats(env):
    """Тик идёт раз в минуту — без защиты канал завалило бы напоминаниями."""
    bot, repo, _, _, auto = env
    await join_users(auto.engine, repo, 2)
    move_deadline(repo, 1.0)

    for _ in range(5):
        await auto.tick()

    reminders = [t for t in bot.channel_posts if "Остался последний час" in t]
    assert len(reminders) == 1


@pytest.mark.asyncio
async def test_nothing_is_sent_far_from_the_deadline(env):
    bot, repo, _, _, auto = env
    await join_users(auto.engine, repo, 2)
    move_deadline(repo, 10.0)
    before = len(bot.channel_posts)

    await auto.tick()

    assert len(bot.channel_posts) == before


@pytest.mark.asyncio
async def test_nothing_is_sent_after_the_deadline(env):
    bot, repo, _, _, auto = env
    await join_users(auto.engine, repo, 2)
    move_deadline(repo, -1.0)
    before = len(bot.channel_posts)

    await auto.tick()

    assert len(bot.channel_posts) == before


@pytest.mark.asyncio
async def test_participants_get_a_personal_nudge_with_their_link(env):
    bot, repo, config, _, auto = env
    await join_users(auto.engine, repo, 2)
    move_deadline(repo, 1.0)

    await auto.tick()

    letter = "".join(bot.direct[1])
    assert "До итогов" in letter
    assert f"{config.bot_username}?start=v1" in letter, "ссылка для голосующих"


@pytest.mark.asyncio
async def test_a_new_round_gets_its_own_reminder(env):
    """Ключ включает номер раунда — иначе второй раунд остался бы без напоминания."""
    bot, repo, _, _, auto = env
    await join_users(auto.engine, repo, 2)
    move_deadline(repo, 1.0)
    await auto.tick()

    repo.set_round(1, 2, datetime.now(MSK) + timedelta(hours=1))
    await auto.tick()

    reminders = [t for t in bot.channel_posts if "Остался последний час" in t]
    assert len(reminders) == 2


# ------------------------------------------------------------------ реклама

@pytest.mark.asyncio
async def test_a_promo_is_published(env):
    bot, repo, _, _, auto = env
    repo.add_promo("Лучшие батлы тут!", "Перейти", "https://t.me/realed")

    await auto.tick()

    assert any("Лучшие батлы тут!" in text for text in bot.channel_posts)


@pytest.mark.asyncio
async def test_a_promo_is_not_repeated_within_its_interval(env):
    bot, repo, _, _, auto = env
    repo.add_promo("Реклама", None, None)

    for _ in range(10):
        await auto.tick()

    assert len([t for t in bot.channel_posts if t == "Реклама"]) == 1


@pytest.mark.asyncio
async def test_promos_take_turns(env):
    """Очередь идёт по кругу: следующим публикуется наименее показанный."""
    bot, repo, _, settings, auto = env
    repo.add_promo("Первый", None, None)
    repo.add_promo("Второй", None, None)

    assert repo.next_promo()["text"] == "Первый"
    repo.mark_promo_sent(1)
    assert repo.next_promo()["text"] == "Второй"
    repo.mark_promo_sent(2)
    assert repo.next_promo()["text"] == "Первый"


@pytest.mark.asyncio
async def test_a_disabled_promo_is_skipped(env):
    bot, repo, _, _, auto = env
    repo.add_promo("Выключенный", None, None)
    repo.toggle_promo(1)

    await auto.tick()

    assert not any("Выключенный" in text for text in bot.channel_posts)


@pytest.mark.asyncio
async def test_no_promos_means_nothing_happens(env):
    bot, repo, _, _, auto = env
    before = len(bot.channel_posts)

    await auto.tick()

    assert len(bot.channel_posts) == before


# -------------------------------------------------------------- выключение

@pytest.mark.asyncio
async def test_the_autopilot_can_be_switched_off(env):
    bot, repo, _, settings, auto = env
    await join_users(auto.engine, repo, 2)
    move_deadline(repo, 1.0)
    settings.set("autopilot_enabled", False)
    before = len(bot.channel_posts)

    await auto.tick()

    assert len(bot.channel_posts) == before


@pytest.mark.asyncio
async def test_one_broken_task_does_not_stop_the_others(env):
    """Сбой в напоминании не должен отменять рекламу."""
    bot, repo, _, _, auto = env
    repo.add_promo("Реклама", None, None)

    async def boom():
        raise RuntimeError("сломалось")

    auto._remind_before_deadline = boom
    await auto.tick()

    assert any("Реклама" in text for text in bot.channel_posts)
