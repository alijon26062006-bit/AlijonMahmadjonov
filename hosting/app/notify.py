"""Уведомления: владельцу — в Telegram, клиентам — на почту.

Если ключи не заданы, уведомление просто пишется в лог. Отправка идёт в фоне,
ошибка доставки никогда не ломает основное действие (заказ, оплату и т.п.).
"""
from __future__ import annotations

import logging
import smtplib
import ssl
import threading
from email.message import EmailMessage

import httpx

from .config import Settings

log = logging.getLogger("hosting.notify")


class Notifier:
    def __init__(self, settings: Settings, background: bool = True):
        self.s = settings
        self.background = background
        self.sent: list[tuple[str, str, str]] = []  # (канал, кому, текст) — для тестов и отладки

    def _run(self, fn, *args) -> None:
        if self.background:
            threading.Thread(target=fn, args=args, daemon=True).start()
        else:
            fn(*args)

    # ── владельцу ──
    def admin(self, text: str) -> None:
        self.sent.append(("telegram", "admin", text))
        if not (self.s.telegram_bot_token and self.s.telegram_admin_chat_id):
            log.info("admin: %s", text)
            return
        self._run(self._telegram, text)

    def _telegram(self, text: str) -> None:
        try:
            httpx.post(f"https://api.telegram.org/bot{self.s.telegram_bot_token}/sendMessage",
                       json={"chat_id": self.s.telegram_admin_chat_id, "text": f"{self.s.brand_name}\n{text}",
                             "disable_web_page_preview": True}, timeout=10)
        except httpx.HTTPError as e:
            log.warning("telegram: %s", e.__class__.__name__)

    def admin_file(self, text: str, path, mime: str) -> None:
        """Сообщение владельцу с файлом (чек об оплате): фото — как фото, остальное — как документ."""
        self.sent.append(("telegram_file", "admin", f"{text}\n[{path}]"))
        if not (self.s.telegram_bot_token and self.s.telegram_admin_chat_id):
            log.info("admin (file %s): %s", path, text)
            return
        self._run(self._telegram_file, text, str(path), mime)

    def _telegram_file(self, text: str, path: str, mime: str) -> None:
        as_photo = mime in ("image/jpeg", "image/png", "image/webp")
        method, field = ("sendPhoto", "photo") if as_photo else ("sendDocument", "document")
        try:
            with open(path, "rb") as fh:
                httpx.post(f"https://api.telegram.org/bot{self.s.telegram_bot_token}/{method}",
                           data={"chat_id": self.s.telegram_admin_chat_id, "caption": f"{self.s.brand_name}\n{text}"[:1000]},
                           files={field: (path.rsplit("/", 1)[-1], fh, mime)}, timeout=30)
        except (httpx.HTTPError, OSError) as e:
            log.warning("telegram file: %s", e.__class__.__name__)
            self._telegram(text + "\n(чек не удалось приложить — смотрите в админке)")

    # ── клиенту ──
    def email(self, to: str, subject: str, body: str) -> None:
        self.sent.append(("email", to, f"{subject}\n{body}"))
        if not (self.s.smtp_host and self.s.smtp_from):
            log.info("email to %s: %s", to, subject)
            return
        self._run(self._smtp, to, subject, body)

    def _smtp(self, to: str, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["From"] = f"{self.s.brand_name} <{self.s.smtp_from}>"
        msg["To"] = to
        msg["Subject"] = subject
        signature = f"\n\n—\n{self.s.brand_name}"
        if self.s.support_telegram:
            signature += f"\nПоддержка в Telegram: https://t.me/{self.s.support_telegram}"
        if self.s.support_email:
            signature += f"\nПочта поддержки: {self.s.support_email}"
        msg.set_content(body + signature + f"\nЛичный кабинет: {self.s.public_url}/app")
        try:
            if self.s.smtp_port == 465:
                server = smtplib.SMTP_SSL(self.s.smtp_host, 465, context=ssl.create_default_context(), timeout=20)
            else:
                server = smtplib.SMTP(self.s.smtp_host, self.s.smtp_port, timeout=20)
                if self.s.smtp_tls:
                    server.starttls(context=ssl.create_default_context())
            with server:
                if self.s.smtp_user:
                    server.login(self.s.smtp_user, self.s.smtp_password)
                server.send_message(msg)
        except (OSError, smtplib.SMTPException) as e:
            log.warning("smtp to %s: %s", to, e.__class__.__name__)
