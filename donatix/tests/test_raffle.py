"""Розыгрыш за покупки: билеты за каждые $15, участие только по кнопке с ником Instagram, Telegram — автоматически."""

import pytest

from conftest import balance, make_client

from donatix import db, raffle

_N = [0]


def buy(conn, uid, usd, source="panel", status="completed"):
    _N[0] += 1
    conn.execute(
        "INSERT INTO orders (public_id, user_id, product_id, kind, product_name, quantity, unit_price, total_micro, "
        "cost_micro, status, supplier_idem_key, source, created_at, updated_at) "
        "VALUES (?, ?, 'p', 'topup', 'Алмазы', 1, '1', ?, 0, ?, ?, ?, ?, ?)",
        (f"rf{_N[0]}", uid, int(usd * 10_000), status, f"rfk{_N[0]}", source, db.now(), db.now()))


def tg(conn, uid, tg_id):
    conn.execute("INSERT INTO shop_users (tg_id, user_id, name, created_at, last_seen) VALUES (?, ?, 'Али', ?, ?)",
                 (tg_id, uid, db.now(), db.now()))


@pytest.fixture
def on(conn):
    raffle.save_settings(conn, {"channel_id": "@dx_news", "instagram": "donatix.tj"})
    raffle.start(conn)
    return conn


def member(subscribed):
    return lambda method, **p: {"status": "member" if p["user_id"] in subscribed else "left"}


def test_tickets_only_for_own_completed_purchases_after_join(on, config):
    conn = on
    uid = make_client(conn, login="rf1")[0]
    tg(conn, uid, 9001)
    buy(conn, uid, 20)
    buy(conn, uid, 40, source="api")            # партнёрские/API — не считаются
    buy(conn, uid, 40, status="failed")         # невыполненный — не считается
    st = raffle.status(conn, config, uid)
    assert st["spent"] == "20.00" and st["percent"] == 100 and not st["joined"] and st["tickets"] == []   # кнопку не нажал
    assert "Участвую" in raffle.new_ticket_note(conn, uid)
    got = raffle.join(conn, config, uid, "https://instagram.com/Ali_2006/", api=member({9001}))
    assert got["instagram"] == "ali_2006" and len(got["new_tickets"]) == 1
    buy(conn, uid, 100, source="shopbot")       # купил ещё — второго билета нет: один человек — один билет
    assert raffle.new_ticket_note(conn, uid) == ""
    st = raffle.status(conn, config, uid)
    assert st["joined"] and len(st["tickets"]) == 1 and st["tg_ok"] is True


def test_progress_before_minimum(on, config):
    conn = on
    uid = make_client(conn, login="rf2")[0]
    buy(conn, uid, 8.5)
    st = raffle.status(conn, config, uid)
    assert st["spent"] == "8.50" and st["need"] == "6.50" and st["percent"] == 56
    assert all("total" not in k for k in st) and st["top"] == [250, 200, 100] and st["winners_n"] == 50


def test_join_needs_instagram_telegram_and_subscription(on, config):
    conn = on
    uid = make_client(conn, login="rf3")[0]
    tg(conn, uid, 9003)
    with pytest.raises(raffle.RaffleError, match="NEED_BUY"):            # без покупки на $15 записаться нельзя
        raffle.join(conn, config, uid, "@ali", api=member({9003}))
    assert raffle.entry(conn, uid) is None and not raffle.status(conn, config, uid)["can_join"]
    buy(conn, uid, 14.99)
    with pytest.raises(raffle.RaffleError, match="NEED_BUY"):            # $14.99 — ещё мало
        raffle.join(conn, config, uid, "@ali", api=member({9003}))
    buy(conn, uid, 0.01)
    assert raffle.status(conn, config, uid)["can_join"]                   # набрал $15 — кнопка появилась
    conn.execute("DELETE FROM shop_users WHERE tg_id = 9003")
    with pytest.raises(raffle.RaffleError):
        raffle.join(conn, config, uid, "", api=member(set()))
    with pytest.raises(raffle.RaffleError, match="NEED_TG"):
        raffle.join(conn, config, uid, "@ali", api=member(set()))
    tg(conn, uid, 9003)
    with pytest.raises(raffle.RaffleError, match="NEED_SUB"):
        raffle.join(conn, config, uid, "@ali", api=member(set()))
    raffle.join(conn, config, uid, "@ali", api=member({9003}))
    other = make_client(conn, login="rf3b")[0]
    tg(conn, other, 9004)
    buy(conn, other, 15)
    with pytest.raises(raffle.RaffleError, match="уже участвует"):
        raffle.join(conn, config, other, "ali", api=member({9004}))      # один Instagram — один аккаунт


