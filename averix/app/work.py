"""
Запросы к базе для фрилансеров, клиентских проектов и задач.

Вынесено из models.py: там публичная часть сайта, здесь — внутренняя
работа студии. Пересекаются они только в одном месте — когда админ
принимает отклик и заводит человека в команду.
"""
import secrets
import sqlite3

from . import security

# ============================================================
# Справочники
# ============================================================

SPECIALIZATIONS = {
    "frontend": "Frontend",
    "backend": "Backend",
    "fullstack": "Fullstack",
    "bots": "Telegram-боты",
    "mobile": "Мобильная разработка",
    "design": "UI/UX дизайн",
    "qa": "Тестирование",
    "devops": "DevOps",
    "ai": "AI",
    "other": "Другое",
}

AVAILABILITY = {
    "available": "Свободен",
    "partially_busy": "Частично занят",
    "busy": "Занят",
}

RATE_TYPES = {"hour": "за час", "project": "за проект"}

FREELANCER_STATUSES = {
    "new": "Новая анкета",
    "reviewing": "Смотрим",
    "approved": "Одобрен",
    "rejected": "Отказ",
    "active": "В работе",
    "busy": "Занят",
    "archived": "В архиве",
}

# Кому можно выдать вход в кабинет. Анкета со статусом «новая»
# доступа не получает никогда — сначала её должен посмотреть человек.
CAN_LOG_IN = ("approved", "active", "busy")

CLIENT_PROJECT_STATUSES = {
    "new": "Новый",
    "planning": "Планирование",
    "in_progress": "В работе",
    "review": "На проверке",
    "completed": "Завершён",
    "cancelled": "Отменён",
}

TASK_STATUSES = {
    "todo": "Не начата",
    "assigned": "Назначена",
    "in_progress": "В работе",
    "review": "На проверке",
    "revision": "На доработке",
    "completed": "Завершена",
    "cancelled": "Отменена",
}

# Кто и куда может двигать задачу. Ключ — роль, значение — из чего во что.
# Завершить задачу может только админ: иначе исполнитель закрывал бы
# собственную работу сам.
FREELANCER_MOVES = {
    "assigned": ("in_progress",),
    "revision": ("in_progress",),
    "in_progress": ("review",),
}
ADMIN_MOVES = {
    "todo": ("assigned", "cancelled"),
    "assigned": ("todo", "in_progress", "cancelled"),
    "in_progress": ("review", "cancelled"),
    "review": ("completed", "revision", "cancelled"),
    "revision": ("in_progress", "cancelled"),
    "completed": ("review",),
    "cancelled": ("todo",),
}


# ============================================================
# Фрилансеры
# ============================================================

FREELANCER_COLUMNS = [
    "name", "telegram", "email", "country", "city", "specialization",
    "skills", "experience", "years", "about", "portfolio_url", "github_url",
    "cv_file", "photo", "rate", "rate_type", "availability", "status",
    "admin_note", "login",
]


# У этих колонок в базе стоит NOT NULL DEFAULT, но явно переданный NULL
# умолчание не включает — приводим значения перед записью.
_FREELANCER_DEFAULTS = {
    "specialization": ("other", SPECIALIZATIONS),
    "rate_type": ("hour", RATE_TYPES),
    "availability": ("available", AVAILABILITY),
    "status": ("new", FREELANCER_STATUSES),
}


def _normalize_freelancer(data: dict) -> dict:
    for key, (default, allowed) in _FREELANCER_DEFAULTS.items():
        if data.get(key) not in allowed:
            data[key] = default
    return data


def add_freelancer(conn: sqlite3.Connection, data: dict) -> int:
    _normalize_freelancer(data)
    cols = ["name", "telegram", "email", "country", "city", "specialization",
            "skills", "experience", "years", "about", "portfolio_url",
            "github_url", "cv_file", "rate", "rate_type", "availability", "ip"]
    cur = conn.execute(
        f"INSERT INTO freelancers ({','.join(cols)})"
        f" VALUES ({','.join('?' * len(cols))})",
        tuple(data.get(c) for c in cols),
    )
    return int(cur.lastrowid)


