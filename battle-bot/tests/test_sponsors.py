"""Обязательная подписка: какие каналы проверяются и что видит человек."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import sponsors
from storage.db import connect
from storage.repo import Repo
from storage.settings import Settings
from tests.test_engine import make_config

MAIN = -1001111111111
BATTLES = -1003775036903


@pytest.fixture()
def env(tmp_path):
    path = str(tmp_path / "sponsors.db")
    repo = Repo(connect(path))
    config = make_config(db_path=path, channel_id=BATTLES, require_subscription=True)
    settings = Settings(repo.conn, config)
    settings.bootstrap()
    return config, settings


# ------------------------------------------------------- какие каналы

def test_the_main_channel_is_required_by_default(env):
    """Подписка нужна там, где выходит анонс набора."""
    config, settings = env
    settings.set("main_channel_id", MAIN)

    assert sponsors.required(config, settings) == [MAIN]


def test_the_battle_channel_is_not_required_when_a_main_one_exists(env):
    """В канал с парами заходят по ссылке из поста — подписка там не нужна."""
    config, settings = env
    settings.set("main_channel_id", MAIN)

    assert BATTLES not in sponsors.required(config, settings)


def test_without_a_main_channel_the_battle_channel_is_used(env):
    config, settings = env
    assert sponsors.required(config, settings) == [BATTLES]


def test_an_explicit_list_wins(env):
    config, settings = env
    settings.set("main_channel_id", MAIN)
    settings.set("sponsor_channels", "-1002222222222,-1003333333333")

    assert sponsors.required(config, settings) == [-1002222222222, -1003333333333]


def test_a_messy_list_is_read_anyway(env):
    config, settings = env
    settings.set("sponsor_channels", " -1002222222222 ; -1003333333333 , мусор ")

    assert sponsors.required(config, settings) == [-1002222222222, -1003333333333]


def test_clearing_the_list_falls_back_to_the_main_channel(env):
    config, settings = env
    settings.set("main_channel_id", MAIN)
    settings.set("sponsor_channels", "")

    assert sponsors.required(config, settings) == [MAIN]


# ------------------------------------------------------------ проверка

class FakeBot:
    def __init__(self, subscribed_to: set[int]) -> None:
        self.subscribed_to = subscribed_to

    async def get_chat_member(self, chat_id, user_id):
        class Member:
            status = "member" if chat_id in self.subscribed_to else "left"

        return Member()

    async def get_chat(self, chat_id):
        class Chat:
            title = f"Канал {chat_id}"
            username = None
            invite_link = f"https://t.me/+invite{abs(chat_id)}"

        return Chat()


@pytest.mark.asyncio
async def test_a_subscriber_passes(env):
    config, settings = env
    settings.set("main_channel_id", MAIN)

    assert await sponsors.missing(FakeBot({MAIN}), config, settings, 500) == []


@pytest.mark.asyncio
async def test_a_non_subscriber_is_listed(env):
    config, settings = env
    settings.set("main_channel_id", MAIN)

    result = await sponsors.missing(FakeBot(set()), config, settings, 500)

    assert len(result) == 1
    title, url = result[0]
    assert title and url.startswith("https://t.me/")


@pytest.mark.asyncio
async def test_all_required_channels_are_checked(env):
    config, settings = env
    settings.set("sponsor_channels", f"{MAIN},{BATTLES}")

    only_one = await sponsors.missing(FakeBot({MAIN}), config, settings, 500)
    assert len(only_one) == 1, "второй канал должен остаться в списке"

    both = await sponsors.missing(FakeBot({MAIN, BATTLES}), config, settings, 500)
    assert both == []


@pytest.mark.asyncio
async def test_the_check_can_be_switched_off(env):
    config, settings = env
    settings.set("main_channel_id", MAIN)
    settings.set("require_subscription", False)

    assert await sponsors.missing(FakeBot(set()), config, settings, 500) == []


# ------------------------------------------------------------- экран

def test_the_screen_lists_every_channel_and_offers_a_retry():
    channels = [("Батлы", "https://t.me/realed"), ("Спонсор", "https://t.me/sponsor")]

    body = sponsors.text(channels)
    assert "t.me/realed" in body and "t.me/sponsor" in body
    assert "2 канала" in body

    markup = sponsors.keyboard(channels, "refresh:7")
    labels = [b.text for row in markup.inline_keyboard for b in row]
    assert len(markup.inline_keyboard) == 3, "две подписки плюс проверка"
    assert labels[-1].endswith("Я подписался")
    assert markup.inline_keyboard[-1][0].callback_data == "refresh:7"


def test_one_channel_reads_as_a_single_line():
    """Экран стоит между человеком и голосом — он должен быть коротким."""
    body = sponsors.text([("Батлы", "https://t.me/seady")])

    assert body.count("\n") == 0
    assert "t.me/seady" in body
    assert "https://" not in body.split('">')[-1], "ссылку показываем без протокола"


def test_the_wording_matches_what_the_person_is_doing():
    """Заявку подают не «чтобы проголосовать»."""
    body = sponsors.text([("Батлы", "https://t.me/seady")], "участвовать")

    assert "Чтобы участвовать" in body


def test_a_single_channel_gets_a_short_button():
    markup = sponsors.keyboard([("Батлы", "https://t.me/seady")], "join:retry")

    assert markup.inline_keyboard[0][0].text == "Подписаться ↗"


def test_a_channel_without_a_link_gets_no_broken_button():
    markup = sponsors.keyboard([("Приватный", "")], "join:retry")
    assert len(markup.inline_keyboard) == 1, "остаётся только «Я подписался»"
