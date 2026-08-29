"""
AVERIX — серверная часть.

Страницы отдаёт приложение, статику (стили, скрипты, шрифты,
загруженные картинки) — nginx напрямую.
"""
import asyncio
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import audit, journal, models, security
from .adminkit import (_ERRORS, back, current_session, error_page, guard,
                       insecure_page, page)
from .render import client_ip, is_secure, no_store, templates
from .uploads import UploadError, delete_image_file, save_image
from .config import (
    ALLOW_INSECURE,
    DEBUG,
    SECURE_COOKIES,
    SESSION_COOKIE,
    SESSION_HOURS,
)
from .db import connect, migrate

LOGIN_COOKIE = "averix_lc"          # одноразовый токен формы входа


@asynccontextmanager
async def lifespan(_: FastAPI):
    journal.setup(DEBUG)
    applied = migrate()
    if applied:
        journal.event("миграции.применены", files=", ".join(applied))
    with connect() as conn:
        security.purge_expired(conn)
        from . import work as _work
        _work.purge_freelancer_sessions(conn)
    journal.event("приложение.запущено")
    yield
    journal.event("приложение.остановлено")


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

from .routes_public import router as public_router  # noqa: E402  (после создания app)
from .routes_public import public_notfound  # noqa: E402
from .routes_admin_studio import router as studio_router  # noqa: E402
from .routes_admin_work import router as work_router  # noqa: E402
from .routes_freelancer import router as freelancer_router  # noqa: E402
app.include_router(public_router)
app.include_router(studio_router)
app.include_router(work_router)
app.include_router(freelancer_router)


# ---------- вспомогательное ----------

def set_cookie(resp: Response, name: str, value: str, max_age: int) -> None:
    resp.set_cookie(
        name, value,
        max_age=max_age, path="/",
        httponly=True, secure=SECURE_COOKIES, samesite="lax",
    )


# ---------- вход ----------

@app.get("/admin", response_class=HTMLResponse)
@app.get("/admin/", response_class=HTMLResponse)
async def admin_root(request: Request):
    if SECURE_COOKIES and not ALLOW_INSECURE and not is_secure(request):
        return insecure_page(request)
    session = current_session(request)
    if session is not None:
        return await dashboard(request)
    return login_page(request)


def login_page(request: Request, error: str | None = None, status: int = 200) -> Response:
    lc = secrets.token_urlsafe(24)
    resp = templates.TemplateResponse(
        request, "admin/login.html", {"error": error, "lc": lc}, status_code=status
    )
    set_cookie(resp, LOGIN_COOKIE, lc, 900)
    return no_store(resp)


@app.post("/admin/login", response_class=HTMLResponse)
async def admin_login(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    lc: str = Form(""),
):
    if SECURE_COOKIES and not ALLOW_INSECURE and not is_secure(request):
        return insecure_page(request)

    # Двойная отправка токена: форма и cookie должны совпасть.
    # Защищает от чужой формы, отправляющей вход на наш адрес.
    if not lc or lc != request.cookies.get(LOGIN_COOKIE, ""):
        return login_page(
            request,
            "Форма устарела или браузер не сохранил cookie. Обновите страницу.",
            400,
        )

    ip = client_ip(request)
    with connect() as conn:
        failures = security.recent_failures(conn, ip)
        if security.is_blocked(failures):
            journal.warn("вход.заблокирован", ip=ip, login=username, попыток=failures)
            return login_page(
                request,
                "Слишком много попыток. Подождите 15 минут.",
                429,
            )

        delay = security.login_delay(failures)
        row = conn.execute(
            "SELECT id, password_hash FROM admins WHERE username = ?", (username,)
        ).fetchone()

        ok = row is not None and security.verify_password(password, row["password_hash"])
        security.record_attempt(conn, ip, username, ok)

        if not ok:
            journal.warn("вход.неудача", ip=ip, login=username, попыток=failures + 1)
            if delay:
                await asyncio.sleep(delay)
            # Один и тот же текст для неверного логина и неверного пароля:
            # иначе по ответу можно узнать, какие логины существуют.
            return login_page(request, "Неверный логин или пароль.", 401)

        journal.event("вход.успех", ip=ip, login=username)
        conn.execute(
            "INSERT INTO admin_log (admin_id, username, action) VALUES (?, ?, 'LOGIN')",
            (row["id"], username),
        )
        token = security.create_session(
            conn, row["id"], ip, request.headers.get("user-agent", "")
        )

    resp = RedirectResponse("/admin", status_code=303)
    set_cookie(resp, SESSION_COOKIE, token, SESSION_HOURS * 3600)
    resp.delete_cookie(LOGIN_COOKIE, path="/")
    return no_store(resp)


