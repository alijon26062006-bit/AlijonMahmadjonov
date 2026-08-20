"""Устойчивость к сбоям: сеть моргнула — бот повторяет, а не теряет сообщение."""
import sys
from pathlib import Path

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError, TelegramServerError
from aiogram.methods import SendMessage

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from handlers import errors
from services.retry import RetryMiddleware


def network_error() -> TelegramNetworkError:
    return TelegramNetworkError(
        method=SendMessage(chat_id=1, text="t"),
        message="ServerDisconnectedError: Server disconnected",
    )


class Flaky:
    """Падает заданное число раз, потом отвечает успехом."""

    def __init__(self, failures: int, error=None) -> None:
        self.left = failures
        self.error = error or network_error()
        self.calls = 0

    async def __call__(self, bot, method):
        self.calls += 1
        if self.left:
            self.left -= 1
            raise self.error
        return "доставлено"


# --------------------------------------------------------------- повтор

@pytest.mark.asyncio
async def test_a_dropped_connection_is_retried():
    """Именно этот случай терял сообщение: Telegram оборвал соединение."""
    send = Flaky(failures=1)
    middleware = RetryMiddleware(attempts=3, delay=0)

    assert await middleware(send, bot=None, method=SendMessage(chat_id=1, text="t")) == "доставлено"
    assert send.calls == 2, "одна неудача и один успешный повтор"


@pytest.mark.asyncio
async def test_retries_stop_at_the_limit():
    send = Flaky(failures=99)
    middleware = RetryMiddleware(attempts=3, delay=0)

    with pytest.raises(TelegramNetworkError):
        await middleware(send, bot=None, method=SendMessage(chat_id=1, text="t"))
    assert send.calls == 3, "больше трёх попыток не делаем"


@pytest.mark.asyncio
async def test_a_server_error_is_retried_too():
    send = Flaky(
        failures=1,
        error=TelegramServerError(method=SendMessage(chat_id=1, text="t"), message="Bad Gateway"),
    )
    middleware = RetryMiddleware(attempts=2, delay=0)

    assert await middleware(send, bot=None, method=SendMessage(chat_id=1, text="t"))


@pytest.mark.asyncio
async def test_a_mistake_in_the_request_is_not_retried():
    """Неверный запрос повторять бессмысленно — он и со второго раза неверный."""
    send = Flaky(
        failures=1,
        error=TelegramBadRequest(method=SendMessage(chat_id=1, text="t"), message="chat not found"),
    )
    middleware = RetryMiddleware(attempts=3, delay=0)

    with pytest.raises(TelegramBadRequest):
        await middleware(send, bot=None, method=SendMessage(chat_id=1, text="t"))
    assert send.calls == 1


@pytest.mark.asyncio
async def test_a_healthy_request_goes_straight_through():
    send = Flaky(failures=0)
    middleware = RetryMiddleware(attempts=3, delay=0)

    assert await middleware(send, bot=None, method=SendMessage(chat_id=1, text="t"))
    assert send.calls == 1, "лишних запросов быть не должно"


# ------------------------------------------------- отчёты админу

def test_the_same_error_is_reported_once_in_a_while():
    """Один сбой не должен заваливать админа десятком одинаковых трейсбеков."""
    errors._reported.clear()
    first = network_error()

    assert errors._should_report(first) is True
    assert errors._should_report(network_error()) is False, "повтор в пределах паузы"


def test_a_different_error_is_reported_immediately():
    errors._reported.clear()
    errors._should_report(network_error())

    other = TelegramBadRequest(method=SendMessage(chat_id=1, text="t"), message="chat not found")
    assert errors._should_report(other) is True


def test_the_cooldown_expires():
    from datetime import datetime, timedelta, timezone

    errors._reported.clear()
    error = network_error()
    errors._should_report(error)

    signature = next(iter(errors._reported))
    errors._reported[signature] = datetime.now(timezone.utc) - timedelta(hours=1)

    assert errors._should_report(error) is True, "через паузу отчёт снова уместен"


# ------------------------------- ожидаемые ответы Telegram, а не поломки

def bad_request(text: str) -> TelegramBadRequest:
    return TelegramBadRequest(method=SendMessage(chat_id=1, text="t"), message=text)


def forbidden(text: str = "Forbidden: bot was blocked by the user"):
    from aiogram.exceptions import TelegramForbiddenError

    return TelegramForbiddenError(method=SendMessage(chat_id=1, text="t"), message=text)


@pytest.mark.parametrize("error_text", [
    "Forbidden: bot was blocked by the user",
    "Forbidden: user is deactivated",
    "Bad Request: chat not found",
])
def test_a_closed_door_is_recognised(error_text):
    """Человек заблокировал бота или удалил аккаунт — писать ему больше нельзя."""
    from services.tg import is_blocked

    assert is_blocked(bad_request(error_text)) or is_blocked(forbidden(error_text))


