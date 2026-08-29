"""Работа с проектами. Только подготовленные выражения — строки в SQL не склеиваются."""
import re
import sqlite3

CATEGORIES = {
    "web": "Web",
    "telegram-bot": "Telegram Bot",
    "backend": "Backend & API",
    "automation": "Automation",
    "ai": "AI",
}

# Поля, которые пользователь заполняет в форме. Список задаёт и порядок
# колонок в запросах, поэтому добавлять новое поле нужно только сюда.
TEXT_FIELDS = [
    "title_ru", "title_tj", "excerpt_ru", "excerpt_tj", "body_ru", "body_tj",
    "task_ru", "task_tj", "solution_ru", "solution_tj",
    "features_ru", "features_tj", "result_ru", "result_tj",
    "seo_title_ru", "seo_title_tj", "seo_description_ru", "seo_description_tj",
    "project_url", "github_url",
]

_TRANSLIT = {
    "а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"e","ж":"zh","з":"z","и":"i",
    "й":"y","к":"k","л":"l","м":"m","н":"n","о":"o","п":"p","р":"r","с":"s","т":"t",
    "у":"u","ф":"f","х":"h","ц":"c","ч":"ch","ш":"sh","щ":"sch","ъ":"","ы":"y","ь":"",
    "э":"e","ю":"yu","я":"ya",
    "ғ":"g","ӣ":"i","қ":"q","ӯ":"u","ҳ":"h","ҷ":"j",
}


def slugify(text: str) -> str:
    out = "".join(_TRANSLIT.get(ch, ch) for ch in (text or "").lower())
    out = re.sub(r"[^a-z0-9]+", "-", out).strip("-")
    return out[:80] or "proekt"


def unique_slug(conn: sqlite3.Connection, base: str, exclude_id: int | None = None) -> str:
    slug, n = base, 2
    while True:
        row = conn.execute(
            "SELECT id FROM projects WHERE slug = ? AND id IS NOT ?", (slug, exclude_id)
        ).fetchone()
        if row is None:
            return slug
        slug, n = f"{base}-{n}", n + 1


# ---------- чтение ----------

def list_projects(conn: sqlite3.Connection, status: str | None = None) -> list[sqlite3.Row]:
    sql = ("SELECT p.*, i.filename AS cover FROM projects p"
           " LEFT JOIN project_images i ON i.id = p.cover_image_id")
    args: tuple = ()
    if status:
        sql += " WHERE p.status = ?"
        args = (status,)
    sql += " ORDER BY p.sort_order, p.created_at DESC"
    return conn.execute(sql, args).fetchall()


