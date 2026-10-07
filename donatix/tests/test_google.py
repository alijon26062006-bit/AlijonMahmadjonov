from conftest import web_login
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient

from donatix import accounts, google_auth

REAL_FETCH = google_auth.fetch_profile


@pytest.fixture
def gconf(config):
    config.google_client_id = "cid.apps.googleusercontent.com"
    config.google_client_secret = "secret"
    return config


def _google(monkeypatch, profile):
    def handler(req: httpx.Request):
        if req.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "at"})
        return httpx.Response(200, json=profile)
    monkeypatch.setattr(google_auth, "fetch_profile",
                        lambda config, code: REAL_FETCH(config, code, transport=httpx.MockTransport(handler)))


def _login(client, q=""):
    r = client.get("/auth/google" + q, follow_redirects=False)
    q = parse_qs(urlparse(r.headers["location"]).query)
    assert q["redirect_uri"] == ["http://testserver/auth/google/callback"] and q["client_id"]
    return client.get(f"/auth/google/callback?code=abc&state={q['state'][0]}", follow_redirects=False)


def test_button_only_when_configured(app, config):
    assert "Войти через Google" not in TestClient(app).get("/login").text
    config.google_client_id, config.google_client_secret = "x", "y"
    assert "Войти через Google" in TestClient(app).get("/login").text


def test_new_user_created_and_existing_matched(gconf, app, conn, monkeypatch):
    _google(monkeypatch, {"sub": "g1", "email": "Ali.Shop@gmail.com", "email_verified": True, "name": "Ali"})
    c = TestClient(app)
    r = _login(c)
    assert r.status_code == 303 and r.headers["location"] == "/panel"
    u = conn.execute("SELECT * FROM users WHERE email = 'ali.shop@gmail.com'").fetchone()
    assert u["google_sub"] == "g1" and u["login"] == "ali.shop" and u["status"] == "active"
    # второй вход — тот же аккаунт
    r = _login(TestClient(app))
    assert conn.execute("SELECT COUNT(*) FROM users WHERE role = 'client'").fetchone()[0] == 1

    # клиент с паролем, та же почта в Google — входит в свой аккаунт, Google запоминается.
    # Пароль, заданный без подтверждения почты, гасим: аккаунт мог заранее завести чужой
    uid = accounts.create_user(conn, email="old@example.com", login="oldshop", password="password123",
                               status="active")
    squatter = TestClient(app)
    web_login(squatter, "old@example.com", "password123")
    _google(monkeypatch, {"sub": "g2", "email": "old@example.com", "email_verified": True})
    c2 = TestClient(app)
    _login(c2)
    assert accounts.get_user(conn, uid)["google_sub"] == "g2"
    assert "oldshop" in c2.get("/panel").text
    assert accounts.authenticate(conn, "old@example.com", "password123") is None
    assert squatter.get("/panel", follow_redirects=False).status_code in (302, 303)
    c3 = TestClient(app)                                   # следующий вход через Google — сразу в аккаунт
    assert _login(c3).headers["location"] == "/panel"


def test_rejects_bad_state_and_unverified(gconf, app, conn, monkeypatch):
    c = TestClient(app)
    r = c.get("/auth/google/callback?code=abc&state=forged")
    assert "устарела" in r.text
    _google(monkeypatch, {"sub": "g3", "email": "x@gmail.com", "email_verified": False})
    r = _login(c)
    assert r.headers["location"] == "/login"
    assert conn.execute("SELECT COUNT(*) FROM users WHERE email = 'x@gmail.com'").fetchone()[0] == 0


def test_forgot_password_via_google(gconf, app, conn, monkeypatch):
    from conftest import csrf_of, make_client
    make_client(conn, login="gforgot")
    _google(monkeypatch, {"sub": "g9", "email": "gforgot@example.com", "email_verified": True, "name": "G"})
    c = TestClient(app)
    assert "Восстановить через Google" in c.get("/forgot").text
    r = _login(c, "?reset=1")
    assert r.headers["location"] == "/panel/password"
    form = c.get("/panel/password").text
    assert 'name="old"' not in form
    c.post("/panel/password", data={"csrf": csrf_of(form), "new": "brandnew123", "new2": "brandnew123"})
    web_login(TestClient(app), "gforgot@example.com", "brandnew123")


def test_link_google_satisfies_requirement(gconf, app, conn, monkeypatch):
    from conftest import make_client
    uid, _ = make_client(conn, login="glink")
    c = TestClient(app)
    web_login(c, "glink@example.com", "password123")
    assert c.get("/panel", follow_redirects=False).status_code == 200   # кабинет открыт сразу, привязка — по желанию
    assert c.get("/panel/telegram", follow_redirects=False).headers["location"] == "/panel"
    _google(monkeypatch, {"sub": "g10", "email": "other.mail@gmail.com", "email_verified": True, "name": "G"})
    r = _login(c, "?link=1")
    assert r.headers["location"] == "/panel"
    assert accounts.get_user(conn, uid)["google_sub"] == "g10"
    assert c.get("/panel", follow_redirects=False).status_code == 200
    # этот Google уже занят — другой аккаунт привязать его не может
    uid2, _ = make_client(conn, login="glink2")
    c2 = TestClient(app)
    web_login(c2, "glink2@example.com", "password123")
    assert _login(c2, "?link=1").headers["location"] == "/panel/telegram"
    assert accounts.get_user(conn, uid2)["google_sub"] is None
    # забыл пароль — входит через привязанный Google (почта другая)
    c3 = TestClient(app)
    assert _login(c3, "?reset=1").headers["location"] == "/panel/password"
