"""Хранилище: имена, смены, мягкое удаление."""

from __future__ import annotations

import sqlite3

import pytest

from counter import db


@pytest.fixture()
def conn(tmp_path):
    connection = db.connect(tmp_path / "counter.db")
    yield connection
    connection.close()


def test_same_name_in_any_case_is_one_person(conn):
    first, status = db.add_worker(conn, 1, "Иброхим")
    assert status == "created"
    again, status = db.add_worker(conn, 1, "иброхим")
    assert status == "exists" and again["id"] == first["id"]
    assert db.add_worker(conn, 1, "  ИБРОХИМ  ")[1] == "exists"
    assert len(db.list_workers(conn, 1)) == 1


def test_same_name_in_different_chats_is_fine(conn):
    assert db.add_worker(conn, 1, "Азиз")[1] == "created"
    assert db.add_worker(conn, 2, "Азиз")[1] == "created"


def test_rename_checks_collision(conn):
    first, _ = db.add_worker(conn, 1, "Азиз")
    second, _ = db.add_worker(conn, 1, "Умар")
    assert db.rename_worker(conn, second["id"], "азиз") == "exists"
    assert db.rename_worker(conn, second["id"], "Умарбек") == "ok"
    assert db.get_worker(conn, second["id"])["name"] == "Умарбек"


def test_archive_keeps_entries_and_restores(conn):
    session = db.current_session(conn, 1)
    worker, _ = db.add_worker(conn, 1, "Азиз")
    db.set_active_worker(conn, 1, worker["id"])
    db.add_entry(conn, chat_id=1, session_id=session["id"], worker_id=worker["id"], amount=500)

    db.archive_worker(conn, worker["id"])
    assert db.list_workers(conn, 1) == []
    assert db.active_worker(conn, 1) is None
    assert db.grand_total(conn, 1, session["id"]) == (1, 500)   # записи целы

    restored, status = db.add_worker(conn, 1, "азиз")
    assert status == "restored" and restored["id"] == worker["id"]


def test_deleted_entries_do_not_count_but_come_back(conn):
    session = db.current_session(conn, 1)
    worker, _ = db.add_worker(conn, 1, "Азиз")
    entry = db.add_entry(conn, chat_id=1, session_id=session["id"], worker_id=worker["id"], amount=700)

    db.set_deleted(conn, entry["id"], True)
    assert db.grand_total(conn, 1, session["id"]) == (0, 0)
    assert db.get_entry(conn, entry["id"])["amount"] == 700     # ничего не потеряли

    db.set_deleted(conn, entry["id"], False)
    assert db.grand_total(conn, 1, session["id"]) == (1, 700)


def test_new_session_starts_from_zero(conn):
    first = db.current_session(conn, 1)
    worker, _ = db.add_worker(conn, 1, "Азиз")
    db.add_entry(conn, chat_id=1, session_id=first["id"], worker_id=worker["id"], amount=700)

    second = db.start_session(conn, 1, title="Смена 2")
    assert second["id"] != first["id"]
    assert db.get_session(conn, first["id"])["closed_at"] is not None
    assert db.grand_total(conn, 1, second["id"]) == (0, 0)
    assert db.grand_total(conn, 1, None) == (1, 700)            # история на месте


def test_summary_shows_everyone_even_without_entries(conn):
    session = db.current_session(conn, 1)
    busy, _ = db.add_worker(conn, 1, "Азиз")
    db.add_worker(conn, 1, "Умар")
    db.add_entry(conn, chat_id=1, session_id=session["id"], worker_id=busy["id"], amount=700)

    rows = {row["name"]: (row["count"], row["total"]) for row in db.summary(conn, 1, session["id"])}
    assert rows == {"Азиз": (1, 700), "Умар": (0, 0)}


def test_old_database_gets_upgraded(tmp_path):
    """База прошлой версии (без name_key) должна открыться и починиться."""
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.executescript(
        """
        CREATE TABLE workers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            archived INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        INSERT INTO workers(chat_id, name, archived, created_at)
        VALUES (1, 'Иброхим', 0, '2026-01-01T00:00:00+00:00');
        """
    )
    old.commit()
    old.close()

    conn = db.connect(path)
    assert db.add_worker(conn, 1, "иброхим")[1] == "exists"
    conn.close()


def test_duplicate_guard_window(conn):
    session = db.current_session(conn, 1)
    worker, _ = db.add_worker(conn, 1, "Азиз")
    db.add_entry(conn, chat_id=1, session_id=session["id"], worker_id=worker["id"], amount=700)

    assert db.recent_duplicate(conn, worker["id"], 700, 60) is not None
    assert db.recent_duplicate(conn, worker["id"], 800, 60) is None
    assert db.recent_duplicate(conn, worker["id"], 700, 0) is None
