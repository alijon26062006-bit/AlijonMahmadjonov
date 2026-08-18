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

    # Какую версию показывать — решает один флаг. Оригинал при этом никуда
    # не девается: переключатель в панели возвращает его мгновенно.
    if p.use_processed and p.proc_file_id:
        full_id, thumb_id = p.proc_file_id, p.proc_thumb_file_id
        unique = p.proc_file_unique_id or p.file_unique_id
    else:
        full_id, thumb_id = p.file_id, p.thumb_file_id
        unique = p.file_unique_id

    etag = f'"{unique}-{size}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={**CACHE_HEADERS, "ETag": etag})

    file_id = thumb_id if (size == "thumb" and thumb_id) else full_id
    fu = f"{unique}_{size}" if size == "thumb" else unique
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
