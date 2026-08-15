"""Прокси фотографий. Публичный (для <img>), но только для одобренных объявлений."""
import uuid as uuid_mod

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import select

from app.api.deps import Cache, Db
from app.db.models import ST_APPROVED, Listing, ListingPhoto
from app.services.telegram_files import get_photo_bytes

router = APIRouter(prefix="/api/photos", tags=["photos"])

CACHE_HEADERS = {"Cache-Control": "public, max-age=31536000, immutable"}


@router.get("/{public_id}")
async def photo(public_id: uuid_mod.UUID, request: Request,
                session: Db, redis: Cache, size: str = "full"):
    row = (await session.execute(
        select(ListingPhoto, Listing.status, Listing.author_id)
        .join(Listing, Listing.id == ListingPhoto.listing_id)
        .where(ListingPhoto.public_id == public_id))).first()
    if not row:
        raise HTTPException(404)
    p, status, _author = row
    if status not in (ST_APPROVED, "pending", "occupied", "sold"):
        raise HTTPException(404)

    etag = f'"{p.file_unique_id}-{size}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={**CACHE_HEADERS, "ETag": etag})

    file_id = p.thumb_file_id if (size == "thumb" and p.thumb_file_id) else p.file_id
    fu = f"{p.file_unique_id}_{size}" if size == "thumb" else p.file_unique_id
    try:
        data = await get_photo_bytes(redis, file_id, fu)
    except Exception:
        # Ни один сбой не должен превращаться в 500 — иначе на сайте
        # пропадают все изображения разом
        raise HTTPException(404) from None
    if data is None:
        raise HTTPException(404)
    return Response(content=data, media_type="image/jpeg",
                    headers={**CACHE_HEADERS, "ETag": etag})
