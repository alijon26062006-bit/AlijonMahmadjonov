"""Условия для ботов партнёров: каждый бот должен принять правила Donatix (на таджикском).

Админ в «Конструкторе ботов» жмёт «Отправить условия»: в КАЖДЫЙ бот партнёра (всем его админам) уходит
сообщение от имени этого бота с условиями и тремя кнопками — «Розӣ ҳастам», «Қабул намекунам»,
«Ботро нест кардан». Кнопки ведут на страницу сайта /bot-terms/<ключ> (ключ — только у владельца бота),
там выбор подтверждается ещё одним нажатием — случайное открытие ссылки ничего не меняет.

  розӣ          — бот работает как раньше (если был выключен из-за условий — включается);
  қабул намекунам — бот выключается (причина 'terms'), сам владелец его не включит, пока не согласится;
  нест кардан    — бот удаляется из Donatix (данные бота остаются на диске, как при обычном удалении);
  нет ответа за DEADLINE_HOURS часов — бот выключается так же, как при отказе.

Код самих ботов (partner_bot/) не меняется: сообщение уходит напрямую через Telegram API токеном бота.
"""

from __future__ import annotations

import logging
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse

from . import db
from .config import Config
from .deps import get_config, get_conn, templates

log = logging.getLogger(__name__)
router = APIRouter(include_in_schema=False)

DEADLINE_HOURS = 72
ACTIONS = ("agree", "decline", "delete")

DEFAULT_TEXT = (
    "📜 <b>Шартҳои ҳамкорӣ бо Donatix</b>\n\n"
    "Боти шумо {bot} дар асоси Donatix кор мекунад. Барои идомаи кор бо ин шарт розӣ шавед:\n\n"
    "📢 <b>Реклама.</b> Donatix рекламаи худро дар <b>ҳамаи ботҳои шарикон</b> нишон медиҳад — дар боти шумо "
    "низ. Реклама ба мизоҷон дар менюи асосӣ, на зиёда аз 2 маротиба дар як рӯз нишон дода мешавад. "
    "Ба шумо ва админҳои бот реклама нишон дода намешавад.\n\n"
    "✅ <b>Розӣ ҳастам</b> — бот мисли пештара кор мекунад.\n"
    "❌ <b>Қабул намекунам</b> — бот хомӯш мешавад.\n"
    "🗑 <b>Ботро нест кардан</b> — бот аз Donatix хориҷ мешавад.\n\n"
    "⏳ Агар то {deadline} ҷавоб надиҳед, бот хомӯш мешавад."
)

TITLES = {"agree": "✅ Розӣ ҳастам", "decline": "❌ Қабул намекунам", "delete": "🗑 Ботро нест кардан"}
STATUS = {None: "⏳ ҷавоб нест", "agree": "✅ розӣ", "decline": "❌ рад кард", "timeout": "⌛ ҷавоб надод",
          "delete": "🗑 нест кард"}


def text(conn: sqlite3.Connection) -> str:
    return db.get_setting(conn, "botterms.text") or DEFAULT_TEXT


def save_text(conn: sqlite3.Connection, value: str) -> None:
    db.set_setting(conn, "botterms.text", value.strip() or DEFAULT_TEXT)


def version(conn: sqlite3.Connection) -> int:
    return int(db.get_setting(conn, "botterms.version") or 0)


def statuses(conn: sqlite3.Connection) -> dict[int, sqlite3.Row]:
    """Ответ каждого бота на последнюю рассылку условий."""
    v = version(conn)
    return {r["bot_id"]: r for r in conn.execute("SELECT * FROM bot_terms WHERE version = ?", (v,))}


def _deadline(sent_at: str, tz: int) -> str:
    dt = datetime.fromisoformat(sent_at.replace("Z", "+00:00")) + timedelta(hours=DEADLINE_HOURS)
    return dt.astimezone(timezone(timedelta(hours=tz))).strftime("%d.%m %H:%M")


def _send(token: str, chats: list[str], body: str, url: str) -> int:
    """Сообщение от имени бота партнёра с тремя кнопками-ссылками на страницу ответа."""
    markup = {"inline_keyboard": [[{"text": TITLES["agree"], "url": f"{url}?a=agree", "style": "success"}],
                                  [{"text": TITLES["decline"], "url": f"{url}?a=decline", "style": "danger"}],
                                  [{"text": TITLES["delete"], "url": f"{url}?a=delete"}]]}
    ok = 0
    for chat in chats:
        try:
            r = httpx.post(f"https://api.telegram.org/bot{token}/sendMessage", timeout=15,
                           json={"chat_id": int(chat), "text": body, "parse_mode": "HTML",
                                 "disable_web_page_preview": True, "reply_markup": markup})
            ok += bool(r.json().get("ok"))
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("условия в бот партнёра (чат %s): %s", chat, exc)
    return ok


def send_all(conn: sqlite3.Connection, config: Config, sender=_send) -> tuple[int, int]:
    """Новая рассылка условий во все боты. Вернёт (доставлено ботам, не доставлено)."""
    from .security import unseal
    v = version(conn) + 1
    db.set_setting(conn, "botterms.version", str(v))
    now = db.now()
    sent = failed = 0
    for b in conn.execute("SELECT * FROM bots ORDER BY id").fetchall():
        key = secrets.token_urlsafe(18)
        conn.execute("INSERT INTO bot_terms (bot_id, version, token, sent_at) VALUES (?, ?, ?, ?)", (b["id"], v, key, now))
        token = unseal(config.secret_key, b["token_enc"])
        chats = [c for c in str(b["admin_ids"] or "").replace(" ", "").split(",") if c.lstrip("-").isdigit()]
        body = text(conn).replace("{bot}", "@" + (b["username"] or "бот")).replace(
            "{deadline}", _deadline(now, config.tz_offset))
        if token and chats and sender(token, chats, body, f"{config.base_url.rstrip('/')}/bot-terms/{key}"):
            sent += 1
        else:
            failed += 1
    return sent, failed


