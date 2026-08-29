"""Админка: вход, права, CSRF, разделы студии."""
import io

from conftest import ADMIN_LOGIN, ADMIN_PASSWORD, login, make_project

from app.db import connect

CLOSED = ("/admin/projects", "/admin/settings", "/admin/team",
          "/admin/vacancies", "/admin/requests", "/admin/applications")


# ---------- вход ----------

def test_admin_pages_need_login(client):
    for url in CLOSED:
        answer = client.get(url, follow_redirects=False)
        assert answer.status_code == 303, url
        assert answer.headers["location"] == "/admin"


def test_wrong_password_is_rejected(client):
    import re
    lc = re.search(r'name="lc" value="([^"]+)"', client.get("/admin").text).group(1)
    answer = client.post("/admin/login", data={
        "username": ADMIN_LOGIN, "password": "не тот пароль", "lc": lc,
    })
    assert answer.status_code == 401
    assert "averix_session" not in answer.cookies


def test_password_never_leaves_the_server(client):
    login(client)
    for url in ("/admin", "/admin/settings"):
        assert ADMIN_PASSWORD not in client.get(url).text


def test_login_is_blocked_after_repeated_failures(client):
    import re
    for _ in range(6):
        lc = re.search(r'name="lc" value="([^"]+)"', client.get("/admin").text)
        client.post("/admin/login", data={
            "username": ADMIN_LOGIN, "password": "мимо", "lc": lc.group(1) if lc else "",
        })
    with connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM login_attempts").fetchone()[0] >= 5


def test_logout_kills_the_session(client):
    csrf = login(client)
    client.post("/admin/logout", data={"csrf": csrf}, follow_redirects=False)
    assert client.get("/admin/projects", follow_redirects=False).status_code == 303


# ---------- CSRF ----------

def test_foreign_csrf_changes_nothing(client):
    login(client)
    for token in ("", "подделка", "x" * 64):
        client.post("/admin/team/save", data={"csrf": token, "name": "Взлом"},
                    follow_redirects=False)
    with connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM team_members").fetchone()[0] == 0


def test_cyrillic_csrf_does_not_crash(client):
    """Подделанный токен с кириллицей раньше ронял запрос ошибкой 500."""
    login(client)
    answer = client.post("/admin/team/save",
                         data={"csrf": "подделка", "name": "Взлом"},
                         follow_redirects=False)
    assert answer.status_code == 303


# ---------- настройки ----------

def test_settings_change_the_site(client):
    csrf = login(client)
    with connect() as conn:
        rows = conn.execute("SELECT * FROM site_settings").fetchall()
    data = {"csrf": csrf}
    for row in rows:
        data["ru__" + row["key"]] = row["value_ru"] or ""
        data["tj__" + row["key"]] = row["value_tj"] or ""
    data["ru__city"] = "Худжанд"
    client.post("/admin/settings", data=data, follow_redirects=False)
    assert "Худжанд" in client.get("/").text


def test_unknown_setting_key_is_ignored(client):
    csrf = login(client)
    client.post("/admin/settings", data={"csrf": csrf, "ru__чужой_ключ": "зло"},
                follow_redirects=False)
    with connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM site_settings WHERE key = 'чужой_ключ'"
        ).fetchone()[0] == 0


# ---------- команда ----------

def test_team_member_appears_on_the_site(client):
    csrf = login(client)
    client.post("/admin/team/save", data={
        "csrf": csrf, "name": "Мария", "position_ru": "дизайнер", "visible": "1",
    }, follow_redirects=False)
    assert "Мария" in client.get("/team").text


def test_hidden_member_is_not_shown(client):
    csrf = login(client)
    client.post("/admin/team/save", data={"csrf": csrf, "name": "Скрытый"},
                follow_redirects=False)
    assert "Скрытый" not in client.get("/team").text


def test_member_without_name_is_not_created(client):
    csrf = login(client)
    client.post("/admin/team/save", data={"csrf": csrf, "name": "  "},
                follow_redirects=False)
    with connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM team_members").fetchone()[0] == 0


# ---------- вакансии ----------

def test_open_vacancy_appears_on_the_site(client):
    csrf = login(client)
    client.post("/admin/vacancies/save", data={
        "csrf": csrf, "title_ru": "Backend-разработчик",
        "work_type": "remote", "employment": "project", "status": "open",
    }, follow_redirects=False)
    assert "Backend-разработчик" in client.get("/careers").text


