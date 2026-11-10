"""Розыгрыш по промокодам: генерация с призами, 1 код в день, публикация в канал, сайт и бот."""

from conftest import csrf_of, make_client, web_login
from test_shopbot import TG, FakeApi, msg, press

from donatix import db, giveaway, shopbot


def test_generate_puts_prizes_on_random_codes(conn):
    bid = giveaway.generate(conn, 50, ["Ваучер на месяц", "Ваучер на неделю", ""], "Тест")
    rows = conn.execute("SELECT * FROM giveaway_codes WHERE batch_id = ?", (bid,)).fetchall()
    assert len(rows) == 50 and len({r["code"] for r in rows}) == 50
    assert sorted(r["prize"] for r in rows if r["prize"]) == ["Ваучер на месяц", "Ваучер на неделю"]
    assert all(r["code"].startswith("DX-") and len(r["code"]) == 9 for r in rows)


def test_three_codes_per_day_and_each_code_once(conn):
    uid, _ = make_client(conn)
    other, _ = make_client(conn, login="shop2")
    giveaway.generate(conn, 6, ["Приз"])
    codes = [r["code"] for r in conn.execute("SELECT code FROM giveaway_codes ORDER BY id")]
    res = giveaway.activate(conn, uid, codes[0].lower().replace("-", " "))
    assert res["code"] == codes[0] and res["left"] == 2
    assert giveaway.activate(conn, uid, codes[1])["left"] == 1
    assert giveaway.activate(conn, uid, codes[2])["left"] == 0
    try:
        giveaway.activate(conn, uid, codes[3])
        raise AssertionError("4-й код в тот же день")
    except giveaway.GiveawayError as exc:
        assert "3 попытки" in str(exc) and "завтра" in str(exc)
    assert conn.execute("SELECT user_id FROM giveaway_codes WHERE code = ?", (codes[3],)).fetchone()[0] is None
    try:
        giveaway.activate(conn, other, codes[0])
        raise AssertionError("тот же код второй раз")
    except giveaway.GiveawayError as exc:
        assert "уже активировали" in str(exc)
    assert giveaway.activate(conn, other, codes[3])["code"] == codes[3]


def test_wrong_codes_limited(conn):
    uid, _ = make_client(conn)
    giveaway.generate(conn, 2, [])
    for _ in range(giveaway.MAX_WRONG_PER_DAY):
        try:
            giveaway.activate(conn, uid, "DX-AAAAAA")
        except giveaway.GiveawayError as exc:
            assert "нет" in str(exc)
    code = conn.execute("SELECT code FROM giveaway_codes LIMIT 1").fetchone()[0]
    try:
        giveaway.activate(conn, uid, code)
        raise AssertionError("перебор должен остановиться")
    except giveaway.GiveawayError as exc:
        assert "завтра" in str(exc)


def test_announce_posts_to_channel(conn, config):
    uid, _ = make_client(conn)
    giveaway.generate(conn, 1, ["Ваучер"])
    code = conn.execute("SELECT code FROM giveaway_codes").fetchone()[0]
    res = giveaway.activate(conn, uid, code)
    api = FakeApi()
    config.shop_bot_token = "x"
    giveaway.announce(config, conn, uid, res, api=api)
    sent = [p for m, p in api.calls if m == "sendMessage"]
    assert sent and sent[0]["chat_id"] == "@donatixtj" and code in sent[0]["text"] and "Ваучер" in sent[0]["text"]


def test_site_home_has_no_promo_card(app, client, conn):
    """Промокод проверяют только в Telegram-боте — на сайте карточки нет."""
    giveaway.generate(conn, 2, ["Ваучер на месяц"])
    assert 'id="promo-code"' not in client.get("/").text


def test_admin_generates_and_marks_given(app, client, config, conn):
    web_login(client, config.admin_email, config.admin_password)
    page = client.get("/admin/giveaway")
    client.post("/admin/giveaway", data={"csrf": csrf_of(page.text), "action": "generate", "count": "10",
                                         "prizes": "Приз 1\nПриз 2", "title": "Ноябрь"})
    assert conn.execute("SELECT COUNT(*) FROM giveaway_codes").fetchone()[0] == 10
    uid, _ = make_client(conn)
    code = conn.execute("SELECT id, code FROM giveaway_codes WHERE prize = 'Приз 1'").fetchone()
    giveaway.activate(conn, uid, code["code"])
    page = client.get("/admin/giveaway")
    assert "Приз 1" in page.text and "Выдано" in page.text
    client.post("/admin/giveaway", data={"csrf": csrf_of(page.text), "action": "given", "item": str(code["id"])})
    assert conn.execute("SELECT given_at FROM giveaway_codes WHERE id = ?", (code["id"],)).fetchone()[0]


def test_bot_button_and_activation(app, config, conn, supplier):
    giveaway.generate(conn, 2, [])
    code = conn.execute("SELECT code FROM giveaway_codes LIMIT 1").fetchone()[0]
    bot = shopbot.ShopBot(config, supplier, api=FakeApi())
    bot.handle(conn, msg("/start"))
    bot.handle(conn, press(bot.api.button("Проверить промокод")))
    bot.handle(conn, msg(code))
    assert "пусто" in bot.api.last_text() and code in bot.api.last_text()
    assert conn.execute("SELECT source FROM giveaway_codes WHERE code = ?", (code,)).fetchone()[0] == "bot"
    assert db is not None


def test_only_winners_posted(conn, config):
    """В канал — только выигрыши, пустые коды не публикуются."""
    uid, _ = make_client(conn)
    giveaway.generate(conn, 3, ["Ваучер"])
    empty = conn.execute("SELECT code FROM giveaway_codes WHERE prize IS NULL LIMIT 1").fetchone()[0]
    win = conn.execute("SELECT code FROM giveaway_codes WHERE prize IS NOT NULL").fetchone()[0]
    config.shop_bot_token = "x"
    api = FakeApi()
    giveaway.announce(config, conn, uid, giveaway.activate(conn, uid, empty), api=api)
    assert not [p for m, p in api.calls if m == "sendMessage"]
    giveaway.announce(config, conn, uid, giveaway.activate(conn, uid, win), api=api)
    assert len([p for m, p in api.calls if m == "sendMessage"]) == 1


def test_admin_sees_all_codes_prizes_and_who(app, client, config, conn):
    giveaway.generate(conn, 5, ["Ваучер на месяц"])
    win = conn.execute("SELECT code FROM giveaway_codes WHERE prize IS NOT NULL").fetchone()[0]
    web_login(client, config.admin_email, config.admin_password)
    page = client.get("/admin/giveaway").text
    assert win in page and "Ваучер на месяц" in page
