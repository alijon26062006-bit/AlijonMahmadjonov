"""Расписание: когда подводить итоги раунда."""
import sys
from datetime import datetime, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import MSK, _parse_times
from core.scheduler import (
    FALLBACK_INTERVAL, first_deadline, next_deadline,
)

TIMES = [time(18, 0), time(19, 30), time(21, 0)]


def test_the_nearest_slot_is_taken():
    assert next_deadline(datetime(2026, 8, 20, 9, 39), TIMES) == datetime(2026, 8, 20, 18, 0)


def test_a_passed_slot_is_skipped():
    """Батл создаёт админ в любой момент — берём следующий подходящий слот."""
    assert next_deadline(datetime(2026, 8, 20, 18, 30), TIMES) == datetime(2026, 8, 20, 19, 30)
    assert next_deadline(datetime(2026, 8, 20, 20, 0), TIMES) == datetime(2026, 8, 20, 21, 0)


def test_a_slot_too_close_is_skipped():
    """До 19:30 пять минут — голосовать некогда, берём следующий."""
    assert next_deadline(datetime(2026, 8, 20, 19, 26), TIMES) == datetime(2026, 8, 20, 21, 0)


def test_when_the_day_is_over_a_fixed_interval_is_used():
    now = datetime(2026, 8, 20, 23, 50)
    assert next_deadline(now, TIMES) == now + FALLBACK_INTERVAL


def test_an_empty_schedule_falls_back_too():
    now = datetime(2026, 8, 20, 12, 0)
    assert next_deadline(now, []) == now + FALLBACK_INTERVAL


def test_the_order_of_times_does_not_matter():
    messy = [time(21, 0), time(18, 0), time(19, 30)]
    assert next_deadline(datetime(2026, 8, 20, 9, 0), messy) == datetime(2026, 8, 20, 18, 0)


# ------------------------------------------- первый раунд идёт до утра

def moment(text: str) -> datetime:
    return datetime.strptime(f"2026-08-21 {text}", "%Y-%m-%d %H:%M").replace(tzinfo=MSK)


EVENING = _parse_times("18:00,19:30,21:00,22:15,23:30")


def test_a_battle_started_in_the_morning_ends_the_same_day():
    assert first_deadline(moment("09:00"), EVENING) == moment("18:00")


def test_a_battle_started_after_the_evening_final_ends_tomorrow():
    """Главное: созданный в 21:05 батл не должен сгореть за тот же вечер."""
    deadline = first_deadline(moment("21:05"), EVENING)

    assert deadline.day == 22 and deadline.hour == 18


def test_the_slot_burns_if_it_is_almost_here():
    """До 18:00 осталось пять минут — люди не успеют, ждём завтра."""
    deadline = first_deadline(moment("17:55"), EVENING)

    assert deadline.day == 22 and deadline.hour == 18


def test_the_first_round_ignores_later_slots():
    """Ближайший слот в 22:15, но первый раунд идёт до первого времени."""
    assert first_deadline(moment("21:05"), EVENING) != moment("22:15")


def test_later_rounds_still_take_the_nearest_slot():
    """Второй раунд после итогов в 18:00 — в тот же вечер, а не завтра."""
    assert next_deadline(moment("18:00"), EVENING) == moment("19:30")


def test_without_any_times_the_round_gets_a_fixed_length():
    now = moment("21:05")
    assert first_deadline(now, []) == now + FALLBACK_INTERVAL
