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

TOPICS = {"order": "Заказ", "payment": "Пополнение", "account": "Аккаунт", "other": "Другое"}
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


def _save_file(config: Config, data: bytes) -> str | None:
    if not data:
        return None
    if len(data) > MAX_FILE:
        raise TicketError("Скриншот больше 5 МБ — уменьшите его.")
    from .payments import receipt_kind
    ext = receipt_kind(data)
    if ext is None:
        raise TicketError("Можно приложить картинку (JPG, PNG, WEBP) или PDF.")
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
        notify(conn, config, t["user_id"], f"💬 Ответ поддержки по обращению #{ticket_id}: {text[:200]}",
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

def alert_text(conn: sqlite3.Connection, config: Config, ticket_id: int, new: bool = False) -> str:
    from .tgbot import _e, client_name
    t = get(conn, ticket_id)
    u = conn.execute("SELECT login FROM users WHERE id = ?", (t["user_id"],)).fetchone()
    last = conn.execute("SELECT * FROM ticket_messages WHERE ticket_id = ? AND author = 'client' ORDER BY id DESC "
                        "LIMIT 1", (ticket_id,)).fetchone()
    head = "🎫 <b>Новый тикет" if new else "💬 <b>Сообщение в тикете"
    return (f"{head} #{ticket_id}</b> · {_e(TOPICS.get(t['topic'], ''))}"
            + (f" · {_e(t['order_ref'])}" if t["order_ref"] else "")
            + f"\nКлиент: {_e(client_name(conn, t['user_id'], u['login'] if u else '?'))}"
            + f"\nТема: {_e(t['subject'])}\n\n{_e((last['text'] if last else '')[:1500])}"
            + ("\n📎 приложен скриншот" if last and last["file"] else ""))


def admin_chat(config: Config) -> str:
    return str(config.support_admin_id or config.alert_telegram_chat_id or "").strip()


def app_url(config: Config, ticket_id: int | None = None) -> str:
    return f"{config.base_url}/support-app" + (f"?t={ticket_id}" if ticket_id else "")


def alert_admin(conn: sqlite3.Connection, config: Config, ticket_id: int, new: bool = False) -> None:
    """Админу в бот поддержки: сообщение с кнопкой «📂 Открыть» — открывается мини-приложение с перепиской."""
    text = alert_text(conn, config, ticket_id, new)
    import threading   # Telegram отвечает не мгновенно — клиент не ждёт, его сообщение уже сохранено
    threading.Thread(target=_deliver, args=(config, ticket_id, text), daemon=True).start()


_menu_set: set[str] = set()


def _deliver(config: Config, ticket_id: int, text: str) -> None:
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
            api("sendMessage", chat_id=chat, text=text, parse_mode="HTML", disable_web_page_preview=True,
                reply_markup={"inline_keyboard": [[{"text": "📂 Открыть и ответить",
                                                    "web_app": {"url": app_url(config, ticket_id)}}]]})
            return
        from .worker import notify_admin   # бот поддержки не подключён — хотя бы сообщение в админ-бот
        notify_admin(config, text + "\n\n⚠️ Бот поддержки не подключён (DONATIX_SUPPORT_BOT_TOKEN) — отвечать "
                                    "на тикеты можно будет в нём.", html=True)
    except Exception:  # noqa: BLE001 — тикет сохранён; админ увидит его в мини-приложении
        log.exception("тикет #%s: админу не доставлено", ticket_id)
