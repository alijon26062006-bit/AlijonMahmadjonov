"""
AVERIX Freelance — вход в площадку.

Регистрация, вход, выход, подтверждение почты, восстановление пароля
и выбор роли. Всё остальное (проекты, отклики, контракты, переписка)
живёт в отдельных модулях и подключается по мере готовности.

Три правила, общие для всего маркетплейса:

  * проверка прав серверная и стоит первой строкой маршрута;
  * ответ формы не выдаёт, есть ли такой адрес в базе;
  * после входа переходим только по своему адресу — параметр next
    проверяется, иначе он превращается в открытый редирект.
"""
import asyncio
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from . import accounts, journal, mailer, security
from .adminkit import insecure_page
from .config import ALLOW_INSECURE, SECURE_COOKIES, SITE_URL
from .db import connect
from .render import client_ip, is_secure, no_store, templates

router = APIRouter(prefix="/freelance")

# Одноразовый токен формы входа и регистрации: сессии ещё нет,
# поэтому CSRF проверяем совпадением поля формы и cookie.
FORM_COOKIE = "averix_flc"

# Разделы в шапке. Список пополняется вместе с готовыми разделами:
# ссылка на страницу, которой ещё нет, — это сломанная ссылка,
# а не обещание.
NAV: list[dict] = [
    {"key": "specialists", "url": "/freelance/specialists", "label": "Специалисты"},
]


def _set_cookie(resp: Response, name: str, value: str, max_age: int) -> None:
    resp.set_cookie(name, value, max_age=max_age, path="/",
                    httponly=True, secure=SECURE_COOKIES, samesite="lax")


def current(request: Request):
    with connect() as conn:
        return accounts.get_session(conn, request.cookies.get(accounts.SESSION_COOKIE))


def _http_stop(request: Request) -> Response | None:
    """По http пароль уходит открытым текстом, и cookie с флагом Secure
    браузер не сохранит. Говорим об этом прямо, а не «форма устарела»."""
    if SECURE_COOKIES and not ALLOW_INSECURE and not is_secure(request):
        return insecure_page(request)
    return None


def safe_next(raw: str) -> str:
    """
    Куда возвращаться после входа.

    Принимаем только свой путь внутри площадки. Без этой проверки
    ссылка вида /freelance/login?next=https://чужой-сайт превращает
    вход в переадресацию на чужой сайт с логотипом AVERIX в памяти
    посетителя.
    """
    value = (raw or "").strip()
    if not value.startswith("/freelance") or value.startswith("//"):
        return "/freelance/dashboard"
    if any(ch in value for ch in ("\\", "\r", "\n")):
        return "/freelance/dashboard"
    return value[:200]


def context(request: Request, session=None, **extra) -> dict:
    data = {
        "me": session,
        "csrf": session["csrf_token"] if session else "",
        "nav": NAV,
        "page": "",
        "site_url": SITE_URL,
        "canonical": None,
        "year": datetime.now(timezone.utc).year,
        "errors": {},
        "old": {},
    }
    data.update(extra)
    return data


def render(request: Request, template: str, ctx: dict, status: int = 200) -> Response:
    return no_store(templates.TemplateResponse(request, template, ctx,
                                               status_code=status))


def guard(request: Request, next_url: str = ""):
    """(сессия, None) либо (None, ответ). Проверка обязательная и серверная."""
    stop = _http_stop(request)
    if stop:
        return None, stop
    session = current(request)
    if session is None:
        where = "/freelance/login"
        if next_url:
            where += f"?next={next_url}"
        return None, no_store(RedirectResponse(where, status_code=303))
    return session, None


def form_page(request: Request, template: str, ctx: dict, status: int = 200) -> Response:
    """
    Страница с формой, у которой ещё нет сессии: вход, регистрация,
    восстановление пароля.

    Одно и то же случайное значение уходит и в скрытое поле, и в cookie.
    Чужая страница не может прочитать нашу cookie, поэтому подобрать
    пару она не сможет — это и есть защита от отправки формы со стороны.

    Токен считается ДО создания ответа: шаблон отрисовывается сразу,
    в конструкторе, и дописать значение в контекст потом уже нельзя.
    """
    token = secrets.token_urlsafe(24)
    ctx["fc"] = token
    resp = templates.TemplateResponse(request, template, ctx, status_code=status)
    _set_cookie(resp, FORM_COOKIE, token, 900)
    return no_store(resp)


