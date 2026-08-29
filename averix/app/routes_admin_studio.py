"""
Разделы админки: настройки сайта, команда, вакансии, заявки и отклики.

Проекты и вход остались в main.py — здесь только то, что появилось
вместе с разделами студии.
"""
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, Response

from . import journal, models, security
from .adminkit import back, error_page, guard, page
from .db import connect
from .uploads import UploadError, delete_image_file, save_image

router = APIRouter(prefix="/admin")

# Настройки, которые редактируются как многострочный текст
LONG_SETTINGS = {"hero_title", "hero_subtitle", "about_text", "cta_title", "careers_intro"}
# Понятные подписи вместо ключей из базы
SETTING_LABELS = {
    "contact_telegram": "Telegram (без @)",
    "contact_email": "Почта",
    "contact_instagram": "Instagram (без @)",
    "contact_github": "GitHub (логин)",
    "city": "Город",
    "hero_eyebrow": "Первый экран: строка над заголовком",
    "hero_title": "Первый экран: заголовок (можно <em>выделение</em>)",
    "hero_subtitle": "Первый экран: подзаголовок",
    "stat_years": "Цифра: лет в разработке",
    "stat_active": "Цифра: активных проектов",
    "stat_accepted": "Цифра: процент принятых работ",
    "about_text": "О студии: описание",
    "cta_title": "Призыв в конце страницы",
    "careers_intro": "Вакансии: вступление",

    "stat_years_on": "Показывать первый показатель",
    "stat_years": "Первый показатель: число",
    "stat_years_unit": "Первый показатель: знак после числа",
    "stat_years_label": "Первый показатель: подпись",
    "stat_active_on": "Показывать второй показатель",
    "stat_active": "Второй показатель: число",
    "stat_active_unit": "Второй показатель: знак после числа",
    "stat_active_label": "Второй показатель: подпись",
    "stat_accepted_on": "Показывать третий показатель",
    "stat_accepted": "Третий показатель: число",
    "stat_accepted_unit": "Третий показатель: знак после числа",
    "stat_accepted_label": "Третий показатель: подпись",
}
# Порядок и группировка на странице настроек. По алфавиту из базы
# получалась каша, в которой контакты стояли вперемешку с текстами.
SETTING_GROUPS = [
    ("Контакты", ["contact_telegram", "contact_email", "contact_instagram",
                  "contact_github", "city"]),
    ("Первый экран", ["hero_eyebrow", "hero_title", "hero_subtitle"]),
    ("Показатель 1", ["stat_years_on", "stat_years", "stat_years_unit", "stat_years_label"]),
    ("Показатель 2", ["stat_active_on", "stat_active", "stat_active_unit", "stat_active_label"]),
    ("Показатель 3", ["stat_accepted_on", "stat_accepted", "stat_accepted_unit", "stat_accepted_label"]),
    ("Тексты страниц", ["about_text", "cta_title", "careers_intro"]),
]


def _grouped(rows) -> list[tuple[str, list]]:
    by_key = {row["key"]: row for row in rows}
    out = []
    for title, keys in SETTING_GROUPS:
        block = [by_key.pop(key) for key in keys if key in by_key]
        if block:
            out.append((title, block))
    # Настройка, добавленная позже и не попавшая в список, не должна
    # молча исчезать со страницы
    if by_key:
        out.append(("Прочее", list(by_key.values())))
    return out


def _val(form, name: str, limit: int = 4000) -> str:
    return str(form.get(name, "")).strip()[:limit]


def _flag(form, name: str) -> int:
    return 1 if form.get(name) else 0


# ============================================================
# Настройки сайта
# ============================================================

@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, saved: str = ""):
    session, stop = guard(request)
    if stop:
        return stop
    with connect() as conn:
        rows = models.all_settings(conn)
    return page(request, session, "admin/settings.html",
                groups=_grouped(rows), labels=SETTING_LABELS, long=LONG_SETTINGS,
                saved=saved == "1")


@router.post("/settings")
async def settings_save(request: Request):
    session, stop = guard(request)
    if stop:
        return stop
    form = await request.form()
    if not security.check_csrf(session, form.get("csrf")):
        return back("/admin/settings")

    with connect() as conn:
        # Ключи берём из базы, а не из формы: иначе подделанное поле
        # добавило бы в настройки что угодно
        for row in models.all_settings(conn):
            key = row["key"]
            ru = _val(form, f"ru__{key}")
            # У переключателей нет второго языка: снятая галочка вообще
            # не приходит в форме, поэтому пустое значение и есть «выключено»
            tj = ru if key.endswith("_on") else _val(form, f"tj__{key}")
            models.save_setting(conn, key, ru, tj)
    journal.event("настройки.сохранены", кто=session["username"])
    return back("/admin/settings?saved=1")


