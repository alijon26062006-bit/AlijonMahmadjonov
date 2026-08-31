"""
Кабинет специалиста площадки: профиль по шагам и портфолио.

Шаги — не украшение. Профиль специалиста это пятнадцать полей, и одна
страница с пятнадцатью полями заполняется до середины, а потом
закрывается. Каждый шаг сохраняется сам по себе, поэтому уйти
на середине и вернуться завтра можно без потерь.

Правится только своё: список колонок задан в specialists.OWN_COLUMNS,
и ни статус, ни публикация, ни логин через форму не проходят.
Владелец работы стоит в самом SQL-запросе.
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from . import journal, security, specialists, taxonomy
from .db import connect
from .notify import notify
from .render import no_store
from .routes_freelance import context, guard, render
from .uploads import UploadError, delete_image_file, save_image

router = APIRouter(prefix="/freelance/profile")

# Порядок шагов: адрес, название и то поле из проверки заполненности,
# по которому шаг считается пройденным. Третий элемент нужен, чтобы
# галочку в навигации не пришлось выводить условиями прямо в шаблоне.
STEPS = (
    ("basics", "Кто вы", "title"),
    ("direction", "Направление и навыки", "skills"),
    ("experience", "Опыт", "about"),
    ("terms", "Условия и занятость", "rate"),
    ("portfolio", "Портфолио", "portfolio"),
)


def _val(form, name: str, limit: int = 300) -> str:
    return str(form.get(name, "")).strip()[:limit]


def _int(form, name: str) -> int | None:
    raw = _val(form, name, 12)
    return int(raw) if raw.isdigit() else None


def me(request: Request):
    """
    (сессия, профиль, None) либо (None, None, ответ).

    Профиль специалиста есть не у каждого: человек мог завести только
    лицо заказчика. Тогда отправляем в кабинет, а не показываем пустые
    формы неизвестно про кого.
    """
    session, stop = guard(request, "/freelance/profile")
    if stop:
        return None, None, stop
    with connect() as conn:
        row = specialists.by_user(conn, session["user_id"])
    if row is None:
        return None, None, no_store(
            RedirectResponse("/freelance/dashboard", status_code=303))
    return session, row, None


def _page(request: Request, session, row, template: str, **extra):
    with connect() as conn:
        state = specialists.completeness(conn, row)
        extra.setdefault("person", specialists.profile_view(conn, row))
    ctx = context(request, session, page="profile", steps=STEPS, state=state,
                  checklist=specialists.CHECKLIST,
                  listings=specialists.LISTINGS, **extra)
    return render(request, template, ctx)


def _back(where: str = "/freelance/profile"):
    return no_store(RedirectResponse(where, status_code=303))


def _csrf_ok(session, form) -> bool:
    return security.check_csrf(session, form.get("csrf"))


# ============================================================
# Обзор профиля
# ============================================================

@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def overview(request: Request, error: str = "", note: str = ""):
    session, row, stop = me(request)
    if stop:
        return stop
    with connect() as conn:
        blockers = specialists.can_publish(conn, row)
    return _page(request, session, row, "freelance/profile.html",
                 error=error, note=note, blockers=blockers)


@router.post("/publish")
async def publish(request: Request):
    session, row, stop = me(request)
    if stop:
        return stop
    form = await request.form()
    if not _csrf_ok(session, form):
        return _back()
    wanted = _val(form, "wanted", 4) == "1"
    with connect() as conn:
        problem = specialists.request_listing(conn, row["id"], wanted)
        if not problem and wanted:
            # Проверять профили должен человек, и он должен об этом узнать
            notify(conn, "listing", f"Профиль на проверку: {row['name']}",
                   "freelancers", row["id"])
    if problem:
        return _back(f"/freelance/profile?error={problem}")
    journal.event("площадка.профиль.публикация", id=row["id"],
                  просит=1 if wanted else 0)
    return _back("/freelance/profile?note=" + ("sent" if wanted else "hidden"))


# ============================================================
# Шаг 1. Кто вы
# ============================================================

@router.get("/basics", response_class=HTMLResponse)
async def basics(request: Request, error: str = ""):
    session, row, stop = me(request)
    if stop:
        return stop
    return _page(request, session, row, "freelance/step_basics.html",
                 step="basics", error=error)


@router.post("/basics")
async def basics_save(request: Request):
    session, row, stop = me(request)
    if stop:
        return stop
    form = await request.form()
    if not _csrf_ok(session, form):
        return _back()
    with connect() as conn:
        specialists.save_profile(conn, row["id"], {
            "name": _val(form, "name", 100) or row["name"],
            "title": _val(form, "title", 120),
            "city": _val(form, "city", 80),
            "country": _val(form, "country", 80),
        })
    return _back("/freelance/profile/direction")


@router.post("/photo")
async def photo(request: Request):
    """Фотография профиля. Файл пересохраняется нашим кодом: наружу
    попадают только пиксели, без EXIF с координатами съёмки."""
    session, row, stop = me(request)
    if stop:
        return stop
    form = await request.form()
    if not _csrf_ok(session, form):
        return _back()
    upload = form.get("photo")
    if upload is None or not getattr(upload, "filename", ""):
        return _back("/freelance/profile/basics?error=Выберите файл.")
    try:
        saved = save_image(await upload.read(), upload.filename)
    except UploadError as problem:
        return _back(f"/freelance/profile/basics?error={problem}")
    with connect() as conn:
        old = row["photo"]
        conn.execute("UPDATE freelancers SET photo = ?,"
                     " updated_at = datetime('now') WHERE id = ?",
                     (saved.filename, row["id"]))
    if old:
        delete_image_file(old)
    return _back("/freelance/profile/basics")


@router.post("/photo/delete")
async def photo_delete(request: Request):
    session, row, stop = me(request)
    if stop:
        return stop
    form = await request.form()
    if not _csrf_ok(session, form):
        return _back()
    with connect() as conn:
        conn.execute("UPDATE freelancers SET photo = NULL,"
                     " updated_at = datetime('now') WHERE id = ?", (row["id"],))
    if row["photo"]:
        delete_image_file(row["photo"])
    return _back("/freelance/profile/basics")


# ============================================================
# Шаг 2. Направление и навыки
# ============================================================

@router.get("/direction", response_class=HTMLResponse)
async def direction(request: Request, error: str = ""):
    session, row, stop = me(request)
    if stop:
        return stop
    with connect() as conn:
        tree = taxonomy.category_tree(conn)
        known = taxonomy.visible_skills(conn)
        mine = taxonomy.freelancer_skills(conn, row["id"])
    return _page(request, session, row, "freelance/step_direction.html",
                 step="direction", tree=tree, known=known, mine=mine, error=error)


@router.post("/direction")
async def direction_save(request: Request):
    session, row, stop = me(request)
    if stop:
        return stop
    form = await request.form()
    if not _csrf_ok(session, form):
        return _back()
    category_id = _int(form, "category_id")
    with connect() as conn:
        if category_id is not None and taxonomy.get_category(conn, category_id) is None:
            category_id = None
        specialists.save_profile(conn, row["id"], {"category_id": category_id})
        taxonomy.set_freelancer_skills(conn, row["id"], _val(form, "skills", 600))
    return _back("/freelance/profile/experience")


# ============================================================
# Шаг 3. Опыт
# ============================================================

@router.get("/experience", response_class=HTMLResponse)
async def experience(request: Request, error: str = ""):
    session, row, stop = me(request)
    if stop:
        return stop
    return _page(request, session, row, "freelance/step_experience.html",
                 step="experience", levels=specialists.LEVELS, error=error)


@router.post("/experience")
async def experience_save(request: Request):
    session, row, stop = me(request)
    if stop:
        return stop
    form = await request.form()
    if not _csrf_ok(session, form):
        return _back()
    level = _val(form, "level", 20)
    with connect() as conn:
        specialists.save_profile(conn, row["id"], {
            "level": level if level in specialists.LEVELS else row["level"],
            "years": _val(form, "years", 40),
            "experience": _val(form, "experience", 500),
            "about": _val(form, "about", 3000),
        })
    return _back("/freelance/profile/terms")


# ============================================================
# Шаг 4. Условия и занятость
# ============================================================

AVAILABILITY = {
    "available": "Доступен для работы",
    "partially_busy": "Частично занят",
    "busy": "Занят",
}


@router.get("/terms", response_class=HTMLResponse)
async def terms(request: Request, error: str = ""):
    session, row, stop = me(request)
    if stop:
        return stop
    with connect() as conn:
        from . import models
        settings = models.settings(conn, "ru")
    return _page(request, session, row, "freelance/step_terms.html",
                 step="terms", availability=AVAILABILITY,
                 currency=settings.get("freelance_currency_short", "смн"),
                 error=error)


@router.post("/terms")
async def terms_save(request: Request):
    session, row, stop = me(request)
    if stop:
        return stop
    form = await request.form()
    if not _csrf_ok(session, form):
        return _back()

    raw_hour, raw_project = _val(form, "rate_hour", 20), _val(form, "rate_project", 20)
    hour = specialists.parse_money(raw_hour)
    project = specialists.parse_money(raw_project)
    if (raw_hour and hour is None) or (raw_project and project is None):
        return _back("/freelance/profile/terms?error="
                     "Цену пишите числом, например 300 или 300,50.")

    availability = _val(form, "availability", 20)
    with connect() as conn:
        specialists.save_profile(conn, row["id"], {
            "rate_hour": hour,
            "rate_project_min": project,
            "availability": (availability if availability in AVAILABILITY
                             else row["availability"]),
            "telegram": _val(form, "telegram", 120),
            "email": _val(form, "email", 120),
            "portfolio_url": _val(form, "portfolio_url", 300),
            "github_url": _val(form, "github_url", 300),
        })
    return _back("/freelance/profile/portfolio")


# ============================================================
# Шаг 5. Портфолио
# ============================================================

@router.get("/portfolio", response_class=HTMLResponse)
async def portfolio(request: Request, error: str = ""):
    session, row, stop = me(request)
    if stop:
        return stop
    with connect() as conn:
        items = specialists.portfolio(conn, row["id"])
    return _page(request, session, row, "freelance/step_portfolio.html",
                 step="portfolio", items=items, error=error,
                 limit=specialists.MAX_PORTFOLIO_ITEMS)


@router.get("/portfolio/new", response_class=HTMLResponse)
async def portfolio_new(request: Request, error: str = ""):
    session, row, stop = me(request)
    if stop:
        return stop
    with connect() as conn:
        tree = taxonomy.category_tree(conn)
    return _page(request, session, row, "freelance/portfolio_form.html",
                 step="portfolio", item=None, tree=tree, error=error)


@router.get("/portfolio/{item_id}", response_class=HTMLResponse)
async def portfolio_edit(request: Request, item_id: int, error: str = ""):
    session, row, stop = me(request)
    if stop:
        return stop
    with connect() as conn:
        item = specialists.portfolio_item(conn, item_id, row["id"])
        tree = taxonomy.category_tree(conn)
    if item is None:
        return _back("/freelance/profile/portfolio?error=Работа не найдена.")
    return _page(request, session, row, "freelance/portfolio_form.html",
                 step="portfolio", item=item, tree=tree, error=error,
                 images_left=specialists.MAX_PORTFOLIO_IMAGES - len(item["images"]))


@router.post("/portfolio/save")
async def portfolio_save(request: Request):
    session, row, stop = me(request)
    if stop:
        return stop
    form = await request.form()
    if not _csrf_ok(session, form):
        return _back()
    item_id = _int(form, "id")
    with connect() as conn:
        saved_id, problem = specialists.save_portfolio_item(conn, item_id, row["id"], {
            "title": _val(form, "title", 120),
            "description": _val(form, "description", 2000),
            "category_id": _int(form, "category_id"),
            "tech": _val(form, "tech", 300),
            "url": _val(form, "url", 300),
        })
    if problem:
        where = f"/freelance/profile/portfolio/{item_id}" if item_id else \
                "/freelance/profile/portfolio/new"
        return _back(f"{where}?error={problem}")
    return _back(f"/freelance/profile/portfolio/{saved_id}")


@router.post("/portfolio/{item_id}/delete")
async def portfolio_delete(request: Request, item_id: int):
    session, row, stop = me(request)
    if stop:
        return stop
    form = await request.form()
    if not _csrf_ok(session, form):
        return _back()
    with connect() as conn:
        files = specialists.delete_portfolio_item(conn, item_id, row["id"])
    for name in files:
        delete_image_file(name)
    return _back("/freelance/profile/portfolio")


@router.post("/portfolio/{item_id}/image")
async def portfolio_image(request: Request, item_id: int):
    session, row, stop = me(request)
    if stop:
        return stop
    form = await request.form()
    if not _csrf_ok(session, form):
        return _back()
    upload = form.get("image")
    where = f"/freelance/profile/portfolio/{item_id}"
    if upload is None or not getattr(upload, "filename", ""):
        return _back(f"{where}?error=Выберите файл.")
    try:
        saved = save_image(await upload.read(), upload.filename)
    except UploadError as problem:
        return _back(f"{where}?error={problem}")
    with connect() as conn:
        problem = specialists.add_portfolio_image(conn, item_id, row["id"], saved)
    if problem:
        # Файл уже на диске, а в базу не попал — убираем, иначе он
        # останется мусором навсегда
        delete_image_file(saved.filename)
        return _back(f"{where}?error={problem}")
    return _back(where)


@router.post("/portfolio/image/{image_id}/delete")
async def portfolio_image_delete(request: Request, image_id: int):
    session, row, stop = me(request)
    if stop:
        return stop
    form = await request.form()
    if not _csrf_ok(session, form):
        return _back()
    with connect() as conn:
        filename = specialists.delete_portfolio_image(conn, image_id, row["id"])
    if filename:
        delete_image_file(filename)
    return _back(f"/freelance/profile/portfolio/{_int(form, 'item_id') or ''}")
