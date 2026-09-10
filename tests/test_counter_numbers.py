"""Разбор чисел — сердце бота. Ошибётся здесь — посчитает не то."""

from counter.numbers import (
    SCALE,
    format_amount,
    parse_numbers,
    parse_single,
)


def one(text: str):
    return parse_single(text)


def test_words_russian():
    assert one("семь тысяч шестьсот") == 7600 * SCALE
    assert one("сто двадцать три") == 123 * SCALE
    assert one("девятьсот девяносто девять") == 999 * SCALE
    assert one("две тысячи") == 2000 * SCALE
    assert one("одна тысяча пятьсот") == 1500 * SCALE
    assert one("двадцать пять") == 25 * SCALE


def test_spoken_shortcut_without_thousand():
    """Так говорят на складе: «семь шестьсот» — это 7600, а не 607."""
    assert one("семь шестьсот") == 7600 * SCALE
    assert one("пять четыреста") == 5400 * SCALE
    assert one("семь шестьсот пятьдесят") == 7650 * SCALE


def test_uzbek():
    assert one("yetti ming olti yuz") == 7600 * SCALE
    assert one("yetti olti yuz") == 7600 * SCALE
    assert one("besh ming tort yuz") == 5400 * SCALE
    assert one("o'n besh") == 15 * SCALE
    assert one("yigirma bir") == 21 * SCALE


def test_digits():
    assert one("7600") == 7600 * SCALE
    assert one("7 600") == 7600 * SCALE
    assert one("7 600") == 7600 * SCALE           # неразрывный пробел
    assert one("7600,5") == 760050
    assert one("7600.5") == 760050


def test_letters_are_ignored():
    assert one("коробка семь шестьсот штук") == 7600 * SCALE
    assert one("обувь 7600 пар") == 7600 * SCALE
    assert parse_numbers("привет как дела") == []
    assert parse_numbers("") == []


def test_shtuk_is_not_a_thousand():
    """«семь штук» на складе — это семь штук, а не семь тысяч."""
    assert one("семь штук") == 7 * SCALE


def test_several_numbers_stay_separate():
    values = [found.value for found in parse_numbers("пятьсот и триста")]
    assert values == [500 * SCALE, 300 * SCALE]
    assert parse_single("пятьсот триста") is None   # два числа — спросим, какое


def test_format():
    assert format_amount(7600 * SCALE) == "7 600"
    assert format_amount(760050) == "7 600,5"
    assert format_amount(0) == "0"
    assert format_amount(-500 * SCALE) == "-500"
