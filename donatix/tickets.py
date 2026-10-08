"""Поддержка на сайте — тикеты, как у FazerCards.

Клиент в кабинете открывает обращение: тема, о чём (заказ, пополнение…), номер заказа, текст и скриншот.
Дальше — переписка как в чате. Новое сообщение клиента сразу приходит админу в бот поддержки с кнопкой
«📂 Открыть» — внутри Telegram открывается мини-приложение с перепиской, там и отвечает. Ответ админа клиент видит на сайте
и получает уведомление (сайт, телефон, бот-магазин). Админ отвечает в мини-приложении бота поддержки (support_app.py): всё читается как чат.
"""

from __future__ import annotations

import logging
import secrets
import sqlite3
from pathlib import Path
from typing import Any

from . import db
from .config import Config

log = logging.getLogger(__name__)

from .support_kb import TOPIC_TITLES as TOPICS  # noqa: E402 — темы и тексты в одном месте
STATUS = {"open": "Ждёт ответа", "answered": "Есть ответ", "closed": "Закрыт"}
MAX_TEXT = 3000
MAX_FILE = 5 * 1024 * 1024
OPEN_LIMIT = 5                 # открытых обращений у одного клиента одновременно


class TicketError(ValueError):
    pass


def files_dir(config: Config) -> Path:
    path = Path(config.db_path).parent / "tickets"
    path.mkdir(parents=True, exist_ok=True)
    return path


AUDIO = ("webm", "ogg", "mp3", "m4a", "wav")
MAX_AUDIO = 15 * 1024 * 1024


def _kind(data: bytes) -> str | None:
    """Тип файла по содержимому: картинка, PDF или голосовое (запись в браузере — webm/ogg/m4a)."""
    from .payments import receipt_kind
    ext = receipt_kind(data)
    if ext:
        return ext
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return "webm"
    if data[:4] == b"OggS":
        return "ogg"
    if data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "mp3"
    if data[4:8] == b"ftyp":
        return "m4a"
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "wav"
    return None


def file_kind(name: str | None) -> str:
    """image | pdf | audio — как показывать вложение."""
    ext = (name or "").rsplit(".", 1)[-1]
    return "audio" if ext in AUDIO else ("pdf" if ext == "pdf" else "image")


def media_type(name: str) -> str:
    ext = name.rsplit(".", 1)[-1]
    return {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp", "pdf": "application/pdf",
            "webm": "audio/webm", "ogg": "audio/ogg", "mp3": "audio/mpeg", "m4a": "audio/mp4",
            "wav": "audio/wav"}.get(ext, "application/octet-stream")


def _save_file(config: Config, data: bytes) -> str | None:
    if not data:
        return None
    ext = _kind(data)
    if ext is None:
        raise TicketError("Можно приложить картинку (JPG, PNG, WEBP), PDF или голосовое сообщение.")
    if len(data) > (MAX_AUDIO if ext in AUDIO else MAX_FILE):
        raise TicketError("Файл слишком большой: картинка — до 5 МБ, голосовое — до 15 МБ.")
    name = f"{secrets.token_hex(10)}.{ext}"
    (files_dir(config) / name).write_bytes(data)
    return name


def create(conn: sqlite3.Connection, config: Config, user_id: int, subject: str, topic: str, order_ref: str,
           text: str, file: bytes = b"") -> int:
    subject, text, order_ref = subject.strip()[:120], text.strip()[:MAX_TEXT], order_ref.strip()[:40]
    if topic not in TOPICS:
        topic = "other"
    if not text:
        raise TicketError("Опишите проблему — хотя бы пару слов.")
    if not subject:
        subject = (TOPICS[topic] + (f" {order_ref}" if order_ref else "")).strip()
    n_open = conn.execute("SELECT COUNT(*) FROM tickets WHERE user_id = ? AND status != 'closed'",
                          (user_id,)).fetchone()[0]
    if n_open >= OPEN_LIMIT:
        raise TicketError(f"У вас уже {n_open} открытых обращений — напишите в одно из них или закройте лишние.")
    name = _save_file(config, file)
    now = db.now()
    with db.tx(conn):
        tid = int(conn.execute(
            "INSERT INTO tickets (user_id, subject, topic, order_ref, status, created_at, updated_at, client_seen_at) "
            "VALUES (?, ?, ?, ?, 'open', ?, ?, ?)",
            (user_id, subject, topic, order_ref or None, now, now, now)).lastrowid)
        conn.execute("INSERT INTO ticket_messages (ticket_id, author, text, file, created_at) VALUES (?, 'client', ?, ?, ?)",
                     (tid, text, name, now))
    alert_admin(conn, config, tid, new=True)
    return tid


