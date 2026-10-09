"""Мини-приложение бота поддержки: тикеты с сайта — список, переписка как чат, ответ клиенту.

Открывается кнопкой «📂 Открыть и ответить» под уведомлением о тикете или кнопкой «Тикеты» у поля ввода
в боте поддержки. Кто открыл — узнаём по подписи Telegram (initData, подписана токеном бота): пускаем
только админа поддержки (DONATIX_SUPPORT_ADMIN_ID, иначе — чат админ-бота).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from typing import Any
from urllib.parse import parse_qsl

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, JSONResponse

from . import accounts, tickets
from .config import Config
from .deps import get_config, get_conn, templates

router = APIRouter(prefix="/support-app", include_in_schema=False)

INIT_TTL = 24 * 3600


LOGIN_TTL = 3600   # вход покупателя по подписи Telegram — подпись не старше часа (её могли подсмотреть)


def check_init(init_data: str, bot_token: str, now: float | None = None, ttl: int = INIT_TTL) -> dict[str, Any] | None:
    """Подпись Telegram WebApp: вернёт пользователя или None, если подпись чужая или старая."""
    if not init_data or not bot_token:
        return None
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    got = pairs.pop("hash", "")
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(hmac.new(secret, check.encode(), hashlib.sha256).hexdigest(), got):
        return None
    try:
        if (now or time.time()) - int(pairs.get("auth_date", "0")) > ttl:
            return None
        return json.loads(pairs.get("user") or "{}")
    except ValueError:
        return None


def _admin(request: Request, config: Config) -> bool:
    user = check_init(request.headers.get("x-tg-init", ""), config.support_bot_token)
    return bool(user) and str(user.get("id")) == tickets.admin_chat(config)


def _deny() -> JSONResponse:
    return JSONResponse({"error": "Откройте из бота поддержки (доступ только админу)."}, status_code=403)


def _file_sig(config: Config, name: str) -> str:
    return hmac.new(config.secret_key.encode(), f"tk-file:{name}".encode(), hashlib.sha256).hexdigest()[:24]


@router.get("")
def app_page(request: Request):
    return templates.TemplateResponse(request, "support_app.html", {})


@router.post("/api/list")
async def api_list(request: Request, conn=Depends(get_conn), config: Config = Depends(get_config)):
    if not _admin(request, config):
        return _deny()
    body = await request.json()
    from .tgbot import client_name
    items = tickets.listing(conn, status=str(body.get("status") or "active"))
    return {"items": [{"id": t["id"], "subject": t["subject"], "status": t["status"],
                       "status_title": tickets.STATUS[t["status"]], "topic": tickets.TOPICS.get(t["topic"], ""),
                       "order_ref": t["order_ref"] or "", "client": tickets.who_is(conn, t["user_id"]),
                       "last": (t["last_text"] or "")[:90], "last_author": t["last_author"],
                       "new": t["new_for_admin"], "at": t["updated_at"]} for t in items],
            "open": tickets.open_count(conn)}


@router.post("/api/ticket")
async def api_ticket(request: Request, conn=Depends(get_conn), config: Config = Depends(get_config)):
    if not _admin(request, config):
        return _deny()
    body = await request.json()
    t = tickets.get(conn, int(body.get("id") or 0))
    if t is None:
        return JSONResponse({"error": "Тикет не найден."}, status_code=404)
    from .money import fmt
    from .tgbot import client_name
    u = accounts.get_user(conn, t["user_id"])
    after = int(body.get("after") or 0)
    msgs = [{"id": m["id"], "author": m["author"], "who": m["who"] or "", "text": m["text"], "at": m["created_at"],
             "file": (f"/support-app/file/{m['file']}?s={_file_sig(config, m['file'])}" if m["file"] else ""),
             "kind": tickets.file_kind(m["file"])}
            for m in tickets.messages(conn, t["id"], after)]
    tickets.seen(conn, t["id"], "admin")
    orders = conn.execute("SELECT public_id, product_name, status, total_micro FROM orders WHERE user_id = ? "
                          "ORDER BY id DESC LIMIT 5", (t["user_id"],)).fetchall()
    return {"id": t["id"], "subject": t["subject"], "status": t["status"], "name": tickets.who_is(conn, t["user_id"]),
            "status_title": tickets.STATUS[t["status"]], "topic": tickets.TOPICS.get(t["topic"], ""),
            "order_ref": t["order_ref"] or "", "client": client_name(conn, t["user_id"], u["login"] if u else "?"),
            "balance": fmt(u["balance_micro"]) if u else "0", "messages": msgs,
            "orders": [{"id": o["public_id"], "name": o["product_name"], "status": o["status"],
                        "total": fmt(o["total_micro"])} for o in orders]}


@router.post("/api/reply")
async def api_reply(request: Request, conn=Depends(get_conn), config: Config = Depends(get_config)):
    """Ответ клиенту: текст, голосовое или файл (чек, скриншот). Форма (с файлом) или JSON."""
    if not _admin(request, config):
        return _deny()
    data = b""
    if request.headers.get("content-type", "").startswith("multipart/"):
        form = await request.form()
        body = {k: form.get(k) for k in ("id", "text", "close")}
        up = form.get("file")
        if up is not None and getattr(up, "filename", ""):
            data = await up.read()
    else:
        body = await request.json()
    tid = int(body.get("id") or 0)
    try:
        tickets.add(conn, config, tid, "admin", str(body.get("text") or ""), data, who="поддержка")
        if body.get("close") in (True, "1", "true"):
            tickets.set_status(conn, tid, closed=True)
    except tickets.TicketError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return {"ok": True}


@router.post("/api/history")
async def api_history(request: Request, conn=Depends(get_conn), config: Config = Depends(get_config)):
    """История клиента — только посмотреть: баланс, пополнения, куда тратил, какие заказы."""
    if not _admin(request, config):
        return _deny()
    body = await request.json()
    t = tickets.get(conn, int(body.get("id") or 0))
    if t is None:
        return JSONResponse({"error": "Тикет не найден."}, status_code=404)
    from .money import fmt
    uid = t["user_id"]
    u = accounts.get_user(conn, uid)
    got = conn.execute("SELECT COALESCE(SUM(amount_micro), 0) FROM transactions WHERE user_id = ? "
                       "AND amount_micro > 0 AND note LIKE 'Пополнение%'", (uid,)).fetchone()[0]
    spent, n_done = conn.execute("SELECT COALESCE(SUM(total_micro), 0), COUNT(*) FROM orders WHERE user_id = ? "
                                 "AND status = 'completed'", (uid,)).fetchone()
    ops = conn.execute("SELECT t.amount_micro, t.note, t.balance_after, t.created_at, o.product_name, o.public_id "
                       "FROM transactions t LEFT JOIN orders o ON o.id = t.order_id WHERE t.user_id = ? "
                       "ORDER BY t.id DESC LIMIT 100", (uid,)).fetchall()
    orders = conn.execute("SELECT public_id, product_name, status, total_micro, fields_json, created_at FROM orders "
                          "WHERE user_id = ? ORDER BY id DESC LIMIT 50", (uid,)).fetchall()
    pays = conn.execute("SELECT id, status, pay_amount, pay_currency, created_at FROM payments WHERE user_id = ? "
                        "ORDER BY id DESC LIMIT 30", (uid,)).fetchall()
    return {
        "name": tickets.who_is(conn, uid), "balance": fmt(u["balance_micro"]) if u else "0",
        "topped": fmt(got), "spent": fmt(spent), "orders_done": n_done,
        "ops": [{"amount": fmt(abs(o["amount_micro"])), "plus": o["amount_micro"] > 0,
                 "what": (f"{o['public_id']} · {o['product_name']}" if o["product_name"] else o["note"] or ""),
                 "after": fmt(o["balance_after"]), "at": o["created_at"]} for o in ops],
        "orders": [{"id": o["public_id"], "name": o["product_name"], "status": o["status"],
                    "total": fmt(o["total_micro"]),
                    "to": ", ".join(str(v) for v in json.loads(o["fields_json"] or "{}").values()),
                    "at": o["created_at"]} for o in orders],
        "pays": [{"id": p["id"], "status": p["status"], "amount": f"{p['pay_amount']} {p['pay_currency']}",
                  "at": p["created_at"]} for p in pays],
    }


@router.post("/api/status")
async def api_status(request: Request, conn=Depends(get_conn), config: Config = Depends(get_config)):
    if not _admin(request, config):
        return _deny()
    body = await request.json()
    tid = int(body.get("id") or 0)
    if tickets.get(conn, tid) is None:
        return JSONResponse({"error": "Тикет не найден."}, status_code=404)
    tickets.set_status(conn, tid, closed=bool(body.get("closed")))
    return {"ok": True}


@router.get("/file/{name}")
def app_file(name: str, s: str = "", config: Config = Depends(get_config)):
    """Скриншот из тикета — по подписанной ссылке (картинка в <img> не может нести подпись Telegram)."""
    path = tickets.files_dir(config) / name
    if (not re.fullmatch(r"[0-9a-f]{20}\.(jpg|png|webp|pdf|webm|ogg|mp3|m4a|wav)", name) or not hmac.compare_digest(s, _file_sig(config, name))
            or not path.is_file()):
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(path, media_type=tickets.media_type(name), headers={"Cache-Control": "private, max-age=86400"})



# ── Покупатель бота-магазина: «🛟 Поддержка» открывает тикеты на сайте прямо в Telegram ──
# Бот-магазин даёт кнопку-мини-приложение. Страница присылает подпись Telegram (ключ — токен бота-магазина),
# по ней узнаём покупателя, входим в его аккаунт (тот же, что у бота) и открываем «Поддержку» на сайте.


@router.get("/me")
def me_page(request: Request):
    return templates.TemplateResponse(request, "support_me.html", {})


@router.post("/me/login")
async def me_login(request: Request, conn=Depends(get_conn), config: Config = Depends(get_config)):
    import secrets as _secrets

    from . import db, shopbot
    # Только настоящий JSON: форма с чужого сайта (text/plain) могла «залогинить» человека в чужой аккаунт,
    # и его пополнение ушло бы туда. JSON с другого сайта браузер без нашего разрешения (CORS) не отправит.
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
        return JSONResponse({"error": "Неверный запрос."}, status_code=415)
    try:
        body = await request.json()
    except ValueError:
        return JSONResponse({"error": "Неверный запрос."}, status_code=400)
    user = check_init(str(body.get("init") or "") if isinstance(body, dict) else "", config.shop_bot_token,
                      ttl=LOGIN_TTL)
    su = shopbot.shop_user(conn, int(user["id"])) if user and user.get("id") else None
    if su is None:
        return JSONResponse({"error": "Откройте поддержку из бота-магазина."}, status_code=403)
    u = accounts.get_user(conn, su["user_id"])
    if u is None or u["status"] != "active":
        return JSONResponse({"error": "Аккаунт недоступен."}, status_code=403)
    if u["role"] != "client":   # админ входит только паролем и кодом (2FA), не через мини-приложение
        return JSONResponse({"error": "Этот аккаунт входит на сайт через пароль."}, status_code=403)
    request.session.clear()
    sid = _secrets.token_urlsafe(24)
    conn.execute("INSERT INTO logins (user_id, ip, user_agent, created_at, sid) VALUES (?, ?, ?, ?, ?)",
                 (u["id"], (request.client.host if request.client else "?")[:64],
                  "Telegram (бот-магазин)", db.now(), sid))
    request.session["user_id"], request.session["sid"] = u["id"], sid
    return {"ok": True, "next": "/panel/support"}