def _form_token_ok(request, sent: str) -> bool:
    saved = request.cookies.get(FORM_COOKIE, "")
    return bool(saved) and security.check_csrf({"csrf_token": saved}, sent)


def _val(form, name: str, limit: int = 300) -> str:
    return str(form.get(name, "")).strip()[:limit]


# ============================================================
# Вход в площадку
# ============================================================

@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    session = current(request)
    ctx = context(request, session, page="home", canonical="/freelance")
    # no-store, потому что в шапке видно, вошёл человек или нет:
    # общий кеш не должен отдать чужое состояние следующему посетителю
    return render(request, "freelance/landing.html", ctx)


# ============================================================
# Регистрация
# ============================================================

def _register_page(request: Request, status: int = 200, **extra) -> Response:
    ctx = context(request, None, page="register", **extra)
    return form_page(request, "freelance/register.html", ctx, status)


@router.get("/register", response_class=HTMLResponse)
async def register_form(request: Request):
    stop = _http_stop(request)
    if stop:
        return stop
    if current(request) is not None:
        return no_store(RedirectResponse("/freelance/dashboard", status_code=303))
    return _register_page(request)


@router.post("/register", response_class=HTMLResponse)
async def register(request: Request):
    stop = _http_stop(request)
    if stop:
        return stop
    form = await request.form()
    ip = client_ip(request)

    old = {
        "email": _val(form, "email", 190),
        "name": _val(form, "name", 100),
        "telegram": _val(form, "telegram", 120),
        "role": _val(form, "role", 20),
    }

    if not _form_token_ok(request, _val(form, "fc", 100)):
        return _register_page(request, 400, old=old,
                              alert="Форма устарела. Попробуйте ещё раз.")

    # Скрытое поле: человек его не видит и не заполняет
    if _val(form, "website", 100):
        journal.warn("площадка.регистрация.бот", ip=ip)
        return no_store(RedirectResponse("/freelance/login", status_code=303))

    role = old["role"] if old["role"] in ("client", "freelancer") else ""
    password = str(form.get("password", ""))

    errors: dict[str, str] = {}
    if len(old["name"]) < 2:
        errors["name"] = "Напишите, как вас зовут."
    if not role:
        errors["role"] = "Выберите, как вы будете пользоваться площадкой."

    with connect() as conn:
        if accounts.too_many(conn, ip, "register"):
            journal.warn("площадка.регистрация.частит", ip=ip)
            return _register_page(
                request, 429, old=old,
                alert="Слишком много попыток регистрации. Попробуйте через час.")
        accounts.hit(conn, ip, "register")

        # Сначала проверяем всё, и только потом пишем. Иначе ошибка
        # в одном поле оставляет наполовину заведённую учётную запись.
        errors.update(accounts.check_new_user(conn, old["email"], password))
        if errors:
            return _register_page(request, 400, old=old, errors=errors)

        user_id = accounts.create_user(conn, old["email"], password, old["telegram"])

        if role == "client":
            accounts.ensure_client_profile(conn, user_id, old["name"])
        else:
            accounts.ensure_freelancer_profile(conn, user_id, old["name"])

        token = accounts.issue_token(conn, user_id, "verify", accounts.VERIFY_HOURS)
        session_token = accounts.create_session(
            conn, user_id, ip, request.headers.get("user-agent", ""))

    # Письмо уходит после того, как всё записано: недоступный почтовый
    # сервер не должен ломать регистрацию
    mailer.send_verification(old["email"], token)
    journal.event("площадка.регистрация", id=user_id, роль=role, ip=ip)

    resp = RedirectResponse("/freelance/dashboard", status_code=303)
    _set_cookie(resp, accounts.SESSION_COOKIE, session_token,
                accounts.SESSION_DAYS * 86400)
    resp.delete_cookie(FORM_COOKIE, path="/")
    return no_store(resp)


# ============================================================
# Вход
# ============================================================

