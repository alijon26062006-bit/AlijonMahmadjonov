"""Избранное покупателя."""
import uuid as uuid_mod

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, Db
from app.db.models import Favorite, P_ACTIVE, P_OUT, Product

router = APIRouter(prefix="/api/favorites", tags=["favorites"])


@router.get("/ids")
async def ids(session: Db, user: CurrentUser):
    rows = (await session.execute(
        select(Product.public_id).join(Favorite, Favorite.product_id == Product.id)
        .where(Favorite.user_id == user.id))).all()
    return {"ids": [str(r[0]) for r in rows]}


@router.get("")
async def listing(session: Db, user: CurrentUser):
    from app.api.routers.catalog import card
    rows = (await session.scalars(
        select(Product).join(Favorite, Favorite.product_id == Product.id)
        .where(Favorite.user_id == user.id,
               Product.status.in_((P_ACTIVE, P_OUT)))
        .options(selectinload(Product.photos), selectinload(Product.variants))
        .order_by(Favorite.created_at.desc()))).all()
    return {"items": [card(p) for p in rows]}


@router.put("/{public_id}")
async def add(public_id: uuid_mod.UUID, session: Db, user: CurrentUser):
    product = await session.scalar(
        select(Product).where(Product.public_id == public_id))
    if not product:
        raise HTTPException(404, "not_found")
    exists = await session.scalar(
        select(Favorite).where(Favorite.user_id == user.id,
                               Favorite.product_id == product.id))
    if not exists:
        session.add(Favorite(user_id=user.id, product_id=product.id))
        await session.commit()
    return {"ok": True}


@router.delete("/{public_id}")
async def remove(public_id: uuid_mod.UUID, session: Db, user: CurrentUser):
    product = await session.scalar(
        select(Product).where(Product.public_id == public_id))
    if product:
        await session.execute(
            Favorite.__table__.delete().where(Favorite.user_id == user.id,
                                              Favorite.product_id == product.id))
        await session.commit()
    return {"ok": True}
