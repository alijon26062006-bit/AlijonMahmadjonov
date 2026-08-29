"""
Кабинет фрилансера.

Отдельная роль со своим входом. Здесь нет и не должно быть ничего
из админки: ни списка других специалистов, ни чужих задач, ни данных
заказчика, ни настроек сайта.

Главный принцип: выборка по владельцу стоит в самом SQL-запросе,
а не в проверке после. Тогда чужая задача не покажется даже при
ошибке в шаблоне — её просто не будет в данных.
"""
import asyncio
import secrets

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from . import journal, security, work
from .config import ALLOW_INSECURE, SECURE_COOKIES
from .db import connect
from .render import client_ip, is_secure, no_store, templates

router = APIRouter(prefix="/freelancer")

SESSION_COOKIE = "averix_worker"
LOGIN_COOKIE = "averix_wlc"


def _set_cookie(resp: Response, name: str, value: str, max_age: int) -> None:
    resp.set_cookie(name, value, max_age=max_age, path="/",
                    httponly=True, secure=SECURE_COOKIES, samesite="lax")


def current(request: Request):
    with connect() as conn:
        return work.get_freelancer_session(conn, request.cookies.get(SESSION_COOKIE))


def guard(request: Request):
    """(сессия, None) либо (None, ответ). Проверка серверная и обязательная."""
    if SECURE_COOKIES and not ALLOW_INSECURE and not is_secure(request):
        from .adminkit import insecure_page
        return None, insecure_page(request)
    session = current(request)
    if session is None:
        return None, no_store(RedirectResponse("/freelancer/login", status_code=303))
    return session, None


def _page(request: Request, session, template: str, **ctx) -> Response:
    data = {
        "me": session,
        "csrf": session["csrf_token"],
        "statuses": work.TASK_STATUSES,
        "availability": work.AVAILABILITY,
    }
    data.update(ctx)
    return no_store(templates.TemplateResponse(request, template, data))


# ============================================================
# Вход
# ============================================================

@router.get("/login", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def login_form(request: Request, error: str = ""):
    if SECURE_COOKIES and not ALLOW_INSECURE and not is_secure(request):
        from .adminkit import insecure_page
        return insecure_page(request)
    if current(request) is not None:
        return no_store(RedirectResponse("/freelancer/dashboard", status_code=303))

    lc = secrets.token_urlsafe(24)
    resp = templates.TemplateResponse(request, "freelancer/login.html",
                                      {"lc": lc, "error": error or None})
    _set_cookie(resp, LOGIN_COOKIE, lc, 900)
    return no_store(resp)


@router.post("/login", response_class=HTMLResponse)
async def login(request: Request, login: str = Form(""), password: str = Form(""),
                lc: str = Form("")):
    if SECURE_COOKIES and not ALLOW_INSECURE and not is_secure(request):
        from .adminkit import insecure_page
        return insecure_page(request)

    # Двойная отправка формы: значение из cookie должно совпасть с полем
    sent = request.cookies.get(LOGIN_COOKIE, "")
    if not sent or not lc or not security.check_csrf({"csrf_token": sent}, lc):
        return await login_form(request, error="Форма устарела. Попробуйте ещё раз.")

    ip = client_ip(request)
    with connect() as conn:
        # Счётчик неудач общий с админкой: перебор — это перебор,
        # с какой бы формы его ни вели
        failures = security.recent_failures(conn, ip)
        if security.is_blocked(failures):
            journal.warn("кабинет.вход.блок", ip=ip)
            return await login_form(request,
                                    error="Слишком много попыток. Подождите 15 минут.")
        delay = security.login_delay(failures)
        row = work.freelancer_login(conn, login, password)
        security.record_attempt(conn, ip, login, row is not None)
        if row is None:
            journal.warn("кабинет.вход.неудача", ip=ip)
            if delay:
                await asyncio.sleep(delay)
            # Один текст на все случаи: иначе по ответу видно,
            # какие логины существуют и кто из них одобрен
            return await login_form(request, error="Неверный логин или пароль.")
        token = work.create_freelancer_session(conn, row["id"])
        journal.event("кабинет.вход", id=row["id"], ip=ip)

    resp = RedirectResponse("/freelancer/dashboard", status_code=303)
    _set_cookie(resp, SESSION_COOKIE, token, work.SESSION_HOURS * 3600)
    resp.delete_cookie(LOGIN_COOKIE, path="/")
    return no_store(resp)


@router.post("/logout")
async def logout(request: Request, csrf: str = Form("")):
    session = current(request)
    if not security.check_csrf(session, csrf):
        return no_store(RedirectResponse("/freelancer/dashboard", status_code=303))
    with connect() as conn:
        work.destroy_freelancer_session(conn, request.cookies.get(SESSION_COOKIE))
    resp = RedirectResponse("/freelancer/login", status_code=303)
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return no_store(resp)


# ============================================================
# Кабинет
# ============================================================

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, error: str = ""):
    session, stop = guard(request)
    if stop:
        return stop
    with connect() as conn:
        tasks = work.freelancer_tasks(conn, session["id"])
    counts = {
        "active": sum(1 for t in tasks if t["status"] in
                      ("assigned", "in_progress", "revision")),
        "review": sum(1 for t in tasks if t["status"] == "review"),
        "done": sum(1 for t in tasks if t["status"] == "completed"),
    }
    return _page(request, session, "freelancer/dashboard.html",
                 tasks=tasks, counts=counts, error=error or None)


