"""Повтор запросов при сетевых сбоях.

Telegram изредка закрывает keep-alive соединение прямо во время запроса —
получается ServerDisconnectedError. Это не поломка бота: тот же запрос со
второй попытки проходит. Без повтора сообщение просто терялось, а человек
видел, что бот не ответил.
"""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.exceptions import (
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)

log = logging.getLogger(__name__)

TRANSIENT = (TelegramNetworkError, TelegramServerError)
MAX_FLOOD_WAIT = 60.0  # дольше ждать бессмысленно, лучше отдать ошибку наверх


class RetryMiddleware(BaseRequestMiddleware):
    """Повторяет запрос при сетевой ошибке с нарастающей паузой."""

    def __init__(self, attempts: int = 3, delay: float = 0.5) -> None:
        self.attempts = max(1, attempts)
        self.delay = delay

    async def __call__(self, make_request, bot: Bot, method):
        last: BaseException | None = None
        for attempt in range(1, self.attempts + 1):
            try:
                return await make_request(bot, method)
            except TelegramRetryAfter as error:
                # Telegram сам говорит, сколько ждать. На тысячах пользователей
                # это норма, а не сбой: пережидаем и повторяем.
                last = error
                if attempt == self.attempts or error.retry_after > MAX_FLOOD_WAIT:
                    break
                log.warning("Флуд-контроль: ждём %s c", error.retry_after)
                await asyncio.sleep(error.retry_after + 0.5)
            except TRANSIENT as error:
                last = error
                if attempt == self.attempts:
                    break
                pause = self.delay * attempt
                log.warning(
                    "Сеть подвела на %s (попытка %s из %s), повтор через %.1f c: %s",
                    type(method).__name__, attempt, self.attempts, pause, error,
                )
                await asyncio.sleep(pause)
        raise last
