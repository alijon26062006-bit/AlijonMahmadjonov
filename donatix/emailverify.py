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


KINDS = ("verify", "reset")   # подтвердить почту / восстановить пароль


def _ensure(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS mail_codes (user_id INTEGER NOT NULL, kind TEXT NOT NULL, "
                 "code_hash TEXT NOT NULL, email TEXT NOT NULL, expires_at REAL NOT NULL, "
                 "tries INTEGER NOT NULL DEFAULT 0, sent_at REAL NOT NULL, PRIMARY KEY (user_id, kind))")


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


def _hash(config: Config, uid: int, code: str, kind: str = "verify") -> str:
    return hmac.new(config.secret_key.encode(), f"code:{kind}:{uid}:{code}".encode(), hashlib.sha256).hexdigest()


def needs(user) -> bool:
    """Аккаунту есть что подтверждать: настоящая почта и ещё не подтверждена."""
    try:
        return bool(user and not user["email_verified_at"] and not str(user["email"]).endswith(FAKE_DOMAINS))
    except (KeyError, IndexError):
        return False


def wait_left(conn: sqlite3.Connection, uid: int, kind: str = "verify") -> int:
    """Сколько секунд ждать до следующего письма (0 — можно)."""
    _ensure(conn)
    row = conn.execute("SELECT sent_at FROM mail_codes WHERE user_id = ? AND kind = ?", (uid, kind)).fetchone()
    return max(0, int(RESEND_GAP - (time.time() - row["sent_at"]))) if row else 0


def has_code(conn: sqlite3.Connection, uid: int, kind: str = "verify") -> bool:
    """Код уже отправлен и ещё действует — показываем поле для кода, а не вопрос «подтвердить?»."""
    _ensure(conn)
    row = conn.execute("SELECT expires_at, tries FROM mail_codes WHERE user_id = ? AND kind = ?",
                       (uid, kind)).fetchone()
    return bool(row and row["expires_at"] > time.time() and row["tries"] < CODE_TRIES)


def layout(config: Config, *, title: str, lead: str, code: str = "", note: str = "",
           button: tuple[str, str] | None = None, tj: str = "", footer: str = "") -> str:
    """Письмо в стиле сайта: шапка с логотипом, крупный код, кнопка, подвал. Таблицы и стили в строке —
    так письмо одинаково выглядит в Gmail, Mail.ru, Яндексе, Outlook и на телефоне."""
    site = config.site_name
    font = "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;"
    code_html = ""
    if code:
        cells = '<td style="width:8px"></td>'.join(
            f'<td style="{font}width:44px;height:56px;background:#ffffff;border:2px solid #e2e4ff;border-radius:12px;'
            f'font-size:30px;font-weight:800;color:#1e1b4b;text-align:center;vertical-align:middle">{d}</td>'
            for d in code)
        code_html = (f'<table role="presentation" cellpadding="0" cellspacing="0" align="center" '
                     f'style="margin:18px auto 6px"><tr>{cells}</tr></table>'
                     f'<p style="{font}margin:0 0 4px;text-align:center;font-size:12px;color:#8a8fa8">'
                     f'Код можно скопировать: <b style="color:#1e1b4b;letter-spacing:3px">{code}</b></p>')
    btn_html = ""
    if button:
        btn_html = (f'<table role="presentation" cellpadding="0" cellspacing="0" align="center" style="margin:22px auto 4px">'
                    f'<tr><td style="border-radius:12px;background:#4f46e5;background-image:linear-gradient(135deg,#4f46e5,'
                    f'#7c3aed)"><a href="{button[1]}" style="{font}display:inline-block;padding:14px 28px;color:#ffffff;'
                    f'font-size:15px;font-weight:700;text-decoration:none;border-radius:12px">{button[0]}</a></td></tr></table>')
    tj_html = (f'<p style="{font}margin:18px 0 0;padding:12px 14px;background:#f6f7ff;border-radius:10px;'
               f'font-size:13px;color:#4b4f6b;text-align:center">{tj}</p>') if tj else ""
    return f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light">
<title>{title}</title></head>
<body style="margin:0;padding:0;background:#eef0f7">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#eef0f7;padding:28px 12px">
<tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px">
  <tr><td style="padding:0 0 14px" align="center">
    <table role="presentation" cellpadding="0" cellspacing="0"><tr>
      <td style="width:38px;height:38px;border-radius:10px;background:#4f46e5;color:#ffffff;{font}font-size:22px;
        font-weight:800;text-align:center;vertical-align:middle">D</td>
      <td style="{font}padding-left:10px;font-size:20px;font-weight:800;color:#1e1b4b">{site}</td>
    </tr></table></td></tr>
  <tr><td style="background:#ffffff;border-radius:20px;overflow:hidden;box-shadow:0 6px 24px rgba(30,27,75,.08)">
    <div style="height:6px;background:#4f46e5;background-image:linear-gradient(90deg,#4f46e5,#7c3aed,#f59e0b)"></div>
    <div style="padding:30px 28px 28px">
      <h1 style="{font}margin:0 0 10px;font-size:22px;color:#1e1b4b;text-align:center">{title}</h1>
      <p style="{font}margin:0;font-size:15px;color:#4b4f6b;text-align:center;line-height:1.5">{lead}</p>
      {code_html}
      <p style="{font}margin:14px 0 0;font-size:14px;color:#4b4f6b;text-align:center;line-height:1.5">{note}</p>
      {btn_html}{tj_html}
    </div></td></tr>
  <tr><td style="{font}padding:18px 20px 0;font-size:12px;color:#8a8fa8;text-align:center;line-height:1.6">
    {footer}<br><a href="{config.base_url}" style="color:#4f46e5;text-decoration:none;font-weight:600">{config.base_url.split("//")[-1]}</a>
    · Письмо отправлено автоматически, отвечать на него не нужно.</td></tr>
</table></td></tr></table></body></html>"""


def send_code(conn: sqlite3.Connection, config: Config, uid: int, email: str, *, kind: str = "verify",
              wait: bool = False) -> bool:
    """Новый код на почту (старый перестаёт действовать). kind: verify — подтвердить почту, reset — новый пароль."""
    if not ready(config) or email.endswith(FAKE_DOMAINS):
        return False
    _ensure(conn)
    code = f"{secrets.randbelow(1_000_000):06d}"
    now = time.time()
    conn.execute("INSERT INTO mail_codes (user_id, kind, code_hash, email, expires_at, tries, sent_at) "
                 "VALUES (?, ?, ?, ?, ?, 0, ?) ON CONFLICT(user_id, kind) DO UPDATE SET code_hash = excluded.code_hash, "
                 "email = excluded.email, expires_at = excluded.expires_at, tries = 0, sent_at = excluded.sent_at",
                 (uid, kind, _hash(config, uid, code, kind), email.lower(), now + CODE_TTL, now))
    if kind == "reset":
        return _send_reset(config, email, code, wait)
    link = f"{config.base_url}/verify-email?t={token(config, uid, email)}"
    subject = f"{code} — код подтверждения {config.site_name}"
    text = (f"Ваш код подтверждения: {code}\n\nВведите его на сайте {config.site_name}. Код действует 10 минут.\n"
            f"Или откройте ссылку: {link}\n\nЕсли вы не регистрировались — просто удалите это письмо.\n\n"
            f"Рамзи тасдиқ: {code}\n\n— {config.site_name}")
    html = layout(config, title="Подтвердите почту", lead="Ваш код подтверждения:", code=code,
                  note="Введите его на сайте. Код действует <b>10 минут</b>.",
                  button=("Подтвердить одной кнопкой", link),
                  tj=f"Рамзи тасдиқ: <b>{code}</b> — онро дар сайт ворид кунед.",
                  footer="Вы получили это письмо, потому что указали эту почту на сайте. "
                         "Если это были не вы — просто удалите письмо.")
    if wait:
        return deliver(config, email, subject, text, html)
    threading.Thread(target=deliver, args=(config, email, subject, text, html), daemon=True).start()
    return True


def _send_reset(config: Config, email: str, code: str, wait: bool) -> bool:
    subject = f"{code} — восстановление пароля {config.site_name}"
    text = (f"Код для восстановления пароля: {code}\n\nВведите его на сайте {config.site_name}. Код действует "
            "10 минут.\nЕсли вы не просили восстановить пароль — просто удалите это письмо, ваш аккаунт в "
            f"безопасности.\n\nРамзи барқарорсозии парол: {code}\n\n— {config.site_name}")
    html = layout(config, title="Восстановление пароля", lead="Код для восстановления пароля:", code=code,
                  note="Введите его на сайте и придумайте новый пароль. Код действует <b>10 минут</b>.",
                  tj=f"Рамзи барқарорсозии парол: <b>{code}</b>",
                  footer="Если вы не просили восстановить пароль — просто удалите это письмо. "
                         "Ваш аккаунт в безопасности, никто не сможет войти без этого кода.")
    if wait:
        return deliver(config, email, subject, text, html)
    threading.Thread(target=deliver, args=(config, email, subject, text, html), daemon=True).start()
    return True


def send_admin_hint(config: Config, email: str) -> bool:
    """Админ нажал «Забыли пароль?»: кода не даём (вход в админку защищён), но подсказываем, как войти."""
    if not ready(config):
        return False
    text = (f"Кто-то (возможно, вы) запросил восстановление пароля на {config.site_name} для аккаунта "
            "администратора.\n\nДля админа восстановление по коду на почту отключено — так безопаснее. "
            "Войдите через «Войти через Google» этой же почтой, либо задайте пароль на сервере.\n\n"
            "Если это были не вы — ничего не делайте, аккаунт в безопасности.")
    html = layout(config, title="Вход администратора",
                  lead="Кто-то (возможно, вы) запросил восстановление пароля для аккаунта администратора.",
                  note="Для админа восстановление по коду отключено — так безопаснее. Войдите кнопкой "
                       "<b>«Войти через Google»</b> этой же почтой.",
                  button=("Открыть вход", f"{config.base_url}/login"),
                  footer="Если это были не вы — ничего не делайте, аккаунт в безопасности.")
    threading.Thread(target=deliver, args=(config, email, f"Вход администратора {config.site_name}", text, html),
                     daemon=True).start()
    return True


def check_code(conn: sqlite3.Connection, config: Config, uid: int, code: str, kind: str = "verify") -> str:
    """'ok' | 'bad' (неверный, попытки ещё есть) | 'expired' (устарел или попытки кончились — нужен новый)."""
    _ensure(conn)
    code = "".join(ch for ch in (code or "") if ch.isdigit())
    row = conn.execute("SELECT * FROM mail_codes WHERE user_id = ? AND kind = ?", (uid, kind)).fetchone()
    u = conn.execute("SELECT email FROM users WHERE id = ?", (uid,)).fetchone()
    if row is None or u is None or row["email"] != u["email"].lower() or row["expires_at"] < time.time() \
            or row["tries"] >= CODE_TRIES:
        return "expired"
    if len(code) != 6 or not hmac.compare_digest(row["code_hash"], _hash(config, uid, code, kind)):
        conn.execute("UPDATE mail_codes SET tries = tries + 1 WHERE user_id = ? AND kind = ?", (uid, kind))
        return "expired" if row["tries"] + 1 >= CODE_TRIES else "bad"
    conn.execute("DELETE FROM mail_codes WHERE user_id = ? AND kind = ?", (uid, kind))
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
            log.info("письмо «%s» отправлено на %s", subject.split(" — ")[-1], to)
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
