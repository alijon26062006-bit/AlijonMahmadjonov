"""Подтверждение email: письмо со ссылкой, по ней — «почта подтверждена».

Нужно для конкурса рефералов: друг засчитывается, только когда подтвердил почту. Вход через Google почту уже
подтверждает. Письма идут через SMTP из .env (DONATIX_SMTP_*): Gmail или Brevo — бесплатно, см. deploy/email.sh.
Ссылка подписана ключом сайта и живёт 3 дня; подделать или подставить чужой аккаунт нельзя.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import smtplib
import sqlite3
import threading
import time
from email.message import EmailMessage

from .config import Config

log = logging.getLogger(__name__)

TTL = 3 * 86400
FAKE_DOMAINS = ("@telegram.user", "@guest.donatix.tj")


def ready(config: Config) -> bool:
    return bool(config.smtp_host)


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


def needs(user) -> bool:
    """Аккаунту есть что подтверждать: настоящая почта и ещё не подтверждена."""
    try:
        return bool(user and not user["email_verified_at"] and not str(user["email"]).endswith(FAKE_DOMAINS))
    except (KeyError, IndexError):
        return False


def send(config: Config, uid: int, email: str, *, wait: bool = False) -> bool:
    """Отправить письмо со ссылкой. wait=False — в фоне, сайт не ждёт почтовый сервер."""
    if not ready(config) or email.endswith(FAKE_DOMAINS):
        return False
    link = f"{config.base_url}/verify-email?t={token(config, uid, email)}"
    msg = EmailMessage()
    msg["Subject"] = f"{config.site_name}: подтвердите почту"
    msg["From"] = config.smtp_from or config.smtp_user
    msg["To"] = email
    msg.set_content(f"Здравствуйте!\n\nЧтобы подтвердить почту на {config.site_name}, откройте ссылку:\n{link}\n\n"
                    "Ссылка действует 3 дня. Если вы не регистрировались — просто удалите это письмо.\n\n"
                    f"Салом! Барои тасдиқи почта ҳаволаро кушоед:\n{link}\n\n— {config.site_name}")
    msg.add_alternative(
        f"<p>Здравствуйте!</p><p>Чтобы подтвердить почту на <b>{config.site_name}</b>, нажмите кнопку:</p>"
        f'<p><a href="{link}" style="display:inline-block;padding:12px 22px;background:#4f46e5;color:#fff;'
        f'border-radius:10px;text-decoration:none;font-weight:700">Подтвердить почту</a></p>'
        f'<p style="color:#666;font-size:13px">Или откройте ссылку: {link}<br>Ссылка действует 3 дня. '
        "Если вы не регистрировались — просто удалите это письмо.</p>"
        f"<p>Салом! Барои тасдиқи почта тугмаро пахш кунед.</p><p>— {config.site_name}</p>", subtype="html")

    def run() -> bool:
        try:
            with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=20) as s:
                s.starttls()
                if config.smtp_user:
                    s.login(config.smtp_user, config.smtp_password)
                s.send_message(msg)
            return True
        except Exception as exc:  # noqa: BLE001 — почта не должна ломать сайт
            log.warning("письмо подтверждения на %s не отправлено: %s", email, exc)
            return False
    if wait:
        return run()
    threading.Thread(target=run, daemon=True).start()
    return True
