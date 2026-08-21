"""Общие приготовления для всех тестов."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import subscription


@pytest.fixture(autouse=True)
def clean_subscription_cache():
    """Кэш подписки живёт в процессе — между тестами он мешает."""
    subscription.forget()
    yield
    subscription.forget()
