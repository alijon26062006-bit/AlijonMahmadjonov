"""
Публичная часть сайта.

Статику (стили, скрипты, шрифты, картинки) отдаёт nginx напрямую —
сюда приходят только запросы за страницами.
"""
import re

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response

from . import journal, models
from .config import SITE_URL
from .db import connect
from .render import client_ip, no_store, public_context, templates

router = APIRouter()

# Заявок с одного адреса за десять минут
SPAM_LIMIT = 3
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+\.[a-zA-Z]{2,}$")


def _val(form, name: str, limit: int = 3000) -> str:
    return str(form.get(name, "")).strip()[:limit]


def _looks_like_spam(form, ip: str, table: str, conn) -> str | None:
    """Возвращает причину отказа или None."""
    # Скрытое поле: человек его не видит и не заполняет, робот заполняет
    if _val(form, "website", 100):
        return "spam-honeypot"
    if models.recent_from_ip(conn, table, ip) >= SPAM_LIMIT:
        return "spam-rate"
    return None


# ============================================================
# Страницы
# ============================================================

@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    with connect() as conn:
        ctx = public_context(request, conn, page="home")
        ctx["featured"] = models.public_projects(
            conn, ctx["lang"], featured_only=True, limit=4
        )
    return templates.TemplateResponse(request, "public/home.html", ctx)


@router.get("/projects", response_class=HTMLResponse)
async def projects(request: Request, category: str = ""):
    if category and category not in models.CATEGORIES:
        category = ""
    with connect() as conn:
        ctx = public_context(request, conn, page="projects")
        ctx["projects"] = models.public_projects(conn, ctx["lang"], category or None)
        used = models.used_categories(conn)
        ctx["filters"] = {k: v for k, v in models.CATEGORIES.items() if k in used}
        ctx["active"] = category
    return templates.TemplateResponse(request, "public/projects.html", ctx)


@router.get("/projects/{slug}", response_class=HTMLResponse)
async def case(request: Request, slug: str):
    with connect() as conn:
        ctx = public_context(request, conn, page="projects")
        project = models.public_project(conn, slug, ctx["lang"])
        if project is None:
            # Черновик и несуществующий проект неотличимы снаружи:
            # иначе по ответу можно было бы узнать о скрытых работах
            return _not_found(request, ctx)
        ctx["p"] = project
        ctx["next_project"] = models.neighbour_project(conn, project, ctx["lang"])
    return templates.TemplateResponse(request, "public/case.html", ctx)


@router.get("/team", response_class=HTMLResponse)
async def team(request: Request):
    with connect() as conn:
        ctx = public_context(request, conn, page="team")
        ctx["team"] = models.public_team(conn, ctx["lang"])
    return templates.TemplateResponse(request, "public/team.html", ctx)


@router.get("/careers", response_class=HTMLResponse)
async def careers(request: Request):
    with connect() as conn:
        ctx = public_context(request, conn, page="careers")
        ctx["vacancies"] = models.open_vacancies(conn, ctx["lang"])
    return templates.TemplateResponse(request, "public/careers.html", ctx)


@router.get("/thanks", response_class=HTMLResponse)
async def thanks(request: Request, kind: str = "request"):
    with connect() as conn:
        ctx = public_context(request, conn, page="thanks")
    ctx["kind"] = "job" if kind == "job" else "request"
    return no_store(templates.TemplateResponse(request, "public/thanks.html", ctx))


def _not_found(request: Request, ctx: dict) -> Response:
    return templates.TemplateResponse(
        request, "public/notfound.html", ctx, status_code=404
    )


def public_notfound(request: Request) -> Response:
    """404 в оформлении сайта — для любого адреса вне админки."""
    with connect() as conn:
        ctx = public_context(request, conn, page="404")
    return _not_found(request, ctx)


# ============================================================
# Формы
# ============================================================

