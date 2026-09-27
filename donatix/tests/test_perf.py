import threading
import time

from donatix import cache, db


def test_cache_computed_once_under_concurrency():
    cache.clear("t:")
    calls = []

    def slow():
        calls.append(1)
        time.sleep(0.2)
        return 42

    results = []
    threads = [threading.Thread(target=lambda: results.append(cache.get_or_set("t:x", 60, slow))) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results == [42] * 20 and len(calls) == 1          # не «лавина» из 20 одинаковых запросов


def test_stale_value_served_while_one_refreshes():
    cache.clear("t:")
    cache.get_or_set("t:y", 0.01, lambda: "old")
    time.sleep(0.02)
    started = threading.Event()

    def slow():
        started.set()
        time.sleep(0.3)
        return "new"

    t = threading.Thread(target=lambda: cache.get_or_set("t:y", 60, slow))
    t.start()
    started.wait(1)
    t0 = time.monotonic()
    assert cache.get_or_set("t:y", 60, lambda: "other") == "old"    # не ждёт пересчёта
    assert time.monotonic() - t0 < 0.1
    t.join()
    assert cache.get_or_set("t:y", 60, lambda: "other") == "new"


def test_pool_reuses_and_rolls_back(tmp_path):
    path = tmp_path / "p.db"
    db.init(path)
    pool = db.pool(path)
    c = pool.acquire()
    c.execute("BEGIN")
    c.execute("INSERT INTO settings (key, value) VALUES ('x', '1')")
    pool.release(c)                                     # недописанная транзакция откатилась
    c2 = pool.acquire()
    assert c2 is c and c2.execute("SELECT value FROM settings WHERE key = 'x'").fetchone() is None
    pool.release(c2)


def test_api_key_activity_written_at_most_once_a_minute(client, conn):
    from conftest import make_client
    _, key = make_client(conn)
    client.get("/api/v1/balance", headers={"X-API-Key": key})
    first = conn.execute("SELECT last_used_at FROM api_keys").fetchone()[0]
    client.get("/api/v1/balance", headers={"X-API-Key": key})
    assert conn.execute("SELECT last_used_at FROM api_keys").fetchone()[0] == first
