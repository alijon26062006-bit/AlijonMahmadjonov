"""База для тестов: SQLite в файле всегда, плюс настоящий MySQL, если задан WBM_TEST_MYSQL_URL.

Пример: WBM_TEST_MYSQL_URL=mysql+aiomysql://wbm:wbmpass@127.0.0.1:3306/wbm_test?charset=utf8mb4
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from wbm.db.base import Base
from wbm.db.session import make_engine, make_sessionmaker

MYSQL_URL = os.environ.get("WBM_TEST_MYSQL_URL")

_BACKENDS = [
    pytest.param("sqlite", id="sqlite"),
    pytest.param(
        "mysql",
        id="mysql",
        marks=[
            pytest.mark.mysql,
            pytest.mark.skipif(not MYSQL_URL, reason="WBM_TEST_MYSQL_URL не задан"),
        ],
    ),
]


def backend_url(backend: str, tmp_path: Path) -> str:
    if backend == "mysql":
        assert MYSQL_URL is not None
        return MYSQL_URL
    return f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"


@pytest.fixture(params=_BACKENDS)
async def engine(request: pytest.FixtureRequest, tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    engine = make_engine(backend_url(request.param, tmp_path))
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return make_sessionmaker(engine)
