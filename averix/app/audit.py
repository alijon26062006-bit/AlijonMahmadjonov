"""
Журнал действий администратора.

Отвечает на вопрос «кто и когда это поменял» — тот самый, который
возникает через месяц, когда проект пропал с сайта, а никто не помнит,
кто нажал кнопку.

Пишутся только действие, сущность и её номер. Паролей, токенов
и содержимого форм здесь нет и быть не может.
"""
import sqlite3

# Действия из задания. Список закрытый: строка, которой здесь нет,
# в журнал не попадёт — иначе он со временем превращается в свалку
# из десятков похожих названий одного и того же.
ACTIONS = {
    "LOGIN": "Вход в админку",
    "LOGOUT": "Выход",
    "PROJECT_CREATED": "Проект создан",
    "PROJECT_UPDATED": "Проект изменён",
    "PROJECT_DELETED": "Проект удалён",
    "TEAM_CHANGED": "Команда изменена",
    "VACANCY_CHANGED": "Вакансия изменена",
    "APPLICATION_STATUS_CHANGED": "Статус отклика изменён",
    "FREELANCER_CHANGED": "Специалист изменён",
    "CLIENT_PROJECT_CHANGED": "Клиентский проект изменён",
    "TASK_CHANGED": "Задача изменена",
    "SETTINGS_CHANGED": "Настройки изменены",
}


def record(conn: sqlite3.Connection, session, action: str,
           entity: str = "", entity_id: int | None = None,
           details: str = "") -> None:
    if action not in ACTIONS:
        raise ValueError(f"неизвестное действие журнала: {action}")
    admin_id = session["admin_id"] if session and "admin_id" in session.keys() else None
    username = session["username"] if session else ""
    conn.execute(
        "INSERT INTO admin_log (admin_id, username, action, entity, entity_id, details)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (admin_id, (username or "")[:80], action, entity[:40] or None,
         entity_id, (details or "")[:300]),
    )


def recent(conn: sqlite3.Connection, limit: int = 100) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM admin_log ORDER BY created_at DESC, id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r, action_label=ACTIONS.get(r["action"], r["action"])) for r in rows]
