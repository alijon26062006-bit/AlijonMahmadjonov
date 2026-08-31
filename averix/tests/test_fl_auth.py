"""
AVERIX Freelance — учётные записи.

Проверяем не то, что форма отрисовалась, а то, что происходит в базе
и что видно снаружи: можно ли перебрать адреса, можно ли войти дважды
по одной ссылке, закрываются ли чужие сессии при смене пароля.
"""
import re

from app import accounts
from app.db import connect

REG = "/freelance/register"
LOGIN = "/freelance/login"


def form_token(client, url: str) -> str:
    """Забирает одноразовый токен формы. Cookie клиент хранит сам."""
    page = client.get(url).text
    match = re.search(r'name="fc" value="([^"]+)"', page)
    assert match, f"на странице {url} нет токена формы"
    return match.group(1)


def register(client, email="ivan@example.com", password="ochen-dlinnyy-parol",
             name="Иван", role="freelancer", **extra):
    data = {"fc": form_token(client, REG), "email": email, "password": password,
            "name": name, "role": role}
    data.update(extra)
    return client.post(REG, data=data, follow_redirects=False)


def sign_in(client, email="ivan@example.com", password="ochen-dlinnyy-parol",
            **extra):
    data = {"fc": form_token(client, LOGIN), "email": email, "password": password}
    data.update(extra)
    return client.post(LOGIN, data=data, follow_redirects=False)


def csrf_of(text: str) -> str:
    return re.search(r'name="csrf" value="([^"]+)"', text).group(1)


def count(table: str) -> int:
    with connect() as conn:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


# ============================================================
# Регистрация
# ============================================================

def test_registration_creates_account_and_signs_in(client):
    answer = register(client)
    assert answer.status_code == 303
    assert answer.headers["location"] == "/freelance/dashboard"
    assert count("users") == 1
    with connect() as conn:
        row = conn.execute("SELECT * FROM users").fetchone()
    assert row["email"] == "ivan@example.com"
    # Пароль в базе не лежит ни в каком виде, кроме хеша
    assert "ochen-dlinnyy-parol" not in row["password_hash"]
    assert row["password_hash"].startswith("scrypt$")
    assert client.get("/freelance/dashboard").status_code == 200


def test_role_choice_creates_the_right_profile(client):
    register(client, role="client", name="ООО Ромашка")
    assert count("client_profiles") == 1
    assert count("freelancers") == 0

    client.post("/freelance/logout", data={})
    client.cookies.clear()

    register(client, email="petr@example.com", role="freelancer", name="Пётр")
    assert count("freelancers") == 1
    with connect() as conn:
        row = conn.execute("SELECT name, user_id, status FROM freelancers").fetchone()
    assert row["name"] == "Пётр"
    assert row["user_id"] is not None
    assert row["status"] == "new"


def test_registration_refuses_duplicate_email(client):
    register(client)
    client.cookies.clear()
    answer = register(client, name="Другой Иван")
    assert answer.status_code == 400
    assert count("users") == 1


def test_registration_ignores_case_of_email(client):
    register(client, email="Ivan@Example.com")
    with connect() as conn:
        assert conn.execute("SELECT email FROM users").fetchone()[0] == "ivan@example.com"
    client.cookies.clear()
    answer = register(client, email="IVAN@EXAMPLE.COM")
    assert answer.status_code == 400
    assert count("users") == 1


def test_registration_refuses_short_password(client):
    answer = register(client, password="korotkiy")
    assert answer.status_code == 400
    assert "Пароль" in answer.text
    assert count("users") == 0


def test_registration_refuses_bad_email(client):
    answer = register(client, email="не-почта")
    assert answer.status_code == 400
    assert count("users") == 0


def test_registration_requires_role(client):
    answer = register(client, role="")
    assert answer.status_code == 400
    assert count("users") == 0


def test_registration_without_form_token_is_refused(client):
    answer = client.post(REG, data={
        "email": "ivan@example.com", "password": "ochen-dlinnyy-parol",
        "name": "Иван", "role": "client",
    }, follow_redirects=False)
    assert answer.status_code == 400
    assert count("users") == 0