@pytest.mark.parametrize("error_text", [
    "Bad Request: message is not modified",
    "Bad Request: query is too old and response timeout expired",
    "Bad Request: message to edit not found",
    "Bad Request: message can't be deleted for everyone",
    "Bad Request: user is deactivated",
])
def test_everyday_telegram_answers_are_not_failures(error_text):
    """Такое случается постоянно и чинить тут нечего — админа тревожить не надо."""
    from services.tg import is_expected

    assert is_expected(bad_request(error_text)) is True


def test_a_real_failure_is_still_a_failure():
    from services.tg import is_expected

    assert is_expected(bad_request("Bad Request: BUTTON_URL_INVALID")) is False
    assert is_expected(ValueError("что-то сломалось")) is False


def test_a_blocked_user_is_forgotten_and_remembered_back(tmp_path):
    """Заблокировавших исключаем из рассылки, но возвращаем, когда напишут снова."""
    from storage.db import connect
    from storage.repo import Repo

    repo = Repo(connect(str(tmp_path / "blocked.db")))
    repo.upsert_user(1, "a", "A")
    repo.upsert_user(2, "b", "B")

    assert repo.all_user_ids() == [1, 2]

    repo.mark_blocked(2)
    assert repo.all_user_ids() == [1], "заблокировавшему больше не пишем"
    assert repo.blocked_count() == 1

    repo.upsert_user(2, "b", "B")  # человек снова написал боту
    assert repo.all_user_ids() == [1, 2], "вернулся — снова пишем"
    assert repo.blocked_count() == 0


@pytest.mark.asyncio
async def test_a_broadcast_marks_those_who_left(tmp_path):
    """На тысячах пользователей важно не долбиться в ушедших каждый раз."""
    from services import broadcast
    from storage.db import connect
    from storage.repo import Repo

    repo = Repo(connect(str(tmp_path / "cast.db")))
    for user_id in (1, 2, 3):
        repo.upsert_user(user_id, f"n{user_id}", "N")

    class Bot:
        async def send_message(self, chat_id=None, **kwargs):
            if chat_id == 2:
                raise forbidden()

    report = await broadcast.run(
        Bot(), broadcast.Draft(text="привет"), [1, 2, 3], delay=0, repo=repo
    )

    assert report.sent == 2 and report.blocked == 1
    assert repo.all_user_ids() == [1, 3], "следующая рассылка его уже не тронет"


@pytest.mark.asyncio
async def test_a_blocked_user_does_not_break_battle_notifications(tmp_path):
    """Один заблокировавший не должен мешать остальным получить итоги."""
    from core.engine import BattleEngine
    from storage.db import connect
    from storage.repo import Repo
    from tests.test_engine import FakeBot, join_users, make_config

    path = str(tmp_path / "engine.db")
    repo = Repo(connect(path))
    config = make_config(db_path=path)

    class PartlyBlocked(FakeBot):
        async def send_message(self, chat_id, text, reply_markup=None, **kwargs):
            if chat_id == 2:
                raise forbidden()
            return await super().send_message(chat_id, text, reply_markup, **kwargs)

    bot = PartlyBlocked()
    engine = BattleEngine(bot, repo, config)
    await join_users(engine, repo, 4)

    assert repo.get_user(2)["is_blocked"] == 1, "отмечен как заблокировавший"
    assert bot.direct.get(1), "остальные получили свои сообщения"
    assert bot.direct.get(3)


# --------------------------------------------------- флуд-контроль Telegram

@pytest.mark.asyncio
async def test_flood_control_is_waited_out_not_treated_as_a_failure():
    """На тысячах пользователей Telegram просит подождать — это норма."""
    from aiogram.exceptions import TelegramRetryAfter

    from services.retry import RetryMiddleware

    calls = {"n": 0}

    async def send(bot, method):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TelegramRetryAfter(
                method=SendMessage(chat_id=1, text="t"),
                message="Too Many Requests: retry after 0",
                retry_after=0,
            )
        return "доставлено"

    middleware = RetryMiddleware(attempts=3, delay=0)
    assert await middleware(send, bot=None, method=SendMessage(chat_id=1, text="t")) == "доставлено"
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_an_absurd_flood_wait_is_not_slept_through():
    """Ждать час внутри обработчика нельзя — отдаём ошибку наверх."""
    from aiogram.exceptions import TelegramRetryAfter

    from services.retry import RetryMiddleware

    async def send(bot, method):
        raise TelegramRetryAfter(
            method=SendMessage(chat_id=1, text="t"),
            message="Too Many Requests: retry after 3600",
            retry_after=3600,
        )

    with pytest.raises(TelegramRetryAfter):
        await RetryMiddleware(attempts=3, delay=0)(
            send, bot=None, method=SendMessage(chat_id=1, text="t")
        )


def test_the_database_waits_instead_of_failing_when_busy(tmp_path):
    """«database is locked» под нагрузкой лечится ожиданием, а не падением."""
    from storage.db import connect

    conn = connect(str(tmp_path / "busy.db"))
    timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]

    assert timeout >= 5000
