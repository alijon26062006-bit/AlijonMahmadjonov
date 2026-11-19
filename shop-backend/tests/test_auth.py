from tests.conftest import register


def test_register_login_me_logout(client):
    r = register(client)
    assert r.status_code == 201
    assert r.json()["role"] == "user" and r.json()["balance"] == "0.0000"
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    assert client.get("/api/auth/me").json()["username"] == "user1"
    assert client.post("/api/auth/logout").status_code == 204
    client.cookies.clear()
    assert client.get("/api/auth/me").status_code == 401
    r = client.post("/api/auth/login", json={"email": "USER@example.com", "password": "password123"})
    assert r.status_code == 200
    assert client.get("/api/auth/me").status_code == 200


def test_duplicate_and_validation(client):
    assert register(client).status_code == 201
    assert register(client, username="other").status_code == 409
    assert register(client, email="x@example.com", username="USER1").status_code == 409
    assert register(client, email="y@example.com", username="a b").status_code == 422
    assert register(client, email="z@example.com", username="zzz", password="short").status_code == 422


def test_wrong_password_and_rate_limit(client):
    register(client)
    client.cookies.clear()
    for _ in range(5):
        assert client.post("/api/auth/login", json={"email": "user@example.com", "password": "nope"}).status_code == 401
    r = client.post("/api/auth/login", json={"email": "user@example.com", "password": "password123"})
    assert r.status_code == 429


def test_password_is_hashed(client, engine):
    register(client)
    from sqlalchemy import text
    with engine.connect() as conn:
        h = conn.execute(text("select password_hash from users")).scalar()
    assert h.startswith("$argon2") and "password123" not in h


def test_admin_by_email(client):
    r = register(client, email="boss@example.com", username="boss")
    assert r.json()["role"] == "admin"


def test_bad_token_rejected(client):
    client.cookies.set("session", "garbage")
    assert client.get("/api/auth/me").status_code == 401