# ============================================================
# Команда
# ============================================================

@router.get("/team", response_class=HTMLResponse)
async def team_list(request: Request):
    session, stop = guard(request)
    if stop:
        return stop
    with connect() as conn:
        rows = models.all_team(conn)
    return page(request, session, "admin/team.html", people=rows)


@router.get("/team/new", response_class=HTMLResponse)
async def team_new(request: Request):
    session, stop = guard(request)
    if stop:
        return stop
    return page(request, session, "admin/team_form.html", member=None, error=None)


@router.get("/team/{member_id}", response_class=HTMLResponse)
async def team_edit(request: Request, member_id: int):
    session, stop = guard(request)
    if stop:
        return stop
    with connect() as conn:
        member = models.get_member(conn, member_id)
    if member is None:
        return error_page(request, 404)
    return page(request, session, "admin/team_form.html", member=member, error=None)


@router.post("/team/save")
async def team_save(request: Request):
    session, stop = guard(request)
    if stop:
        return stop
    form = await request.form()
    if not security.check_csrf(session, form.get("csrf")):
        return back("/admin/team")

    raw_id = _val(form, "id", 10)
    member_id = int(raw_id) if raw_id.isdigit() else None
    name = _val(form, "name", 100)
    if not name:
        return back("/admin/team/new")

    data = {
        "name": name,
        "position_ru": _val(form, "position_ru", 120),
        "position_tj": _val(form, "position_tj", 120),
        "bio_ru": _val(form, "bio_ru", 2000),
        "bio_tj": _val(form, "bio_tj", 2000),
        "telegram": _val(form, "telegram", 80).lstrip("@"),
        "github": _val(form, "github", 80).lstrip("@"),
        "linkedin": _val(form, "linkedin", 300),
        "website": _val(form, "website", 300),
        "visible": _flag(form, "visible"),
        "sort_order": int(_val(form, "sort_order", 6) or 0) if _val(form, "sort_order", 6).lstrip("-").isdigit() else 0,
    }

    upload = form.get("photo")
    old_photo = None
    with connect() as conn:
        current = models.get_member(conn, member_id) if member_id else None
        data["photo"] = current["photo"] if current else None

        if upload is not None and getattr(upload, "filename", ""):
            raw = await upload.read()
            try:
                saved = save_image(raw, upload.filename)
            except UploadError as exc:
                journal.warn("команда.фото.отклонено", причина=str(exc))
                member = models.get_member(conn, member_id) if member_id else None
                return page(request, session, "admin/team_form.html",
                            member=member, error=str(exc))
            old_photo = data["photo"]
            data["photo"] = saved.filename

        member_id = models.save_member(conn, member_id, data)

    if old_photo:
        delete_image_file(old_photo)
    journal.event("команда.сохранена", id=member_id, кто=session["username"])
    return back("/admin/team")


@router.post("/team/{member_id}/delete")
async def team_delete(request: Request, member_id: int, csrf: str = Form("")):
    session, stop = guard(request)
    if stop:
        return stop
    if not security.check_csrf(session, csrf):
        return back("/admin/team")
    with connect() as conn:
        photo = models.delete_member(conn, member_id)
    if photo:
        delete_image_file(photo)
    journal.event("команда.удалена", id=member_id, кто=session["username"])
    return back("/admin/team")


# ============================================================
# Вакансии
# ============================================================

@router.get("/vacancies", response_class=HTMLResponse)
async def vacancy_list(request: Request):
    session, stop = guard(request)
    if stop:
        return stop
    with connect() as conn:
        rows = models.all_vacancies(conn)
    return page(request, session, "admin/vacancies.html", vacancies=rows,
                work_types=models.WORK_TYPES, employment=models.EMPLOYMENT)


@router.get("/vacancies/new", response_class=HTMLResponse)
async def vacancy_new(request: Request):
    session, stop = guard(request)
    if stop:
        return stop
    return page(request, session, "admin/vacancy_form.html", vacancy=None,
                work_types=models.WORK_TYPES, employment=models.EMPLOYMENT)


@router.get("/vacancies/{vacancy_id}", response_class=HTMLResponse)
async def vacancy_edit(request: Request, vacancy_id: int):
    session, stop = guard(request)
    if stop:
        return stop
    with connect() as conn:
        row = models.get_vacancy(conn, vacancy_id)
    if row is None:
        return error_page(request, 404)
    return page(request, session, "admin/vacancy_form.html", vacancy=row,
                work_types=models.WORK_TYPES, employment=models.EMPLOYMENT)