def _login_page(request: Request, status: int = 200, **extra) -> Response:
    ctx = context(request, None, page="login", **extra)
    ctx.setdefault("next_url", "/freelance/dashboard")
    return form_page(request, "freelance/login.html", ctx, status)


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request, next: str = ""):
    stop = _http_stop(request)
    if stop:
        return stop
    if current(request) is not None:
        return no_store(RedirectResponse(safe_next(next), status_code=303))
    return _login_page(request, next_url=safe_next(next))


@router.post("/login", response_class=HTMLResponse)
async def login(request: Request):
    stop = _http_stop(request)
    if stop:
        return stop
    form = await request.form()
    ip = client_ip(request)
    email = _val(form, "email", 190)
    where = safe_next(_val(form, "next", 200))

    if not _form_token_ok(request, _val(form, "fc", 100)):
        return _login_page(request, 400, next_url=where, old={"email": email},
                           alert="Форма устарела. Попробуйте ещё раз.")

    with connect() as conn:
        # Счётчик общий с админкой: подбор пароля — это подбор пароля,
        # с какой бы формы его ни вели
        failures = security.recent_failures(conn, ip)
        if security.is_blocked(failures):
            journal.warn("площадка.вход.блок", ip=ip)
            return _login_page(request, 429, next_url=where, old={"email": email},
                               alert="Слишком много попыток. Подождите 15 минут.")
        delay = security.login_delay(failures)

        row, problem = accounts.verify_login(conn, email, str(form.get("password", "")))
        security.record_attempt(conn, ip, email, row is not None)
        if row is None:
            journal.warn("площадка.вход.неудача", ip=ip)
            if delay:
                await asyncio.sleep(delay)
            return _login_page(request, 401, next_url=where, old={"email": email},
                               alert=problem)

        token = accounts.create_session(conn, row["id"], ip,
                                        request.headers.get("user-agent", ""))
        accounts.touch(conn, row["id"])

    journal.event("площадка.вход", id=row["id"], ip=ip)
    resp = RedirectResponse(where, status_code=303)
    _set_cookie(resp, accounts.SESSION_COOKIE, token, accounts.SESSION_DAYS * 86400)
    resp.delete_cookie(FORM_COOKIE, path="/")
    return no_store(resp)


@router.post("/logout")
async def logout(request: Request):
    form = await request.form()
    session = current(request)
    if not security.check_csrf(session, form.get("csrf")):
        return no_store(RedirectResponse("/freelance", status_code=303))
    with connect() as conn:
        accounts.destroy_session(conn, request.cookies.get(accounts.SESSION_COOKIE))
    resp = RedirectResponse("/freelance", status_code=303)
    resp.delete_cookie(accounts.SESSION_COOKIE, path="/")
    return no_store(resp)


# ============================================================
# Подтверждение почты
# ============================================================

@router.get("/verify", response_class=HTMLResponse)
async def verify(request: Request, token: str = ""):
    session = current(request)
    with connect() as conn:
        user_id = accounts.use_token(conn, token, "verify")
        if user_id is not None:
            accounts.mark_verified(conn, user_id)
    ok = user_id is not None
    if ok:
        journal.event("площадка.почта.подтверждена", id=user_id)
    ctx = context(request, session, page="verify", ok=ok)
    return render(request, "freelance/verify.html", ctx, 200 if ok else 400)


@router.post("/verify/resend")
async def verify_resend(request: Request):
    session, stop = guard(request)
    if stop:
        return stop
    form = await request.form()
    if not security.check_csrf(session, form.get("csrf")):
        return no_store(RedirectResponse("/freelance/dashboard", status_code=303))
    ip = client_ip(request)
    with connect() as conn:
        if accounts.too_many(conn, ip, "verify_resend"):
            return no_store(RedirectResponse(
                "/freelance/dashboard?note=often", status_code=303))
        accounts.hit(conn, ip, "verify_resend")
        token = accounts.issue_token(conn, session["user_id"], "verify",
                                     accounts.VERIFY_HOURS)
    mailer.send_verification(session["email"], token)
    return no_store(RedirectResponse("/freelance/dashboard?note=sent",
                                     status_code=303))


# ============================================================
# Восстановление пароля
# ============================================================

