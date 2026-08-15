"""FastAPI-приложение: uvicorn app.api.main:app"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routers import (
    admin, auth, categories, dicts, favorites, listings, photos, uploads,
)
from app.config import get_settings
from app.db.base import SessionMaker


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(get_settings().media_cache_dir).mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="Бозор API", lifespan=lifespan, docs_url="/api/docs",
              openapi_url="/api/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["*"], allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(categories.router)
app.include_router(dicts.router)
app.include_router(listings.router)
app.include_router(favorites.router)
app.include_router(photos.router)
app.include_router(uploads.router)
app.include_router(admin.router)


@app.get("/health")
async def health():
    try:
        async with SessionMaker() as session:
            await session.execute(text("SELECT 1"))
        db = "ok"
    except Exception:
        db = "fail"
    return {"db": db}
