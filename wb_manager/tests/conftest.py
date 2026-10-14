"""Фикстуры: управляемые часы и фабрика клиента WB."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable

import pytest

from tests.helpers import FakeClock, NoJitter, make_settings, personal_token
from wbm.wb_client.client import WBClient
from wbm.wb_client.ratelimit import RateLimiterRegistry

ClientFactory = Callable[..., WBClient]
"""Создаёт клиента: factory(token=None, **настройки WB). Все клиенты теста делят часы и лимиты."""


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def registry(clock: FakeClock) -> RateLimiterRegistry:
    return RateLimiterRegistry(clock)


@pytest.fixture
async def make_client(
    clock: FakeClock, registry: RateLimiterRegistry
) -> AsyncIterator[ClientFactory]:
    created: list[WBClient] = []

    def factory(token: str | None = None, **settings: object) -> WBClient:
        client = WBClient(
            token or personal_token(),
            make_settings(**settings),
            limiters=registry,
            sleep=clock.sleep,
            rng=NoJitter(),
        )
        created.append(client)
        return client

    yield factory
    for client in created:
        await client.aclose()