def get(conn: sqlite3.Connection, ticket_id: int, user_id: int | None = None) -> sqlite3.Row | None:
    """Тикет; с user_id — только свой."""
    if user_id is None:
        return conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    return conn.execute("SELECT * FROM tickets WHERE id = ? AND user_id = ?", (ticket_id, user_id)).fetchone()


def messages(conn: sqlite3.Connection, ticket_id: int, after: int = 0) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM ticket_messages WHERE ticket_id = ? AND id > ? ORDER BY id",
                        (ticket_id, after)).fetchall()


def listing(conn: sqlite3.Connection, user_id: int | None = None, status: str = "") -> list[dict[str, Any]]:
    """Тикеты с последним сообщением и пометкой «есть новое» — для клиента (user_id) или для админа."""
    where, args = "1=1", []
    if user_id is not None:
        where += " AND t.user_id = ?"
        args.append(user_id)
    if status == "active":
        where += " AND t.status != 'closed'"
    elif status in STATUS:
        where += " AND t.status = ?"
        args.append(status)
    rows = conn.execute(
        "SELECT t.*, u.login, u.email, "
        "(SELECT text FROM ticket_messages m WHERE m.ticket_id = t.id ORDER BY m.id DESC LIMIT 1) AS last_text, "
        "(SELECT author FROM ticket_messages m WHERE m.ticket_id = t.id ORDER BY m.id DESC LIMIT 1) AS last_author, "
        "(SELECT MAX(created_at) FROM ticket_messages m WHERE m.ticket_id = t.id AND m.author = 'admin') AS last_admin, "
        "(SELECT MAX(created_at) FROM ticket_messages m WHERE m.ticket_id = t.id AND m.author = 'client') AS last_client "
        f"FROM tickets t JOIN users u ON u.id = t.user_id WHERE {where} "
        "ORDER BY (t.status = 'closed'), t.updated_at DESC LIMIT 200", args).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["new_for_client"] = bool(d["last_admin"] and d["last_admin"] > (d["client_seen_at"] or ""))
        d["new_for_admin"] = bool(d["last_client"] and d["last_client"] > (d["admin_seen_at"] or ""))
        out.append(d)
    return out