@router.post("/vacancies/save")
async def vacancy_save(request: Request):
    session, stop = guard(request)
    if stop:
        return stop
    form = await request.form()
    if not security.check_csrf(session, form.get("csrf")):
        return back("/admin/vacancies")

    raw_id = _val(form, "id", 10)
    vacancy_id = int(raw_id) if raw_id.isdigit() else None
    title = _val(form, "title_ru", 200)
    if not title:
        return back("/admin/vacancies/new")

    work_type = _val(form, "work_type", 20)
    employment = _val(form, "employment", 20)
    order = _val(form, "sort_order", 6)
    data = {
        "title_ru": title,
        "title_tj": _val(form, "title_tj", 200),
        "description_ru": _val(form, "description_ru", 4000),
        "description_tj": _val(form, "description_tj", 4000),
        "requirements_ru": _val(form, "requirements_ru", 4000),
        "requirements_tj": _val(form, "requirements_tj", 4000),
        "location": _val(form, "location", 120),
        # В базе стоит CHECK — чужое значение уронило бы запрос ошибкой
        "work_type": work_type if work_type in models.WORK_TYPES else "remote",
        "employment": employment if employment in models.EMPLOYMENT else "project",
        "status": "open" if form.get("status") else "closed",
        "sort_order": int(order) if order.lstrip("-").isdigit() else 0,
    }
    with connect() as conn:
        vacancy_id = models.save_vacancy(conn, vacancy_id, data)
    journal.event("вакансия.сохранена", id=vacancy_id, кто=session["username"])
    return back("/admin/vacancies")


@router.post("/vacancies/{vacancy_id}/delete")
async def vacancy_delete(request: Request, vacancy_id: int, csrf: str = Form("")):
    session, stop = guard(request)
    if stop:
        return stop
    if not security.check_csrf(session, csrf):
        return back("/admin/vacancies")
    with connect() as conn:
        conn.execute("DELETE FROM vacancies WHERE id = ?", (vacancy_id,))
    journal.event("вакансия.удалена", id=vacancy_id, кто=session["username"])
    return back("/admin/vacancies")


# ============================================================
# Заявки клиентов и отклики на вакансии
# ============================================================

@router.get("/requests", response_class=HTMLResponse)
async def requests_list(request: Request):
    session, stop = guard(request)
    if stop:
        return stop
    with connect() as conn:
        rows = models.list_requests(conn, "client_requests")
    return page(request, session, "admin/requests.html", items=rows,
                statuses=models.REQUEST_STATUSES, types=models.REQUEST_TYPES)


@router.get("/applications", response_class=HTMLResponse)
async def applications_list(request: Request):
    session, stop = guard(request)
    if stop:
        return stop
    with connect() as conn:
        rows = models.list_requests(conn, "job_applications")
        titles = {v["id"]: v["title_ru"] for v in models.all_vacancies(conn)}
    return page(request, session, "admin/applications.html", items=rows,
                statuses=models.JOB_STATUSES, vacancies=titles)


@router.post("/requests/{table}/{item_id}/status")
async def request_status(request: Request, table: str, item_id: int):
    session, stop = guard(request)
    if stop:
        return stop
    form = await request.form()
    if not security.check_csrf(session, form.get("csrf")):
        return back("/admin")
    where = "/admin/requests" if table == "client_requests" else "/admin/applications"
    with connect() as conn:
        ok = models.set_request_status(conn, table, item_id,
                                       _val(form, "status", 20), _val(form, "note", 2000))
    if not ok:
        return error_page(request, 404)
    journal.event("заявка.статус", таблица=table, id=item_id, кто=session["username"])
    return back(where)


@router.post("/applications/{item_id}/hire")
async def application_hire(request: Request, item_id: int, csrf: str = Form("")):
    """Переносит принятый отклик в команду — черновиком, скрытым от сайта."""
    session, stop = guard(request)
    if stop:
        return stop
    if not security.check_csrf(session, csrf):
        return back("/admin/applications")

    with connect() as conn:
        row = conn.execute("SELECT * FROM job_applications WHERE id = ?", (item_id,)).fetchone()
        if row is None:
            return error_page(request, 404)
        models.save_member(conn, None, {
            "name": row["name"],
            "position_ru": row["direction"] or "",
            "position_tj": "",
            "bio_ru": "", "bio_tj": "", "photo": None,
            "telegram": (row["telegram"] or "").lstrip("@"),
            "github": row["github_url"] or "",
            "linkedin": "", "website": row["portfolio_url"] or "",
            # Скрыт до тех пор, пока карточку не заполнят руками
            "visible": 0, "sort_order": 0,
        })
        models.set_request_status(conn, "job_applications", item_id, "accepted",
                                  row["admin_note"] or "")
    journal.event("отклик.в_команду", id=item_id, кто=session["username"])
    return back("/admin/team")
