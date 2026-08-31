"""
Учётные записи маркетплейса AVERIX Freelance.

Здесь только работа с базой: пользователи, сессии, одноразовые ссылки
из писем, лица заказчика и специалиста. Ни одного HTML-ответа —
маршруты живут отдельно.

Три вещи, ради которых этот модуль написан именно так:

  1. Один человек — одна учётная запись. Лицо заказчика и лицо
     специалиста лежат в отдельных таблицах и включаются по желанию.
     Второй учётки для второй роли не требуется.
  2. Ответ формы не должен выдавать, есть ли такой адрес в базе.
     Поэтому неизвестная почта считает хеш вхолостую и отвечает
     тем же текстом и примерно за то же время.
  3. В базе не лежит ничего, чем можно воспользоваться напрямую:
     ни пароля, ни токена сессии, ни ссылки из письма — только их хеши.
"""
import re
import secrets
import sqlite3

from . import security

# Сессия живёт две недели: это площадка, а не админка, и выкидывать
# человека каждые двенадцать часов здесь нечем оправдать.
SESSION_DAYS = 14
SESSION_COOKIE = "averix_user"

VERIFY_HOURS = 48
RESET_HOURS = 2

MIN_PASSWORD = 10

# Проверяем форму адреса, а не его существование: существование
# проверяет только письмо, которое до него дошло.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+\.[a-zA-Z]{2,}$")

USER_STATUSES = {
    "active": "Активен",
    "suspended": "Приостановлен",
    "deleted": "Удалён",
}

# Кому вход закрыт. Приостановленный видит внятную причину — но только
# после верного пароля, иначе по ответу можно было бы перебирать адреса.
BLOCKED_STATUSES = ("suspended", "deleted")


def normalize_email(value: str) -> str:
    return (value or "").strip().lower()[:190]


def check_password(password: str, email: str = "") -> str | None:
    """Возвращает текст ошибки или None."""
    if len(password) < MIN_PASSWORD:
        return f"Пароль не короче {MIN_PASSWORD} символов."
    if email and password.strip().lower() == normalize_email(email):
        return "Пароль не должен совпадать с почтой."
    return None


# ============================================================
# Пользователи
# ============================================================

def user_by_email(conn: sqlite3.Connection, email: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM users WHERE email = ?", (normalize_email(email),)
    ).fetchone()


def get_user(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def check_new_user(conn: sqlite3.Connection, email: str, password: str) -> dict:
    """
    Ошибки по полям — БЕЗ записи в базу.

    Проверка отделена от создания намеренно. Пока они были одной
    функцией, ошибка в соседнем поле формы (не выбрана роль) приводила
    к тому, что учётная запись уже создана, а человеку показана форма
    с ошибкой: он жмёт «отправить» второй раз и получает «такая почта
    уже зарегистрирована» — на собственную регистрацию.
    """
    email = normalize_email(email)
    errors: dict[str, str] = {}
    if not EMAIL_RE.match(email):
        errors["email"] = "Проверьте адрес почты."
    elif user_by_email(conn, email) is not None:
        # Здесь мы всё-таки говорим прямо: без этого человек не поймёт,
        # почему форма не проходит, и будет жать кнопку до посинения.
        # Перебор адресов через регистрацию ограничен счётчиком по IP.
        errors["email"] = "Такая почта уже зарегистрирована. Войдите или восстановите пароль."
    problem = check_password(password, email)
    if problem:
        errors["password"] = problem
    return errors


def create_user(conn: sqlite3.Connection, email: str, password: str,
                telegram: str = "") -> int:
    """Заводит учётную запись. Вызывать только после check_new_user."""
    cur = conn.execute(
        "INSERT INTO users (email, password_hash, telegram) VALUES (?,?,?)",
        (normalize_email(email), security.hash_password(password),
         (telegram or "").strip()[:120]),
    )
    return int(cur.lastrowid)


def verify_login(conn: sqlite3.Connection, email: str, password: str):
    """
    Возвращает (строка пользователя, ошибка). Ровно один из двух — не None.

    Неверная почта и неверный пароль отвечают одинаково и примерно
    за одно и то же время: иначе по форме входа можно составить список
    зарегистрированных адресов.
    """
    row = user_by_email(conn, email)
    if row is None:
        security.verify_password("x" * 20, security.hash_password("y" * 20))
        return None, "Неверная почта или пароль."
    if not security.verify_password(password, row["password_hash"]):
        return None, "Неверная почта или пароль."
    if row["status"] in BLOCKED_STATUSES:
        # Сюда можно попасть только с верным паролем, так что подсказкой
        # для перебора этот текст не работает.
        return None, "Учётная запись приостановлена. Напишите в студию."
    return row, None


def set_password(conn: sqlite3.Connection, user_id: int, password: str) -> None:
    conn.execute(
        "UPDATE users SET password_hash = ?, updated_at = datetime('now') WHERE id = ?",
        (security.hash_password(password), user_id),
    )
    # Смена пароля закрывает все входы. Если пароль меняют потому, что
    # его подсмотрели, чужая сессия должна перестать работать сразу.
    conn.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))


