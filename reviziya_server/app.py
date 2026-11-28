"""HTTP-сервер мини-аппа: отдаёт страницу и принимает запросы от неё.

Каждый запрос к /api/ несёт подписанные Telegram данные запуска, по ним сервер
узнаёт сотрудника. Ключ Anthropic живёт только здесь, в телефоны он не попадает.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import logging
import time
from collections import defaultdict, deque

from aiohttp import web

from . import db, report
from .reader import ReaderError
from .tgauth import AuthError, check_init_data

log = logging.getLogger("reviziya.app")

MAX_IMAGE_BYTES = 400_000      # кадр из рамки весит 20-60 КБ, это запас
SCANS_PER_MINUTE = 120         # на одного сотрудника: защита ключа от случайного цикла
MAX_AMOUNT = 100_000_000
PARALLEL_READS = 8


def err(code: str, status: int = 400) -> web.Response:
    return web.json_response({"error": code}, status=status)


def _name(tg_user: dict) -> str:
    full = " ".join(p for p in (tg_user.get("first_name"), tg_user.get("last_name")) if p).strip()
    return (full or tg_user.get("username") or "Сотрудник")[:60]


def create_app(config, conn, reader, notifier) -> web.Application:
    app = web.Application(client_max_size=MAX_IMAGE_BYTES * 2, middlewares=[_no_cache, _auth])
    app["config"], app["conn"], app["reader"], app["notifier"] = config, conn, reader, notifier
    app["hits"] = defaultdict(deque)
    app["reads"] = asyncio.Semaphore(PARALLEL_READS)

    r = app.router
    r.add_get("/api/health", health)
    r.add_post("/api/me", me)
    r.add_post("/api/scan", scan)
    r.add_post("/api/add", add)
    r.add_post("/api/minus", minus)
    r.add_post("/api/void", void)
    r.add_post("/api/admin", admin)
    r.add_post("/api/admin/user", admin_user)
    r.add_post("/api/admin/report", admin_report)
    r.add_post("/api/admin/new_revision", admin_new_revision)
    r.add_get("/", index)
    r.add_static("/", config.web_dir, show_index=False)
    return app


@web.middleware
async def _no_cache(request, handler):
    # Telegram держит старую страницу в кэше; без этого обновления не доходят до телефонов.
    response = await handler(request)
    response.headers["Cache-Control"] = "no-cache"
    return response


@web.middleware
async def _auth(request: web.Request, handler):
    if not request.path.startswith("/api/") or request.path == "/api/health":
        return await handler(request)
    app = request.app
    try:
        tg_user = check_init_data(request.headers.get("X-Tg-Init-Data", ""), app["config"].bot_token)
    except AuthError as exc:
        return web.json_response({"error": "auth", "detail": str(exc)}, status=401)

    user, is_new = db.upsert_user(
        app["conn"], tg_user["id"], _name(tg_user), tg_user.get("username"), app["config"].admin_ids
    )
    if is_new and user["status"] == "pending":
        asyncio.ensure_future(_safe(app["notifier"].access_request(user)))
    request["user"] = user

    if request.path != "/api/me" and user["status"] != "active":
        return err(user["status"], 403)   # pending или blocked
    if request.path.startswith("/api/admin") and user["role"] != "admin":
        return err("not_admin", 403)
    return await handler(request)


async def _safe(coro):
    try:
        await coro
    except Exception:  # сообщение в Telegram не должно ронять запрос сотрудника
        log.exception("не удалось отправить сообщение в Telegram")


async def _json(request: web.Request) -> dict:
    try:
        body = await request.json()
    except Exception:
        return {}
    return body if isinstance(body, dict) else {}


def _int(value, low: int, high: int) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if low <= number <= high else None


def _profile(conn, user: dict) -> dict:
    return {
        "user": {"id": user["tg_id"], "name": user["name"], "role": user["role"], "status": user["status"]},
        "totals": db.totals(conn, user["tg_id"]),
    }


# ── страница ───────────────────────────────────────────────────────────────

async def index(request: web.Request) -> web.FileResponse:
    return web.FileResponse(request.app["config"].web_dir / "index.html")


async def health(request: web.Request) -> web.Response:
    return web.json_response({"ok": True})


# ── сотрудник ──────────────────────────────────────────────────────────────

async def me(request: web.Request) -> web.Response:
    conn, user = request.app["conn"], request["user"]
    out = _profile(conn, user)
    out["revision"] = {k: db.current_revision(conn)[k] for k in ("id", "title")}
    out["log"] = db.recent(conn, user["tg_id"]) if user["status"] == "active" else []
    return web.json_response(out)


async def scan(request: web.Request) -> web.Response:
    app, user = request.app, request["user"]
    hits = app["hits"][user["tg_id"]]
    now = time.monotonic()
    while hits and now - hits[0] > 60:
        hits.popleft()
    if len(hits) >= SCANS_PER_MINUTE:
        return err("too_fast", 429)
    hits.append(now)

    image = (await _json(request)).get("image")
    if not isinstance(image, str) or not image or len(image) > MAX_IMAGE_BYTES * 4 // 3:
        return err("bad_image")
    try:
        base64.b64decode(image, validate=True)
    except (binascii.Error, ValueError):
        return err("bad_image")

    started = time.monotonic()
    try:
        async with app["reads"]:
            price, unsure = await app["reader"].read(image)
    except ReaderError as exc:
        log.warning("Claude не ответил (%s): %s", exc.code, exc)
        return err("reader_" + exc.code, 502)
    sec = round(time.monotonic() - started, 1)

    if not price:
        return web.json_response({"result": "none", "sec": sec})
    if unsure:  # не записываем, пока сотрудник не подтвердит цену
        return web.json_response({"result": "unsure", "price": price, "sec": sec})
    entry = db.add_entry(app["conn"], user["tg_id"], price, sec)
    return web.json_response({"result": "ok", "price": price, "sec": sec, "entry": entry,
                              "totals": db.totals(app["conn"], user["tg_id"])})


async def add(request: web.Request) -> web.Response:
    """Сотрудник подтвердил цену, в которой Claude сомневался."""
    conn, user, body = request.app["conn"], request["user"], await _json(request)
    price = _int(body.get("price"), 1, MAX_AMOUNT)
    if price is None:
        return err("bad_amount")
    sec = body.get("sec")
    entry = db.add_entry(conn, user["tg_id"], price, sec if isinstance(sec, (int, float)) and 0 < sec < 120 else None)
    return web.json_response({"entry": entry, "totals": db.totals(conn, user["tg_id"])})


async def minus(request: web.Request) -> web.Response:
    conn, user, body = request.app["conn"], request["user"], await _json(request)
    amount = _int(body.get("amount"), 1, MAX_AMOUNT)
    if amount is None:
        return err("bad_amount")
    entry = db.add_entry(conn, user["tg_id"], -amount)
    return web.json_response({"entry": entry, "totals": db.totals(conn, user["tg_id"])})


async def void(request: web.Request) -> web.Response:
    conn, user, body = request.app["conn"], request["user"], await _json(request)
    entry_id = _int(body.get("id"), 1, 2**62)
    if entry_id is None or not db.void_entry(conn, entry_id, user):
        return err("not_found", 404)
    return web.json_response({"id": entry_id, "totals": db.totals(conn, user["tg_id"])})


# ── админ ──────────────────────────────────────────────────────────────────

async def admin(request: web.Request) -> web.Response:
    return web.json_response(db.admin_summary(request.app["conn"]))


async def admin_user(request: web.Request) -> web.Response:
    conn, me_, body = request.app["conn"], request["user"], await _json(request)
    target = db.get_user(conn, _int(body.get("id"), 1, 2**62) or 0)
    status, role = body.get("status"), body.get("role")
    if not target or status not in (None, "active", "blocked") or role not in (None, "admin", "staff"):
        return err("bad_request")
    if target["tg_id"] == me_["tg_id"]:
        return err("self")  # админ не может случайно заблокировать или разжаловать сам себя
    was_pending = target["status"] == "pending"
    db.set_user(conn, target["tg_id"], status=status, role=role)
    if was_pending and status:
        asyncio.ensure_future(_safe(request.app["notifier"].access_decided(target, status == "active")))
    return web.json_response(db.admin_summary(conn))


async def admin_report(request: web.Request) -> web.Response:
    data, filename = report.build_xlsx(request.app["conn"])
    try:
        await request.app["notifier"].send_report(request["user"]["tg_id"], data, filename)
    except Exception:
        log.exception("не удалось отправить отчёт")
        return err("send_failed", 502)
    return web.json_response({"sent": True})


async def admin_new_revision(request: web.Request) -> web.Response:
    conn, body = request.app["conn"], await _json(request)
    title = body.get("title")
    db.new_revision(conn, title if isinstance(title, str) else None)
    return web.json_response(db.admin_summary(conn))
