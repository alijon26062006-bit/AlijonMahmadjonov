import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot import db as db_module  # noqa: E402
from bot.config import Config  # noqa: E402


@pytest.fixture
def conn(tmp_path):
    connection = db_module.connect(tmp_path / "test.db")
    yield connection
    connection.close()


@pytest.fixture
def config(tmp_path):
    from bot.config import _first_existing, FONT_CANDIDATES, FONT_BOLD_CANDIDATES

    return Config(
        telegram_token="x",
        allowed_user_ids=frozenset({1}),
        openai_api_key="x",
        anthropic_api_key="x",
        data_dir=tmp_path / "data",
        font_path=_first_existing(FONT_CANDIDATES),
        font_bold_path=_first_existing(FONT_BOLD_CANDIDATES),
    )
