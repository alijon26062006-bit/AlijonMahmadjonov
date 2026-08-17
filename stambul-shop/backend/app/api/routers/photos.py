"""Прокси фотографий товара. Публичный — картинки нужны и гостю."""
import uuid as uuid_mod

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import select

from app.api.deps import Cache, Db
from app.db.models import ProductPhoto
from app.services.telegram_files import get_photo_bytes

router = APIRouter(prefix="/api/photos", tags=["photos"])

CACHE_HEADERS = {"Cache-Control": "public, max-age=31536000, immutable"}


@router.get("/{public_id}")
async def photo(public_id: uuid_mod.UUID, request: Request,
                session: Db, redis: Cache, size: str = "full"):
    p = await session.scalar(
        select(ProductPhoto).where(ProductPhoto.public_id == public_id))
    if not p:
        raise HTTPException(404)

    etag = f'"{p.file_unique_id}-{size}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={**CACHE_HEADERS, "ETag": etag})

    file_id = p.thumb_file_id if (size == "thumb" and p.thumb_file_id) else p.file_id
    fu = f"{p.file_unique_id}_{size}" if size == "thumb" else p.file_unique_id
    try:
        data = await get_photo_bytes(redis, file_id, fu)
    except Exception:
        # ни один сбой не должен превращаться в 500 — иначе на витрине
        # пропадают все изображения разом
        raise HTTPException(404) from None
    if data is None:
        raise HTTPException(404)
    return Response(content=data, media_type="image/jpeg",
                    headers={**CACHE_HEADERS, "ETag": etag})
