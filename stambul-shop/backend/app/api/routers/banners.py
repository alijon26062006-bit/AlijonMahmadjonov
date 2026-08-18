"""Баннеры на главной: свои фотографии, срок показа, порядок.

Баннер — не украшение, а место, откуда человек уходит в подборку. Поэтому
у него обязательна ссылка и необязателен текст: хорошая фотография
работает и без слов, а слова без фотографии — нет.

Срок показа задаётся днями и хранится датой окончания. Витрина сама
перестаёт показывать просроченное — снимать руками ничего не нужно.
"""
import uuid as uuid_mod
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from fastapi import Request, Response

from app.api.deps import Cache, Db
from app.api.routers.admin import Admin, _log, sign_photo
from app.db.models import Banner
from app.services.telegram_files import get_photo_bytes

public_router = APIRouter(prefix="/api", tags=["banners"])
router = APIRouter(prefix="/api/admin/banners", tags=["banners"])

MAX_BANNERS = 10
CACHE_HEADERS = {"Cache-Control": "public, max-age=86400"}


class PhotoIn(BaseModel):
    file_id: str
    thumb_file_id: str | None = None
    thumb_w: int | None = None
    file_unique_id: str
    sig: str


class BannerIn(BaseModel):
    photo: PhotoIn | None = None
    eyebrow: str | None = Field(default=None, max_length=60)
    title: str | None = Field(default=None, max_length=120)
    subtitle: str | None = Field(default=None, max_length=200)
    button_text: str | None = Field(default=None, max_length=40)
    link: str | None = Field(default=None, max_length=300)
    # на сколько дней показывать; 0 — без срока
    days: int | None = Field(default=None, ge=0, le=365)
    is_active: bool | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _out(b: Banner) -> dict:
    left = None
    if b.expires_at:
        left = max(0, (b.expires_at - _now()).days)
    return {
        "id": str(b.public_id),
        "photo": f"/api/banners/{b.public_id}/photo",
        "eyebrow": b.eyebrow,
        "title": b.title,
        "subtitle": b.subtitle,
        "button_text": b.button_text,
        "link": b.link,
        "sort_order": b.sort_order,
        "is_active": b.is_active,
        "days_left": left,
        "expired": bool(b.expires_at and b.expires_at <= _now()),
    }


def _apply(b: Banner, body: BannerIn) -> None:
    for field in ("eyebrow", "title", "subtitle", "button_text", "link"):
        value = getattr(body, field)
        if value is not None:
            setattr(b, field, " ".join(value.split()) or None)
    if body.is_active is not None:
        b.is_active = body.is_active
    if body.days is not None:
        b.expires_at = None if body.days == 0 else _now() + timedelta(days=body.days)
    if body.photo is not None:
        if sign_photo(body.photo.model_dump()) != body.photo.sig:
            raise HTTPException(400, "Фотография не наша")
        b.file_id = body.photo.file_id
        b.thumb_file_id = body.photo.thumb_file_id
        b.thumb_w = body.photo.thumb_w
        b.file_unique_id = body.photo.file_unique_id


# ─────────────────────────── Витрина ───────────────────────────

@public_router.get("/banners")
async def public_banners(session: Db):
    """То, что реально показывается: включённое и не просроченное."""
    rows = (await session.scalars(
        select(Banner)
        .where(Banner.is_active.is_(True))
        .order_by(Banner.sort_order, Banner.id))).all()
    now = _now()
    live = [b for b in rows if not b.expires_at or b.expires_at > now]
    return {"items": [_out(b) for b in live]}


@public_router.get("/banners/{public_id}/photo")
async def banner_photo(public_id: uuid_mod.UUID, request: Request,
                       session: Db, redis: Cache, size: str = "full"):
    banner = await session.scalar(
        select(Banner).where(Banner.public_id == public_id))
    if banner is None:
        raise HTTPException(404)

    etag = f'"{banner.file_unique_id}-{size}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304,
                        headers={**CACHE_HEADERS, "ETag": etag})

    file_id = banner.thumb_file_id if (size == "thumb" and banner.thumb_file_id) \
        else banner.file_id
    unique = f"{banner.file_unique_id}_{size}" if size == "thumb" \
        else banner.file_unique_id
    try:
        data = await get_photo_bytes(redis, file_id, unique)
    except Exception:
        raise HTTPException(404) from None
    if data is None:
        raise HTTPException(404)
    return Response(content=data, media_type="image/jpeg",
                    headers={**CACHE_HEADERS, "ETag": etag})


# ─────────────────────────── Панель ───────────────────────────

@router.get("")
async def list_banners(session: Db, admin: Admin):
    rows = (await session.scalars(
        select(Banner).order_by(Banner.sort_order, Banner.id))).all()
    return {"items": [_out(b) for b in rows]}


@router.post("")
async def create_banner(body: BannerIn, session: Db, admin: Admin):
    if body.photo is None:
        raise HTTPException(400, "Нужна фотография")
    count = len((await session.scalars(select(Banner.id))).all())
    if count >= MAX_BANNERS:
        raise HTTPException(400, f"Баннеров уже {MAX_BANNERS}, больше не нужно")

    banner = Banner(file_id="", file_unique_id="", sort_order=count + 1)
    _apply(banner, body)
    session.add(banner)
    await session.commit()
    await session.refresh(banner)
    _log(session, admin, "banner_add", str(banner.public_id), banner.title or "")
    await session.commit()
    return _out(banner)


async def _get(session, public_id: uuid_mod.UUID) -> Banner:
    banner = await session.scalar(
        select(Banner).where(Banner.public_id == public_id))
    if banner is None:
        raise HTTPException(404, "not_found")
    return banner


@router.patch("/{public_id}")
async def update_banner(public_id: uuid_mod.UUID, body: BannerIn, session: Db,
                        admin: Admin):
    banner = await _get(session, public_id)
    _apply(banner, body)
    await session.commit()
    return _out(banner)


@router.post("/{public_id}/move")
async def move_banner(public_id: uuid_mod.UUID, session: Db, admin: Admin,
                      direction: str = "up"):
    """Меняет местами с соседом. Порядок — это очередь показа на главной."""
    rows = (await session.scalars(
        select(Banner).order_by(Banner.sort_order, Banner.id))).all()
    order = list(rows)
    index = next((i for i, b in enumerate(order) if b.public_id == public_id), None)
    if index is None:
        raise HTTPException(404, "not_found")
    swap = index - 1 if direction == "up" else index + 1
    if 0 <= swap < len(order):
        order[index], order[swap] = order[swap], order[index]
    for position, banner in enumerate(order, 1):
        banner.sort_order = position
    await session.commit()
    return {"items": [_out(b) for b in order]}


@router.delete("/{public_id}")
async def delete_banner(public_id: uuid_mod.UUID, session: Db, admin: Admin):
    banner = await _get(session, public_id)
    _log(session, admin, "banner_del", str(public_id), banner.title or "")
    await session.delete(banner)
    await session.commit()
    return {"ok": True}
