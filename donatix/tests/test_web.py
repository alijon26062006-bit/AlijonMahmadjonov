import re

from conftest import balance, csrf_of, web_login

from donatix import orders


def _register(client, login="newshop"):
    token = csrf_of(client.get("/register").text)
    return client.post("/register", data={
        "csrf": token, "email": f"{login}@example.com", "login": login,
        "password": "password123", "password2": "password123", "project": "t.me/newshop",
    }, follow_redirects=False)


def test_home_and_docs(client):
    assert "Donatix" in client.get("/").text
    assert "/api/v1" in client.get("/docs").text


def test_panel_requires_login(client):
    r = client.get("/panel", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"


def test_csrf_required(client):
    r = client.post("/login", data={"email": "admin@example.com", "password": "adminpass123"})
    assert r.status_code == 403


def test_register_then_admin_approves_and_credits(client, conn, app):
    r = _register(client)
    assert r.status_code == 303 and r.headers["location"] == "/panel"
    assert "ждёт одобрения" in client.get("/panel").text
    uid = conn.execute("SELECT id, status, project FROM users WHERE login = 'newshop'").fetchone()
    assert uid["status"] == "pending" and uid["project"] == "t.me/newshop"

    from fastapi.testclient import TestClient
    admin = TestClient(app)
    token = web_login(admin, "admin@example.com", "adminpass123")
    assert "Новых заявок: 1" in admin.get("/admin").text
    r = admin.post(f"/admin/users/{uid['id']}", data={"csrf": token, "status": "active", "tier": "silver",
                                                     "markup_override": ""}, follow_redirects=False)
    assert r.status_code == 303
    admin.post(f"/admin/users/{uid['id']}/balance", data={"csrf": token, "amount": "50", "note": "USDT"})
    assert balance(conn, uid["id"]) == 500_000
    # Нельзя увести в минус
    admin.post(f"/admin/users/{uid['id']}/balance", data={"csrf": token, "amount": "-60", "note": ""})
    assert balance(conn, uid["id"]) == 500_000


def test_client_cannot_open_admin(client, conn):
    _register(client, "sneaky")
    assert client.get("/admin").status_code == 403


def test_buy_in_panel(client, conn, supplier):
    from donatix import accounts, db
    uid = accounts.create_user(conn, email="p@example.com", login="panelshop", password="password123",
                               status="active")
    with db.tx(conn):
        accounts.post_ledger(conn, uid, 100_000, "Пополнение")
    token = web_login(client, "p@example.com", "password123")
    page = client.get("/panel/buy/tg-stars").text
    idem = re.search(r'name="idem" value="([^"]+)"', page).group(1)
    data = {"csrf": token, "idem": idem, "field_telegram_username": "@buyer_one", "quantity": "50"}
    r = client.post("/panel/buy/tg-stars", data=data, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/panel/orders/dx-")
    # Двойное нажатие кнопки — второй заказ не создаётся
    r2 = client.post("/panel/buy/tg-stars", data=data, follow_redirects=False)
    assert r2.headers["location"] == r.headers["location"]
    assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 1
    orders.process_pending(conn, supplier)
    assert "Готово" in client.get(r.headers["location"]).text


def test_panel_buy_error_shown(client, conn):
    from donatix import accounts
    accounts.create_user(conn, email="z@example.com", login="zero", password="password123", status="active")
    token = web_login(client, "z@example.com", "password123")
    r = client.post("/panel/buy/tg-stars", data={"csrf": token, "idem": "x", "field_telegram_username": "@buyer_one",
                                                "quantity": "50"})
    assert r.status_code == 400 and "Недостаточно средств" in r.text


def test_api_key_lifecycle(client, conn):
    from donatix import accounts
    accounts.create_user(conn, email="k@example.com", login="keys", password="password123", status="active")
    token = web_login(client, "k@example.com", "password123")
    page = client.post("/panel/api/keys", data={"csrf": token, "name": "bot"}).text  # после редиректа
    key = re.search(r"(dx_live_[A-Za-z0-9_\-]+)", page).group(1)
    assert client.get("/api/v1/balance", headers={"X-API-Key": key}).status_code == 200
    assert key not in client.get("/panel/api").text  # показывается один раз
    key_id = conn.execute("SELECT id FROM api_keys").fetchone()[0]
    client.post(f"/panel/api/keys/{key_id}/revoke", data={"csrf": token})
    assert client.get("/api/v1/balance", headers={"X-API-Key": key}).status_code == 401


def test_admin_refunds_attention_order(client, conn, app, shop, supplier, monkeypatch):
    monkeypatch.setattr(orders, "IN_FLIGHT_SECONDS", 0)
    supplier.fail_next = "unavailable"
    client.post("/api/v1/orders", headers=shop["h"],
                json={"product_id": "tg-premium-3", "fields": {"telegram_username": "@someone"}})
    orders.process_pending(conn, supplier)
    oid = conn.execute("SELECT id, status FROM orders").fetchone()
    assert oid["status"] == "attention"
    token = web_login(client, "admin@example.com", "adminpass123")
    assert "требующих внимания: 1" in client.get("/admin").text
    client.post(f"/admin/orders/{oid['id']}/refund", data={"csrf": token, "reason": "Нет у поставщика"})
    assert balance(conn, shop["id"]) == 1_000_000
    client.post(f"/admin/orders/{oid['id']}/refund", data={"csrf": token, "reason": "ещё раз"})
    assert balance(conn, shop["id"]) == 1_000_000


def test_catalog_games_and_regions(app, config, conn):
    from conftest import web_login
    from fastapi.testclient import TestClient

    from donatix import accounts, catalog

    catalog.sync_catalog(conn, app.state.supplier)
    accounts.create_user(conn, email="g@example.com", login="gamer", password="password123", status="active")
    client = TestClient(app)
    web_login(client, "g@example.com", "password123")
    page = client.get("/panel/catalog?kind=topup").text
    assert "game-card" in page and "Free Fire" in page and "Регионов: 2" in page
    assert "pack-card" not in page  # сначала выбирают игру
    assert "от $0.97" in page and "$0.89<" not in page  # 0.89 + 8%, закупку не видно
    page = client.get("/panel/catalog?kind=topup&category=free_fire").text
    assert page.count("pack-card\"") == 4 and "Турция" in page and "Все регионы" in page
    page = client.get("/panel/catalog?kind=topup&category=free_fire&region=TR").text
    assert page.count("pack-card\"") == 2
