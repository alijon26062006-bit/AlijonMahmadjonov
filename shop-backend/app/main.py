import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import admin, auth, catalog

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="Shop API", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_origin_list, allow_credentials=True,
                       allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Content-Type"])
    app.include_router(auth.router)
    app.include_router(catalog.router)
    app.include_router(admin.router)

    @app.get("/api/health")
    def health():
        return {"ok": True}

    return app


app = create_app()