def test_honeypot_drops_registration_silently(client):
    answer = register(client, website="http://spam", email="bot@example.com")
    assert answer.status_code == 303
    # Роботу не сообщаем, что его раскусили: ответ обычный
    assert count("users") == 0


def test_registration_is_rate_limited(client):
    for n in range(5):
        client.cookies.clear()
        assert register(client, email=f"user{n}@example.com").status_code == 303
    client.cookies.clear()
    answer = register(client, email="user6@example.com")
    assert answer.status_code == 429
    assert count("users") == 5


# ============================================================
# Вход
# ============================================================

def test_login_and_logout(client):
    register(client)
    client.cookies.clear()

    assert sign_in(client).status_code == 303
    page = client.get("/freelance/dashboard")
    assert page.status_code == 200

    client.post("/freelance/logout", data={"csrf": csrf_of(page.text)})
    assert client.get("/freelance/dashboard",
                      follow_redirects=False).status_code == 303


def test_logout_without_csrf_keeps_session(client):
    register(client)
    client.post("/freelance/logout", data={"csrf": "чужое"})
    assert client.get("/freelance/dashboard").status_code == 200


def test_unknown_email_and_wrong_password_answer_the_same(client):
    register(client)
    client.cookies.clear()

    unknown = sign_in(client, email="net-takogo@example.com")
    wrong = sign_in(client, password="ne-tot-parol-vovse")
    assert unknown.status_code == wrong.status_code == 401
    # Тексты совпадают дословно: иначе по ответу перебирают адреса
    assert "Неверная почта или пароль" in unknown.text
    assert "Неверная почта или пароль" in wrong.text


def test_login_is_blocked_after_five_failures(client):
    register(client)
    client.cookies.clear()
    for _ in range(5):
        sign_in(client, password="ne-tot-parol-vovse")
    answer = sign_in(client)
    assert answer.status_code == 429
    assert "Слишком много попыток" in answer.text


def test_suspended_account_cannot_enter(client):
    register(client)
    with connect() as conn:
        conn.execute("UPDATE users SET status = 'suspended'")
        conn.commit()
    # Уже открытая сессия перестаёт работать сразу
    assert client.get("/freelance/dashboard",
                      follow_redirects=False).status_code == 303
    client.cookies.clear()
    answer = sign_in(client)
    assert answer.status_code == 401
    assert "приостановлена" in answer.text


def test_session_cookie_is_httponly(client):
    answer = register(client)
    raw = answer.headers.get("set-cookie", "")
    assert accounts.SESSION_COOKIE in raw
    assert "HttpOnly" in raw
    assert "SameSite=lax" in raw or "samesite=lax" in raw.lower()


# ============================================================
# Куда пускает параметр next
# ============================================================

def test_guard_sends_to_login_with_return_address(client):
    answer = client.get("/freelance/dashboard", follow_redirects=False)
    assert answer.status_code == 303
    assert answer.headers["location"] == "/freelance/login?next=/freelance/dashboard"


def test_next_cannot_lead_to_another_site(client):
    register(client)
    client.cookies.clear()
    for evil in ("https://zloy.example.com", "//zloy.example.com",
                 "/admin", "/freelance\\..\\admin"):
        answer = sign_in(client, next=evil)
        assert answer.status_code == 303
        assert answer.headers["location"] == "/freelance/dashboard", evil
        client.cookies.clear()


# ============================================================
# Ссылки из писем
# ============================================================

def test_verification_link_works_once(client):
    register(client)
    with connect() as conn:
        user_id = conn.execute("SELECT id FROM users").fetchone()["id"]
        token = accounts.issue_token(conn, user_id, "verify", 48)
        conn.commit()

    first = client.get(f"/freelance/verify?token={token}")
    assert first.status_code == 200
    with connect() as conn:
        assert conn.execute("SELECT email_verified FROM users").fetchone()[0] == 1

    second = client.get(f"/freelance/verify?token={token}")
    assert second.status_code == 400


