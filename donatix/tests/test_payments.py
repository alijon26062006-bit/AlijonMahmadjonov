from fastapi.testclient import TestClient
from conftest import balance, web_login

from donatix import accounts, orders


def _setup(app, config, conn):
    config.pay_methods = {"alif": "Алиф: +992 90 000 00 00 (Али)", "usdt_trc20": "TXyz…"}
    uid = accounts.create_user(conn, email="c@example.com", login="client1", password="password123", status="active")
    client = TestClient(app)
    token = web_login(client, "c@example.com", "password123")
    return uid, client, token


def test_topup_request_confirm_notify(app, config, conn):
    uid, client, token = _setup(app, config, conn)
    page = client.get("/panel/balance").text
    assert "Алиф (Alif Mobi)" in page and "+992 90 000 00 00" in page
    r = client.post("/panel/balance", data={"csrf": token, "method": "alif", "amount": "50", "reference": "4821"})
    assert "Заявка #1 создана" in r.text and "545.00 TJS" in r.text  # 50 × 10.9

    admin = TestClient(app)
    atoken = web_login(admin, "admin@example.com", "adminpass123")
    assert "Заявок на пополнение: 1" in admin.get("/admin").text
    assert "client1" in admin.get("/admin/payments").text
    admin.post("/admin/payments/1/confirm", data={"csrf": atoken, "credit": "50"})
    assert balance(conn, uid) == 500_000
    admin.post("/admin/payments/1/confirm", data={"csrf": atoken, "credit": "50"})  # повтор — без второго зачисления
    assert balance(conn, uid) == 500_000

    panel = client.get("/panel").text
    assert 'class="dot-count">1<' in panel
    notes = client.get("/panel/notifications").text
    assert "Баланс пополнен на $50.0000" in notes
    assert 'class="dot-count"' not in client.get("/panel").text


def test_topup_validation_and_reject(app, config, conn):
    uid, client, token = _setup(app, config, conn)
    r = client.post("/panel/balance", data={"csrf": token, "method": "binance", "amount": "50"})
    assert "Выберите способ оплаты" in r.text
    r = client.post("/panel/balance", data={"csrf": token, "method": "alif", "amount": "1"})
    assert "Минимальная сумма" in r.text
    client.post("/panel/balance", data={"csrf": token, "method": "usdt_trc20", "amount": "20"})
    admin = TestClient(app)
    atoken = web_login(admin, "admin@example.com", "adminpass123")
    admin.post("/admin/payments/1/reject", data={"csrf": atoken, "reason": "Перевод не найден"})
    assert balance(conn, uid) == 0
    assert "Перевод не найден" in client.get("/panel/notifications").text


def test_refund_and_admin_credit_notify(client, conn, shop, supplier, app):
    supplier.fail_next = "reject"
    client.post("/api/v1/orders", headers=shop["h"],
                json={"product_id": "tg-stars", "quantity": 50, "fields": {"telegram_username": "@player_one"}})
    rows = conn.execute("SELECT text FROM notifications WHERE user_id = ?", (shop["id"],)).fetchall()
    assert any("вернулись на баланс" in r["text"] for r in rows)


def test_errors_page(client, conn, shop, supplier):
    supplier.fail_next = "reject"
    client.post("/api/v1/orders", headers=shop["h"],
                json={"product_id": "tg-stars", "quantity": 50, "fields": {"telegram_username": "@player_one"}})
    token = web_login(client, "admin@example.com", "adminpass123")
    page = client.get("/admin/errors").text
    assert "dx-1" in page and "Деньги возвращены" in page
    assert token and orders
