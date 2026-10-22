"""API барои барномасозон: боти ё сайти дигар аз мо худкор мехарад.

Дар дохили худи бот кор мекунад (як база, як ҳисоб, як иҷрои фармоиш).

    GET  /api/docs                 ҳуҷҷатҳо (бо забони русӣ)
    GET  /api/v1/ping              санҷиши зинда будан (бе калид)
    GET  /api/v1/balance           баланс
    GET  /api/v1/products          молҳо бо нархи ҳамин харидор
    POST /api/v1/check             санҷиши ID / username пеш аз харид
    POST /api/v1/orders            харид (Idempotency-Key — бехатар такрор)
    GET  /api/v1/orders            таърихи фармоишҳо
    GET  /api/v1/orders/{id}       як фармоиш

Калид: сарлавҳаи ``X-API-Key`` ё ``Authorization: Bearer``. Калидро харидор
худаш дар бот месозад (🔌 API). Дар база танҳо хеши калид нигоҳ дошта мешавад.

Ҳамаи матнҳои ҷавоб ба забони русӣ — барои барномасозон.
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import time
from pathlib import Path
from typing import Any

from aiohttp import web

from . import catalog, guard
from .config import Config
from .db import DuplicateRequest, NotEnoughMoney, Database, price_of
from .fulfillment import deliver_in_background, pick_supplier

log = logging.getLogger(__name__)

API_ON_KEY = "api_enabled"          # тугмаи админ: API фаъол/хомӯш
KEY_PREFIX = "ak_live_"
CURRENCY = "TJS"
MAX_BODY = 32 * 1024
DOCS_FILE = Path(__file__).with_name("api_docs.html")

STATUS = {"new": "processing", "sent": "processing", "done": "completed", "rejected": "failed"}

#: Суроғаи оммавии API — пас аз оғози бот муайян мешавад (барои тугмаи бот).
PUBLIC_URL = ""


# ── калидҳо ───────────────────────────────────────────────────────────
def new_key() -> str:
    return KEY_PREFIX + secrets.token_urlsafe(30)


def key_hash(plain: str) -> str:
    return hashlib.sha256(plain.strip().encode()).hexdigest()


def key_hint(plain: str) -> str:
    return f"{plain[:12]}…{plain[-4:]}"


def issue_key(db: Database, user_id: int) -> str:
    """Калиди нав месозад (кӯҳна бекор мешавад) ва онро ЯК бор бармегардонад."""
    plain = new_key()
    db.create_api_key(user_id, key_hash(plain), key_hint(plain))
    return plain


def api_open(db: Database, cfg: Config) -> bool:
    return cfg.api_enabled and db.setting(API_ON_KEY, "1") == "1"


def docs_url(cfg: Config) -> str:
    base = cfg.api_public_url or PUBLIC_URL
    return f"{base}/api/docs" if base else ""


async def resolve_public_url(cfg: Config) -> str:
    """http://IP:порт — аз танзимот, вагарна IP-и оммавии сервер."""
    global PUBLIC_URL
    if cfg.api_public_url:
        PUBLIC_URL = cfg.api_public_url
        return PUBLIC_URL
    ip = ""
    try:
        import aiohttp

        timeout = aiohttp.ClientTimeout(total=6)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get("https://api.ipify.org") as resp:
                text = (await resp.text()).strip()
                if resp.status == 200 and text.count(".") == 3:
                    ip = text
    except Exception as exc:
        log.info("IP-и оммавӣ муайян нашуд: %s", exc)
    if not ip:
        label = guard.host_label()
        ip = label[label.find("(") + 1:label.find(")")] if "(" in label else ""
    PUBLIC_URL = f"http://{ip}:{cfg.api_port}" if ip else ""
    return PUBLIC_URL