@app.post("/admin/logout")
async def admin_logout(request: Request, csrf: str = Form("")):
    session = current_session(request)
    if not security.check_csrf(session, csrf):
        return no_store(RedirectResponse("/admin", status_code=303))
    with connect() as conn:
        audit.record(conn, session, "LOGOUT")
    journal.event("выход", login=session["username"])
    with connect() as conn:
        security.destroy_session(conn, request.cookies.get(SESSION_COOKIE))
    resp = RedirectResponse("/admin", status_code=303)
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return no_store(resp)


# ---------- панель ----------

async def dashboard(request: Request) -> Response:
    session = current_session(request)
    if session is None:
        return no_store(RedirectResponse("/admin", status_code=303))

    with connect() as conn:
        stats = models.dashboard_counts(conn)
        latest = conn.execute(
            "SELECT id, title_ru, status, created_at FROM projects"
            " ORDER BY created_at DESC LIMIT 5"
        ).fetchall()

    resp = templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        {
            "username": session["username"],
            "csrf": session["csrf_token"],
            "counts": stats,
            "latest": latest,
        },
    )
    return no_store(resp)


# ---------- проекты ----------

@app.get("/admin/projects", response_class=HTMLResponse)
async def projects_list(request: Request):
    session, stop = guard(request)
    if stop:
        return stop
    with connect() as conn:
        rows = models.list_projects(conn)
    return no_store(templates.TemplateResponse(request, "admin/projects.html", {
        "username": session["username"], "csrf": session["csrf_token"],
        "projects": rows, "categories": models.CATEGORIES,
    }))


@app.get("/admin/projects/new", response_class=HTMLResponse)
async def project_new(request: Request):
    session, stop = guard(request)
    if stop:
        return stop
    return no_store(templates.TemplateResponse(request, "admin/project_form.html", {
        "username": session["username"], "csrf": session["csrf_token"],
        "project": None, "images": [], "tech": "",
        "categories": models.CATEGORIES, "error": None,
    }))


@app.get("/admin/projects/{project_id}", response_class=HTMLResponse)
async def project_edit(request: Request, project_id: int):
    session, stop = guard(request)
    if stop:
        return stop
    with connect() as conn:
        project = models.get_project(conn, project_id)
        if project is None:
            # молчаливый переброс на список скрывал бы опечатку в адресе
            return error_page(request, 404)
        imgs = models.images(conn, project_id)
        stack = ", ".join(models.tech(conn, project_id))
    return no_store(templates.TemplateResponse(request, "admin/project_form.html", {
        "username": session["username"], "csrf": session["csrf_token"],
        "project": project, "images": imgs, "tech": stack,
        "categories": models.CATEGORIES, "error": None,
    }))


@app.post("/admin/projects/save")
async def project_save(request: Request):
    session, stop = guard(request)
    if stop:
        return stop
    form = await request.form()
    if not security.check_csrf(session, form.get("csrf")):
        return back()

    def val(name: str, limit: int = 4000) -> str:
        return (str(form.get(name, "")).strip())[:limit]

    title = val("title_ru", 200)
    if not title:
        return back("/admin/projects/new")

    category = val("category", 40)
    if category not in models.CATEGORIES:
        category = "web"

    year_raw = val("year", 4)
    year = int(year_raw) if year_raw.isdigit() and 2000 <= int(year_raw) <= 2100 else None

    data = {f: val(f) for f in models.TEXT_FIELDS}
    data["title_ru"] = title
    data["category"] = category
    data["year"] = year
    data["featured"] = 1 if form.get("featured") else 0
    data["status"] = "published" if form.get("status") == "published" else "draft"
    data["sort_order"] = 0

    raw_id = str(form.get("id", "")).strip()
    project_id = int(raw_id) if raw_id.isdigit() else None

    with connect() as conn:
        base = models.slugify(val("slug", 100) or title)
        data["slug"] = models.unique_slug(conn, base, project_id)
        if project_id is not None:
            if models.get_project(conn, project_id) is None:
                return back()
            existing = models.get_project(conn, project_id)
            data["sort_order"] = existing["sort_order"]
            models.update_project(conn, project_id, data)
        else:
            project_id = models.create_project(conn, data)
        models.set_tech(conn, project_id, val("tech", 500))
        audit.record(conn, session,
                     "PROJECT_UPDATED" if form.get("id") else "PROJECT_CREATED",
                     "projects", project_id, data["slug"])

    journal.event("проект.сохранён", id=project_id, slug=data["slug"],
                  статус=data["status"], кем=session["username"])
    return back(f"/admin/projects/{project_id}")


@app.post("/admin/projects/{project_id}/delete")
async def project_delete(request: Request, project_id: int, csrf: str = Form("")):
    session, stop = guard(request)
    if stop:
        return stop
    if not security.check_csrf(session, csrf):
        return back()
    with connect() as conn:
        files = models.delete_project(conn, project_id)
        audit.record(conn, session, "PROJECT_DELETED", "projects", project_id)
    for name in files:
        delete_image_file(name)
    journal.warn("проект.удалён", id=project_id, картинок=len(files),
                 кем=session["username"])
    return back()


