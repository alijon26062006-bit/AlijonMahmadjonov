"""Клиенты, API-ключи и журнал движения денег."""

from __future__ import annotations

import re
import sqlite3
from decimal import Decimal

from . import db
from .config import TIERS, Config
from .money import MoneyError, to_decimal
from .security import hash_api_key, hash_password, new_api_key, new_webhook_secret, verify_password

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
LOGIN_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")


class AccountError(ValueError):
    pass


class InsufficientBalance(Exception):
    def __init__(self, need: int, have: int):
        super().__init__("недостаточно средств")
        self.need = need
        self.have = have


def get_user(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def create_user(
    conn: sqlite3.Connection,
    *,
    email: str,
    login: str,
    password: str,
    role: str = "client",
    status: str = "pending",
    project: str = "",
) -> int:
    email = email.strip().lower()
    login = login.strip()
    if not EMAIL_RE.match(email):
        raise AccountError("Неверный email.")
    if not LOGIN_RE.match(login):
        raise AccountError("Имя пользователя: 3–32 символа, латиница, цифры, _ . -")
    if len(password) < 8:
        raise AccountError("Пароль — минимум 8 символов.")
    exists = conn.execute(
        "SELECT email, login FROM users WHERE email = ? OR lower(login) = lower(?)", (email, login)
    ).fetchone()
    if exists:
        raise AccountError("Такой email или имя уже заняты.")
    cur = conn.execute(
        "INSERT INTO users (email, login, password_hash, role, status, created_at, webhook_secret, project) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (email, login, hash_password(password), role, status, db.now(), new_webhook_secret(),
         project.strip()[:300] or None),
    )
    return int(cur.lastrowid)


def authenticate(conn: sqlite3.Connection, email_or_login: str, password: str) -> sqlite3.Row | None:
    ident = email_or_login.strip()
    user = conn.execute(
        "SELECT * FROM users WHERE email = lower(?) OR lower(login) = lower(?)", (ident, ident)
    ).fetchone()
    if user is None or not verify_password(password, user["password_hash"]):
        return None
    return user


def ensure_admin(conn: sqlite3.Connection, config: Config) -> None:
    """Создать первого админа из .env, если админов ещё нет."""
    if not (config.admin_email and config.admin_password):
        return
    if conn.execute("SELECT 1 FROM users WHERE role = 'admin'").fetchone():
        return
    login = config.admin_email.split("@")[0][:32] or "admin"
    if not LOGIN_RE.match(login):
        login = "admin"
    create_user(conn, email=config.admin_email, login=login, password=config.admin_password,
                role="admin", status="active")


def markup_for(user: sqlite3.Row, config: Config) -> Decimal:
    if user["markup_override"] not in (None, ""):
        return to_decimal(user["markup_override"])
    return config.markups.get(user["tier"], config.markups["bronze"])


def update_user_admin(
    conn: sqlite3.Connection, user_id: int, *, status: str, tier: str, markup_override: str
) -> None:
    if status not in ("pending", "active", "blocked"):
        raise AccountError("Неверный статус.")
    if tier not in TIERS:
        raise AccountError("Неверный уровень.")
    override = markup_override.strip().replace(",", ".")
    if override:
        try:
            value = to_decimal(override)
        except MoneyError as exc:
            raise AccountError("Наценка — число в процентах.") from exc
        if not (Decimal("-50") <= value <= Decimal("500")):
            raise AccountError("Наценка вне разумных пределов.")
    conn.execute(
        "UPDATE users SET status = ?, tier = ?, markup_override = ? WHERE id = ?",
        (status, tier, override or None, user_id),
    )


def set_webhook(conn: sqlite3.Connection, user_id: int, url: str) -> None:
    url = url.strip()
    if url and not re.match(r"^https?://[^\s]+$", url):
        raise AccountError("Адрес webhook должен начинаться с http:// или https://")
    conn.execute("UPDATE users SET webhook_url = ? WHERE id = ?", (url or None, user_id))


def rotate_webhook_secret(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute("UPDATE users SET webhook_secret = ? WHERE id = ?", (new_webhook_secret(), user_id))


# ── API-ключи ────────────────────────────────────────────────


def create_api_key(conn: sqlite3.Connection, user_id: int, name: str) -> str:
    active = conn.execute(
        "SELECT COUNT(*) FROM api_keys WHERE user_id = ? AND revoked_at IS NULL", (user_id,)
    ).fetchone()[0]
    if active >= 10:
        raise AccountError("Не больше 10 активных ключей. Отзовите ненужные.")
    key, prefix, key_hash = new_api_key()
    conn.execute(
        "INSERT INTO api_keys (user_id, name, prefix, key_hash, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, (name.strip() or "Ключ")[:64], prefix, key_hash, db.now()),
    )
    return key


def revoke_api_key(conn: sqlite3.Connection, user_id: int, key_id: int) -> None:
    conn.execute(
        "UPDATE api_keys SET revoked_at = ? WHERE id = ? AND user_id = ? AND revoked_at IS NULL",
        (db.now(), key_id, user_id),
    )


def user_by_api_key(conn: sqlite3.Connection, key: str) -> sqlite3.Row | None:
    row = conn.execute(
        "SELECT u.*, k.id AS api_key_id FROM api_keys k JOIN users u ON u.id = k.user_id "
        "WHERE k.key_hash = ? AND k.revoked_at IS NULL",
        (hash_api_key(key),),
    ).fetchone()
    if row is not None:
        ts = db.now()
        conn.execute("UPDATE api_keys SET last_used_at = ? WHERE id = ?", (ts, row["api_key_id"]))
        conn.execute("UPDATE users SET last_active_at = ? WHERE id = ?", (ts, row["id"]))
    return row


# ── Журнал денег ─────────────────────────────────────────────


def post_ledger(
    conn: sqlite3.Connection,
    user_id: int,
    amount_micro: int,
    note: str,
    *,
    order_id: int | None = None,
    created_by: int | None = None,
    allow_negative: bool = False,
) -> int:
    """Изменить баланс и записать в журнал. Вызывать ВНУТРИ db.tx()."""
    before = conn.execute("SELECT balance_micro FROM users WHERE id = ?", (user_id,)).fetchone()[0]
    after = before + amount_micro
    if after < 0 and not allow_negative:
        raise InsufficientBalance(need=-amount_micro, have=before)
    conn.execute("UPDATE users SET balance_micro = ? WHERE id = ?", (after, user_id))
    cur = conn.execute(
        "INSERT INTO transactions (user_id, type, amount_micro, balance_before, balance_after, note, "
        "order_id, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, "credit" if amount_micro >= 0 else "debit", amount_micro, before, after, note,
         order_id, created_by, db.now()),
    )
    return int(cur.lastrowid)


def tx_public_id(tx_id: int) -> str:
    return f"tx{tx_id}"


def parse_tx_id(public_id: str) -> int | None:
    m = re.fullmatch(r"tx(\d+)", public_id.strip())
    return int(m.group(1)) if m else None
