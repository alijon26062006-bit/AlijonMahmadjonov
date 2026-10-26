"""Рекламные баннеры вверху страниц: админ загружает, сайт показывает ленту, клики считаются."""
import io

import pytest
from conftest import csrf_of, make_client, web_login
from fastapi.testclient import TestClient
from PIL import Image

from donatix import banners, cache


def _png(w=1200, h=400, color="purple"):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def admin(app):
    c = TestClient(app)
    token = web_login(c, "admin@example.com", "adminpass123")
    return c, csrf_of(c.get("/admin/banners").text) or token


def _add(c, token, **form):
    data = {"csrf": token, "title": "Скидка", "link": "/panel/catalog", "sort": "0", **form}
    return c.post("/admin/banners", data=data, files={"image": ("b.png", _png(), "image/png")}, follow_redirects=False)


def test_upload_makes_two_webp_5x2(admin, config, conn):
    c, token = admin
    assert _add(c, token).status_code == 303
    row = banners.all_rows(conn)[0]
    for width in banners.SIZES:
        with Image.open(banners.folder(config) / f"{row['image']}-{width}.webp") as im:
            assert im.format == "WEBP" and im.size == (width, width * 2 // 5)


def test_shown_on_site_and_cabinet_not_in_admin(admin, app, conn):
    c, token = admin
    _add(c, token, title="Акция недели")
    cache.clear()
    home = TestClient(app).get("/").text
    assert 'data-bnr' in home and "Акция недели" in home and 'fetchpriority="high"' in home and "Реклама" in home
    _, key = make_client(conn, login="buyer")
    buyer = TestClient(app)
    web_login(buyer, "buyer@example.com", "password123")
    assert "data-bnr" in buyer.get("/panel").text
    assert "data-bnr" not in c.get("/admin").text


def test_click_counted_and_redirects(admin, app, conn):
    c, token = admin
    _add(c, token, link="t.me/donatix")
    bid = banners.all_rows(conn)[0]["id"]
    r = TestClient(app).get(f"/bn-go/{bid}", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "https://t.me/donatix"
    assert banners.all_rows(conn)[0]["clicks"] == 1


def test_bad_link_and_not_image_rejected(admin, conn):
    c, token = admin
    _add(c, token, link="javascript:alert(1)")
    _add(c, token, link="http://example.com")
    r = c.post("/admin/banners", data={"csrf": token, "link": "/"}, files={"image": ("x.png", b"not an image", "image/png")})
    assert banners.all_rows(conn) == []
    assert "Нужна картинка" in r.text or "Ссылка" in r.text


def test_dates_and_toggle(admin, conn):
    c, token = admin
    _add(c, token, starts_at="2030-01-01")
    _add(c, token, ends_at="2020-01-01")
    _add(c, token, title="Сейчас")
    assert [b["title"] for b in banners.active(conn, today="2026-10-25")] == ["Сейчас"]
    bid = next(r["id"] for r in banners.all_rows(conn) if r["title"] == "Сейчас")
    c.post(f"/admin/banners/{bid}/toggle", data={"csrf": token})
    assert banners.active(conn, today="2026-10-25") == []


def test_delete_removes_files(admin, config, conn):
    c, token = admin
    _add(c, token)
    row = banners.all_rows(conn)[0]
    c.post(f"/admin/banners/{row['id']}/delete", data={"csrf": token})
    assert banners.all_rows(conn) == []
    assert not (banners.folder(config) / f"{row['image']}-750.webp").exists()


def test_no_banners_no_markup(client):
    cache.clear()
    assert "data-bnr" not in client.get("/").text


def _buyer(app, conn, balance="100"):
    make_client(conn, login="buyer", balance=balance)
    c = TestClient(app)
    web_login(c, "buyer@example.com", "password123")
    return c, csrf_of(c.get("/panel/ads").text)


def test_client_request_waits_for_approval(admin, app, conn):
    c, token = _buyer(app, conn)
    page = c.get("/panel/ads").text
    assert "1500 × 600 px" in page and "Азартные игры" in page and "Скопировать промпт" in page
    r = c.post("/panel/ads", data={"csrf": token, "title": "Мой канал", "link": "t.me/mychan", "days": "3"},
               files={"image": ("b.png", _png(1500, 600), "image/png")}, follow_redirects=False)
    assert r.status_code == 303
    row = banners.pending(conn)[0]
    assert row["status"] == "pending" and row["login"] == "buyer"
    assert row["paid_micro"] > 0 and row["paid_micro"] == banners.price_micro(conn, app.state.config, 3)
    bal = conn.execute("SELECT balance_micro FROM users WHERE login = 'buyer'").fetchone()[0]
    assert bal == 100 * 10_000 - row["paid_micro"]        # 21 сомони списаны сразу
    cache.clear()
    assert banners.active(conn) == []                       # без одобрения не показывается
    assert "На проверке" in c.get("/panel/ads").text
    a, atoken = admin
    assert "Заявки на проверку" in a.get("/admin/banners").text
    a.post(f"/admin/banners/{row['id']}/decide", data={"csrf": atoken, "action": "approve"})
    shown = banners.active(conn)
    assert [b["id"] for b in shown] == [row["id"]]
    got = conn.execute("SELECT from_ts, until_ts FROM banners WHERE id = ?", (row["id"],)).fetchone()
    assert got["until_ts"] - got["from_ts"] == 3 * 86400            # 3 дня — ровно 72 часа, до секунды


def test_client_request_rejected_with_reason(admin, app, conn):
    c, token = _buyer(app, conn)
    c.post("/panel/ads", data={"csrf": token, "title": "Ставки", "link": "https://example.com", "days": "2"},
           files={"image": ("b.png", _png(), "image/png")})
    bid = banners.pending(conn)[0]["id"]
    a, atoken = admin
    a.post(f"/admin/banners/{bid}/decide", data={"csrf": atoken, "action": "reject", "note": "Азартные игры"})
    cache.clear()
    assert banners.active(conn) == [] and banners.pending(conn) == []
    assert "Причина: Азартные игры" in c.get("/panel/ads").text
    bal = conn.execute("SELECT balance_micro FROM users WHERE login = 'buyer'").fetchone()[0]
    assert bal == 100 * 10_000                               # отказ — деньги вернулись


def test_client_request_needs_link_and_valid_days(app, conn):
    c, token = _buyer(app, conn)
    for data in ({"title": "Канал", "link": "", "days": "7"}, {"title": "Канал", "link": "t.me/x", "days": "7"},
                 {"title": "Канал", "link": "javascript:alert(1)", "days": "7"}):
        c.post("/panel/ads", data={"csrf": token, **data}, files={"image": ("b.png", _png(), "image/png")})
    assert banners.pending(conn) == []


def test_client_request_needs_balance(app, conn, config):
    c, token = _buyer(app, conn, balance="0.5")              # меньше 7 сомони
    r = c.post("/panel/ads", data={"csrf": token, "title": "Канал", "link": "t.me/x", "days": "1"},
               files={"image": ("b.png", _png(), "image/png")})
    assert "Не хватает денег" in r.text
    assert conn.execute("SELECT COUNT(*) FROM banners").fetchone()[0] == 0
    assert list(banners.folder(config).glob("*.webp")) == []  # картинку не оставили


def test_ads_page_open_without_login(app):
    r = TestClient(app).get("/panel/ads", follow_redirects=False)
    assert r.status_code == 200
    assert "7 сомони за день" in r.text and "Азартные игры" in r.text and "/register?next=/panel/ads" in r.text


def test_banners_in_telegram_mini_app(admin, app):
    c, token = admin
    _add(c, token, title="Здесь может быть ваша реклама", link="/panel/ads")
    cache.clear()
    page = TestClient(app).get("/tg").text
    assert "data-bnr" in page and "Здесь может быть ваша реклама" in page


def test_banner_image_served_under_static(admin, app, conn):
    """Картинки — под /static/bn/: Cloudflare не проверяет этот путь, и в мини-приложении картинка грузится."""
    c, token = admin
    _add(c, token)
    cache.clear()
    src = banners.active(conn)[0]["src"]
    assert src.startswith("/static/bn/")
    r = TestClient(app).get(src)
    assert r.status_code == 200 and r.headers["content-type"] == "image/webp"
    assert "immutable" in r.headers["cache-control"]


def test_house_banner_always_last_and_kept(admin, conn):
    c, token = admin
    _add(c, token, title="Здесь может быть ваша реклама", link="https://donatix.tj/panel/ads", sort="0")
    for i in range(banners.MAX_ACTIVE + 2):
        _add(c, token, title=f"Платный {i}", link="t.me/x", sort="100")
    cache.clear()
    shown = banners.active(conn)
    assert len(shown) == banners.MAX_ACTIVE
    assert shown[-1]["title"] == "Здесь может быть ваша реклама"
    assert all(b["title"].startswith("Платный") for b in shown[:-1])


UA = {"user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Mobile/15E148 Safari/604.1"}


def test_views_and_clicks_counted_honestly(admin, app, conn):
    c, token = admin
    _add(c, token, link="t.me/x")
    bid = banners.all_rows(conn)[0]["id"]
    one, two, robot = TestClient(app), TestClient(app), TestClient(app)
    one.cookies.set("dx_vid", "a" * 16)
    two.cookies.set("dx_vid", "b" * 16)
    for _ in range(5):                                  # обновлял страницу — всё равно один просмотр
        assert one.post("/api/bn-view", content='{"id": %d}' % bid, headers=UA).status_code == 204
        one.get(f"/bn-go/{bid}", headers=UA, follow_redirects=False)
    two.post("/api/bn-view", content='{"id": %d}' % bid, headers=UA)
    robot.post("/api/bn-view", content='{"id": %d}' % bid, headers={"user-agent": "Googlebot/2.1"})
    robot.get(f"/bn-go/{bid}", headers={"user-agent": "TelegramBot (like TwitterBot)"}, follow_redirects=False)
    one.post("/api/bn-view", content="мусор", headers=UA)
    row = banners.all_rows(conn)[0]
    assert (row["views"], row["clicks"]) == (2, 1)
    assert banners.ctr(2, 1) == "50%" and banners.ctr(0, 0) == "—"
    assert "На сайте" in c.get("/admin/banners").text and "В ботах" in c.get("/admin/banners").text


# ── Реклама в ботах ─────────────────────────────────────────

DAY = 86400


def _paid_and_house(admin):
    c, token = admin
    _add(c, token, title="Здесь может быть ваша реклама", link="/panel/ads")
    _add(c, token, title="Канал А", link="t.me/a")
    _add(c, token, title="Канал Б", link="t.me/b")
    cache.clear()


def test_bot_ads_two_per_day_spaced_and_not_for_newbies(admin, conn, config):
    _paid_and_house(admin)
    t0 = 1_800_000_000.0
    nxt = lambda t: banners.bot_next(conn, config, 555, "shop", now=t)  # noqa: E731
    assert nxt(t0) is None                                   # новичок — не на самом первом /start
    assert nxt(t0 + 30) is None                              # и не раньше минуты
    first = nxt(t0 + 11 * 60)
    assert first and first["photo"].endswith("-tg.jpg") and "/bn-go/" in first["url"]
    assert nxt(t0 + 60 * 60) is None                         # меньше 4 часов — рано
    second = nxt(t0 + 11 * 60 + 4 * 3600 + 1)
    assert second and second["id"] != first["id"]            # чередуем: второй — другой платный
    assert nxt(t0 + 2 * DAY) is not None                     # через пару дней пришёл — сразу видит (гарантия)
    titles = {first["title"], second["title"]}
    assert titles == {"Канал А", "Канал Б"}                  # пока есть платные — приглашение не показываем


def test_bot_ads_daily_cap(admin, conn, config):
    _paid_and_house(admin)
    t0 = 1_800_000_000.0
    banners.bot_next(conn, config, 7, "shop", now=t0)
    got = [banners.bot_next(conn, config, 7, "gift", now=t0 + 600 + i * 5 * 3600) for i in range(5)]
    # 5 попыток с шагом 5 часов (25 часов): в одни сутки — не больше двух показов
    days = {}
    for i, ad in enumerate(got):
        if ad:
            d = int((t0 + 600 + i * 5 * 3600 + banners.BOT_TZ) // DAY)
            days[d] = days.get(d, 0) + 1
    assert days and max(days.values()) <= 2
    assert sum(1 for a in got if a) == 4                     # каждые 5 часов: 2 + 2 по суткам, без пропусков


def test_bot_message_has_go_and_skip(admin, conn, config):
    _paid_and_house(admin)
    ad = banners.bot_next(conn, config, 9, "shop", now=1_800_000_000.0 + 3600) or \
        banners.bot_next(conn, config, 9, "shop", now=1_800_000_000.0 + 7200)
    msg = banners.bot_message(ad)
    kb = msg["reply_markup"]["inline_keyboard"]
    assert kb[0][0]["text"] == "Перейти" and kb[0][0]["url"] == ad["url"]
    assert kb[1][0] == {"text": "Пропустить", "callback_data": "adskip"}
    assert msg["caption"].endswith("Реклама")
    assert (banners.folder(config) / ad["photo"].rsplit("/", 1)[1]).exists()


def test_partner_api_never_shows_ad_to_bot_staff(admin, app, conn):
    _paid_and_house(admin)
    uid, key = make_client(conn, login="partner")
    conn.execute("INSERT INTO bots (user_id, token_enc, username, admin_ids, enabled, created_at, updated_at) "
                 "VALUES (?, 'x', 'pbot', '111,222', 1, '2026-01-01', '2026-01-01')", (uid,))
    c = TestClient(app)
    h = {"X-API-Key": key}
    banners._ensure_bot(conn)                                # оба «давно знакомы» — правило новичка не мешает
    conn.execute("INSERT OR IGNORE INTO banner_bot_users (tg_id, first_seen) VALUES (111, 0), (333, 0)")
    import random
    random.seed(1)
    for _ in range(20):
        assert c.post("/api/v2/ads/next", json={"tg_user_id": 111}, headers=h).json()["ad"] is None   # владелец
    got = [c.post("/api/v2/ads/next", json={"tg_user_id": 333}, headers=h).json()["ad"] for _ in range(20)]
    assert sum(1 for a in got if a) == 1                     # клиенту — один показ (дальше 4 часа ждать)
    _, other = make_client(conn, login="nobot")
    assert c.post("/api/v2/ads/next", json={"tg_user_id": 333}, headers={"X-API-Key": other}).json()["ad"] is None



def test_paid_banner_ends_exactly_after_24h(admin, app, conn):
    """Одобрили в 07:00 на сутки — завтра в 07:00 показ заканчивается, секунда в секунду."""
    c, token = _buyer(app, conn)
    c.post("/panel/ads", data={"csrf": token, "title": "Канал", "link": "t.me/x", "days": "1"},
           files={"image": ("b.png", _png(1500, 600), "image/png")})
    bid = banners.pending(conn)[0]["id"]
    a, atoken = admin
    a.post(f"/admin/banners/{bid}/decide", data={"csrf": atoken, "action": "approve"})
    row = conn.execute("SELECT from_ts, until_ts FROM banners WHERE id = ?", (bid,)).fetchone()
    start = row["from_ts"]
    assert row["until_ts"] == start + 86400
    ids = lambda t: [b["id"] for b in banners.active(conn, now=t)]  # noqa: E731
    assert bid in ids(start + 1)
    assert bid in ids(start + 86400 - 1)                            # за секунду до конца — ещё показывается
    assert bid not in ids(start + 86400)                            # ровно через сутки — уже нет
    assert banners.when(1_800_000_000) == "15.01 13:00"             # время — по Душанбе (UTC+5)
    assert banners.left(start + 86400, now=start + 3600) == "23 ч 0 мин"
    page = c.get("/panel/ads").text
    assert "осталось" in page and "Показ:" in page
