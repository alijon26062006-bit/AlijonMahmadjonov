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
    got = conn.execute("SELECT starts_at, ends_at FROM banners WHERE id = ?", (row["id"],)).fetchone()
    from datetime import date, timedelta
    assert got["ends_at"] == (date.fromisoformat(got["starts_at"]) + timedelta(days=2)).isoformat()


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