def get_project(conn: sqlite3.Connection, project_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()


def counts(conn: sqlite3.Connection) -> dict:
    r = conn.execute(
        "SELECT COUNT(*) AS total,"
        " COALESCE(SUM(status = 'published'), 0) AS published,"
        " COALESCE(SUM(status = 'draft'), 0) AS draft FROM projects"
    ).fetchone()
    return {"total": r["total"], "published": r["published"], "draft": r["draft"]}


def images(conn: sqlite3.Connection, project_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM project_images WHERE project_id = ? ORDER BY sort_order, id",
        (project_id,),
    ).fetchall()


def tech(conn: sqlite3.Connection, project_id: int) -> list[str]:
    return [r["name"] for r in conn.execute(
        "SELECT name FROM project_tech WHERE project_id = ? ORDER BY sort_order, id",
        (project_id,),
    )]


# ---------- запись ----------

def create_project(conn: sqlite3.Connection, data: dict) -> int:
    cols = ["slug", "category", "year", "featured", "status", "sort_order"] + TEXT_FIELDS
    marks = ",".join("?" * len(cols))
    cur = conn.execute(
        f"INSERT INTO projects ({','.join(cols)}) VALUES ({marks})",
        tuple(data.get(c) for c in cols),
    )
    return int(cur.lastrowid)


def update_project(conn: sqlite3.Connection, project_id: int, data: dict) -> None:
    cols = ["slug", "category", "year", "featured", "status", "sort_order"] + TEXT_FIELDS
    sets = ",".join(f"{c} = ?" for c in cols)
    conn.execute(
        f"UPDATE projects SET {sets}, updated_at = datetime('now') WHERE id = ?",
        tuple(data.get(c) for c in cols) + (project_id,),
    )


def delete_project(conn: sqlite3.Connection, project_id: int) -> list[str]:
    """Удаляет проект. Возвращает имена файлов, которые надо стереть с диска."""
    files = [r["filename"] for r in conn.execute(
        "SELECT filename FROM project_images WHERE project_id = ?", (project_id,)
    )]
    # обложка ссылается на картинку, картинка на проект: снимаем ссылку,
    # иначе внешний ключ не даст удалить
    conn.execute("UPDATE projects SET cover_image_id = NULL WHERE id = ?", (project_id,))
    conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    return files


def set_tech(conn: sqlite3.Connection, project_id: int, raw: str) -> None:
    names = [n.strip()[:40] for n in re.split(r"[,\n]", raw or "") if n.strip()][:20]
    conn.execute("DELETE FROM project_tech WHERE project_id = ?", (project_id,))
    conn.executemany(
        "INSERT INTO project_tech (project_id, name, sort_order) VALUES (?,?,?)",
        [(project_id, n, i) for i, n in enumerate(names)],
    )


def add_image(conn: sqlite3.Connection, project_id: int, saved, alt_ru: str = "") -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(sort_order), -1) + 1 AS n FROM project_images WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    cur = conn.execute(
        "INSERT INTO project_images (project_id, filename, alt_ru, width, height, bytes, sort_order)"
        " VALUES (?,?,?,?,?,?,?)",
        (project_id, saved.filename, alt_ru, saved.width, saved.height, saved.bytes, row["n"]),
    )
    image_id = int(cur.lastrowid)
    # первая картинка сразу становится обложкой
    conn.execute(
        "UPDATE projects SET cover_image_id = ? WHERE id = ? AND cover_image_id IS NULL",
        (image_id, project_id),
    )
    return image_id


def delete_image(conn: sqlite3.Connection, image_id: int) -> str | None:
    row = conn.execute(
        "SELECT filename, project_id FROM project_images WHERE id = ?", (image_id,)
    ).fetchone()
    if row is None:
        return None
    conn.execute(
        "UPDATE projects SET cover_image_id = NULL WHERE cover_image_id = ?", (image_id,)
    )
    conn.execute("DELETE FROM project_images WHERE id = ?", (image_id,))
    # обложкой становится следующая оставшаяся
    nxt = conn.execute(
        "SELECT id FROM project_images WHERE project_id = ? ORDER BY sort_order LIMIT 1",
        (row["project_id"],),
    ).fetchone()
    if nxt:
        conn.execute(
            "UPDATE projects SET cover_image_id = ? WHERE id = ? AND cover_image_id IS NULL",
            (nxt["id"], row["project_id"]),
        )
    return row["filename"]


def set_cover(conn: sqlite3.Connection, project_id: int, image_id: int) -> bool:
    """Обложкой можно назначить только картинку этого же проекта."""
    row = conn.execute(
        "SELECT id FROM project_images WHERE id = ? AND project_id = ?",
        (image_id, project_id),
    ).fetchone()
    if row is None:
        return False
    conn.execute("UPDATE projects SET cover_image_id = ? WHERE id = ?", (image_id, project_id))
    return True


def move_project(conn: sqlite3.Connection, project_id: int, direction: int) -> None:
    """Меняет проект местами с соседом по порядку."""
    rows = list_projects(conn)
    order = [r["id"] for r in rows]
    if project_id not in order:
        return
    i = order.index(project_id)
    j = i + direction
    if not 0 <= j < len(order):
        return
    order[i], order[j] = order[j], order[i]
    conn.executemany(
        "UPDATE projects SET sort_order = ? WHERE id = ?",
        [(pos, pid) for pos, pid in enumerate(order)],
    )


# ============================================================
# Настройки сайта
# ============================================================

