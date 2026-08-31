"""
Профиль специалиста площадки, портфолио и публичный каталог.

Одно правило проходит через весь модуль и объясняет половину запросов:

    в каталог попадает только строка с user_id — то есть человек,
    который сам завёл учётную запись и сам согласился показать профиль.

Анкеты из закрытой базы студии (user_id IS NULL) не появляются
в каталоге ни при каких значениях остальных полей. Люди оставляли их
под обещанием «мы никого не публикуем без спроса», и это обещание
не отменяется появлением площадки.
"""
import sqlite3

from . import taxonomy
from .models import slugify

LEVELS = {
    "junior": "Начинающий",
    "middle": "Средний",
    "senior": "Опытный",
    "expert": "Эксперт",
}

LISTINGS = {
    "draft": "Черновик",
    "pending": "Ждёт проверки",
    "published": "В каталоге",
    "rejected": "Отказ в публикации",
}

# Статусы отношений со студией, при которых профиль снимается с показа
# независимо от желания человека
BLOCKED_STATUSES = ("rejected", "archived")

PAGE_SIZE = 12
MAX_PORTFOLIO_ITEMS = 12
MAX_PORTFOLIO_IMAGES = 6


# ============================================================
# Деньги
# ============================================================

MAX_MONEY = 100_000_000  # сто миллионов минорных единиц — потолок от опечаток


def parse_money(raw: str) -> int | None:
    """
    «300», «300.50», «300,50», «1 200» → целое в минорных единицах.

    Дробное здесь не появляется вовсе: в деньгах оно однажды даёт
    0.1 + 0.2 = 0.30000000000000004 прямо в счёте.
    """
    text = (raw or "").strip().replace(" ", "").replace(" ", "").replace(",", ".")
    if not text:
        return None
    negative = text.startswith("-")
    text = text.lstrip("+-")
    if not text or text.count(".") > 1:
        return None
    whole, _, fraction = text.partition(".")
    if not whole.isdigit() or (fraction and not fraction.isdigit()):
        return None
    minor = int(whole) * 100 + int((fraction + "00")[:2] or 0)
    if negative or minor > MAX_MONEY:
        return None
    return minor


def people_word(n: int) -> str:
    """«1 человек», «2 человека», «5 человек» — склонение в одном месте,
    а не выражением из трёх условий посреди шаблона."""
    if 11 <= n % 100 <= 14:
        return "человек"
    last = n % 10
    if last == 1:
        return "человек"
    if 2 <= last <= 4:
        return "человека"
    return "человек"


def format_money(minor: int | None) -> str:
    """Целое в минорных единицах → строка для показа."""
    if minor is None:
        return ""
    whole, rest = divmod(int(minor), 100)
    # Пробел между разрядами: 12000 читается хуже, чем 12 000
    body = f"{whole:,}".replace(",", " ")
    return body if rest == 0 else f"{body},{rest:02d}"


# ============================================================
# Профиль
# ============================================================

def by_user(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM freelancers WHERE user_id = ?",
                        (user_id,)).fetchone()


def by_id(conn: sqlite3.Connection, freelancer_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM freelancers WHERE id = ?",
                        (freelancer_id,)).fetchone()


# Что человек правит сам. Списка достаточно, чтобы ни status, ни listing,
# ни login не проехали через форму: имена колонок берутся отсюда,
# а не из того, что пришло в запросе.
OWN_COLUMNS = (
    "name", "title", "category_id", "level", "about", "years",
    "experience", "city", "country", "telegram", "email",
    "portfolio_url", "github_url", "availability",
    "rate_hour", "rate_project_min",
)


def save_profile(conn: sqlite3.Connection, freelancer_id: int, data: dict) -> None:
    """Пишет только свои поля. Чужие в запрос не попадают вовсе."""
    fields = [c for c in OWN_COLUMNS if c in data]
    if not fields:
        return
    sets = ",".join(f"{c} = ?" for c in fields)
    conn.execute(
        f"UPDATE freelancers SET {sets}, updated_at = datetime('now') WHERE id = ?",
        tuple(data[c] for c in fields) + (freelancer_id,),
    )