def list_freelancers(conn: sqlite3.Connection, status: str = "") -> list[sqlite3.Row]:
    sql = "SELECT * FROM freelancers"
    args: tuple = ()
    if status in FREELANCER_STATUSES:
        sql += " WHERE status = ?"
        args = (status,)
    sql += " ORDER BY created_at DESC"
    return conn.execute(sql, args).fetchall()


def get_freelancer(conn: sqlite3.Connection, freelancer_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM freelancers WHERE id = ?", (freelancer_id,)
    ).fetchone()


def save_freelancer(conn: sqlite3.Connection, freelancer_id: int, data: dict) -> None:
    _normalize_freelancer(data)
    sets = ",".join(f"{c} = ?" for c in FREELANCER_COLUMNS)
    conn.execute(
        f"UPDATE freelancers SET {sets}, updated_at = datetime('now') WHERE id = ?",
        tuple(data.get(c) for c in FREELANCER_COLUMNS) + (freelancer_id,),
    )


def set_freelancer_status(conn: sqlite3.Connection, freelancer_id: int,
                          status: str, note: str = "") -> bool:
    if status not in FREELANCER_STATUSES:
        return False
    conn.execute(
        "UPDATE freelancers SET status = ?, admin_note = ?,"
        " updated_at = datetime('now') WHERE id = ?",
        (status, note[:2000], freelancer_id),
    )
    return conn.total_changes > 0


def set_freelancer_login(conn: sqlite3.Connection, freelancer_id: int,
                         login: str, password: str) -> str | None:
    """Заводит вход в кабинет. Возвращает текст ошибки или None."""
    login = login.strip().lower()
    if len(login) < 3:
        return "Логин должен быть не короче трёх символов."
    if len(password) < 10:
        return "Пароль должен быть не короче десяти символов."
    row = get_freelancer(conn, freelancer_id)
    if row is None:
        return "Специалист не найден."
    if row["status"] not in CAN_LOG_IN:
        return "Сначала одобрите анкету — только потом можно выдать доступ."
    taken = conn.execute(
        "SELECT 1 FROM freelancers WHERE login = ? AND id <> ?",
        (login, freelancer_id),
    ).fetchone()
    if taken:
        return "Такой логин уже занят."
    conn.execute(
        "UPDATE freelancers SET login = ?, password_hash = ?,"
        " updated_at = datetime('now') WHERE id = ?",
        (login, security.hash_password(password), freelancer_id),
    )
    return None


def approved_freelancers(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    marks = ",".join("?" * len(CAN_LOG_IN))
    return conn.execute(
        f"SELECT * FROM freelancers WHERE status IN ({marks})"
        " ORDER BY name",
        CAN_LOG_IN,
    ).fetchall()


# ============================================================
# Вход фрилансера
# ============================================================

SESSION_HOURS = 12


def freelancer_login(conn: sqlite3.Connection, login: str, password: str):
    """Возвращает строку фрилансера или None. Разницы между «нет такого
    логина» и «неверный пароль» снаружи не видно — иначе по ответу
    можно было бы перебирать существующие логины."""
    row = conn.execute(
        "SELECT * FROM freelancers WHERE login = ?", (login.strip().lower(),)
    ).fetchone()
    if row is None or not row["password_hash"]:
        # Считаем хеш вхолостую, чтобы несуществующий логин отвечал
        # столько же времени, сколько существующий
        security.verify_password("x" * 20, security.hash_password("y" * 20))
        return None
    if not security.verify_password(password, row["password_hash"]):
        return None
    if row["status"] not in CAN_LOG_IN:
        return None
    return row


def create_freelancer_session(conn: sqlite3.Connection, freelancer_id: int) -> str:
    token = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO freelancer_sessions (token_hash, freelancer_id, csrf_token, expires_at)"
        f" VALUES (?, ?, ?, datetime('now', '+{SESSION_HOURS} hours'))",
        (security._token_hash(token), freelancer_id, secrets.token_urlsafe(24)),
    )
    return token


