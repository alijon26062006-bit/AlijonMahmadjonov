"""Фриланс: анкеты, кабинет, задачи, разграничение доступа."""
import re

import pytest
from conftest import login

from app import work
from app.db import connect


# ============================================================
# Помощники
# ============================================================

def make_freelancer(name="Пётр", status="approved", login_name="", password=""):
    with connect() as conn:
        fid = work.add_freelancer(conn, {
            "name": name, "telegram": "@" + (login_name or "user"),
            "specialization": "frontend", "skills": "React",
        })
        if status != "new":
            work.set_freelancer_status(conn, fid, status)
        if login_name:
            problem = work.set_freelancer_login(conn, fid, login_name, password)
            assert problem is None, problem
        conn.commit()
        return fid


def make_task(freelancer_id=None, status="todo", title="Задача"):
    with connect() as conn:
        pid = work.save_client_project(conn, None, {
            "title": "Внутренний проект", "client": "Заказчик",
            "budget": "коммерческая тайна", "status": "in_progress",
        })
        tid = work.save_task(conn, None, {
            "project_id": pid, "title": title, "status": status,
            "freelancer_id": freelancer_id, "actor": "AVERIX",
        })
        conn.commit()
        return pid, tid


def enter(client, login_name, password):
    page = client.get("/freelancer/login").text
    lc = re.search(r'name="lc" value="([^"]+)"', page).group(1)
    answer = client.post("/freelancer/login",
                         data={"login": login_name, "password": password, "lc": lc},
                         follow_redirects=True)
    return answer


def csrf_of(text: str) -> str:
    return re.search(r'name="csrf" value="([^"]+)"', text).group(1)


# ============================================================
# Публичная страница
# ============================================================

def test_freelance_page_opens(client):
    assert client.get("/freelance").status_code == 200


def test_application_is_saved(client):
    answer = client.post("/freelance/apply", data={
        "name": "Пётр", "telegram": "@petr", "skills": "React",
        "about": "Пишу интерфейсы два года, делал магазин и админку.",
    }, follow_redirects=False)
    assert answer.status_code == 303
    with connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM freelancers").fetchone()[0] == 1


def test_application_never_appears_on_the_site(client):
    client.post("/freelance/apply", data={
        "name": "Пётр Незаметный", "telegram": "@petr", "skills": "React",
        "about": "Пишу интерфейсы два года, делал магазин и админку.",
    })
    for url in ("/", "/team", "/freelance", "/projects", "/sitemap.xml"):
        assert "Незаметный" not in client.get(url).text, url


def test_application_without_skills_is_rejected(client):
    answer = client.post("/freelance/apply", data={
        "name": "Пётр", "telegram": "@petr", "skills": "",
        "about": "Пишу интерфейсы два года, делал магазин и админку.",
    })
    assert answer.status_code == 400
    with connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM freelancers").fetchone()[0] == 0


def test_honeypot_drops_application(client):
    answer = client.post("/freelance/apply", data={
        "name": "Бот", "telegram": "@bot", "skills": "всё",
        "about": "Спам спам спам спам спам спам.", "website": "http://spam",
    }, follow_redirects=False)
    assert answer.status_code == 303
    with connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM freelancers").fetchone()[0] == 0


def test_application_creates_notification(client):
    client.post("/freelance/apply", data={
        "name": "Пётр", "telegram": "@petr", "skills": "React",
        "about": "Пишу интерфейсы два года, делал магазин и админку.",
    })
    with connect() as conn:
        row = conn.execute("SELECT kind, seen FROM notifications").fetchone()
    assert row["kind"] == "freelancer"
    assert row["seen"] == 0


# ============================================================
# Вход в кабинет
# ============================================================

def test_cabinet_needs_login(client):
    for url in ("/freelancer/dashboard", "/freelancer/profile", "/freelancer/tasks/1"):
        answer = client.get(url, follow_redirects=False)
        assert answer.status_code == 303, url
        assert answer.headers["location"] == "/freelancer/login"


def test_new_application_cannot_log_in(client):
    make_freelancer(status="new")
    with connect() as conn:
        # доступ такому не выдаётся вовсе
        fid = conn.execute("SELECT id FROM freelancers").fetchone()["id"]
        problem = work.set_freelancer_login(conn, fid, "petr", "very-long-pass")
    assert problem is not None


def test_login_works_after_approval(client):
    make_freelancer(login_name="petr", password="very-long-pass")
    answer = enter(client, "petr", "very-long-pass")
    assert answer.status_code == 200
    assert "Мои задачи" in answer.text


def test_wrong_password_is_refused(client):
    make_freelancer(login_name="petr", password="very-long-pass")
    answer = enter(client, "petr", "не тот пароль")
    assert "Неверный логин или пароль" in answer.text
    assert client.get("/freelancer/dashboard", follow_redirects=False).status_code == 303


