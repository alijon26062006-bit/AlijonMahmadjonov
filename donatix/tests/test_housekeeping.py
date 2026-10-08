import time
from datetime import datetime, timezone

from donatix import db, housekeeping

from conftest import make_client

OLD = "2020-01-01T00:00:00.000Z"


def test_removes_junk_keeps_user_data(conn):
    uid = make_client(conn)[0]
    now = time.time()
    conn.execute("INSERT INTO tg_logins (token, created_at, expires_at, status) VALUES ('old', ?, ?, 'new')",
                 (OLD, now - 7200))
    conn.execute("INSERT INTO tg_logins (token, created_at, expires_at, status) VALUES ('new', ?, ?, 'new')",
                 (db.now(), now + 300))
    conn.execute("INSERT INTO logins (user_id, created_at, ended_at) VALUES (?, ?, ?)", (uid, OLD, OLD))
    conn.execute("INSERT INTO logins (user_id, created_at) VALUES (?, ?)", (uid, OLD))   # открытый вход — оставить
    conn.execute("INSERT INTO notifications (user_id, text, created_at, read_at) VALUES (?, 'a', ?, ?)", (uid, OLD, OLD))
    conn.execute("INSERT INTO notifications (user_id, text, created_at) VALUES (?, 'b', ?)", (uid, OLD))
    conn.execute("INSERT INTO player_names (game, uid, valid, checked_at) VALUES ('ff', '1', 1, ?)", (now - 90 * 86400,))
    conn.execute("INSERT INTO player_names (game, uid, valid, checked_at) VALUES ('ff', '2', 1, ?)", (now,))
    tx = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]

    done = housekeeping.run(conn)

    assert done["tg_logins"] == 1 and done["logins"] == 1 and done["notifications"] == 1 and done["player_names"] == 1
    assert conn.execute("SELECT COUNT(*) FROM logins").fetchone()[0] == 1
    assert conn.execute("SELECT text FROM notifications").fetchone()[0] == "b"   # непрочитанное — осталось
    assert conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == tx   # деньги не тронуты
    assert conn.execute("SELECT COUNT(*) FROM users WHERE id = ?", (uid,)).fetchone()[0] == 1


def test_once_a_day_after_4am(conn):
    early = datetime(2026, 5, 1, 22, 0, tzinfo=timezone.utc)       # 3:00 в Душанбе
    late = datetime(2026, 5, 1, 23, 30, tzinfo=timezone.utc)       # 4:30
    assert housekeeping.maybe_run(conn, 5, early) is None
    assert housekeeping.maybe_run(conn, 5, late) is not None
    assert housekeeping.maybe_run(conn, 5, late) is None              # второй раз за сутки — нет
