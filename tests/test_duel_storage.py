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


def test_leaderboard_lists_everyone_with_newcomers_last(db):
    """Новичок не может стоять выше того, кто играл и проиграл: стартовая
    тысяча очков есть у всех. Но и прятать его незачем — под пьедесталом
    должен быть список, а не пустота."""
    for user_id, name, score in ((1, "Первый", 1300), (2, "Второй", 900), (3, "Третий", 1500)):
        storage.touch_player(db, user_id, name)
        storage.apply_result(db, user_id, new_rating=score, outcome="win", correct=1, wrong=0, best_streak=1)
    storage.touch_player(db, 4, "Новичок")

    rows = storage.top(db)
    assert [row["name"] for row in rows] == ["Третий", "Первый", "Второй", "Новичок"]
    assert rows[-1]["games"] == 0, "новичок в конце, хотя очков у него 1000"


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


def test_players_are_listed_by_when_they_last_came(db):
    """Список нужен, чтобы позвать в бой: сверху те, кто заходил недавно."""
    for user_id, name, when in (
        (1, "Вчерашний", "2026-09-06T12:00:00+00:00"),
        (2, "Сегодняшний", "2026-09-07T09:00:00+00:00"),
        (3, "Годовалый", "2025-09-07T09:00:00+00:00"),
    ):
        storage.touch_player(db, user_id, name)
        db.execute("UPDATE players SET last_seen_at = ? WHERE id = ?", (when, user_id))
    db.commit()
    assert [r["name"] for r in storage.by_last_seen(db)] == [
        "Сегодняшний", "Вчерашний", "Годовалый",
    ]


def test_you_are_not_in_your_own_list(db):
    storage.touch_player(db, 1, "Я")
    storage.touch_player(db, 2, "Другой")
    assert [r["name"] for r in storage.by_last_seen(db, exclude=1)] == ["Другой"]
    assert storage.count_players(db, exclude=1) == 1


def test_long_list_is_given_out_in_parts(db):
    for user_id in range(1, 8):
        storage.touch_player(db, user_id, f"Игрок {user_id}")
    first = storage.by_last_seen(db, limit=3)
    second = storage.by_last_seen(db, limit=3, offset=3)
    assert len(first) == len(second) == 3
    assert not ({r["id"] for r in first} & {r["id"] for r in second})


def test_how_long_ago_someone_came(db):
    from datetime import datetime, timedelta, timezone

    now = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
    hour_ago = (now - timedelta(hours=1)).isoformat()
    assert storage.seconds_since(hour_ago, now) == 3600
    assert storage.seconds_since(now.isoformat(), now) == 0


def test_broken_time_counts_as_very_long_ago(db):
    """Испорченная запись не должна ронять список — просто уходит в конец."""
    assert storage.seconds_since("чепуха") > 10 ** 8
    assert storage.seconds_since("") > 10 ** 8


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
