"""Тексты кабинета: причина возврата с точкой и без повторов, пустые состояния, «Забыли пароль?»."""

from conftest import make_client, web_login
from fastapi.testclient import TestClient

from donatix import orders


def test_refund_reason_reads_as_sentences(app, config, conn, supplier):
    uid, _ = make_client(conn, login="refundy", balance="50")
    user = conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    pid = conn.execute("SELECT id FROM products WHERE kind = 'gift_card' AND active = 1 LIMIT 1").fetchone()["id"]
    supplier.fail_next = "reject_other"   # «Поставщик отклонил заказ: Игрок не найден» — без точки в конце
    rejected, _ = orders.create_order(conn, config, supplier, user, product_id=pid, source="web")
    by_admin, _ = orders.create_order(conn, config, supplier, user, product_id=pid, source="web")
    orders.fail_and_refund(conn, by_admin["id"], "Отменён администратором")
    no_stock, _ = orders.create_order(conn, config, supplier, user, product_id=pid, source="web")
    orders.fail_and_refund(conn, no_stock["id"], "Товар временно недоступен. Деньги возвращены на баланс.")
    c = TestClient(app)
    web_login(c, "refundy@example.com", "password123")
    page = c.get(f"/panel/orders/{rejected['public_id']}").text
    assert "Игрок не найден. Деньги вернулись на баланс." in page
    page = c.get(f"/panel/orders/{by_admin['public_id']}").text
    assert "Отменён администратором. Деньги вернулись на баланс." in page
    page = c.get(f"/panel/orders/{no_stock['public_id']}").text
    assert "Деньги возвращены на баланс." in page and "Деньги вернулись на баланс." not in page


def test_bots_empty_state_does_not_point_to_missing_form(app, conn):
    make_client(conn, login="nobots", balance="")
    c = TestClient(app)
    web_login(c, "nobots@example.com", "password123")
    page = c.get("/panel/bots").text
    assert "Свой бот пока закрыт" in page and "Ботов пока нет." in page and "подключите первый выше" not in page
    assert "Заказов пока нет." in c.get("/panel/orders").text                         # ещё ничего не покупал
    assert "Заказов не найдено." in c.get("/panel/orders?q=dx-999").text               # а это — поиск без результата


def test_forgot_link_always_shown_and_page_explains_support(client):
    assert 'href="/forgot"' in client.get("/login").text
    page = client.get("/forgot").text   # ни почты, ни Google, ни Telegram — только поддержка
    assert 'href="/panel/support"' in page and "сразу придумаете новый пароль" not in page


def test_footer_shows_panel_link_only_when_logged_in(app, client, conn):
    assert '<a href="/login">Войти</a>' in client.get("/").text            # гость: «Войти», «Стать партнёром»
    make_client(conn, login="footy", balance="")
    c = TestClient(app)
    web_login(c, "footy@example.com", "password123")
    page = c.get("/").text
    assert '<a href="/panel">Панель</a>' in page and '<a href="/login">Войти</a>' not in page