def test_live_draw_from_last_place_one_win_per_person_and_prize_to_balance(conn, config, monkeypatch):
    raffle.save_settings(conn, {"prizes": "1 x 250\n1 x 200\n2 x 40"})
    raffle.start(conn)
    monkeypatch.setattr(raffle, "tg_member", lambda *a, **k: True)
    users = []
    for i in range(5):
        uid = make_client(conn, login=f"rfd{i}", balance="")[0]
        buy(conn, uid, 15 * (i + 1))
        raffle.join(conn, config, uid, f"nick{i}")
        users.append(uid)
    assert raffle.board(conn)["tickets"] == 5 and raffle.places(conn) == [250, 200, 40, 40]
    first = raffle.draw_next(conn, config)
    assert first["place"] == 4                                           # с последнего места к первому
    with pytest.raises(raffle.RaffleError):
        raffle.draw_next(conn, config)                                   # сначала решить по выбранному
    raffle.redraw(conn)                                                  # не подписан на Instagram — перевыбрать
    again = raffle.draw_next(conn, config)
    assert again["place"] == 4 and again["user_id"] != first["user_id"]
    with db.tx(conn):
        paid = raffle.confirm(conn, config)
    assert paid["prize_tjs"] == 40 and balance(conn, again["user_id"]) == paid["micro"] > 0
    winners = {again["user_id"]}
    for place in (3, 2, 1):
        w = raffle.draw_next(conn, config)
        assert w["place"] == place and w["user_id"] not in winners and w["user_id"] != first["user_id"]
        winners.add(w["user_id"])
        with db.tx(conn):
            raffle.confirm(conn, config)
    with pytest.raises(raffle.RaffleError, match="Все места"):
        raffle.draw_next(conn, config)
    late = make_client(conn, login="rflate")[0]
    with pytest.raises(raffle.RaffleError):
        raffle.join(conn, config, late, "late")                          # после начала эфира участие закрыто
    assert [w["place"] for w in raffle.public_winners(conn)] == [1, 2, 3, 4]


# ── сайт, админка, бот, мини-приложение ──

def test_site_banner_page_join_and_profile(app, conn, config, monkeypatch):
    from fastapi.testclient import TestClient
    from conftest import csrf_of, web_login
    c = TestClient(app)
    assert 'id="rff"' not in c.get("/").text and "не идёт" in c.get("/raffle").text          # не запущен — ничего не видно
    raffle.save_settings(conn, {"instagram": "donatix.tj"})
    raffle.start(conn)
    home = c.get("/").text
    assert 'id="rff"' in home and "250 с." in home and "2500" not in home            # общую сумму не показываем
    page = c.get("/raffle").text
    assert "Войти и участвовать" in page and "2500" not in page and "40 с." in page
    uid = make_client(conn, login="rfweb")[0]
    buy(conn, uid, 8.5)
    web_login(c, "rfweb@example.com", "password123")
    page = c.get("/raffle").text
    assert "$6.50" in page and "56%" in page
    assert "$6.50" in c.get("/panel").text                                               # профиль: сколько осталось
    token = csrf_of(c.get("/panel/balance").text)
    assert 'action="/raffle/join"' not in page and "появится после покупки" in page    # $8.50 — кнопки нет
    r = c.post("/raffle/join", data={"csrf": token, "instagram": "@rf_web"}, follow_redirects=True)
    assert "Сначала купите" in r.text and raffle.entry(conn, uid) is None              # и в обход — не пускаем
    buy(conn, uid, 10)
    assert 'action="/raffle/join"' in c.get("/raffle").text                             # $18.50 — кнопка появилась
    r = c.post("/raffle/join", data={"csrf": token, "instagram": "??"}, follow_redirects=True)
    assert "ник Instagram" in r.text and raffle.entry(conn, uid) is None
    r = c.post("/raffle/join", data={"csrf": token, "instagram": "@rf_web"}, follow_redirects=True)
    assert "Вы участвуете" in r.text and "№ 0001" in r.text
    assert "Вы участвуете" in c.get("/panel").text


