"""Справочники: города, районы, бренды, модели."""
from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import Db
from app.db.models import Brand, City, District, VehicleModel

router = APIRouter(prefix="/api/dicts", tags=["dicts"])


@router.get("/cities")
async def cities(session: Db):
    rows = (await session.scalars(
        select(City).where(City.is_active).order_by(City.sort_order))).all()
    return {"items": [{"id": c.id, "name": c.name, "lat": c.lat, "lon": c.lon}
                      for c in rows]}


@router.get("/districts")
async def districts(city_id: int, session: Db):
    rows = (await session.scalars(
        select(District).where(District.city_id == city_id)
        .order_by(District.name))).all()
    return {"items": [{"id": d.id, "name": d.name} for d in rows]}


@router.get("/brands")
async def brands(area: str, session: Db):
    rows = (await session.scalars(
        select(Brand).where(Brand.areas.any(area[:24]))
        .order_by(Brand.sort_order, Brand.name))).all()
    return {"items": [{"name": b.name, "popular": b.popular} for b in rows]}


@router.get("/models")
async def models(brand: str, session: Db, area: str = "cars"):
    rows = (await session.scalars(
        select(VehicleModel).join(Brand)
        .where(Brand.name == brand[:80], VehicleModel.area == area[:24])
        .order_by(VehicleModel.sort_order))).all()
    return {"items": [{"name": m.name} for m in rows]}
