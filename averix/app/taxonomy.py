"""
Справочники площадки: категории и навыки.

Здесь решается одна неприятная задача, из-за которой каталоги
на биржах обычно и превращаются в мусор: люди пишут одно и то же
по-разному. React, react, REACT — для человека одно, для базы три
разные строки, и фильтр по навыку перестаёт работать.

Приём простой: навык опознаётся не по написанию, а по slug. Три
варианта выше дают «react» и попадают в одну строку. То, что slug
не совпал (React.js), администратор сливает вручную — и связи
специалистов при слиянии переезжают, а не теряются.
"""
import sqlite3

from .models import slugify

# Что показываем в фильтрах каталога. Навык со статусом pending уже
# работает в анкете, но в фильтры не лезет: сначала на него посмотрит
# человек. Иначе первая же опечатка станет пунктом меню.
VISIBLE = "active"

SKILL_STATUSES = {
    "pending": "Ждёт проверки",
    "active": "В справочнике",
    "hidden": "Скрыт",
}

MAX_SKILLS_PER_PERSON = 20


# ============================================================
# Категории
# ============================================================

def categories(conn: sqlite3.Connection, only_enabled: bool = True) -> list[dict]:
    sql = "SELECT * FROM fl_categories"
    if only_enabled:
        sql += " WHERE enabled = 1"
    sql += " ORDER BY parent_id IS NOT NULL, sort_order, id"
    return [dict(r) for r in conn.execute(sql)]


def category_tree(conn: sqlite3.Connection, only_enabled: bool = True) -> list[dict]:
    """Верхние категории, у каждой список подкатегорий."""
    rows = categories(conn, only_enabled)
    tops = [dict(r, children=[]) for r in rows if r["parent_id"] is None]
    index = {t["id"]: t for t in tops}
    for row in rows:
        parent = index.get(row["parent_id"])
        if parent is not None:
            parent["children"].append(row)
    return tops


def get_category(conn: sqlite3.Connection, category_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM fl_categories WHERE id = ?",
                        (category_id,)).fetchone()


def _free_slug(conn: sqlite3.Connection, table: str, base: str,
               exclude_id: int | None = None) -> str:
    slug, n = base or "punkt", 2
    while conn.execute(
        f"SELECT 1 FROM {table} WHERE slug = ? AND id IS NOT ?", (slug, exclude_id)
    ).fetchone():
        slug, n = f"{base}-{n}", n + 1
    return slug


def save_category(conn: sqlite3.Connection, category_id: int | None, name: str,
                  parent_id: int | None = None, sort_order: int = 0) -> tuple[int | None, str]:
    """Заводит или переименовывает категорию. Возвращает (номер, ошибка)."""
    name = (name or "").strip()[:80]
    if len(name) < 2:
        return None, "Название категории — хотя бы два символа."
    if parent_id is not None:
        parent = get_category(conn, parent_id)
        if parent is None:
            return None, "Родительская категория не найдена."
        # Два уровня и всё: третий никому не нужен, а дерево с ним
        # начинает требовать рекурсии в каждом запросе
        if parent["parent_id"] is not None:
            return None, "Подкатегория не может быть внутри подкатегории."
    if category_id is None:
        slug = _free_slug(conn, "fl_categories", slugify(name, ""))
        cur = conn.execute(
            "INSERT INTO fl_categories (parent_id, name, slug, sort_order)"
            " VALUES (?,?,?,?)", (parent_id, name, slug, sort_order))
        return int(cur.lastrowid), ""
    if get_category(conn, category_id) is None:
        return None, "Категория не найдена."
    if parent_id == category_id:
        return None, "Категория не может быть родителем самой себе."
    # Адрес не трогаем: по нему уже могли дать ссылку на каталог
    conn.execute(
        "UPDATE fl_categories SET name = ?, parent_id = ?, sort_order = ? WHERE id = ?",
        (name, parent_id, sort_order, category_id))
    return category_id, ""


def set_category_enabled(conn: sqlite3.Connection, category_id: int,
                         enabled: bool) -> None:
    """
    Категорию выключают, а не удаляют.

    На неё уже могут ссылаться профили и проекты; удаление либо порвёт
    их, либо потребует переносить всё вручную прямо сейчас.
    """
    conn.execute("UPDATE fl_categories SET enabled = ? WHERE id = ?",
                 (1 if enabled else 0, category_id))
    if not enabled:
        conn.execute("UPDATE fl_categories SET enabled = 0 WHERE parent_id = ?",
                     (category_id,))


# ============================================================
# Навыки
# ============================================================

def skills(conn: sqlite3.Connection, query: str = "", status: str = "",
           limit: int = 300) -> list[dict]:
    sql = "SELECT s.*, (SELECT COUNT(*) FROM fl_freelancer_skills f" \
          " WHERE f.skill_id = s.id) AS people FROM fl_skills s WHERE 1 = 1"
    args: list = []
    if status in SKILL_STATUSES:
        sql += " AND s.status = ?"
        args.append(status)
    query = (query or "").strip()[:60]
    if query:
        sql += " AND s.name LIKE ? ESCAPE '\\'"
        args.append("%" + query.replace("\\", "\\\\").replace("%", "\\%")
                    .replace("_", "\\_") + "%")
    sql += " ORDER BY s.status = 'pending' DESC, s.name LIMIT ?"
    args.append(max(1, min(int(limit), 1000)))
    return [dict(r) for r in conn.execute(sql, args)]