def test_admin_runs_live_draw(app, conn, config, monkeypatch):
    from fastapi.testclient import TestClient
    from conftest import csrf_of, web_login
    monkeypatch.setattr(raffle, "tg_member", lambda *a, **k: True)
    c = TestClient(app)
    web_login(c, "admin@example.com", "adminpass123")
    page = c.get("/admin/raffle")
    assert page.status_code == 200 and "Не запущен" in page.text
    token = csrf_of(page.text)
    post = lambda **d: c.post("/admin/raffle", data={"csrf": token, **d}, follow_redirects=True)   # noqa: E731
    assert "7 x 50" in post(action="save", prizes="1 x 250\n7 x 50", draw="2026-12-18", min_usd="15",
                            instagram="donatix.tj", channel_id="@dx_news", channel_url="").text
    assert "Идёт" in post(action="start").text
    uid = make_client(conn, login="rfadm", balance="")[0]
    buy(conn, uid, 30)
    tg(conn, uid, 9050)
    raffle.join(conn, config, uid, "rfadm_ig")
    page = post(action="draw").text
    assert "8 место" in page and "@rfadm_ig" in page and "Подтвердить" in page
    assert "зачислен" in post(action="confirm").text and balance(conn, uid) > 0
    assert "СБРОС" in post(action="reset", sure="").text and raffle.board(conn)["tickets"] == 1
    post(action="reset", sure="СБРОС")
    assert raffle.board(conn)["tickets"] == 0 and not raffle.active(conn)


def test_shop_bot_join_flow_with_channel_check(app, config, conn, supplier):
    import test_shopbot as tb
    subscribed = set()

    class Api(tb.FakeApi):
        def __call__(self, method, **p):
            if method == "getChatMember":
                return {"status": "member" if p["user_id"] in subscribed else "left"}
            return super().__call__(method, **p)
    api = Api()
    bot = tb._bot(config, supplier, api)
    su = tb._start(bot, conn)
    assert not any("Розыгрыш" in b["text"] for b in api.last_buttons())                 # не запущен — кнопки нет
    raffle.save_settings(conn, {"channel_id": "@dx_news", "instagram": "donatix.tj"})
    raffle.start(conn)
    bot.handle(conn, tb.msg("/start"))
    bot.handle(conn, tb.press(api.button("Розыгрыш")))
    assert not any("Участвую" in b["text"] for b in api.last_buttons())                 # без покупки кнопки нет
    bot.handle(conn, tb.press("rfj"))
    bot.handle(conn, tb.msg("@sneaky"))
    assert "Сначала купите" in api.last_text() and raffle.entry(conn, su["user_id"]) is None   # и в обход — нет
    buy(conn, su["user_id"], 16, source="shopbot")
    bot.handle(conn, tb.msg("/start"))
    bot.handle(conn, tb.press(api.button("Розыгрыш")))
    text = api.last_text()
    assert "250 с." in text and "2500" not in text and "Участвую" in text and "100%" in text
    bot.handle(conn, tb.press("rfj"))
    bot.handle(conn, tb.msg("@Ali_Bot_User"))
    assert "подпишитесь" in api.last_text() and raffle.entry(conn, su["user_id"]) is None   # не подписан на канал
    subscribed.add(tb.TG)
    bot.handle(conn, tb.press("rfc"))
    assert "Вы участвуете" in api.last_text() and "№ 0001" in api.last_text()
    assert raffle.entry(conn, su["user_id"])["instagram"] == "ali_bot_user"


def test_mini_app_raffle_status_and_join(app, conn, config, monkeypatch):
    from dataclasses import replace

    from fastapi.testclient import TestClient
    import test_tgapp_catalog as tc
    app.state.config = replace(config, gift_bot_token=tc.TOKEN)
    c = TestClient(app)
    assert c.post("/tg/api/raffle", json={}, headers=tc.H).json()["raffle"] is None
    raffle.start(conn)
    uid = conn.execute("SELECT user_id FROM shop_users WHERE tg_id = 5501").fetchone()[0]
    r = c.post("/tg/api/raffle", json={"join": 1, "instagram": "ali.app"}, headers=tc.H).json()
    assert not r["ok"] and "купите" in r["error"]                                       # до покупки — нельзя
    buy(conn, uid, 15, source="tgapp")
    st = c.post("/tg/api/raffle", json={}, headers=tc.H).json()["raffle"]
    assert st["percent"] == 100 and not st["joined"] and st["can_join"]
    r = c.post("/tg/api/raffle", json={"join": 1, "instagram": "ali.app"}, headers=tc.H).json()
    assert r["ok"] and r["new_tickets"] == [1] and r["raffle"]["joined"]
    assert c.post("/tg/api/raffle", json={}).status_code == 403
    assert "rfbox" in c.get("/tg").text
