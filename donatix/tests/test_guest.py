"""Гость смотрит каталог и цены без входа и покупает без регистрации: ID → оплата → заказ оформляется сам."""
from conftest import RECEIPT, balance, csrf_of, web_login
from fastapi.testclient import TestClient


def _product(conn, kind="topup"):
    return conn.execute("SELECT id FROM products WHERE kind = ? AND active = 1 LIMIT 1", (kind,)).fetchone()["id"]


def test_guest_sees_catalog_and_prices(app, conn):
    guest = TestClient(app)
    page = guest.get("/panel/catalog?kind=topup")
    assert page.status_code == 200 and "Регистрация" in page.text and "Войти" in page.text
    pid = _product(conn)
    buy = guest.get(f"/panel/buy/{pid}")
    assert buy.status_code == 200
    assert "Зарегистрироваться и купить" not in buy.text and " с.</span>" in buy.text   # цена в сомони, купить сразу
    assert guest.get("/panel/catalog?kind=telegram").status_code == 200
    home = guest.get("/").text
    assert "Выберите игру" in home and "Без регистрации" in home


def test_guest_buys_without_registration(app, config, conn, monkeypatch):
    """Гость: ID → «Купить» → оплата ровно стоимости (без минимума пополнения) → админ подтвердил → заказ сам."""
    from donatix import db, payments, quickbuy
    monkeypatch.setattr("donatix.worker.notify_admin_file", lambda *a, **k: None)
    config.pay_methods = {"alif": "Алиф: +992 90 000 00 00 (Али)"}
    db.set_setting(conn, "pay.min_tjs", "500")
    guest = TestClient(app)
    pid = _product(conn)
    token = csrf_of(guest.get(f"/panel/buy/{pid}").text)
    r = guest.post(f"/panel/buy/{pid}", data={"csrf": token, "quantity": "1", "field_player_id": "123456789"},
                   follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/panel/balance?buy=1"
    user = conn.execute("SELECT * FROM users WHERE email LIKE '%@guest.donatix.tj'").fetchone()
    assert user is not None and quickbuy.is_guest(user) and balance(conn, user["id"]) == 0
    page = guest.get("/panel/balance?buy=1").text
    assert "Оплата покупки" in page and "123456789" in page and "Сохраните аккаунт" not in page
    tjs = page.split('readonly')[0].rsplit('value="', 1)[1].split('"')[0]
    r = guest.post("/panel/balance", data={"csrf": csrf_of(page), "method": "alif", "amount_tjs": "1", "buy": "1"},
                   files=RECEIPT)
    pay = conn.execute("SELECT * FROM payments WHERE user_id = ?", (user["id"],)).fetchone()
    assert pay["intent"] and pay["pay_amount"] == tjs and float(tjs) < 500   # сумму считаем сами, минимума нет
    assert "заказ оформится сам" in r.text
    from donatix import tgbot
    note = tgbot.payment_event(conn, pay["id"], config)[0]                      # что видит админ в боте
    assert "Клиент: Гость G-" in note and "🛒 Покупка:" in note and "123456789" in note
    assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0

    payments.confirm(conn, config, pay["id"], 1, who="админ")
    assert quickbuy.run_pending(conn, config, app.state.supplier) == 1
    order = conn.execute("SELECT * FROM orders WHERE user_id = ?", (user["id"],)).fetchone()
    assert order is not None and order["product_id"] == pid and "123456789" in order["fields_json"]
    assert quickbuy.run_pending(conn, config, app.state.supplier) == 0          # второй раз заказ не создаётся
    st = guest.get(f"/panel/data/payment/{pay['id']}").json()
    assert st == {"status": "paid", "order": order["public_id"]}

    home = guest.get("/panel").text                                              # сохранить аккаунт
    assert "Сохраните аккаунт" in home
    code = quickbuy.code_of(conn, user["id"])
    assert code.startswith("G-") and code in home                               # код покупателя виден

    later = TestClient(app)                                                      # вернулся через неделю: тот же браузер
    later.cookies.set("dx_guest", guest.cookies.get("dx_guest"))
    assert order["public_id"] in later.get("/panel/orders").text
    stranger = TestClient(app)                                                   # подделанный ключ — не входит
    stranger.cookies.set("dx_guest", f"{user['id']}.wrong")
    assert stranger.get("/panel/orders", follow_redirects=False).status_code == 303

    admin = TestClient(app)                                                      # админ находит по коду
    web_login(admin, "admin@example.com", "adminpass123")
    r = admin.get("/admin/users", params={"q": code.lower().replace("-", " ")}, follow_redirects=False)
    assert r.headers["location"] == f"/admin/users/{user['id']}"
    assert f"Гость {code}" in admin.get(r.headers["location"]).text
    from donatix import tgbot
    text, buttons = tgbot.screen_client(conn, config, quickbuy.by_code(conn, code))
    assert f"Гость {code}" in text and any("hy:0:" in b[1] for row in buttons for b in row)
    save = guest.get("/panel/save").text
    guest.post("/panel/save", data={"csrf": csrf_of(save), "email": "ali@example.com", "login": "ali_2006",
                                    "password": "password123"})
    again = TestClient(app)
    web_login(again, "ali@example.com", "password123")
    assert order["public_id"] in again.get("/panel/orders").text
    old_cookie = TestClient(app)                                                 # аккаунт сохранён — по cookie не входит
    old_cookie.cookies.set("dx_guest", guest.cookies.get("dx_guest"))
    assert old_cookie.get("/panel/orders", follow_redirects=False).status_code == 303
    assert quickbuy.code_of(conn, user["id"]) == code                            # код для поиска остаётся


def test_guest_wrong_id_creates_no_account(app, conn, monkeypatch):
    from donatix import orders, quickbuy
    def bad(*a, **k):
        raise orders.OrderError("Аккаунт не найден — проверьте ID.", "account_not_found")
    monkeypatch.setattr(quickbuy, "precheck", bad)
    guest = TestClient(app)
    pid = _product(conn)
    token = csrf_of(guest.get(f"/panel/buy/{pid}").text)
    r = guest.post(f"/panel/buy/{pid}", data={"csrf": token, "quantity": "1", "field_player_id": "1"})
    assert r.status_code == 400 and "проверьте ID" in r.text
    assert conn.execute("SELECT COUNT(*) FROM users WHERE email LIKE '%@guest.donatix.tj'").fetchone()[0] == 0
    assert guest.get("/panel/balance", follow_redirects=False).headers["location"] == "/login"


def test_client_without_money_pays_only_the_difference(app, config, conn, monkeypatch):
    from conftest import make_client
    from donatix import quickbuy
    make_client(conn, balance="0.05")
    client = TestClient(app)
    web_login(client, "shop1@example.com", "password123")
    pid = _product(conn)
    token = csrf_of(client.get(f"/panel/buy/{pid}").text)
    r = client.post(f"/panel/buy/{pid}", data={"csrf": token, "quantity": "1", "field_player_id": "123456789"},
                    follow_redirects=False)
    assert r.headers["location"] == "/panel/balance?buy=1"
    page = client.get("/panel/balance?buy=1").text
    assert "Оплата покупки" in page


def test_register_returns_guest_to_the_product(app, conn):
    guest = TestClient(app)
    pid = _product(conn)
    page = guest.get(f"/register?next=/panel/buy/{pid}")
    assert "вернём вас к товару" in page.text
    r = guest.post("/register", data={"csrf": csrf_of(page.text), "email": "new@example.com", "login": "newbie",
                                      "password": "password123", "password2": "password123"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/panel/buy/{pid}"
    assert "Купить" in guest.get(f"/panel/buy/{pid}").text


def test_next_only_inside_panel(app):
    guest = TestClient(app)
    page = guest.get("/register?next=https://evil.example/x")
    r = guest.post("/register", data={"csrf": csrf_of(page.text), "email": "n2@example.com", "login": "newbie2",
                                      "password": "password123", "password2": "password123"}, follow_redirects=False)
    assert r.headers["location"] == "/panel"
