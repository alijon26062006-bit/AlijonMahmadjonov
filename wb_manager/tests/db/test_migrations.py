"""Миграции Alembic создают ровно ту схему, что описана в моделях, и откатываются."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from tests.db.conftest import MYSQL_URL
from wbm.db.base import Base

ROOT = Path(__file__).resolve().parents[2]


def alembic_config(url: str) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes["database_url"] = url
    config.attributes["configure_logger"] = False
    return config


def sync_url(url: str) -> str:
    return url.replace("+aiosqlite", "").replace("+aiomysql", "+pymysql")


@pytest.fixture(
    params=[
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
)
def database_url(request: pytest.FixtureRequest, tmp_path: Path) -> str:
    if request.param == "mysql":
        assert MYSQL_URL is not None
        url = MYSQL_URL
        engine = create_engine(sync_url(url))
        with engine.begin() as connection:
            Base.metadata.drop_all(connection)
            connection.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
        engine.dispose()
        return url
    return f"sqlite+aiosqlite:///{tmp_path / 'migrations.db'}"


def test_upgrade_matches_models_and_downgrade_cleans_up(database_url: str) -> None:
    config = alembic_config(database_url)

    command.upgrade(config, "head")

    engine = create_engine(sync_url(database_url))
    with engine.connect() as connection:
        diff = compare_metadata(
            MigrationContext.configure(connection, opts={"compare_type": True}), Base.metadata
        )
    assert diff == [], f"Миграции расходятся с моделями: {diff}"

    command.downgrade(config, "base")

    with engine.connect() as connection:
        assert set(inspect(connection).get_table_names()) <= {"alembic_version"}
    engine.dispose()