def profile_view(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    """Строка профиля вместе с тем, что к ней прицеплено."""
    person = dict(row)
    person["skills"] = taxonomy.freelancer_skills(conn, row["id"])
    person["portfolio"] = portfolio(conn, row["id"])
    person["category"] = None
    if row["category_id"]:
        category = taxonomy.get_category(conn, row["category_id"])
        if category is not None:
            person["category"] = dict(category)
            if category["parent_id"]:
                parent = taxonomy.get_category(conn, category["parent_id"])
                person["parent_category"] = dict(parent) if parent else None
    person["rate_hour_text"] = format_money(row["rate_hour"])
    person["rate_project_text"] = format_money(row["rate_project_min"])
    person["level_label"] = LEVELS.get(row["level"], "")
    return person


# ---------- заполненность ----------

# Что именно считается заполненным. Считается по настоящим полям,
# и человек не может подкрутить это число сам — оно нигде не хранится.
CHECKLIST = (
    ("photo", "Фотография"),
    ("title", "Название профессии"),
    ("category_id", "Направление"),
    ("skills", "Навыки — хотя бы три"),
    ("about", "О себе — хотя бы 120 символов"),
    ("years", "Опыт в годах"),
    ("availability", "Занятость"),
    ("rate", "Ставка или минимальная цена"),
    ("portfolio", "Хотя бы одна работа"),
)


def completeness(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    skills = taxonomy.freelancer_skills(conn, row["id"])
    works = int(conn.execute(
        "SELECT COUNT(*) FROM fl_portfolio WHERE freelancer_id = ?",
        (row["id"],)).fetchone()[0])
    done = {
        "photo": bool(row["photo"]),
        "title": bool((row["title"] or "").strip()),
        "category_id": row["category_id"] is not None,
        "skills": len(skills) >= 3,
        "about": len((row["about"] or "").strip()) >= 120,
        "years": bool((row["years"] or "").strip()),
        "availability": bool(row["availability"]),
        "rate": bool(row["rate_hour"] or row["rate_project_min"]),
        "portfolio": works > 0,
    }
    filled = sum(1 for value in done.values() if value)
    return {
        "percent": round(filled * 100 / len(CHECKLIST)),
        "done": done,
        "missing": [label for key, label in CHECKLIST if not done[key]],
    }


# ---------- публикация ----------

# Без этого профиль в каталоге бесполезен: карточка без профессии,
# направления и рассказа о себе не помогает выбрать человека.
REQUIRED_TO_PUBLISH = ("title", "category_id", "skills", "about")


def can_publish(conn: sqlite3.Connection, row: sqlite3.Row) -> list[str]:
    """Чего не хватает для публикации. Пустой список — можно."""
    state = completeness(conn, row)
    return [label for key, label in CHECKLIST
            if key in REQUIRED_TO_PUBLISH and not state["done"][key]]


def _free_slug(conn: sqlite3.Connection, base: str) -> str:
    slug, n = base or "spec", 2
    while conn.execute("SELECT 1 FROM freelancers WHERE public_slug = ?",
                       (slug,)).fetchone():
        slug, n = f"{base}-{n}", n + 1
    return slug


def request_listing(conn: sqlite3.Connection, freelancer_id: int,
                    wanted: bool) -> str:
    """
    Человек просит показать профиль в каталоге или убрать оттуда.

    Опубликовать себя сам он не может — только попросить. А снять
    с публикации может в любой момент и без спроса: согласие, которое
    нельзя отозвать, — не согласие.
    """
    row = by_id(conn, freelancer_id)
    if row is None:
        return "Профиль не найден."
    if not wanted:
        conn.execute(
            "UPDATE freelancers SET listing = 'draft', updated_at = datetime('now')"
            " WHERE id = ?", (freelancer_id,))
        return ""
    if row["listing"] == "published":
        return ""
    if row["status"] in BLOCKED_STATUSES:
        return "Профиль в архиве. Напишите в студию."
    missing = can_publish(conn, row)
    if missing:
        return "Перед публикацией заполните: " + ", ".join(missing).lower() + "."
    conn.execute(
        "UPDATE freelancers SET listing = 'pending', listed_at = datetime('now'),"
        " updated_at = datetime('now') WHERE id = ?", (freelancer_id,))
    return ""


def set_listing(conn: sqlite3.Connection, freelancer_id: int, listing: str,
                note: str = "") -> str:
    """Решение студии по публикации."""
    if listing not in LISTINGS:
        return "Неизвестное состояние публикации."
    row = by_id(conn, freelancer_id)
    if row is None:
        return "Профиль не найден."
    if listing == "published":
        if row["user_id"] is None:
            # Анкету закрытой базы опубликовать нельзя даже вручную
            return "Это анкета из базы студии, а не профиль площадки."
        if row["status"] in BLOCKED_STATUSES:
            return "Профиль в архиве или с отказом."
        slug = row["public_slug"] or _free_slug(conn, slugify(row["name"], "spec"))
        conn.execute(
            "UPDATE freelancers SET listing = 'published', public_slug = ?,"
            " published_at = COALESCE(published_at, datetime('now')),"
            " updated_at = datetime('now') WHERE id = ?", (slug, freelancer_id))
    else:
        conn.execute(
            "UPDATE freelancers SET listing = ?, updated_at = datetime('now')"
            " WHERE id = ?", (listing, freelancer_id))
    if note:
        conn.execute("UPDATE freelancers SET admin_note = ? WHERE id = ?",
                     (note[:2000], freelancer_id))
    return ""


def pending_count(conn: sqlite3.Connection) -> int:
    return int(conn.execute(
        "SELECT COUNT(*) FROM freelancers WHERE listing = 'pending'").fetchone()[0])


# ============================================================
# Публичный каталог
# ============================================================

# Условие показа собрано один раз и подставляется везде: в список,
# в карточку и в sitemap. Разъехаться они не могут.
_PUBLIC = (
    " f.user_id IS NOT NULL"
    " AND f.listing = 'published'"
    " AND f.public_slug IS NOT NULL"
    " AND f.status NOT IN ('rejected', 'archived')"
    " AND u.status = 'active'"
)
_FROM = " FROM freelancers f JOIN users u ON u.id = f.user_id WHERE" + _PUBLIC

# Сначала свободные, потом занятые. Ни платных мест, ни рейтингов:
# рейтингов пока просто нет, и рисовать их нечем.
_ORDER = (
    " ORDER BY CASE f.availability WHEN 'available' THEN 0"
    "   WHEN 'partially_busy' THEN 1 ELSE 2 END,"
    " f.completed DESC, f.published_at DESC, f.id DESC"
)


def _like(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _filters(query: str, category_id: int | None, level: str,
             availability: str, skill_id: int | None) -> tuple[str, list]:
    sql, args = "", []
    if query:
        sql += (" AND (f.name LIKE ? ESCAPE '\\' OR f.title LIKE ? ESCAPE '\\'"
                " OR f.about LIKE ? ESCAPE '\\' OR f.city LIKE ? ESCAPE '\\')")
        args += [_like(query)] * 4
    if category_id:
        # Направление верхнего уровня захватывает свои специализации
        sql += (" AND (f.category_id = ? OR f.category_id IN"
                " (SELECT id FROM fl_categories WHERE parent_id = ?))")
        args += [category_id, category_id]
    if level in LEVELS:
        sql += " AND f.level = ?"
        args.append(level)
    if availability:
        sql += " AND f.availability = ?"
        args.append(availability)
    if skill_id:
        sql += (" AND EXISTS (SELECT 1 FROM fl_freelancer_skills fs"
                " WHERE fs.freelancer_id = f.id AND fs.skill_id = ?)")
        args.append(skill_id)
    return sql, args


def public_list(conn: sqlite3.Connection, query: str = "",
                category_id: int | None = None, level: str = "",
                availability: str = "", skill_id: int | None = None,
                page: int = 1) -> dict:
    """Страница каталога вместе с общим числом — для постраничности."""
    query = (query or "").strip()[:80]
    where, args = _filters(query, category_id, level, availability, skill_id)

    total = int(conn.execute(
        "SELECT COUNT(*)" + _FROM + where, args).fetchone()[0])
    page = max(1, int(page))
    pages = max(1, -(-total // PAGE_SIZE))
    page = min(page, pages)

    rows = conn.execute(
        "SELECT f.*" + _FROM + where + _ORDER + " LIMIT ? OFFSET ?",
        args + [PAGE_SIZE, (page - 1) * PAGE_SIZE],
    ).fetchall()

    people = []
    for row in rows:
        person = dict(row)
        person["skills"] = taxonomy.freelancer_skills(conn, row["id"])[:6]
        person["level_label"] = LEVELS.get(row["level"], "")
        person["rate_hour_text"] = format_money(row["rate_hour"])
        person["rate_project_text"] = format_money(row["rate_project_min"])
        people.append(person)

    return {"people": people, "total": total, "page": page, "pages": pages}


def public_one(conn: sqlite3.Connection, slug: str) -> dict | None:
    """Карточка по адресу. Условие показа стоит в самом запросе, поэтому
    скрытый профиль не найдётся даже по прямой ссылке."""
    row = conn.execute(
        "SELECT f.*" + _FROM + " AND f.public_slug = ?", (slug,)).fetchone()
    return profile_view(conn, row) if row is not None else None


def public_slugs(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Для sitemap — тем же условием, что и сам каталог."""
    return conn.execute(
        "SELECT f.public_slug, f.updated_at" + _FROM + _ORDER).fetchall()


def catalog_facets(conn: sqlite3.Connection) -> dict:
    """Что вообще есть в каталоге — чтобы не показывать пустые фильтры."""
    rows = conn.execute(
        "SELECT f.category_id, f.level, f.availability" + _FROM).fetchall()
    categories: dict[int, int] = {}
    levels: dict[str, int] = {}
    for row in rows:
        if row["category_id"]:
            categories[row["category_id"]] = categories.get(row["category_id"], 0) + 1
        levels[row["level"]] = levels.get(row["level"], 0) + 1
    return {"categories": categories, "levels": levels, "total": len(rows)}


# ============================================================
# Портфолио
# ============================================================

PORTFOLIO_COLUMNS = ("title", "description", "category_id", "tech", "url")


def portfolio(conn: sqlite3.Connection, freelancer_id: int) -> list[dict]:
    items = [dict(r) for r in conn.execute(
        "SELECT * FROM fl_portfolio WHERE freelancer_id = ?"
        " ORDER BY sort_order, id", (freelancer_id,))]
    for item in items:
        item["images"] = [dict(r) for r in conn.execute(
            "SELECT * FROM fl_portfolio_images WHERE item_id = ?"
            " ORDER BY sort_order, id", (item["id"],))]
        item["cover"] = item["images"][0]["filename"] if item["images"] else None
    return items


def portfolio_item(conn: sqlite3.Connection, item_id: int,
                   freelancer_id: int) -> dict | None:
    """
    Работа по номеру — но только своя.

    Владелец стоит в самом запросе, а не в проверке после выборки:
    чужая работа не попадёт в данные даже при ошибке в шаблоне.
    """
    row = conn.execute(
        "SELECT * FROM fl_portfolio WHERE id = ? AND freelancer_id = ?",
        (item_id, freelancer_id)).fetchone()
    if row is None:
        return None
    item = dict(row)
    item["images"] = [dict(r) for r in conn.execute(
        "SELECT * FROM fl_portfolio_images WHERE item_id = ? ORDER BY sort_order, id",
        (item_id,))]
    return item


def save_portfolio_item(conn: sqlite3.Connection, item_id: int | None,
                        freelancer_id: int, data: dict) -> tuple[int | None, str]:
    title = (data.get("title") or "").strip()[:120]
    if len(title) < 2:
        return None, "Название работы — хотя бы два символа."
    values = {
        "title": title,
        "description": (data.get("description") or "").strip()[:2000],
        "category_id": data.get("category_id"),
        "tech": (data.get("tech") or "").strip()[:300],
        "url": (data.get("url") or "").strip()[:300],
    }
    if item_id is None:
        count = int(conn.execute(
            "SELECT COUNT(*) FROM fl_portfolio WHERE freelancer_id = ?",
            (freelancer_id,)).fetchone()[0])
        if count >= MAX_PORTFOLIO_ITEMS:
            return None, f"Больше {MAX_PORTFOLIO_ITEMS} работ добавить нельзя."
        cur = conn.execute(
            "INSERT INTO fl_portfolio (freelancer_id, title, description,"
            " category_id, tech, url, sort_order) VALUES (?,?,?,?,?,?,?)",
            (freelancer_id, values["title"], values["description"],
             values["category_id"], values["tech"], values["url"], count))
        return int(cur.lastrowid), ""
    if portfolio_item(conn, item_id, freelancer_id) is None:
        return None, "Работа не найдена."
    conn.execute(
        "UPDATE fl_portfolio SET title = ?, description = ?, category_id = ?,"
        " tech = ?, url = ?, updated_at = datetime('now')"
        " WHERE id = ? AND freelancer_id = ?",
        (values["title"], values["description"], values["category_id"],
         values["tech"], values["url"], item_id, freelancer_id))
    return item_id, ""


def delete_portfolio_item(conn: sqlite3.Connection, item_id: int,
                          freelancer_id: int) -> list[str]:
    """Удаляет свою работу. Возвращает файлы, которые надо стереть с диска."""
    item = portfolio_item(conn, item_id, freelancer_id)
    if item is None:
        return []
    files = [image["filename"] for image in item["images"]]
    conn.execute("DELETE FROM fl_portfolio WHERE id = ? AND freelancer_id = ?",
                 (item_id, freelancer_id))
    return files


def add_portfolio_image(conn: sqlite3.Connection, item_id: int,
                        freelancer_id: int, saved) -> str:
    if portfolio_item(conn, item_id, freelancer_id) is None:
        return "Работа не найдена."
    count = int(conn.execute(
        "SELECT COUNT(*) FROM fl_portfolio_images WHERE item_id = ?",
        (item_id,)).fetchone()[0])
    if count >= MAX_PORTFOLIO_IMAGES:
        return f"У одной работы не больше {MAX_PORTFOLIO_IMAGES} картинок."
    conn.execute(
        "INSERT INTO fl_portfolio_images (item_id, filename, width, height,"
        " bytes, sort_order) VALUES (?,?,?,?,?,?)",
        (item_id, saved.filename, saved.width, saved.height, saved.bytes, count))
    return ""


def delete_portfolio_image(conn: sqlite3.Connection, image_id: int,
                           freelancer_id: int) -> str | None:
    """Картинка должна принадлежать работе этого человека."""
    row = conn.execute(
        "SELECT i.id, i.filename FROM fl_portfolio_images i"
        " JOIN fl_portfolio p ON p.id = i.item_id"
        " WHERE i.id = ? AND p.freelancer_id = ?",
        (image_id, freelancer_id)).fetchone()
    if row is None:
        return None
    conn.execute("DELETE FROM fl_portfolio_images WHERE id = ?", (image_id,))
    return row["filename"]
