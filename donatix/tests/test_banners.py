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
