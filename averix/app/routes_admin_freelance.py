"""
Админка площадки AVERIX Freelance.

Отдельного второго кабинета для этого не заводим: раздел живёт внутри
существующей панели, под своим адресом и со своей подшапкой. У площадки
слишком много разделов, чтобы разложить их в общей строке навигации,
и слишком мало общего с витриной, чтобы мешать их в одну кучу.

Каждый маршрут начинается с guard(). Проверка серверная: спрятанная
в шаблоне кнопка защитой не считается.
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from . import audit, journal, security, specialists, taxonomy
from .adminkit import back, error_page, guard, page
from .db import connect

router = APIRouter(prefix="/admin/freelance")

HERE = "/admin/freelance"


def _val(form, name: str, limit: int = 300) -> str:
    return str(form.get(name, "")).strip()[:limit]


def _int(form, name: str) -> int | None:
    raw = _val(form, name, 12)
    return int(raw) if raw.lstrip("-").isdigit() else None


def _counts(conn) -> dict:
    """Только настоящие числа. Ни одного придуманного."""
    one = lambda sql: int(conn.execute(sql).fetchone()[0])  # noqa: E731
    return {
        "users": one("SELECT COUNT(*) FROM users"),
        "clients": one("SELECT COUNT(*) FROM client_profiles"),
        "freelancers": one("SELECT COUNT(*) FROM freelancers WHERE user_id IS NOT NULL"),
        "studio_people": one("SELECT COUNT(*) FROM freelancers WHERE user_id IS NULL"),
        "categories": one("SELECT COUNT(*) FROM fl_categories WHERE enabled = 1"),
        "skills": one("SELECT COUNT(*) FROM fl_skills WHERE status = 'active'"),
        "skills_pending": one("SELECT COUNT(*) FROM fl_skills WHERE status = 'pending'"),
        "published": one("SELECT COUNT(*) FROM freelancers"
                         " WHERE listing = 'published' AND user_id IS NOT NULL"),
        "listing_pending": one("SELECT COUNT(*) FROM freelancers"
                               " WHERE listing = 'pending'"),
    }


# ============================================================
# Обзор
# ============================================================

@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def hub(request: Request):
    session, stop = guard(request)
    if stop:
        return stop
    with connect() as conn:
        counts = _counts(conn)
    return page(request, session, "admin/fl_hub.html", counts=counts, sub="hub")


# ============================================================
# Профили специалистов: проверка перед публикацией
# ============================================================

@router.get("/specialists", response_class=HTMLResponse)
async def specialists_list(request: Request, listing: str = "pending",
                           error: str = ""):
    session, stop = guard(request)
    if stop:
        return stop
    if listing not in specialists.LISTINGS:
        listing = ""
    with connect() as conn:
        sql = ("SELECT f.*, u.email, u.created_at AS user_since"
               " FROM freelancers f JOIN users u ON u.id = f.user_id")
        args: tuple = ()
        if listing:
            sql += " WHERE f.listing = ?"
            args = (listing,)
        sql += " ORDER BY f.listed_at DESC, f.id DESC"
        rows = [dict(r) for r in conn.execute(sql, args)]
        for row in rows:
            row["skills"] = taxonomy.freelancer_skills(conn, row["id"])
            row["works"] = int(conn.execute(
                "SELECT COUNT(*) FROM fl_portfolio WHERE freelancer_id = ?",
                (row["id"],)).fetchone()[0])
        counts = {key: 0 for key in specialists.LISTINGS}
        for row in conn.execute(
            "SELECT listing, COUNT(*) n FROM freelancers"
            " WHERE user_id IS NOT NULL GROUP BY listing"
        ):
            counts[row["listing"]] = row["n"]
    return page(request, session, "admin/fl_specialists.html",
                people=rows, active=listing, counts=counts,
                listings=specialists.LISTINGS, levels=specialists.LEVELS,
                error=error, sub="specialists")


@router.post("/specialists/{freelancer_id}/listing")
async def specialist_listing(request: Request, freelancer_id: int):
    """
    Решение по публикации профиля.

    Отдельно от статуса специалиста в базе студии: одобрить человека
    для задач и показать его карточку на сайте — разные решения,
    и путать их нельзя.
    """
    session, stop = guard(request)
    if stop:
        return stop
    form = await request.form()
    if not security.check_csrf(session, form.get("csrf")):
        return back(f"{HERE}/specialists")
    listing = _val(form, "listing", 20)
    note = _val(form, "note", 2000)
    with connect() as conn:
        problem = specialists.set_listing(conn, freelancer_id, listing, note)
        if problem:
            return back(f"{HERE}/specialists?error={problem}")
        audit.record(conn, session, "FL_LISTING_CHANGED", "freelancers",
                     freelancer_id, f"публикация: {listing}")
    journal.event("площадка.профиль.решение", id=freelancer_id, состояние=listing,
                  кто=session["username"])
    return back(f"{HERE}/specialists?listing={_val(form, 'back', 20) or 'pending'}")


# ============================================================
# Категории
# ============================================================

@router.get("/categories", response_class=HTMLResponse)
async def categories(request: Request, error: str = ""):
    session, stop = guard(request)
    if stop:
        return stop
    with connect() as conn:
        tree = taxonomy.category_tree(conn, only_enabled=False)
        tops = [c for c in taxonomy.categories(conn, only_enabled=False)
                if c["parent_id"] is None]
    return page(request, session, "admin/fl_categories.html",
                tree=tree, tops=tops, error=error, sub="categories")


@router.post("/categories")
async def category_save(request: Request):
    session, stop = guard(request)
    if stop:
        return stop
    form = await request.form()
    if not security.check_csrf(session, form.get("csrf")):
        return back(f"{HERE}/categories")
    with connect() as conn:
        _, problem = taxonomy.save_category(
            conn, _int(form, "id"), _val(form, "name", 80),
            _int(form, "parent_id"), int(_val(form, "sort_order", 6) or 0))
        if problem:
            return back(f"{HERE}/categories?error={problem}")
        audit.record(conn, session, "FL_TAXONOMY_CHANGED", "fl_categories",
                     _int(form, "id"), "категория")
    journal.event("площадка.справочник.категория", кто=session["username"])
    return back(f"{HERE}/categories")


@router.post("/categories/{category_id}/toggle")
async def category_toggle(request: Request, category_id: int):
    session, stop = guard(request)
    if stop:
        return stop
    form = await request.form()
    if not security.check_csrf(session, form.get("csrf")):
        return back(f"{HERE}/categories")
    with connect() as conn:
        row = taxonomy.get_category(conn, category_id)
        if row is None:
            return error_page(request, 404)
        taxonomy.set_category_enabled(conn, category_id, not row["enabled"])
        audit.record(conn, session, "FL_TAXONOMY_CHANGED", "fl_categories",
                     category_id, "включена" if not row["enabled"] else "выключена")
    return back(f"{HERE}/categories")


# ============================================================
# Навыки
# ============================================================

@router.get("/skills", response_class=HTMLResponse)
async def skills(request: Request, q: str = "", status: str = "", error: str = ""):
    session, stop = guard(request)
    if stop:
        return stop
    with connect() as conn:
        rows = taxonomy.skills(conn, q, status)
        active = taxonomy.visible_skills(conn)
        cats = [c for c in taxonomy.categories(conn, only_enabled=False)]
        pending = taxonomy.pending_count(conn)
    return page(request, session, "admin/fl_skills.html",
                skills=rows, active_skills=active, categories=cats,
                statuses=taxonomy.SKILL_STATUSES, q=q, status=status,
                pending=pending, error=error, sub="skills")


@router.post("/skills")
async def skill_add(request: Request):
    session, stop = guard(request)
    if stop:
        return stop
    form = await request.form()
    if not security.check_csrf(session, form.get("csrf")):
        return back(f"{HERE}/skills")
    with connect() as conn:
        skill_id = taxonomy.find_or_create_skill(
            conn, _val(form, "name", 60), _int(form, "category_id"))
        if skill_id is None:
            return back(f"{HERE}/skills?error=Название навыка — хотя бы два символа.")
        # Заведённый администратором навык проверять не нужно
        taxonomy.set_skill_status(conn, skill_id, "active")
        audit.record(conn, session, "FL_TAXONOMY_CHANGED", "fl_skills", skill_id,
                     "навык добавлен")
    return back(f"{HERE}/skills")


@router.post("/skills/{skill_id}/status")
async def skill_status(request: Request, skill_id: int):
    session, stop = guard(request)
    if stop:
        return stop
    form = await request.form()
    if not security.check_csrf(session, form.get("csrf")):
        return back(f"{HERE}/skills")
    with connect() as conn:
        if not taxonomy.set_skill_status(conn, skill_id, _val(form, "status", 20)):
            return error_page(request, 404)
        audit.record(conn, session, "FL_TAXONOMY_CHANGED", "fl_skills", skill_id,
                     f"статус: {_val(form, 'status', 20)}")
    return back(f"{HERE}/skills?q={_val(form, 'q', 60)}&status={_val(form, 'back_status', 20)}")


@router.post("/skills/{skill_id}/rename")
async def skill_rename(request: Request, skill_id: int):
    session, stop = guard(request)
    if stop:
        return stop
    form = await request.form()
    if not security.check_csrf(session, form.get("csrf")):
        return back(f"{HERE}/skills")
    with connect() as conn:
        if taxonomy.get_skill(conn, skill_id) is None:
            return error_page(request, 404)
        problem = taxonomy.rename_skill(conn, skill_id, _val(form, "name", 60))
        if problem:
            return back(f"{HERE}/skills?error={problem}")
        audit.record(conn, session, "FL_TAXONOMY_CHANGED", "fl_skills", skill_id,
                     "переименован")
    return back(f"{HERE}/skills")


@router.post("/skills/merge")
async def skill_merge(request: Request):
    """Слить дубликат: связи специалистов переезжают на конечный навык."""
    session, stop = guard(request)
    if stop:
        return stop
    form = await request.form()
    if not security.check_csrf(session, form.get("csrf")):
        return back(f"{HERE}/skills")
    source, target = _int(form, "source_id"), _int(form, "target_id")
    if source is None or target is None:
        return back(f"{HERE}/skills?error=Выберите оба навыка.")
    with connect() as conn:
        problem = taxonomy.merge_skills(conn, source, target)
        if problem:
            return back(f"{HERE}/skills?error={problem}")
        audit.record(conn, session, "FL_TAXONOMY_CHANGED", "fl_skills", source,
                     f"слит с {target}")
    journal.event("площадка.справочник.слияние", из=source, в=target,
                  кто=session["username"])
    return back(f"{HERE}/skills")
