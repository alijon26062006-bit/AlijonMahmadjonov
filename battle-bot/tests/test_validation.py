"""Ввод от человека: бот объясняет ошибку и никогда не падает."""
import sys
from datetime import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import validation as v
from services.validation import InputError


# --------------------------------------------------------------------- числа

@pytest.mark.parametrize("raw,expected", [("100", 100), ("  42  ", 42), ("0", 0), ("-5", -5)])
def test_valid_numbers_pass(raw, expected):
    assert v.as_int(raw) == expected


@pytest.mark.parametrize("raw", ["тысяча", "abc", "", "   ", "12abc", "--5", "1000₽"])
def test_bad_numbers_explain_themselves(raw):
    with pytest.raises(InputError) as caught:
        v.as_int(raw)
    assert str(caught.value), "сообщение об ошибке не должно быть пустым"


def test_spaces_inside_a_number_are_forgiven():
    """«1 000» — обычный способ записи, отказывать в нём глупо."""
    assert v.as_int("1 000") == 1000


def test_digits_of_other_alphabets_are_accepted():
    """Арабо-индийские цифры — тоже цифры, отказывать в них незачем."""
    assert v.as_int("١٢٣٤") == 1234


def test_the_message_quotes_what_the_person_typed():
    with pytest.raises(InputError, match="тысяча"):
        v.as_int("тысяча")


def test_a_decimal_gets_its_own_explanation():
    with pytest.raises(InputError, match="дробное"):
        v.as_int("10.5")


def test_bounds_are_checked():
    with pytest.raises(InputError, match="Минимум"):
        v.as_int("3", minimum=10)
    with pytest.raises(InputError, match="Максимум"):
        v.as_int("300", maximum=100)
    assert v.as_int("50", minimum=1, maximum=100) == 50


# --------------------------------------------------------------------- списки

def test_prize_list_is_parsed():
    assert v.as_int_list("1000, 500,250") == [1000, 500, 250]


def test_a_broken_item_points_at_its_position():
    with pytest.raises(InputError, match="№2"):
        v.as_int_list("1000, пятьсот, 250")


def test_too_many_items_are_refused():
    with pytest.raises(InputError, match="Максимум"):
        v.as_int_list("1,2,3,4", max_items=3)


def test_negative_prizes_are_refused():
    with pytest.raises(InputError):
        v.as_int_list("1000,-500", minimum=0)


# ---------------------------------------------------------------------- время

def test_times_are_parsed_and_sorted():
    assert v.as_times("21:00, 18:00") == [time(18, 0), time(21, 0)]


def test_hour_only_is_accepted():
    assert v.as_times("18") == [time(18, 0)]


@pytest.mark.parametrize("raw,fragment", [
    ("25:00", "час"),
    ("18:70", "минуты"),
    ("18-00", "не похоже"),
    ("вечером", "не похоже"),
    ("", "Пустое"),
])
def test_bad_times_explain_what_is_wrong(raw, fragment):
    with pytest.raises(InputError, match=fragment):
        v.as_times(raw)


def test_duplicate_times_are_refused():
    with pytest.raises(InputError, match="дважды"):
        v.as_times("18:00,18:00")


# ----------------------------------------------------------------------- ники

def test_username_is_accepted_with_or_without_at():
    assert v.as_username("@Satoorov") == "Satoorov"
    assert v.as_username("Satoorov") == "Satoorov"


@pytest.mark.parametrize("raw", ["", "@", "ник с пробелом", "@" + "x" * 40, "при-вет"])
def test_bad_usernames_are_refused(raw):
    with pytest.raises(InputError):
        v.as_username(raw)


def test_user_id_must_be_numeric():
    assert v.as_user_id("7418217143") == 7418217143
    with pytest.raises(InputError, match="числовой"):
        v.as_user_id("@Satoorov")


# --------------------------------------------------- ничто не роняет процесс

@pytest.mark.parametrize("raw", [
    "", " ", "0", "-1", "999999999999999999999", "٤٢", "🍋", "<b>xss</b>",
    "1,2,3", "18:00", "None", "null", "\n\n", "a" * 500,
])
def test_no_input_ever_raises_something_other_than_input_error(raw):
    """Что бы ни прислал человек — только InputError, никаких падений."""
    for check in (v.as_int, v.as_int_list, v.as_times, v.as_username, v.as_user_id):
        try:
            check(raw)
        except InputError:
            pass  # ожидаемо: понятное объяснение человеку
        except Exception as error:  # noqa: BLE001 - именно это и ловим
            pytest.fail(f"{check.__name__}({raw!r}) уронил бота: {type(error).__name__}: {error}")
