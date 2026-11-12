"""Пароли, сессии, CSRF и ограничение частоты запросов."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque

from .db import Database, now

SESSION_TTL = 14 * 24 * 3600
SESSION_COOKIE = "amc_session"

# ── Пароли аккаунта ───────────────────────────────────────
_SCRYPT = dict(n=2 ** 14, r=8, p=1, dklen=32)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, salt_b64, dk_b64 = stored.split("$")
        if algo != "scrypt":
            return False
        dk = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt_b64), **_SCRYPT)
        return hmac.compare_digest(dk, base64.b64decode(dk_b64))
    except (ValueError, TypeError):
        return False


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


# ── Сессии ────────────────────────────────────────────────
def create_session(db: Database, user_id: int, ip: str) -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(24)
    db.run("INSERT INTO sessions(token_hash, user_id, csrf, created_at, expires_at, ip) VALUES (?,?,?,?,?,?)",
           (sha256(token), user_id, csrf, now(), now() + SESSION_TTL, ip))
    return token, csrf


def load_session(db: Database, token: str | None) -> dict | None:
    if not token:
        return None
    row = db.one(
        "SELECT s.csrf, s.expires_at, u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?",
        (sha256(token),))
    if not row or row["expires_at"] < now():
        return None
    return row


def destroy_session(db: Database, token: str | None) -> None:
    if token:
        db.run("DELETE FROM sessions WHERE token_hash = ?", (sha256(token),))


# ── Ограничение частоты (в памяти процесса) ───────────────
class RateLimiter:
    def __init__(self):
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window: int) -> bool:
        t = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and q[0] <= t - window:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(t)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


# ── Root-пароль сервера ───────────────────────────────────
ROOT_PW_ALLOWED = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    "!@#$%^&*()-_=+[]{}.,:;?~"
)


def root_password_problems(pw: str) -> list[str]:
    """Пустой список — пароль подходит. Требования совпадают с подсказками в интерфейсе."""
    problems = []
    if len(pw) < 12:
        problems.append("не короче 12 символов")
    if len(pw) > 128:
        problems.append("не длиннее 128 символов")
    if not any(c.islower() for c in pw):
        problems.append("строчные буквы")
    if not any(c.isupper() for c in pw):
        problems.append("заглавные буквы")
    if not any(c.isdigit() for c in pw):
        problems.append("цифры")
    if not any(not c.isalnum() for c in pw):
        problems.append("символы")
    if any(c not in ROOT_PW_ALLOWED for c in pw):
        problems.append("только латиница, цифры и символы !@#$%^&*()-_=+[]{}.,:;?~")
    return problems


def generate_root_password(length: int = 20) -> str:
    sets = ["abcdefghijkmnopqrstuvwxyz", "ABCDEFGHJKLMNPQRSTUVWXYZ", "23456789", "!@#$%^&*-_=+"]
    alphabet = "".join(sets)
    chars = [secrets.choice(s) for s in sets] + [secrets.choice(alphabet) for _ in range(length - len(sets))]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)
