"""Бот поддержки — только для тикетов с сайта.

Клиенты в боте не переписываются: поддержка — тикетом на сайте (бот отвечает ссылкой). Админу бот приносит
каждое сообщение клиента: имя и кнопка «💬 Открыть чат» (мини-приложение, support_app.py). Ответить можно и прямо
в боте: reply на сообщение о тикете — текстом, голосовым, фото или файлом — и это уйдёт в тикет клиенту.
"""

from __future__ import annotations

import logging
import re
import threading
from typing import Any, Callable

from . import db, tickets
from .config import Config

log = logging.getLogger(__name__)

POLL_SECONDS = 25
_TICKET = re.compile(r"[Тт]икет #(\d+)")


class TicketBot:
    def __init__(self, config: Config, api: Callable[..., Any] | None = None):
        from .tgbot import TelegramApi
        self.config = config
        self.api = api or TelegramApi(config.support_bot_token)
        self.admin = tickets.admin_chat(config)
        self._stop = threading.Event()

    def start(self) -> None:
        threading.Thread(target=self._run, name="donatix-ticketbot", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        conn = db.connect(self.config.db_path)
        offset = int(db.get_setting(conn, "ticketbot.offset", "0") or 0)
        try:
            self.api("deleteWebhook", drop_pending_updates=False)
            me = self.api("getMe") or {}
            if me.get("username"):
                db.set_setting(conn, "support.bot_username", me["username"])
            self.api("setMyCommands", commands=[{"command": "start", "description": "Тикеты поддержки"}])
            self.menu()
        except Exception as exc:  # noqa: BLE001
            log.warning("бот поддержки: %s", exc)
        try:
            while not self._stop.is_set():
                try:
                    updates = self.api("getUpdates", offset=offset, timeout=POLL_SECONDS,
                                       allowed_updates=["message"]) or []
                except Exception as exc:  # noqa: BLE001
                    log.warning("бот поддержки: %s", exc)
                    self._stop.wait(10)
                    continue
                for upd in updates:
                    offset = max(offset, int(upd["update_id"]) + 1)
                    try:
                        self.handle(conn, upd)
                    except Exception:
                        log.exception("бот поддержки: обработка %s", upd.get("update_id"))
                if updates:
                    db.set_setting(conn, "ticketbot.offset", str(offset))
        finally:
            conn.close()

    def send(self, chat: Any, text: str, markup: dict | None = None) -> None:
        self.api("sendMessage", chat_id=chat, text=text, parse_mode="HTML", disable_web_page_preview=True,
                 reply_markup=markup)

    def menu(self) -> None:
        """Кнопка «Тикеты» у поля ввода — все обращения в один тап."""
        if self.admin:
            self.api("setChatMenuButton", chat_id=self.admin, menu_button={
                "type": "web_app", "text": "Тикеты", "web_app": {"url": tickets.app_url(self.config)}})

    def handle(self, conn, upd: dict[str, Any]) -> None:
        msg = upd.get("message") or {}
        chat = msg.get("chat") or {}
        if chat.get("type") != "private":
            return
        tg_id = str(chat.get("id"))
        if tg_id != self.admin:   # клиенты — на сайт, переписка только тикетами
            self.send(tg_id, "🛟 Поддержка Donatix — на сайте: откройте обращение, ответим там и пришлём уведомление."
                             "\n🛟 Дастгирии Donatix — дар сайт: муроҷиат кушоед, ҷавоб ҳамон ҷо меояд.\n\n"
                             f"{self.config.base_url}/panel/support")
            return
        text = (msg.get("text") or msg.get("caption") or "").strip()
        original = (msg.get("reply_to_message") or {}).get("text") or ""
        found = _TICKET.search(original)
        if found:
            self.reply(conn, int(found.group(1)), msg, text)
            return
        open_n = tickets.open_count(conn)
        self.send(self.admin, f"🎫 Тикетов ждут ответа: <b>{open_n}</b>\n\nОтветить клиенту: кнопка «💬 Открыть чат» "
                              "под его сообщением или reply на это сообщение — текстом, голосовым, фото.",
                  {"inline_keyboard": [[{"text": "📂 Все тикеты", "web_app": {"url": tickets.app_url(self.config)}}]]})
        try:
            self.menu()
        except Exception:  # noqa: BLE001
            pass

    def reply(self, conn, ticket_id: int, msg: dict[str, Any], text: str) -> None:
        """Reply админа в боте → в тикет: текст, голосовое, фото, файл."""
        data = b""
        media = (msg.get("voice") or msg.get("audio") or msg.get("document")
                 or (msg.get("photo") or [None])[-1])
        if media and media.get("file_id"):
            try:
                data = self.api.download(media["file_id"], max_bytes=tickets.MAX_AUDIO)
            except Exception as exc:  # noqa: BLE001
                self.send(self.admin, f"⚠️ Не удалось получить файл: {exc}")
                return
        try:
            tickets.add(conn, self.config, ticket_id, "admin", text, data, who="поддержка")
        except tickets.TicketError as exc:
            self.send(self.admin, f"⚠️ {exc}")
            return
        self.send(self.admin, f"✅ Отправлено клиенту в тикет #{ticket_id}.")