@app.post("/admin/projects/{project_id}/toggle")
async def project_toggle(
    request: Request, project_id: int, field: str = Form(""), csrf: str = Form("")
):
    session, stop = guard(request)
    if stop:
        return stop
    if not security.check_csrf(session, csrf):
        return back()
    with connect() as conn:
        project = models.get_project(conn, project_id)
        if project is None:
            return back()
        if field == "featured":
            conn.execute("UPDATE projects SET featured = ? WHERE id = ?",
                         (0 if project["featured"] else 1, project_id))
        elif field == "status":
            new = "draft" if project["status"] == "published" else "published"
            conn.execute("UPDATE projects SET status = ? WHERE id = ?", (new, project_id))
            audit.record(conn, session, "PROJECT_UPDATED", "projects", project_id,
                         f"статус: {new}")
            journal.event("проект.статус", id=project_id, стал=new, кем=session["username"])
    return back()


@app.post("/admin/projects/{project_id}/move")
async def project_move(
    request: Request, project_id: int, direction: str = Form("up"), csrf: str = Form("")
):
    session, stop = guard(request)
    if stop:
        return stop
    if not security.check_csrf(session, csrf):
        return back()
    with connect() as conn:
        models.move_project(conn, project_id, -1 if direction == "up" else 1)
    return back()


# ---------- картинки ----------

@app.post("/admin/projects/{project_id}/images")
async def image_upload(request: Request, project_id: int):
    session, stop = guard(request)
    if stop:
        return stop
    form = await request.form()
    if not security.check_csrf(session, form.get("csrf")):
        return back()

    upload = form.get("image")
    if upload is None or not hasattr(upload, "read"):
        return back(f"/admin/projects/{project_id}")

    raw = await upload.read()
    try:
        saved = save_image(raw, getattr(upload, "filename", ""))
    except UploadError as exc:
        journal.warn("картинка.отклонена", проект=project_id, причина=str(exc),
                     кем=session["username"])
        with connect() as conn:
            project = models.get_project(conn, project_id)
            imgs = models.images(conn, project_id)
            stack = ", ".join(models.tech(conn, project_id))
        if project is None:
            return back()
        return no_store(templates.TemplateResponse(request, "admin/project_form.html", {
            "username": session["username"], "csrf": session["csrf_token"],
            "project": project, "images": imgs, "tech": stack,
            "categories": models.CATEGORIES, "error": str(exc),
        }, status_code=400))

    with connect() as conn:
        if models.get_project(conn, project_id) is None:
            delete_image_file(saved.filename)
            return back()
        models.add_image(conn, project_id, saved,
                         str(form.get("alt_ru", ""))[:200])
    journal.event("картинка.загружена", проект=project_id, файл=saved.filename,
                  размер=f"{saved.width}x{saved.height}", кем=session["username"])
    return back(f"/admin/projects/{project_id}")


@app.post("/admin/projects/{project_id}/cover")
async def image_cover(
    request: Request, project_id: int, image_id: int = Form(0), csrf: str = Form("")
):
    session, stop = guard(request)
    if stop:
        return stop
    if not security.check_csrf(session, csrf):
        return back()
    with connect() as conn:
        models.set_cover(conn, project_id, image_id)
    return back(f"/admin/projects/{project_id}")


@app.post("/admin/projects/{project_id}/images/{image_id}/delete")
async def image_delete(
    request: Request, project_id: int, image_id: int, csrf: str = Form("")
):
    session, stop = guard(request)
    if stop:
        return stop
    if not security.check_csrf(session, csrf):
        return back()
    with connect() as conn:
        # картинка обязана принадлежать этому проекту: иначе по чужому id
        # можно было бы удалить снимок из другого кейса
        row = conn.execute(
            "SELECT id FROM project_images WHERE id = ? AND project_id = ?",
            (image_id, project_id),
        ).fetchone()
        if row is None:
            return back(f"/admin/projects/{project_id}")
        filename = models.delete_image(conn, image_id)
    if filename:
        delete_image_file(filename)
        journal.event("картинка.удалена", проект=project_id, файл=filename,
                      кем=session["username"])
    return back(f"/admin/projects/{project_id}")


# ---------- служебное ----------

@app.get("/admin/health")
async def health():
    with connect() as conn:
        conn.execute("SELECT 1")
    return {"ok": True}


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    # На сайте и в админке ошибка выглядит по-разному: посетителю нужна
    # страница в стиле сайта со ссылками на проекты, а не служебная плашка
    if exc.status_code == 404 and not request.url.path.startswith("/admin"):
        return public_notfound(request)
    if exc.status_code in _ERRORS:
        return error_page(request, exc.status_code)
    return HTMLResponse(f"Ошибка {exc.status_code}", status_code=exc.status_code)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    # Наружу не уходит ни трассировка, ни текст ошибки — только в журнал
    journal.error("ошибка.необработанная", путь=request.url.path,
                  тип=type(exc).__name__)
    if DEBUG:
        raise exc
    return error_page(request, 500)
