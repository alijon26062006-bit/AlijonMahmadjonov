"""Публикация в канал: лимиты Telegram и откат на обычные эмодзи."""
import sys
from datetime import datetime
from pathlib import Path

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import SendMessage

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.models import Player
from services.channel import ChannelPublisher
from storage.db import connect
from storage.repo import Repo
from tests.test_engine import FakeMessage, make_config

CHANNEL = -1001234567890


def error(text: str) -> TelegramBadRequest:
    return TelegramBadRequest(method=SendMessage(chat_id=1, text="t"), message=text)


class FlakyBot:
    """Падает заданными ошибками, потом отвечает успехом."""

    def __init__(self, failures: list[Exception]) -> None:
        self.failures = failures
        self.calls = 0

    async def send_message(self, **kwargs):
        self.calls += 1
        if self.failures:
            raise self.failures.pop(0)
        return FakeMessage(500)


@pytest.fixture()
def publisher_factory(tmp_path):
    def build(failures: list[Exception]):
        repo = Repo(connect(str(tmp_path / "channel.db")))
        config = make_config(db_path=str(tmp_path / "channel.db"), channel_id=CHANNEL)
        skip: set[int] = set()
        bot = FlakyBot(failures)
        return ChannelPublisher(bot, repo, config, skip), bot, skip

    return build


@pytest.mark.asyncio
async def test_premium_emoji_rejection_disables_them_for_the_channel(publisher_factory):
    """Нет Fragment-username — Telegram откажет. Пост должен выйти обычными."""
    publisher, bot, skip = publisher_factory([error("Bad Request: CUSTOM_EMOJI_INVALID")])

    message = await publisher._send("🏆 итоги")

    assert message is not None, "пост обязан выйти, пусть и без премиум-эмодзи"
    assert bot.calls == 2, "одна неудачная попытка и один повтор"
    assert CHANNEL in skip, "премиум-эмодзи отключены для канала"


@pytest.mark.asyncio
async def test_the_channel_is_disabled_only_once(publisher_factory):
    """Второй такой же отказ уже не считается поводом для повтора."""
    publisher, bot, skip = publisher_factory(
        [error("CUSTOM_EMOJI_INVALID"), error("CUSTOM_EMOJI_INVALID")]
    )

    await publisher._send("🏆 итоги")

    assert CHANNEL in skip
    assert bot.calls == 3, "повтор один, дальше обычная обработка ошибки"


@pytest.mark.asyncio
async def test_other_errors_do_not_touch_the_emoji_setting(publisher_factory):
    publisher, bot, skip = publisher_factory([error("Bad Request: chat not found")])

    await publisher._send("🏆 итоги")

    assert CHANNEL not in skip, "чужая ошибка не должна отключать эмодзи"


@pytest.mark.asyncio
async def test_a_hopeless_send_gives_up_instead_of_hanging(publisher_factory):
    publisher, bot, _ = publisher_factory([error("chat not found")] * 5)

    assert await publisher._send("текст") is None
    assert bot.calls == 3, "три попытки и выход"