def get_freelancer_session(conn: sqlite3.Connection, token: str | None):
    if not token:
        return None
    return conn.execute(
        "SELECT s.token_hash, s.csrf_token, f.* FROM freelancer_sessions s"
        " JOIN freelancers f ON f.id = s.freelancer_id"
        " WHERE s.token_hash = ? AND s.expires_at > datetime('now')",
        (security._token_hash(token),),
    ).fetchone()


def destroy_freelancer_session(conn: sqlite3.Connection, token: str | None) -> None:
    if token:
        conn.execute("DELETE FROM freelancer_sessions WHERE token_hash = ?",
                     (security._token_hash(token),))


def purge_freelancer_sessions(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM freelancer_sessions WHERE expires_at <= datetime('now')")


# ============================================================
# Клиентские проекты
# ============================================================

CLIENT_PROJECT_COLUMNS = ["title", "client", "description", "budget",
                          "deadline", "status", "admin_note"]


def list_client_projects(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT p.*,"
        " (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id) AS tasks_total,"
        " (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id"
        "    AND t.status = 'completed') AS tasks_done"
        " FROM client_projects p ORDER BY p.created_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def get_client_project(conn: sqlite3.Connection, project_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM client_projects WHERE id = ?", (project_id,)
    ).fetchone()


def save_client_project(conn: sqlite3.Connection, project_id: int | None,
                        data: dict) -> int:
    if data.get("status") not in CLIENT_PROJECT_STATUSES:
        data["status"] = "new"
    if project_id is None:
        marks = ",".join("?" * len(CLIENT_PROJECT_COLUMNS))
        cur = conn.execute(
            f"INSERT INTO client_projects ({','.join(CLIENT_PROJECT_COLUMNS)})"
            f" VALUES ({marks})",
            tuple(data.get(c) for c in CLIENT_PROJECT_COLUMNS),
        )
        return int(cur.lastrowid)
    sets = ",".join(f"{c} = ?" for c in CLIENT_PROJECT_COLUMNS)
    conn.execute(
        f"UPDATE client_projects SET {sets}, updated_at = datetime('now') WHERE id = ?",
        tuple(data.get(c) for c in CLIENT_PROJECT_COLUMNS) + (project_id,),
    )
    return project_id


def delete_client_project(conn: sqlite3.Connection, project_id: int) -> None:
    conn.execute("DELETE FROM client_projects WHERE id = ?", (project_id,))


# ============================================================
# Задачи
# ============================================================

TASK_COLUMNS = ["project_id", "title", "description", "specialization",
                "skills", "deadline", "price", "status", "freelancer_id",
                "admin_note", "sort_order"]


def project_tasks(conn: sqlite3.Connection, project_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT t.*, f.name AS freelancer_name FROM tasks t"
        " LEFT JOIN freelancers f ON f.id = t.freelancer_id"
        " WHERE t.project_id = ? ORDER BY t.sort_order, t.id",
        (project_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_task(conn: sqlite3.Connection, task_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT t.*, p.title AS project_title, f.name AS freelancer_name"
        " FROM tasks t"
        " JOIN client_projects p ON p.id = t.project_id"
        " LEFT JOIN freelancers f ON f.id = t.freelancer_id"
        " WHERE t.id = ?",
        (task_id,),
    ).fetchone()


def freelancer_tasks(conn: sqlite3.Connection, freelancer_id: int) -> list[dict]:
    """Только свои задачи. Фильтр по владельцу стоит прямо в запросе,
    поэтому чужая задача не попадёт в выборку даже по ошибке шаблона."""
    rows = conn.execute(
        "SELECT t.*, p.title AS project_title FROM tasks t"
        " JOIN client_projects p ON p.id = t.project_id"
        " WHERE t.freelancer_id = ?"
        " ORDER BY CASE t.status"
        "   WHEN 'revision' THEN 0 WHEN 'assigned' THEN 1"
        "   WHEN 'in_progress' THEN 2 WHEN 'review' THEN 3 ELSE 4 END,"
        " t.deadline IS NULL, t.deadline",
        (freelancer_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def freelancer_task(conn: sqlite3.Connection, task_id: int,
                    freelancer_id: int) -> sqlite3.Row | None:
    """Задача по номеру, но только если она принадлежит этому человеку."""
    return conn.execute(
        "SELECT t.*, p.title AS project_title FROM tasks t"
        " JOIN client_projects p ON p.id = t.project_id"
        " WHERE t.id = ? AND t.freelancer_id = ?",
        (task_id, freelancer_id),
    ).fetchone()


def save_task(conn: sqlite3.Connection, task_id: int | None, data: dict) -> int:
    if data.get("status") not in TASK_STATUSES:
        data["status"] = "todo"
    # В базе у колонки стоит NOT NULL DEFAULT 0, но явно переданный NULL
    # умолчание не включает — приводим сами
    data["sort_order"] = int(data.get("sort_order") or 0)
    if task_id is None:
        marks = ",".join("?" * len(TASK_COLUMNS))
        cur = conn.execute(
            f"INSERT INTO tasks ({','.join(TASK_COLUMNS)}) VALUES ({marks})",
            tuple(data.get(c) for c in TASK_COLUMNS),
        )
        task_id = int(cur.lastrowid)
        log_task(conn, task_id, None, data["status"], data.get("actor", "админ"),
                 "задача создана")
        return task_id
    sets = ",".join(f"{c} = ?" for c in TASK_COLUMNS)
    conn.execute(
        f"UPDATE tasks SET {sets}, updated_at = datetime('now') WHERE id = ?",
        tuple(data.get(c) for c in TASK_COLUMNS) + (task_id,),
    )
    return task_id


def delete_task(conn: sqlite3.Connection, task_id: int) -> None:
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))


def log_task(conn: sqlite3.Connection, task_id: int, old: str | None,
             new: str, actor: str, comment: str = "") -> None:
    conn.execute(
        "INSERT INTO task_history (task_id, from_status, to_status, actor, comment)"
        " VALUES (?, ?, ?, ?, ?)",
        (task_id, old, new, actor[:80], comment[:500]),
    )


def task_history(conn: sqlite3.Connection, task_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM task_history WHERE task_id = ? ORDER BY created_at, id",
        (task_id,),
    ).fetchall()


def move_task(conn: sqlite3.Connection, task_id: int, new_status: str,
              *, by_admin: bool, actor: str, comment: str = "",
              freelancer_id: int | None = None) -> str | None:
    """
    Переводит задачу в новое состояние. Возвращает текст ошибки или None.

    Разрешённые переходы заданы таблицей, а не проверками на месте:
    так нельзя случайно разрешить фрилансеру закрыть свою же задачу.
    """
    if new_status not in TASK_STATUSES:
        return "Неизвестное состояние задачи."

    if by_admin:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        allowed = ADMIN_MOVES
    else:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND freelancer_id = ?",
            (task_id, freelancer_id),
        ).fetchone()
        allowed = FREELANCER_MOVES
    if row is None:
        return "Задача не найдена."

    current = row["status"]
    if new_status not in allowed.get(current, ()):
        return f"Из состояния «{TASK_STATUSES[current]}» так перейти нельзя."

    conn.execute(
        "UPDATE tasks SET status = ?, updated_at = datetime('now') WHERE id = ?",
        (new_status, task_id),
    )
    log_task(conn, task_id, current, new_status, actor, comment)
    return None


def submit_result(conn: sqlite3.Connection, task_id: int, freelancer_id: int,
                  text: str, url: str, actor: str) -> str | None:
    """Отправка результата: сохраняем и переводим задачу на проверку."""
    if len(text.strip()) < 5 and not url.strip():
        return "Опишите, что сделано, или приложите ссылку."
    row = conn.execute(
        "SELECT status FROM tasks WHERE id = ? AND freelancer_id = ?",
        (task_id, freelancer_id),
    ).fetchone()
    if row is None:
        return "Задача не найдена."
    conn.execute(
        "UPDATE tasks SET result_text = ?, result_url = ?,"
        " updated_at = datetime('now') WHERE id = ?",
        (text[:4000], url[:500], task_id),
    )
    return move_task(conn, task_id, "review", by_admin=False, actor=actor,
                     comment="результат отправлен", freelancer_id=freelancer_id)


def tasks_awaiting_review(conn: sqlite3.Connection) -> int:
    return int(conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE status = 'review'"
    ).fetchone()[0])
