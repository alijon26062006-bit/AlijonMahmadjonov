"""Хранилище: профили, итоги матчей, таблица лидеров."""

import pytest

from duel import storage


@pytest.fixture
def db(tmp_path):
    connection = storage.connect(tmp_path / "duel.sqlite3")
    yield connection
    connection.close()


def test_new_player_starts_at_the_base_rating(db):
    row = storage.touch_player(db, 1, "Алиджон")
    assert row["rating"] == 1000 and row["games"] == 0


def test_second_visit_updates_the_name_but_keeps_the_rating(db):
    storage.touch_player(db, 1, "Старое имя")
    storage.apply_result(db, 1, new_rating=1100, outcome="win", correct=5, wrong=0, best_streak=3)
    row = storage.touch_player(db, 1, "Новое имя")
    assert row["name"] == "Новое имя" and row["rating"] == 1100


def test_results_add_up(db):
    storage.touch_player(db, 1, "Игрок")
    storage.apply_result(db, 1, new_rating=1020, outcome="win", correct=8, wrong=1, best_streak=4)
    storage.apply_result(db, 1, new_rating=1005, outcome="loss", correct=3, wrong=2, best_streak=2)
    storage.apply_result(db, 1, new_rating=1005, outcome="draw", correct=4, wrong=0, best_streak=6)
    row = storage.get_player(db, 1)
    assert (row["games"], row["wins"], row["losses"], row["draws"]) == (3, 1, 1, 1)
    assert row["correct"] == 15 and row["wrong"] == 3
    assert row["best_streak"] == 6, "лучшая серия только растёт"


def test_best_rating_remembers_the_peak(db):
    storage.touch_player(db, 1, "Игрок")
    storage.apply_result(db, 1, new_rating=1300, outcome="win", correct=1, wrong=0, best_streak=1)
    storage.apply_result(db, 1, new_rating=1100, outcome="loss", correct=1, wrong=0, best_streak=1)
    assert storage.get_player(db, 1)["best_rating"] == 1300


def test_unknown_outcome_is_refused(db):
    storage.touch_player(db, 1, "Игрок")
    with pytest.raises(ValueError):
        storage.apply_result(db, 1, new_rating=1, outcome="чепуха", correct=0, wrong=0, best_streak=0)


def test_leaderboard_is_sorted_and_skips_the_untested(db):
    for user_id, name, score in ((1, "Первый", 1300), (2, "Второй", 1100), (3, "Третий", 1500)):
        storage.touch_player(db, user_id, name)
        storage.apply_result(db, user_id, new_rating=score, outcome="win", correct=1, wrong=0, best_streak=1)
    storage.touch_player(db, 4, "Не играл")
    names = [row["name"] for row in storage.top(db)]
    assert names == ["Третий", "Первый", "Второй"]


def test_place_is_counted_from_the_top(db):
    for user_id, score in ((1, 1500), (2, 1300), (3, 1100)):
        storage.touch_player(db, user_id, f"И{user_id}")
        storage.apply_result(db, user_id, new_rating=score, outcome="win", correct=1, wrong=0, best_streak=1)
    assert storage.place_of(db, 1) == 1
    assert storage.place_of(db, 3) == 3
    storage.touch_player(db, 9, "Новичок")
    assert storage.place_of(db, 9) == 0


def test_match_goes_into_history_for_both(db):
    storage.touch_player(db, 1, "A")
    storage.touch_player(db, 2, "B")
    storage.save_match(
        db, player_a=1, player_b=2, score_a=9, score_b=7, rope=2,
        winner=1, reason="time", delta_a=15, delta_b=-15, duration=60, level="normal",
    )
    assert len(storage.history(db, 1)) == 1
    assert len(storage.history(db, 2)) == 1
    assert storage.totals(db)["matches"] == 1


def test_language_is_remembered(db):
    storage.touch_player(db, 1, "Игрок")
    storage.set_lang(db, 1, "tg")
    assert storage.get_player(db, 1)["lang"] == "tg"
    with pytest.raises(ValueError):
        storage.set_lang(db, 1, "fr")


def test_reopening_the_database_keeps_everything(db, tmp_path):
    storage.touch_player(db, 1, "Игрок")
    storage.apply_result(db, 1, new_rating=1234, outcome="win", correct=2, wrong=0, best_streak=2)
    db.close()
    again = storage.connect(tmp_path / "duel.sqlite3")
    assert storage.get_player(again, 1)["rating"] == 1234
    again.close()
