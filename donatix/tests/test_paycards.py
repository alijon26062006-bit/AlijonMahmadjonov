"""Несколько карт на банк: ровные суммы, карта держится за клиентом, чек — хозяину карты, ИИ перенаправляет."""

from donatix import cashiers, db, paycards, payments


def _method(conn, config):
    config.pay_methods = {"alif": "Алиф: +992 90 000 00 00 (Али)"}
    return "alif"


def test_cards_balance_hold_and_reroute(conn, app):
    from conftest import make_client
    config = app.state.config
    method = _method(conn, config)
    db.set_setting(conn, "cards.rest", "0")      # здесь проверяем распределение, без отдыха карт
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


def test_one_card_rests_each_day_by_turns(conn, app, monkeypatch):
    from datetime import datetime, timezone
    from conftest import make_client
    method = _method(conn, app.state.config)
    ids = [paycards.add(conn, method, f"Карта 4444 5555 6666 70{i}0", 0) for i in range(3)]
    seen = set()
    for day in range(3):                                   # три дня подряд — отдыхают разные карты, по кругу
        fixed = datetime(2026, 11, 17 + day, 12, tzinfo=timezone.utc)
        monkeypatch.setattr(paycards, "datetime", type("D", (datetime,), {"now": staticmethod(lambda tz=None, f=fixed: f)}))
        rest = paycards.resting_id(conn, method)
        seen.add(rest)
        uid = make_client(conn, login=f"rest{day}")[0]
        for _ in range(5):
            assert paycards.pick(conn, uid, method)["id"] != rest       # отдыхающую карту не показываем
            conn.execute("DELETE FROM pay_card_hold")
    assert seen == set(ids)
    db.set_setting(conn, "cards.rest", "0")
    assert paycards.resting_id(conn, method) == 0                        # отдых выключен в админке
    paycards.set_active(conn, ids[1], False)
    paycards.set_active(conn, ids[2], False)
    db.set_setting(conn, "cards.rest", "1")
    assert paycards.resting_id(conn, method) == 0                        # одна карта — не отдыхает


def test_ai_and_masks_route_receipt_to_the_card_that_got_money(conn, app):
    """ИИ назвал нашу карту, или видна маска/имя — заявка уходит хозяину ИМЕННО той карты, даже если карту не показывали."""
    from conftest import make_client
    config = app.state.config
    method = _method(conn, config)
    a = paycards.add(conn, method, "Карта 4444 5555 6666 1111\nПолучатель: Фаррух", 777011)
    b = paycards.add(conn, method, "Карта 5555 7777 8888 2222\nПолучатель: Шахзод", 777012)
    tel = paycards.add(conn, method, "Телефон +992 93 555 44 33\nПолучатель: Бахтиёр", 0)
    assert "[карта #%d]" % a in paycards.all_details(conn, method)                      # ИИ видит каждую карту отдельно
    assert paycards.match(conn, "5555 77** **** 2222")["id"] == b                     # маска карты
    assert paycards.match(conn, "**** 2222")["id"] == b
    assert paycards.match(conn, "4444 55** **** 2222") is None                        # начало от одной, конец от другой
    assert paycards.match(conn, "935554433")["id"] == tel                            # телефон без кода страны
    assert paycards.match(conn, "Шахзод М.")["id"] == b                              # по имени, если цифр нет
    uid = make_client(conn, login="pay9")[0]
    pid = payments.create(conn, config, conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone(), method, "", amount_tjs="70")
    conn.execute("UPDATE payments SET card_id = NULL WHERE id = ?", (pid,))          # карту не показывали
    assert paycards.reroute(conn, pid, {"recipient": "", "our_card": b})               # ИИ сказал: карта b
    assert conn.execute("SELECT card_id FROM payments WHERE id = ?", (pid,)).fetchone()[0] == b
    note = paycards.reroute(conn, pid, {"our_card": 99999, "recipient": "чужой 9999"})       # выдуманную карту не берём
    assert "не узнал" in note and conn.execute("SELECT card_id FROM payments WHERE id = ?", (pid,)).fetchone()[0] == b
    note = paycards.reroute(conn, pid, {"recipient": "4444 55** **** 1111"})
    assert "****1111" in note and conn.execute("SELECT card_id FROM payments WHERE id = ?", (pid,)).fetchone()[0] == a


def test_cards_go_strictly_by_turn_new_card_does_not_take_all(conn, app):
    """Новую карту добавили посреди дня — она НЕ забирает всех: клиенты идут по кругу А, Б, В, А, Б, В…"""
    from conftest import make_client
    config = app.state.config
    method = _method(conn, config)
    db.set_setting(conn, "cards.rest", "0")
    a = paycards.add(conn, method, "Карта 4444 5555 6666 1111", 0)
    b = paycards.add(conn, method, "Карта 4444 5555 6666 2222", 0)
    users = [make_client(conn, login=f"turn{i}")[0] for i in range(7)]
    for uid in users[:2]:                                    # утром было две карты, пришли большие суммы
        u = conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
        pid = payments.create(conn, config, u, method, "", amount_tjs="900")
        conn.execute("UPDATE payments SET status = 'paid', resolved_at = created_at WHERE id = ?", (pid,))
    c = paycards.add(conn, method, "Карта 4444 5555 6666 3333", 0)   # добавили новую
    got = [paycards.pick(conn, uid, method)["id"] for uid in users[2:]]
    assert sorted(got[:3]) == sorted([a, b, c]) and got[3:] == got[:2]   # по одному на каждую, потом снова по кругу
    assert got.count(c) == 2 and got.count(a) + got.count(b) == 3
    assert paycards.pick(conn, users[2], method)["id"] == got[0]          # тот же клиент — та же карта, очередь не сдвигается
    assert paycards.pick(conn, users[3], method)["id"] == got[1]
