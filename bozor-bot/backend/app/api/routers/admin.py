"""Админ-панель: очередь модерации, жалобы, пользователи, справочники, статистика.

Права проверяются по флагу в базе, а не только по токену: если админа
разжаловали, доступ пропадает сразу, не дожидаясь истечения сессии.
"""
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, Db
from app.db.models import (
    ST_APPROVED, ST_ARCHIVED, ST_PENDING, ST_REJECTED, Brand, City, District,
    Listing, ModerationLog, Report, User, VehicleModel,
)
from app.schemas_engine.registry import get_schema
from app.services import moderation_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


async def require_admin(user: CurrentUser) -> User:
    if not user.is_admin:
        raise HTTPException(403, "forbidden")
    return user


Admin = Annotated[User, Depends(require_admin)]


# ─────────────────────────── Статистика ───────────────────────────

@router.get("/stats")
async def stats(session: Db, admin: Admin):
    day_ago = datetime.utcnow() - timedelta(days=1)
    week_ago = datetime.utcnow() - timedelta(days=7)

    async def count(*conds) -> int:
        return await session.scalar(
            select(func.count()).select_from(Listing).where(*conds)) or 0

    by_category = (await session.execute(
        select(Listing.category_slug, func.count())
        .where(Listing.status == ST_APPROVED)
        .group_by(Listing.category_slug)
        .order_by(func.count().desc()).limit(20))).all()

    return {
        "pending": await count(Listing.status == ST_PENDING),
        "approved": await count(Listing.status == ST_APPROVED),
        "rejected": await count(Listing.status == ST_REJECTED),
        "archived": await count(Listing.status == ST_ARCHIVED),
        "today": await count(Listing.created_at > day_ago),
        "week": await count(Listing.created_at > week_ago),
        "users": await session.scalar(select(func.count()).select_from(User)) or 0,
        "users_week": await session.scalar(
            select(func.count()).select_from(User)
            .where(User.created_at > week_ago)) or 0,
        "banned": await session.scalar(
            select(func.count()).select_from(User).where(User.is_banned)) or 0,
        "reports_new": await session.scalar(
            select(func.count()).select_from(Report)
            .where(Report.status == "new")) or 0,
        "by_category": [
            {"slug": slug,
             "title": (s.title if (s := get_schema(slug)) else slug),
             "count": n}
            for slug, n in by_category
        ],
    }


# ─────────────────────────── Очередь ───────────────────────────

@router.get("/listings")
async def queue(session: Db, admin: Admin,
                status: str = ST_PENDING, limit: int = 30, offset: int = 0):
    rows = (await session.scalars(
        select(Listing).where(Listing.status == status)
        .options(selectinload(Listing.photos))
        .order_by(Listing.created_at.asc())
        .limit(min(limit, 100)).offset(offset))).all()

    author_ids = {l.author_id for l in rows}
    authors = {u.id: u for u in (await session.scalars(
        select(User).where(User.id.in_(author_ids)))).all()} if author_ids else {}
    cities = {c.id: c.name for c in (await session.scalars(select(City))).all()}
    districts = {d.id: d.name for d in (await session.scalars(select(District))).all()}

    total = await session.scalar(
        select(func.count()).select_from(Listing).where(Listing.status == status)) or 0

    def item(l: Listing) -> dict:
        author = authors.get(l.author_id)
        schema = get_schema(l.category_slug)
        return {
            "id": l.id,
            "public_id": str(l.public_id),
            "title": l.title,
            "category": schema.title if schema else l.category_slug,
            "price": float(l.price), "currency": l.currency,
            "description": l.description,
            "city": cities.get(l.city_id), "district": districts.get(l.district_id),
            "address": l.address,
            "created_at": l.created_at.isoformat() if l.created_at else None,
            "flag_note": l.flag_note,
            "reject_reason": l.reject_reason,
            "photos": [{"thumb": f"/api/photos/{p.public_id}?size=thumb",
                        "full": f"/api/photos/{p.public_id}"} for p in l.photos],
            "attrs": l.attrs,
            "author": {
                "id": author.id if author else None,
                "tg_id": author.tg_id if author else None,
                "name": author.first_name if author else "?",
                "username": author.username if author else None,
                "is_banned": author.is_banned if author else False,
            },
        }

    return {"items": [item(l) for l in rows], "total": total}


