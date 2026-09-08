"""Хранилище: профили, итоги матчей, таблица лидеров."""

import pytest

from duel import storage


@pytest.fixture
def db(tmp_path):
    connection = storage.connect(tmp_path / "duel.sqlite3")
    yield connection
    connection.close()


def test_new_player_starts_at_the_base_rating(db):
    storage.touch_player(db, 1, "Алиджон")
    assert storage.rating_of(db, 1, "rope") == (1000, 0)
    assert storage.standing(db, 1, "rope") is None, "очков нет, пока не сыграл"


def test_second_visit_updates_the_name_but_keeps_the_rating(db):
    storage.touch_player(db, 1, "Старое имя")
    storage.apply_result(db, 1, "rope", new_rating=1100, outcome="win", correct=5, wrong=0, best_streak=3)
    row = storage.touch_player(db, 1, "Новое имя")
    assert row["name"] == "Новое имя"
    assert storage.rating_of(db, 1, "rope") == (1100, 1)


def test_results_add_up(db):
    storage.touch_player(db, 1, "Игрок")
    storage.apply_result(db, 1, "rope", new_rating=1020, outcome="win", correct=8, wrong=1, best_streak=4)
    storage.apply_result(db, 1, "rope", new_rating=1005, outcome="loss", correct=3, wrong=2, best_streak=2)
    storage.apply_result(db, 1, "rope", new_rating=1005, outcome="draw", correct=4, wrong=0, best_streak=6)
    row = storage.standing(db, 1, "rope")
    assert (row["games"], row["wins"], row["losses"], row["draws"]) == (3, 1, 1, 1)
    assert row["correct"] == 15 and row["wrong"] == 3
    assert row["best_streak"] == 6, "лучшая серия только растёт"


def test_best_rating_remembers_the_peak(db):
    storage.touch_player(db, 1, "Игрок")
    storage.apply_result(db, 1, "rope", new_rating=1300, outcome="win", correct=1, wrong=0, best_streak=1)
    storage.apply_result(db, 1, "rope", new_rating=1100, outcome="loss", correct=1, wrong=0, best_streak=1)
    assert storage.standing(db, 1, "rope")["best_rating"] == 1300


def test_unknown_outcome_is_refused(db):
    storage.touch_player(db, 1, "Игрок")
    with pytest.raises(ValueError):
        storage.apply_result(db, 1, "rope", new_rating=1, outcome="чепуха", correct=0, wrong=0, best_streak=0)


def test_leaderboard_lists_everyone_with_newcomers_last(db):
    """Новичок не может стоять выше того, кто играл и проиграл: стартовая
    тысяча очков есть у всех. Но и прятать его незачем — под пьедесталом
    должен быть список, а не пустота."""
    for user_id, name, score in ((1, "Первый", 1300), (2, "Второй", 900), (3, "Третий", 1500)):
        storage.touch_player(db, user_id, name)
        storage.apply_result(db, user_id, "rope", new_rating=score, outcome="win", correct=1, wrong=0, best_streak=1)
    storage.touch_player(db, 4, "Новичок")

    rows = storage.top(db)
    assert [row["name"] for row in rows] == ["Третий", "Первый", "Второй", "Новичок"]
    assert rows[-1]["games"] == 0, "новичок в конце, хотя очков у него 1000"


def test_place_is_counted_from_the_top(db):
    for user_id, score in ((1, 1500), (2, 1300), (3, 1100)):
        storage.touch_player(db, user_id, f"И{user_id}")
        storage.apply_result(db, user_id, "rope", new_rating=score, outcome="win", correct=1, wrong=0, best_streak=1)
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
    storage.apply_result(db, 1, "rope", new_rating=1234, outcome="win", correct=2, wrong=0, best_streak=2)
    db.close()
    again = storage.connect(tmp_path / "duel.sqlite3")
    assert storage.standing(again, 1, "rope")["rating"] == 1234
    again.close()


# ── очки по играм и переезд старой базы ─────────────────────────────────────


def test_each_game_keeps_its_own_score(db):
    storage.touch_player(db, 1, "Алиджон")
    storage.apply_result(db, 1, "rope", new_rating=1100, outcome="win", correct=5, wrong=0, best_streak=3)
    storage.apply_result(db, 1, "sea", new_rating=950, outcome="loss", correct=1, wrong=3, best_streak=1)
    assert storage.rating_of(db, 1, "rope") == (1100, 1)
    assert storage.rating_of(db, 1, "sea") == (950, 1)


def test_leaderboards_are_separate(db):
    storage.touch_player(db, 1, "Канатчик")
    storage.touch_player(db, 2, "Моряк")
    storage.apply_result(db, 1, "rope", new_rating=1200, outcome="win", correct=1, wrong=0, best_streak=1)
    storage.apply_result(db, 2, "sea", new_rating=1200, outcome="win", correct=1, wrong=0, best_streak=1)
    assert [r["name"] for r in storage.top(db, "rope")] == ["Канатчик", "Моряк"]
    assert [r["name"] for r in storage.top(db, "sea")] == ["Моряк", "Канатчик"]
    assert storage.place_of(db, 2, "rope") == 0 and storage.place_of(db, 2, "sea") == 1


