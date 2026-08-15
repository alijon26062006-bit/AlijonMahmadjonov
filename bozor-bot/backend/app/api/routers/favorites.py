"""Избранное."""
import uuid as uuid_mod

from fastapi import APIRouter, HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, Db
from app.db.models import Favorite, Listing

router = APIRouter(prefix="/api/favorites", tags=["favorites"])


async def _listing_by_uuid(session, public_id):
    listing = await session.scalar(
        select(Listing).where(Listing.public_id == public_id))
    if not listing:
        raise HTTPException(404, "not_found")
    return listing


@router.get("")
async def list_favorites(session: Db, user: CurrentUser):
    from app.api.routers.listings import _card, _names
    rows = (await session.scalars(
        select(Listing).join(Favorite, Favorite.listing_id == Listing.id)
        .where(Favorite.user_id == user.id)
        .options(selectinload(Listing.photos))
        .order_by(Favorite.created_at.desc()).limit(100))).all()
    cities, districts = await _names(session, rows)
    return {"items": [_card(l, cities, districts) for l in rows]}


@router.get("/ids")
async def favorite_ids(session: Db, user: CurrentUser):
    rows = (await session.execute(
        select(Listing.public_id).join(Favorite, Favorite.listing_id == Listing.id)
        .where(Favorite.user_id == user.id))).scalars().all()
    return {"ids": [str(x) for x in rows]}


@router.put("/{public_id}")
async def add(public_id: uuid_mod.UUID, session: Db, user: CurrentUser):
    listing = await _listing_by_uuid(session, public_id)
    await session.execute(
        pg_insert(Favorite).values(user_id=user.id, listing_id=listing.id)
        .on_conflict_do_nothing())
    await session.execute(update(Listing).where(Listing.id == listing.id)
                          .values(favorites_count=Listing.favorites_count + 1))
    await session.commit()
    return {"ok": True}


@router.delete("/{public_id}")
async def remove(public_id: uuid_mod.UUID, session: Db, user: CurrentUser):
    listing = await _listing_by_uuid(session, public_id)
    await session.execute(
        delete(Favorite).where(Favorite.user_id == user.id,
                               Favorite.listing_id == listing.id))
    await session.commit()
    return {"ok": True}
