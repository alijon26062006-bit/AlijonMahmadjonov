from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import admin_user
from ..settings_store import get_markup, set_markup
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


@router.post("/cache/clear", status_code=204)
def clear_cache():
    cache.clear()
