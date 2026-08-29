"""
Админка: специалисты, клиентские проекты, задачи, уведомления и журнал.

Всё, что здесь есть, живёт внутри студии и наружу не показывается.
Каждый маршрут начинается с guard(): без действующей сессии дальше
первой строки дело не идёт, и проверка эта серверная — скрытая
кнопка в шаблоне защитой не считается.
"""
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from . import audit, journal, models, notify, security, work
from .adminkit import back, error_page, guard, page
from .db import connect

router = APIRouter(prefix="/admin")


def _val(form, name: str, limit: int = 4000) -> str:
    return str(form.get(name, "")).strip()[:limit]


# В истории задачи админ подписан студией, а не своим логином: эту
# историю видит и фрилансер, а логин админа — половина доступа к панели.
# Кто именно нажал кнопку, остаётся в журнале действий.
ADMIN_ACTOR = "AVERIX"


def _int(form, name: str) -> int | None:
    raw = _val(form, name, 12)
    return int(raw) if raw.lstrip("-").isdigit() else None


# ============================================================
# Специалисты
# ============================================================

@router.get("/freelancers", response_class=HTMLResponse)
async def freelancers_list(request: Request, status: str = ""):
    session, stop = guard(request)
    if stop:
        return stop
    with connect() as conn:
        rows = work.list_freelancers(conn, status)
        counts = {k: 0 for k in work.FREELANCER_STATUSES}
        for r in conn.execute("SELECT status, COUNT(*) n FROM freelancers GROUP BY status"):
            counts[r["status"]] = r["n"]
    return page(request, session, "admin/freelancers.html",
                people=rows, active=status, counts=counts,
                statuses=work.FREELANCER_STATUSES,
                specializations=work.SPECIALIZATIONS,
                availability=work.AVAILABILITY,
                rate_types=work.RATE_TYPES)


@router.get("/freelancers/{freelancer_id}", response_class=HTMLResponse)
async def freelancer_card(request: Request, freelancer_id: int, error: str = ""):
    session, stop = guard(request)
    if stop:
        return stop
    with connect() as conn:
        row = work.get_freelancer(conn, freelancer_id)
        if row is None:
            return error_page(request, 404)
        tasks = conn.execute(
            "SELECT t.*, p.title AS project_title FROM tasks t"
            " JOIN client_projects p ON p.id = t.project_id"
            " WHERE t.freelancer_id = ? ORDER BY t.updated_at DESC",
            (freelancer_id,),
        ).fetchall()
    return page(request, session, "admin/freelancer_card.html",
                person=row, tasks=tasks, error=error,
                statuses=work.FREELANCER_STATUSES,
                specializations=work.SPECIALIZATIONS,
                availability=work.AVAILABILITY,
                rate_types=work.RATE_TYPES,
                task_statuses=work.TASK_STATUSES,
                can_log_in=work.CAN_LOG_IN)


@router.post("/freelancers/{freelancer_id}/status")
async def freelancer_status(request: Request, freelancer_id: int):
    session, stop = guard(request)
    if stop:
        return stop
    form = await request.form()
    if not security.check_csrf(session, form.get("csrf")):
        return back("/admin/freelancers")
    status = _val(form, "status", 20)
    with connect() as conn:
        if not work.set_freelancer_status(conn, freelancer_id, status,
                                          _val(form, "admin_note", 2000)):
            return error_page(request, 404)
        audit.record(conn, session, "FREELANCER_CHANGED", "freelancers",
                     freelancer_id, f"статус: {status}")
    journal.event("специалист.статус", id=freelancer_id, кто=session["username"])
    return back(f"/admin/freelancers/{freelancer_id}")


@router.post("/freelancers/{freelancer_id}/save")
async def freelancer_save(request: Request, freelancer_id: int):
    session, stop = guard(request)
    if stop:
        return stop
    form = await request.form()
    if not security.check_csrf(session, form.get("csrf")):
        return back("/admin/freelancers")
    with connect() as conn:
        current = work.get_freelancer(conn, freelancer_id)
        if current is None:
            return error_page(request, 404)
        work.save_freelancer(conn, freelancer_id, {
            "name": _val(form, "name", 100) or current["name"],
            "telegram": _val(form, "telegram", 120),
            "email": _val(form, "email", 120),
            "country": _val(form, "country", 80),
            "city": _val(form, "city", 80),
            "specialization": _val(form, "specialization", 40),
            "skills": _val(form, "skills", 500),
            "experience": _val(form, "experience", 500),
            "years": _val(form, "years", 40),
            "about": _val(form, "about", 3000),
            "portfolio_url": _val(form, "portfolio_url", 300),
            "github_url": _val(form, "github_url", 300),
            "cv_file": current["cv_file"],
            "photo": current["photo"],
            "rate": _val(form, "rate", 80),
            "rate_type": _val(form, "rate_type", 20),
            "availability": _val(form, "availability", 20),
            "status": _val(form, "status", 20) or current["status"],
            "admin_note": _val(form, "admin_note", 2000),
            # Логин меняется отдельной формой: случайная правка карточки
            # не должна отбирать у человека доступ в кабинет
            "login": current["login"],
        })
        audit.record(conn, session, "FREELANCER_CHANGED", "freelancers", freelancer_id)
    return back(f"/admin/freelancers/{freelancer_id}")