def test_answer_does_not_reveal_existing_logins(client):
    make_freelancer(login_name="petr", password="very-long-pass")
    exists = enter(client, "petr", "мимо").text
    missing = enter(client, "такого-нет", "мимо").text
    assert "Неверный логин или пароль" in exists
    assert "Неверный логин или пароль" in missing


def test_archived_freelancer_loses_access(client):
    fid = make_freelancer(login_name="petr", password="very-long-pass")
    with connect() as conn:
        work.set_freelancer_status(conn, fid, "archived")
        conn.commit()
    answer = enter(client, "petr", "very-long-pass")
    assert "Мои задачи" not in answer.text


def test_logout_ends_the_session(client):
    make_freelancer(login_name="petr", password="very-long-pass")
    answer = enter(client, "petr", "very-long-pass")
    client.post("/freelancer/logout", data={"csrf": csrf_of(answer.text)},
                follow_redirects=False)
    assert client.get("/freelancer/dashboard", follow_redirects=False).status_code == 303


# ============================================================
# Чужое остаётся чужим
# ============================================================

def test_other_task_is_invisible(client):
    mine = make_freelancer("Пётр", login_name="petr", password="very-long-pass")
    other = make_freelancer("Иван")
    _, tid = make_task(freelancer_id=other, status="assigned")
    enter(client, "petr", "very-long-pass")
    assert client.get("/freelancer/tasks/%d" % tid).status_code == 404
    assert "/freelancer/tasks/" not in client.get("/freelancer/dashboard").text


def test_other_task_cannot_be_moved(client):
    make_freelancer("Пётр", login_name="petr", password="very-long-pass")
    other = make_freelancer("Иван")
    _, tid = make_task(freelancer_id=other, status="assigned")
    answer = enter(client, "petr", "very-long-pass")
    client.post("/freelancer/tasks/%d/move" % tid,
                data={"csrf": csrf_of(answer.text), "status": "in_progress"},
                follow_redirects=False)
    with connect() as conn:
        assert conn.execute("SELECT status FROM tasks WHERE id = ?",
                            (tid,)).fetchone()[0] == "assigned"


def test_other_task_cannot_be_submitted(client):
    make_freelancer("Пётр", login_name="petr", password="very-long-pass")
    other = make_freelancer("Иван")
    _, tid = make_task(freelancer_id=other, status="in_progress")
    answer = enter(client, "petr", "very-long-pass")
    client.post("/freelancer/tasks/%d/submit" % tid,
                data={"csrf": csrf_of(answer.text), "result_text": "это сделал я",
                      "result_url": ""},
                follow_redirects=False)
    with connect() as conn:
        row = conn.execute("SELECT status, result_text FROM tasks WHERE id = ?",
                           (tid,)).fetchone()
    assert row["status"] == "in_progress"
    assert row["result_text"] is None


def test_client_data_never_reaches_the_cabinet(client):
    mine = make_freelancer("Пётр", login_name="petr", password="very-long-pass")
    _, tid = make_task(freelancer_id=mine, status="assigned")
    enter(client, "petr", "very-long-pass")
    pages = (client.get("/freelancer/dashboard").text
             + client.get("/freelancer/tasks/%d" % tid).text
             + client.get("/freelancer/profile").text)
    assert "коммерческая тайна" not in pages
    assert "Заказчик" not in pages


def test_admin_login_is_not_shown_to_the_freelancer(client):
    """История задачи общая, но логин админа — половина доступа в панель."""
    mine = make_freelancer("Пётр", login_name="petr", password="very-long-pass")
    _, tid = make_task(freelancer_id=mine, status="assigned")
    csrf = login(client)
    client.post("/admin/tasks/%d/move" % tid,
                data={"csrf": csrf, "status": "cancelled"}, follow_redirects=False)
    client.post("/admin/logout", data={"csrf": csrf}, follow_redirects=False)

    enter(client, "petr", "very-long-pass")
    assert "tester" not in client.get("/freelancer/tasks/%d" % tid).text


def test_profile_edits_only_own_fields(client):
    fid = make_freelancer("Пётр", login_name="petr", password="very-long-pass")
    with connect() as conn:
        work.set_freelancer_status(conn, fid, "approved", "заметка студии")
        conn.commit()
    answer = enter(client, "petr", "very-long-pass")
    client.post("/freelancer/profile", data={
        "csrf": csrf_of(answer.text), "name": "Пётр С.", "skills": "Vue",
        # попытка поднять себе статус, стереть заметку и сменить логин
        "status": "active", "admin_note": "", "login": "admin",
    }, follow_redirects=False)
    with connect() as conn:
        row = conn.execute("SELECT * FROM freelancers WHERE id = ?", (fid,)).fetchone()
    assert row["name"] == "Пётр С."
    assert row["skills"] == "Vue"
    assert row["status"] == "approved"
    assert row["admin_note"] == "заметка студии"
    assert row["login"] == "petr"


# ============================================================
# Ход задачи
# ============================================================