@router.post("/request")
async def client_request(request: Request):
    form = await request.form()
    ip = client_ip(request)

    with connect() as conn:
        ctx = public_context(request, conn, page="home")
        reason = _looks_like_spam(form, ip, "client_requests", conn)
        if reason:
            journal.warn("заявка.отклонена", причина=reason, ip=ip)
            # Роботу не сообщаем, что его раскусили
            return RedirectResponse("/thanks?kind=request", status_code=303)

        name = _val(form, "name", 100)
        contact = _val(form, "contact", 120)
        message = _val(form, "message", 3000)
        project_type = _val(form, "project_type", 40)
        if project_type not in models.REQUEST_TYPES:
            project_type = "other"

        errors = {}
        if len(name) < 2:
            errors["name"] = "Напишите, как к вам обращаться."
        if len(contact) < 3:
            errors["contact"] = "Оставьте Telegram или телефон — иначе я не смогу ответить."
        if len(message) < 10:
            errors["message"] = "Опишите задачу хотя бы в двух предложениях."

        if errors:
            ctx["errors"] = errors
            ctx["old"] = {"name": name, "contact": contact, "message": message,
                          "project_type": project_type, "budget": _val(form, "budget", 80)}
            ctx["featured"] = models.public_projects(conn, ctx["lang"], featured_only=True, limit=4)
            return templates.TemplateResponse(
                request, "public/home.html", ctx, status_code=400
            )

        is_email = bool(EMAIL_RE.match(contact))
        new_id = models.add_client_request(conn, {
            "name": name,
            "telegram": "" if is_email else contact,
            "email": contact if is_email else "",
            "project_type": project_type,
            "budget": _val(form, "budget", 80),
            "message": message,
            "ip": ip,
        })
    journal.event("заявка.клиент", id=new_id, тип=project_type, ip=ip)
    return RedirectResponse("/thanks?kind=request", status_code=303)


@router.post("/apply")
async def job_apply(request: Request):
    form = await request.form()
    ip = client_ip(request)

    with connect() as conn:
        ctx = public_context(request, conn, page="careers")
        reason = _looks_like_spam(form, ip, "job_applications", conn)
        if reason:
            journal.warn("отклик.отклонён", причина=reason, ip=ip)
            return RedirectResponse("/thanks?kind=job", status_code=303)

        raw_vacancy = _val(form, "vacancy_id", 10)
        vacancy_id = int(raw_vacancy) if raw_vacancy.isdigit() else None
        if vacancy_id is not None:
            row = models.get_vacancy(conn, vacancy_id)
            # На закрытую вакансию отклик не принимаем
            if row is None or row["status"] != "open":
                vacancy_id = None

        name = _val(form, "name", 100)
        contact = _val(form, "telegram", 120)
        message = _val(form, "message", 3000)

        errors = {}
        if len(name) < 2:
            errors["name"] = "Напишите, как вас зовут."
        if len(contact) < 3:
            errors["telegram"] = "Оставьте Telegram или почту для связи."
        if len(message) < 20:
            errors["message"] = "Расскажите о себе чуть подробнее — хотя бы пару фраз."

        if errors:
            ctx["errors"] = errors
            ctx["old"] = {k: _val(form, k, 300) for k in
                          ("name", "telegram", "email", "country", "direction",
                           "experience", "skills", "portfolio_url", "github_url", "message")}
            ctx["old"]["vacancy_id"] = raw_vacancy
            ctx["vacancies"] = models.open_vacancies(conn, ctx["lang"])
            return templates.TemplateResponse(
                request, "public/careers.html", ctx, status_code=400
            )

        new_id = models.add_job_application(conn, {
            "vacancy_id": vacancy_id,
            "name": name,
            "telegram": contact,
            "email": _val(form, "email", 120),
            "country": _val(form, "country", 80),
            "direction": _val(form, "direction", 80),
            "experience": _val(form, "experience", 200),
            "skills": _val(form, "skills", 500),
            "portfolio_url": _val(form, "portfolio_url", 300),
            "github_url": _val(form, "github_url", 300),
            "message": message,
            "ip": ip,
        })
    journal.event("отклик.вакансия", id=new_id, вакансия=vacancy_id, ip=ip)
    return RedirectResponse("/thanks?kind=job", status_code=303)


# ============================================================
# Для поисковиков
# ============================================================

@router.get("/robots.txt", response_class=PlainTextResponse)
async def robots():
    return PlainTextResponse(
        "User-agent: *\n"
        "Disallow: /admin\n"
        "Disallow: /thanks\n"
        "Disallow: /uploads/\n"
        f"\nSitemap: {SITE_URL}/sitemap.xml\n"
    )


@router.get("/sitemap.xml")
async def sitemap():
    urls = [("/", "1.0"), ("/projects", "0.9"), ("/team", "0.6"), ("/careers", "0.6")]
    with connect() as conn:
        for p in conn.execute(
            "SELECT slug, updated_at FROM projects"
            " WHERE status = 'published' AND allow_indexing = 1"
        ):
            urls.append((f"/projects/{p['slug']}", "0.8"))

    body = ['<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path, priority in urls:
        body.append(f"  <url><loc>{SITE_URL}{path}</loc>"
                    f"<priority>{priority}</priority></url>")
    body.append("</urlset>")
    return Response("\n".join(body), media_type="application/xml")
