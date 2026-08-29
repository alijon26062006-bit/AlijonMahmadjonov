"""
Пароли, сессии, CSRF и защита от перебора.

Пароль хешируется scrypt из стандартной библиотеки: он памяте-затратный,
то есть подбор на видеокартах дорог. Внешняя зависимость для этого
не нужна — чем меньше чужого кода в проверке пароля, тем лучше.
"""
import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from .config import (
    LOGIN_BLOCK_AFTER,
    LOGIN_SLOWDOWN_AFTER,
    LOGIN_WINDOW_MINUTES,
    SESSION_HOURS,
)

# Параметры scrypt: 32 МБ памяти на одну проверку
_N, _R, _P, _DKLEN = 2 ** 15, 8, 1, 32
_MAXMEM = 96 * 1024 * 1024


def _utc(offset_hours: float = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=offset_hours)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


# ---------- пароли ----------

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P,
        dklen=_DKLEN, maxmem=_MAXMEM,
    )
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_hex, dk_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        dk = hashlib.scrypt(
            password.encode("utf-8"), salt=bytes.fromhex(salt_hex),
            n=int(n), r=int(r), p=int(p), dklen=len(dk_hex) // 2, maxmem=_MAXMEM,
        )
    except (ValueError, TypeError):
        return False
    # Сравнение за постоянное время: иначе по задержке можно подбирать хеш
    return hmac.compare_digest(dk.hex(), dk_hex)


# ---------- сессии ----------

def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(conn: sqlite3.Connection, admin_id: int, ip: str, ua: str) -> str:
    """Возвращает токен для cookie. В базе хранится только его хеш."""
    token = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO sessions (token_hash, admin_id, csrf_token, expires_at, ip, user_agent)"
        " VALUES (?,?,?,?,?,?)",
        (_token_hash(token), admin_id, secrets.token_urlsafe(24),
         _utc(SESSION_HOURS), ip, (ua or "")[:400]),
    )
    conn.execute("UPDATE admins SET last_login_at = ? WHERE id = ?", (_utc(), admin_id))
    return token


def get_session(conn: sqlite3.Connection, token: str | None) -> sqlite3.Row | None:
    if not token:
        return None
    row = conn.execute(
        "SELECT s.*, a.username FROM sessions s"
        " JOIN admins a ON a.id = s.admin_id"
        " WHERE s.token_hash = ? AND s.expires_at > ?",
        (_token_hash(token), _utc()),
    ).fetchone()
    return row


def destroy_session(conn: sqlite3.Connection, token: str | None) -> None:
    if token:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))


def purge_expired(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (_utc(),))
    conn.execute(
        "DELETE FROM login_attempts WHERE attempted_at <= ?",
        (_utc(-24),),
    )


# ---------- CSRF ----------

def check_csrf(session: sqlite3.Row | None, sent: str | None) -> bool:
    if session is None or not sent:
        return False
    # compare_digest на строках падает, если внутри есть не-ASCII: подделанный
    # токен с кириллицей ронял бы запрос вместо честного «не совпало».
    # Сравниваем байты — сравнение остаётся постоянным по времени.
    return hmac.compare_digest(
        str(session["csrf_token"]).encode("utf-8"), str(sent).encode("utf-8")
    )


# ---------- защита от перебора ----------

def recent_failures(conn: sqlite3.Connection, ip: str) -> int:
    since = (datetime.now(timezone.utc) - timedelta(minutes=LOGIN_WINDOW_MINUTES)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM login_attempts"
        " WHERE ip = ? AND success = 0 AND attempted_at > ?",
        (ip, since),
    ).fetchone()
    return int(row["n"])


def record_attempt(conn: sqlite3.Connection, ip: str, username: str, success: bool) -> None:
    conn.execute(
        "INSERT INTO login_attempts (ip, username, success) VALUES (?,?,?)",
        (ip, (username or "")[:100], 1 if success else 0),
    )


def login_delay(failures: int) -> float:
    """Задержка перед ответом — чтобы перебор был медленным, а не мгновенным."""
    if failures < LOGIN_SLOWDOWN_AFTER:
        return 0.0
    return min(2.0 ** (failures - LOGIN_SLOWDOWN_AFTER + 1), 8.0)


def is_blocked(failures: int) -> bool:
    return failures >= LOGIN_BLOCK_AFTER