def test_freelancer_cannot_finish_own_task(client):
    mine = make_freelancer("Пётр", login_name="petr", password="very-long-pass")
    _, tid = make_task(freelancer_id=mine, status="in_progress")
    answer = enter(client, "petr", "very-long-pass")
    client.post("/freelancer/tasks/%d/move" % tid,
                data={"csrf": csrf_of(answer.text), "status": "completed"},
                follow_redirects=False)
    with connect() as conn:
        assert conn.execute("SELECT status FROM tasks WHERE id = ?",
                            (tid,)).fetchone()[0] == "in_progress"


def test_full_task_cycle(client):
    mine = make_freelancer("Пётр", login_name="petr", password="very-long-pass")
    _, tid = make_task(freelancer_id=mine, status="assigned")

    answer = enter(client, "petr", "very-long-pass")
    fcsrf = csrf_of(answer.text)
    client.post("/freelancer/tasks/%d/move" % tid,
                data={"csrf": fcsrf, "status": "in_progress"}, follow_redirects=False)
    client.post("/freelancer/tasks/%d/submit" % tid,
                data={"csrf": fcsrf, "result_text": "Готово", "result_url": ""},
                follow_redirects=False)
    with connect() as conn:
        assert conn.execute("SELECT status FROM tasks WHERE id = ?",
                            (tid,)).fetchone()[0] == "review"

    acsrf = login(client)
    client.post("/admin/tasks/%d/move" % tid,
                data={"csrf": acsrf, "status": "revision", "comment": "поправить"},
                follow_redirects=False)
    with connect() as conn:
        assert conn.execute("SELECT status FROM tasks WHERE id = ?",
                            (tid,)).fetchone()[0] == "revision"
    client.post("/admin/tasks/%d/move" % tid,
                data={"csrf": acsrf, "status": "completed"}, follow_redirects=False)
    # из «на доработке» сразу в «завершена» нельзя
    with connect() as conn:
        assert conn.execute("SELECT status FROM tasks WHERE id = ?",
                            (tid,)).fetchone()[0] == "revision"


def test_history_records_every_move(client):
    mine = make_freelancer("Пётр", login_name="petr", password="very-long-pass")
    _, tid = make_task(freelancer_id=mine, status="assigned")
    answer = enter(client, "petr", "very-long-pass")
    client.post("/freelancer/tasks/%d/move" % tid,
                data={"csrf": csrf_of(answer.text), "status": "in_progress"},
                follow_redirects=False)
    with connect() as conn:
        rows = work.task_history(conn, tid)
    assert [r["to_status"] for r in rows] == ["assigned", "in_progress"]
    assert rows[-1]["actor"] == "Пётр"


# ============================================================
# Админка фриланса
# ============================================================

def test_admin_pages_need_login(client):
    for url in ("/admin/freelancers", "/admin/client-projects",
                "/admin/notifications", "/admin/log"):
        answer = client.get(url, follow_redirects=False)
        assert answer.status_code == 303, url


def test_task_cannot_be_moved_to_another_project(client):
    csrf = login(client)
    pid_a, tid = make_task(status="todo")
    with connect() as conn:
        pid_b = work.save_client_project(conn, None, {"title": "Чужой проект"})
        conn.commit()
    answer = client.post("/admin/tasks/save", data={
        "csrf": csrf, "id": str(tid), "project_id": str(pid_b), "title": "Подмена",
    }, follow_redirects=False)
    assert answer.status_code == 403
    with connect() as conn:
        assert conn.execute("SELECT project_id FROM tasks WHERE id = ?",
                            (tid,)).fetchone()[0] == pid_a


def test_unapproved_freelancer_cannot_be_assigned(client):
    csrf = login(client)
    stranger = make_freelancer("Новичок", status="new")
    with connect() as conn:
        pid = work.save_client_project(conn, None, {"title": "Проект"})
        conn.commit()
    client.post("/admin/tasks/save", data={
        "csrf": csrf, "project_id": str(pid), "title": "Задача",
        "freelancer_id": str(stranger),
    }, follow_redirects=False)
    with connect() as conn:
        assert conn.execute("SELECT freelancer_id FROM tasks").fetchone()[0] is None


def test_admin_actions_reach_the_log(client):
    csrf = login(client)
    fid = make_freelancer()
    client.post("/admin/freelancers/%d/status" % fid,
                data={"csrf": csrf, "status": "reviewing"}, follow_redirects=False)
    with connect() as conn:
        rows = conn.execute(
            "SELECT action, entity, entity_id FROM admin_log ORDER BY id"
        ).fetchall()
    actions = [r["action"] for r in rows]
    assert "LOGIN" in actions
    assert "FREELANCER_CHANGED" in actions


def test_log_holds_no_secrets(client):
    csrf = login(client)
    fid = make_freelancer(status="approved")
    client.post("/admin/freelancers/%d/access" % fid,
                data={"csrf": csrf, "login": "petr", "password": "secret-password-123"},
                follow_redirects=False)
    with connect() as conn:
        dump = " ".join(str(dict(r)) for r in conn.execute("SELECT * FROM admin_log"))
    assert "secret-password-123" not in dump
