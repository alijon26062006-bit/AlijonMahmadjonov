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
    assert "Новая заявка" in page
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


OGG = b"OggS" + b"\0" * 60          # голосовое из Telegram / браузера
WEBM = b"\x1a\x45\xdf\xa3" + b"\0" * 60


def test_voice_and_receipt_in_ticket_and_client_history(app, config, conn, monkeypatch):
    """Голосовое и чек — с обеих сторон; во вкладке «История» — только посмотреть: куда тратил, какие заказы."""
    from donatix import accounts, db
    _setup(config)
    monkeypatch.setattr(tickets, "alert_admin", lambda *a, **k: None)
    uid, _ = make_client(conn)
    with db.tx(conn):
        oid = conn.execute("INSERT INTO orders (public_id, user_id, product_id, kind, product_name, quantity, unit_price, "
                           "total_micro, cost_micro, status, supplier_idem_key, fields_json, created_at, updated_at) "
                           "VALUES ('dx-9', ?, 'p', 'topup', 'Free Fire 100', 1, '1', 10000, 9000, 'completed', 'k9', "
                           "'{\"player_id\": \"123456789\"}', '2026-10-08T08:00:00', '2026-10-08T08:00:00')",
                           (uid,)).lastrowid
        accounts.post_ledger(conn, uid, -10_000, "Заказ dx-9", order_id=oid)
    c = TestClient(app)
    web_login(c, "shop1@example.com", "password123")
    page = c.get("/panel/support").text
    c.post("/panel/support", data={"csrf": csrf_of(page), "topic": "order", "text": "Слушайте голосовое"},
           files={"file": ("voice.webm", WEBM, "audio/webm")})
    m = tickets.messages(conn, 1)[0]
    assert m["file"].endswith(".webm") and tickets.file_kind(m["file"]) == "audio"
    chat = c.get("/panel/support/1").text
    assert '<audio class="tk-audio"' in chat
    assert c.get(f"/panel/ticket-files/{m['file']}").headers["content-type"].startswith("audio/webm")

    h = {"X-Tg-Init": _init(ADMIN)}
    admin = TestClient(app)
    t = admin.post("/support-app/api/ticket", json={"id": 1}, headers=h).json()
    assert t["messages"][0]["kind"] == "audio" and t["name"].startswith("shop1")
    r = admin.post("/support-app/api/reply", data={"id": "1", "text": "Вот чек"}, headers=h,
                   files={"file": ("chek.png", RECEIPT_PNG, "image/png")})
    assert r.json()["ok"] and tickets.messages(conn, 1)[-1]["file"].endswith(".png")
    admin.post("/support-app/api/reply", data={"id": "1", "text": ""}, headers=h,
               files={"file": ("voice.ogg", OGG, "audio/ogg")})
    assert tickets.messages(conn, 1)[-1]["file"].endswith(".ogg")
    note = conn.execute("SELECT text FROM notifications WHERE user_id = ? ORDER BY id DESC", (uid,)).fetchone()["text"]
    assert "голосовое" in note

    hist = admin.post("/support-app/api/history", json={"id": 1}, headers=h).json()
    assert hist["spent"] == "1.0000" and hist["orders"][0]["id"] == "dx-9" and hist["orders"][0]["to"] == "123456789"
    assert any("dx-9 · Free Fire 100" in o["what"] and not o["plus"] for o in hist["ops"])
    assert "balance" in hist and "topup" not in str(hist)             # только просмотр — ни пополнить, ни списать
    assert admin.post("/support-app/api/history", json={"id": 1}, headers={"X-Tg-Init": _init("999")}).status_code == 403


def test_support_bot_is_only_for_tickets(config, conn, monkeypatch):
    """Клиент пишет боту — его отправляют на сайт. Админ отвечает reply — текстом или голосовым — в тикет."""
    from donatix import ticketbot
    _setup(config)
    monkeypatch.setattr(tickets, "alert_admin", lambda *a, **k: None)
    uid, _ = make_client(conn)
    tid = tickets.create(conn, config, uid, "Вопрос", "payment", "#5", "баланс не пополнился")
    sent = []

    class Api:
        def __call__(self, method, **p):
            sent.append((method, p))

        def download(self, file_id, max_bytes=0):
            assert file_id == "voice-1"
            return OGG

    bot = ticketbot.TicketBot(config, api=Api())
    bot.handle(conn, {"message": {"chat": {"id": 42, "type": "private"}, "text": "помогите"}})
    assert "/panel/support" in sent[-1][1]["text"] and sent[-1][1]["chat_id"] == "42"
    alert = tickets.alert_text(conn, config, tid, new=True)
    assert alert.startswith("👤 <b>shop1</b>") and "Новый тикет #1" in alert
    bot.handle(conn, {"message": {"chat": {"id": int(ADMIN), "type": "private"}, "text": "Зачислили",
                                  "reply_to_message": {"text": "👤 shop1\n🎫 Новый тикет #1 · Пополнение"}}})
    bot.handle(conn, {"message": {"chat": {"id": int(ADMIN), "type": "private"}, "voice": {"file_id": "voice-1"},
                                  "reply_to_message": {"text": "👤 shop1\n💬 Тикет #1 · Пополнение"}}})
    msgs = tickets.messages(conn, tid)
    assert msgs[-2]["text"] == "Зачислили" and msgs[-1]["file"].endswith(".ogg") and msgs[-1]["author"] == "admin"
    assert "Отправлено клиенту в тикет #1" in sent[-1][1]["text"]