# ── маҳдудият ─────────────────────────────────────────────────────────
class Limiter:
    """Дар як дақиқа на зиёда аз N дархост барои як калид."""

    def __init__(self, per_minute: int) -> None:
        self.per_minute = per_minute
        self._hits: dict[int, list[float]] = {}

    def allow(self, who: int, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        hits = [t for t in self._hits.get(who, ()) if now - t < 60]
        if len(hits) >= self.per_minute:
            self._hits[who] = hits
            return False
        hits.append(now)
        self._hits[who] = hits
        return True


# ── ёрирасонҳо ────────────────────────────────────────────────────────
class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.status, self.code, self.message, self.extra = status, code, message, extra


def money(diram: int) -> str:
    return f"{diram // 100}.{diram % 100:02d}"


def _json(data: dict, status: int = 200) -> web.Response:
    return web.json_response(data, status=status, dumps=lambda o: json.dumps(o, ensure_ascii=False))


def _needs_server(row) -> bool:
    group = row["group_code"] if "group_code" in row.keys() else ""
    return group in catalog.SERVER_GROUPS


def product_json(row, partner: bool, groups: dict[str, str]) -> dict:
    info = catalog.CATEGORY_INFO.get(row["category"])
    if info is not None and info.target == "username":
        fields = [{"key": "username", "label": "Telegram @username", "required": True}]
    else:
        fields = [{"key": "player_id", "label": "ID игрока", "required": True}]
        if _needs_server(row):
            fields.append({"key": "server", "label": "Номер сервера (зоны)", "required": True})
    return {
        "id": row["code"],
        "title": row["title"],
        "category": row["category"],
        "category_title": info.title if info else row["category"],
        "group": groups.get(row["group_code"] or "", ""),
        "price": money(price_of(row, partner)),
        "currency": CURRENCY,
        "fields": fields,
    }


def order_json(row) -> dict:
    target, _, server = (row["target"] or "").partition(" (")
    status = STATUS.get(row["status"], "processing")
    data = {
        "id": row["id"],
        "status": status,
        "product": row["product_code"],
        "title": row["title"],
        "target": target.strip(),
        "server": server.rstrip(")") or None,
        "nickname": row["nickname"],
        "price": money(row["price"]),
        "currency": CURRENCY,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "error": None,
    }
    if status == "failed":
        data["error"] = "Заказ не выполнен, деньги возвращены на баланс"
        data["reason"] = row["note"] or None
    return data


async def _body(request: web.Request) -> tuple[dict, bytes]:
    raw = await request.read()
    if not raw:
        return {}, raw
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise ApiError(400, "invalid_json", "Тело запроса — не JSON") from None
    if not isinstance(data, dict):
        raise ApiError(400, "invalid_json", "Ожидается JSON-объект {...}")
    return data, raw


def _target_for(row, body: dict) -> tuple[str, str]:
    """(ID/username, сервер) из запроса — с той же проверкой, что и в боте."""
    from .handlers.common import clean_player_id, clean_player_server, clean_username

    info = catalog.CATEGORY_INFO.get(row["category"])
    if info is not None and info.target == "username":
        raw = str(body.get("username") or body.get("player_id") or "").strip()
        if not raw:
            raise ApiError(400, "missing_field", "Не указан username", field="username")
        clean = clean_username(raw)
        if clean is None:
            raise ApiError(400, "invalid_field", "Неверный Telegram username", field="username")
        return clean, ""

    raw = str(body.get("player_id") or "").strip()
    if not raw:
        raise ApiError(400, "missing_field", "Не указан player_id", field="player_id")
    if _needs_server(row):
        server = str(body.get("server") or "").strip()
        if not server:
            raise ApiError(400, "missing_field", "Для этой игры нужен server", field="server")
        pair = clean_player_server(f"{raw} {server}")
        if pair is None:
            raise ApiError(400, "invalid_field", "Неверный player_id или server", field="player_id")
        return pair
    clean = clean_player_id(raw)
    if clean is None:
        raise ApiError(400, "invalid_field", "Неверный player_id (только цифры, 6–12 знаков)",
                       field="player_id")
    return clean, ""


def _product(db: Database, body: dict):
    code = str(body.get("product") or "").strip()
    if not code:
        raise ApiError(400, "missing_field", "Не указан product", field="product")
    row = db.product(code)
    if row is None or not row["active"]:
        raise ApiError(404, "product_not_found", "Товар не найден или сейчас недоступен")
    return row


# ── барнома ───────────────────────────────────────────────────────────
def build_app(db: Database, cfg: Config, supplier, bot) -> web.Application:
    requests_limit, orders_limit = Limiter(120), Limiter(30)

    @web.middleware
    async def errors(request: web.Request, handler):
        try:
            return await handler(request)
        except ApiError as exc:
            return _json({"ok": False, "code": exc.code, "error": exc.message, **exc.extra},
                         exc.status)
        except web.HTTPException as exc:
            if exc.status == 404:
                return _json({"ok": False, "code": "not_found", "error": "Нет такого адреса"}, 404)
            if exc.status == 413:
                return _json({"ok": False, "code": "too_large", "error": "Слишком большой запрос"}, 413)
            raise
        except Exception:
            log.exception("API: ошибка обработки %s", request.path)
            return _json({"ok": False, "code": "server_error",
                          "error": "Внутренняя ошибка, повторите позже"}, 500)

    def auth(request: web.Request):
        if not api_open(db, cfg):
            raise ApiError(503, "api_disabled", "API временно выключено владельцем магазина")
        plain = request.headers.get("X-API-Key", "")
        if not plain:
            bearer = request.headers.get("Authorization", "")
            plain = bearer[7:] if bearer.lower().startswith("bearer ") else ""
        plain = plain.strip()
        if not plain.startswith(KEY_PREFIX):
            raise ApiError(401, "unauthorized", "Нужен ключ API в заголовке X-API-Key")
        key = db.api_key_by_hash(key_hash(plain))
        if key is None:
            raise ApiError(401, "unauthorized", "Ключ API неверный или отозван")
        user = db.user(key["user_id"])
        if user is None or user.is_blocked:
            raise ApiError(403, "account_blocked", "Аккаунт заблокирован")
        if not requests_limit.allow(key["id"]):
            raise ApiError(429, "rate_limited", "Слишком много запросов, подождите минуту")
        return key, user

    async def ping(request: web.Request) -> web.Response:
        return _json({"ok": True, "api": "v1", "enabled": api_open(db, cfg)})

    async def balance(request: web.Request) -> web.Response:
        _, user = auth(request)
        return _json({"ok": True, "balance": money(user.balance), "currency": CURRENCY})

    async def products(request: web.Request) -> web.Response:
        _, user = auth(request)
        partner = db.is_partner(user.id)
        only = request.query.get("category", "").strip()
        groups: dict[str, str] = {}
        items = []
        for category in catalog.CATEGORIES:
            if only and category != only:
                continue
            for group in db.groups(category, only_active=False):
                groups[group["code"]] = group["title"]
            items += [product_json(r, partner, groups) for r in db.products(category)]
        return _json({"ok": True, "items": items, "count": len(items)})

    async def check(request: web.Request) -> web.Response:
        _, user = auth(request)
        body, _ = await _body(request)
        row = _product(db, body)
        target, server = _target_for(row, body)
        kind, sku = row["kind"] or "game", row["sku"] or ""
        if pick_supplier(cfg, supplier, kind, sku) is None:
            return _json({"ok": True, "supported": False, "valid": None, "nickname": None,
                          "message": "Для этого товара проверка недоступна"})
        result = await supplier.check(kind=kind, sku=sku, target=target,
                                      amount=row["amount"], server=server)
        if result.ok and result.nickname:
            return _json({"ok": True, "supported": True, "valid": True,
                          "nickname": result.nickname})
        if result.ok:
            return _json({"ok": True, "supported": False, "valid": None, "nickname": None,
                          "message": "Поставщик не проверяет этот аккаунт"})
        return _json({"ok": True, "supported": True, "valid": False, "nickname": None,
                      "message": "Аккаунт не найден или ID неверный"})

    async def create_order(request: web.Request) -> web.Response:
        key, user = auth(request)
        if not orders_limit.allow(key["id"]):
            raise ApiError(429, "rate_limited", "Не больше 30 заказов в минуту")
        body, raw = await _body(request)
        row = _product(db, body)
        target, server = _target_for(row, body)
        price = price_of(row, db.is_partner(user.id))

        idem_key = request.headers.get("Idempotency-Key", "").strip()[:100]
        idem = (idem_key, hashlib.sha256(raw).hexdigest()) if idem_key else None
        try:
            order_id = db.create_order(
                user_id=user.id, product_code=row["code"], category=row["category"],
                title=row["title"], price=price,
                target=target + (f" ({server})" if server else ""),
                nickname=None, sku=row["sku"] or "", kind=row["kind"] or "game",
                source="api", api_key_id=key["id"], idem=idem,
            )
        except DuplicateRequest as dup:
            if not dup.same_body:
                raise ApiError(409, "idempotency_key_reused",
                               "Этот Idempotency-Key уже использован для другого заказа") from None
            existing = db.order(dup.order_id)
            return _json({"ok": True, "duplicate": True, "order": order_json(existing)})
        except NotEnoughMoney:
            fresh = db.user(user.id)
            raise ApiError(
                402, "insufficient_balance",
                f"Недостаточно средств: нужно {money(price)} {CURRENCY}, "
                f"на балансе {money(fresh.balance if fresh else 0)} {CURRENCY}",
            ) from None

        deliver_in_background(bot, db, cfg, supplier, order_id)
        fresh = db.user(user.id)
        return _json({"ok": True, "order": order_json(db.order(order_id)),
                      "balance": money(fresh.balance if fresh else 0)}, 201)

    async def list_orders(request: web.Request) -> web.Response:
        _, user = auth(request)
        try:
            limit = max(1, min(int(request.query.get("limit", 20)), 100))
            offset = max(0, int(request.query.get("offset", 0)))
        except ValueError:
            raise ApiError(400, "invalid_field", "limit и offset — целые числа") from None
        rows = db.api_orders(user.id, limit, offset)
        return _json({"ok": True, "items": [order_json(r) for r in rows],
                      "limit": limit, "offset": offset})

    async def get_order(request: web.Request) -> web.Response:
        _, user = auth(request)
        try:
            order_id = int(request.match_info["order_id"])
        except ValueError:
            raise ApiError(404, "not_found", "Заказ не найден") from None
        row = db.order(order_id)
        if row is None or row["user_id"] != user.id:
            raise ApiError(404, "not_found", "Заказ не найден")
        return _json({"ok": True, "order": order_json(row)})

    async def docs(request: web.Request) -> web.Response:
        origin = cfg.api_public_url or PUBLIC_URL or f"{request.scheme}://{request.host}"
        try:
            page = DOCS_FILE.read_text(encoding="utf-8")
        except OSError:
            page = "<h1>Документация недоступна</h1>"
        page = page.replace("{{BASE}}", f"{origin}/api/v1").replace("{{ORIGIN}}", origin)
        return web.Response(text=page, content_type="text/html", charset="utf-8")

    async def to_docs(request: web.Request) -> web.Response:
        raise web.HTTPFound("/api/docs")

    app = web.Application(middlewares=[errors], client_max_size=MAX_BODY)
    app.router.add_get("/", to_docs)
    app.router.add_get("/api", to_docs)
    app.router.add_get("/api/", to_docs)
    app.router.add_get("/api/docs", docs)
    app.router.add_get("/api/v1/ping", ping)
    app.router.add_get("/api/v1/balance", balance)
    app.router.add_get("/api/v1/products", products)
    app.router.add_post("/api/v1/check", check)
    app.router.add_post("/api/v1/orders", create_order)
    app.router.add_get("/api/v1/orders", list_orders)
    app.router.add_get(r"/api/v1/orders/{order_id}", get_order)
    return app


async def start(db: Database, cfg: Config, supplier, bot) -> web.AppRunner | None:
    """API-ро дар паси бот оғоз мекунад. Агар порт банд бошад — бот бе API кор мекунад."""
    if not cfg.api_enabled:
        log.info("API барои барномасозон хомӯш (SHOP_API_ENABLED=0).")
        return None
    runner = web.AppRunner(build_app(db, cfg, supplier, bot), access_log=None)
    await runner.setup()
    try:
        await web.TCPSite(runner, cfg.api_host, cfg.api_port).start()
    except OSError as exc:
        log.error("API оғоз нашуд (порт %s): %s", cfg.api_port, exc)
        await runner.cleanup()
        return None
    url = await resolve_public_url(cfg)
    log.info("API барои барномасозон: %s/api/docs", url or f"http://<IP>:{cfg.api_port}")
    return runner
