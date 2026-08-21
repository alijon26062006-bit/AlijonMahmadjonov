"""Проверки на то, из-за чего бот вёл себя нестабильно.

Каждый тест здесь описывает конкретный сбой, который случался вживую.
"""
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from aiogram.exceptions import TelegramBadRequest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import MSK
from core import background
from core.engine import BattleEngine
from core.models import Player
from handlers import errors, voting
from services import subscription, ui
from storage.db import connect
from storage.repo import Repo
from storage.settings import Settings
from tests.test_engine import FakeBot, enqueue_users, make_config


def bad_request(text: str) -> TelegramBadRequest:
    from aiogram.methods import SendMessage

    return TelegramBadRequest(method=SendMessage(chat_id=1, text="t"), message=text)


# ------------------------------------- кнопка на слишком старом сообщении

class Stale:
    """Что Telegram присылает вместо сообщения, которого больше нет.

    Ни edit_text, ни edit_reply_markup, ни photo — только answer.
    """

    def __init__(self) -> None:
        self.sent: list[str] = []

    async def answer(self, text, reply_markup=None, **kwargs):
        self.sent.append(text)


class StaleCallback:
    def __init__(self, data: str, user_id: int = 500) -> None:
        self.data = data
        self.message = Stale()
        self.from_user = type("U", (), {"id": user_id, "username": "n", "first_name": "N"})()
        self.bot = None
        self.alerts: list[str] = []

    async def answer(self, text="", **kwargs):
        self.alerts.append(text)


@pytest.mark.asyncio
async def test_refreshing_a_stale_screen_does_not_crash():
    """Раньше здесь падал AttributeError и человек видел «что-то пошло не так»."""
    path = ":memory:"
    repo = Repo(connect(path))
    config = make_config(db_path=path)
    for uid in (1, 2):
        repo.upsert_user(uid, f"n{uid}", f"N{uid}")
    deadline = datetime.now(MSK) + timedelta(hours=1)
    battle_id = repo.create_battle(deadline)
    match_id = repo.create_match(
        battle_id, 1, 1, [Player(1, "n1"), Player(2, "n2")],
        advance=1, is_final=False, deadline=deadline,
    )

    callback = StaleCallback(f"refresh:{match_id}")
    await voting.refresh_votes(callback, repo, config)

    assert callback.alerts == ["Обновлено"], "кнопка обязана ответить, а не упасть"


@pytest.mark.asyncio
async def test_an_undrawable_screen_arrives_as_a_new_message():
    """Панель живёт одним сообщением: удалили его — присылаем новое."""
    class Dead:
        def __init__(self) -> None:
            self.sent: list[str] = []

        async def edit_text(self, text, reply_markup=None, **kwargs):
            raise bad_request("Bad Request: message to edit not found")

        async def answer(self, text, reply_markup=None, **kwargs):
            self.sent.append(text)

    dead = Dead()
    await ui.edit_or_send(dead, "экран", None)
    assert dead.sent == ["экран"]


def test_a_long_screen_is_clipped_instead_of_being_refused():
    """Telegram откажет от текста длиннее 4096 — обрезаем сами."""
    clipped = ui.clip("а" * 9000)
    assert len(clipped) <= ui.TEXT_LIMIT
    assert clipped.endswith(ui.CUT_MARK)


# --------------------------------------------- устаревшие данные у кнопки

@pytest.mark.asyncio
async def test_a_button_from_an_older_version_is_answered_politely():
    repo = Repo(connect(":memory:"))
    config = make_config(db_path=":memory:")
    settings = Settings(repo.conn, config)
    settings.bootstrap()

    callback = StaleCallback("vote:мусор")
    await voting.cast_vote(callback, repo, config, settings)

    assert callback.alerts and "устарела" in callback.alerts[0]


# ------------------------------------------- досрочное закрытие раунда

@pytest.mark.asyncio
async def test_a_second_close_does_not_eat_the_next_round(tmp_path):
    """Главный сбой: два вызова итогов подряд сжигали следующий раунд.

    Первый закрывает первый раунд и открывает второй. Второй вызов —
    например, кнопка админа, нажатая пока шёл подсчёт, — доходил до уже
    открытого раунда и закрывал его, не дожидаясь ни одного голоса.
    """
    path = str(tmp_path / "cascade.db")
    repo = Repo(connect(path))
    config = make_config(db_path=path, min_participants=4)
    engine = BattleEngine(FakeBot(), repo, config)

    await enqueue_users(engine, repo, 8)
    await engine.create_from_queue()
    battle_id = int(repo.current_battle()["id"])

    # время итогов первого раунда пришло
    repo.set_round(battle_id, 1, datetime.now(MSK) - timedelta(minutes=1))
    await engine.close_round()

    battle = repo.current_battle()
    assert battle is not None and int(battle["round_no"]) == 2
    open_before = len(repo.open_matches(battle_id, 2))
    assert open_before, "второй раунд должен идти"

    await engine.close_round()  # тот самый «лишний» вызов

    assert len(repo.open_matches(battle_id, 2)) == open_before, (
        "второй раунд закрылся досрочно"
    )