def test_reset_changes_password_and_closes_all_sessions(client):
    register(client)
    with connect() as conn:
        user_id = conn.execute("SELECT id FROM users").fetchone()["id"]
        token = accounts.issue_token(conn, user_id, "reset", 2)
        conn.commit()
    assert count("user_sessions") == 1

    fc = form_token(client, f"/freelance/reset?token={token}")
    answer = client.post("/freelance/reset", data={
        "fc": fc, "token": token, "password": "sovsem-drugoy-parol"})
    assert answer.status_code == 200
    assert "Пароль изменён" in answer.text

    # Все прежние входы закрыты
    assert count("user_sessions") == 0
    client.cookies.clear()
    assert sign_in(client, password="sovsem-drugoy-parol").status_code == 303


def test_reset_link_works_once(client):
    register(client)
    with connect() as conn:
        user_id = conn.execute("SELECT id FROM users").fetchone()["id"]
        token = accounts.issue_token(conn, user_id, "reset", 2)
        conn.commit()
    fc = form_token(client, f"/freelance/reset?token={token}")
    client.post("/freelance/reset", data={"fc": fc, "token": token,
                                          "password": "sovsem-drugoy-parol"})
    fc = form_token(client, f"/freelance/reset?token={token}")
    again = client.post("/freelance/reset", data={
        "fc": fc, "token": token, "password": "eshchyo-odin-parol-tut"})
    assert again.status_code == 400
    assert "устарела" in again.text


def test_forgot_answers_the_same_for_any_address(client):
    register(client)
    client.cookies.clear()

    known = client.post("/freelance/forgot", data={
        "fc": form_token(client, "/freelance/forgot"), "email": "ivan@example.com"})
    unknown = client.post("/freelance/forgot", data={
        "fc": form_token(client, "/freelance/forgot"), "email": "nikto@example.com"})
    assert known.status_code == unknown.status_code == 200
    assert "письмо со ссылкой отправлено" in known.text
    assert "письмо со ссылкой отправлено" in unknown.text
    # Ссылка на сброс заведена только для существующего адреса
    with connect() as conn:
        resets = conn.execute(
            "SELECT COUNT(*) FROM user_tokens WHERE kind = 'reset'").fetchone()[0]
    assert resets == 1


# ============================================================
# Два лица одного человека
# ============================================================

def test_second_role_is_added_without_second_account(client):
    register(client, role="freelancer", name="Пётр")
    page = client.get("/freelance/dashboard")
    client.post("/freelance/roles", data={"csrf": csrf_of(page.text),
                                          "role": "client", "name": "Пётр"})
    assert count("users") == 1
    assert count("client_profiles") == 1
    assert count("freelancers") == 1


def test_second_role_needs_csrf(client):
    register(client, role="freelancer")
    client.post("/freelance/roles", data={"csrf": "чужое", "role": "client"})
    assert count("client_profiles") == 0


# ============================================================
# Площадка и витрина не мешают друг другу
# ============================================================

def test_new_specialist_profile_is_not_published_anywhere(client):
    register(client, role="freelancer", name="Пётр Неопубликованный")
    for url in ("/", "/team", "/projects", "/freelance", "/sitemap.xml"):
        assert "Неопубликованный" not in client.get(url).text, url


def test_studio_application_form_kept_its_address(client):
    assert client.get("/freelance/studio").status_code == 200
    answer = client.post("/freelance/apply", data={
        "name": "Пётр", "telegram": "@petr", "skills": "React",
        "about": "Пишу интерфейсы два года, делал магазин и админку.",
    }, follow_redirects=False)
    assert answer.status_code == 303
    with connect() as conn:
        # Анкета с сайта учётной записи не создаёт
        row = conn.execute("SELECT user_id, login FROM freelancers").fetchone()
    assert row["user_id"] is None
    assert row["login"] is None


def test_private_marketplace_pages_are_closed_to_search(client):
    body = client.get("/robots.txt").text
    for path in ("/freelance/dashboard", "/freelance/login", "/freelance/register"):
        assert f"Disallow: {path}" in body
    assert "/freelance/dashboard" not in client.get("/sitemap.xml").text
