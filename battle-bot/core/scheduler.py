"""Расписание раундов.

Заявки принимаются до первого дедлайна (по умолчанию 18:00 МСК), дальше
раунды идут в тот же вечер по списку ROUND_TIMES. Если раундов оказалось
больше, чем заготовленных времён (очень большой батл), остаток идёт с
фиксированным интервалом.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Awaitable, Callable, Sequence

log = logging.getLogger(__name__)

FALLBACK_INTERVAL = timedelta(minutes=45)
MIN_ROUND_LENGTH = timedelta(minutes=10)


def next_deadline(now: datetime, times: Sequence[time]) -> datetime:
    """Ближайшее время подведения итогов после «сейчас».

    Батл создаёт админ в любой момент, поэтому привязка к номеру раунда не
    работает: берём ближайший слот, до которого осталось хотя бы немного
    времени. Слотов на сегодня не осталось — считаем от текущего момента.
    """
    for slot in sorted(times):
        candidate = now.replace(
            hour=slot.hour, minute=slot.minute, second=0, microsecond=0
        )
        if candidate - now >= MIN_ROUND_LENGTH:
            return candidate
    return now + FALLBACK_INTERVAL


class Ticker:
    """Фоновая задача, которая просто зовёт callback раз в N секунд."""

    def __init__(self, callback: Callable[[], Awaitable[None]], every: float = 60.0) -> None:
        self._callback = callback
        self._every = every
        self._task: asyncio.Task | None = None

    def start(self, name: str = "ticker") -> None:
        self._task = asyncio.create_task(self._run(), name=name)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self) -> None:
        while True:
            try:
                await self._callback()
            except asyncio.CancelledError:
                raise
            except Exception:  # фоновая задача не должна умирать от одной ошибки
                log.exception("Ошибка в фоновой задаче")
            await asyncio.sleep(self._every)


class DeadlineWatcher:
    """Фоновая задача: раз в минуту проверяет, не пора ли подводить итоги."""

    def __init__(
        self,
        due_deadline: Callable[[], datetime | None],
        on_due: Callable[[], Awaitable[None]],
        tick: float = 30.0,
    ) -> None:
        self._due_deadline = due_deadline
        self._on_due = on_due
        self._tick = tick
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="deadline-watcher")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self) -> None:
        while True:
            try:
                deadline = self._due_deadline()
                if deadline is not None and datetime.now(deadline.tzinfo) >= deadline:
                    await self._on_due()
            except asyncio.CancelledError:
                raise
            except Exception:  # фоновая задача не должна умирать от одной ошибки
                log.exception("Ошибка при подведении итогов раунда")
            await asyncio.sleep(self._tick)
