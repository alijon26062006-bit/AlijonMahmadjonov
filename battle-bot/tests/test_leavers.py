"""Штраф за выход из канала: забрал приз и отписался — вернись за звёзды."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.engine import BattleEngine
from handlers import membership, payments
from services import panel_ui, texts
from storage.db import connect
from storage.repo import Repo
from storage.settings import Settings
from tests.test_engine import FakeBot, make_config

MAIN = -1001111111111
OTHER = -1009999999999


class Member:
    def __init__(self, status, user, is_member=True) -> None:
        self.status = status
        self.user = user
        self.is_member = is_member


class User:
    def __init__(self, user_id, is_bot=False) -> None:
        self.id = user_id
        self.is_bot = is_bot
        self.username = f"u{user_id}"
        self.first_name = "U"


class Event:
    def __init__(self, chat_id, user_id, was="member", now="left", is_bot=False) -> None:
        self.chat = type("C", (), {"id": chat_id})()
        user = User(user_id, is_bot)
        self.old_chat_member = Member(was, user)
        self.new_chat_member = Member(now, user)


class Bot:
    def __init__(self) -> None:
        self.sent: dict[int, list[str]] = {}

    async def send_message(self, chat_id, text, reply_markup=None, **kwargs):
        self.sent.setdefault(chat_id, []).append(text)
        return None


@pytest.fixture()
def env(tmp_path):
    path = str(tmp_path / "leave.db")
    repo = Repo(connect(path))
    config = make_config(db_path=path, admin_ids=[99])
    settings = Settings(repo.conn, config)
    settings.bootstrap()
    settings.set("main_channel_id", MAIN)
    return repo, config, settings, Bot(), BattleEngine(FakeBot(), repo, config, settings=settings)


# ------------------------------------------------------- ловим сам выход

@pytest.mark.asyncio
async def test_leaving_the_main_channel_is_recorded(env):
    repo, config, settings, bot, _ = env

    await membership.someone_left(Event(MAIN, 7), bot, repo, config, settings)

    left = repo.leaver(7)
    assert left is not None and int(left["times"]) == 1
    assert "вышли из канала" in bot.sent[7][0].lower()


@pytest.mark.asyncio
async def test_a_second_leave_is_counted(env):
    repo, config, settings, bot, _ = env

    await membership.someone_left(Event(MAIN, 7), bot, repo, config, settings)
    await membership.someone_left(Event(MAIN, 7), bot, repo, config, settings)

    assert int(repo.leaver(7)["times"]) == 2
    assert "2-й раз" in bot.sent[7][1]


@pytest.mark.asyncio
async def test_leaving_a_side_channel_is_ignored(env):
    """Канал не из обязательных — уход из него ничего не значит."""
    repo, config, settings, bot, _ = env

    await membership.someone_left(Event(OTHER, 7), bot, repo, config, settings)

    assert repo.leaver(7) is None


@pytest.mark.asyncio
async def test_the_admin_is_never_punished(env):
    repo, config, settings, bot, _ = env

    await membership.someone_left(Event(MAIN, 99), bot, repo, config, settings)

    assert repo.leaver(99) is None


@pytest.mark.asyncio
async def test_bots_are_ignored(env):
    repo, config, settings, bot, _ = env

    await membership.someone_left(Event(MAIN, 7, is_bot=True), bot, repo, config, settings)

    assert repo.leaver(7) is None


@pytest.mark.asyncio
async def test_a_role_change_inside_the_channel_is_not_a_leave(env):
    """Стал админом — это не выход."""
    repo, config, settings, bot, _ = env

    await membership.someone_left(
        Event(MAIN, 7, was="member", now="administrator"), bot, repo, config, settings
    )

    assert repo.leaver(7) is None


@pytest.mark.asyncio
async def test_joining_is_not_a_leave(env):
    repo, config, settings, bot, _ = env

    await membership.someone_left(
        Event(MAIN, 7, was="left", now="member"), bot, repo, config, settings
    )

    assert repo.leaver(7) is None


@pytest.mark.asyncio
async def test_the_rule_can_be_switched_off(env):
    repo, config, settings, bot, _ = env
    settings.set("leave_penalty_enabled", False)

    await membership.someone_left(Event(MAIN, 7), bot, repo, config, settings)

    assert repo.leaver(7) is None


@pytest.mark.asyncio
async def test_a_closed_bot_does_not_break_the_mark(env):
    """Человек закрыл бота — отметка всё равно должна встать."""
    repo, config, settings, _, _ = env

    class Silent:
        async def send_message(self, *args, **kwargs):
            from aiogram.exceptions import TelegramForbiddenError

            raise TelegramForbiddenError(method=None, message="bot was blocked")

    await membership.someone_left(Event(MAIN, 7), Silent(), repo, config, settings)

    assert repo.leaver(7) is not None


# --------------------------------------------- нынешние подписчики целы

@pytest.mark.asyncio
async def test_nobody_is_punished_retroactively(env):
    """Главное про обновление: подписчиков задним числом не задевает."""
    repo, config, settings, _, engine = env
    repo.upsert_user(5, "loyal", "L")

    accepted, _ = await engine.join(5, "loyal")

    assert accepted, "тот, кто не выходил, участвует как обычно"
    assert repo.leaver_count() == 0


# ----------------------------------------------------- отказ на заявке

@pytest.mark.asyncio
async def test_a_leaver_cannot_apply(env):
    repo, config, settings, bot, engine = env
    repo.upsert_user(7, "runner", "R")
    await membership.someone_left(Event(MAIN, 7), bot, repo, config, settings)

    accepted, note = await engine.join(7, "runner")

    assert not accepted
    assert "выходили из канала" in note.lower()
    assert "50⭐" in note


@pytest.mark.asyncio
async def test_resubscribing_alone_does_not_help(env):
    """Подписаться обратно недостаточно — иначе штраф ничего не значит."""
    repo, config, settings, bot, engine = env
    repo.upsert_user(7, "runner", "R")
    await membership.someone_left(Event(MAIN, 7), bot, repo, config, settings)
    await membership.someone_left(
        Event(MAIN, 7, was="left", now="member"), bot, repo, config, settings
    )

    accepted, _ = await engine.join(7, "runner")
    assert not accepted


@pytest.mark.asyncio
async def test_a_leaver_is_pulled_out_of_the_queue(env):
    repo, config, settings, bot, engine = env
    repo.upsert_user(7, "runner", "R")
    await engine.join(7, "runner")
    assert repo.in_queue(7)

    await membership.someone_left(Event(MAIN, 7), bot, repo, config, settings)

    assert not repo.in_queue(7), "в очереди вышедшему не место"


# ------------------------------------------------------------- возврат

class Payment:
    def __init__(self, payload="rejoin", charge="ch-1", amount=50) -> None:
        self.invoice_payload = payload
        self.telegram_payment_charge_id = charge
        self.total_amount = amount


class PaidMessage:
    def __init__(self, user_id, payment) -> None:
        self.from_user = type("U", (), {"id": user_id})()
        self.successful_payment = payment
        self.sent: list[str] = []

    async def answer(self, text, **kwargs):
        self.sent.append(text)


@pytest.mark.asyncio
async def test_paying_returns_access(env):
    repo, config, settings, bot, engine = env
    repo.upsert_user(7, "runner", "R")
    await membership.someone_left(Event(MAIN, 7), bot, repo, config, settings)

    message = PaidMessage(7, Payment())
    await payments.payment_done(message, repo)

    assert repo.leaver(7) is None
    accepted, _ = await engine.join(7, "runner")
    assert accepted, "после оплаты заявка снова проходит"


@pytest.mark.asyncio
async def test_a_repeated_payment_update_is_ignored(env):
    repo, config, settings, bot, _ = env
    repo.upsert_user(7, "runner", "R")
    await membership.someone_left(Event(MAIN, 7), bot, repo, config, settings)

    await payments.payment_done(PaidMessage(7, Payment()), repo)
    await membership.someone_left(Event(MAIN, 7), bot, repo, config, settings)
    second = PaidMessage(7, Payment())
    await payments.payment_done(second, repo)

    assert repo.leaver(7) is not None, "второй апдейт не должен снимать новую отметку"
    assert second.sent == []


def test_the_admin_can_forgive(env):
    repo, _, _, _, _ = env
    repo.upsert_user(7, "runner", "R")
    repo.mark_left(7, MAIN)

    assert repo.forgive_leaver(7) is True
    assert repo.leaver(7) is None


# --------------------------------------------------------------- экраны

def test_the_panel_lists_leavers(env):
    repo, _, _, _, _ = env
    repo.upsert_user(7, "runner", "R")
    repo.mark_left(7, MAIN)
    repo.mark_left(7, MAIN)

    text, markup = panel_ui.leavers(repo.leavers(), True, 50, repo.leaver_count())

    assert "@runner" in text and "выходов: 2" in text
    assert markup.inline_keyboard


def test_the_card_offers_to_return_access(env):
    repo, _, _, _, _ = env
    repo.upsert_user(7, "runner", "R")
    repo.mark_left(7, MAIN)

    _, markup = panel_ui.person(
        repo.get_user(7), repo.stats_for(7), 0, (0, 0), None, repo.leaver(7)
    )
    actions = [b.callback_data for row in markup.inline_keyboard for b in row]

    assert "p:person:left:7" in actions


def test_the_message_says_what_the_problem_is():
    body = texts.left_the_channel(1, 50)

    assert "нужен приз" in body, "человеку надо объяснить причину"
    assert "50⭐" in body