@router.post("/freelancers/{freelancer_id}/access")
async def freelancer_access(request: Request, freelancer_id: int):
    """Выдаёт вход в кабинет. Пароль задаёт админ и передаёт лично."""
    session, stop = guard(request)
    if stop:
        return stop
    form = await request.form()
    if not security.check_csrf(session, form.get("csrf")):
        return back("/admin/freelancers")
    with connect() as conn:
        problem = work.set_freelancer_login(
            conn, freelancer_id, _val(form, "login", 60), _val(form, "password", 200)
        )
        if problem:
            # Пароль в адрес не попадает — только текст ошибки
            return back(f"/admin/freelancers/{freelancer_id}?error={problem}")
        audit.record(conn, session, "FREELANCER_CHANGED", "freelancers",
                     freelancer_id, "выдан доступ в кабинет")
    journal.event("специалист.доступ", id=freelancer_id, кто=session["username"])
    return back(f"/admin/freelancers/{freelancer_id}")


@router.post("/freelancers/{freelancer_id}/delete")
async def freelancer_delete(request: Request, freelancer_id: int, csrf: str = Form("")):
    session, stop = guard(request)
    if stop:
        return stop
    if not security.check_csrf(session, csrf):
        return back("/admin/freelancers")
    with connect() as conn:
        conn.execute("DELETE FROM freelancers WHERE id = ?", (freelancer_id,))
        audit.record(conn, session, "FREELANCER_CHANGED", "freelancers",
                     freelancer_id, "анкета удалена")
    return back("/admin/freelancers")


# ============================================================
# Клиентские проекты
# ============================================================

@router.get("/client-projects", response_class=HTMLResponse)
async def client_projects(request: Request):
    session, stop = guard(request)
    if stop:
        return stop
    with connect() as conn:
        rows = work.list_client_projects(conn)
    return page(request, session, "admin/client_projects.html",
                projects=rows, statuses=work.CLIENT_PROJECT_STATUSES)


@router.get("/client-projects/new", response_class=HTMLResponse)
async def client_project_new(request: Request):
    session, stop = guard(request)
    if stop:
        return stop
    return page(request, session, "admin/client_project_form.html",
                project=None, tasks=[], people=[],
                statuses=work.CLIENT_PROJECT_STATUSES,
                task_statuses=work.TASK_STATUSES,
                specializations=work.SPECIALIZATIONS)


@router.get("/client-projects/{project_id}", response_class=HTMLResponse)
async def client_project_edit(request: Request, project_id: int):
    session, stop = guard(request)
    if stop:
        return stop
    with connect() as conn:
        row = work.get_client_project(conn, project_id)
        if row is None:
            return error_page(request, 404)
        tasks = work.project_tasks(conn, project_id)
        people = work.approved_freelancers(conn)
    return page(request, session, "admin/client_project_form.html",
                project=row, tasks=tasks, people=people,
                statuses=work.CLIENT_PROJECT_STATUSES,
                task_statuses=work.TASK_STATUSES,
                specializations=work.SPECIALIZATIONS)


@router.post("/client-projects/save")
async def client_project_save(request: Request):
    session, stop = guard(request)
    if stop:
        return stop
    form = await request.form()
    if not security.check_csrf(session, form.get("csrf")):
        return back("/admin/client-projects")
    title = _val(form, "title", 200)
    if not title:
        return back("/admin/client-projects/new")
    project_id = _int(form, "id")
    with connect() as conn:
        project_id = work.save_client_project(conn, project_id, {
            "title": title,
            "client": _val(form, "client", 200),
            "description": _val(form, "description", 4000),
            "budget": _val(form, "budget", 120),
            "deadline": _val(form, "deadline", 40),
            "status": _val(form, "status", 20),
            "admin_note": _val(form, "admin_note", 2000),
        })
        audit.record(conn, session, "CLIENT_PROJECT_CHANGED", "client_projects", project_id)
    return back(f"/admin/client-projects/{project_id}")


@router.post("/client-projects/{project_id}/delete")
async def client_project_delete(request: Request, project_id: int, csrf: str = Form("")):
    session, stop = guard(request)
    if stop:
        return stop
    if not security.check_csrf(session, csrf):
        return back("/admin/client-projects")
    with connect() as conn:
        work.delete_client_project(conn, project_id)
        audit.record(conn, session, "CLIENT_PROJECT_CHANGED", "client_projects",
                     project_id, "проект удалён вместе с задачами")
    return back("/admin/client-projects")


# ============================================================
# Задачи
# ============================================================

