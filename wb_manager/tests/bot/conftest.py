"""Бот и воркер на SQLite + фиктивный WB."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.helpers import FakeClock, make_settings
from wbm.bot.services import BotServices
from wbm.db.base import Base
from wbm.db.session import make_engine, make_sessionmaker
from wbm.security.crypto import TokenCipher, generate_key
from wbm.wb_client.ratelimit import RateLimiterRegistry


@pytest.fixture
async def sessions(tmp_path: Path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = make_engine(f"sqlite+aiosqlite:///{tmp_path / 'bot.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield make_sessionmaker(engine)
    await engine.dispose()


@pytest.fixture
def cipher() -> TokenCipher:
    return TokenCipher([generate_key()])


@pytest.fixture
def services(sessions: async_sessionmaker[AsyncSession], cipher: TokenCipher) -> BotServices:
    return BotServices(
        sessions,
        cipher,
        make_settings(max_retries=0),
        limiters=RateLimiterRegistry(FakeClock()),
    )
