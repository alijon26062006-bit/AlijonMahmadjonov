"""Проверка защиты: дыры, найденные при аудите, закрыты."""

import base64
import json
import re

import pytest
from conftest import balance, csrf_of, web_login
from fastapi.testclient import TestClient

from donatix import accounts, cashiers, supplier_queue, tgbot, webhooks
from donatix.suppliers.base import SupplierRejected, normalize_status


def _stars(client, h, user="@player_one"):
    return client.post("/api/v1/orders", headers=h,
                       json={"product_id": "tg-stars", "quantity": 50, "fields": {"telegram_username": user}})


def _session(client) -> dict:
    raw = client.cookies.get("dx_session").split(".")[0]
    return json.loads(base64.b64decode(raw + "=" * (-len(raw) % 4)))


# ── 2FA админа ──

def test_2fa_code_is_not_in_cookie_and_tries_count_on_server(app, config, conn, monkeypatch):
    config.alert_telegram_token, config.alert_telegram_chat_id = "t", "777"
    sent = []
    monkeypatch.setattr("donatix.worker.notify_admin", lambda cfg, text, *a, **k: sent.append(text))
    c = TestClient(app)
    c.post("/login", data={"csrf": csrf_of(c.get("/login").text), "email": "admin@example.com",
                           "password": "adminpass123"})
    code = re.search(r"(\d{6})", sent[-1]).group(1)
    pending = _session(c)["pending_2fa"]
    assert isinstance(pending, str) and code not in json.dumps(_session(c))   # в cookie только номер попытки
    saved = dict(c.cookies)
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        c.cookies.clear()
        c.cookies.update(saved)                                    # старый cookie попытки не сбрасывает
        c.post("/login/code", data={"csrf": csrf_of(c.get("/login/code").text), "code": wrong})
    c.cookies.clear()
    c.cookies.update(saved)
    r = c.post("/login/code", data={"csrf": csrf_of(c.get("/login/code").text), "code": code},
               follow_redirects=False)
    assert r.headers["location"] == "/login"                       # 5 неверных — код сгорел
    assert c.get("/admin", follow_redirects=False).status_code in (302, 303)


def test_2fa_code_not_written_to_log(app, config, conn, monkeypatch, caplog):
    config.alert_telegram_token, config.alert_telegram_chat_id = "", ""
    monkeypatch.setattr("donatix.sitecfg.admin_2fa_active", lambda *a: True)
    c = TestClient(app)
    with caplog.at_level("WARNING"):
        c.post("/login", data={"csrf": csrf_of(c.get("/login").text), "email": "admin@example.com",
                               "password": "adminpass123"})
    assert not re.search(r"\b\d{6}\b", caplog.text)


# ── Сессии ──

def test_logout_kills_copied_cookie(app, conn):
    accounts.create_user(conn, email="s@example.com", login="sess1", password="password123", status="active")
    c = TestClient(app)
    web_login(c, "s@example.com", "password123")
    stolen = dict(c.cookies)
    assert c.get("/panel", follow_redirects=False).status_code == 200
    c.post("/logout", data={"csrf": csrf_of(c.get("/panel").text)})
    thief = TestClient(app)
    thief.cookies.update(stolen)
    assert thief.get("/panel", follow_redirects=False).status_code in (302, 303)


def test_spoofed_forwarded_for_does_not_reset_login_limit(app, conn):
    c = TestClient(app)
    codes = []
    for i in range(12):
        r = c.post("/login", headers={"X-Forwarded-For": f"10.0.0.{i}"},
                   data={"csrf": csrf_of(c.get("/login").text), "email": "admin@example.com", "password": "bad"})
        codes.append(r.status_code)
    assert 429 in codes


# ── Поставщик ──

def test_word_balance_in_rejection_does_not_freeze_queue(client, conn, shop, supplier):
    def boom(*a, **k):
        raise SupplierRejected("Steam wallet balance limit exceeded for @balance_x", http_status=400)
    supplier.create_order = boom
    order = _stars(client, shop["h"]).json()["order"]
    assert order["status"] == "failed"                             # отказ — деньги вернули
    assert not supplier_queue.on_hold(conn, "mock") and supplier_queue.queued_count(conn) == 0


def test_conflict_from_supplier_goes_to_admin_not_refund(client, conn, shop, supplier):
    def boom(*a, **k):
        raise SupplierRejected("duplicate order", http_status=409)
    supplier.create_order = boom
    before = balance(conn, shop["id"])
    order = _stars(client, shop["h"]).json()["order"]
    row = conn.execute("SELECT status FROM orders WHERE public_id = ?", (order["order_id"],)).fetchone()
    assert row["status"] == "attention" and balance(conn, shop["id"]) < before


@pytest.mark.parametrize("raw", ["partially_refunded", "partial_refund", "Частично выполнен"])
def test_partial_status_is_not_full_refund(raw):
    assert normalize_status(raw) == "partial"


def test_real_no_funds_phrase_still_queues():
    assert supplier_queue.is_no_funds(SupplierRejected("Insufficient balance"))
    assert supplier_queue.is_no_funds(SupplierRejected("Недостаточно средств на счёте"))
    assert not supplier_queue.is_no_funds(SupplierRejected("wallet balance limit"))


# ── Webhook ──

@pytest.mark.parametrize("url", ["http://127.0.0.1:8000/x", "http://169.254.169.254/latest", "http://10.0.0.5/",
                                 "http://localhost/hook", "http://[::1]/", "ftp://example.com/"])
def test_webhook_cannot_point_inside_server(url):
    assert webhooks.public_target(url) is False
    with pytest.raises(accounts.AccountError):
        accounts.set_webhook(None, 1, url)


# ── Кассир ──

def test_cashier_cannot_approve_own_request(app, config, conn, monkeypatch):
    from test_one_request import _client, _send
    monkeypatch.setattr("donatix.worker.notify_admin_file", lambda *a, **k: None)
    monkeypatch.setattr("donatix.cashiers.send_file", lambda *a, **k: 7)
    cashiers.add(conn, 5550002, "Свой")
    uid, client, token = _client(app, config, conn)
    conn.execute("INSERT INTO support_links (tg_id, user_id, linked_at) VALUES (?, ?, '2026-01-01')",
                 (5550002, uid))
    _send(client, token)
    config.alert_telegram_chat_id = "777"
    bot = tgbot.AdminBot(config, api=lambda m, **p: {})
    bot.handle(conn, {"update_id": 1, "callback_query": {
        "id": "c", "data": "pay:ok:1", "from": {"id": 5550002},
        "message": {"message_id": 7, "chat": {"id": 5550002, "type": "private"}, "caption": "чек", "photo": [{}]}}})
    assert balance(conn, uid) == 0


def test_group_member_is_not_admin(app, config, conn):
    config.alert_telegram_chat_id = "-100500"
    calls = []

    def api(method, **p):
        calls.append(method)
        return {"status": "member"} if method == "getChatMember" else {}
    bot = tgbot.AdminBot(config, api=api)
    bot.handle(conn, {"update_id": 1, "message": {"chat": {"id": -100500, "type": "supergroup"},
                                                   "from": {"id": 42}, "text": "/payments"}})
    assert calls == ["getChatMember"]                              # не админ группы — бот молчит
