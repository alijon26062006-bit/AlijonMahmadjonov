from sitora import db, shop
from test_web_bot import PNG, client


def test_admin_only(config):
    c = client(config)
    assert c.get("/api/me").json()["admin"] is False
    assert c.get("/api/admin/summary").status_code == 403
    assert c.post("/api/admin/settings", json={"rate": "20"}).status_code == 403
    a = client(config, uid=999, name="boss")
    assert a.get("/api/me").json()["admin"] is True
    assert a.get("/api/admin/summary").status_code == 200


def test_admin_flow(config, conn, bot, faketg):
    cl = client(config, bot)
    t = cl.post("/api/topup", json={"method": "alif", "amount": "30"}).json()["topup"]
    cl.post(f"/api/topup/{t['id']}/receipt", files={"file": ("c.png", PNG)})
    a = client(config, bot, uid=999, name="boss")
    s = a.get("/api/admin/summary").json()
    assert [x["id"] for x in s["topups"]] == [t["id"]] and s["topups"][0]["who"] == "Али @ali_dev"
    assert a.get(f"/api/admin/receipt/{t['id']}").content == PNG
    assert cl.get(f"/api/admin/receipt/{t['id']}").status_code == 403           # клиент чек не увидит
    assert a.post(f"/api/admin/topup/{t['id']}", json={"ok": True}).status_code == 200
    assert a.post(f"/api/admin/topup/{t['id']}", json={"ok": True}).status_code == 400   # второй раз нельзя
    assert conn.execute("SELECT balance FROM users WHERE id = 1").fetchone()[0] == 3000
    # заказ: отмена с возвратом
    o = shop.place_order(conn, 1, {"kind": "stars", "qty": 50, "to": "@ali_dev"})
    assert a.post(f"/api/admin/order/{o['id']}", json={"action": "refund"}).status_code == 200
    assert conn.execute("SELECT balance FROM users WHERE id = 1").fetchone()[0] == 3000
    assert a.post(f"/api/admin/order/{o['id']}", json={"action": "refund"}).status_code == 400
    # карты и цены
    assert a.post("/api/admin/cards", json={"method": "dc", "details": "4444 5555 6666 7777 Али"}).status_code == 200
    cid = [x for x in a.get("/api/admin/summary").json()["cards"] if x["method"] == "dc"][0]["id"]
    a.post(f"/api/admin/cards/{cid}/off")
    assert [x["method"] for x in shop.cards(conn)] == ["alif"]
    assert a.post("/api/admin/settings", json={"rate": "11,4", "markup": "12", "gift_star": "0,3"}).status_code == 200
    assert (db.get_setting(conn, "rate"), db.get_setting(conn, "markup"), db.get_setting(conn, "gift_star_diram")) == ("11.4", "12", "30")
    assert a.post("/api/admin/settings", json={"rate": "99"}).status_code == 400
    # клиент: поиск, баланс, блок
    u = a.get("/api/admin/user", params={"q": "@ali_dev"}).json()
    assert u["user"]["id"] == 1 and u["ledger"]
    a.post("/api/admin/user/1", json={"amount": "-10", "note": "проверка"})
    assert conn.execute("SELECT balance FROM users WHERE id = 1").fetchone()[0] == 2000
    a.post("/api/admin/user/1", json={"banned": True})
    assert cl.get("/api/me").status_code == 403


def test_min_topup_everywhere(config, conn):
    a = client(config, uid=999, name="boss")
    c = client(config)
    assert c.get("/api/me").json()["min_topup"] == 100                    # по умолчанию 1 сомони
    assert a.post("/api/admin/settings", json={"min_topup": "0,5"}).status_code == 400
    assert a.post("/api/admin/settings", json={"min_topup": "5"}).status_code == 200
    assert a.get("/api/admin/summary").json()["settings"]["min_topup"] == "5"
    assert c.get("/api/me").json()["min_topup"] == 500
    r = c.post("/api/topup", json={"method": "alif", "amount": 2})
    assert r.status_code == 400 and "5" in r.json()["error"]              # 2 < 5 — нельзя
    assert c.post("/api/topup", json={"method": "alif", "amount": 5}).json()["topup"]["amount"] == 500
    # покупка переводом: не хватает 1 сомони, а минимум 5 — платит 5 (остаток на баланс)
    price = shop.quote(conn, {"kind": "stars", "qty": 100})["price"]
    with db.tx(conn):
        shop.move(conn, 1, price - 100, "seed")
    t = c.post("/api/topup", json={"method": "alif", "intent": {"kind": "stars", "qty": 100, "to": "@ali_dev"}}).json()["topup"]
    assert t["amount"] == 500