def test_an_unknown_game_is_refused_everywhere(db):
    storage.touch_player(db, 1, "Игрок")
    with pytest.raises(ValueError):
        storage.apply_result(db, 1, "chess", new_rating=1, outcome="win", correct=0, wrong=0, best_streak=0)
    with pytest.raises(ValueError):
        storage.top(db, "chess")
    with pytest.raises(ValueError):
        storage.save_match(db, game="chess", player_a=1, player_b=2)


def test_history_remembers_the_game(db):
    storage.touch_player(db, 1, "A")
    storage.touch_player(db, 2, "B")
    storage.save_match(db, game="sea", player_a=1, player_b=2, winner=1)
    assert storage.history(db, 1)[0]["game"] == "sea"


def old_database(path):
    """База в том виде, в каком она сейчас на сервере: очки прямо в players."""
    import sqlite3

    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE schema_version (version INTEGER NOT NULL);
        INSERT INTO schema_version VALUES (1);
        CREATE TABLE players (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, username TEXT NOT NULL DEFAULT '',
            photo_url TEXT NOT NULL DEFAULT '', lang TEXT NOT NULL DEFAULT 'ru',
            rating INTEGER NOT NULL DEFAULT 1000, games INTEGER NOT NULL DEFAULT 0,
            wins INTEGER NOT NULL DEFAULT 0, losses INTEGER NOT NULL DEFAULT 0,
            draws INTEGER NOT NULL DEFAULT 0, correct INTEGER NOT NULL DEFAULT 0,
            wrong INTEGER NOT NULL DEFAULT 0, best_streak INTEGER NOT NULL DEFAULT 0,
            best_rating INTEGER NOT NULL DEFAULT 1000,
            created_at TEXT NOT NULL, last_seen_at TEXT NOT NULL
        );
        CREATE TABLE matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL, duration INTEGER NOT NULL, level TEXT NOT NULL,
            private INTEGER NOT NULL DEFAULT 0, player_a INTEGER NOT NULL,
            player_b INTEGER NOT NULL, score_a INTEGER NOT NULL, score_b INTEGER NOT NULL,
            rope INTEGER NOT NULL, winner INTEGER, reason TEXT NOT NULL DEFAULT '',
            delta_a INTEGER NOT NULL DEFAULT 0, delta_b INTEGER NOT NULL DEFAULT 0
        );
        INSERT INTO players (id, name, rating, games, wins, losses, draws, correct, wrong,
                             best_streak, best_rating, created_at, last_seen_at)
        VALUES (1, 'uways', 1057, 6, 4, 2, 0, 40, 5, 7, 1080, 't', 't'),
               (2, 'mahm',  923, 7, 2, 5, 0, 30, 9, 4, 1000, 't', 't'),
               (3, 'Новый', 1000, 0, 0, 0, 0, 0, 0, 0, 1000, 't', 't');
        INSERT INTO matches (started_at, finished_at, duration, level, player_a, player_b,
                             score_a, score_b, rope, winner)
        VALUES ('t', 't', 60, 'auto', 1, 2, 9, 7, 2, 1);
        """
    )
    conn.commit()
    conn.close()


def test_the_old_server_database_moves_over_without_losing_a_point(tmp_path):
    """На сервере база ещё старая. Никто не должен проснуться с обнулённым рейтингом."""
    path = tmp_path / "old.sqlite3"
    old_database(path)

    db = storage.connect(path)
    assert storage.rating_of(db, 1, "rope") == (1057, 6)
    assert storage.rating_of(db, 2, "rope") == (923, 7)
    assert storage.standing(db, 1, "rope")["wins"] == 4
    assert storage.standing(db, 3, "rope") is None, "кто не играл — тому и переносить нечего"
    assert [r["name"] for r in storage.top(db, "rope")] == ["uways", "mahm", "Новый"]
    assert storage.history(db, 1)[0]["game"] == "rope", "старые матчи — канат"
    assert storage.rating_of(db, 1, "sea") == (1000, 0), "в море все начинают заново"
    assert db.execute("SELECT version FROM schema_version").fetchone()[0] == storage.SCHEMA_VERSION
    db.close()


def test_reopening_a_moved_database_does_not_move_it_again(tmp_path):
    path = tmp_path / "old.sqlite3"
    old_database(path)
    storage.connect(path).close()
    db = storage.connect(path)
    storage.apply_result(db, 1, "rope", new_rating=1070, outcome="win", correct=3, wrong=0, best_streak=2)
    db.close()
    db = storage.connect(path)
    assert storage.rating_of(db, 1, "rope") == (1070, 7), "повторное открытие ничего не откатило"
    db.close()