def test_support_buttons_lead_to_tickets_not_telegram(app, config, conn, monkeypatch):
    """«Поддержка» на сайте — тикеты; в боте-магазине — мини-приложение, которое само входит и открывает тикеты."""
    from test_shopbot import TG, FakeApi, msg

    from donatix import shopbot
    config.support_contact = "@donatix_support"
    config.shop_bot_token = "777:shop-token"
    make_client(conn)
    c = TestClient(app)
    web_login(c, "shop1@example.com", "password123")
    home = c.get("/panel").text
    assert 'href="/panel/support"' in home and "t.me/donatix_support" not in home

    api = FakeApi()
    bot = shopbot.ShopBot(config, None, api=api)
    bot.handle(conn, msg("/start"))
    su = shopbot.shop_user(conn, TG)
    bot.on_button(conn, su, "sup", 1)
    markup = [p for m, p in api.calls if m in ("editMessageText", "sendMessage")][-1]["reply_markup"]
    assert markup["inline_keyboard"][0][0]["web_app"]["url"].endswith("/support-app/me")

    guest = TestClient(app)                                   # покупатель бота открыл мини-приложение
    assert guest.post("/support-app/me/login", json={"init": _init(str(TG), token="1:wrong")}).status_code == 403
    r = guest.post("/support-app/me/login", json={"init": _init(str(TG), token="777:shop-token")})
    assert r.json()["next"] == "/panel/support"
    assert "Новая заявка" in guest.get("/panel/support").text


def test_support_page_like_fazercards_and_thread_per_person(app, config, conn, monkeypatch):
    """Поиск и база знаний, «С чем нужна помощь?» → форма по теме; в боте у каждого тикета своя ветка."""
    _setup(config)
    make_client(conn)
    c = TestClient(app)
    web_login(c, "shop1@example.com", "password123")
    page = c.get("/panel/support").text
    for text in ("Чем мы можем помочь?", "База знаний", "Платежи и баланс", "Ваши заявки", "У вас пока нет заявок",
                 "С чем нужна помощь?", "Пополнение не зачислилось", "/panel/support/new?topic=order_missing"):
        assert text in page, text
    assert "Сколько ждать зачисления?" in c.get("/panel/support/kb/payments").text
    form = c.get("/panel/support/new?topic=order_missing").text
    assert "Алмазы или товар не пришли" in form and 'name="order_ref"' in form
    assert 'name="order_ref"' not in c.get("/panel/support/new?topic=account").text

    calls = []

    class Api:
        def __init__(self, token):
            pass

        def __call__(self, method, **p):
            calls.append((method, p))
            return {"message_id": 900 + len(calls)} if method == "sendMessage" else {}

    monkeypatch.setattr("donatix.tgbot.TelegramApi", Api)
    threads = []
    monkeypatch.setattr("threading.Thread", lambda target, args, daemon: threads.append((target, args)) or
                        type("T", (), {"start": lambda self: target(*args)})())
    r = c.post("/panel/support", data={"csrf": csrf_of(form), "topic": "order_missing", "subject": "x",
                                       "order_ref": "dx-5", "text": "Не пришли"})
    first = [p for m, p in calls if m == "sendMessage"][-1]
    assert "reply_parameters" not in first and tickets.get(conn, 1)["admin_msg"]
    c.post("/panel/support/1", data={"csrf": csrf_of(r.text), "text": "Ещё жду"})
    second = [p for m, p in calls if m == "sendMessage"][-1]
    assert second["reply_parameters"]["message_id"] == tickets.get(conn, 1)["admin_msg"]   # та же ветка


def test_ticket_spam_limited(client, conn, config):
    import re

    from conftest import make_client, web_login
    from donatix import tickets
    uid = make_client(conn, login="spammer")[0]
    web_login(client, "spammer", "password123")
    tid = tickets.create(conn, config, uid, "", "other", "", "помогите")
    csrf = re.search(r'name="csrf" value="([^"]+)"', client.get(f"/panel/support/{tid}").text).group(1)
    for i in range(25):
        client.post(f"/panel/support/{tid}", data={"csrf": csrf, "text": f"msg {i}"})
    n = conn.execute("SELECT COUNT(*) FROM ticket_messages WHERE ticket_id = ?", (tid,)).fetchone()[0]
    assert n == 1 + 20   # первое сообщение + не больше 20 за 10 минут — админа в Telegram не заспамить
