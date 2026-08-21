"""Призы: не только звёзды, но и любой текст."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.models import Slot
from services import main_post, panel_ui, prizes, texts
from services.validation import InputError


# ---------------------------------------------------------------- разбор

def test_a_prize_per_line():
    assert prizes.parse("1000\n500\nTelegram Premium") == ["1000", "500", "Telegram Premium"]


def test_the_old_comma_record_still_reads():
    """В базе уже лежит «1000,500,250» — оно обязано читаться как раньше."""
    assert prizes.parse("1000,500,250") == ["1000", "500", "250"]
    assert prizes.parse(" 2000 ; 1000 ; 500 ") == ["2000", "1000", "500"]


def test_a_comma_inside_a_text_prize_does_not_split_it():
    """«Premium, 3 месяца» — это один приз, а не два."""
    assert prizes.parse("Telegram Premium, 3 месяца") == ["Telegram Premium, 3 месяца"]


def test_a_mixed_list_keeps_commas_inside_lines():
    assert prizes.parse("1000\nРеклама в канале, закреп на неделю") == [
        "1000", "Реклама в канале, закреп на неделю",
    ]


def test_empty_input_gives_nothing():
    assert prizes.parse("") == []
    assert prizes.parse("   \n  ") == []


def test_extra_prizes_are_cut_at_the_limit():
    many = "\n".join(str(i) for i in range(prizes.MAX_PRIZES + 5))
    assert len(prizes.parse(many)) == prizes.MAX_PRIZES


def test_a_saved_list_reads_back_the_same():
    values = ["1000", "Telegram Premium, 3 месяца", "Реклама"]
    assert prizes.parse(prizes.dump(values)) == values


# -------------------------------------------------------------- как выглядит

def test_a_number_becomes_stars():
    assert prizes.label("1000") == "1000⭐"
    assert prizes.label(" 500 ") == "500⭐"


def test_text_is_shown_as_it_is():
    assert prizes.label("Telegram Premium на 3 месяца") == "Telegram Premium на 3 месяца"


def test_dangerous_text_cannot_break_the_message():
    """Приз попадает в HTML-сообщение — теги должны обезвредиться."""
    assert prizes.label("<b>жирный</b> приз") == "&lt;b&gt;жирный&lt;/b&gt; приз"

    body = texts.prizes_block(["<b>взлом</b>"])
    assert "&lt;b&gt;взлом&lt;/b&gt;" in body, "теги приза должны быть обезврежены"
    assert "<b><b>взлом" not in body


# ------------------------------------------------------------------- ввод

def test_an_empty_value_is_explained():
    with pytest.raises(InputError) as failure:
        prizes.check("   ")
    assert "с новой строки" in str(failure.value)


def test_a_too_long_prize_is_refused():
    with pytest.raises(InputError) as failure:
        prizes.check("а" * (prizes.MAX_LENGTH + 1))
    assert "слишком длинный" in str(failure.value).lower()


def test_too_many_prizes_are_refused():
    with pytest.raises(InputError) as failure:
        prizes.check("\n".join(str(i) for i in range(prizes.MAX_PRIZES + 3)))
    assert "Максимум" in str(failure.value)


def test_a_text_prize_passes_the_check():
    assert prizes.check("1000\nTelegram Premium\nРеклама в канале") == [
        "1000", "Telegram Premium", "Реклама в канале",
    ]


# ----------------------------------------------------- где призы показываются

def test_the_channel_post_shows_text_prizes():
    body = texts.prizes_block(["1000", "Telegram Premium на 3 месяца"])
    assert "1000⭐" in body
    assert "Telegram Premium на 3 месяца" in body


def test_long_prizes_go_in_a_column():
    """В строку длинные призы не помещаются — переносим."""
    long_list = texts.prizes_block(["Telegram Premium на 3 месяца", "Реклама в канале"])
    short_list = texts.prizes_block(["1000", "500"])
    assert "\n🥈" in long_list
    assert "  ·  " in short_list


def test_the_winner_is_told_the_text_prize():
    assert "Telegram Premium" in texts.took_place(1, "Telegram Premium")
    assert "1000⭐" in texts.took_place(1, "1000")


def test_the_final_announcement_names_text_prizes():
    ranking = [Slot(1, "nick1", 9, 1), Slot(2, "nick2", 4, 2)]
    body = texts.final_announcement(ranking, ["Реклама в канале", "500"])

    assert "Реклама в канале" in body
    assert "500⭐" in body


def test_the_main_post_shows_text_prizes():
    body = main_post.default_text(["Telegram Premium", "1000"])
    assert "1 место — <b>Telegram Premium</b>" in body
    assert "2 место — <b>1000⭐</b>" in body


def test_the_panel_screen_shows_both_kinds():
    text, markup = panel_ui.prizes(["1000", "Реклама в канале"])
    assert "1000⭐" in text and "Реклама в канале" in text
    assert markup.inline_keyboard


def test_the_panel_screen_survives_an_empty_list():
    text, markup = panel_ui.prizes([])
    assert text.strip() and markup.inline_keyboard


def test_the_input_screen_shows_a_multiline_value_as_a_block():
    text, _ = panel_ui.ask("Призы", "1000\n500", "подсказка", "prizes")
    assert "<blockquote>" in text, "список не должен слипаться в одну строку"
