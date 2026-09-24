"""Сборка приложения: `python -m donatix serve` или `uvicorn donatix.app:create_app --factory`."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from . import accounts, admin, api, db, web
from .config import ROOT, Config
from .deps import Forbidden, LoginRequired, render
from .ratelimit import RateLimiter
from .suppliers import Supplier, make_supplier
from .worker import Worker


def create_app(config: Config | None = None, supplier: Supplier | None = None) -> FastAPI:
    config = config or Config.from_env()
    supplier = supplier or make_supplier(config)
    db.init(config.db_path)
    conn = db.connect(config.db_path)
    try:
        accounts.ensure_admin(conn, config)
    finally:
        conn.close()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        bg = bot = None
        if config.run_worker:
            bg = Worker(config, supplier)
            bg.start()
            if config.alert_telegram_token and config.alert_telegram_chat_id:
                from .tgbot import AdminBot
                bot = AdminBot(config)
                bot.start()
        yield
        if bot:
            bot.stop()
        if bg:
            bg.stop()

    app = FastAPI(
        title=f"{config.site_name} API",
        version="1",
        lifespan=lifespan,
        docs_url="/api/swagger",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.config = config
    app.state.supplier = supplier
    app.state.limiter = RateLimiter()

    app.add_middleware(
        SessionMiddleware,
        secret_key=config.secret_key,
        session_cookie="dx_session",
        max_age=14 * 24 * 3600,
        same_site="lax",
        https_only=config.cookie_secure,
    )
    app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")
    # Картинки каталога, скачанные с поставщика к себе (админка → Загрузка каталога)
    from . import catalog_job
    catalog_job.load_image_index(config)
    app.mount("/media", StaticFiles(directory=str(catalog_job.images_dir(config))), name="media")
    app.include_router(api.router)
    from . import compat
    app.include_router(compat.router)
    app.include_router(web.router)
    app.include_router(admin.router)

    @app.exception_handler(api.ApiError)
    async def _api_error(request: Request, exc: api.ApiError):
        return api.api_error_response(exc)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(x) for x in first.get("loc", []) if x != "body")
        message = f"Неверный запрос: {where} — {first.get('msg', '')}".strip(" —")
        if request.url.path.startswith("/api/"):
            return JSONResponse({"ok": False, "error": message, "code": "validation_error"}, status_code=400)
        return render(request, "error.html", {"message": message}, 400)

    @app.exception_handler(LoginRequired)
    async def _login(request: Request, exc: LoginRequired):
        return RedirectResponse("/login", status_code=303)

    @app.exception_handler(Forbidden)
    async def _forbidden(request: Request, exc: Forbidden):
        return render(request, "error.html", {"message": str(exc)}, 403)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        if request.url.path.startswith("/api/"):
            code = "not_found" if exc.status_code == 404 else "http_error"
            return JSONResponse({"ok": False, "error": str(exc.detail), "code": code}, status_code=exc.status_code)
        message = "Страница не найдена." if exc.status_code == 404 else str(exc.detail)
        return render(request, "error.html", {"message": message}, exc.status_code)

    return app
