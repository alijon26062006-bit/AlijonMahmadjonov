from __future__ import annotations

import pytest

from tests.helpers import FakeClock
from wbm.wb_client.ratelimit import (
    GCRALimiter,
    RateLimit,
    RateLimiterRegistry,
    RateLimitWaitTooLong,
)

CONTENT = RateLimit(period_s=60, limit=100, interval_s=0.6, burst=5)


def test_burst_then_interval() -> None:
    clock = FakeClock()
    limiter = GCRALimiter(CONTENT, clock)

    waits = [limiter.reserve(max_wait=100) for _ in range(7)]

    assert waits[:5] == [0, 0, 0, 0, 0]
    assert waits[5] == pytest.approx(0.6)
    assert waits[6] == pytest.approx(1.2)


def test_bucket_refills_over_time() -> None:
    clock = FakeClock()
    limiter = GCRALimiter(CONTENT, clock)
    for _ in range(5):
        limiter.reserve(max_wait=100)

    clock.now += 0.6 * 5

    assert [limiter.reserve(max_wait=100) for _ in range(5)] == [0, 0, 0, 0, 0]


def test_too_long_wait_does_not_take_a_slot() -> None:
    clock = FakeClock()
    limiter = GCRALimiter(RateLimit(period_s=60, limit=1, interval_s=60, burst=1), clock)
    assert limiter.reserve(max_wait=0) == 0

    with pytest.raises(RateLimitWaitTooLong) as exc:
        limiter.reserve(max_wait=10)

    assert exc.value.wait == pytest.approx(60)
    assert limiter.reserve(max_wait=100) == pytest.approx(60)  # очередь не сдвинулась


def test_block_after_429() -> None:
    clock = FakeClock()
    limiter = GCRALimiter(CONTENT, clock)

    limiter.block(2.0)

    assert limiter.reserve(max_wait=100) == pytest.approx(2.0)
    assert limiter.reserve(max_wait=100) == pytest.approx(2.6)


def test_sync_remaining_only_tightens() -> None:
    clock = FakeClock()
    limiter = GCRALimiter(CONTENT, clock)
    limiter.reserve(max_wait=100)

    limiter.sync_remaining(0)  # WB: «без паузы больше нельзя» (например, 4xx засчитан как 10)
    assert limiter.reserve(max_wait=100) == pytest.approx(0.6)

    limiter.sync_remaining(50)  # больше, чем всплеск, — локальный учёт не ослабляем
    assert limiter.reserve(max_wait=100) == pytest.approx(1.2)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"period_s": 0, "limit": 1, "interval_s": 1, "burst": 1},
        {"period_s": 1, "limit": 0, "interval_s": 1, "burst": 1},
        {"period_s": 1, "limit": 1, "interval_s": 0, "burst": 1},
        {"period_s": 1, "limit": 1, "interval_s": 1, "burst": 0},
    ],
)
def test_rate_limit_validation(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError, match="лимит"):
        RateLimit(**kwargs)  # type: ignore[arg-type]


def test_registry_shares_bucket_per_account_group_kind() -> None:
    registry = RateLimiterRegistry(FakeClock())

    first = registry.get("seller", "content", "PERSONAL", CONTENT)

    assert registry.get("seller", "content", "PERSONAL", CONTENT) is first
    assert registry.get("other", "content", "PERSONAL", CONTENT) is not first
    assert registry.get("seller", "ping", "PERSONAL", CONTENT) is not first
