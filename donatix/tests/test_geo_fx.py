"""Страны СНГ: цены в местной валюте (только показ), оплата — только крипта. Таджикистан — как раньше."""
import ipaddress
import json
from decimal import Decimal

import pytest

from donatix import fx, geo

UZ_IP, RU_IP, TJ_IP = "84.54.64.10", "5.8.1.1", "185.70.0.5"


def _rows(*items):
    return [[int(ipaddress.ip_address(a)), int(ipaddress.ip_address(b)), cc] for a, b, cc in items]


@pytest.fixture
def geodb(config, monkeypatch):
    data = {"v4": _rows(("84.54.64.0", "84.54.127.255", "UZ"), ("5.8.0.0", "5.8.255.255", "RU"),
                        ("185.70.0.0", "185.70.0.255", "TJ")), "v6": []}
    geo.path(config).write_text(json.dumps(data))
    geo._cache.update({"path": None, "mtime": None})
    return config


def test_build_keeps_only_cis():
    csv = "1.0.0.0,1.0.0.255,AU\n84.54.64.0,84.54.127.255,UZ\n2a00::,2a00::ffff,RU\n"
    out = geo.build(csv)
    assert [r[2] for r in out["v4"]] == ["UZ"] and [r[2] for r in out["v6"]] == ["RU"]


def test_country_lookup(geodb):
    assert geo.country(geodb, UZ_IP) == "UZ"
    assert geo.country(geodb, RU_IP) == "RU"
    assert geo.country(geodb, TJ_IP) == "TJ"
    assert geo.country(geodb, "8.8.8.8") == geo.OTHER
    assert geo.country(geodb, "127.0.0.1") == "" and geo.country(geodb, "nonsense") == ""


def test_fmt_rounds_up_and_groups():
    assert fx.fmt(Decimal("1"), "UZS", Decimal("12800.5")) == "12 801 сум"
    assert fx.fmt(Decimal("0.999"), "BYN", Decimal("3.3")) == "3.30 Br"
    assert fx.fmt(Decimal("10"), "RUB", Decimal("95.01")) == "951 ₽"


def test_rate_has_margin(config, conn):
    r = fx.rate(config, "UZS")
    assert r >= Decimal("12800") * Decimal("1.03")
    assert fx.rate(config, "TJS") is None and fx.rate(config, "USD") is None


def _client_from(app, ip):
    from fastapi.testclient import TestClient
    return TestClient(app, client=(ip, 50000))


def test_uz_visitor_sees_sum(app, geodb):
    c = _client_from(app, UZ_IP)
    html = c.get("/").text
    assert 'code: "UZS"' in html and "сум" in html


def test_tj_visitor_unchanged(app, geodb):
    html = _client_from(app, TJ_IP).get("/").text
    assert 'code: "TJS"' in html


def test_cookie_choice_wins(app, geodb):
    c = _client_from(app, UZ_IP)
    c.cookies.set("dx_cur", "USD")
    assert 'code: "USD"' in c.get("/").text
    r = c.get("/currency/RUB", follow_redirects=False)
    assert r.cookies.get("dx_cur") == "RUB"


def test_crypto_only_for_cis(app, geodb, conn):
    from conftest import csrf_of
    from donatix import accounts
    accounts.create_user(conn, email="uz@example.com", login="uzbek1", password="password123", status="active")
    c = _client_from(app, UZ_IP)
    token = csrf_of(c.get("/login").text)
    c.post("/login", data={"csrf": token, "email": "uz@example.com", "password": "password123"})
    from donatix import web
    from starlette.requests import Request
    req = Request({"type": "http", "client": (UZ_IP, 1), "app": app, "headers": []})
    assert web._crypto_only(req)
    assert all(m.get("network") for m in web._pay_methods(req, conn, app.state.config))
    req_tj = Request({"type": "http", "client": (TJ_IP, 1), "app": app, "headers": []})
    assert not web._crypto_only(req_tj)


def test_other_country_usd_and_crypto(app, geodb, conn):
    assert geo.country(geodb, "8.8.8.8") == geo.OTHER
    html = _client_from(app, "8.8.8.8").get("/").text
    assert 'code: "USD"' in html
    from donatix import web
    from starlette.requests import Request
    req = Request({"type": "http", "client": ("8.8.8.8", 1), "app": app, "headers": []})
    assert web._crypto_only(req)


