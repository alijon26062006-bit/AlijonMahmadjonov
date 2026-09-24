"""Уведомления клиентам: в кабинете (колокольчик) и, если настроена почта, на email."""

from __future__ import annotations

import logging
import smtplib
import sqlite3
import threading
from email.message import EmailMessage

from . import db
from .config import Config

log = logging.getLogger(__name__)


def notify(conn: sqlite3.Connection, config: Config | None, user_id: int, text: str, link: str = "") -> None:
    conn.execute(
        "INSERT INTO notifications (user_id, text, link, created_at) VALUES (?, ?, ?, ?)",
        (user_id, text[:500], link or None, db.now()),
    )
    if config and config.smtp_host:
        row = conn.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()
        if row:
            threading.Thread(target=_send_email, args=(config, row["email"], text, link), daemon=True).start()


def _send_email(config: Config, to: str, text: str, link: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = f"{config.site_name}: {text[:80]}"
    msg["From"] = config.smtp_from or config.smtp_user
    msg["To"] = to
    body = text + (f"\n\n{config.base_url}{link}" if link else "") + f"\n\n— {config.site_name}"
    msg.set_content(body)
    try:
        with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=20) as s:
            s.starttls()
            if config.smtp_user:
                s.login(config.smtp_user, config.smtp_password)
            s.send_message(msg)
    except Exception as exc:  # почта не должна ломать работу сайта
        log.warning("письмо на %s не отправлено: %s", to, exc)


def unread_count(conn: sqlite3.Connection, user_id: int) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND read_at IS NULL", (user_id,)
    ).fetchone()[0]


def latest(conn: sqlite3.Connection, user_id: int, limit: int = 50) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM notifications WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit)
    ).fetchall()


def mark_read(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute("UPDATE notifications SET read_at = ? WHERE user_id = ? AND read_at IS NULL", (db.now(), user_id))