class RejectIn(BaseModel):
    reason: str


@router.post("/listings/{listing_id}/approve")
async def approve(listing_id: int, session: Db, admin: Admin):
    try:
        await moderation_service.approve(session, listing_id, admin)
    except moderation_service.AlreadyHandled as e:
        raise HTTPException(409, f"already:{e.status}") from None
    return {"ok": True}


@router.post("/listings/{listing_id}/reject")
async def reject(listing_id: int, body: RejectIn, session: Db, admin: Admin):
    reason = body.reason.strip()
    if not reason:
        raise HTTPException(400, "reason_required")
    try:
        await moderation_service.reject(session, listing_id, admin, reason)
    except moderation_service.AlreadyHandled as e:
        raise HTTPException(409, f"already:{e.status}") from None
    return {"ok": True}


@router.post("/listings/{listing_id}/archive")
async def archive(listing_id: int, session: Db, admin: Admin):
    listing = await session.get(Listing, listing_id)
    if not listing:
        raise HTTPException(404, "not_found")
    listing.status = ST_ARCHIVED
    session.add(ModerationLog(listing_id=listing.id, admin_id=admin.id,
                              action="archive"))
    await session.commit()
    return {"ok": True}


# ─────────────────────────── Жалобы ───────────────────────────

@router.get("/reports")
async def reports(session: Db, admin: Admin, status: str = "new"):
    rows = (await session.execute(
        select(Report, Listing.title, Listing.public_id, Listing.status)
        .join(Listing, Listing.id == Report.listing_id)
        .where(Report.status == status)
        .order_by(Report.created_at.desc()).limit(100))).all()
    return {"items": [
        {"id": r.id, "reason": r.reason, "comment": r.comment,
         "created_at": r.created_at.isoformat() if r.created_at else None,
         "listing_id": r.listing_id, "listing_title": title,
         "listing_public_id": str(pub), "listing_status": st}
        for r, title, pub, st in rows
    ]}


@router.post("/reports/{report_id}/resolve")
async def resolve_report(report_id: int, session: Db, admin: Admin,
                         accept: bool = False):
    report = await session.get(Report, report_id)
    if not report:
        raise HTTPException(404, "not_found")
    report.status = "accepted" if accept else "dismissed"
    if accept:      # жалоба обоснована — снимаем объявление
        listing = await session.get(Listing, report.listing_id)
        if listing:
            listing.status = ST_ARCHIVED
            session.add(ModerationLog(listing_id=listing.id, admin_id=admin.id,
                                      action="archive", reason="по жалобе"))
    await session.commit()
    return {"ok": True}


# ─────────────────────────── Пользователи ───────────────────────────

@router.get("/users")
async def users(session: Db, admin: Admin, q: str = "", limit: int = 50):
    stmt = select(User).order_by(User.created_at.desc()).limit(min(limit, 200))
    if q.strip():
        like = f"%{q.strip()[:50]}%"
        conds = [User.first_name.ilike(like), User.username.ilike(like)]
        if q.strip().lstrip("-").isdigit():
            conds.append(User.tg_id == int(q.strip()))
        stmt = stmt.where(or_(*conds))
    rows = (await session.scalars(stmt)).all()

    counts = dict((await session.execute(
        select(Listing.author_id, func.count())
        .where(Listing.author_id.in_([u.id for u in rows]))
        .group_by(Listing.author_id))).all()) if rows else {}

    return {"items": [
        {"id": u.id, "tg_id": u.tg_id, "name": u.first_name,
         "username": u.username, "phone": u.phone,
         "is_admin": u.is_admin, "is_banned": u.is_banned,
         "listings": counts.get(u.id, 0),
         "created_at": u.created_at.isoformat() if u.created_at else None}
        for u in rows
    ]}


