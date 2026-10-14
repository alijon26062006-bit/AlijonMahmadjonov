"""Учёт лимитов WB и очередь запросов.

WB считает лимиты алгоритмом token bucket и описывает их четырьмя числами:
период, лимит, интервал, всплеск (burst). Здесь тот же bucket в форме GCRA:
каждый запрос заранее «бронирует» ближайшее разрешённое время отправки.
Брони выдаются по порядку, поэтому запросы выстраиваются в честную очередь (FIFO),
а ожидание известно до отправки — слишком долгое можно сразу отклонить.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

Clock = Callable[[], float]
_EPSILON = 1e-6


@dataclass(frozen=True, slots=True)
class RateLimit:
    """Лимит метода WB: `limit` запросов за `period_s`, интервал `interval_s`, всплеск `burst`."""

    period_s: float
    limit: int
    interval_s: float
    burst: int

    def __post_init__(self) -> None:
        if self.period_s <= 0 or self.interval_s <= 0 or self.limit < 1 or self.burst < 1:
            raise ValueError(f"Некорректный лимит: {self}")


class RateLimitWaitTooLong(Exception):
    """Внутренний сигнал: ждать дольше допустимого. Клиент превращает его в WBRateLimitError."""

    def __init__(self, wait: float) -> None:
        super().__init__(f"Ожидание {wait:.1f} с")
        self.wait = wait


class GCRALimiter:
    """Один bucket. Состояние — теоретическое время прибытия следующего запроса (TAT)."""

    def __init__(self, limit: RateLimit, clock: Clock = time.monotonic) -> None:
        self.limit = limit
        self._clock = clock
        self._interval = limit.interval_s
        self._tolerance = (limit.burst - 1) * limit.interval_s
        self._tat = float("-inf")

    def reserve(self, max_wait: float) -> float:
        """Бронирует место в очереди. Возвращает, сколько секунд ждать перед отправкой.

        Если ждать дольше `max_wait`, бронь не создаётся и бросается RateLimitWaitTooLong.
        """
        now = self._clock()
        tat = max(self._tat, now)
        wait = tat - self._tolerance - now
        if wait < _EPSILON:  # погрешность сложения float — не повод ждать
            wait = 0.0
        if wait > max_wait:
            raise RateLimitWaitTooLong(wait)
        self._tat = tat + self._interval
        return wait

    def block(self, seconds: float) -> None:
        """WB ответил 429 и попросил подождать `seconds` (X-Ratelimit-Retry)."""
        now = self._clock()
        self._tat = max(self._tat, now + max(0.0, seconds) + self._tolerance)

    def sync_remaining(self, remaining: int) -> None:
        """Подстраивается под X-Ratelimit-Remaining: сколько запросов WB разрешает без паузы.

        Только ужесточает локальный учёт — например, когда ответ 4xx засчитан WB как 10 запросов.
        """
        now = self._clock()
        target = now + self._tolerance - (max(0, remaining) - 1) * self._interval
        self._tat = max(self._tat, target)


class RateLimiterRegistry:
    """Bucket'ы по ключу (аккаунт продавца, группа лимита, тип токена).

    Лимиты WB считаются на аккаунт продавца, поэтому все клиенты одного продавца
    в процессе должны делить один реестр.
    """

    def __init__(self, clock: Clock = time.monotonic) -> None:
        self._clock = clock
        self._limiters: dict[tuple[str, str, str], GCRALimiter] = {}

    def get(self, account: str, group: str, kind: str, limit: RateLimit) -> GCRALimiter:
        key = (account, group, kind)
        limiter = self._limiters.get(key)
        if limiter is None or limiter.limit != limit:
            limiter = GCRALimiter(limit, self._clock)
            self._limiters[key] = limiter
        return limiter


DEFAULT_REGISTRY = RateLimiterRegistry()