def visible_skills(conn: sqlite3.Connection) -> list[dict]:
    """Справочник для подсказок и фильтров."""
    return [dict(r) for r in conn.execute(
        "SELECT * FROM fl_skills WHERE status = ? ORDER BY name", (VISIBLE,))]


def get_skill(conn: sqlite3.Connection, skill_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM fl_skills WHERE id = ?", (skill_id,)).fetchone()


def find_or_create_skill(conn: sqlite3.Connection, name: str,
                         category_id: int | None = None) -> int | None:
    """
    Навык по написанию. Разные регистры дают одну строку.

    Новый навык заводится со статусом pending: в анкете он работает
    сразу, в фильтры попадёт после того, как его увидит администратор.
    """
    name = (name or "").strip()[:60]
    if len(name) < 2:
        return None
    slug = slugify(name, "")
    if not slug:
        return None
    row = conn.execute("SELECT id, merged_into_id FROM fl_skills WHERE slug = ?",
                       (slug,)).fetchone()
    if row is not None:
        # Слитый навык подставляем тот, в который слили: иначе связь
        # уедет на строку, которой в справочнике уже нет
        return int(row["merged_into_id"] or row["id"])
    cur = conn.execute(
        "INSERT INTO fl_skills (name, slug, category_id) VALUES (?,?,?)",
        (name, slug, category_id))
    return int(cur.lastrowid)


def set_skill_status(conn: sqlite3.Connection, skill_id: int, status: str) -> bool:
    if status not in SKILL_STATUSES:
        return False
    cur = conn.execute("UPDATE fl_skills SET status = ? WHERE id = ?",
                       (status, skill_id))
    return cur.rowcount > 0


def rename_skill(conn: sqlite3.Connection, skill_id: int, name: str) -> str:
    name = (name or "").strip()[:60]
    if len(name) < 2:
        return "Название навыка — хотя бы два символа."
    slug = _free_slug(conn, "fl_skills", slugify(name, ""), skill_id)
    conn.execute("UPDATE fl_skills SET name = ?, slug = ? WHERE id = ?",
                 (name, slug, skill_id))
    return ""


def merge_skills(conn: sqlite3.Connection, source_id: int, target_id: int) -> str:
    """
    Сливает один навык в другой: все связи переезжают, исходный прячется.

    Возвращает текст ошибки или пустую строку.
    """
    if source_id == target_id:
        return "Навык нельзя слить сам с собой."
    source, target = get_skill(conn, source_id), get_skill(conn, target_id)
    if source is None or target is None:
        return "Навык не найден."
    if target["merged_into_id"]:
        return "Этот навык сам уже слит с другим — выберите конечный."
    # INSERT OR IGNORE, потому что у человека могут быть оба написания:
    # первичный ключ из двух колонок такую пару просто не примет дважды
    conn.execute(
        "INSERT OR IGNORE INTO fl_freelancer_skills (freelancer_id, skill_id)"
        " SELECT freelancer_id, ? FROM fl_freelancer_skills WHERE skill_id = ?",
        (target_id, source_id))
    conn.execute("DELETE FROM fl_freelancer_skills WHERE skill_id = ?", (source_id,))
    conn.execute(
        "UPDATE fl_skills SET merged_into_id = ?, status = 'hidden' WHERE id = ?",
        (target_id, source_id))
    # Если в этот навык раньше слили что-то ещё — переводим цепочку
    # на конечный, чтобы не появлялось «слит в слитый»
    conn.execute("UPDATE fl_skills SET merged_into_id = ? WHERE merged_into_id = ?",
                 (target_id, source_id))
    return ""


# ============================================================
# Навыки специалиста
# ============================================================

def freelancer_skills(conn: sqlite3.Connection, freelancer_id: int) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT s.* FROM fl_freelancer_skills fs"
        " JOIN fl_skills s ON s.id = fs.skill_id"
        " WHERE fs.freelancer_id = ? ORDER BY s.name",
        (freelancer_id,))]


def set_freelancer_skills(conn: sqlite3.Connection, freelancer_id: int,
                          raw: str) -> list[dict]:
    """Принимает строку через запятую, сохраняет связи, возвращает итог."""
    names = [part.strip() for part in (raw or "").replace("\n", ",").split(",")]
    names = [n for n in names if n][:MAX_SKILLS_PER_PERSON]

    ids: list[int] = []
    for name in names:
        skill_id = find_or_create_skill(conn, name)
        if skill_id is not None and skill_id not in ids:
            ids.append(skill_id)

    conn.execute("DELETE FROM fl_freelancer_skills WHERE freelancer_id = ?",
                 (freelancer_id,))
    conn.executemany(
        "INSERT OR IGNORE INTO fl_freelancer_skills (freelancer_id, skill_id)"
        " VALUES (?, ?)", [(freelancer_id, sid) for sid in ids])
    return freelancer_skills(conn, freelancer_id)


def pending_count(conn: sqlite3.Connection) -> int:
    return int(conn.execute(
        "SELECT COUNT(*) FROM fl_skills WHERE status = 'pending'").fetchone()[0])
