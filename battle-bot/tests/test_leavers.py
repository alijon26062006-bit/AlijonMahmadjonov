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


# ------------------------------------ кнопка «Проверить всех» в панели

class SweepBot:
    """Телеграм, который знает, кто сейчас в канале."""

    def __init__(self, inside: set[int]) -> None:
        self.inside = inside
        self.sent: dict[int, list[str]] = {}
        self.checks = 0

    async def get_chat_member(self, chat_id, user_id):
        self.checks += 1
        status = "member" if user_id in self.inside else "left"
        return type("M", (), {"status": status})()

    async def send_message(self, chat_id, text, reply_markup=None, **kwargs):
        self.sent.setdefault(chat_id, []).append(text)
        return None


def played(repo, user_id: int, battle_id: int = 1) -> None:
    """Человек прошёл гейт подписки: участвовал в батле."""
    repo.upsert_user(user_id, f"u{user_id}", "U")
    repo.add_participant(battle_id, user_id, f"u{user_id}")


@pytest.mark.asyncio
async def test_the_sweep_marks_those_who_are_gone(env):
    """Кнопка догоняет выходы, пропущенные пока бот лежал."""
    repo, config, settings, _, _ = env
    from datetime import datetime

    repo.create_battle(datetime.now())
    for user_id in (10, 11, 12):
        played(repo, user_id)
    bot = SweepBot(inside={10, 11})  # двенадцатый уже вышел

    checked, marked = await membership.sweep(bot, repo, config, settings, delay=0)

    assert (checked, marked) == (3, 1)
    assert repo.leaver(12) is not None
    assert repo.leaver(10) is None and repo.leaver(11) is None


@pytest.mark.asyncio
async def test_the_sweep_ignores_those_who_never_subscribed(env):
    """Нажал /start и ушёл, не подписавшись — он ничего не покидал."""
    repo, config, settings, _, _ = env
    repo.upsert_user(50, "curious", "C")  # только /start, без участия
    bot = SweepBot(inside=set())

    checked, marked = await membership.sweep(bot, repo, config, settings, delay=0)

    assert (checked, marked) == (0, 0)
    assert repo.leaver(50) is None


@pytest.mark.asyncio
async def test_a_voter_counts_as_a_verified_subscriber(env):
    """Голосовать без подписки нельзя — значит голосовавший точно был в канале."""
    repo, config, settings, _, _ = env
    from datetime import datetime, timedelta

    from config import MSK
    from core.models import Player, VoteSource

    repo.upsert_user(1, "a", "A")
    repo.upsert_user(2, "b", "B")
    repo.upsert_user(60, "voter", "V")
    deadline = datetime.now(MSK) + timedelta(hours=1)
    battle_id = repo.create_battle(deadline)
    match_id = repo.create_match(
        battle_id, 1, 1, [Player(1, "a"), Player(2, "b")],
        advance=1, is_final=False, deadline=deadline,
    )
    repo.add_vote(match_id, 60, 1, VoteSource.FREE)

    bot = SweepBot(inside=set())
    _, marked = await membership.sweep(bot, repo, config, settings, delay=0)

    assert repo.leaver(60) is not None, "голосовавший проходил гейт"
    assert marked >= 1


@pytest.mark.asyncio
async def test_the_sweep_does_not_recheck_the_already_marked(env):
    """Кто уже в списке, того второй раз дёргать незачем."""
    repo, config, settings, _, _ = env
    from datetime import datetime

    repo.create_battle(datetime.now())
    played(repo, 10)
    repo.mark_left(10, MAIN)
    bot = SweepBot(inside=set())

    checked, _ = await membership.sweep(bot, repo, config, settings, delay=0)

    assert checked == 0 and bot.checks == 0


@pytest.mark.asyncio
async def test_the_sweep_never_marks_the_admin(env):
    repo, config, settings, _, _ = env
    from datetime import datetime

    repo.create_battle(datetime.now())
    played(repo, 99)  # 99 — админ из конфига
    bot = SweepBot(inside=set())

    _, marked = await membership.sweep(bot, repo, config, settings, delay=0)

    assert marked == 0 and repo.leaver(99) is None


@pytest.mark.asyncio
async def test_a_broken_check_never_punishes(env):
    """Сеть моргнула — отметку не ставим.

    Отметка снимается только за 50⭐, поэтому ошибиться тут дороже, чем
    пропустить: пропущенного догоним следующей проверкой.
    """
    repo, config, settings, _, _ = env
    from datetime import datetime

    from aiogram.exceptions import TelegramBadRequest

    repo.create_battle(datetime.now())
    played(repo, 10)

    class Broken(SweepBot):
        async def get_chat_member(self, chat_id, user_id):
            raise TelegramBadRequest(method=None, message="Bad Gateway")

    checked, marked = await membership.sweep(Broken(set()), repo, config, settings, delay=0)

    assert checked == 1 and marked == 0
    assert repo.leaver(10) is None, "невиновный не должен платить за сбой сети"


@pytest.mark.asyncio
async def test_the_gate_still_fails_closed(env):
    """А вот голосование при сбое по-прежнему закрывается: там отказ обратим."""
    from services import subscription

    class Broken:
        async def get_chat_member(self, chat_id, user_id):
            from aiogram.exceptions import TelegramBadRequest

            raise TelegramBadRequest(method=None, message="Bad Gateway")

    assert await subscription.is_subscribed(Broken(), MAIN, 7) is False
    assert await subscription.check(Broken(), MAIN, 7) is None