def test_closed_vacancy_is_hidden(client):
    csrf = login(client)
    client.post("/admin/vacancies/save", data={
        "csrf": csrf, "title_ru": "Закрытая", "work_type": "remote",
        "employment": "project",
    }, follow_redirects=False)
    assert "Закрытая" not in client.get("/careers").text


def test_invented_work_type_does_not_break_the_database(client):
    csrf = login(client)
    client.post("/admin/vacancies/save", data={
        "csrf": csrf, "title_ru": "Странная", "work_type": "телепортация",
        "employment": "выдумка", "status": "open",
    }, follow_redirects=False)
    with connect() as conn:
        row = conn.execute("SELECT work_type, employment FROM vacancies").fetchone()
    assert row["work_type"] == "remote"
    assert row["employment"] == "project"


# ---------- заявки ----------

def test_status_changes(client):
    csrf = login(client)
    client.post("/request", data={
        "name": "Иван", "contact": "@ivan", "message": "Нужен сайт для кофейни.",
    })
    with connect() as conn:
        rid = conn.execute("SELECT id FROM client_requests").fetchone()["id"]
    client.post(f"/admin/requests/client_requests/{rid}/status",
                data={"csrf": csrf, "status": "contacted", "note": "позвонил"},
                follow_redirects=False)
    with connect() as conn:
        assert conn.execute("SELECT status FROM client_requests").fetchone()[0] == "contacted"


def test_invented_status_is_refused(client):
    csrf = login(client)
    client.post("/request", data={
        "name": "Иван", "contact": "@ivan", "message": "Нужен сайт для кофейни.",
    })
    with connect() as conn:
        rid = conn.execute("SELECT id FROM client_requests").fetchone()["id"]
    answer = client.post(f"/admin/requests/client_requests/{rid}/status",
                         data={"csrf": csrf, "status": "хакер", "note": ""},
                         follow_redirects=False)
    assert answer.status_code == 404
    with connect() as conn:
        assert conn.execute("SELECT status FROM client_requests").fetchone()[0] == "new"


def test_foreign_table_name_is_refused(client):
    csrf = login(client)
    answer = client.post("/admin/requests/admins/1/status",
                         data={"csrf": csrf, "status": "new"}, follow_redirects=False)
    assert answer.status_code == 404


def test_application_can_become_a_team_card(client):
    csrf = login(client)
    client.post("/apply", data={
        "name": "Пётр", "telegram": "@petr", "direction": "frontend",
        "message": "Пишу на React два года, хочу в студию.",
    })
    with connect() as conn:
        aid = conn.execute("SELECT id FROM job_applications").fetchone()["id"]
    client.post(f"/admin/applications/{aid}/hire", data={"csrf": csrf},
                follow_redirects=False)
    with connect() as conn:
        member = conn.execute("SELECT * FROM team_members").fetchone()
        status = conn.execute("SELECT status FROM job_applications").fetchone()[0]
    assert member["name"] == "Пётр"
    # карточка скрыта, пока её не заполнили руками
    assert member["visible"] == 0
    assert status == "accepted"


# ---------- проекты и картинки ----------

def test_project_publishing(client):
    csrf = login(client)
    pid = make_project(slug="draft-one", status="draft")
    assert client.get("/projects/draft-one").status_code == 404
    client.post(f"/admin/projects/{pid}/toggle",
                data={"csrf": csrf, "field": "status"}, follow_redirects=False)
    assert client.get("/projects/draft-one").status_code == 200


def _png() -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (60, 40), (30, 20, 50)).save(buf, "PNG")
    return buf.getvalue()


def test_script_disguised_as_picture_is_refused(client):
    csrf = login(client)
    pid = make_project()
    answer = client.post(
        f"/admin/projects/{pid}/images",
        data={"csrf": csrf},
        files={"image": ("shell.php.jpg", b"<?php system($_GET['c']); ?>", "image/jpeg")},
    )
    assert answer.status_code in (200, 303, 400)
    with connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM project_images").fetchone()[0] == 0


def test_picture_of_another_project_cannot_be_deleted(client):
    csrf = login(client)
    mine = make_project(slug="mine")
    other = make_project(slug="other")
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO project_images (project_id, filename) VALUES (?, 'a.webp')",
            (other,),
        )
        conn.commit()
        image_id = cur.lastrowid
    client.post(f"/admin/projects/{mine}/images/{image_id}/delete",
                data={"csrf": csrf}, follow_redirects=False)
    with connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM project_images").fetchone()[0] == 1
