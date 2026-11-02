"""Админка, второй круг: огромная сумма не роняет страницу, знак перед $, склонения, пустые состояния."""

from conftest import make_client, web_login
from fastapi.testclient import TestClient

from donatix import orders


def _admin(app):
    c = TestClient(app)
    token = web_login(c, "admin@example.com", "adminpass123")
    return c, token


def test_huge_balance_amount_is_an_error_not_500(app, conn):
    uid, _ = make_client(conn, login="bigsum", balance="10")
    c, token = _admin(app)
    r = c.post(f"/admin/users/{uid}/balance", data={"csrf": token, "amount": "1e30", "note": ""}, follow_redirects=False)
    assert r.status_code == 303
    assert "Сумма — число" in c.get(f"/admin/users/{uid}").text


def test_balance_minus_sign_goes_before_dollar(app, conn):
    uid, _ = make_client(conn, login="minus", balance="10")
    c, token = _admin(app)
    page = c.post(f"/admin/users/{uid}/balance", data={"csrf": token, "amount": "-2.5", "note": "Списание"}).text
    assert "Баланс изменён на −$2.5000." in page
    assert "−$2.5000" in page and "$-2.5000" not in page


def test_dashboard_rings_and_finance_count_words(app, config, conn, supplier):
    uid, _ = make_client(conn, login="ringer", balance="50")
    user = conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    pid = conn.execute("SELECT id FROM products WHERE kind = 'gift_card' AND active = 1 LIMIT 1").fetchone()["id"]
    order, _ = orders.create_order(conn, config, supplier, user, product_id=pid, source="web")
    orders.complete(conn, order["id"], None)
    c, _ = _admin(app)
    page = c.get("/admin").text
    assert "1 из 1 заказа" in page and "из 1 заказов" not in page
    assert "продано 1 заказ на" in c.get("/admin/finance").text


def test_reviews_empty_state(app):
    c, _ = _admin(app)
    page = c.get("/admin/reviews").text
    assert "Отзывов пока нет." in page and "Все отзывы с ответом" not in page


def test_pending_payment_without_receipt_has_hint(app, conn):
    from donatix import db
    uid, _ = make_client(conn, login="norcpt", balance="")
    conn.execute("INSERT INTO payments (user_id, method, amount_micro, pay_amount, pay_currency, reference, status, "
                 "created_at) VALUES (?, 'card', 100000, '109', 'TJS', ?, 'pending', ?)", (uid, "f" * 64, db.now()))
    c, _ = _admin(app)
    page = c.get("/admin/payments").text
    assert "Чека пока нет" in page
    assert 'overflow-wrap:anywhere">Чек / хэш:' in page
