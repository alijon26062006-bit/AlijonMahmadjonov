"""Поддержка тикетами: клиент пишет на сайте → в бот поддержки с кнопкой «📂 Открыть» → мини-приложение:
админ читает переписку и отвечает — клиент видит ответ на сайте и получает уведомление."""
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from conftest import RECEIPT_PNG, csrf_of, make_client, web_login
from fastapi.testclient import TestClient

from donatix import support_app, tickets

TOKEN = "123456:support-test-token"
ADMIN = "555"


def _init(user_id: str, token: str = TOKEN, age: int = 0) -> str:
    """initData так, как её подписывает Telegram."""
    pairs = {"auth_date": str(int(time.time()) - age), "user": json.dumps({"id": int(user_id), "first_name": "A"}),
             "query_id": "q1"}
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(pairs)


def _setup(config):
    config.support_bot_token, config.support_admin_id = TOKEN, ADMIN


def test_client_ticket_admin_answers_in_mini_app(app, config, conn, monkeypatch):
    _setup(config)
    sent = []
    monkeypatch.setattr(tickets, "alert_admin", lambda c, cfg, tid, new=False: sent.append((tid, new)))
    uid, _ = make_client(conn)
    c = TestClient(app)
    web_login(c, "shop1@example.com", "password123")
    page = c.get("/panel/support").text
    assert "Открыть обращение" in page
    r = c.post("/panel/support", data={"csrf": csrf_of(page), "topic": "order", "order_ref": "dx-77",
                                      "subject": "Алмазы не пришли", "text": "ID 123456789, оплатил в 14:00"},
               files={"file": ("s.png", RECEIPT_PNG, "image/png")})
    assert "#1 · Алмазы не пришли" in r.text and sent == [(1, True)]

    admin = TestClient(app)                                              # мини-приложение в боте поддержки
    h = {"X-Tg-Init": _init(ADMIN)}
    assert admin.get("/support-app").status_code == 200
    items = admin.post("/support-app/api/list", json={"status": "active"}, headers=h).json()["items"]
    assert items[0]["subject"] == "Алмазы не пришли" and items[0]["new"] is True
    t = admin.post("/support-app/api/ticket", json={"id": 1}, headers=h).json()
    assert t["messages"][0]["text"] == "ID 123456789, оплатил в 14:00" and t["order_ref"] == "dx-77"
    assert admin.get(t["messages"][0]["file"]).content == RECEIPT_PNG          # скриншот по подписанной ссылке
    assert admin.get(t["messages"][0]["file"] + "x").status_code == 404
    assert admin.post("/support-app/api/reply", json={"id": 1, "text": "Отправили повторно."}, headers=h).json()["ok"]
    assert tickets.get(conn, 1)["status"] == "answered"
    note = conn.execute("SELECT text, link FROM notifications WHERE user_id = ? ORDER BY id DESC", (uid,)).fetchone()
    assert "Ответ поддержки по обращению #1" in note["text"] and note["link"] == "/panel/support/1"
    data = c.get("/panel/data/ticket/1?after=1").json()
    assert data["messages"][0]["author"] == "admin" and "повторно" in data["messages"][0]["text"]

    admin.post("/support-app/api/reply", json={"id": 1, "text": "Всё дошло?", "close": True}, headers=h)
    assert tickets.get(conn, 1)["status"] == "closed"
    mine = c.get("/panel/support/1").text
    assert "Всё дошло?" in mine and "Закрыт" in mine
    c.post("/panel/support/1", data={"csrf": csrf_of(mine), "text": "Да, спасибо!"})   # написал — снова открыт
    assert tickets.get(conn, 1)["status"] == "open" and sent[-1] == (1, False)


def test_mini_app_only_for_support_admin(app, config, conn, monkeypatch):
    _setup(config)
    monkeypatch.setattr(tickets, "alert_admin", lambda *a, **k: None)
    uid, _ = make_client(conn)
    tickets.create(conn, config, uid, "Вопрос", "other", "", "текст")
    x = TestClient(app)
    for headers in ({}, {"X-Tg-Init": _init("999")}, {"X-Tg-Init": _init(ADMIN, token="1:other")},
                    {"X-Tg-Init": _init(ADMIN, age=3 * 86400)}):
        assert x.post("/support-app/api/list", json={}, headers=headers).status_code == 403
        assert x.post("/support-app/api/reply", json={"id": 1, "text": "x"}, headers=headers).status_code == 403
    assert len(tickets.messages(conn, 1)) == 1


def test_alert_goes_to_support_bot_with_open_button(config, conn, monkeypatch):
    _setup(config)
    calls = []

    class Api:
        def __init__(self, token):
            assert token == TOKEN

        def __call__(self, method, **p):
            calls.append((method, p))

    monkeypatch.setattr("donatix.tgbot.TelegramApi", Api)
    monkeypatch.setattr(tickets, "alert_admin", lambda *a, **k: None)
    uid, _ = make_client(conn)
    tid = tickets.create(conn, config, uid, "Пополнение", "payment", "#5", "баланс не пополнился")
    tickets._deliver(config, tid, tickets.alert_text(conn, config, tid, new=True))
    msg = [p for m, p in calls if m == "sendMessage"][0]
    assert msg["chat_id"] == ADMIN and "Новый тикет #1" in msg["text"] and "#5" in msg["text"]
    button = msg["reply_markup"]["inline_keyboard"][0][0]
    assert button["web_app"]["url"].endswith("/support-app?t=1")
    assert any(m == "setChatMenuButton" for m, _ in calls)


def test_ticket_is_private(app, config, conn, monkeypatch):
    monkeypatch.setattr(tickets, "alert_admin", lambda *a, **k: None)
    uid, _ = make_client(conn)
    tid = tickets.create(conn, config, uid, "Вопрос", "other", "", "секрет", RECEIPT_PNG)
    name = conn.execute("SELECT file FROM ticket_messages").fetchone()["file"]
    make_client(conn, login="shop2")
    other = TestClient(app)
    web_login(other, "shop2@example.com", "password123")
    assert other.get(f"/panel/support/{tid}", follow_redirects=False).status_code == 303
    assert other.get(f"/panel/data/ticket/{tid}").status_code == 404
    assert other.get(f"/panel/ticket-files/{name}").status_code == 404
    owner = TestClient(app)
    web_login(owner, "shop1@example.com", "password123")
    assert owner.get(f"/panel/ticket-files/{name}").content == RECEIPT_PNG


def test_check_init_signature():
    user = support_app.check_init(_init(ADMIN), TOKEN)
    assert user and user["id"] == int(ADMIN)
    assert support_app.check_init(_init(ADMIN), "1:wrong") is None
    assert support_app.check_init(_init(ADMIN).replace("q1", "q2"), TOKEN) is None   # подделали данные
