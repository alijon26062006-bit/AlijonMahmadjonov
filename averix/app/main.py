"""
AVERIX — серверная часть.

Пока обслуживает только админку: публичный сайт продолжает отдаваться
nginx как статика и этими маршрутами не затрагивается.
"""
import asyncio
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from . import security
from .config import (
    BASE_DIR,
    DEBUG,
    SECURE_COOKIES,
    SESSION_COOKIE,
    SESSION_HOURS,
)
from .db import connect, migrate

LOGIN_COOKIE = "averix_lc"          # одноразовый токен формы входа
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@asynccontextmanager
async def lifespan(_: FastAPI):
    applied = migrate()
    if applied:
        print("Применены миграции:", ", ".join(applied))
    with connect() as conn:
        security.purge_expired(conn)
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


# ---------- вспомогательное ----------

def client_ip(request: Request) -> str:
    """
    За nginx настоящий адрес приходит в X-Forwarded-For. Берём последний
    элемент — его подставляет наш собственный прокси, и подделать его
    клиент не может, в отличие от первого.
    """
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[-1].strip()[:64]
    return (request.client.host if request.client else "?")[:64]


def set_cookie(resp: Response, name: str, value: str, max_age: int) -> None:
    resp.set_cookie(
        name, value,
        max_age=max_age, path="/",
        httponly=True, secure=SECURE_COOKIES, samesite="lax",
    )


def current_session(request: Request):
    with connect() as conn:
        return security.get_session(conn, request.cookies.get(SESSION_COOKIE))


def no_store(resp: Response) -> Response:
    resp.headers["Cache-Control"] = "no-store"
    return resp


# ---------- вход ----------

@app.get("/admin", response_class=HTMLResponse)
@app.get("/admin/", response_class=HTMLResponse)
async def admin_root(request: Request):
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
    # Двойная отправка токена: форма и cookie должны совпасть.
    # Защищает от чужой формы, отправляющей вход на наш адрес.
    if not lc or lc != request.cookies.get(LOGIN_COOKIE, ""):
        return login_page(request, "Форма устарела. Попробуйте ещё раз.", 400)

    ip = client_ip(request)
    with connect() as conn:
        failures = security.recent_failures(conn, ip)
        if security.is_blocked(failures):
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
            if delay:
                await asyncio.sleep(delay)
            # Один и тот же текст для неверного логина и неверного пароля:
            # иначе по ответу можно узнать, какие логины существуют.
            return login_page(request, "Неверный логин или пароль.", 401)

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
        counts = conn.execute(
            "SELECT"
            " COUNT(*) AS total,"
            " SUM(status = 'published') AS published,"
            " SUM(status = 'draft') AS draft"
            " FROM projects"
        ).fetchone()
        latest = conn.execute(
            "SELECT title_ru, status, created_at FROM projects"
            " ORDER BY created_at DESC LIMIT 5"
        ).fetchall()

    resp = templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        {
            "username": session["username"],
            "csrf": session["csrf_token"],
            "counts": {
                "total": counts["total"] or 0,
                "published": counts["published"] or 0,
                "draft": counts["draft"] or 0,
            },
            "latest": latest,
        },
    )
    return no_store(resp)


# ---------- служебное ----------

@app.get("/admin/health")
async def health():
    with connect() as conn:
        conn.execute("SELECT 1")
    return {"ok": True}


if not DEBUG:
    @app.exception_handler(500)
    async def server_error(_request: Request, _exc):
        # Наружу не уходит ни трассировка, ни текст ошибки
        return HTMLResponse("Внутренняя ошибка сервера", status_code=500)
