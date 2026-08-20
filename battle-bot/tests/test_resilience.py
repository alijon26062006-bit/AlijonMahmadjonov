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
