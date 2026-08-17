"""FastAPI-приложение магазина."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routers import (
    admin, auth, cart, catalog, config, favorites, orders, photos, uploads,
)
from app.config import get_settings
from app.db.base import engine

app = FastAPI(title="Stambul Shop", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(config.router)
app.include_router(catalog.router)
app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(favorites.router)
app.include_router(photos.router)
app.include_router(uploads.router)
app.include_router(admin.router)


@app.get("/health")
async def health():
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"db": "ok"}
