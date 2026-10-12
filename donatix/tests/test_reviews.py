"""Отзывы: только к своему выполненному заказу, один на заказ, ответ магазина, уведомления, скрытие."""
import pytest
from conftest import make_client, web_login
from test_analytics import _order as _mk

from donatix import accounts, reviews


def _order(conn, uid, status, total):
    _mk(conn, uid, status, total)
    return conn.execute("SELECT MAX(id) FROM orders").fetchone()[0]


def _pub(conn, oid):
    return conn.execute("SELECT public_id FROM orders WHERE id = ?", (oid,)).fetchone()[0]


def test_add_reply_and_rules(app, config, conn):
    uid = make_client(conn, balance="5")[0]
    user = accounts.get_user(conn, uid)
    done, busy = _order(conn, uid, "completed", 100000), _order(conn, uid, "processing", 100000)
    with pytest.raises(reviews.ReviewError, match="выполнен"):
        reviews.add(conn, config, user, _pub(conn, busy), 5, "Супер")
    with pytest.raises(reviews.ReviewError, match="оценку"):
        reviews.add(conn, config, user, _pub(conn, done), 0, "Супер")
    rid = reviews.add(conn, config, user, _pub(conn, done), 4, "Всё пришло за минуту")
    assert reviews.add(conn, config, user, _pub(conn, done), 5, "Всё пришло за минуту!") == rid   # правка, не дубль
    admin = conn.execute("SELECT * FROM users WHERE role = 'admin'").fetchone()
    assert conn.execute("SELECT COUNT(*) FROM notifications WHERE user_id = ? AND link = '/admin/reviews'",
                        (admin["id"],)).fetchone()[0] >= 1                     # админу пришло «новый отзыв»
    reviews.reply(conn, config, admin, rid, "Спасибо, ждём снова!")
    assert conn.execute("SELECT COUNT(*) FROM notifications WHERE user_id = ? AND text LIKE 'Магазин ответил%'",
                        (uid,)).fetchone()[0] == 1
    with pytest.raises(reviews.ReviewError, match="уже ответил"):
        reviews.add(conn, config, user, _pub(conn, done), 1, "передумал")
    s = reviews.summary(conn)
    assert s["total"] == 1 and s["avg"] == 5 and s["unanswered"] == 0
    reviews.set_hidden(conn, rid, True)
    assert reviews.summary(conn)["total"] == 0 and reviews.listing(conn) == []


def test_other_users_order_rejected(app, config, conn):
    a = make_client(conn, login="aaa", balance="5")[0]
    b = make_client(conn, login="bbb", balance="5")[0]
    oid = _order(conn, a, "completed", 100000)
    with pytest.raises(reviews.ReviewError, match="не найден"):
        reviews.add(conn, config, accounts.get_user(conn, b), _pub(conn, oid), 5, "чужой заказ")


def test_pages(app, client, config, conn):
    uid = make_client(conn, balance="5")[0]
    oid = _order(conn, uid, "completed", 100000)
    token = web_login(client, "shop1@example.com", "password123")
    page = client.get(f"/panel/orders/{_pub(conn, oid)}").text
    assert "Оцените заказ" in page
    r = client.post("/panel/reviews", data={"csrf": token, "order": _pub(conn, oid), "rating": "5",
                                            "text": "Быстро и честно"}, follow_redirects=False)
    assert r.status_code == 303
    pub = client.get("/reviews").text
    assert "Быстро и честно" in pub and "покупка подтверждена" in pub and "Отзывы покупателей" in pub
    assert "Быстро и честно" in client.get("/").text                            # на главной — последние отзывы
    assert "Быстро и честно" not in client.get("/reviews?stars=1").text
