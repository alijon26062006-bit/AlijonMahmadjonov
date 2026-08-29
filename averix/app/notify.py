"""
Уведомления о новых заявках, откликах и анкетах.

Две независимые части:

  1. Запись в таблицу notifications — она есть всегда и видна в админке.
  2. Сообщение в Telegram — только если владелец задал токен и чат
     в переменных окружения.

Вторая часть не имеет права ломать первую: если Telegram недоступен,
токен неверный или сети нет, форма на сайте всё равно обязана
сохранить заявку и ответить посетителю «спасибо». Поэтому отправка
идёт после записи в базу, в фоне и с проглатыванием ошибок.

Токен читается только на сервере. Во фронтенд он не попадает никогда
и в журнал тоже: journal сам заменяет такие поля на «скрыто».
"""
import json
import sqlite3
import threading
import urllib.error
import urllib.request

from . import journal
from .config import TELEGRAM_CHAT, TELEGRAM_TOKEN

_TIMEOUT = 6


def _send_telegram(text: str) -> None:
    """Шлёт сообщение владельцу. Любая ошибка остаётся здесь."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        return
    payload = json.dumps({
        "chat_id": TELEGRAM_CHAT,
        "text": text[:3500],
        "disable_web_page_preview": True,
    }).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as answer:
            if answer.status != 200:
                journal.warn("telegram.не_доставлено", код=answer.status)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        # Ни текста ошибки от Telegram, ни адреса с токеном в журнал
        journal.warn("telegram.не_доставлено", причина=type(exc).__name__)


def notify(conn: sqlite3.Connection, kind: str, title: str,
           entity: str = "", entity_id: int | None = None) -> None:
    """Записывает уведомление и, если настроен Telegram, шлёт его туда."""
    conn.execute(
        "INSERT INTO notifications (kind, title, entity, entity_id)"
        " VALUES (?, ?, ?, ?)",
        (kind[:40], title[:300], entity[:40] or None, entity_id),
    )
    if TELEGRAM_TOKEN and TELEGRAM_CHAT:
        # Отдельным потоком: посетитель не должен ждать чужой сервер
        threading.Thread(
            target=_send_telegram,
            args=(f"AVERIX\n{title}",),
            daemon=True,
        ).start()


def unseen(conn: sqlite3.Connection) -> int:
    return int(conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE seen = 0"
    ).fetchone()[0])


def recent(conn: sqlite3.Connection, limit: int = 20) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM notifications ORDER BY created_at DESC, id DESC LIMIT ?",
        (limit,),
    ).fetchall()


def mark_all_seen(conn: sqlite3.Connection) -> None:
    conn.execute("UPDATE notifications SET seen = 1 WHERE seen = 0")