def add(conn: sqlite3.Connection, config: Config, ticket_id: int, author: str, text: str, file: bytes = b"",
        who: str = "") -> int:
    """Сообщение в тикет. Клиент написал — админу в Telegram; админ ответил — клиенту уведомление."""
    t = get(conn, ticket_id)
    if t is None:
        raise TicketError("Обращение не найдено.")
    text = text.strip()[:MAX_TEXT]
    if not text and not file:
        raise TicketError("Напишите сообщение.")
    name = _save_file(config, file)
    now = db.now()
    status = "open" if author == "client" else "answered"
    seen = "client_seen_at" if author == "client" else "admin_seen_at"
    with db.tx(conn):
        mid = int(conn.execute(
            "INSERT INTO ticket_messages (ticket_id, author, who, text, file, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (ticket_id, author, who or None, text, name, now)).lastrowid)
        conn.execute(f"UPDATE tickets SET status = ?, updated_at = ?, {seen} = ? WHERE id = ?",
                     (status, now, now, ticket_id))
    if author == "client":
        alert_admin(conn, config, ticket_id)
    else:
        from .notify import notify
        notify(conn, config, t["user_id"], f"💬 Ответ поддержки по обращению #{ticket_id}: "
                                           + (text[:200] or attach_label(name)),
               f"/panel/support/{ticket_id}")
    return mid


def set_status(conn: sqlite3.Connection, ticket_id: int, closed: bool) -> None:
    conn.execute("UPDATE tickets SET status = ?, updated_at = ? WHERE id = ?",
                 ("closed" if closed else "open", db.now(), ticket_id))


def seen(conn: sqlite3.Connection, ticket_id: int, by: str) -> None:
    column = "client_seen_at" if by == "client" else "admin_seen_at"
    conn.execute(f"UPDATE tickets SET {column} = ? WHERE id = ?", (db.now(), ticket_id))


def unread_for_client(conn: sqlite3.Connection, user_id: int) -> int:
    return sum(1 for t in listing(conn, user_id) if t["new_for_client"])


def open_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM tickets WHERE status = 'open'").fetchone()[0]


# ── Админу в Telegram ──────────────────────────────────────────

def who_is(conn: sqlite3.Connection, user_id: int) -> str:
    """Имя клиента для поддержки: имя из Telegram (если покупал в боте), логин или «Гость G-…»."""
    from .tgbot import buyer_of, client_name
    u = conn.execute("SELECT login FROM users WHERE id = ?", (user_id,)).fetchone()
    name = client_name(conn, user_id, u["login"] if u else "?")
    su = buyer_of(conn, user_id)
    if su is not None and su["name"]:
        name = f"{su['name']} ({name})"
    return name


def attach_label(name: str | None) -> str:
    return {"audio": "🎤 голосовое", "pdf": "📎 PDF", "image": "🖼 скриншот"}[file_kind(name)] if name else ""


def alert_text(conn: sqlite3.Connection, config: Config, ticket_id: int, new: bool = False) -> str:
    from .tgbot import _e
    t = get(conn, ticket_id)
    last = conn.execute("SELECT * FROM ticket_messages WHERE ticket_id = ? AND author = 'client' ORDER BY id DESC "
                        "LIMIT 1", (ticket_id,)).fetchone()
    body = _e((last["text"] if last else "")[:1200])
    extra = attach_label(last["file"]) if last else ""
    return (f"👤 <b>{_e(who_is(conn, t['user_id']))}</b>\n"
            + ("🎫 Новый тикет" if new else "💬 Тикет") + f" #{ticket_id} · {_e(TOPICS.get(t['topic'], ''))}"
            + (f" · {_e(t['order_ref'])}" if t["order_ref"] else "") + f"\n<i>{_e(t['subject'])}</i>\n\n"
            + (body or "") + (f"\n{extra}" if extra else ""))


def admin_chat(config: Config) -> str:
    return str(config.support_admin_id or config.alert_telegram_chat_id or "").strip()


def app_url(config: Config, ticket_id: int | None = None) -> str:
    return f"{config.base_url}/support-app" + (f"?t={ticket_id}" if ticket_id else "")


def alert_admin(conn: sqlite3.Connection, config: Config, ticket_id: int, new: bool = False) -> None:
    """Админу в бот поддержки: сообщение с кнопкой «📂 Открыть» — открывается мини-приложение с перепиской."""
    text = alert_text(conn, config, ticket_id, new)
    t = get(conn, ticket_id)
    reply_to = t["admin_msg"] if t is not None and "admin_msg" in t.keys() else None
    import threading   # Telegram отвечает не мгновенно — клиент не ждёт, его сообщение уже сохранено
    threading.Thread(target=_deliver, args=(config, ticket_id, text, reply_to), daemon=True).start()


_menu_set: set[str] = set()


def _deliver(config: Config, ticket_id: int, text: str, reply_to: int | None = None) -> None:
    """Каждый человек — своя ветка: первое сообщение тикета, следующие приходят ответом (reply) на него."""
    chat = admin_chat(config)
    try:
        if config.support_bot_token and chat:
            from .tgbot import TelegramApi
            api = TelegramApi(config.support_bot_token)
            if chat not in _menu_set:   # кнопка «Тикеты» слева от поля ввода — все обращения в один тап
                try:
                    api("setChatMenuButton", chat_id=chat, menu_button={
                        "type": "web_app", "text": "Тикеты", "web_app": {"url": app_url(config)}})
                    _menu_set.add(chat)
                except Exception as exc:  # noqa: BLE001
                    log.warning("тикеты: кнопка меню не поставлена: %s", exc)
            markup = {"inline_keyboard": [[{"text": "💬 Открыть чат", "web_app": {"url": app_url(config, ticket_id)}}]]}
            extra = ({"reply_parameters": {"message_id": reply_to, "allow_sending_without_reply": True}}
                     if reply_to else {})
            sent = api("sendMessage", chat_id=chat, text=text, parse_mode="HTML", disable_web_page_preview=True,
                       reply_markup=markup, **extra) or {}
            if not reply_to and sent.get("message_id"):
                c = db.connect(config.db_path)
                try:
                    c.execute("UPDATE tickets SET admin_msg = ? WHERE id = ? AND admin_msg IS NULL",
                              (sent["message_id"], ticket_id))
                finally:
                    c.close()
            return
        from .worker import notify_admin   # бот поддержки не подключён — хотя бы сообщение в админ-бот
        notify_admin(config, text + "\n\n⚠️ Бот поддержки не подключён (DONATIX_SUPPORT_BOT_TOKEN) — отвечать "
                                    "на тикеты можно будет в нём.", html=True)
    except Exception:  # noqa: BLE001 — тикет сохранён; админ увидит его в мини-приложении
        log.exception("тикет #%s: админу не доставлено", ticket_id)
