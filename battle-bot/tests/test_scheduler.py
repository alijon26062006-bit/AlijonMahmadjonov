import sys
from datetime import datetime, time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.scheduler import FALLBACK_INTERVAL, deadline_for_round

TIMES = [time(18, 0), time(19, 30), time(21, 0)]


def test_first_round_closes_today_when_there_is_still_time():
    now = datetime(2026, 8, 20, 9, 39)
    assert deadline_for_round(1, now, TIMES) == datetime(2026, 8, 20, 18, 0)


def test_first_round_rolls_over_to_tomorrow_after_the_deadline():
    now = datetime(2026, 8, 20, 18, 30)
    assert deadline_for_round(1, now, TIMES) == datetime(2026, 8, 21, 18, 0)


def test_later_rounds_run_the_same_evening():
    now = datetime(2026, 8, 20, 18, 0)
    assert deadline_for_round(2, now, TIMES) == datetime(2026, 8, 20, 19, 30)
    assert deadline_for_round(3, now, TIMES) == datetime(2026, 8, 20, 21, 0)


def test_a_round_never_gets_less_than_ten_minutes():
    now = datetime(2026, 8, 20, 19, 25)  # до 19:30 всего пять минут
    assert deadline_for_round(2, now, TIMES) == now + FALLBACK_INTERVAL


def test_extra_rounds_fall_back_to_a_fixed_interval():
    now = datetime(2026, 8, 20, 21, 0)
    assert deadline_for_round(4, now, TIMES) == now + FALLBACK_INTERVAL
