"""Переводы: ничего не потеряно и числа согласованы со словами."""

import pytest

from duel import i18n


def test_every_russian_line_has_a_tajik_one():
    """Пропущенный перевод молча подменяется русским — заметить это в игре
    почти невозможно, поэтому сверяем списками."""
    missing = sorted(k for k in i18n.STRINGS["ru"] if k not in i18n.STRINGS["tg"])
    assert missing == []


def test_no_extra_lines_hanging_in_tajik():
    extra = sorted(k for k in i18n.STRINGS["tg"] if k not in i18n.STRINGS["ru"])
    assert extra == []


def test_nothing_is_left_empty():
    for lang, table in i18n.STRINGS.items():
        for key, value in table.items():
            assert value.strip(), f"{lang}: пустая строка {key}"


@pytest.mark.parametrize("word", ["online.searching", "online.playing"])
def test_counted_words_have_both_forms(word):
    """«1 ищут соперника» режет глаз — для таких слов нужны обе формы."""
    for lang in i18n.LANGS:
        assert i18n.t(f"ui.{word}.one", lang) != f"ui.{word}.one"
        assert i18n.t(f"ui.{word}.many", lang) != f"ui.{word}.many"
        assert i18n.t(f"ui.{word}.one", lang) != i18n.t(f"ui.{word}.many", lang)


def test_app_gets_its_strings_without_the_prefix():
    strings = i18n.ui_strings("ru")
    assert "play" in strings and "ui.play" not in strings
    assert strings["play"] == i18n.t("ui.play")
    assert not any(key.startswith("bot.") for key in strings), "боту — своё, игре — своё"


def test_app_strings_are_complete_in_both_languages():
    assert set(i18n.ui_strings("ru")) == set(i18n.ui_strings("tg"))


def test_language_of_telegram_is_understood():
    assert i18n.normalize("ru-RU") == "ru"
    assert i18n.normalize("tg") == "tg"
    assert i18n.normalize("en-US") == "ru", "незнакомый язык — говорим по-русски"
    assert i18n.normalize(None) == "ru"
    assert i18n.normalize("") == "ru"


def test_missing_key_returns_itself_and_does_not_crash():
    assert i18n.t("ui.такого.нет") == "ui.такого.нет"


def test_placeholders_are_filled():
    text = i18n.t("bot.result.win", "ru", opponent="Фирдавс")
    assert "Фирдавс" in text and "{" not in text


def test_titles_are_translated():
    assert i18n.title("мастер", "tg") == "устод"
    assert i18n.title("мастер", "ru") == "мастер"
