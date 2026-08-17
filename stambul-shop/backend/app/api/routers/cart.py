"""Корзина покупателя."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.deps import CurrentUser, Db
from app.config import get_settings
from app.services import cart_service
from app.services.product_service import ShopError

router = APIRouter(prefix="/api/cart", tags=["cart"])


class AddIn(BaseModel):
    variant_id: int
    qty: int = 1


class QtyIn(BaseModel):
    qty: int


@router.get("")
async def show(session: Db, user: CurrentUser):
    return await cart_service.contents(session, user)


@router.post("")
async def add(body: AddIn, session: Db, user: CurrentUser):
    try:
        await cart_service.add(session, user, body.variant_id, body.qty,
                               get_settings().cart_max_items)
    except ShopError as e:
        raise HTTPException(400, str(e)) from None
    return await cart_service.contents(session, user)


@router.patch("/{variant_id}")
async def set_qty(variant_id: int, body: QtyIn, session: Db, user: CurrentUser):
    await cart_service.set_qty(session, user, variant_id, body.qty)
    return await cart_service.contents(session, user)


@router.delete("/{variant_id}")
async def remove(variant_id: int, session: Db, user: CurrentUser):
    await cart_service.remove(session, user, variant_id)
    return await cart_service.contents(session, user)


@router.delete("")
async def clear(session: Db, user: CurrentUser):
    await cart_service.clear(session, user)
    return await cart_service.contents(session, user)