@router.post("/tasks/save")
async def task_save(request: Request):
    session, stop = guard(request)
    if stop:
        return stop
    form = await request.form()
    if not security.check_csrf(session, form.get("csrf")):
        return back("/admin/client-projects")

    project_id = _int(form, "project_id")
    title = _val(form, "title", 200)
    if project_id is None or not title:
        return back("/admin/client-projects")

    task_id = _int(form, "id")
    assignee = _int(form, "freelancer_id")

    with connect() as conn:
        if work.get_client_project(conn, project_id) is None:
            return error_page(request, 404)
        if assignee is not None:
            person = work.get_freelancer(conn, assignee)
            # Назначать можно только одобренного: иначе задача уйдёт
            # человеку, которого ещё никто не смотрел
            if person is None or person["status"] not in work.CAN_LOG_IN:
                assignee = None

        current = work.get_task(conn, task_id) if task_id else None
        if current is not None and current["project_id"] != project_id:
            # Задачу нельзя перекинуть в чужой проект подменой поля в форме
            return error_page(request, 403)

        status = _val(form, "status", 20)
        if current is None:
            status = "assigned" if assignee else "todo"
        else:
            status = current["status"]

        task_id = work.save_task(conn, task_id, {
            "project_id": project_id,
            "title": title,
            "description": _val(form, "description", 4000),
            "specialization": _val(form, "specialization", 40),
            "skills": _val(form, "skills", 500),
            "deadline": _val(form, "deadline", 40),
            "price": _val(form, "price", 80),
            "status": status,
            "freelancer_id": assignee,
            "admin_note": _val(form, "admin_note", 2000),
            "sort_order": _int(form, "sort_order") or 0,
            "actor": ADMIN_ACTOR,
        })
        if current is not None and current["freelancer_id"] != assignee:
            work.log_task(conn, task_id, current["status"], current["status"],
                          ADMIN_ACTOR,
                          "исполнитель назначен" if assignee else "исполнитель снят")
            if assignee and current["status"] == "todo":
                work.move_task(conn, task_id, "assigned", by_admin=True,
                               actor=ADMIN_ACTOR)
        audit.record(conn, session, "TASK_CHANGED", "tasks", task_id)
    return back(f"/admin/client-projects/{project_id}")


@router.post("/tasks/{task_id}/move")
async def task_move(request: Request, task_id: int):
    session, stop = guard(request)
    if stop:
        return stop
    form = await request.form()
    if not security.check_csrf(session, form.get("csrf")):
        return back("/admin/client-projects")
    with connect() as conn:
        row = work.get_task(conn, task_id)
        if row is None:
            return error_page(request, 404)
        problem = work.move_task(conn, task_id, _val(form, "status", 20),
                                 by_admin=True, actor=ADMIN_ACTOR,
                                 comment=_val(form, "comment", 500))
        if problem is None:
            audit.record(conn, session, "TASK_CHANGED", "tasks", task_id,
                         _val(form, "status", 20))
        project_id = row["project_id"]
    return back(f"/admin/client-projects/{project_id}")


@router.post("/tasks/{task_id}/delete")
async def task_delete(request: Request, task_id: int, csrf: str = Form("")):
    session, stop = guard(request)
    if stop:
        return stop
    if not security.check_csrf(session, csrf):
        return back("/admin/client-projects")
    with connect() as conn:
        row = work.get_task(conn, task_id)
        if row is None:
            return error_page(request, 404)
        project_id = row["project_id"]
        work.delete_task(conn, task_id)
        audit.record(conn, session, "TASK_CHANGED", "tasks", task_id, "задача удалена")
    return back(f"/admin/client-projects/{project_id}")


@router.get("/tasks/{task_id}", response_class=HTMLResponse)
async def task_card(request: Request, task_id: int):
    session, stop = guard(request)
    if stop:
        return stop
    with connect() as conn:
        row = work.get_task(conn, task_id)
        if row is None:
            return error_page(request, 404)
        history = work.task_history(conn, task_id)
        people = work.approved_freelancers(conn)
    return page(request, session, "admin/task_card.html",
                task=row, history=history, people=people,
                statuses=work.TASK_STATUSES,
                moves=work.ADMIN_MOVES.get(row["status"], ()),
                specializations=work.SPECIALIZATIONS)


# ============================================================
# Уведомления и журнал
# ============================================================

@router.get("/notifications", response_class=HTMLResponse)
async def notifications(request: Request):
    session, stop = guard(request)
    if stop:
        return stop
    with connect() as conn:
        rows = notify.recent(conn, 50)
        notify.mark_all_seen(conn)
    return page(request, session, "admin/notifications.html", items=rows)


@router.get("/log", response_class=HTMLResponse)
async def admin_log(request: Request):
    session, stop = guard(request)
    if stop:
        return stop
    with connect() as conn:
        rows = audit.recent(conn, 200)
    return page(request, session, "admin/log.html", items=rows)