@pytest.mark.asyncio
async def test_the_admin_can_still_close_early(tmp_path):
    """Кнопка «Подвести итоги сейчас» обязана работать до дедлайна."""
    path = str(tmp_path / "force.db")
    repo = Repo(connect(path))
    config = make_config(db_path=path, min_participants=4)
    engine = BattleEngine(FakeBot(), repo, config)

    await enqueue_users(engine, repo, 4)
    await engine.create_from_queue()
    battle_id = int(repo.current_battle()["id"])

    await engine.close_round(force=True)

    assert not repo.open_matches(battle_id, 1), "раунд должен закрыться по кнопке"


# --------------------------------------------------- заявка не ждёт итогов

@pytest.mark.asyncio
async def test_joining_never_waits_for_a_long_round_close(tmp_path):
    """Подсчёт идёт минутами — кнопка «Принять участие» не должна висеть."""
    path = str(tmp_path / "lock.db")
    repo = Repo(connect(path))
    config = make_config(db_path=path)
    engine = BattleEngine(FakeBot(), repo, config)
    repo.upsert_user(99, "late", "L")

    async with engine._lock:  # имитируем идущий подсчёт итогов
        accepted, _ = await engine.join(99, "late")

    assert accepted, "заявка должна проходить, пока идут итоги"
    assert repo.in_queue(99)


# ----------------------------------------------------- кэш подписки

@pytest.mark.asyncio
async def test_the_subscription_answer_is_cached_for_a_while():
    """Спрашивать Telegram на каждый голос — прямой путь во флуд-контроль."""
    calls = []

    class Bot:
        async def get_chat_member(self, chat_id, user_id):
            calls.append((chat_id, user_id))
            return type("M", (), {"status": "member"})()

    bot = Bot()
    assert await subscription.is_subscribed(bot, -100, 7)
    assert await subscription.is_subscribed(bot, -100, 7)
    assert len(calls) == 1, "второй раз ответ берётся из памяти"


@pytest.mark.asyncio
async def test_a_refusal_is_never_cached():
    """Человек подписался и жмёт «Я подписался» — он должен пройти сразу."""
    answers = iter(["left", "member"])

    class Bot:
        async def get_chat_member(self, chat_id, user_id):
            return type("M", (), {"status": next(answers)})()

    bot = Bot()
    assert not await subscription.is_subscribed(bot, -100, 7)
    assert await subscription.is_subscribed(bot, -100, 7)


@pytest.mark.asyncio
async def test_the_cache_lets_go_after_its_time():
    calls = []

    class Bot:
        async def get_chat_member(self, chat_id, user_id):
            calls.append(1)
            return type("M", (), {"status": "member"})()

    bot = Bot()
    await subscription.is_subscribed(bot, -100, 7)
    subscription.remember(-100, 7, time.monotonic() - subscription.CACHE_TTL - 1)
    await subscription.is_subscribed(bot, -100, 7)

    assert len(calls) == 2, "просроченная отметка должна перепроверяться"


# ---------------------------------------------------------- журнал сбоев

def test_failures_land_in_the_journal():
    repo = Repo(connect(":memory:"))
    repo.record_error("AttributeError", "нет edit_text", "кнопка vote:1:2", 7)
    repo.record_error("Сеть", "ServerDisconnectedError", "кнопка refresh:1", 8)

    rows = repo.recent_errors()
    assert len(rows) == 2
    assert rows[0]["kind"] == "Сеть", "последние сверху"
    assert {row["kind"] for row in repo.error_summary()} == {"AttributeError", "Сеть"}


def test_the_journal_does_not_grow_forever():
    repo = Repo(connect(":memory:"))
    for index in range(repo.KEEP_ERRORS + 25):
        repo.record_error("Сбой", f"номер {index}")

    assert len(repo.recent_errors(limit=1000)) == repo.KEEP_ERRORS


@pytest.mark.asyncio
async def test_the_error_handler_writes_to_the_journal():
    repo = Repo(connect(":memory:"))
    config = make_config()

    class Update:
        message = None
        callback_query = None

    event = type("E", (), {"update": Update(), "exception": ValueError("сломалось")})()

    class Bot:
        async def send_message(self, *args, **kwargs):
            return None

    handled = await errors.catch_everything(event, Bot(), config, repo)

    assert handled is True, "бот обязан продолжить работу"
    assert repo.recent_errors()[0]["kind"] == "ValueError"


# ------------------------------------------------- здоровье фоновых задач

def test_background_report_notices_a_dead_task():
    import asyncio

    async def scenario():
        alive = asyncio.create_task(asyncio.sleep(5))
        dead = asyncio.create_task(asyncio.sleep(0))
        await asyncio.sleep(0.01)

        background.forget()
        background.register("живая", alive)
        background.register("мёртвая", dead)
        report = background.report()

        alive.cancel()
        return report

    report = asyncio.run(scenario())
    assert report == {"живая": True, "мёртвая": False}
    background.forget()


def test_an_empty_registry_is_reported_as_trouble():
    background.forget()
    assert all(state is False for state in background.report().values())