def test_default_by_country_choice_any(app, geodb):
    c = _client_from(app, RU_IP)
    assert 'code: "RUB"' in c.get("/").text          # не выбрал сам — валюта страны
    c.cookies.set("dx_cur", "TJS")
    assert 'code: "TJS"' in c.get("/").text          # выбрал сам — любая из списка, сомони тоже
    c.cookies.set("dx_cur", "XYZ")
    assert 'code: "RUB"' in c.get("/").text          # чужой код — как по умолчанию
    assert fx.allowed("TJ") == ("TJS", "USD") and fx.allowed("RU") == ("RUB", "USD")
    assert fx.allowed(geo.OTHER) == ("USD",) and fx.allowed("") == ("TJS", "USD")
    assert fx.choose("KZ", "") == ("KZT", ("KZT", "USD"))
    assert fx.choose("KZ", "TJS") == ("TJS", ("TJS", "KZT", "USD"))   # выбранная — и в быстрых кнопках
    assert fx.choose("TJ", "USD") == ("USD", ("TJS", "USD"))
    assert fx.choose(geo.OTHER, "UZS") == ("UZS", ("UZS", "USD"))
    codes = [o["code"] for o in fx.options()]
    assert codes[:2] == ["TJS", "USD"] and set(codes) == {"TJS", "USD", *fx.CURRENCIES}
    assert fx.badge("TJS") == "с." and fx.badge("USD") == "$" and fx.badge("RUB") == "₽"


def _login(c, conn, login):
    from conftest import web_login
    from donatix import accounts
    accounts.create_user(conn, email=f"{login}@example.com", login=login, password="password123", status="active")
    web_login(c, f"{login}@example.com", "password123")


def test_settings_list_has_all_cis(app, geodb, conn):
    c = _client_from(app, TJ_IP)
    _login(c, conn, "tjuser1")
    page = c.get("/panel").text
    assert "Валюта цен" in page and 'popovertarget="cur-sheet"' in page and 'id="cur-sheet"' in page
    for code in fx.ALL:                                # в настройках — сомони, доллар и все валюты СНГ
        assert f'href="/currency/{code}?next=/panel"' in page
    assert "Поиск валюты" in page
    r = c.get("/currency/KGS?next=/panel", follow_redirects=False)
    assert r.headers["location"] == "/panel" and r.cookies.get("dx_cur") == "KGS"
    c.cookies.set("dx_cur", "KGS")
    page = c.get("/panel").text
    assert 'code: "KGS"' in page and "сом" in page and 'href="/currency/KGS"' in page   # и в шапке


def test_admin_header_has_currency_picker(app, geodb, conn):
    from conftest import web_login
    c = _client_from(app, RU_IP)                       # админа определило как Россию
    web_login(c, "admin@example.com", "adminpass123")
    page = c.get("/admin/stats").text
    assert 'class="cur-btn adm-cur"' in page and 'id="cur-sheet"' in page
    assert 'href="/currency/TJS?next=/admin/stats"' in page   # сомони выбрать можно
    r = c.get("/currency/TJS?next=/admin/stats", follow_redirects=False)
    assert r.headers["location"] == "/admin/stats"
    c.cookies.set("dx_cur", "TJS")
    assert 'code: "TJS"' in c.get("/admin/stats").text


@pytest.mark.parametrize("bad", ["https://evil.example/x", "//evil.example", "/\\evil.example", "/a\r\nSet-Cookie: x=1"])
def test_currency_next_only_own_pages(app, bad):
    from fastapi.testclient import TestClient
    r = TestClient(app).get("/currency/USD", params={"next": bad}, follow_redirects=False)
    assert r.headers["location"] == "/panel"


def test_live_balance_in_chosen_currency(app, geodb, conn, config):
    from donatix import live
    uid = conn.execute("SELECT id FROM users WHERE role = 'admin'").fetchone()[0]
    assert "₽" in live.state(config, uid, False, "RUB")["balance_html"]
    assert "с." in live.state(config, uid, False, "TJS")["balance_html"]
    assert live.state(config, uid, False, "USD")["balance_html"].startswith("$")


def test_tj_user_other_currency_hides_somoni_methods(app, geodb, conn):
    """Из Таджикистана, но выбрал не сомони — способы в сомони не показываем, подсказка «переключите на TJS»."""
    from conftest import csrf_of
    from donatix import accounts, web
    from starlette.requests import Request
    import json
    from donatix import db
    db.set_setting(conn, "pay.methods_json", json.dumps([
        {"code": "alif", "title": "Алиф", "details": "+992 900 000 000", "currency": "TJS", "enabled": True},
        {"code": "usdt", "title": "USDT TRC20", "details": "TXyz", "currency": "USDT", "network": "TRC20",
         "enabled": True}]))
    req = Request({"type": "http", "client": (TJ_IP, 1), "app": app, "headers": [(b"cookie", b"dx_cur=RUB")]})
    assert web._no_tjs(req) and not web._crypto_only(req)
    assert all(m["currency"] != "TJS" for m in web._pay_methods(req, conn, app.state.config))
    req_tjs = Request({"type": "http", "client": (TJ_IP, 1), "app": app, "headers": [(b"cookie", b"dx_cur=TJS")]})
    assert any(m["currency"] == "TJS" for m in web._pay_methods(req_tjs, conn, app.state.config))
    accounts.create_user(conn, email="tj@example.com", login="tojik1", password="password123", status="active")
    c = _client_from(app, TJ_IP)
    token = csrf_of(c.get("/login").text)
    c.post("/login", data={"csrf": token, "email": "tj@example.com", "password": "password123"})
    c.cookies.set("dx_cur", "RUB")
    html = c.get("/panel/balance").text
    assert "способы оплаты в сомони скрыты" in html and "/currency/TJS" in html
