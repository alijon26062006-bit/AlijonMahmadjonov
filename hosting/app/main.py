"""HTTP API панели и раздача фронтенда."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .catalog import Catalog, cents
from .config import BASE_DIR, Settings
from .db import Database
from .legal import render_legal
from .notify import Notifier
from .providers import ProviderError, build_providers
from .security import (SESSION_COOKIE, SESSION_TTL, RateLimiter, create_session, destroy_session, hash_password,
                       load_session, verify_password)
from .services import Hosting, ServiceError
from .validators import ValidationError

log = logging.getLogger("hosting")
STATIC = BASE_DIR / "static"
MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


# ── Модели запросов ───────────────────────────────────────
class RegisterIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=200)
    name: str = Field(default="", max_length=100)


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=200)


class OrderIn(BaseModel):
    plan: str
    location: str
    image: str
    name: str = Field(max_length=63)
    root_password: str | None = Field(default=None, max_length=128)


class PowerIn(BaseModel):
    action: Literal["start", "stop", "force_stop", "reboot", "reset"]


class PasswordIn(BaseModel):
    mode: Literal["custom", "generate"]
    password: str | None = Field(default=None, max_length=128)
    account_password: str = Field(max_length=200)


class RebuildIn(BaseModel):
    image: str
    account_password: str = Field(max_length=200)


class ConfirmIn(BaseModel):
    account_password: str = Field(max_length=200)


class DomainIn(BaseModel):
    domain: str = Field(max_length=253)
    purchase: bool = False


class RecordIn(BaseModel):
    type: str = Field(max_length=10)
    name: str = Field(default="@", max_length=253)
    value: str = Field(max_length=2048)
    ttl: int = 3600


class FlagIn(BaseModel):
    value: bool


class AmountIn(BaseModel):
    amount: float = Field(gt=0, le=10000)
    note: str = Field(default="", max_length=200)


class ProfileIn(BaseModel):
    name: str = Field(default="", max_length=120)
    company: str = Field(default="", max_length=120)
    phone: str = Field(default="", max_length=40)
    country: str = Field(default="", max_length=2)
    city: str = Field(default="", max_length=120)
    address: str = Field(default="", max_length=120)
    zipcode: str = Field(default="", max_length=20)


class TopupRequestIn(BaseModel):
    amount: float = Field(gt=0, le=10000)
    method: str = Field(max_length=80)
    reference: str = Field(default="", max_length=200)
    receipt_data: str | None = Field(default=None, max_length=7_200_000)  # base64, до ~5 МБ
    receipt_name: str = Field(default="", max_length=200)


class DecideIn(BaseModel):
    approve: bool
    note: str = Field(default="", max_length=200)


class NameserversIn(BaseModel):
    nameservers: list[str] | None = Field(default=None, max_length=13)


class CatalogIn(BaseModel):
    plans: list[dict] = Field(max_length=50)
    tlds: list[dict] = Field(max_length=200)


def create_app(settings: Settings | None = None, db: Database | None = None, hosting: Hosting | None = None,
               start_billing: bool = True) -> FastAPI:
    settings = settings or Settings.from_env()
    for problem in settings.validate():
        log.warning("Настройки: %s", problem)
    db = db or Database(settings.database_path)
    catalog = Catalog.load()
    hosting = hosting or Hosting(settings, db, catalog, build_providers(settings), notifier=Notifier(settings))
    limiter = RateLimiter()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task = None
        if start_billing:
            async def loop():
                while True:
                    try:
                        stats = await run_in_threadpool(hosting.run_billing)
                        if any(stats.values()):
                            log.info("billing: %s", stats)
                    except Exception:  # noqa: BLE001
                        log.exception("billing failed")
                    await asyncio.sleep(settings.billing_interval_sec)
            task = asyncio.create_task(loop())
        yield
        if task:
            task.cancel()

    app = FastAPI(title=settings.brand_name, lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings, app.state.db, app.state.hosting, app.state.limiter = settings, db, hosting, limiter

    # ── Ошибки → понятный JSON ──
    @app.exception_handler(ServiceError)
    async def _service_error(_: Request, e: ServiceError):
        return JSONResponse({"error": e.message, "field": e.field}, status_code=e.status)

    @app.exception_handler(ProviderError)
    async def _provider_error(_: Request, e: ProviderError):
        return JSONResponse({"error": e.message, "field": None}, status_code=e.status)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, e: RequestValidationError):
        first = e.errors()[0] if e.errors() else {}
        field = str(first.get("loc", ["", ""])[-1])
        return JSONResponse({"error": "Проверьте поле: " + field, "field": field}, status_code=422)

    # ── Заголовки безопасности и защита от CSRF ──
    @app.middleware("http")
    async def guard(request: Request, call_next):
        path = request.url.path
        if (request.method in MUTATING and path.startswith("/api/") and path != "/api/agent/report"
                and request.headers.get("x-requested-with") != "fetch"):
            return JSONResponse({"error": "Запрос отклонён (CSRF)"}, status_code=403)
        resp: Response = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; "
            "img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        if path.startswith("/api/"):
            resp.headers.setdefault("Cache-Control", "no-store")
        return resp

    # ── Зависимости ──
    def ip_of(request: Request) -> str:
        return request.client.host if request.client else ""

    def current_user(request: Request) -> dict:
        user = load_session(db, request.cookies.get(SESSION_COOKIE))
        if not user:
            raise ServiceError("Войдите в аккаунт", 401)
        if request.method in MUTATING and request.headers.get("x-csrf-token") != user["csrf"]:
            raise ServiceError("Сессия устарела, обновите страницу", 403)
        return user

    def admin_user(user: dict = Depends(current_user)) -> dict:
        if not user["is_admin"]:
            raise ServiceError("Нужны права администратора", 403)
        return user

    def limit(key: str, n: int, window: int) -> None:
        if not limiter.allow(key, n, window):
            raise ServiceError("Слишком много попыток, подождите немного", 429)

    def confirm_password(user: dict, password: str, request: Request) -> None:
        limit(f"confirm:{user['id']}", 8, 600)
        if not verify_password(password, user["pw_hash"]):
            raise ServiceError("Неверный пароль от личного кабинета", 403, field="account_password")

    def user_view(u: dict) -> dict:
        return {"id": u["id"], "email": u["email"], "name": u["name"], "is_admin": bool(u["is_admin"]),
                "verified": bool(u.get("verified")), "balance": u["balance_cents"] / 100, "csrf": u.get("csrf"),
                "profile": {f: u.get(f) or "" for f in Hosting.PROFILE_FIELDS}}

    def set_cookie(resp: Response, token: str) -> None:
        resp.set_cookie(SESSION_COOKIE, token, max_age=SESSION_TTL, httponly=True, samesite="lax",
                        secure=settings.cookie_secure, path="/")

    # ═══════════ Публичное ═══════════
    @app.get("/api/config")
    def config():
        return {"brand": settings.brand_name, "currency": settings.currency, "demo_payments": settings.demo_payments,
                "vps_provider": settings.vps_provider, "dns_provider": settings.dns_provider,
                "registrar": settings.registrar, "nameservers": settings.nameservers,
                "payment_methods": settings.payment_methods, "payment_instructions": settings.payment_instructions,
                "support": {"telegram": settings.support_telegram, "email": settings.support_email, "phone": settings.support_phone},
                "company": settings.company_name, "new_user_server_limit": settings.new_user_server_limit}

    @app.get("/api/catalog")
    def get_catalog():
        return hosting.catalog.public()

    @app.get("/api/domains/check")
    def check(name: str, request: Request):
        limit(f"check:{ip_of(request)}", 30, 60)
        return {"results": hosting.check_domains(name)}

    # ═══════════ Аккаунт ═══════════
    @app.post("/api/auth/register")
    def register(body: RegisterIn, request: Request, response: Response):
        limit(f"register:{ip_of(request)}", 5, 3600)
        try:
            email = body.email.strip().lower()
            if "@" not in email or "." not in email.split("@")[-1] or len(email) < 5:
                raise ValidationError("email", "Некорректный email")
        except ValidationError as e:
            raise ServiceError(e.message, field="email") from None
        if len(body.password) < 10:
            raise ServiceError("Пароль от кабинета — не короче 10 символов", field="password")
        if db.one("SELECT 1 FROM users WHERE email = ?", (email,)):
            raise ServiceError("Такой email уже зарегистрирован", 409, field="email")
        is_admin = int(bool(settings.admin_email) and email == settings.admin_email)
        uid = db.run("INSERT INTO users(email, name, pw_hash, is_admin, created_at) VALUES (?,?,?,?,strftime('%s','now'))",
                     (email, body.name.strip()[:100], hash_password(body.password), is_admin))
        token, _ = create_session(db, uid, ip_of(request))
        set_cookie(response, token)
        db.audit(uid, "user.register", email, ip_of(request))
        hosting.notify.admin(f"👤 Новый клиент: {email}")
        hosting.notify.email(email, f"Добро пожаловать в {settings.brand_name}",
                             "Аккаунт создан. В личном кабинете можно заказать сервер, зарегистрировать домен и настроить DNS.")
        return {"ok": True}

    @app.post("/api/auth/login")
    def login(body: LoginIn, request: Request, response: Response):
        email = body.email.strip().lower()
        limit(f"login:{ip_of(request)}", 20, 600)
        limit(f"login:{email}", 8, 600)
        user = db.one("SELECT * FROM users WHERE email = ?", (email,))
        if not user or not verify_password(body.password, user["pw_hash"]):
            raise ServiceError("Неверный email или пароль", 401, field="password")
        token, _ = create_session(db, user["id"], ip_of(request))
        set_cookie(response, token)
        db.audit(user["id"], "user.login", "", ip_of(request))
        return {"ok": True}

    @app.post("/api/auth/logout")
    def logout(request: Request, response: Response):
        destroy_session(db, request.cookies.get(SESSION_COOKIE))
        response.delete_cookie(SESSION_COOKIE, path="/")
        return {"ok": True}

    @app.get("/api/me")
    def me(user: dict = Depends(current_user)):
        return user_view(user)

    @app.post("/api/profile")
    def profile(body: ProfileIn, request: Request, user: dict = Depends(current_user)):
        updated = hosting.update_profile(user, body.model_dump())
        db.audit(user["id"], "user.profile", "", ip_of(request))
        return user_view({**updated, "csrf": user["csrf"]})

    # ═══════════ Серверы ═══════════
    @app.get("/api/servers")
    def servers(user: dict = Depends(current_user)):
        return {"servers": hosting.list_servers(user)}

    @app.post("/api/servers")
    def order(body: OrderIn, request: Request, user: dict = Depends(current_user)):
        limit(f"order:{user['id']}", 10, 3600)
        row, generated = hosting.order_server(user, plan_id=body.plan, location=body.location, image=body.image,
                                              name=body.name, root_password=body.root_password or None, ip=ip_of(request))
        return {"server": hosting.server_view(row), "root_password": generated}

    @app.get("/api/servers/{sid}")
    def server(sid: int, user: dict = Depends(current_user)):
        return {"server": hosting.server_view(hosting.refresh(hosting.get_server(user, sid)))}

    @app.post("/api/servers/{sid}/power")
    def power(sid: int, body: PowerIn, request: Request, user: dict = Depends(current_user)):
        limit(f"power:{user['id']}", 30, 300)
        return {"server": hosting.power(user, hosting.get_server(user, sid), body.action, ip_of(request))}

    @app.post("/api/servers/{sid}/password")
    def password(sid: int, body: PasswordIn, request: Request, user: dict = Depends(current_user)):
        row = hosting.get_server(user, sid)
        confirm_password(user, body.account_password, request)
        limit(f"rootpw:{sid}", 5, 600)
        if body.mode == "custom" and not body.password:
            raise ServiceError("Введите новый пароль", field="password")
        return hosting.change_root_password(user, row, body.password if body.mode == "custom" else None, ip_of(request))

    @app.post("/api/servers/{sid}/rebuild")
    def rebuild(sid: int, body: RebuildIn, request: Request, user: dict = Depends(current_user)):
        row = hosting.get_server(user, sid)
        confirm_password(user, body.account_password, request)
        return {"root_password": hosting.rebuild(user, row, body.image, ip_of(request))}

    @app.post("/api/servers/{sid}/delete")
    def delete(sid: int, body: ConfirmIn, request: Request, user: dict = Depends(current_user)):
        row = hosting.get_server(user, sid)
        confirm_password(user, body.account_password, request)
        hosting.delete_server(user, row, ip_of(request))
        return {"ok": True}

    @app.get("/api/servers/{sid}/metrics")
    def metrics(sid: int, range: str = "1h", user: dict = Depends(current_user)):  # noqa: A002
        return hosting.metrics(hosting.get_server(user, sid), range)

    @app.post("/api/agent/report")
    async def agent_report(request: Request):
        auth = request.headers.get("authorization", "")
        try:
            payload = await request.json()
        except ValueError:
            raise ServiceError("Ожидался JSON") from None
        if not isinstance(payload, dict):
            raise ServiceError("Ожидался объект JSON")
        await run_in_threadpool(hosting.agent_report, auth.removeprefix("Bearer ").strip(), payload)
        return {"ok": True}

    # ═══════════ Домены ═══════════
    @app.get("/api/domains")
    def domains(user: dict = Depends(current_user)):
        return {"domains": hosting.list_domains(user)}

    @app.post("/api/domains")
    def add_domain(body: DomainIn, request: Request, user: dict = Depends(current_user)):
        limit(f"domain:{user['id']}", 20, 3600)
        return {"domain": hosting.add_domain(user, body.domain, body.purchase, ip_of(request))}

    @app.get("/api/domains/{did}")
    def domain(did: int, user: dict = Depends(current_user)):
        row = hosting.get_domain(user, did)
        return {"domain": hosting.domain_view(row), "records": hosting.records(row)}

    @app.post("/api/domains/{did}/records")
    def add_record(did: int, body: RecordIn, request: Request, user: dict = Depends(current_user)):
        limit(f"dns:{user['id']}", 120, 3600)
        row = hosting.get_domain(user, did)
        return {"record": hosting.add_record(user, row, body.type, body.name, body.value, body.ttl, ip_of(request))}

    @app.delete("/api/domains/{did}/records/{rid}")
    def delete_record(did: int, rid: int, request: Request, user: dict = Depends(current_user)):
        hosting.delete_record(user, hosting.get_domain(user, did), rid, ip_of(request))
        return {"ok": True}

    @app.post("/api/domains/{did}/nameservers")
    def nameservers(did: int, body: NameserversIn, request: Request, user: dict = Depends(current_user)):
        limit(f"ns:{user['id']}", 20, 3600)
        return {"domain": hosting.set_nameservers(user, hosting.get_domain(user, did), body.nameservers, ip_of(request))}

    @app.post("/api/domains/{did}/auto-renew")
    def auto_renew(did: int, body: FlagIn, user: dict = Depends(current_user)):
        hosting.set_auto_renew(hosting.get_domain(user, did), body.value)
        return {"ok": True}

    # ═══════════ Баланс ═══════════
    @app.get("/api/billing")
    def billing(user: dict = Depends(current_user)):
        tx = db.all("SELECT amount_cents, kind, description, created_at FROM transactions WHERE user_id = ? "
                    "ORDER BY id DESC LIMIT 50", (user["id"],))
        monthly = db.one("SELECT COALESCE(SUM(price_cents), 0) AS s FROM servers WHERE user_id = ? AND deleted_at IS NULL",
                         (user["id"],))["s"]
        reqs = db.all("SELECT id, amount_cents, method, reference, status, admin_note, created_at, pay_amount, pay_currency,"
                      " receipt != '' AS has_receipt FROM topup_requests"
                      " WHERE user_id = ? ORDER BY id DESC LIMIT 20", (user["id"],))
        return {"balance": user["balance_cents"] / 100, "monthly": monthly / 100,
                "transactions": [{**t, "amount": t["amount_cents"] / 100} for t in tx],
                "requests": [{**r, "amount": r["amount_cents"] / 100} for r in reqs],
                "demo_payments": settings.demo_payments, "payment_methods": [a["name"] for a in hosting.payment_accounts()],
                "payment_accounts": hosting.payment_accounts(), "payment_instructions": settings.payment_instructions,
                "pay": hosting.pay_info()}

    @app.post("/api/billing/requests")
    def topup_request(body: TopupRequestIn, request: Request, user: dict = Depends(current_user)):
        limit(f"topupreq:{user['id']}", 10, 3600)
        r = hosting.create_topup_request(user, body.amount, body.method, body.reference, ip_of(request),
                                         receipt={"data": body.receipt_data, "name": body.receipt_name} if body.receipt_data else None)
        return {"request": {**r, "amount": r["amount_cents"] / 100}}

    @app.post("/api/billing/topup")
    def topup(body: AmountIn, request: Request, user: dict = Depends(current_user)):
        if not settings.demo_payments:
            raise ServiceError("Пополнение через платёжную систему пока не подключено", 501)
        limit(f"topup:{user['id']}", 10, 3600)
        db.credit(user["id"], cents(min(body.amount, 500)), "topup", "Пополнение (демо)")
        db.audit(user["id"], "billing.topup_demo", str(body.amount), ip_of(request))
        return {"ok": True}

    # ═══════════ Админка ═══════════
    @app.get("/api/admin/overview")
    def admin_overview(_: dict = Depends(admin_user)):
        users = db.all(
            "SELECT u.id, u.email, u.name, u.balance_cents, u.is_admin, u.verified, u.created_at,"
            " (SELECT COUNT(*) FROM servers s WHERE s.user_id = u.id AND s.deleted_at IS NULL) AS servers,"
            " (SELECT COUNT(*) FROM domains d WHERE d.user_id = u.id) AS domains"
            " FROM users u ORDER BY u.id DESC LIMIT 200")
        totals = db.one("SELECT (SELECT COUNT(*) FROM users) AS users,"
                        " (SELECT COUNT(*) FROM topup_requests WHERE status = 'pending') AS pending_topups,"
                        " (SELECT COUNT(*) FROM servers WHERE deleted_at IS NULL) AS servers,"
                        " (SELECT COUNT(*) FROM domains) AS domains,"
                        " (SELECT COALESCE(SUM(price_cents),0) FROM servers WHERE deleted_at IS NULL) AS mrr")
        audit = db.all("SELECT a.action, a.target, a.ip, a.created_at, u.email FROM audit a LEFT JOIN users u ON u.id = a.user_id"
                       " ORDER BY a.id DESC LIMIT 50")
        return {"users": [{**u, "balance": u["balance_cents"] / 100} for u in users],
                "totals": {**totals, "mrr": totals["mrr"] / 100}, "audit": audit}

    @app.post("/api/admin/users/{uid}/credit")
    def admin_credit(uid: int, body: AmountIn, request: Request, admin: dict = Depends(admin_user)):
        if not db.one("SELECT 1 FROM users WHERE id = ?", (uid,)):
            raise ServiceError("Пользователь не найден", 404)
        db.credit(uid, cents(body.amount), "admin", body.note or "Пополнение администратором")
        db.audit(admin["id"], "admin.credit", f"{uid}:{body.amount}", ip_of(request))
        return {"ok": True}

    @app.post("/api/admin/users/{uid}/verify")
    def admin_verify(uid: int, body: FlagIn, request: Request, admin: dict = Depends(admin_user)):
        if not db.one("SELECT 1 FROM users WHERE id = ?", (uid,)):
            raise ServiceError("Пользователь не найден", 404)
        db.run("UPDATE users SET verified = ? WHERE id = ?", (int(body.value), uid))
        db.audit(admin["id"], "admin.verify", f"{uid}:{int(body.value)}", ip_of(request))
        return {"ok": True}

    @app.get("/api/admin/topups")
    def admin_topups(status: str = "pending", _: dict = Depends(admin_user)):
        rows = db.all("SELECT t.*, u.email FROM topup_requests t JOIN users u ON u.id = t.user_id"
                      " WHERE (? = 'all' OR t.status = ?) ORDER BY t.id DESC LIMIT 100", (status, status))
        return {"requests": [{**r, "amount": r["amount_cents"] / 100} for r in rows]}

    @app.post("/api/admin/topups/{rid}")
    def admin_decide(rid: int, body: DecideIn, request: Request, admin: dict = Depends(admin_user)):
        r = hosting.decide_topup(admin, rid, body.approve, body.note, ip_of(request))
        return {"request": {**r, "amount": r["amount_cents"] / 100}}

    @app.get("/api/admin/topups/{rid}/receipt")
    def admin_receipt(rid: int, _: dict = Depends(admin_user)):
        found = hosting.receipt_file(rid)
        if not found:
            raise ServiceError("Чек не найден", 404)
        path, mime = found
        resp = FileResponse(path, media_type=mime, content_disposition_type="inline")
        resp.headers["Cache-Control"] = "private, no-store"
        return resp

    @app.get("/api/admin/catalog")
    def admin_catalog(_: dict = Depends(admin_user)):
        return hosting.catalog.to_dict()

    @app.post("/api/admin/catalog")
    def admin_catalog_save(body: CatalogIn, request: Request, admin: dict = Depends(admin_user)):
        return hosting.update_catalog(admin, body.plans, body.tlds, ip_of(request))

    @app.get("/api/admin/settings")
    def admin_settings(_: dict = Depends(admin_user)):
        return hosting.site_settings()

    @app.post("/api/admin/settings")
    def admin_settings_save(body: dict, request: Request, admin: dict = Depends(admin_user)):
        limit(f"settings:{admin['id']}", 30, 3600)
        return hosting.update_site_settings(admin, body, ip_of(request))

    @app.get("/api/admin/readiness")
    def admin_readiness(_: dict = Depends(admin_user)):
        checks = hosting.readiness()
        return {"checks": checks, "ready": all(c["ok"] for c in checks if c["required"])}

    @app.get("/api/admin/provider")
    def admin_provider(_: dict = Depends(admin_user)):
        vps = hosting.p.vps
        active = db.all("SELECT plan, location, price_cents FROM servers WHERE deleted_at IS NULL")
        revenue = sum(r["price_cents"] for r in active) / 100
        registrar = {"name": hosting.p.registrar.name}
        if hasattr(hosting.p.registrar, "balance"):
            try:
                registrar.update(hosting.p.registrar.balance())
            except ProviderError as e:
                registrar["error"] = e.message
        if vps.name != "hetzner":
            return {"provider": vps.name, "server_types": [], "note": "Демо-режим: вставьте токен Hetzner в Настройках",
                    "costs": {"servers": len(active), "revenue": revenue, "hetzner_month": None}, "registrar": registrar}
        types = vps.server_types()
        prices = {}
        for st in types:
            for p in st.get("prices", []):
                # Цена без НДС: для клиентов вне ЕС Hetzner НДС не начисляет.
                prices.setdefault(st["name"], {})[p["location"]] = float(p["price_monthly"]["net"])
        plans = [{"plan": p["id"], "server_type": p["server_type"], "our_price": p["price_month"],
                  "hetzner_price": prices.get(p["server_type"], {}),
                  "exists": p["server_type"] in prices} for p in hosting.catalog.plans]
        # Во сколько вам обходятся серверы клиентов у Hetzner (баланса и счетов в их API нет).
        cost, unknown = 0.0, 0
        for r in active:
            plan = hosting.catalog.plan(r["plan"]) or {}
            price = prices.get(plan.get("server_type", ""), {}).get(r["location"])
            if price is None:
                unknown += 1
            else:
                cost += price
        return {"provider": "hetzner", "plans": plans,
                "costs": {"servers": len(active), "revenue": revenue, "hetzner_month": round(cost, 2), "unknown": unknown},
                "registrar": registrar,
                "server_types": [{"name": t["name"], "cores": t["cores"], "memory": t["memory"], "disk": t["disk"],
                                  "deprecated": bool(t.get("deprecation"))} for t in types]}

    # ═══════════ Страницы ═══════════
    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC / "home.html")

    @app.get("/legal/{doc}", include_in_schema=False)
    def legal(doc: str):
        page = render_legal(doc, settings)
        if page is None:
            raise ServiceError("Документ не найден", 404)
        return HTMLResponse(page)

    @app.get("/app", include_in_schema=False)
    def app_page():
        return FileResponse(STATIC / "app.html")


    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
