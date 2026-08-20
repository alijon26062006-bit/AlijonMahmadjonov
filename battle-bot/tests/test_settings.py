"""Настройки в базе: перенос из .env, правка на лету, стойкость к мусору."""
import sys
from datetime import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from storage.db import connect
from storage.settings import FIELDS, Settings
from tests.test_engine import make_config


@pytest.fixture()
def env(tmp_path):
    conn = connect(str(tmp_path / "settings.db"))
    config = make_config()
    settings = Settings(conn, config)
    settings.bootstrap()
    return settings, config


def test_initial_values_come_from_env(env):
    settings, config = env
    assert settings.get("prizes") == [1000, 500, 250]
    assert settings.get("min_participants") == config.min_participants


def test_changing_a_setting_reaches_the_running_config(env):
    """Правка из панели должна работать без перезапуска бота."""
    settings, config = env
    settings.set("prizes", [2000, 1000, 500])

    assert settings.get("prizes") == [2000, 1000, 500]
    assert config.prizes == [2000, 1000, 500], "рабочий конфиг обязан обновиться"


def test_vote_price_drives_the_pack(env):
    settings, config = env
    settings.set("vote_price", 7)

    assert settings.vote_price == 7
    assert len(config.vote_packs) == 1
    assert config.vote_packs[0].votes == 1
    assert config.vote_packs[0].stars == 7


def test_round_times_survive_a_round_trip(env):
    settings, _ = env
    settings.set("round_times", [time(18, 0), time(20, 30)])
    assert settings.get("round_times") == [time(18, 0), time(20, 30)]


def test_flags_survive_a_round_trip(env):
    settings, config = env
    settings.set("require_subscription", False)
    assert settings.get("require_subscription") is False
    assert config.require_subscription is False

    settings.set("require_subscription", True)
    assert config.require_subscription is True


def test_settings_persist_across_restart(tmp_path):
    path = str(tmp_path / "restart.db")
    first = Settings(connect(path), make_config())
    first.bootstrap()
    first.set("vote_price", 42)

    second = Settings(connect(path), make_config())
    second.bootstrap()  # повторный запуск не должен затирать правки

    assert second.vote_price == 42


def test_a_corrupted_value_does_not_break_the_bot(env):
    """Кто-то поправил базу руками — бот берёт значение из .env, а не падает."""
    settings, config = env
    settings.conn.execute("UPDATE settings SET value = 'не число' WHERE key = 'vote_price'")
    settings.conn.commit()

    assert isinstance(settings.get("vote_price"), int)
    settings.apply()  # и не роняет применение


def test_every_field_survives_a_round_trip(env):
    """Каждая настройка должна одинаково записываться и читаться."""
    settings, _ = env
    for key in FIELDS:
        value = settings.get(key)
        settings.set(key, value)
        assert settings.get(key) == value, f"настройка {key} испортилась при записи"
