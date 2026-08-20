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


def deadline_for_round(
    round_no: int,
    now: datetime,
    times: Sequence[time],
) -> datetime:
    """Когда закрывать голосование этого раунда."""
    if round_no <= len(times):
        candidate = now.replace(
            hour=times[round_no - 1].hour,
            minute=times[round_no - 1].minute,
            second=0,
            microsecond=0,
        )
        if round_no == 1:
            # приём заявок: если сегодняшнее время уже прошло — набираем на завтра
            if candidate <= now:
                candidate += timedelta(days=1)
            return candidate
        if candidate - now >= MIN_ROUND_LENGTH:
            return candidate
    # времён не хватило или следующее слишком близко — берём интервал от «сейчас»
    return now + FALLBACK_INTERVAL


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