def settings(conn: sqlite3.Connection, lang: str = "ru") -> dict:
    """Плоский словарь ключ → значение на нужном языке.

    Таджикский пустой — отдаём русский. Машинного перевода нет.
    """
    out: dict[str, str] = {}
    for row in conn.execute("SELECT key, value_ru, value_tj FROM site_settings"):
        value = row["value_tj"] if lang == "tg" and row["value_tj"] else row["value_ru"]
        out[row["key"]] = value or ""
    return out


# Показатели на главной. Ключ задаёт четвёрку настроек:
# <ключ> — число, <ключ>_on — показывать ли, _unit — знак после числа,
# _label — подпись. Цифру, которую нечем подтвердить, админ выключает.
STAT_KEYS = ("stat_years", "stat_active", "stat_accepted")


def visible_stats(settings_map: dict) -> list[dict]:
    out = []
    for key in STAT_KEYS:
        if settings_map.get(f"{key}_on") != "1":
            continue
        value = (settings_map.get(key) or "").strip()
        if not value:
            continue
        out.append({
            "value": value,
            "unit": settings_map.get(f"{key}_unit") or "",
            "label": settings_map.get(f"{key}_label") or "",
        })
    return out


def all_settings(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM site_settings ORDER BY key").fetchall()


def save_setting(conn: sqlite3.Connection, key: str, ru: str, tj: str) -> None:
    conn.execute(
        "UPDATE site_settings SET value_ru = ?, value_tj = ?, updated_at = datetime('now')"
        " WHERE key = ?",
        (ru, tj, key),
    )


# ============================================================
# Публичная часть: проекты
# ============================================================

def _localize(row: sqlite3.Row, lang: str, fields: tuple[str, ...]) -> dict:
    """Собирает запись на нужном языке с откатом на русский."""
    out = dict(row)
    for f in fields:
        tj = row[f"{f}_tj"] if f"{f}_tj" in row.keys() else None
        out[f] = (tj if lang == "tg" and tj else row[f"{f}_ru"]) or ""
    return out


PUBLIC_FIELDS = ("title", "excerpt", "body", "task", "solution", "features", "result",
                 "seo_title", "seo_description")


def public_projects(conn: sqlite3.Connection, lang: str = "ru",
                    category: str | None = None, featured_only: bool = False,
                    limit: int | None = None) -> list[dict]:
    sql = ("SELECT p.*, i.filename AS cover, i.width AS cover_w, i.height AS cover_h"
           " FROM projects p LEFT JOIN project_images i ON i.id = p.cover_image_id"
           " WHERE p.status = 'published'")
    args: list = []
    if category:
        sql += " AND p.category = ?"
        args.append(category)
    if featured_only:
        sql += " AND p.featured = 1"
    sql += " ORDER BY p.sort_order, p.created_at DESC"
    if limit:
        sql += " LIMIT ?"
        args.append(limit)

    out = []
    for row in conn.execute(sql, tuple(args)):
        item = _localize(row, lang, PUBLIC_FIELDS)
        item["category_label"] = CATEGORIES.get(row["category"], row["category"])
        item["tech"] = tech(conn, row["id"])
        out.append(item)
    return out


def public_project(conn: sqlite3.Connection, slug: str, lang: str = "ru") -> dict | None:
    row = conn.execute(
        "SELECT p.*, i.filename AS cover, i.width AS cover_w, i.height AS cover_h"
        " FROM projects p LEFT JOIN project_images i ON i.id = p.cover_image_id"
        " WHERE p.slug = ? AND p.status = 'published'",
        (slug,),
    ).fetchone()
    if row is None:
        return None
    item = _localize(row, lang, PUBLIC_FIELDS)
    item["category_label"] = CATEGORIES.get(row["category"], row["category"])
    item["tech"] = tech(conn, row["id"])
    item["gallery"] = [
        dict(r, alt=(r["alt_tj"] if lang == "tg" and r["alt_tj"] else r["alt_ru"]) or "")
        for r in images(conn, row["id"])
    ]
    return item


def neighbour_project(conn: sqlite3.Connection, current: dict, lang: str = "ru") -> dict | None:
    """Следующий опубликованный проект по порядку, по кругу."""
    rows = conn.execute(
        "SELECT slug, title_ru, title_tj FROM projects WHERE status = 'published'"
        " ORDER BY sort_order, created_at DESC"
    ).fetchall()
    if len(rows) < 2:
        return None
    slugs = [r["slug"] for r in rows]
    try:
        i = slugs.index(current["slug"])
    except ValueError:
        return None
    nxt = rows[(i + 1) % len(rows)]
    title = (nxt["title_tj"] if lang == "tg" and nxt["title_tj"] else nxt["title_ru"])
    return {"slug": nxt["slug"], "title": title}


def used_categories(conn: sqlite3.Connection) -> list[str]:
    return [r["category"] for r in conn.execute(
        "SELECT DISTINCT category FROM projects WHERE status = 'published'"
    )]


# ============================================================
# Команда
# ============================================================

TEAM_FIELDS = ("position", "bio")


def public_team(conn: sqlite3.Connection, lang: str = "ru") -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM team_members WHERE visible = 1 ORDER BY sort_order, id"
    ).fetchall()
    return [_localize(r, lang, TEAM_FIELDS) for r in rows]


