import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import LedgerEntry, Order, User
from ..orders_service import (OrderError, place_telegram_premium, place_telegram_stars, place_topup,
                              sync_order)

router = APIRouter(prefix="/api", tags=["orders"])
TG_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{4,31}$")
STATUS_RU = {"new": "processing", "processing": "processing", "completed": "completed",
             "refunded": "refunded", "failed": "refunded"}


def order_out(o: Order) -> dict:
    st = STATUS_RU.get(o.status, "processing")
    return {"id": o.public_id, "type": o.product_type, "title": o.title, "price": f"{o.price:.2f}",
            "status": st, "created_at": o.created_at.isoformat(), "delivery": o.delivery,
            "message": o.error if st == "refunded" else None}


def _http(e: OrderError) -> HTTPException:
    return HTTPException(e.status, str(e))


class TopupIn(BaseModel):
    category_id: str = Field(min_length=1, max_length=128)
    offer_id: str = Field(min_length=1, max_length=128)
    fields: dict[str, str] = Field(default_factory=dict)
    expected_price: Decimal | None = Field(default=None, ge=0)


class TgBase(BaseModel):
    username: str
    expected_price: Decimal | None = Field(default=None, ge=0)

    @field_validator("username")
    @classmethod
    def _u(cls, v: str) -> str:
        v = v.strip().lstrip("@")
        if not TG_RE.match(v):
            raise ValueError("Username Telegram: от 5 символов, латиница, цифры и _, начинается с буквы")
        return v


class StarsIn(TgBase):
    quantity: int = Field(ge=1, le=1_000_000)


class PremiumIn(TgBase):
    months: int


@router.post("/orders/topup", status_code=201)
def order_topup(data: TopupIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        return order_out(place_topup(db, user.id, data.category_id, data.offer_id, data.fields, data.expected_price))
    except OrderError as e:
        raise _http(e)


@router.post("/orders/telegram-stars", status_code=201)
def order_stars(data: StarsIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        return order_out(place_telegram_stars(db, user.id, data.username, data.quantity, data.expected_price))
    except OrderError as e:
        raise _http(e)


@router.post("/orders/telegram-premium", status_code=201)
def order_premium(data: PremiumIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        return order_out(place_telegram_premium(db, user.id, data.username, data.months, data.expected_price))
    except OrderError as e:
        raise _http(e)


@router.get("/orders")
def my_orders(page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=100),
              status: str | None = None, type: str | None = None, q: str | None = Query(None, max_length=64),
              user: User = Depends(current_user), db: Session = Depends(get_db)):
    cond = [Order.user_id == user.id]
    if status == "processing":
        cond.append(Order.status.in_(("new", "processing")))
    elif status == "refunded":
        cond.append(Order.status.in_(("refunded", "failed")))
    elif status:
        cond.append(Order.status == status)
    if type:
        cond.append(Order.product_type == type)
    if q:
        like = f"%{q.strip()}%"
        cond.append(or_(Order.public_id.ilike(like), Order.title.ilike(like)))
    total = db.scalar(select(func.count()).select_from(Order).where(*cond))
    rows = db.scalars(select(Order).where(*cond).order_by(Order.created_at.desc(), Order.id.desc())
                      .offset((page - 1) * limit).limit(limit)).all()
    return {"items": [order_out(o) for o in rows], "total": total, "page": page, "limit": limit}


@router.get("/orders/{public_id}")
def my_order(public_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    o = db.scalar(select(Order).where(Order.public_id == public_id, Order.user_id == user.id))
    if o is None:
        raise HTTPException(404, "Заказ не найден")
    stale = o.last_sync_at is None or o.last_sync_at.replace(tzinfo=o.last_sync_at.tzinfo or timezone.utc) \
        < datetime.now(timezone.utc) - timedelta(seconds=10)
    if o.status in ("new", "processing") and not o.needs_review and stale:
        o = sync_order(db, o.id)
    return order_out(o)


@router.get("/balance")
def my_balance(page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=100),
               user: User = Depends(current_user), db: Session = Depends(get_db)):
    total = db.scalar(select(func.count()).select_from(LedgerEntry).where(LedgerEntry.user_id == user.id))
    rows = db.scalars(select(LedgerEntry).where(LedgerEntry.user_id == user.id)
                      .order_by(LedgerEntry.id.desc()).offset((page - 1) * limit).limit(limit)).all()
    db.refresh(user)
    return {"balance": f"{user.balance:.4f}", "total": total, "page": page, "limit": limit,
            "items": [{"id": e.id, "kind": e.kind, "reason": e.reason, "amount": f"{e.amount:.4f}",
                       "balance_after": f"{e.balance_after:.4f}", "ref": e.ref, "note": e.note,
                       "created_at": e.created_at.isoformat()} for e in rows]}