def _forgot_page(request: Request, status: int = 200, **extra) -> Response:
    ctx = context(request, None, page="forgot",
                  mail_ready=mailer.configured(), **extra)
    return form_page(request, "freelance/forgot.html", ctx, status)


@router.get("/forgot", response_class=HTMLResponse)
async def forgot_form(request: Request):
    stop = _http_stop(request)
    if stop:
        return stop
    return _forgot_page(request)


@router.post("/forgot", response_class=HTMLResponse)
async def forgot(request: Request):
    stop = _http_stop(request)
    if stop:
        return stop
    form = await request.form()
    ip = client_ip(request)
    email = _val(form, "email", 190)

    if not _form_token_ok(request, _val(form, "fc", 100)):
        return _forgot_page(request, 400, old={"email": email},
                            alert="Форма устарела. Попробуйте ещё раз.")

    with connect() as conn:
        if accounts.too_many(conn, ip, "reset"):
            journal.warn("площадка.сброс.частит", ip=ip)
            return _forgot_page(request, 429, old={"email": email},
                                alert="Слишком много запросов. Попробуйте через час.")
        accounts.hit(conn, ip, "reset")
        user = accounts.user_by_email(conn, email)
        token = ""
        if user is not None and user["status"] == "active":
            token = accounts.issue_token(conn, user["id"], "reset",
                                         accounts.RESET_HOURS)

    if token:
        mailer.send_reset(email, token)
    journal.event("площадка.сброс.запрошен", ip=ip)
    # Ответ одинаковый и для существующего адреса, и для любого другого:
    # иначе по этой форме составляется список зарегистрированных.
    return _forgot_page(request, sent=True)


def _reset_page(request: Request, token: str, status: int = 200, **extra) -> Response:
    ctx = context(request, None, page="reset", token=token, **extra)
    return form_page(request, "freelance/reset.html", ctx, status)


@router.get("/reset", response_class=HTMLResponse)
async def reset_form(request: Request, token: str = ""):
    stop = _http_stop(request)
    if stop:
        return stop
    return _reset_page(request, token)


@router.post("/reset", response_class=HTMLResponse)
async def reset(request: Request):
    stop = _http_stop(request)
    if stop:
        return stop
    form = await request.form()
    token = _val(form, "token", 100)
    password = str(form.get("password", ""))

    if not _form_token_ok(request, _val(form, "fc", 100)):
        return _reset_page(request, token, 400,
                           alert="Форма устарела. Попробуйте ещё раз.")

    problem = accounts.check_password(password)
    if problem:
        return _reset_page(request, token, 400, errors={"password": problem})

    with connect() as conn:
        user_id = accounts.use_token(conn, token, "reset")
        if user_id is None:
            return _reset_page(
                request, "", 400,
                alert="Ссылка уже использована или устарела. Запросите новую.")
        accounts.set_password(conn, user_id, password)

    journal.event("площадка.пароль.изменён", id=user_id)
    return _login_page(request, ok="Пароль изменён. Войдите с новым паролем.")


# ============================================================
# Кабинет
# ============================================================

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, note: str = ""):
    session, stop = guard(request, "/freelance/dashboard")
    if stop:
        return stop
    with connect() as conn:
        who = accounts.roles(conn, session["user_id"])
        accounts.touch(conn, session["user_id"])
    ctx = context(request, session, page="dashboard", roles=who,
                  mail_ready=mailer.configured(),
                  note=note if note in ("sent", "often") else "")
    return render(request, "freelance/dashboard.html", ctx)


@router.post("/roles")
async def add_role(request: Request):
    """Второе лицо для того же человека: заказчик у специалиста и наоборот."""
    session, stop = guard(request)
    if stop:
        return stop
    form = await request.form()
    if not security.check_csrf(session, form.get("csrf")):
        return no_store(RedirectResponse("/freelance/dashboard", status_code=303))
    role = _val(form, "role", 20)
    name = _val(form, "name", 100)
    with connect() as conn:
        if role == "client":
            accounts.ensure_client_profile(conn, session["user_id"], name)
        elif role == "freelancer":
            accounts.ensure_freelancer_profile(conn, session["user_id"], name)
    journal.event("площадка.роль", id=session["user_id"], роль=role)
    return no_store(RedirectResponse("/freelance/dashboard", status_code=303))
