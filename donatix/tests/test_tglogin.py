"""Вход и регистрация через Telegram: номер один раз, дальше одна кнопка; войти может только свой браузер."""
import re

from conftest import make_client, web_login
from fastapi.testclient import TestClient
from test_shopbot import TG, FakeApi, msg, press

from donatix import accounts, db, shopbot


def _setup(app, config, conn, supplier):
    config.shop_bot_token = "t"
    db.set_setting(conn, "shop.bot_username", "DonatixShopBot")
    return shopbot.ShopBot(config, supplier, api=FakeApi())


def _start(client):
    page = client.get("/auth/telegram")
    assert page.status_code == 200 and "Открыть Telegram" in page.text
    return re.search(r"start=login_([A-Za-z0-9]+)", page.text).group(1)


def _contact(user_id=TG, phone="992901234567"):
    return {"update_id": 3, "message": {"chat": {"id": TG, "type": "private"}, "from": {"id": TG, "first_name": "Али"},
                                        "contact": {"phone_number": phone, "user_id": user_id}}}


def test_first_login_with_phone_then_one_tap(app, config, conn, supplier):
    bot = _setup(app, config, conn, supplier)
    c = TestClient(app)
    assert "Войти через Telegram" in c.get("/login").text and "через Telegram" in c.get("/register").text
    token = _start(c)
    bot.handle(conn, msg(f"/start login_{token}"))
    last = bot.api.calls[-1][1]
    assert last["reply_markup"]["keyboard"][0][0]["request_contact"] is True      # просим номер кнопкой
    bot.handle(conn, _contact(user_id=777))                                         # чужой контакт — нет
    assert "нужен ваш номер" in bot.api.calls[-1][1]["text"]
    bot.handle(conn, _contact())
    assert "Это вы сейчас входите" in bot.api.last_text()
    su = shopbot.shop_user(conn, TG)
    assert accounts.get_user(conn, su["user_id"])["phone"] == "+992901234567"
    assert c.get("/auth/telegram/status").json()["state"] == "new"
    bot.handle(conn, press(f"lg:{token}"))
    assert "Готово" in bot.api.last_text()
    assert c.get("/auth/telegram/status").json()["state"] == "ok"
    r = c.get("/auth/telegram/finish", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/panel"
    assert c.get("/panel").status_code == 200                                       # вошли — тот же аккаунт, что в боте
    assert conn.execute("SELECT user_id FROM logins ORDER BY id DESC LIMIT 1").fetchone()[0] == su["user_id"]

    c2 = TestClient(app)                                                            # второй раз — без номера
    token2 = _start(c2)
    bot.handle(conn, msg(f"/start login_{token2}"))
    assert "Это вы сейчас входите" in bot.api.last_text()
    bot.handle(conn, press(f"lg:{token2}"))
    assert TestClient(app).get("/auth/telegram/finish", follow_redirects=False).headers["location"] == "/login"
    assert c2.get("/auth/telegram/finish", follow_redirects=False).headers["location"] == "/panel"
    assert c2.get("/auth/telegram/finish", follow_redirects=False).headers["location"] == "/login"   # один раз


def test_not_me_cancels_and_old_link_expires(app, config, conn, supplier):
    bot = _setup(app, config, conn, supplier)
    c = TestClient(app)
    token = _start(c)
    bot.handle(conn, msg(f"/start login_{token}"))
    bot.handle(conn, _contact())
    bot.handle(conn, press(f"lgno:{token}"))
    assert "Вход отменён" in bot.api.last_text()
    assert c.get("/auth/telegram/status").json()["state"] == "denied"
    assert c.get("/auth/telegram/finish", follow_redirects=False).headers["location"] == "/login"
    bot.handle(conn, msg("/start login_Nonexistent123"))
    assert "устарела" in bot.api.last_text()


def test_link_telegram_to_existing_email_account(app, config, conn, supplier):
    bot = _setup(app, config, conn, supplier)
    uid, _ = make_client(conn, login="emailuser", balance="7")
    c = TestClient(app)
    web_login(c, "emailuser@example.com", "password123")
    r = c.get("/panel", follow_redirects=False)                                    # без Telegram кабинет закрыт
    assert r.status_code == 303 and r.headers["location"] == "/panel/telegram"
    assert c.get("/panel/orders", follow_redirects=False).headers["location"] == "/panel/telegram"
    assert "Последний шаг — привяжите Telegram" in c.get("/panel/telegram").text
    page = c.get("/auth/telegram?link=1")
    token = re.search(r"start=login_([A-Za-z0-9]+)", page.text).group(1)
    bot.handle(conn, msg(f"/start login_{token}"))
    assert bot.api.calls[-1][1]["reply_markup"]["keyboard"][0][0]["request_contact"]   # номер — один раз
    bot.handle(conn, _contact())
    assert "Привязать этот Telegram к аккаунту emailuser" in bot.api.last_text()
    bot.handle(conn, press(f"lg:{token}"))
    assert shopbot.shop_user(conn, TG)["user_id"] == uid                            # бот теперь на этом аккаунте
    assert accounts.get_user(conn, uid)["phone"] == "+992901234567"
    r = c.get("/auth/telegram/finish", follow_redirects=False)
    assert r.headers["location"] == "/panel"
    assert c.get("/panel", follow_redirects=False).status_code == 200              # кабинет открылся
    assert "Привязать Telegram" not in c.get("/panel").text


def test_forgot_password_via_telegram(app, config, conn, supplier):
    bot = _setup(app, config, conn, supplier)
    uid, _ = make_client(conn, login="forgot", balance="3")
    conn.execute("UPDATE users SET phone = '+992900000000' WHERE id = ?", (uid,))
    conn.execute("INSERT INTO shop_users (tg_id, user_id, name, lang, created_at) "
                 "VALUES (?, ?, 'А', 'ru', '2026-01-01')", (TG, uid))
    c = TestClient(app)
    assert 'href="/forgot"' in c.get("/login").text
    assert "Восстановить через Telegram" in c.get("/forgot").text
    page = c.get("/auth/telegram?reset=1")
    assert "Восстановление пароля" in page.text
    token = re.search(r"start=login_([A-Za-z0-9]+)", page.text).group(1)
    bot.handle(conn, msg(f"/start login_{token}"))
    bot.handle(conn, press(f"lg:{token}"))
    r = c.get("/auth/telegram/finish", follow_redirects=False)
    assert r.headers["location"] == "/panel/password"
    form = c.get("/panel/password").text
    assert "старый пароль не нужен" in form and 'name="old"' not in form
    from conftest import csrf_of
    r = c.post("/panel/password", data={"csrf": csrf_of(form), "new": "newpass123", "new2": "newpass123"},
               follow_redirects=False)
    assert r.status_code == 303
    other = TestClient(app)
    web_login(other, "forgot@example.com", "newpass123")                           # новый пароль работает
    assert other.get("/panel", follow_redirects=False).status_code == 200


def test_password_change_needs_old_password_without_reset(app, config, conn):
    uid, _ = make_client(conn, login="pwuser")
    c = TestClient(app)
    web_login(c, "pwuser@example.com", "password123")
    from conftest import csrf_of
    form = c.get("/panel/password").text
    r = c.post("/panel/password", data={"csrf": csrf_of(form), "old": "wrong", "new": "newpass123",
                                        "new2": "newpass123"})
    assert r.status_code == 400 and "Старый пароль неверный" in r.text
