"""Заявки на вступление в канал: автоприём и «принять всех»."""
import sys
from pathlib import Path

import pytest
from aiogram.exceptions import TelegramBadRequest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from handlers import join_requests
from services import panel_ui
from storage.db import connect
from storage.repo import Repo
from storage.settings import Settings
from tests.test_engine import make_config

CHANNEL = -1003775036903


class Bot:
    """Считает одобрения и умеет отказывать так же, как Telegram."""

    def __init__(self, fail_on=(), gone=()) -> None:
        self.approved: list[int] = []
        self.fail_on = set(fail_on)
        self.gone = set(gone)

    async def approve_chat_join_request(self, chat_id, user_id):
        if user_id in self.gone:
            raise TelegramBadRequest(
                method=None, message="Bad Request: USER_ALREADY_PARTICIPANT"
            )
        if user_id in self.fail_on:
            raise TelegramBadRequest(method=None, message="Bad Request: CHAT_ADMIN_REQUIRED")
        self.approved.append(user_id)


class Event:
    def __init__(self, user_id: int, username: str = "nick") -> None:
        self.chat = type("C", (), {"id": CHANNEL, "title": "Канал"})()
        self.from_user = type(
            "U", (), {"id": user_id, "username": username, "first_name": "Имя"}
        )()


@pytest.fixture()
def env(tmp_path):
    path = str(tmp_path / "joins.db")
    repo = Repo(connect(path))
    config = make_config(db_path=path)
    settings = Settings(repo.conn, config)
    settings.bootstrap()
    return repo, settings, Bot()


def fill(repo: Repo, count: int, start: int = 1) -> None:
    for user_id in range(start, start + count):
        repo.add_join_request(CHANNEL, user_id, f"nick{user_id}", "Имя")


# ------------------------------------------------------------- запись

@pytest.mark.asyncio
async def test_a_request_is_written_down(env):
    """Telegram не отдаёт список заявок — бот ведёт свой."""
    repo, settings, bot = env
    settings.set("join_auto_approve", False)

    await join_requests.new_request(Event(7), bot, repo, settings)

    assert len(repo.pending_join_requests()) == 1
    assert bot.approved == [], "автоприём выключен — принимать не должны"


@pytest.mark.asyncio
async def test_auto_approve_takes_it_at_once(env):
    repo, settings, bot = env

    await join_requests.new_request(Event(7), bot, repo, settings)

    assert bot.approved == [7]
    assert repo.pending_join_requests() == []


@pytest.mark.asyncio
async def test_a_repeated_request_waits_again(env):
    """Человек отозвал заявку и подал снова — она снова ждёт."""
    repo, settings, bot = env
    settings.set("join_auto_approve", False)

    await join_requests.new_request(Event(7), bot, repo, settings)
    repo.close_join_request(CHANNEL, 7, "approved")
    await join_requests.new_request(Event(7), bot, repo, settings)

    assert len(repo.pending_join_requests()) == 1


# --------------------------------------------------------- принять всех

@pytest.mark.asyncio
async def test_everyone_is_approved_by_one_button(env):
    repo, _, bot = env
    fill(repo, 5)
    join_requests.PACE = 0

    done, failed = await join_requests.approve_all(bot, repo)

    assert (done, failed) == (5, 0)
    assert len(bot.approved) == 5
    assert repo.pending_join_requests() == []


@pytest.mark.asyncio
async def test_a_failed_one_stays_waiting(env):
    """Бота лишили прав на середине — остальное не теряем, отказ виден."""
    repo, _, _ = env
    fill(repo, 4)
    join_requests.PACE = 0
    bot = Bot(fail_on=[2, 3])

    done, failed = await join_requests.approve_all(bot, repo)

    assert (done, failed) == (2, 2)
    assert {int(row["user_id"]) for row in repo.pending_join_requests()} == {2, 3}


@pytest.mark.asyncio
async def test_someone_already_inside_is_crossed_out(env):
    """Человек вступил сам — заявку просто вычёркиваем, а не считаем ошибкой."""
    repo, _, _ = env
    fill(repo, 3)
    join_requests.PACE = 0
    bot = Bot(gone=[2])

    done, failed = await join_requests.approve_all(bot, repo)

    assert (done, failed) == (3, 0)
    assert repo.pending_join_requests() == []


@pytest.mark.asyncio
async def test_a_person_is_approved_once(env):
    """Автоприём и «принять всех» могли столкнуться на одном человеке."""
    repo, _, bot = env
    fill(repo, 1)

    assert repo.close_join_request(CHANNEL, 1, "approved") is True
    assert repo.close_join_request(CHANNEL, 1, "approved") is False


@pytest.mark.asyncio
async def test_progress_is_reported(env):
    repo, _, bot = env
    fill(repo, 10)
    join_requests.PACE = 0
    seen = []

    async def report(index, total, done, failed):
        seen.append((index, total))

    await join_requests.approve_all(bot, repo, report=report, every=4)

    assert seen == [(4, 10), (8, 10)]


# ------------------------------------------------------------- панель

def test_the_panel_counts_and_warns(env):
    repo, _, _ = env
    fill(repo, 3)
    waiting, approved = repo.join_request_stats()

    text, markup = panel_ui.join_requests(waiting, approved, True, repo.pending_join_requests())

    assert "Ждут: <b>3</b>" in text
    assert "поданные до этого" in text, "честно сказано, чего бот не видит"
    actions = [b.callback_data for row in markup.inline_keyboard for b in row]
    assert "p:joins:all" in actions


def test_without_requests_there_is_no_button(env):
    repo, _, _ = env

    _, markup = panel_ui.join_requests(0, 0, False, [])

    actions = [b.callback_data for row in markup.inline_keyboard for b in row]
    assert "p:joins:all" not in actions


# ------------------------------------------- впустить по нажатию в боте

class GateBot(Bot):
    """Бот, который умеет отвечать и про подписку."""

    def __init__(self, has_request=True) -> None:
        super().__init__()
        self.has_request = has_request

    async def approve_chat_join_request(self, chat_id, user_id):
        if not self.has_request:
            raise TelegramBadRequest(
                method=None, message="Bad Request: HIDE_REQUESTER_MISSING"
            )
        self.approved.append(user_id)


@pytest.mark.asyncio
async def test_a_waiting_person_is_let_in_by_pressing_in_the_bot(env):
    """Заявку по чужой ссылке бот не видит в списке — но принять может.

    ID появляется в тот момент, когда человек нажимает «Я подписался».
    """
    _, settings, _ = env
    config = make_config(channel_id=CHANNEL)
    bot = GateBot()

    assert await join_requests.let_in(bot, config, settings, 777) is True
    assert bot.approved == [777]


@pytest.mark.asyncio
async def test_without_a_request_nothing_happens(env):
    _, settings, _ = env
    config = make_config(channel_id=CHANNEL)

    assert await join_requests.let_in(GateBot(has_request=False), config, settings, 777) is False


@pytest.mark.asyncio
async def test_a_broken_bot_does_not_break_the_gate(env):
    """Приём заявки — попутная услуга: она не вправе сломать голосование."""
    _, settings, _ = env
    config = make_config(channel_id=CHANNEL)

    class Broken:
        async def approve_chat_join_request(self, chat_id, user_id):
            raise RuntimeError("что угодно")

    assert await join_requests.let_in(Broken(), config, settings, 777) is False