def touch(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute("UPDATE users SET last_seen_at = datetime('now') WHERE id = ?",
                 (user_id,))


# ============================================================
# Сессии
# ============================================================

def create_session(conn: sqlite3.Connection, user_id: int, ip: str = "",
                   user_agent: str = "") -> str:
    """Возвращает токен для cookie. В базе остаётся только его хеш."""
    token = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO user_sessions (token_hash, user_id, csrf_token, expires_at,"
        " ip, user_agent)"
        f" VALUES (?,?,?, datetime('now', '+{SESSION_DAYS} days'), ?, ?)",
        (security._token_hash(token), user_id, secrets.token_urlsafe(24),
         ip[:64], (user_agent or "")[:400]),
    )
    return token


def get_session(conn: sqlite3.Connection, token: str | None) -> sqlite3.Row | None:
    """Сессия вместе с пользователем. Приостановленный не проходит:
    условие стоит в самом запросе, а не в проверке после."""
    if not token:
        return None
    return conn.execute(
        "SELECT s.token_hash, s.csrf_token, s.expires_at,"
        " u.id AS user_id, u.email, u.telegram, u.status, u.email_verified,"
        " u.created_at AS user_created_at"
        " FROM user_sessions s JOIN users u ON u.id = s.user_id"
        " WHERE s.token_hash = ? AND s.expires_at > datetime('now')"
        "   AND u.status = 'active'",
        (security._token_hash(token),),
    ).fetchone()


def destroy_session(conn: sqlite3.Connection, token: str | None) -> None:
    if token:
        conn.execute("DELETE FROM user_sessions WHERE token_hash = ?",
                     (security._token_hash(token),))


def purge_sessions(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM user_sessions WHERE expires_at <= datetime('now')")
    conn.execute("DELETE FROM user_tokens WHERE expires_at <= datetime('now', '-7 days')")
    conn.execute("DELETE FROM fl_rate_events WHERE created_at <= datetime('now', '-1 day')")


# ============================================================
# Ссылки из писем
# ============================================================

def issue_token(conn: sqlite3.Connection, user_id: int, kind: str,
                hours: int) -> str:
    """Заводит одноразовую ссылку и возвращает её код. В базе — хеш."""
    if kind not in ("verify", "reset"):
        raise ValueError("неизвестный вид ссылки")
    # Прежние ссылки того же вида гасим: иначе старое письмо остаётся
    # рабочим ключом ещё сутки после того, как человек запросил новое.
    conn.execute("DELETE FROM user_tokens WHERE user_id = ? AND kind = ?",
                 (user_id, kind))
    token = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO user_tokens (token_hash, user_id, kind, expires_at)"
        f" VALUES (?,?,?, datetime('now', '+{int(hours)} hours'))",
        (security._token_hash(token), user_id, kind),
    )
    return token


def use_token(conn: sqlite3.Connection, token: str, kind: str) -> int | None:
    """Гасит ссылку и возвращает пользователя. Второй раз не сработает."""
    if not token:
        return None
    row = conn.execute(
        "SELECT token_hash, user_id FROM user_tokens"
        " WHERE token_hash = ? AND kind = ? AND used_at IS NULL"
        "   AND expires_at > datetime('now')",
        (security._token_hash(token), kind),
    ).fetchone()
    if row is None:
        return None
    conn.execute("UPDATE user_tokens SET used_at = datetime('now')"
                 " WHERE token_hash = ?", (row["token_hash"],))
    return int(row["user_id"])


def mark_verified(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute(
        "UPDATE users SET email_verified = 1, updated_at = datetime('now')"
        " WHERE id = ?", (user_id,))


# ============================================================
# Лица: заказчик и специалист
# ============================================================

def roles(conn: sqlite3.Connection, user_id: int) -> dict:
    """
    Какие лица заведены у человека.

    Считается наличием строк, а не флажками в users: флажок однажды
    разойдётся с действительностью, а строка — нет.
    """
    client = conn.execute(
        "SELECT id, display_name FROM client_profiles WHERE user_id = ?",
        (user_id,)).fetchone()
    freelancer = conn.execute(
        "SELECT id, name FROM freelancers WHERE user_id = ?", (user_id,)).fetchone()
    return {
        "client": client is not None,
        "freelancer": freelancer is not None,
        "client_id": client["id"] if client else None,
        "freelancer_id": freelancer["id"] if freelancer else None,
        "client_name": client["display_name"] if client else "",
        "freelancer_name": freelancer["name"] if freelancer else "",
    }


def ensure_client_profile(conn: sqlite3.Connection, user_id: int,
                          display_name: str) -> int:
    row = conn.execute("SELECT id FROM client_profiles WHERE user_id = ?",
                       (user_id,)).fetchone()
    if row is not None:
        return int(row["id"])
    cur = conn.execute(
        "INSERT INTO client_profiles (user_id, display_name) VALUES (?, ?)",
        (user_id, (display_name or "").strip()[:120] or "Заказчик"),
    )
    return int(cur.lastrowid)


def ensure_freelancer_profile(conn: sqlite3.Connection, user_id: int,
                              name: str) -> int:
    """
    Заводит специалисту его строку в freelancers.

    Профиль пустой и никуда не показывается: он появится в каталоге
    только после того, как человек сам его заполнит и попросит
    публикацию, а студия проверит. Это отдельная фаза.
    """
    row = conn.execute("SELECT id FROM freelancers WHERE user_id = ?",
                       (user_id,)).fetchone()
    if row is not None:
        return int(row["id"])
    cur = conn.execute(
        "INSERT INTO freelancers (user_id, name, specialization, status)"
        " VALUES (?, ?, 'other', 'new')",
        (user_id, (name or "").strip()[:100] or "Специалист"),
    )
    return int(cur.lastrowid)


# ============================================================
# Ограничение частоты
# ============================================================

# Сколько раз с одного адреса за окно. Вход считается общим счётчиком
# login_attempts вместе с админкой — подбор пароля он и есть подбор.
LIMITS = {
    "register": (5, 60),
    "reset": (5, 60),
    "verify_resend": (5, 60),
}


def hit(conn: sqlite3.Connection, ip: str, kind: str) -> None:
    conn.execute("INSERT INTO fl_rate_events (ip, kind) VALUES (?, ?)",
                 (ip[:64], kind[:40]))


def too_many(conn: sqlite3.Connection, ip: str, kind: str) -> bool:
    limit, minutes = LIMITS.get(kind, (10, 60))
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM fl_rate_events"
        " WHERE kind = ? AND ip = ? AND created_at > datetime('now', ?)",
        (kind, ip[:64], f"-{int(minutes)} minutes"),
    ).fetchone()
    return int(row["n"]) >= limit
