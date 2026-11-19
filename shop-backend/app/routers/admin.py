from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import admin_user
from ..models import Order, User
from ..orders_service import FINAL, _lock_order, _refund_locked, admin_adjust_balance, sync_order
from ..settings_store import (get_limits, get_markup, sales_enabled, set_limits, set_markup,
                              set_sales_enabled)
from ..supplier import SupplierError, cache, get_supplier

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(admin_user)])


@router.get("/supplier/status")
def supplier_status():
    """Is the supplier key working, is the subscription active, how much balance is left."""
    try:
        me = get_supplier().me()
        bal = get_supplier().balance()
    except SupplierError as e:
        return {"ok": False, "error": str(e), "code": e.code}
    return {"ok": True, "plan": me.get("plan"), "subscription_active": me.get("subscriptionActive"),
            "plan_expires_at": me.get("planExpiresAt"), "auto_renew": me.get("planAutoRenew"),
            "balance": bal.get("balance"), "currency": bal.get("currency")}


class MarkupIn(BaseModel):
    percent: Decimal = Field(ge=0, le=500)


@router.get("/settings/markup")
def get_markup_route(db: Session = Depends(get_db)):
    return {"percent": str(get_markup(db))}


@router.put("/settings/markup")
def put_markup(data: MarkupIn, db: Session = Depends(get_db)):
    set_markup(db, data.percent)
    return {"percent": str(get_markup(db))}


class SalesIn(BaseModel):
    enabled: bool


@router.get("/settings/sales")
def get_sales(db: Session = Depends(get_db)):
    return {"enabled": sales_enabled(db)}


@router.put("/settings/sales")
def put_sales(data: SalesIn, db: Session = Depends(get_db)):
    """The «stop sales» switch."""
    set_sales_enabled(db, data.enabled)
    return {"enabled": sales_enabled(db)}


class LimitsIn(BaseModel):
    max_order_usd: Decimal = Field(gt=0, le=100000)
    daily_user_usd: Decimal = Field(gt=0, le=1000000)


@router.get("/settings/limits")
def get_limits_route(db: Session = Depends(get_db)):
    return {k: str(v) for k, v in get_limits(db).items()}


@router.put("/settings/limits")
def put_limits(data: LimitsIn, db: Session = Depends(get_db)):
    set_limits(db, data.max_order_usd, data.daily_user_usd)
    return {k: str(v) for k, v in get_limits(db).items()}


@router.post("/cache/clear", status_code=204)
def clear_cache():
    cache.clear()


# ---------- orders ----------

def admin_order_out(o: Order) -> dict:
    return {"id": o.public_id, "user_id": o.user_id, "type": o.product_type, "title": o.title,
            "status": o.status, "cost": f"{o.cost:.4f}", "price": f"{o.price:.4f}",
            "profit": f"{(o.price - o.cost):.4f}", "supplier_order_id": o.supplier_order_id,
            "needs_check": o.needs_check, "needs_review": o.needs_review, "error": o.error,
            "request": o.request, "supplier_response": o.supplier_response, "delivery": o.delivery,
            "sync_attempts": o.sync_attempts, "created_at": o.created_at.isoformat()}


def _get_order(db: Session, public_id: str) -> Order:
    o = db.scalar(select(Order).where(Order.public_id == public_id))
    if o is None:
        raise HTTPException(404, "Заказ не найден")
    return o


@router.get("/orders")
def admin_orders(page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100), status: str | None = None,
                 needs_review: bool | None = None, db: Session = Depends(get_db)):
    cond = []
    if status:
        cond.append(Order.status == status)
    if needs_review is not None:
        cond.append(Order.needs_review.is_(needs_review))
    total = db.scalar(select(func.count()).select_from(Order).where(*cond))
    rows = db.scalars(select(Order).where(*cond).order_by(Order.id.desc()).offset((page - 1) * limit).limit(limit)).all()
    return {"items": [admin_order_out(o) for o in rows], "total": total, "page": page, "limit": limit}


@router.post("/orders/{public_id}/sync")
def admin_sync(public_id: str, db: Session = Depends(get_db)):
    return admin_order_out(sync_order(db, _get_order(db, public_id).id))


class NoteIn(BaseModel):
    note: str = Field(min_length=3, max_length=200)


@router.post("/orders/{public_id}/refund")
def admin_refund(public_id: str, data: NoteIn, db: Session = Depends(get_db)):
    """Manual refund after checking with the supplier that the order really failed."""
    o = _lock_order(db, _get_order(db, public_id).id)
    if o.status in FINAL:
        db.rollback()
        raise HTTPException(409, f"Заказ уже в статусе {o.status}")
    _refund_locked(db, o, f"Возврат администратором: {data.note}")
    o.needs_review = False
    db.commit()
    return admin_order_out(o)


@router.post("/orders/{public_id}/complete")
def admin_complete(public_id: str, data: NoteIn, db: Session = Depends(get_db)):
    """Mark as delivered after checking with the supplier."""
    o = _lock_order(db, _get_order(db, public_id).id)
    if o.status in FINAL:
        db.rollback()
        raise HTTPException(409, f"Заказ уже в статусе {o.status}")
    o.status, o.needs_review, o.needs_check, o.error = "completed", False, False, data.note
    db.commit()
    return admin_order_out(o)


# ---------- users & money ----------

class BalanceIn(BaseModel):
    amount: Decimal = Field(ne=0, ge=-100000, le=100000)
    note: str = Field(min_length=3, max_length=200)


@router.post("/users/{user_id}/balance")
def adjust_balance(user_id: int, data: BalanceIn, db: Session = Depends(get_db)):
    if db.get(User, user_id) is None:
        raise HTTPException(404, "Пользователь не найден")
    try:
        e = admin_adjust_balance(db, user_id, data.amount, data.note)
    except Exception as ex:
        db.rollback()
        if ex.__class__.__name__ == "InsufficientFunds":
            raise HTTPException(409, "На балансе меньше, чем вы списываете")
        raise
    return {"balance": f"{e.balance_after:.4f}"}


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    done = select(func.count(), func.coalesce(func.sum(Order.price), 0), func.coalesce(func.sum(Order.cost), 0)) \
        .where(Order.status == "completed")
    n, revenue, cost = db.execute(done).one()
    review = db.scalar(select(func.count()).select_from(Order).where(Order.needs_review.is_(True),
                                                                      Order.status.in_(("new", "processing"))))
    return {"completed_orders": n, "revenue": f"{Decimal(revenue):.4f}", "cost": f"{Decimal(cost):.4f}",
            "profit": f"{Decimal(revenue) - Decimal(cost):.4f}", "orders_need_review": review}