@router.post("/users/{user_id}/ban")
async def ban(user_id: int, session: Db, admin: Admin, banned: bool = True):
    user = await moderation_service.set_ban(session, user_id, admin, banned)
    if user is None:
        raise HTTPException(400, "cannot_ban")
    return {"ok": True, "is_banned": user.is_banned}


# ─────────────────────────── Справочники ───────────────────────────

class CityIn(BaseModel):
    name: str
    lat: float | None = None
    lon: float | None = None


@router.post("/dicts/cities")
async def add_city(body: CityIn, session: Db, admin: Admin):
    name = body.name.strip()[:100]
    if not name:
        raise HTTPException(400, "name_required")
    if await session.scalar(select(City).where(City.name == name)):
        raise HTTPException(409, "exists")
    city = City(name=name, lat=body.lat, lon=body.lon, sort_order=100)
    session.add(city)
    await session.commit()
    return {"id": city.id, "name": city.name}


@router.patch("/dicts/cities/{city_id}")
async def toggle_city(city_id: int, session: Db, admin: Admin, active: bool = True):
    city = await session.get(City, city_id)
    if not city:
        raise HTTPException(404, "not_found")
    city.is_active = active
    await session.commit()
    return {"ok": True, "is_active": city.is_active}


class DistrictIn(BaseModel):
    city_id: int
    name: str


@router.post("/dicts/districts")
async def add_district(body: DistrictIn, session: Db, admin: Admin):
    name = body.name.strip()[:100]
    if not name:
        raise HTTPException(400, "name_required")
    if await session.scalar(select(District).where(District.city_id == body.city_id,
                                                   District.name == name)):
        raise HTTPException(409, "exists")
    d = District(city_id=body.city_id, name=name)
    session.add(d)
    await session.commit()
    return {"id": d.id, "name": d.name}


class BrandIn(BaseModel):
    name: str
    areas: list[str]


@router.post("/dicts/brands")
async def add_brand(body: BrandIn, session: Db, admin: Admin):
    name = body.name.strip()[:80]
    areas = [a.strip()[:24] for a in body.areas if a.strip()]
    if not name or not areas:
        raise HTTPException(400, "name_and_area_required")
    existing = await session.scalar(select(Brand).where(Brand.name == name))
    if existing:      # бренд может работать в нескольких областях — дополняем
        existing.areas = sorted(set(existing.areas) | set(areas))
        await session.commit()
        return {"id": existing.id, "name": existing.name, "areas": existing.areas}
    brand = Brand(name=name, areas=areas, popular=False, sort_order=100)
    session.add(brand)
    await session.commit()
    return {"id": brand.id, "name": brand.name, "areas": brand.areas}


class ModelIn(BaseModel):
    brand: str
    name: str
    area: str = "cars"


@router.post("/dicts/models")
async def add_model(body: ModelIn, session: Db, admin: Admin):
    brand = await session.scalar(select(Brand).where(Brand.name == body.brand.strip()))
    if not brand:
        raise HTTPException(404, "brand_not_found")
    name = body.name.strip()[:80]
    if not name:
        raise HTTPException(400, "name_required")
    if await session.scalar(select(VehicleModel).where(
            VehicleModel.brand_id == brand.id, VehicleModel.name == name)):
        raise HTTPException(409, "exists")
    m = VehicleModel(brand_id=brand.id, name=name, area=body.area[:24], sort_order=100)
    session.add(m)
    await session.commit()
    return {"id": m.id, "name": m.name}


# ─────────────────────────── Журнал ───────────────────────────

@router.get("/log")
async def moderation_log(session: Db, admin: Admin, limit: int = 50):
    rows = (await session.execute(
        select(ModerationLog, User.first_name, User.username)
        .outerjoin(User, User.id == ModerationLog.admin_id)
        .order_by(ModerationLog.created_at.desc()).limit(min(limit, 200)))).all()
    return {"items": [
        {"id": m.id, "action": m.action, "reason": m.reason,
         "listing_id": m.listing_id,
         "admin": username or name or "?",
         "created_at": m.created_at.isoformat() if m.created_at else None}
        for m, name, username in rows
    ]}
