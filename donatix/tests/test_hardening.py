"""Укрепление после аудита: заголовки, ошибки 500 на мусоре, кэш, бот-магазин, тикеты, токены в журнале."""
import logging
import threading
import time

from conftest import make_client

from donatix import cache


def test_security_headers(client):
    r = client.get("/")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors" in r.headers["content-security-policy"]
    assert "telegram.org" in r.headers["content-security-policy"]
    assert r.headers["referrer-policy"] == "strict-origin-when-cross-origin"


def test_huge_numbers_no_500(client, conn):
    _, key = make_client(conn, login="bignum")
    h = {"Authorization": f"Bearer {key}"}
    assert client.get("/api/v1/products?offset=99999999999999999999", headers=h).status_code == 400
    assert client.get("/api/v1/payments/99999999999999999999", headers=h).status_code == 400
    assert client.get("/api/v1/transactions?page=99999999999999999999", headers=h).status_code < 500


def test_cache_is_bounded(monkeypatch):
    monkeypatch.setattr(cache, "MAX_KEYS", 50)
    cache.clear()
    for i in range(500):
        cache.get_or_set(f"junk:{i}", 60, lambda: i)
    assert len(cache._store) <= 50 and len(cache._key_locks) <= 60
    cache.clear()


def test_shopbot_one_chat_one_worker(config):
    """10 сообщений одного покупателя не занимают все потоки: остальным отвечаем сразу."""
    from donatix import shopbot
    bot = shopbot.ShopBot(config, None)
    from concurrent.futures import ThreadPoolExecutor
    bot._pool = ThreadPoolExecutor(max_workers=2)
    busy = threading.Event()
    seen = []

    def slow_or_fast(upd):
        if upd["message"]["chat"]["id"] == 1:
            busy.wait(2)
        seen.append(upd["message"]["chat"]["id"])
    bot._process = slow_or_fast
    for i in range(10):
        bot._enqueue({"update_id": i, "message": {"chat": {"id": 1}}})
    bot._enqueue({"update_id": 99, "message": {"chat": {"id": 2}}})
    t0 = time.time()
    while 2 not in seen and time.time() - t0 < 1.5:
        time.sleep(0.01)
    assert 2 in seen          # второй покупатель не ждал, пока разберут сообщения первого
    busy.set()
    bot._pool.shutdown(wait=True)


def test_ticket_number_only_from_header():
    from donatix.ticketbot import _TICKET
    text = "👤 Тикет #1 (tg123)\n💬 Тикет #7 · Пополнение\n<i>тема</i>"
    assert _TICKET.search(text).group(1) == "7"


def test_bot_token_hidden_in_logs(caplog):
    from donatix.app import _HideTokens
    rec = logging.LogRecord("x", logging.WARNING, __file__, 1, "ошибка %s",
                            ("https://api.telegram.org/file/bot123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw/x",), None)
    _HideTokens().filter(rec)
    assert "AAHdq" not in rec.getMessage()