@router.get("/tasks/{task_id}", response_class=HTMLResponse)
async def task(request: Request, task_id: int, error: str = ""):
    session, stop = guard(request)
    if stop:
        return stop
    with connect() as conn:
        # Владелец в запросе: чужой номер просто не найдётся
        row = work.freelancer_task(conn, task_id, session["id"])
        if row is None:
            return no_store(templates.TemplateResponse(
                request, "freelancer/notfound.html",
                {"me": session, "csrf": session["csrf_token"]}, status_code=404))
        history = work.task_history(conn, task_id)
    return _page(request, session, "freelancer/task.html",
                 task=row, history=history, error=error or None,
                 moves=work.FREELANCER_MOVES.get(row["status"], ()))


@router.post("/tasks/{task_id}/move")
async def task_move(request: Request, task_id: int):
    session, stop = guard(request)
    if stop:
        return stop
    form = await request.form()
    if not security.check_csrf(session, form.get("csrf")):
        return no_store(RedirectResponse("/freelancer/dashboard", status_code=303))
    with connect() as conn:
        problem = work.move_task(
            conn, task_id, str(form.get("status", ""))[:20],
            by_admin=False, actor=session["name"],
            freelancer_id=session["id"],
        )
    where = f"/freelancer/tasks/{task_id}"
    if problem:
        return no_store(RedirectResponse(f"{where}?error={problem}", status_code=303))
    return no_store(RedirectResponse(where, status_code=303))


@router.post("/tasks/{task_id}/submit")
async def task_submit(request: Request, task_id: int):
    session, stop = guard(request)
    if stop:
        return stop
    form = await request.form()
    if not security.check_csrf(session, form.get("csrf")):
        return no_store(RedirectResponse("/freelancer/dashboard", status_code=303))
    with connect() as conn:
        problem = work.submit_result(
            conn, task_id, session["id"],
            str(form.get("result_text", ""))[:4000],
            str(form.get("result_url", ""))[:500],
            session["name"],
        )
    where = f"/freelancer/tasks/{task_id}"
    if problem:
        return no_store(RedirectResponse(f"{where}?error={problem}", status_code=303))
    journal.event("кабинет.результат", задача=task_id, кто=session["id"])
    return no_store(RedirectResponse(where, status_code=303))


@router.get("/profile", response_class=HTMLResponse)
async def profile(request: Request, saved: str = ""):
    session, stop = guard(request)
    if stop:
        return stop
    return _page(request, session, "freelancer/profile.html",
                 specializations=work.SPECIALIZATIONS,
                 rate_types=work.RATE_TYPES,
                 saved=saved == "1")


@router.post("/profile")
async def profile_save(request: Request):
    """
    Человек правит только своё и только то, что можно доверить ему.

    Статус, логин и заметки админа сюда не входят: иначе одобрение
    себе можно было бы поставить самому.
    """
    session, stop = guard(request)
    if stop:
        return stop
    form = await request.form()
    if not security.check_csrf(session, form.get("csrf")):
        return no_store(RedirectResponse("/freelancer/profile", status_code=303))

    def val(name: str, limit: int = 500) -> str:
        return str(form.get(name, "")).strip()[:limit]

    with connect() as conn:
        row = work.get_freelancer(conn, session["id"])
        work.save_freelancer(conn, session["id"], {
            "name": val("name", 100) or row["name"],
            "telegram": val("telegram", 120),
            "email": val("email", 120),
            "country": val("country", 80),
            "city": val("city", 80),
            "specialization": val("specialization", 40),
            "skills": val("skills", 500),
            "experience": val("experience", 500),
            "years": val("years", 40),
            "about": val("about", 3000),
            "portfolio_url": val("portfolio_url", 300),
            "github_url": val("github_url", 300),
            "rate": val("rate", 80),
            "rate_type": val("rate_type", 20),
            "availability": val("availability", 20),
            # Дальше — поля, которые принадлежат студии, а не человеку
            "cv_file": row["cv_file"],
            "photo": row["photo"],
            "status": row["status"],
            "admin_note": row["admin_note"],
            "login": row["login"],
        })
    return no_store(RedirectResponse("/freelancer/profile?saved=1", status_code=303))
