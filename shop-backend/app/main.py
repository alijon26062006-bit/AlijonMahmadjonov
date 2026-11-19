import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from . import db as dbmod
from .orders_service import sync_pending
from .routers import admin, auth, catalog, orders

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


log = logging.getLogger("worker")


def _sync_once() -> None:
    gen = dbmod.get_db()
    db = next(gen)
    try:
        sync_pending(db)
    finally:
        gen.close()


async def _order_worker(interval: int) -> None:
    """Checks unfinished orders at the supplier every `interval` seconds."""
    while True:
        try:
            await asyncio.to_thread(_sync_once)
        except Exception:
            log.exception("order sync failed")
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    task = asyncio.create_task(_order_worker(s.order_sync_interval_seconds)) if s.order_sync_enabled else None
    yield
    if task:
        task.cancel()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="Shop API", version="0.2.0", docs_url="/api/docs", openapi_url="/api/openapi.json",
                  lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_origin_list, allow_credentials=True,
                       allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Content-Type"])
    app.include_router(auth.router)
    app.include_router(catalog.router)
    app.include_router(orders.router)
    app.include_router(admin.router)

    @app.get("/api/health")
    def health():
        return {"ok": True}

    return app


app = create_app()
