"""Оформление заказа и «мои заказы»."""
import uuid as uuid_mod

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, Db
from app.config import get_settings
from app.db.models import Order
from app.services import order_service
from app.services.product_service import ShopError

router = APIRouter(prefix="/api/orders", tags=["orders"])


class OrderIn(BaseModel):
    customer_name: str
    phone: str
    city_id: int | None = None
    address: str | None = None
    delivery: str = "courier"
    comment: str | None = None


@router.post("")
async def create(body: OrderIn, session: Db, user: CurrentUser):
    try:
        order = await order_service.create(
            session, user, customer_name=body.customer_name, phone=body.phone,
            city_id=body.city_id, address=body.address,
            delivery=body.delivery, comment=body.comment)
    except ShopError as e:
        raise HTTPException(400, str(e)) from None

    from app.workers.queue import enqueue_new_order
    await enqueue_new_order(order.id)

    s = get_settings()
    out = await order_service.as_dict(session, order)
    out["payment"] = {"phone": s.kaspi_phone, "name": s.kaspi_name,
                      "link": s.kaspi_link} if s.payment_ready else None
    return out


@router.get("/mine")
async def mine(session: Db, user: CurrentUser):
    rows = (await session.scalars(
        select(Order).where(Order.user_id == user.id)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc()).limit(50))).all()
    return {"items": [await order_service.as_dict(session, o) for o in rows]}


@router.get("/{public_id}")
async def one(public_id: uuid_mod.UUID, session: Db, user: CurrentUser):
    order = (await session.scalars(
        select(Order).where(Order.public_id == public_id)
        .options(selectinload(Order.items)))).first()
    if not order or (order.user_id != user.id and not user.is_admin):
        raise HTTPException(404, "not_found")
    return await order_service.as_dict(session, order)
