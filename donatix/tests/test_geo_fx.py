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
    assert geo.country(geodb, "8.8.8.8") == ""
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
