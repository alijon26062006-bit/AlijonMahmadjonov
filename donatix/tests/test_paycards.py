"""Несколько карт на банк: ровные суммы, карта держится за клиентом, чек — хозяину карты, ИИ перенаправляет."""

from donatix import cashiers, db, paycards, payments


def _method(conn, config):
    config.pay_methods = {"alif": "Алиф: +992 90 000 00 00 (Али)"}
    return "alif"


def test_cards_balance_hold_and_reroute(conn, app):
    from conftest import make_client
    config = app.state.config
    method = _method(conn, config)
    a = paycards.add(conn, method, "Карта 4444 5555 6666 1111\nАли", 0)
    b = paycards.add(conn, method, "Карта 4444 5555 6666 2222\nФаррух", 777001)
    u1, u2 = make_client(conn, login="pay1")[0], make_client(conn, login="pay2")[0]
    first = paycards.pick(conn, u1, method)
    assert paycards.pick(conn, u1, method)["id"] == first["id"]          # та же карта для того же клиента
    user1 = conn.execute("SELECT * FROM users WHERE id = ?", (u1,)).fetchone()
    pid = payments.create(conn, config, user1, method, "", amount_tjs="100")
    assert conn.execute("SELECT card_id FROM payments WHERE id = ?", (pid,)).fetchone()[0] == first["id"]
    other = paycards.pick(conn, u2, method)
    assert other["id"] != first["id"]                                     # у первой уже ждёт 100 с. — второму другая
    assert payments.public(conn, config, conn.execute("SELECT * FROM payments WHERE id = ?", (pid,)).fetchone())["details"] == first["details"]
    # клиент перевёл на другую нашу карту — заявка переходит туда
    wrong = b if first["id"] == a else a
    note = paycards.reroute(conn, pid, "**** " + paycards.get(conn, wrong)["details"].split()[4])
    assert note and conn.execute("SELECT card_id FROM payments WHERE id = ?", (pid,)).fetchone()[0] == wrong
    assert paycards.match(conn, "9999") is None                           # чужой номер — не наша карта


def test_only_card_owner_may_decide(conn, app):
    from conftest import make_client
    config = app.state.config
    method = _method(conn, config)
    cashiers.add(conn, 777002, "Кассир Б")
    cashiers.add(conn, 777003, "Кассир В")
    card = paycards.add(conn, method, "Карта 4444 5555 6666 3333", 777002)
    uid = make_client(conn, login="pay3")[0]
    pid = payments.create(conn, config, conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone(), method, "", amount_tjs="50")
    p = conn.execute("SELECT * FROM payments WHERE id = ?", (pid,)).fetchone()
    assert p["card_id"] == card
    assert cashiers.may_decide(conn, config, cashiers.get(conn, 777002), p)
    assert not cashiers.may_decide(conn, config, cashiers.get(conn, 777003), p)   # чужую карту другой кассир не решает


def test_no_cards_keeps_old_behaviour(conn, app):
    config = app.state.config
    method = _method(conn, config)
    assert paycards.pick(conn, 1, method) is None
    assert paycards.details_for(conn, 1, method, "старые реквизиты") == "старые реквизиты"


def test_admin_cards_page(app, conn):
    from fastapi.testclient import TestClient
    from conftest import csrf_of, web_login
    app.state.config.pay_methods = {"alif": "Алиф: +992 90 000 00 00 (Али)"}
    c = TestClient(app)
    web_login(c, "admin@example.com", "adminpass123")
    page = c.get("/admin/cards")
    assert page.status_code == 200 and "Карты для оплаты" in page.text
    token = csrf_of(page.text)
    r = c.post("/admin/cards", data={"csrf": token, "action": "add", "method": "alif",
                                     "details": "Карта 4444 5555 6666 9999", "owner_tg": "0"}, follow_redirects=False)
    assert r.status_code == 303 and "****9999" in c.get("/admin/cards").text