def by_key(conn: sqlite3.Connection, key: str) -> sqlite3.Row | None:
    return conn.execute("SELECT t.*, b.username, b.enabled, b.disabled_reason, b.user_id FROM bot_terms t "
                        "LEFT JOIN bots b ON b.id = t.bot_id WHERE t.token = ?", (key,)).fetchone()


def answer(conn: sqlite3.Connection, config: Config, key: str, action: str) -> str:
    """Ответ владельца. Вернёт итог для страницы (на таджикском)."""
    from . import bots
    row = by_key(conn, key)
    if row is None or row["user_id"] is None:
        return "Ин бот дигар дар Donatix нест."
    if row["version"] != version(conn):
        return "Ин пайванд кӯҳна шудааст — паёми навро дар бот кушоед."
    if action not in ACTIONS:
        return ""
    conn.execute("UPDATE bot_terms SET answer = ?, answered_at = ? WHERE token = ?", (action, db.now(), key))
    if action == "agree":
        if not row["enabled"] and row["disabled_reason"] == "terms":
            conn.execute("UPDATE bots SET disabled_reason = NULL WHERE id = ?", (row["bot_id"],))
            bots.set_enabled(conn, row["bot_id"], True)
        result = "✅ Ташаккур! Шумо бо шартҳо розӣ шудед — бот кор мекунад."
    elif action == "decline":
        bots.set_enabled(conn, row["bot_id"], False)
        conn.execute("UPDATE bots SET disabled_reason = 'terms' WHERE id = ?", (row["bot_id"],))
        result = "❌ Шумо шартҳоро қабул накардед — бот хомӯш шуд. Агар фикратонро иваз кунед, «Розӣ ҳастам»-ро пахш кунед."
    else:
        bots.delete(conn, row["bot_id"], config)
        result = "🗑 Бот аз Donatix нест карда шуд."
    if bots.RUNNER:
        bots.RUNNER.poke()
    from .worker import notify_admin
    notify_admin(config, f"📜 Условия партнёров: @{row['username'] or row['bot_id']} — {STATUS[action]}")
    return result


def enforce(conn: sqlite3.Connection, now: datetime | None = None) -> int:
    """Кто не ответил за DEADLINE_HOURS — бот выключается (как при отказе)."""
    from . import bots
    v = version(conn)
    if not v:
        return 0
    limit = ((now or datetime.now(timezone.utc)) - timedelta(hours=DEADLINE_HOURS)).strftime("%Y-%m-%dT%H:%M:%S")
    rows = conn.execute("SELECT t.bot_id FROM bot_terms t JOIN bots b ON b.id = t.bot_id WHERE t.version = ? "
                        "AND t.answer IS NULL AND t.sent_at < ?", (v, limit)).fetchall()
    for r in rows:
        conn.execute("UPDATE bot_terms SET answer = 'timeout', answered_at = ? WHERE bot_id = ? AND version = ?",
                     (db.now(), r["bot_id"], v))
        bots.set_enabled(conn, r["bot_id"], False)
        conn.execute("UPDATE bots SET disabled_reason = 'terms' WHERE id = ?", (r["bot_id"],))
    if rows and bots.RUNNER:
        bots.RUNNER.poke()
    return len(rows)


# ── Страница ответа владельца (без входа: ключ из сообщения в его боте) ──

def _page(request: Request, conn, config: Config, key: str, action: str = "", done: str = "") -> HTMLResponse:
    row = by_key(conn, key)
    body = text(conn).replace("{bot}", "@" + ((row["username"] if row else None) or "бот")).replace(
        "{deadline}", _deadline(row["sent_at"], config.tz_offset) if row else "")
    from markupsafe import Markup, escape
    # текст пишет админ: экранируем всё, кроме <b>…</b>, переносы строк — <br>
    body = Markup(str(escape(body)).replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>").replace("\n", "<br>"))
    return templates.TemplateResponse(request, "bot_terms.html", {
        "row": row, "key": key, "action": action if action in ACTIONS else "", "done": done,
        "body": body, "titles": TITLES, "status": STATUS, "site_name": config.site_name,
        "current": row is not None and row["version"] == version(conn)})


@router.get("/bot-terms/{key}")
def page(key: str, request: Request, a: str = "", conn=Depends(get_conn), config: Config = Depends(get_config)):
    return _page(request, conn, config, key, a)


@router.post("/bot-terms/{key}")
def submit(key: str, request: Request, action: str = Form(""), sure: str = Form(""), conn=Depends(get_conn),
           config: Config = Depends(get_config)):
    if action == "delete" and sure != "1":
        return _page(request, conn, config, key, "delete")
    return _page(request, conn, config, key, done=answer(conn, config, key, action))


def stats(conn: sqlite3.Connection) -> dict[str, Any]:
    st = statuses(conn)
    return {"version": version(conn), "agree": sum(1 for r in st.values() if r["answer"] == "agree"),
            "pending": sum(1 for r in st.values() if r["answer"] is None),
            "off": sum(1 for r in st.values() if r["answer"] in ("decline", "timeout"))}
