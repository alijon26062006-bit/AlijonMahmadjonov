"""База: деньги не рождаются и не пропадают."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from minesbot import db  # noqa: E402


@pytest.fixture
def conn(tmp_path):
    connection = db.connect(tmp_path / "t.db")
    yield connection
    connection.close()


def test_new_user_gets_start_balance_once(conn):
    assert db.ensure_user(conn, 1, "Ali", 1000) == 1000
    db.deposit(conn, 1, -500, "test")
    assert db.ensure_user(conn, 1, "Ali", 1000) == 500      # повторно не начисляем


def test_balance_cannot_go_negative(conn):
    db.ensure_user(conn, 1, "Ali", 100)
    with pytest.raises(db.Insufficient):
        db.deposit(conn, 1, -101, "test")
    assert db.balance(conn, 1) == 100


def test_transfer_moves_money_whole(conn):
    db.ensure_user(conn, 1, "A", 1000)
    db.ensure_user(conn, 2, "B", 0)
    left, got = db.transfer(conn, 1, 2, 400)
    assert (left, got) == (600, 400)
    assert db.balance(conn, 1) + db.balance(conn, 2) == 1000


def test_transfer_rejects_self_and_zero(conn):
    db.ensure_user(conn, 1, "A", 1000)
    with pytest.raises(ValueError):
        db.transfer(conn, 1, 1, 10)
    with pytest.raises(ValueError):
        db.transfer(conn, 1, 2, 0)


def test_failed_transfer_changes_nothing(conn):
    db.ensure_user(conn, 1, "A", 100)
    db.ensure_user(conn, 2, "B", 100)
    with pytest.raises(db.Insufficient):
        db.transfer(conn, 1, 2, 500)
    assert (db.balance(conn, 1), db.balance(conn, 2)) == (100, 100)


def test_ledger_explains_every_coin(conn):
    db.ensure_user(conn, 1, "A", 1000)
    db.ensure_user(conn, 2, "B", 0)
    db.transfer(conn, 1, 2, 300)
    total = conn.execute("SELECT SUM(delta) AS s FROM ledger WHERE user_id = 1").fetchone()["s"]
    assert total == db.balance(conn, 1) == 700


def test_bet_is_charged_at_start(conn):
    db.ensure_user(conn, 1, "A", 1000)
    game = db.start_game(conn, 1, 10, 100, 3, (0, 1, 2))
    assert db.balance(conn, 1) == 900
    assert db.active_game(conn, 1).game_id == game.game_id


def test_only_one_active_game(conn):
    db.ensure_user(conn, 1, "A", 1000)
    db.start_game(conn, 1, 10, 100, 3, (0, 1, 2))
    with pytest.raises(RuntimeError):
        db.start_game(conn, 1, 10, 100, 3, (5, 6, 7))
    assert db.balance(conn, 1) == 900        # вторая ставка не списана


def test_bet_bigger_than_balance_is_refused(conn):
    db.ensure_user(conn, 1, "A", 50)
    with pytest.raises(db.Insufficient):
        db.start_game(conn, 1, 10, 100, 3, (0, 1, 2))
    assert db.active_game(conn, 1) is None


def test_cell_cannot_be_opened_twice(conn):
    db.ensure_user(conn, 1, "A", 1000)
    game = db.start_game(conn, 1, 10, 100, 3, (0, 1, 2))
    db.open_cell(conn, game.game_id, 7)
    with pytest.raises(db.NoGame):
        db.open_cell(conn, game.game_id, 7)
    assert db.active_game(conn, 1).opened == (7,)


def test_payout_happens_once(conn):
    db.ensure_user(conn, 1, "A", 1000)
    game = db.start_game(conn, 1, 10, 100, 3, (0, 1, 2))
    assert db.finish_game(conn, game.game_id, "cashout", 250) == 1150
    with pytest.raises(db.NoGame):
        db.finish_game(conn, game.game_id, "cashout", 250)
    assert db.balance(conn, 1) == 1150


def test_game_survives_restart(conn, tmp_path):
    db.ensure_user(conn, 1, "A", 1000)
    game = db.start_game(conn, 1, 10, 100, 3, (0, 1, 2))
    db.open_cell(conn, game.game_id, 5)
    conn.close()

    again = db.connect(tmp_path / "t.db")
    restored = db.active_game(again, 1)
    assert restored.opened == (5,) and restored.bet == 100
    again.close()


def test_bonus_has_a_cooldown(conn):
    db.ensure_user(conn, 1, "A", 0)
    given, balance, _ = db.claim_bonus(conn, 1, 500, 12)
    assert (given, balance) == (True, 500)
    given, balance, minutes = db.claim_bonus(conn, 1, 500, 12)
    assert given is False and balance == 500 and minutes > 0


def test_stats_counts_games(conn):
    db.ensure_user(conn, 1, "A", 1000)
    g1 = db.start_game(conn, 1, 10, 100, 3, (0,))
    db.finish_game(conn, g1.game_id, "lost", 0)
    g2 = db.start_game(conn, 1, 10, 100, 3, (0,))
    db.finish_game(conn, g2.game_id, "cashout", 300)
    data = db.stats(conn, 1)
    assert data == {"games": 2, "won": 1, "lost": 1, "net": 100}


def test_top_is_sorted(conn):
    db.ensure_user(conn, 1, "A", 100)
    db.ensure_user(conn, 2, "B", 900)
    assert [r["user_id"] for r in db.top(conn)] == [2, 1]
