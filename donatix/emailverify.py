"""Подтверждение email: письмо с кодом из 6 цифр (и запасной кнопкой-ссылкой).

Клиент регистрируется → на почту приходит «Ваш код: 482915» → вводит код на сайте → почта подтверждена.
Код живёт 10 минут, 5 попыток ввода, новый код — не чаще раза в минуту (и не больше 5 писем в час).
Хранится только хэш кода. Вход через Google почту уже подтверждает.

Письма: Resend API (DONATIX_RESEND_KEY + DONATIX_MAIL_FROM, домен подтверждён в Resend), иначе SMTP
(DONATIX_SMTP_*). Настройка — deploy/resend.sh.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import smtplib
import sqlite3
import threading
import time
from email.message import EmailMessage

import httpx

from .config import Config

log = logging.getLogger(__name__)

TTL = 3 * 86400           # ссылка из письма
CODE_TTL = 10 * 60        # код
CODE_TRIES = 5
RESEND_GAP = 60           # секунд между письмами
RESEND_URL = "https://api.resend.com/emails"
FAKE_DOMAINS = ("@telegram.user", "@guest.donatix.tj")


def ready(config: Config) -> bool:
    return bool(config.resend_key or config.smtp_host)


def _ensure(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS email_codes (user_id INTEGER PRIMARY KEY, code_hash TEXT NOT NULL, "
                 "email TEXT NOT NULL, expires_at REAL NOT NULL, tries INTEGER NOT NULL DEFAULT 0, "
                 "sent_at REAL NOT NULL)")


# ── Ссылка (запасной способ) ─────────────────────────────────


def _mac(config: Config, uid: int, email: str, exp: int) -> str:
    msg = f"verify:{uid}:{email.lower()}:{exp}".encode()
    return hmac.new(config.secret_key.encode(), msg, hashlib.sha256).hexdigest()[:32]


def token(config: Config, uid: int, email: str, now: float | None = None) -> str:
    exp = int((now or time.time()) + TTL)
    return f"{uid}.{exp}.{_mac(config, uid, email, exp)}"


def check(conn: sqlite3.Connection, config: Config, raw: str) -> int:
    """Номер аккаунта, если ссылка верная и не устарела; иначе 0. Почту сменили — старая ссылка не действует."""
    try:
        uid_s, exp_s, mac = (raw or "").split(".", 2)
        uid, exp = int(uid_s), int(exp_s)
    except ValueError:
        return 0
    if exp < time.time():
        return 0
    row = conn.execute("SELECT email FROM users WHERE id = ?", (uid,)).fetchone()
    if row is None or not hmac.compare_digest(mac, _mac(config, uid, row["email"], exp)):
        return 0
    return uid


# ── Код ──────────────────────────────────────────────────────


def _hash(config: Config, uid: int, code: str) -> str:
    return hmac.new(config.secret_key.encode(), f"code:{uid}:{code}".encode(), hashlib.sha256).hexdigest()


def needs(user) -> bool:
    """Аккаунту есть что подтверждать: настоящая почта и ещё не подтверждена."""
    try:
        return bool(user and not user["email_verified_at"] and not str(user["email"]).endswith(FAKE_DOMAINS))
    except (KeyError, IndexError):
        return False


def wait_left(conn: sqlite3.Connection, uid: int) -> int:
    """Сколько секунд ждать до следующего письма (0 — можно)."""
    _ensure(conn)
    row = conn.execute("SELECT sent_at FROM email_codes WHERE user_id = ?", (uid,)).fetchone()
    return max(0, int(RESEND_GAP - (time.time() - row["sent_at"]))) if row else 0


def send_code(conn: sqlite3.Connection, config: Config, uid: int, email: str, *, wait: bool = False) -> bool:
    """Новый код на почту (старый перестаёт действовать)."""
    if not ready(config) or email.endswith(FAKE_DOMAINS):
        return False
    _ensure(conn)
    code = f"{secrets.randbelow(1_000_000):06d}"
    now = time.time()
    conn.execute("INSERT INTO email_codes (user_id, code_hash, email, expires_at, tries, sent_at) "
                 "VALUES (?, ?, ?, ?, 0, ?) ON CONFLICT(user_id) DO UPDATE SET code_hash = excluded.code_hash, "
                 "email = excluded.email, expires_at = excluded.expires_at, tries = 0, sent_at = excluded.sent_at",
                 (uid, _hash(config, uid, code), email.lower(), now + CODE_TTL, now))
    link = f"{config.base_url}/verify-email?t={token(config, uid, email)}"
    subject = f"{code} — код подтверждения {config.site_name}"
    text = (f"Ваш код подтверждения: {code}\n\nВведите его на сайте {config.site_name}. Код действует 10 минут.\n"
            f"Или откройте ссылку: {link}\n\nЕсли вы не регистрировались — просто удалите это письмо.\n\n"
            f"Рамзи тасдиқ: {code}\n\n— {config.site_name}")
    html = (f'<div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;padding:24px;color:#111">'
            f'<h2 style="margin:0 0 12px">{config.site_name}</h2>'
            f'<p>Ваш код подтверждения почты:</p>'
            f'<div style="font-size:34px;font-weight:800;letter-spacing:8px;padding:16px;background:#f3f4ff;'
            f'border-radius:12px;text-align:center">{code}</div>'
            f'<p style="color:#555">Введите его на сайте. Код действует <b>10 минут</b>.</p>'
            f'<p><a href="{link}" style="display:inline-block;padding:12px 22px;background:#4f46e5;color:#fff;'
            f'border-radius:10px;text-decoration:none;font-weight:700">Или подтвердить одной кнопкой</a></p>'
            f'<p style="color:#888;font-size:13px">Если вы не регистрировались — просто удалите это письмо.<br>'
            f'Рамзи тасдиқ: <b>{code}</b></p></div>')
    if wait:
        return deliver(config, email, subject, text, html)
    threading.Thread(target=deliver, args=(config, email, subject, text, html), daemon=True).start()
    return True


def check_code(conn: sqlite3.Connection, config: Config, uid: int, code: str) -> str:
    """'ok' | 'bad' (неверный, попытки ещё есть) | 'expired' (устарел или попытки кончились — нужен новый)."""
    _ensure(conn)
    code = "".join(ch for ch in (code or "") if ch.isdigit())
    row = conn.execute("SELECT * FROM email_codes WHERE user_id = ?", (uid,)).fetchone()
    u = conn.execute("SELECT email FROM users WHERE id = ?", (uid,)).fetchone()
    if row is None or u is None or row["email"] != u["email"].lower() or row["expires_at"] < time.time() \
            or row["tries"] >= CODE_TRIES:
        return "expired"
    if len(code) != 6 or not hmac.compare_digest(row["code_hash"], _hash(config, uid, code)):
        conn.execute("UPDATE email_codes SET tries = tries + 1 WHERE user_id = ?", (uid,))
        return "expired" if row["tries"] + 1 >= CODE_TRIES else "bad"
    conn.execute("DELETE FROM email_codes WHERE user_id = ?", (uid,))
    return "ok"


# ── Доставка ─────────────────────────────────────────────────


def deliver(config: Config, to: str, subject: str, text: str, html: str) -> bool:
    try:
        if config.resend_key:
            r = httpx.post(RESEND_URL, timeout=20, headers={"Authorization": f"Bearer {config.resend_key}"},
                           json={"from": config.mail_from or f"{config.site_name} <noreply@donatix.tj>",
                                 "to": [to], "subject": subject, "text": text, "html": html})
            if r.status_code >= 300:
                log.warning("Resend: письмо на %s не ушло: %s %s", to, r.status_code, r.text[:200])
                return False
            return True
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = config.mail_from or config.smtp_from or config.smtp_user
        msg["To"] = to
        msg.set_content(text)
        msg.add_alternative(html, subtype="html")
        with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=20) as s:
            s.starttls()
            if config.smtp_user:
                s.login(config.smtp_user, config.smtp_password)
            s.send_message(msg)
        return True
    except Exception as exc:  # noqa: BLE001 — почта не должна ломать сайт
        log.warning("письмо на %s не отправлено: %s", to, exc)
        return False