def all_team(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM team_members ORDER BY sort_order, id").fetchall()


def get_member(conn: sqlite3.Connection, member_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM team_members WHERE id = ?", (member_id,)).fetchone()


TEAM_COLUMNS = ["name", "position_ru", "position_tj", "bio_ru", "bio_tj", "photo",
                "telegram", "github", "linkedin", "website", "visible", "sort_order"]


def save_member(conn: sqlite3.Connection, member_id: int | None, data: dict) -> int:
    if member_id is None:
        marks = ",".join("?" * len(TEAM_COLUMNS))
        cur = conn.execute(
            f"INSERT INTO team_members ({','.join(TEAM_COLUMNS)}) VALUES ({marks})",
            tuple(data.get(c) for c in TEAM_COLUMNS),
        )
        return int(cur.lastrowid)
    sets = ",".join(f"{c} = ?" for c in TEAM_COLUMNS)
    conn.execute(
        f"UPDATE team_members SET {sets}, updated_at = datetime('now') WHERE id = ?",
        tuple(data.get(c) for c in TEAM_COLUMNS) + (member_id,),
    )
    return member_id


def delete_member(conn: sqlite3.Connection, member_id: int) -> str | None:
    row = conn.execute("SELECT photo FROM team_members WHERE id = ?", (member_id,)).fetchone()
    conn.execute("DELETE FROM team_members WHERE id = ?", (member_id,))
    return row["photo"] if row else None


# ============================================================
# Вакансии
# ============================================================

WORK_TYPES = {"remote": "Удалённо", "office": "В офисе", "hybrid": "Гибрид"}
EMPLOYMENT = {"full": "Полная занятость", "part": "Частичная", "project": "Проектно"}
VACANCY_FIELDS = ("title", "description", "requirements")
VACANCY_COLUMNS = ["title_ru", "title_tj", "description_ru", "description_tj",
                   "requirements_ru", "requirements_tj", "location", "work_type",
                   "employment", "status", "sort_order"]


def open_vacancies(conn: sqlite3.Connection, lang: str = "ru") -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM vacancies WHERE status = 'open' ORDER BY sort_order, id"
    ).fetchall()
    out = []
    for r in rows:
        item = _localize(r, lang, VACANCY_FIELDS)
        item["work_label"] = WORK_TYPES.get(r["work_type"], r["work_type"])
        item["employment_label"] = EMPLOYMENT.get(r["employment"], r["employment"])
        out.append(item)
    return out


def all_vacancies(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM vacancies ORDER BY sort_order, id").fetchall()


def get_vacancy(conn: sqlite3.Connection, vacancy_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM vacancies WHERE id = ?", (vacancy_id,)).fetchone()


def save_vacancy(conn: sqlite3.Connection, vacancy_id: int | None, data: dict) -> int:
    if vacancy_id is None:
        marks = ",".join("?" * len(VACANCY_COLUMNS))
        cur = conn.execute(
            f"INSERT INTO vacancies ({','.join(VACANCY_COLUMNS)}) VALUES ({marks})",
            tuple(data.get(c) for c in VACANCY_COLUMNS),
        )
        return int(cur.lastrowid)
    sets = ",".join(f"{c} = ?" for c in VACANCY_COLUMNS)
    conn.execute(
        f"UPDATE vacancies SET {sets}, updated_at = datetime('now') WHERE id = ?",
        tuple(data.get(c) for c in VACANCY_COLUMNS) + (vacancy_id,),
    )
    return vacancy_id


# ============================================================
# Заявки
# ============================================================

REQUEST_TYPES = {
    "website": "Сайт или лендинг",
    "bot": "Telegram-бот",
    "backend": "Backend или API",
    "automation": "Автоматизация",
    "ai": "AI-функции",
    "other": "Другое",
}
REQUEST_STATUSES = {
    "new": "Новая",
    "contacted": "Связались",
    "estimate_sent": "Отправили расчёт",
    "in_progress": "В работе",
    "won": "Взяли",
    "closed": "Закрыта",
    "spam": "Спам",
}
JOB_STATUSES = {
    "new": "Новая", "viewed": "Просмотрена", "interview": "Собеседование",
    "accepted": "Принят", "rejected": "Отказ",
}


def add_client_request(conn: sqlite3.Connection, data: dict) -> int:
    cols = ["name", "telegram", "email", "project_type", "budget", "message", "ip"]
    cur = conn.execute(
        f"INSERT INTO client_requests ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
        tuple(data.get(c) for c in cols),
    )
    return int(cur.lastrowid)


def add_job_application(conn: sqlite3.Connection, data: dict) -> int:
    cols = ["vacancy_id", "name", "telegram", "email", "country", "direction",
            "experience", "skills", "portfolio_url", "github_url", "message", "ip"]
    cur = conn.execute(
        f"INSERT INTO job_applications ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
        tuple(data.get(c) for c in cols),
    )
    return int(cur.lastrowid)


# Список закрытый намеренно: имя таблицы подставляется в запрос
# как текст, и без него сюда можно было бы передать что угодно.
RATE_LIMITED = ("client_requests", "job_applications", "freelancers")


def recent_from_ip(conn: sqlite3.Connection, table: str, ip: str, minutes: int = 10) -> int:
    """Сколько заявок пришло с этого адреса за последние минуты."""
    if table not in RATE_LIMITED:
        raise ValueError("неизвестная таблица")
    row = conn.execute(
        f"SELECT COUNT(*) AS n FROM {table}"
        f" WHERE ip = ? AND created_at > datetime('now', ?)",
        (ip, f"-{int(minutes)} minutes"),
    ).fetchone()
    return int(row["n"])


def list_requests(conn: sqlite3.Connection, table: str) -> list[sqlite3.Row]:
    if table not in ("client_requests", "job_applications"):
        raise ValueError("неизвестная таблица")
    return conn.execute(f"SELECT * FROM {table} ORDER BY created_at DESC").fetchall()


def set_request_status(conn: sqlite3.Connection, table: str, item_id: int,
                       status: str, note: str) -> bool:
    allowed = REQUEST_STATUSES if table == "client_requests" else JOB_STATUSES
    if table not in ("client_requests", "job_applications") or status not in allowed:
        return False
    conn.execute(
        f"UPDATE {table} SET status = ?, admin_note = ?, updated_at = datetime('now')"
        " WHERE id = ?",
        (status, note[:2000], item_id),
    )
    return True


def dashboard_counts(conn: sqlite3.Connection) -> dict:
    def one(sql: str) -> int:
        return int(conn.execute(sql).fetchone()[0])
    return {
        **counts(conn),
        "team": one("SELECT COUNT(*) FROM team_members WHERE visible = 1"),
        "vacancies": one("SELECT COUNT(*) FROM vacancies WHERE status = 'open'"),
        "jobs_new": one("SELECT COUNT(*) FROM job_applications WHERE status = 'new'"),
        "requests_new": one("SELECT COUNT(*) FROM client_requests WHERE status = 'new'"),
    }
