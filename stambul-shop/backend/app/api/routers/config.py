"""Публичные настройки магазина для клиента."""
from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import Db
from app.config import get_settings
from app.db.models import Brand, City

router = APIRouter(prefix="/api", tags=["config"])


@router.get("/config")
async def public_config(session: Db):
    s = get_settings()
    cities = (await session.scalars(
        select(City).order_by(City.sort_order, City.name))).all()
    return {
        "shop_name": s.shop_name,
        "tagline": s.shop_tagline,
        "currency_sign": s.currency_sign,
        "bot_link": s.bot_link if s.bot_username else None,
        "google_client_id": s.google_client_id,
        "require_auth_to_browse": s.require_auth_to_browse,
        "site_url": s.site_url,
        "support": f"https://t.me/{s.support_username}" if s.support_username else None,
        "uploads_enabled": bool(s.storage_chat_id),
        "max_photos": s.max_photos,
        "delivery": {
            "city_price": s.delivery_city_price,
            "country_price": s.delivery_country_price,
            "free_from": s.free_delivery_from,
            "pickup_address": s.pickup_address,
        },
        "payment_ready": s.payment_ready,
        "cities": [{"id": c.id, "name": c.name, "days": c.delivery_days}
                   for c in cities],
    }


@router.get("/brands")
async def brands(session: Db, area: str = ""):
    query = select(Brand).order_by(Brand.sort_order, Brand.name)
    if area:
        query = query.where(Brand.areas.any(area))
    rows = (await session.scalars(query)).all()
    return {"items": [{"id": b.id, "name": b.name} for b in rows]}
