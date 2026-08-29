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
