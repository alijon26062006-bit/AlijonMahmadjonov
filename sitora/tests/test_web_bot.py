import json

from fastapi.testclient import TestClient

from sitora import db, shop
from sitora.bot import Handler
from sitora.tg import sign_init_data
from sitora.web import create_app
from conftest import TOKEN

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def client(config, bot=None, uid=1, name="ali_dev"):
    c = TestClient(create_app(config, bot))
    c.headers["X-Init-Data"] = sign_init_data({"id": uid, "username": name, "first_name": "Али", "language_code": "ru"}, TOKEN)
    return c


def test_api_requires_telegram_signature(config):
    c = TestClient(create_app(config))
    assert c.get("/api/me").status_code == 401
    c.headers["X-Init-Data"] = sign_init_data({"id": 1}, "000:wrong")
    assert c.get("/api/me").status_code == 401


def test_me_buy_and_errors(config, conn):
    c = client(config)
    me = c.get("/api/me").json()
    assert me["user"]["balance"] == 0 and me["user"]["lang"] == "ru" and me["methods"] == [{"code": "alif", "title": "Алиф Моби"}]
    r = c.post("/api/order", json={"kind": "stars", "qty": 100, "to": "@ali_dev"})
    assert r.status_code == 400 and "не хватает" in r.json()["error"]
    with db.tx(conn):
        shop.move(conn, 1, 50000, "seed")
    r = c.post("/api/order", json={"kind": "stars", "qty": 100, "to": "@ali_dev"}).json()
    assert r["order"]["title"] == "100 Stars" and r["user"]["balance"] == 50000 - r["order"]["price"]


def test_topup_receipt_goes_to_admin_and_buys(config, conn, bot, faketg):
    c = client(config, bot)
    t = c.post("/api/topup", json={"method": "alif", "intent": {"kind": "stars", "qty": 100, "to": "@ali_dev"}}).json()["topup"]
    assert t["amount"] == shop.quote(conn, {"kind": "stars", "qty": 100})["price"]
    assert c.post(f"/api/topup/{t['id']}/receipt", files={"file": ("a.txt", b"hello")}).status_code == 400   # не картинка
    r = c.post(f"/api/topup/{t['id']}/receipt", files={"file": ("c.png", PNG)})
    assert r.status_code == 200
    again = c.post("/api/topup", json={"method": "alif", "amount": "5"}).json()["topup"]
    assert c.post(f"/api/topup/{again['id']}/receipt", files={"file": ("c.png", PNG)}).status_code == 400  # тот же чек
    import time
    for _ in range(50):
        if conn.execute("SELECT admin_msgs FROM topups WHERE id = ?", (t["id"],)).fetchone()[0]:
            break
        time.sleep(0.02)
    assert "sendPhoto" in faketg.methods()
    h = Handler(config, bot)
    h.on_button({"id": "q", "from": {"id": 5}, "data": f"tp:ok:{t['id']}"})          # не админ
    assert conn.execute("SELECT status FROM topups WHERE id = ?", (t["id"],)).fetchone()[0] == "pending"
    h.on_button({"id": "q", "from": {"id": 999, "first_name": "Owner"}, "data": f"tp:ok:{t['id']}"})
    assert conn.execute("SELECT status FROM topups WHERE id = ?", (t["id"],)).fetchone()[0] == "paid"
    assert conn.execute("SELECT title FROM orders").fetchone()[0] == "100 Stars"
    assert conn.execute("SELECT balance FROM users WHERE id = 1").fetchone()[0] == 0
    assert "editMessageCaption" in faketg.methods()


def test_start_and_admin_commands(config, conn, bot, faketg):
    h = Handler(config, bot)
    msg = lambda uid, text: {"message": {"from": {"id": uid, "first_name": "A"}, "chat": {"id": uid, "type": "private"}, "text": text}}  # noqa: E731
    h.handle(msg(1, "/start"))
    assert faketg.methods()[-1] in ("sendPhoto", "sendMessage")
    sent = faketg.calls[-1][1].decode("utf-8", "ignore")
    assert "web_app" in sent or faketg.methods()[-1] == "sendPhoto"
    h.handle(msg(1, "/rate 20"))                                    # клиенту нельзя
    assert db.get_setting(conn, "rate") == "11"
    h.handle(msg(999, "/rate 11.5")); h.handle(msg(999, "/markup 12"))
    assert db.get_setting(conn, "rate") == "11.5" and db.get_setting(conn, "markup") == "12"
    h.handle(msg(999, "/card add dc 4444 5555 6666 7777 · Али"))
    assert [c["method"] for c in shop.cards(conn)] == ["alif", "dc"]
    h.handle(msg(999, "/give 1 25"))
    assert conn.execute("SELECT balance FROM users WHERE id = 1").fetchone()[0] == 2500
    h.handle(msg(999, "/rate abc"))                                  # ошибка — без падения


def test_gift_link_start(config, conn, bot):
    shop.touch_user(conn, {"id": 1, "username": "ali_dev"})
    with db.tx(conn):
        shop.move(conn, 1, 10000, "seed")
    o = shop.place_order(conn, 1, {"kind": "gift", "gift_id": "g1", "to": "@new_friend"})
    h = Handler(config, bot)
    h.handle({"message": {"from": {"id": 7, "username": "new_friend"}, "chat": {"id": 7, "type": "private"},
                          "text": f"/start g_{o['gift_token']}"}})
    assert conn.execute("SELECT status, recipient_id FROM orders").fetchone()[:] == ("paid", 7)


def test_bank_topup_amount(config, conn):
    c = client(config)
    price = shop.quote(conn, {"kind": "stars", "qty": 100})["price"]
    c.get("/api/me")
    with db.tx(conn):
        shop.move(conn, 1, 500, "seed")                                   # 5 сомони — не хватает
    t = c.post("/api/topup", json={"method": "alif", "intent": {"kind": "stars", "qty": 100, "to": "@ali_dev"}}).json()["topup"]
    assert t["amount"] == price - 500                                     # только недостающее
    with db.tx(conn):
        shop.move(conn, 1, 100000, "seed")                                # хватает, но выбрал перевод
    t = c.post("/api/topup", json={"method": "alif", "intent": {"kind": "stars", "qty": 100, "to": "@ali_dev"}}).json()["topup"]
    assert t["amount"] == price
    assert c.post("/api/topup", json={"method": "alif", "intent": {"kind": "stars", "qty": 100, "to": "@a"}}).status_code == 400
