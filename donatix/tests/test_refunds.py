"""Карта для возврата остатка: обязательна один раз на сайте и в боте, номер зашифрован, админ видит всё."""

import pytest
from conftest import csrf_of, make_client, web_login
from test_shopbot import TG, FakeApi, msg, press

from donatix import refunds, shopbot


@pytest.fixture(autouse=True)
def _on(monkeypatch, conn):
    monkeypatch.setattr(refunds, "ENFORCE", True)
    from donatix import db
    db.set_setting(conn, "refund.required", "1")


def test_number_checks():
    assert refunds.clean_number("card", "9762 0000 1234 5678") == ("9762000012345678", "")
    assert refunds.clean_number("card", "1234")[0] is None
    assert refunds.clean_number("phone", "+992 90 123 45 67") == ("+992901234567", "")
    assert refunds.clean_number("phone", "901234567") == ("+992901234567", "")
    assert refunds.clean_number("phone", "12345")[0] is None
    assert refunds.clean_holder("Алиев Алишер")[0] == "Алиев Алишер"
    assert refunds.clean_holder("12")[0] is None


def test_encrypted_in_db(app, config, conn):
    uid, _ = make_client(conn)
    assert refunds.save(conn, config.secret_key, uid, bank="Алиф", kind="card", number="9762000012345678",
                        holder="Алиев Алишер") == ""
    row = refunds.get(conn, uid)
    assert "9762000012345678" not in row["number_enc"] and row["last4"] == "5678"
    assert refunds.decrypt(config.secret_key, row["number_enc"]) == "9762000012345678"
    assert refunds.decrypt("other-key", row["number_enc"]) is None


def test_site_requires_card_then_lets_in(app, client, config, conn):
    make_client(conn)
    web_login_ok = client.post("/login", data={"csrf": csrf_of(client.get("/login").text), "email": "shop1@example.com",
                                               "password": "password123"}, follow_redirects=False)
    assert web_login_ok.status_code == 303
    r = client.get("/panel/orders", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/panel/refund"
    page = client.get("/panel/refund")
    assert "CVV" in page.text and "закроется" in page.text
    token = csrf_of(page.text)
    bad = client.post("/panel/refund", data={"csrf": token, "bank": "Алиф", "kind": "card", "number": "12",
                                             "holder": "Алиев Алишер", "agree": "1"})
    assert bad.status_code == 400 and "16 цифр" in bad.text
    ok = client.post("/panel/refund", data={"csrf": token, "bank": "Другой банк", "bank_other": "Мой банк",
                                            "kind": "phone", "number": "90 123 45 67", "holder": "Алиев Алишер",
                                            "agree": "1"}, follow_redirects=False)
    assert ok.status_code == 303 and ok.headers["location"] == "/panel/orders"
    assert client.get("/panel/orders", follow_redirects=False).status_code == 200


def test_admin_not_asked_and_sees_report(app, client, config, conn):
    uid, _ = make_client(conn)
    refunds.save(conn, config.secret_key, uid, bank="Эсхата", kind="card", number="4444333322221111", holder="Али Валиев")
    web_login(client, config.admin_email, config.admin_password)
    page = client.get("/admin/refunds")
    assert page.status_code == 200 and "4444333322221111" in page.text and "Эсхата" in page.text
    csv = client.get("/admin/refunds?format=csv")
    assert "4444333322221111" in csv.text and csv.headers["content-type"].startswith("text/csv")
    client.post("/admin/refunds/required", data={"csrf": csrf_of(page.text)})
    assert not refunds.required(conn)


def test_client_cannot_open_admin_report(app, client, config, conn):
    make_client(conn)
    refunds.ENFORCE = False
    web_login(client, "shop1@example.com", "password123")
    assert client.get("/admin/refunds", follow_redirects=False).status_code in (303, 403)


def test_bot_asks_card_before_menu(app, config, conn, supplier):
    bot = shopbot.ShopBot(config, supplier, api=FakeApi())
    bot.handle(conn, msg("/start"))
    assert "Карта для возврата" in bot.api.last_text() and "CVV" in bot.api.last_text()
    bot.handle(conn, press(bot.api.button("Алиф")))
    bot.handle(conn, press(bot.api.button("Номер карты")))
    bot.handle(conn, msg("1234"))
    assert "16 цифр" in bot.api.last_text()
    bot.handle(conn, msg("9762 0000 1234 5678"))
    bot.handle(conn, msg("Алиев Алишер"))
    assert "Сохранено" in bot.api.last_text() and "5678" in bot.api.last_text()
    su = shopbot.shop_user(conn, TG)
    row = refunds.get(conn, su["user_id"])
    assert row["bank"] == "Алиф" and row["source"] == "bot"
    bot.handle(conn, msg("/start"))
    assert "Баланс" in bot.api.last_text()           # дальше — обычное меню
    bot.handle(conn, msg("/card"))                    # изменить можно всегда
    assert "Сейчас указано" in bot.api.last_text()
